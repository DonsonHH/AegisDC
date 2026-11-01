"""Policy-owned causal observation state; masked events never enter its history."""
from copy import deepcopy
import numpy as np

from .active_inspection import measured_anomaly
from .estimation import ObservationState
from .facility_observation import eligible

FIELDS = {'thermal': 'temperature_c', 'cooling': 'pod_flow_kg_s',
          'electrical': 'contact_temperature_c', 'control': 'controller_sensor_error_c'}


def event_key(event):
    return int(event['agent']), int(event['task']), float(event['time_s'])


class MeasurementState:
    def __init__(self, config, tasks, predictor):
        self.config, self.tasks, self.predictor = config, tuple(tasks), predictor
        self.state = ObservationState(config)
        self.qualified = {}
        self.frames, self.frame_times, self.tool_times = [], [], []
        self.raw_prior = np.full(config.racks, 50.)
        self.nominal_at_prior = np.full(config.racks, 50.)
        self.prior_time = -1.
        self.now = 0.
        self.packet = None
        self.updates = []
        self.last_update = None
        self.diagnostic = {}  # Visible residual cues, not synthetic sensor values.

    def temperatures(self, tool='direct_priority'):
        return self._temperature_view(self.state.observer, self.now, tool)

    def _temperature_view(self, obs, now, tool):
        nominal = obs.predicted_temperature.copy()
        if tool == 'nominal_only' or self.prior_time < 0:
            return nominal
        if tool != 'direct_priority':
            raise ValueError('Unregistered state tool')
        result = self.raw_prior + nominal - self.nominal_at_prior
        stamps = obs.temperature_stamp
        direct = (stamps >= 0) & ((stamps >= self.prior_time) | (now - stamps <= 30))
        result[direct] = nominal[direct]
        return result

    def quantity(self, j):
        task = self.tasks[j]
        obs = self.state.observer
        if task.kind == 'thermal':
            return float(self.temperatures()[task.index])
        if task.kind == 'cooling':
            return float(obs.last_flow[task.index]) if obs.flow_stamp[task.index] >= 0 else float(self.packet['pod_pump_command'][task.index] * self.config.nominal_rack_flow_kg_s * 8)
        if task.kind == 'electrical':
            return float(obs.last_contact[task.index])
        return self.qualified.get(j, {}).get('value')

    def advance(self, packet, events, *, blocked=None):
        now = float(packet['time_s'])
        if now != self.now + 5.:
            raise ValueError('One real5s observation advance, no duplicate physical steps')
        # Filter BEFORE reading measurement/alarm or constructing model inputs.
        visible = [e for e in events if event_key(e) != blocked]
        completions = []
        for e in visible:
            task = self.tasks[e['task']]
            if e['time_s'] != now or not e['calibrated'] or not eligible(e['role'], task):
                raise ValueError('Only current qualified real references')
            value = e['measurement'][FIELDS[task.kind]]
            if not np.isfinite(value):
                raise ValueError('Finite reference required')
            completions.append({'time_s': now, 'completion': (task, e['role'], e['measurement'], now)})
        before = None
        if visible:
            preview = deepcopy(self.state)
            preview.update(packet, [])
            before = preview.observer.predicted_temperature.copy()
        self.state.update(packet, completions)
        self.now, self.packet = now, deepcopy(packet)
        current = []
        for e in visible:
            j, task = e['task'], self.tasks[e['task']]
            value = float(e['measurement'][FIELDS[task.kind]])
            if task.kind == 'thermal':
                prior = float(before[task.index])
            elif task.kind == 'cooling':
                prior = float(preview.observer.last_flow[task.index]) if preview.observer.flow_stamp[task.index] >= 0 else float(packet['pod_pump_command'][task.index] * self.config.nominal_rack_flow_kg_s * 8)
            elif task.kind == 'electrical':
                prior = float(preview.observer.last_contact[task.index])
            else:
                prior = self.qualified.get(j, {}).get('value')
            self.qualified[j] = {'value': value, 'time_s': now, 'event_id': list(event_key(e)),
                'kind': task.kind, 'source': 'qualified_reference',
                'alarm': bool(measured_anomaly(task, e['measurement']))}
            update = dict(self.qualified[j], task=j, prior_same_time_nominal=prior,
                          residual=value - prior if prior is not None else None,
                          prior_same_time_estimate=float(self._temperature_view(preview.observer,now,'direct_priority')[task.index]) if task.kind=='thermal' else prior)
            update['innovation'] = value - update['prior_same_time_estimate'] if update['prior_same_time_estimate'] is not None else None
            if task.kind == 'thermal':
                self.diagnostic[task.index] = {'time_s': now, 'residual_c': value - prior,
                    'source_event': list(event_key(e)), 'relation': 'rack_heat_balance_to_its_cooling_branch'}
            current.append(update)
        self.updates.extend(current)
        self.last_update = {'time_s': now, 'visible_references': current}
        if now % 30 == 0:
            self.frames.append(self.state.features(packet).copy())
            self.frames = self.frames[-4:]
            self.frame_times.append(now)
            self.frame_times = self.frame_times[-4:]
            padded = [self.frames[0]] * (4 - len(self.frames)) + self.frames
            context = np.concatenate(padded, axis=-1)
            self.raw_prior = np.asarray(self.predictor(context), dtype=float)
            if self.raw_prior.shape != (self.config.racks,) or not np.isfinite(self.raw_prior).all():
                raise ValueError('Frozen predictor output')
            self.nominal_at_prior = self.state.observer.predicted_temperature.copy()
            self.prior_time = now
            self.tool_times.append(now)

    def project_temperatures(self, delta_s, tool='direct_priority'):
        """Existing nominal heat balance, held CURRENT commands; no past rewrite."""
        c, obs = self.config, self.state.observer
        temp = self.temperatures(tool)
        flows = self.packet['pod_pump_command'] * c.nominal_rack_flow_kg_s * 8
        known = obs.flow_stamp >= 0
        flows[known] = obs.last_flow[known]
        conductance = c.coldplate_ua_kw_k * (np.maximum(0, np.repeat(flows / 8, 8)) / c.nominal_rack_flow_kg_s) ** .8
        remaining = float(delta_s)
        while remaining > 1e-9:
            step = min(5., remaining)
            temp += step * (self.packet['public_delivered_it_kw'] - conductance *
                (temp - np.repeat(self.packet['secondary_supply_c'], 8)) -
                c.chip_ambient_ua_kw_k * (temp - c.ambient_c)) / c.chip_capacity_kj_k
            remaining -= step
        return temp

    def view(self):
        obs = self.state.observer
        return {'time_s': self.now, 'qualified': deepcopy(self.qualified),
            'nominal_temperature_c': obs.predicted_temperature.tolist(), 'temperature_c': self.temperatures().tolist(),
            'temperature_stamp_s': obs.temperature_stamp.tolist(), 'last_temperature_c': obs.last_temperature.tolist(),
            'flow': obs.last_flow.tolist(), 'flow_stamp_s': obs.flow_stamp.tolist(), 'contact': obs.last_contact.tolist(),
            'sensor_verified': obs.sensor_bias_verified.tolist(), 'velocity': self.state.velocity.tolist(),
            'raw_prior': self.raw_prior.tolist(), 'prior_time_s': self.prior_time,
            'latest_update': deepcopy(self.last_update),
            'frame_times_s': list(self.frame_times), 'frame_values': [f.tolist() for f in self.frames],
            'tool_times_s': list(self.tool_times), 'diagnostic': deepcopy(self.diagnostic)}
