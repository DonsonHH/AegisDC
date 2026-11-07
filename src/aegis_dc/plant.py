"""Private plant/evaluator trajectory for the complete synthetic M1 facility.

This is an engineering run interface. No dispatch decision view, latent-fault
report, policy, training call or scientific-effect trial is produced here.
"""
from copy import deepcopy
from hashlib import sha256
import math
import json
from pathlib import Path
import subprocess

from patrol_rsi.contracts import digest
from .environment import condensation_risk, floor_water_step
from .heat_transfer import counterflow_exchange, pump_operating_point, valve_loop_operating_point
from .power import allocate_power, allocate_reserve_power
from .reserve import (RESERVE_MODEL, RESERVE_PROFILE, RESERVE_QUANTITIES, RESERVE_BINARY_PARAMETERS,
                      RESERVE_EXOGENOUS_PARAMETERS,
                      ups_transition, generator_transition, cooling_transition, paid_backup_exchange)
from .runtime_contract import ENVIRONMENT_MODELS, WATER_MODELS
from .local_control import CONTROL_PROFILE, CONTROL_QUANTITIES, CONTROL_BINARY_PARAMETERS, sample_local_control
from .scenario import validate_scenario
from .thermodynamics import SaturationTable, finite_number
from .time_coordinates import TIME_COORDINATE_CONVENTION, same_time, time_due
from .workforce import Workforce

ROOT = Path(__file__).resolve().parents[2]
ENVIRONMENT_EXOGENOUS_PARAMETERS = {
    'room_ambient_temperature', 'room_conductance', 'room_humidity',
    'internal_hot_leak_mass_flow', 'it_access_permit',
}
EXOGENOUS_PARAMETERS = {
    'grid_capacity', 'compute_demand_power', 'network_demand_power', 'storage_demand_power',
    'compute_service_capacity', 'network_service_capacity', 'storage_service_capacity',
    'service_demand', 'lake_temperature', 'filter_resistance_multiplier',
    'lake_valve_opening', 'internal_valve_opening', 'plate_hx_conductance',
    'pump_pressure_rise', 'internal_pump_pressure_rise',
    'room_aux_power', 'floor_water_inflow', 'drainage_mass_flow',
} | ENVIRONMENT_EXOGENOUS_PARAMETERS | set(CONTROL_QUANTITIES) | set(RESERVE_EXOGENOUS_PARAMETERS)

# Parameter commands supported by the current low-order engineering plant.
# They are not field-authorized repairs, capacity restoration or policy actions.
ENGINEERING_COMMAND_PARAMETERS = frozenset({
    'lake_valve_opening', 'internal_valve_opening', 'pump_pressure_rise',
    'internal_pump_pressure_rise', 'backup_cooling_requested',
})


def _boundary_events(rows, parameters, duration, *, model, control_profile=None, reserve_profile=None):
    if not isinstance(rows, (list, tuple)):
        raise ValueError('Boundary events must be a declared list')
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'time_s', 'parameter_id', 'value', 'source_note'}:
            raise ValueError('Declare each timed boundary input with parameter, value and source note')
        time_s = finite_number(row['time_s'], 'Boundary event time')
        name = row['parameter_id']
        if not isinstance(name, str) or name not in EXOGENOUS_PARAMETERS or name not in parameters:
            raise ValueError('Boundary event parameter is not an exogenous input')
        if name in ENVIRONMENT_EXOGENOUS_PARAMETERS and model not in ENVIRONMENT_MODELS:
            raise ValueError('Environmental boundary events require the explicit environment runtime model')
        if name in CONTROL_QUANTITIES and control_profile != CONTROL_PROFILE:
            raise ValueError('Local control events require the implemented explicit control profile')
        if name in RESERVE_QUANTITIES and reserve_profile != RESERVE_PROFILE:
            raise ValueError('Reserve boundary events require the implemented explicit profile')
        value = finite_number(row['value'], 'Boundary event value')
        if name in CONTROL_BINARY_PARAMETERS and value not in (0, 1):
            raise ValueError('Local control availability must be the declared binary 0/1 state')
        if name in RESERVE_BINARY_PARAMETERS and value not in (0, 1):
            raise ValueError('Reserve availability/request must be the declared binary 0/1 state')
        if name == 'it_access_permit' and value not in (0, 1):
            raise ValueError('IT access permission must be the declared binary 0/1 state')
        low, high = parameters[name]['valid_range']
        if not 0 <= time_s <= duration or not low <= value <= high:
            raise ValueError('Boundary event time/value outside declared range')
        if not isinstance(row['source_note'], str) or not row['source_note'].strip():
            raise ValueError('Boundary event requires source_note')
        if any(name == previous_name and same_time(time_s, previous_time)
               for previous_time, previous_name in seen):
            raise ValueError('Conflicting boundary event at the same time and parameter')
        seen.add((time_s, name))
        result.append(dict(row, time_s=time_s, value=value))
    return sorted(result, key=lambda item: item['time_s'])


def validate_boundary_events(scenario, events, *, duration_s):
    """Validate the public exogenous schedule without executing facility state."""
    validate_scenario(scenario)
    if not scenario['schema'].endswith('-v2'):
        raise ValueError('A boundary schedule needs a runnable scenario')
    parameters = {row['id']:row for row in scenario['parameters']}
    duration = finite_number(duration_s, 'Duration', positive=True)
    low, high = parameters['duration']['valid_range']
    if not low <= duration <= high:
        raise ValueError('duration outside declared runtime range')
    runtime = scenario['runtime']
    return _boundary_events(events, parameters, duration, model=runtime['model'],
        control_profile=runtime.get('local_control_profile'), reserve_profile=runtime.get('reserve_profile'))


def _code_identity():
    paths = sorted((ROOT / 'src/aegis_dc').glob('*.py')) + [ROOT / 'src/patrol_rsi/contracts.py']
    files = {str(path.relative_to(ROOT)).replace('\\', '/'): sha256(path.read_bytes()).hexdigest()
             for path in paths}
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        dirty = bool(subprocess.check_output(['git', 'status', '--porcelain', '--',
                                             'src/aegis_dc', 'src/patrol_rsi/contracts.py'],
                                            cwd=ROOT, text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = None, None
    return {'git_commit': commit, 'implementation_has_changes': dirty,
            'source_tree_sha256': digest(files), 'files': files}


def _action_commands(rows, parameters, duration, **profiles):
    if not isinstance(rows, (list, tuple)):
        raise ValueError('Engineering control commands must be a declared list')
    result, identifiers = [], set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'id', 'time_s', 'parameter_id', 'value', 'source_note'}:
            raise ValueError('Declare each engineering control command with its ID and timed parameter')
        identifier = row['id']
        if not isinstance(identifier, str) or not identifier.strip() or identifier in identifiers:
            raise ValueError('Engineering control command IDs must be distinct nonempty text')
        if row['parameter_id'] not in ENGINEERING_COMMAND_PARAMETERS:
            raise ValueError('Engineering command cannot write offered demand, weather or fault/maintenance parameters')
        checked = _boundary_events([{key: value for key, value in row.items() if key != 'id'}],
                                   parameters, duration, **profiles)[0]
        result.append(dict(checked, id=identifier))
        identifiers.add(identifier)
    for index, row in enumerate(result):
        if any(row['parameter_id'] == prior['parameter_id'] and same_time(row['time_s'], prior['time_s'])
               for prior in result[:index]):
            raise ValueError('Conflicting engineering command at the same time and parameter')
    return sorted(result, key=lambda row: (row['time_s'], row['parameter_id'], row['id']))


class _InventorySum:
    """Compensated accumulation of declared flux increments, without clipping."""

    def __init__(self, initial):
        self.total, self.correction = initial, 0.0

    def add(self, value):
        updated = self.total + value
        self.correction = math.fsum([self.correction, self.total, value, -updated])
        self.total = updated
        return math.fsum([self.total, self.correction])


class _Plant:
    def __init__(self, scenario, table):
        self.scenario, self.table = scenario, table
        self.environment_model = scenario['runtime']['model'] in ENVIRONMENT_MODELS
        self.reserve_model = scenario['runtime']['model'] == RESERVE_MODEL
        self.reserve_state = {'ups': None, 'generator': None, 'cooling': None}
        self.p = {row['id']: row['value'] for row in scenario['parameters']}
        p = self.p
        self.capacities = {'solid': p['it_thermal_capacity'], 'room': p['room_thermal_capacity'],
                           'hot': p['internal_hot_mass'] * p['water_specific_heat'],
                           'cold': p['internal_cold_mass'] * p['water_specific_heat']}
        self.energy = {name: self.capacities[name] * p[parameter] for name, parameter in
                       [('solid', 'initial_solid_temperature'), ('room', 'room_temperature'),
                        ('hot', 'initial_hot_temperature'), ('cold', 'initial_cold_temperature')]}
        self.energy.update(coolant=p['coolant_initial_energy'], ups=p['ups_energy'],
                           fuel=p['diesel_initial_fuel_energy'])
        if self.reserve_model:
            self.energy['starter'] = p['generator_initial_start_energy']
        self.floor_mass = p['initial_floor_water_mass']
        self.floor_mass_sum = _InventorySum(self.floor_mass)
        self.hot_mass = p['internal_hot_mass']
        self.floor_energy = self.floor_mass * p['water_specific_heat'] * p['room_ambient_temperature']
        self.room_access_blocked = self.environment_model and p['room_temperature'] >= p['maximum_room_work_temperature']
        self.floor_access_blocked = self.floor_mass >= p['access_block_mass']
        self.floor_access_boundary_mass = self.floor_mass if self.floor_mass == p['access_block_mass'] else None
        self.control = {'mode': 'normal', 'protection_latched': False,
                        'compute_permitted': True, 'pump_speed_command': 1.0,
                        'local_measurement': None}
        self.next_sample = 0.0
        self.sample_index = 0
        self.generator_mode, self.generator_ready = 'off', None
        self.events = []

    def temperatures(self):
        return {key: self.energy[key] / capacity for key, capacity in self.capacities.items()}

    def refrigerant(self):
        return self.table.flash(self.p['coolant_inventory'], self.energy['coolant'],
                                self.p['coolant_control_volume'])

    def stored_energy(self):
        p = self.p
        floor = self.floor_energy if self.environment_model else self.floor_mass * p['water_specific_heat'] * p['room_ambient_temperature']
        return math.fsum(self.energy.values()) + floor

    def blocked_locations(self):
        locations = set(self.scenario['runtime']['closed_location_ids'])
        if self.floor_access_blocked:
            locations.add('loc_it')
        if self.environment_model and self.p['it_access_permit'] == 0:
            locations.add('loc_it')
        if self.room_access_blocked:
            locations.add('loc_it')
        return locations

    def discrete(self, time_s):
        p = self.p
        floor_inflow = p['floor_water_inflow'] + (p['internal_hot_leak_mass_flow'] if self.environment_model else 0)
        floor_rate = floor_inflow - p['drainage_mass_flow']
        threshold = p['access_block_mass']
        projected = time_s + (threshold - self.floor_mass) / floor_rate if floor_rate else None
        # A positive remaining mass can imply a crossing time that rounds to
        # NOW, so filtering future events with value>now must not drop it.
        # Process that time coordinate without changing any physical inventory.
        at_boundary = (self.floor_mass == threshold
            or (projected is not None and same_time(time_s, projected))
            or self.floor_mass == self.floor_access_boundary_mass)
        blocked = (floor_rate > 0 if floor_rate else self.floor_access_blocked) if at_boundary else self.floor_mass > threshold
        if blocked != self.floor_access_blocked:
            self.floor_access_blocked = blocked
            self.events.append(dict(time_s=time_s, kind='floor_access_closed' if blocked else 'floor_access_opened',
                split_step=True, projected_crossing_at_s=projected, actual_floor_mass_kg=self.floor_mass,
                threshold_mass_kg=threshold, applied_at_s=time_s, direction_kg_s=floor_rate,
                numerical_time_convention='aegisdc-binary64-time-v1'))
        if at_boundary:
            # Preserve a stationary boundary's logical side while its exact
            # stored mass remains unchanged; no mass is snapped to threshold.
            self.floor_access_boundary_mass = self.floor_mass
        if self.reserve_model:
            return
        if p['grid_capacity'] == 0 and self.energy['fuel'] > 0:
            if self.generator_mode == 'off':
                self.generator_mode = 'starting'
                self.generator_ready = time_s + p['diesel_start_time']
                self.events.append({'time_s': time_s, 'kind': 'generator_start_requested'})
            if self.generator_mode == 'starting' and time_s >= self.generator_ready:
                self.generator_mode = 'running'
                self.events.append({'time_s': time_s, 'kind': 'generator_running'})
        elif p['grid_capacity'] > 0:
            self.generator_mode, self.generator_ready = 'off', None
        elif self.energy['fuel'] == 0:
            self.generator_mode = 'fuel_exhausted'

    def update_reserves(self, time_s, point, *, sampled=False):
        if not self.reserve_model:
            return
        p, power, old = self.p, point['power'], self.reserve_state
        states = {
            'ups': ups_transition(old['ups'], time_s=time_s, needed=power['ups_transfer_needed'],
                available=p['ups_in_service'], transfer_ok=p['ups_transfer_ok'], energy_J=self.energy['ups'],
                control_power_W=power['ups_control_power_W'], nominal_control_power_W=p['ups_internal_control_power'],
                delay_s=p['ups_transfer_delay']),
            'generator': generator_transition(old['generator'], time_s=time_s, mains_present=power['mains_present'],
                available=p['diesel_in_service'], start_ok=p['diesel_start_ok'], transfer_ok=p['diesel_transfer_ok'],
                fuel_energy_J=self.energy['fuel'], starter_energy_J=self.energy['starter'],
                control_power_W=power['generator_control_power_W'], nominal_control_power_W=p['generator_internal_control_power'],
                start_delay_s=p['diesel_start_time'], transfer_delay_s=p['diesel_transfer_delay']),
            'cooling': cooling_transition(old['cooling'], time_s=time_s, sampled=sampled,
                requested=p['backup_cooling_requested'], available=p['backup_cooling_in_service'],
                transfer_ok=p['backup_cooling_transfer_ok'], controller_power_W=power['actual_powers_W']['local_controller'],
                nominal_controller_power_W=p['controller_power'], delay_s=p['backup_cooling_transfer_delay']),
        }
        changed = False
        for actor, state in states.items():
            previous = old[actor] or {}
            if any(previous.get(key) != state.get(key) for key in ('mode', 'ready_at_s', 'requested_at_s')):
                changed = True
                self.events.append(dict(time_s=time_s, kind='reserve_transition', actor=actor,
                                        mode=state['mode'], request_actor=state['request_actor'],
                                        requested_at_s=state['requested_at_s'], ready_at_s=state['ready_at_s']))
        self.reserve_state = states
        self.generator_mode = states['generator']['mode']
        self.generator_ready = states['generator']['ready_at_s']
        return changed

    def update_room_work_access(self, point):
        """Use the actual post-control right-hand heat direction at equality."""
        if not self.environment_model:
            return
        room, limit = point['temperatures']['room'], self.p['maximum_room_work_temperature']
        if room > limit:
            self.room_access_blocked = True
        elif room < limit:
            self.room_access_blocked = False
        elif point['rates_W']['room']:
            self.room_access_blocked = point['rates_W']['room'] > 0

    def point(self):
        p, control = self.p, self.control
        speed = control['pump_speed_command']
        lake_args = (p['pump_pressure_rise'], p['lake_hydraulic_resistance'] * p['filter_resistance_multiplier'],
                     p['pump_efficiency'], speed)
        internal_args = (p['internal_pump_pressure_rise'], p['internal_hydraulic_resistance'],
                         p['internal_pump_efficiency'], speed)
        operating_point = pump_operating_point
        if self.scenario['runtime']['model'] in WATER_MODELS:
            lake_args = (*lake_args[:2], p['lake_valve_open_resistance'],
                         p['lake_valve_opening'], *lake_args[2:])
            internal_args = (*internal_args[:2], p['internal_valve_open_resistance'],
                             p['internal_valve_opening'], *internal_args[2:])
            operating_point = valve_loop_operating_point
        requested = {'intake_pump': operating_point(*lake_args)['electric_power_W'],
                     'internal_pump': operating_point(*internal_args)['electric_power_W']}
        if self.reserve_model:
            defaults = {'ups': 'bypass', 'generator': 'off', 'cooling': 'primary'}
            modes = {name: self.reserve_state[name]['mode'] if self.reserve_state[name] else initial
                     for name, initial in defaults.items()}
            power = allocate_reserve_power(p, requested, control['compute_permitted'],
                ups_energy_J=self.energy['ups'], fuel_energy_J=self.energy['fuel'],
                starter_energy_J=self.energy['starter'], ups_mode=modes['ups'],
                generator_mode=modes['generator'], cooling_mode=modes['cooling'])
        else:
            power = allocate_power(p, requested, control['compute_permitted'], self.energy['ups'],
                                    self.generator_mode == 'running', self.energy['fuel'])
        actual = power['actual_powers_W']
        lake = operating_point(*lake_args, available_power_W=actual['intake_pump'])
        internal = operating_point(*internal_args, available_power_W=actual['internal_pump'])
        t, r = self.temperatures(), self.refrigerant()
        ci = p['water_density'] * p['water_specific_heat'] * internal['volume_flow_m3_s']
        cl = p['water_density'] * p['water_specific_heat'] * lake['volume_flow_m3_s']
        fraction = p['pump_fluid_heat_fraction']
        # This model has no separate pipe heat-loss or pressure-work export:
        # all q*dp work dissipates in that fluid. f*Pe includes it exactly once.
        # Check the actual operating point, including timed enables, rather
        # than constraining an unpowered/zero-head/shutoff pump's unused eta.
        for pump, efficiency in ((lake, p['pump_efficiency']), (internal, p['internal_pump_efficiency'])):
            if pump['hydraulic_power_W'] > 0 and fraction < efficiency:
                raise ValueError('Pump fluid heat must include the hydraulic dissipation; require fluid heat fraction >= active pump efficiency')
        lake_pump_heat = fraction * actual['intake_pump']
        lake_inlet = p['lake_temperature'] + lake_pump_heat / cl if cl else p['lake_temperature']
        hx = counterflow_exchange(p['plate_hx_conductance'], ci, cl, t['hot'], lake_inlet)
        backup = (paid_backup_exchange(p, water_capacity_W_K=ci, water_inlet_K=t['hot'],
                  external_inlet_K=p['room_ambient_temperature'], fan_power_W=actual['backup_fan'],
                  connected=power['reserve_cooling_connected']) if self.reserve_model else {'heat_W': 0.0})
        condenser = -math.expm1(-p['condenser_conductance'] / ci) * ci \
            * (r['temperature_K'] - t['cold']) if ci else 0.0
        solid_coolant = p['solid_coolant_conductance'] * (t['solid'] - r['temperature_K'])
        solid_air = p['solid_air_conductance'] * (t['solid'] - t['room'])
        room_out = p['room_conductance'] * (t['room'] - p['room_ambient_temperature'])
        circulation = ci * (t['hot'] - t['cold'])
        room_input = (actual['network'] + actual['local_controller'] + actual['room']
                      + power['rectifier_loss_W'] + power['ups_loss_W'] + solid_air
                      + (1 - fraction) * (actual['intake_pump'] + actual['internal_pump'])
                      + power.get('reserve_room_heat_W', 0))
        capacities = {name: min(p[name + '_service_capacity'], actual[name] / p[name + '_nominal_power'])
                      for name in ('compute', 'network', 'storage')}
        delivery = min(p['service_demand'], *capacities.values())
        leak = p['internal_hot_leak_mass_flow'] if self.environment_model else 0.0
        leak_heat = leak * p['water_specific_heat'] * t['hot']
        floor_inflow = p['floor_water_inflow'] + leak
        drain = p['drainage_mass_flow'] if self.floor_mass > 0 else min(floor_inflow, p['drainage_mass_flow'])
        return {'power': power, 'lake_pump': lake, 'internal_pump': internal, 'hx': hx,
                'temperatures': t, 'refrigerant': r, 'lake_inlet_K': lake_inlet,
                'condenser_heat_W': condenser, 'solid_coolant_heat_W': solid_coolant,
                'solid_air_heat_W': solid_air, 'room_out_W': room_out,
                'lake_out_W': hx['heat_W'] + lake_pump_heat,
                'reserve_exchange': backup,
                'reserve_outside_W': backup['heat_W'] + power.get('reserve_external_electric_heat_W', 0),
                'drain_kg_s': drain, 'circulation_W': circulation,
                'hot_leak_kg_s': leak, 'hot_leak_heat_W': leak_heat,
                'floor_inflow_kg_s': floor_inflow,
                'floor_inlet_energy_W': p['floor_water_inflow'] * p['water_specific_heat'] * p['room_ambient_temperature'] + leak_heat,
                'service': {'demand': p['service_demand'], 'delivered': delivery,
                            'capacities': capacities, 'unserved': p['service_demand'] - delivery},
                'rates_W': {
                    'solid': actual['compute'] - solid_coolant - solid_air,
                    'room': room_input - room_out,
                    'coolant': solid_coolant - condenser,
                    'hot': condenser + actual['storage'] + fraction * actual['internal_pump'] - circulation - leak_heat,
                    'cold': circulation - hx['heat_W'] - backup['heat_W'],
                    'ups': -power['ups_depletion_W'], 'fuel': -power['fuel_depletion_W'],
                    **({'starter': -power['starter_depletion_W']} if self.reserve_model else {}),
                }}

    def sample_control(self, time_s, point):
        if not time_due(time_s, self.next_sample):
            return
        p, c = self.p, self.control
        power = point['power']['actual_powers_W']['local_controller']
        if self.scenario['runtime'].get('local_control_profile') == CONTROL_PROFILE:
            measurement = {'observed_at_s': time_s,
                'temperature_K': point['refrigerant']['temperature_K'] + p['local_temperature_bias'],
                'internal_volume_flow_m3_s': point['internal_pump']['volume_flow_m3_s'] + p['local_internal_flow_bias'],
                'temperature_valid': p['local_temperature_sensor_valid'] == 1,
                'flow_valid': p['local_internal_flow_sensor_valid'] == 1,
                'supervisory_connected': p['supervisory_link_available'] == 1}
            self.control = sample_local_control(c, p, measurement, controller_power_W=power)
            self.sample_index += 1
            self.next_sample = self.sample_index * p['control_sample_time']
            return
        if power < p['controller_power'] or p['controller_power'] == 0:
            c.update(mode='unpowered_fail_safe', compute_permitted=False, pump_speed_command=1.0)
        else:
            temperature = point['refrigerant']['temperature_K']
            flow = point['internal_pump']['volume_flow_m3_s']
            trip = temperature >= p['protection_temperature'] or flow < p['minimum_internal_volume_flow']
            if trip:
                c['protection_latched'] = True
            elif temperature <= p['protection_reset_temperature'] and flow >= p['minimum_internal_volume_flow']:
                c['protection_latched'] = False
            c.update(mode='protected' if c['protection_latched'] else 'normal',
                     compute_permitted=not c['protection_latched'])
            if temperature >= p['cooling_setpoint']:
                c['pump_speed_command'] = 1.0
            elif temperature <= p['cooling_setpoint'] - p['control_hysteresis']:
                c['pump_speed_command'] = p['pump_min_speed']
            c['local_measurement'] = {'observed_at_s': time_s, 'temperature_K': temperature,
                                      'internal_volume_flow_m3_s': flow,
                                      'controller_power_W': power, 'visibility': 'LOCAL_PLANT_ONLY'}
        self.sample_index += 1
        self.next_sample = self.sample_index * p['control_sample_time']

    def next_physical_event(self, time_s, point):
        times = [self.next_sample]
        if self.generator_mode == 'starting':
            times.append(self.generator_ready)
        if self.reserve_model:
            times.extend(state['ready_at_s'] for state in self.reserve_state.values()
                         if state and state['ready_at_s'] is not None)
        for key, depletion in [('ups', point['power']['ups_depletion_W']),
                               ('fuel', point['power']['fuel_depletion_W'])] + (
                               [('starter', point['power']['starter_depletion_W'])] if self.reserve_model else []):
            if depletion > 0 and self.energy[key] > 0:
                times.append(time_s + self.energy[key] / depletion)
        floor_rate = point['floor_inflow_kg_s'] - point['drain_kg_s']
        if floor_rate < 0 and self.floor_mass > 0:
            times.append(time_s + self.floor_mass / -floor_rate)
            if self.floor_mass > self.p['access_block_mass']:
                times.append(time_s + (self.floor_mass - self.p['access_block_mass']) / -floor_rate)
        if floor_rate > 0 and self.floor_mass < self.p['access_block_mass']:
            times.append(time_s + (self.p['access_block_mass'] - self.floor_mass) / floor_rate)
        if self.environment_model and point['hot_leak_kg_s'] > 0 \
                and self.hot_mass > self.p['minimum_internal_hot_mass']:
            times.append(time_s + (self.hot_mass - self.p['minimum_internal_hot_mass']) / point['hot_leak_kg_s'])
        if self.environment_model:
            room = point['temperatures']['room']
            rate = point['rates_W']['room'] / self.capacities['room']
            limit = self.p['maximum_room_work_temperature']
            if (rate > 0 and room < limit) or (rate < 0 and room > limit):
                times.append(time_s + (limit - room) / rate)
        return min(value for value in times if value > time_s)

    def integrate(self, start, end, point):
        dt, p = end - start, self.p
        before = self.energy.copy()
        old_floor, old_total = self.floor_mass, self.stored_energy()
        old_hot_mass = self.hot_mass
        old_floor_energy = self.floor_energy if self.environment_model else old_floor * p['water_specific_heat'] * p['room_ambient_temperature']
        leaked_mass = point['hot_leak_kg_s'] * dt
        pool = None
        if self.environment_model:
            new_hot_mass = math.fsum([old_hot_mass, -leaked_mass])
            minimum = p['minimum_internal_hot_mass']
            if new_hot_mass < minimum:
                if old_hot_mass > minimum and point['hot_leak_kg_s'] > 0 and math.isclose(
                        dt, (old_hot_mass - minimum) / point['hot_leak_kg_s'], rel_tol=1e-12, abs_tol=1e-12):
                    new_hot_mass = minimum  # roundoff at the explicitly split domain boundary
                else:
                    raise ValueError('Hot-water inventory below the declared hydraulic validity minimum; low-inventory geometry is not modeled')
            net_drain = point['drain_kg_s'] - point['floor_inflow_kg_s']
            empty_at = start + old_floor / net_drain if old_floor > 0 and net_drain > 0 else None
            if empty_at is not None and same_time(end, empty_at):
                # The already scheduled exact empty event can leave either a
                # positive or negative roundoff residue. Its analytic boundary
                # exports all stored/incoming heat; do not carry a tiny pool
                # into a following interval whose empty time rounds to now.
                incoming = point['floor_inlet_energy_W'] * dt
                pool = dict(mass_kg=0.0, energy_J=0.0, temperature_K=None,
                    drained_mass_kg=math.fsum([old_floor, point['floor_inflow_kg_s'] * dt]),
                    drained_energy_J=math.fsum([old_floor_energy, incoming]), inlet_energy_J=incoming)
                self.events.append(dict(time_s=end, kind='floor_water_emptied', split_step=True,
                    projected_crossing_at_s=empty_at, applied_at_s=end, actual_floor_mass_before_kg=old_floor,
                    raw_after_mass_kg=math.fsum([old_floor, point['floor_inflow_kg_s'] * dt, -point['drain_kg_s'] * dt]),
                    compensation_reset='HIGH_AND_LOW_AT_EXPLICIT_EMPTY',
                    numerical_time_convention='aegisdc-binary64-time-v1'))
            else:
                pool = floor_water_step(old_floor, old_floor_energy, p['water_specific_heat'],
                    point['floor_inflow_kg_s'], point['floor_inlet_energy_W'], point['drain_kg_s'], dt)
            self.floor_mass_sum.add(point['floor_inflow_kg_s'] * dt)
            integrated_mass = self.floor_mass_sum.add(-point['drain_kg_s'] * dt)
            if pool['mass_kg'] == 0:
                # Retain the existing explicit empty-inventory event exactly.
                self.floor_mass_sum = _InventorySum(0.0)
            else:
                pool['mass_kg'] = integrated_mass
        for name, rate in point['rates_W'].items():
            if rate < 0 and before[name] > 0 and math.isclose(dt, before[name] / -rate,
                                                            rel_tol=1e-12, abs_tol=1e-12) \
                    and name in {'ups', 'fuel', 'starter'}:
                self.energy[name] = 0.0
                self.events.append({'time_s': end, 'kind': name + '_depleted', 'split_step': True})
            else:
                self.energy[name] += rate * dt
            if not math.isfinite(self.energy[name]) or self.energy[name] < 0:
                raise ValueError('Invalid energy inventory at ' + str(end) + ' s: ' + name)
        floor_rate = point['floor_inflow_kg_s'] - point['drain_kg_s']
        if self.environment_model:
            self.hot_mass = new_hot_mass
            self.capacities['hot'] = new_hot_mass * p['water_specific_heat']
            self.floor_mass, self.floor_energy = pool['mass_kg'], pool['energy_J']
        elif floor_rate < 0 and math.isclose(dt, old_floor / -floor_rate, rel_tol=1e-12, abs_tol=1e-12):
            self.floor_mass = 0.0
        else:
            self.floor_mass += floor_rate * dt
        if self.floor_mass < 0 or not math.isfinite(self.floor_mass):
            raise ValueError('Invalid floor-water inventory')
        if self.environment_model:
            room = point['temperatures']['room']
            rate = point['rates_W']['room'] / self.capacities['room']
            limit = p['maximum_room_work_temperature']
            if ((rate > 0 and room < limit) or (rate < 0 and room > limit)) and math.isclose(
                    dt, (limit - room) / rate, rel_tol=1e-12, abs_tol=1e-12):
                self.energy['room'] = self.capacities['room'] * limit
                self.room_access_blocked = rate > 0
                self.events.append({'time_s': end, 'kind': 'room_work_access_closed' if rate > 0 else 'room_work_access_opened',
                                    'split_step': True, 'basis': 'DECLARED_RESEARCH_THRESHOLD_NOT_SITE_OR_OCCUPATIONAL_LIMIT'})
        threshold = p['access_block_mass']
        crossing = start + (threshold - old_floor) / floor_rate if floor_rate else None
        crossing_due = crossing is not None and time_due(end, crossing)
        if not self.floor_access_blocked and old_floor < threshold and floor_rate > 0 and (threshold <= self.floor_mass or crossing_due):
            self.floor_access_blocked = True
            self.floor_access_boundary_mass = self.floor_mass
            self.events.append(dict(time_s=end, kind='floor_access_closed', split_step=True,
                projected_crossing_at_s=crossing, actual_floor_mass_kg=self.floor_mass,
                threshold_mass_kg=threshold, applied_at_s=end, direction_kg_s=floor_rate,
                numerical_time_convention='aegisdc-binary64-time-v1'))
        elif self.floor_access_blocked and threshold < old_floor and floor_rate < 0 and (self.floor_mass <= threshold or crossing_due):
            self.floor_access_blocked = False
            self.floor_access_boundary_mass = self.floor_mass
            self.events.append(dict(time_s=end, kind='floor_access_opened', split_step=True,
                projected_crossing_at_s=crossing, actual_floor_mass_kg=self.floor_mass,
                threshold_mass_kg=threshold, applied_at_s=end, direction_kg_s=floor_rate,
                numerical_time_convention='aegisdc-binary64-time-v1'))
        new_t = self.temperatures()
        for name, initial_parameter in [('solid', 'initial_solid_temperature'), ('room', 'room_temperature'),
                                        ('hot', 'initial_hot_temperature'), ('cold', 'initial_cold_temperature')]:
            limits = next(record['valid_range'] for record in self.scenario['parameters'] if record['id'] == initial_parameter)
            if not limits[0] <= new_t[name] <= limits[1]:
                raise ValueError('Temperature outside declared lumped-model domain: ' + name)
            if abs(new_t[name] - point['temperatures'][name]) > p['maximum_temperature_step']:
                raise ValueError('Excessive temperature change; reduce the integration step: ' + name)
        new_refrigerant = self.refrigerant()  # fail rather than serialize a forged phase state
        energy_residuals = {name: (self.energy[name] - before[name]) - rate * dt
                            for name, rate in point['rates_W'].items()}
        power = point['power']
        floor_in = p['floor_water_inflow'] * p['water_specific_heat'] * p['room_ambient_temperature']
        floor_out = pool['drained_energy_J'] / dt if self.environment_model else point['drain_kg_s'] * p['water_specific_heat'] * p['room_ambient_temperature']
        rates = dict(point['rates_W'])
        if self.environment_model:
            rates['floor_water'] = point['floor_inlet_energy_W'] - floor_out
            energy_residuals['floor_water'] = self.floor_energy - old_floor_energy - rates['floor_water'] * dt
        boundary_input = power['grid_draw_W'] + floor_in
        boundary_output = (point['lake_out_W'] + point['room_out_W'] + power['generator_waste_W']
                           + floor_out + point['reserve_outside_W'])
        energy_residuals['facility'] = self.stored_energy() - old_total - (boundary_input - boundary_output) * dt
        old_r = point['refrigerant']
        internal_flow = point['internal_pump']['volume_flow_m3_s'] * p['water_density']
        lake_flow = point['lake_pump']['volume_flow_m3_s'] * p['water_density']
        mass_accounts = {
            'refrigerant': {'before_kg': old_r['liquid_mass_kg'] + old_r['vapor_mass_kg'],
                            'after_kg': new_refrigerant['liquid_mass_kg'] + new_refrigerant['vapor_mass_kg'],
                            'in_kg': 0.0, 'out_kg': 0.0},
            'floor_water': {'before_kg': old_floor, 'after_kg': self.floor_mass,
                            'in_kg': point['floor_inflow_kg_s'] * dt, 'out_kg': point['drain_kg_s'] * dt},
            'lake_throughflow': {'before_kg': 0.0, 'after_kg': 0.0,
                                'in_kg': lake_flow * dt, 'out_kg': lake_flow * dt},
        }
        for name, mass in [('internal_hot', old_hot_mass), ('internal_cold', p['internal_cold_mass'])]:
            mass_accounts[name] = {'before_kg': mass, 'after_kg': mass,
                                  'in_kg': internal_flow * dt, 'out_kg': internal_flow * dt}
        if self.environment_model:
            mass_accounts['internal_hot'].update(after_kg=self.hot_mass, out_kg=internal_flow * dt + leaked_mass)
            mass_accounts['facility_water'] = {
                'before_kg': old_hot_mass + p['internal_cold_mass'] + old_floor,
                'after_kg': self.hot_mass + p['internal_cold_mass'] + self.floor_mass,
                'in_kg': p['floor_water_inflow'] * dt, 'out_kg': point['drain_kg_s'] * dt}
        mass_residuals = {name: math.fsum((row['before_kg'], row['in_kg'], -row['out_kg'], -row['after_kg']))
                          for name, row in mass_accounts.items()}
        electrical_residual = power['grid_draw_W'] + power['generator_output_W'] + power['ups_output_W'] \
            + power.get('starter_output_W', 0) - sum(power['actual_powers_W'].values()) - power['rectifier_loss_W']
        tolerance = p['energy_absolute_tolerance'] + p['balance_relative_tolerance'] \
            * dt * (abs(boundary_input) + abs(boundary_output))
        if max(abs(value) for value in energy_residuals.values()) > tolerance \
                or abs(electrical_residual) * dt > tolerance:
            raise ValueError('Energy conservation residual exceeds the declared tolerance')
        if max(abs(value) for value in mass_residuals.values()) > p['mass_absolute_tolerance']:
            raise ValueError('Mass conservation residual exceeds the declared tolerance')
        for name, slack in power['capacity_slack_W'].items():
            if slack < -p['energy_absolute_tolerance'] / dt:
                raise ValueError('Electrical capacity exceeded: ' + name)
        for label, pump, nominal in [('lake', point['lake_pump'], p['lake_volume_flow']),
                                      ('internal', point['internal_pump'], p['internal_volume_flow'])]:
            if pump['volume_flow_m3_s'] > nominal * (1 + p['balance_relative_tolerance']):
                raise ValueError('Pump outside declared flow capacity: ' + label)
        return {'start_s': start, 'end_s': end, 'energy_residuals_J': energy_residuals,
                'mass_residuals_kg': mass_residuals, 'electrical_residual_W': electrical_residual,
                'mass_accounts_kg': mass_accounts,
                'storage_before_J': dict(before, floor_water=old_floor_energy),
                'storage_after_J': dict(self.energy, floor_water=self.floor_energy if self.environment_model else self.floor_mass * p['water_specific_heat'] * p['room_ambient_temperature']),
                'component_energy_rates_W': rates,
                'heat_transfers_W': {'solid_to_coolant': point['solid_coolant_heat_W'],
                                     'solid_to_room': point['solid_air_heat_W'],
                                     'coolant_to_internal_water': point['condenser_heat_W'],
                                     'plate_hx_to_lake': point['hx']['heat_W'],
                                     'internal_hot_to_cold_advection': point['circulation_W'],
                                     **({'backup_water_to_external_air': point['reserve_exchange']['heat_W']} if self.reserve_model else {}),
                                     **({'hot_water_leak_to_floor': point['hot_leak_heat_W']} if self.environment_model else {})},
                'capacity_slack_W': power['capacity_slack_W'],
                'boundary_input_J': boundary_input * dt, 'boundary_output_J': boundary_output * dt,
                'grid_energy_J': power['grid_draw_W'] * dt, 'lake_heat_J': point['lake_out_W'] * dt,
                'ups_output_energy_J': power['ups_output_W'] * dt,
                'ups_loss_energy_J': power['ups_loss_W'] * dt,
                'generator_output_energy_J': power['generator_output_W'] * dt,
                'generator_waste_energy_J': power['generator_waste_W'] * dt,
                **({'starter_output_energy_J': power['starter_output_W'] * dt,
                    'backup_water_heat_J': point['reserve_exchange']['heat_W'] * dt,
                    'reserve_external_electric_heat_J': power['reserve_external_electric_heat_W'] * dt,
                    'reserve_room_control_heat_J': power['reserve_room_heat_W'] * dt,
                    'backup_fan_energy_J': power['actual_powers_W']['backup_fan'] * dt} if self.reserve_model else {}),
                'floor_water_inlet_mass_kg': p['floor_water_inflow'] * dt,
                'floor_water_drained_mass_kg': point['drain_kg_s'] * dt,
                'floor_inlet_energy_J': floor_in * dt, 'floor_drain_energy_J': floor_out * dt,
                **({'internal_hot_leaked_mass_kg': leaked_mass,
                    'internal_hot_leak_energy_J': point['hot_leak_heat_W'] * dt} if self.environment_model else {}),
                'room_heat_J': point['room_out_W'] * dt,
                'demand_service_unit_s': point['service']['demand'] * dt,
                'delivered_service_unit_s': point['service']['delivered'] * dt,
                'service_deficit_time_s': point['service']['unserved'] / point['service']['demand'] * dt
                if point['service']['demand'] else 0.0}

    def snapshot(self, time_s, point, workforce):
        p, t = self.p, point['temperatures']
        valves = {}
        control = deepcopy(self.control)
        if self.scenario['runtime']['model'] in WATER_MODELS:
            for loop in ('lake', 'internal'):
                pump = point[loop + '_pump']
                valves[loop + '_valve_group'] = {
                    'opening': pump['opening'],
                    'effective_resistance_Pa_s2_m6': pump['valve_resistance_Pa_s2_m6'],
                    'dynamic_pressure_drop_Pa': pump['valve_pressure_drop_Pa'],
                    'closed_valve_interlock': pump['closed_valve_interlock'],
                }
            control['hardwired_pump_permits'] = {
                'intake_pump': not point['lake_pump']['closed_valve_interlock'],
                'internal_pump': not point['internal_pump']['closed_valve_interlock'],
            }
        condensation = {}
        floor_state = {}
        if self.environment_model:
            criterion = condensation_risk(t['room'], p['room_humidity'], t['cold'])
            condensation['condensation_boundary'] = dict(criterion,
                surface_entity_id='internal_water', surface_temperature_K=t['cold'],
                surface_temperature_basis='COLD_BUFFER_BULK_PROXY_NO_WALL_OR_INSULATION_MODEL',
                visibility='PRIVATE_PLANT_EVALUATOR_ONLY')
            floor_state = {'floor_water_temperature_K': self.floor_energy / (self.floor_mass * p['water_specific_heat']) if self.floor_mass else None,
                           'floor_water_sensible_energy_J': self.floor_energy,
                           'it_access_gate': {'entity_id': 'it_access_gate', 'permit': bool(p['it_access_permit'])},
                           'room_work_access_blocked': self.room_access_blocked,
                           'room_work_temperature_limit_K': p['maximum_room_work_temperature']}
        return {'time_s': time_s, 'domains': {
            'power': point['power'],
            'backup': {'ups_energy_J': self.energy['ups'], 'fuel_energy_J': self.energy['fuel'],
                       'generator_mode': self.generator_mode, 'generator_ready_at_s': self.generator_ready,
                       'backup_tower_mode': self.reserve_state['cooling']['mode'] if self.reserve_model else 'standby_uncommanded',
                       **({'starter_energy_J': self.energy['starter'], 'reserve_states': deepcopy(self.reserve_state)} if self.reserve_model else {})},
            'facility_cooling': {'hot_temperature_K': t['hot'], 'cold_temperature_K': t['cold'],
                                 'hot_mass_kg': self.hot_mass, 'cold_mass_kg': p['internal_cold_mass'],
                                 'lake_pump': point['lake_pump'], 'internal_pump': point['internal_pump'],
                                 'internal_mass_flow_kg_s': point['internal_pump']['volume_flow_m3_s'] * p['water_density'],
                                 'lake_mass_flow_kg_s': point['lake_pump']['volume_flow_m3_s'] * p['water_density'],
                                 'lake_hx_inlet_K': point['lake_inlet_K'],
                                 'internal_hx_outlet_K': point['hx']['hot_outlet_K'],
                                 'lake_hx_outlet_K': point['hx']['cold_outlet_K'],
                                 'plate_hx_heat_W': point['hx']['heat_W'],
                                 'condenser_heat_W': point['condenser_heat_W'],
                                 **({'backup_exchange': point['reserve_exchange']} if self.reserve_model else {}),
                                 **({'valve_groups': valves} if valves else {})},
            'equipment_environment': {'solid_temperature_K': t['solid'], 'room_temperature_K': t['room'],
                                      'room_humidity': p['room_humidity'], 'refrigerant': point['refrigerant'],
                                      'solid_coolant_heat_W': point['solid_coolant_heat_W'],
                                      'solid_air_heat_W': point['solid_air_heat_W'], **condensation},
            'it_service': point['service'], 'control_monitoring': control,
            'space_access': {'floor_water_mass_kg': self.floor_mass, 'drain_kg_s': point['drain_kg_s'],
                              'blocked_location_ids': sorted(self.blocked_locations()), **floor_state},
            'people_tools_work': workforce.snapshot(),
        }}


def simulate_scenario(scenario, *, duration_s=None, step_s=None, work_requests=(), boundary_events=(), action_commands=(), work_program=None, inspection_program=None, intervention_program=None, dispatch_program=None):
    """Run the validated complete facility and return a private engineering trace.

    Overrides remain within declared SI ranges. Caller dictionaries are not
    mutated. A v1 structural snapshot is still loadable but is not runnable.
    """
    scenario = deepcopy(validate_scenario(scenario))
    if not scenario['schema'].endswith('-v2'):
        raise ValueError('Simulation requires the explicitly initialized v2 runtime scenario')
    p_records = {row['id']: row for row in scenario['parameters']}
    duration = p_records['duration']['value'] if duration_s is None else finite_number(duration_s, 'Duration', positive=True)
    step = p_records['step_time']['value'] if step_s is None else finite_number(step_s, 'Step', positive=True)
    for name, value in [('duration', duration), ('step_time', step)]:
        low, high = p_records[name]['valid_range']
        if not low <= value <= high:
            raise ValueError(name + ' outside declared runtime range')
    timed_inputs = _boundary_events(boundary_events, p_records, duration, model=scenario['runtime']['model'],
                                    control_profile=scenario['runtime'].get('local_control_profile'),
                                    reserve_profile=scenario['runtime'].get('reserve_profile'))
    commands = _action_commands(action_commands, p_records, duration, model=scenario['runtime']['model'],
                                control_profile=scenario['runtime'].get('local_control_profile'),
                                reserve_profile=scenario['runtime'].get('reserve_profile'))
    boundary_inputs = deepcopy(timed_inputs)
    if any(boundary['parameter_id'] == command['parameter_id'] and same_time(boundary['time_s'], command['time_s'])
           for boundary in timed_inputs for command in commands):
        raise ValueError('Conflicting boundary input and engineering command at the same time and parameter')
    timed_inputs = sorted([dict(row, kind='exogenous_boundary_input') for row in timed_inputs]
                          + [dict(row, kind='engineering_control_command') for row in commands],
                          key=lambda row: (row['time_s'], row['parameter_id']))
    event_index = 0
    runtime = scenario['runtime']
    table = SaturationTable.from_file(ROOT / runtime['property_table'], expected_sha256=runtime['property_sha256'])
    plant = _Plant(scenario, table)
    dispatch = None
    if dispatch_program is not None:
        if work_program is not None or work_requests or inspection_program is not None or intervention_program is not None:
            raise ValueError('Policy execution owns its declared crew and observation/action bindings')
        from .policy_execution import PolicySession
        dispatch = PolicySession(dispatch_program,duration)
        work_program = dispatch.work_program
        inspection_program = dispatch.inspection_program
        intervention_program = dispatch.intervention_program
    if work_program is None:
        workforce = Workforce(scenario, plant.p, work_requests, duration)
    else:
        if work_requests:
            raise ValueError('Use legacy work_requests or a work_program, not both')
        from .workforce_dispatch import CrewWorkforce
        workforce = CrewWorkforce(scenario, plant.p, work_program, duration)
    inspections = None
    if inspection_program is not None:
        if work_program is None:
            raise ValueError('Real inspections require the actual crew work_program')
        from .inspection_execution import InspectionSession
        inspections = InspectionSession(scenario, dispatch.catalog_program if dispatch is not None else work_program, inspection_program)
    interventions = None
    if intervention_program is not None:
        if work_program is None:
            raise ValueError('Actual interventions require a crew work_program')
        from .intervention_execution import InterventionSession
        interventions = InterventionSession(scenario, dispatch.catalog_program if dispatch is not None else work_program, intervention_program)
    initial_energy = plant.stored_energy()
    time_s, trace, balances = 0.0, [], []
    while True:
        while event_index < len(timed_inputs) and time_due(time_s, timed_inputs[event_index]['time_s']):
            event = timed_inputs[event_index]
            plant.p[event['parameter_id']] = event['value']
            plant.events.append(dict(event, applied_at_s=time_s))
            event_index += 1
        plant.discrete(time_s)
        point = plant.point()
        if plant.reserve_model:
            plant.update_reserves(time_s, point)
            point = plant.point()
        sample_due = time_due(time_s, plant.next_sample)
        plant.sample_control(time_s, point)
        point = plant.point()
        if plant.reserve_model:
            # The sampled selector can change the current protected demand.
            # Settle autonomous reserve actors at this same instant without
            # taking a second PLC sample or adding a numeric-step delay.
            for attempt in range(4):
                changed = plant.update_reserves(time_s, point, sampled=sample_due and attempt == 0)
                point = plant.point()
                if not changed:
                    break
            else:
                raise ValueError('Reserve source/selector states did not settle at the current instant')
        plant.update_room_work_access(point)
        workforce.process(time_s, plant.blocked_locations())
        if interventions is not None:
            effects = interventions.process(time_s, workforce, plant.p)
            if effects:
                plant.events.extend(dict(row,kind='completed_research_intervention') for row in effects)
                point = plant.point()
                if plant.reserve_model:
                    # A completed command does not create an extra PLC sample.
                    # Autonomous reserve safety/power settles at this same instant.
                    for _ in range(4):
                        changed = plant.update_reserves(time_s, point, sampled=False)
                        point = plant.point()
                        if not changed:
                            break
                    else:
                        raise ValueError('Post-intervention reserve states did not settle')
                plant.update_room_work_access(point)
                workforce.process(time_s, plant.blocked_locations())
        snapshot = plant.snapshot(time_s, point, workforce)
        if inspections is not None:
            inspections.process(time_s, workforce, snapshot)
        if dispatch is not None and dispatch.sensors is not None:
            dispatch.sensors.process(time_s,snapshot)
        if dispatch is not None and dispatch.process(time_s,workforce,inspections,interventions):
            workforce.process(time_s,plant.blocked_locations())
            snapshot = plant.snapshot(time_s,point,workforce)
        trace.append(snapshot)
        if time_s >= duration:
            break
        next_input = timed_inputs[event_index]['time_s'] if event_index < len(timed_inputs) else duration
        end = min(duration, time_s + step, plant.next_physical_event(time_s, point), next_input,
                  workforce.next_event(time_s),dispatch.next_event(time_s) if dispatch is not None else math.inf)
        occupation = workforce.occupation_rates()
        balance = plant.integrate(time_s, end, point)
        balance.update({key: value * (end - time_s) for key, value in occupation.items()})
        balances.append(balance)
        time_s = end
    summary = {key: math.fsum(row[key] for row in balances) for key in
               ('boundary_input_J', 'boundary_output_J', 'grid_energy_J', 'lake_heat_J', 'room_heat_J',
                'ups_output_energy_J', 'ups_loss_energy_J', 'generator_output_energy_J', 'generator_waste_energy_J',
                'floor_water_inlet_mass_kg', 'floor_water_drained_mass_kg', 'floor_inlet_energy_J', 'floor_drain_energy_J',
                'worker_travel_person_s', 'worker_work_person_s', 'tool_occupation_tool_s',
                'demand_service_unit_s', 'delivered_service_unit_s', 'service_deficit_time_s')}
    if plant.environment_model:
        summary.update({key: math.fsum(row[key] for row in balances) for key in
                        ('internal_hot_leaked_mass_kg', 'internal_hot_leak_energy_J')})
    if work_program is not None:
        summary.update({key: math.fsum(row[key] for row in balances) for key in
                        ('worker_wait_person_s','access_check_person_s','rendezvous_wait_person_s','queue_wait_person_s','tool_work_tool_s')})
    if plant.reserve_model:
        summary.update({key: math.fsum(row[key] for row in balances) for key in
                        ('starter_output_energy_J', 'backup_water_heat_J', 'reserve_external_electric_heat_J',
                         'reserve_room_control_heat_J', 'backup_fan_energy_J')})
    summary.update(duration_s=duration, integration_steps=len(balances), initial_stored_energy_J=initial_energy,
                   final_stored_energy_J=plant.stored_energy(),
                   whole_run_energy_residual_J=plant.stored_energy() - initial_energy
                   - (summary['boundary_input_J'] - summary['boundary_output_J']),
                   max_energy_residual_J=max(abs(value) for row in balances for value in row['energy_residuals_J'].values()),
                   max_mass_residual_kg=max(abs(value) for row in balances for value in row['mass_residuals_kg'].values()))
    whole_tolerance = plant.p['energy_absolute_tolerance'] + plant.p['balance_relative_tolerance'] \
        * (abs(summary['boundary_input_J']) + abs(summary['boundary_output_J']))
    if abs(summary['whole_run_energy_residual_J']) > whole_tolerance:
        raise ValueError('Whole-run energy residual exceeds declared tolerance')
    summary['minimum_capacity_slack_W'] = {name: min(row['capacity_slack_W'][name] for row in balances)
                                           for name in balances[0]['capacity_slack_W']}
    summary['work_rejections'] = {reason: sum(row.get('reason') == reason for row in workforce.records)
                                  for reason in sorted({row['reason'] for row in workforce.records if row['status'] == 'rejected'})}
    return {'schema': 'aegisdc-engineering-facility-run-v1', 'status': 'ENGINEERING_FIXTURE_COMPLETED',
            'basis': scenario['basis'], 'facility_id': scenario['id'], 'engineering_fixture': True,
            'state_visibility': 'PRIVATE_PLANT_EVALUATOR_ONLY', 'dispatch_interface': 'PUBLIC_SELECTION_WITH_PRIVATE_EXECUTION' if dispatch is not None else 'DISABLED_FOR_THIS_RUN',
            'field_calibration': 'PENDING', 'research_gain_claim': 'NOT_ESTABLISHED',
            'research_trials': 0, 'model_calls': 0, 'training_calls': 0,
            'scenario_sha256': digest(scenario), 'source_config': scenario, 'code_identity': _code_identity(),
            'property_reference': {'sha256': table.sha256, 'source': table.source, 'validity': table.validity},
            'time_coordinate_convention': deepcopy(TIME_COORDINATE_CONVENTION),
            **({'workforce_public_feedback': workforce.public_feedback(duration)} if work_program is not None else {}),
            **({'inspection_public_snapshot': inspections.snapshot(duration),
                'inspection_public_models': inspections.public_models(),
                'inspection_public_feedback': inspections.public_feedback(duration),
                'inspection_private_audit': inspections.private_audit()} if inspections is not None else {}),
            **({'intervention_public_feedback': interventions.public_feedback(duration),
                'intervention_private_audit': interventions.private_audit()} if interventions is not None else {}),
            **({'policy_public_decisions': deepcopy(dispatch.decisions)} if dispatch is not None else {}),
            **({'policy_computation_audit': deepcopy(dispatch.computation_audit)} if dispatch is not None else {}),
            **({'policy_public_resource_ledger': dispatch.resource_ledger(duration,workforce,inspections)}
                if dispatch is not None and dispatch.program['policy_program']['schema'] in {'aegisdc-dispatch-policy-program-v3','aegisdc-dispatch-policy-program-v4'} else {}),
            **({'policy_sensor_private_audit': deepcopy(dispatch.sensors.audit)} if dispatch is not None and dispatch.sensors is not None else {}),
            'inputs': {'duration_s': duration, 'maximum_step_s': step, 'work_requests': [] if work_program is not None else workforce.requests,
                       **({'dispatch_program': deepcopy(dispatch_program)} if dispatch is not None else {}),
                       **({'work_program': deepcopy(work_program)} if work_program is not None else {}),
                       **({'inspection_program': deepcopy(inspection_program)} if inspections is not None else {}),
                       **({'intervention_program': deepcopy(intervention_program)} if interventions is not None else {}),
                       'boundary_events': boundary_inputs, **({'action_commands': commands} if commands else {})},
            'summary': summary, 'trace': trace, 'balances': balances, 'events': plant.events, 'work_records': workforce.records}


def describe_run(result):
    """Compact engineering metadata/summary, without private state or config."""
    return {key: value for key, value in result.items() if key not in {'trace', 'balances', 'source_config'}}


def save_run(result, directory):
    """Write a new inspectable engineering artifact directory; never overwrite."""
    directory = Path(directory)
    manifest = deepcopy(describe_run(result))
    documents = {
        'scenario.json': json.dumps(result['source_config'], ensure_ascii=False, indent=2, allow_nan=False) + '\n',
        'private-state.jsonl': ''.join(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n' for row in result['trace']),
        'balances.jsonl': ''.join(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n' for row in result['balances']),
    }
    counts = {'scenario.json': 1, 'private-state.jsonl': len(result['trace']), 'balances.jsonl': len(result['balances'])}
    manifest['artifacts'] = {name: {'sha256': sha256(content.encode('utf-8')).hexdigest(), 'records': counts[name]}
                             for name, content in documents.items()}
    manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    directory.mkdir(parents=True, exist_ok=False)
    for name, content in documents.items():
        (directory / name).write_text(content, encoding='utf-8', newline='\n')
    (directory / 'run.json').write_text(manifest_text, encoding='utf-8', newline='\n')
    return manifest
