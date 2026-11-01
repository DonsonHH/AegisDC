"""Frozen diagnostic first rule and measurement-sensitive task value; no scope DSL."""
from dataclasses import asdict, dataclass
import numpy as np

from .multistep_workflow import digest


@dataclass(frozen=True)
class MeasurementWorkflow:
    estimate_tool: str = 'direct_priority'
    dependency_evidence: str = 'physical'
    normal_followup: str = 'positive_value'

    def __post_init__(self):
        if self.estimate_tool not in ('direct_priority', 'nominal_only') or self.dependency_evidence not in ('physical', 'own_only') or self.normal_followup not in ('positive_value', 'return_tour'):
            raise ValueError('Registered measurement tools/branches only')

    def to_dict(self):
        return dict(schema='measurement-workflow-v1', **asdict(self))

    @property
    def sha256(self):
        return digest(self.to_dict())

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) != {'schema', *asdict(cls())} or value['schema'] != 'measurement-workflow-v1':
            raise ValueError('Closed measurement workflow')
        return cls(**{k: v for k, v in value.items() if k != 'schema'})


def rank_candidates(state, geometry, workflow):
    obs, now = state.state.observer, state.now
    estimates = state.temperatures(workflow.estimate_tool)
    projects = {}
    results = []
    for g in geometry:
        j, pod, kind = g['task'], g['pod'], g['kind']
        task = state.tasks[j]
        qualified = state.qualified.get(j)
        own_signal, related_signal, relation = 0., 0., None
        if kind == 'thermal':
            eta = g['completion_cost_s']
            if eta not in projects:
                projects[eta] = state.project_temperatures(eta, workflow.estimate_tool)
            value, prediction = float(estimates[task.index]), float(projects[eta][task.index])
            own_signal = max(prediction - 65., 0.) / 20.
            stamp = float(obs.temperature_stamp[task.index])
            direct_available = stamp >= 0
            model_difference = min(abs(float(state.raw_prior[task.index]) - float(obs.predicted_temperature[task.index])) / 20., 1.) if state.prior_time >= 0 else 0.
            source = 'direct_reset_then_nominal' if direct_available and (stamp >= state.prior_time or now - stamp <= 30) else workflow.estimate_tool
        elif kind == 'cooling':
            value = state.quantity(j)
            prediction = value
            own_signal = max(1. - value / 33.6, 0.)
            stamp = float(obs.flow_stamp[pod])
            direct_available = stamp >= 0
            model_difference = 0.
            source = 'observed_flow' if direct_available else 'public_pump_command_nominal_flow'
            # A heat-balance residual is a reason to VERIFY cooling, not a flow
            # observation or a claim that all same-pod devices are faulty.
            cues = [v for rack, v in state.diagnostic.items() if rack // 8 == pod and now - v['time_s'] <= 300]
            if workflow.dependency_evidence == 'physical' and cues:
                cue = max(cues, key=lambda v: max(v['residual_c'], 0.))
                related_signal = max(cue['residual_c'], 0.) / 20.
                if related_signal:
                    relation = dict(kind='rack_heat_balance_to_cooling_verification', source_event=cue['source_event'],
                        equation='P - UA(flow)*(T-T_supply) - ambient_loss = C*dT/dt',
                        interpretation='diagnostic_priority_only_not_a_flow_estimate')
        elif kind == 'electrical':
            value = float(obs.last_contact[pod]);prediction = value
            own_signal = max(value - 60., 0.) / 30.
            stamp = float(qualified['time_s']) if qualified else -1.
            direct_available = qualified is not None
            model_difference = 0.;source = 'qualified_contact' if qualified else 'nominal_contact_initialization'
        else:
            value = qualified['value'] if qualified else None;prediction = value
            own_signal = float(abs(value) > 1.) if value is not None else 0.
            stamp = float(qualified['time_s']) if qualified else -1.
            direct_available = qualified is not None
            model_difference = 0.;source = 'qualified_sensor_error' if qualified else 'unobserved'
        start = pod * 8
        requested = state.packet['public_requested_it_kw'][start:start+8].sum()
        delivered = state.packet['public_delivered_it_kw'][start:start+8].sum()
        gap = max(float(requested - delivered), 0.) / max(float(requested), 1.)
        flow_value = float(obs.last_flow[pod]) if obs.flow_stamp[pod] >= 0 else float(state.packet['pod_pump_command'][pod] * state.config.nominal_rack_flow_kg_s * 8)
        flow_cue = max(1. - flow_value / 33.6, 0.)
        thermal_cue = max(float(estimates[start:start+8].max()) - 65., 0.) / 20.
        cross = max(gap, flow_cue) if kind == 'thermal' else max(gap, thermal_cue) if kind == 'cooling' else 0.
        evidence = min(max(model_difference, cross), 1.)
        age_factor = min((now - stamp) / 300., 1.) if direct_available else 1.
        signal = max(own_signal, related_signal)
        benefit = g['weight'] * signal * g['lead_s'] / 300.
        penalty = .05 * g['shift_s'] / 300.
        row = dict(g, current_estimate=value, estimate_at_finish=prediction, input_cutoff_s=now,
            direct_available=direct_available, direct_time_s=stamp if direct_available else None,
            estimate_source=source, own_signal=own_signal, dependency_signal=related_signal,
            dependency=relation, corrected_signal=signal, value_benefit=benefit,
            value_cost=penalty, value=benefit-penalty, information_age_factor=age_factor,
            model_difference=model_difference, public_cross_signal=cross, diagnostic_evidence=evidence,
            already_alarm=bool(qualified['alarm']) if qualified else False)
        results.append(row)
    for r in results:
        r['affected_safe_tasks'] = [v['task'] for v in results if v['task'] != r['task'] and v['pod'] == r['pod']
            and (r['kind'] == 'cooling' and v['kind'] == 'thermal' or r['kind'] == 'thermal' and v['kind'] == 'cooling')]
        r['diagnostic_value'] = r['information_age_factor'] * r['diagnostic_evidence'] * r['weight'] * min(r['lead_s']/300., 1.) / (1.+r['completion_cost_s']/60.)
    ranked = sorted(results, key=lambda r: (-r['value'], r['task']))
    for position, row in enumerate(ranked, 1):
        row['rank'] = position
    return ranked


def choose_first(rows):
    eligible = [r for r in rows if r['information_age_factor'] > 0 and r['diagnostic_evidence'] > 0
                and r['lead_s'] > 0 and r['affected_safe_tasks'] and not r['already_alarm']]
    def score(r):
        return r['information_age_factor'] * r['diagnostic_evidence'] * r['weight'] * min(r['lead_s']/300., 1.) / (1.+r['completion_cost_s']/60.)
    return max(eligible, key=lambda r: (score(r), -r['task']), default=None)


def choose_followup(rows, workflow, first_alarm):
    if workflow.normal_followup == 'return_tour' and first_alarm is False:
        return None
    pool = [r for r in rows if r['value'] > 0 and not r['already_alarm']]
    return max(pool, key=lambda r: (r['value'], -r['task']), default=None)


def first_reference_alarm(visible_history, first_key):
    reference = next((v for v in visible_history if tuple(v['event_id']) == first_key), None)
    return reference['alarm'] if reference is not None else None
