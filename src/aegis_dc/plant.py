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
from .heat_transfer import counterflow_exchange, pump_operating_point
from .power import allocate_power
from .scenario import validate_scenario
from .thermodynamics import SaturationTable, finite_number
from .workforce import Workforce

ROOT = Path(__file__).resolve().parents[2]
EXOGENOUS_PARAMETERS = {
    'grid_capacity', 'compute_demand_power', 'network_demand_power', 'storage_demand_power',
    'compute_service_capacity', 'network_service_capacity', 'storage_service_capacity',
    'service_demand', 'lake_temperature', 'filter_resistance_multiplier',
    'room_aux_power', 'floor_water_inflow', 'drainage_mass_flow',
}


def _boundary_events(rows, parameters, duration):
    if not isinstance(rows, (list, tuple)):
        raise ValueError('Boundary events must be a declared list')
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'time_s', 'parameter_id', 'value', 'source_note'}:
            raise ValueError('Declare each timed boundary input with parameter, value and source note')
        time_s = finite_number(row['time_s'], 'Boundary event time')
        name = row['parameter_id']
        if not isinstance(name, str) or name not in EXOGENOUS_PARAMETERS:
            raise ValueError('Boundary event parameter is not an exogenous input')
        value = finite_number(row['value'], 'Boundary event value')
        low, high = parameters[name]['valid_range']
        if not 0 <= time_s <= duration or not low <= value <= high:
            raise ValueError('Boundary event time/value outside declared range')
        if not isinstance(row['source_note'], str) or not row['source_note'].strip():
            raise ValueError('Boundary event requires source_note')
        if (time_s, name) in seen:
            raise ValueError('Conflicting boundary event at the same time and parameter')
        seen.add((time_s, name))
        result.append(dict(row, time_s=time_s, value=value))
    return sorted(result, key=lambda item: item['time_s'])


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


class _Plant:
    def __init__(self, scenario, table):
        self.scenario, self.table = scenario, table
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
        self.floor_mass = p['initial_floor_water_mass']
        self.floor_access_blocked = self.floor_mass >= p['access_block_mass']
        self.control = {'mode': 'normal', 'protection_latched': False,
                        'compute_permitted': True, 'pump_speed_command': 1.0,
                        'local_measurement': None}
        self.next_sample = 0.0
        self.generator_mode, self.generator_ready = 'off', None
        self.events = []

    def temperatures(self):
        return {key: self.energy[key] / capacity for key, capacity in self.capacities.items()}

    def refrigerant(self):
        return self.table.flash(self.p['coolant_inventory'], self.energy['coolant'],
                                self.p['coolant_control_volume'])

    def stored_energy(self):
        p = self.p
        return math.fsum(self.energy.values()) + self.floor_mass * p['water_specific_heat'] * p['room_ambient_temperature']

    def blocked_locations(self):
        locations = set(self.scenario['runtime']['closed_location_ids'])
        if self.floor_access_blocked:
            locations.add('loc_it')
        return locations

    def discrete(self, time_s):
        p = self.p
        if self.floor_access_blocked and self.floor_mass == p['access_block_mass'] \
                and p['floor_water_inflow'] < p['drainage_mass_flow']:
            self.floor_access_blocked = False
            self.events.append({'time_s': time_s, 'kind': 'floor_access_opened', 'split_step': True})
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

    def point(self):
        p, control = self.p, self.control
        speed = control['pump_speed_command']
        lake_args = (p['pump_pressure_rise'], p['lake_hydraulic_resistance'] * p['filter_resistance_multiplier'],
                     p['pump_efficiency'], speed)
        internal_args = (p['internal_pump_pressure_rise'], p['internal_hydraulic_resistance'],
                         p['internal_pump_efficiency'], speed)
        requested = {'intake_pump': pump_operating_point(*lake_args)['electric_power_W'],
                     'internal_pump': pump_operating_point(*internal_args)['electric_power_W']}
        power = allocate_power(p, requested, control['compute_permitted'], self.energy['ups'],
                                self.generator_mode == 'running', self.energy['fuel'])
        actual = power['actual_powers_W']
        lake = pump_operating_point(*lake_args, available_power_W=actual['intake_pump'])
        internal = pump_operating_point(*internal_args, available_power_W=actual['internal_pump'])
        t, r = self.temperatures(), self.refrigerant()
        ci = p['water_density'] * p['water_specific_heat'] * internal['volume_flow_m3_s']
        cl = p['water_density'] * p['water_specific_heat'] * lake['volume_flow_m3_s']
        fraction = p['pump_fluid_heat_fraction']
        lake_pump_heat = fraction * actual['intake_pump']
        lake_inlet = p['lake_temperature'] + lake_pump_heat / cl if cl else p['lake_temperature']
        hx = counterflow_exchange(p['plate_hx_conductance'], ci, cl, t['hot'], lake_inlet)
        condenser = -math.expm1(-p['condenser_conductance'] / ci) * ci \
            * (r['temperature_K'] - t['cold']) if ci else 0.0
        solid_coolant = p['solid_coolant_conductance'] * (t['solid'] - r['temperature_K'])
        solid_air = p['solid_air_conductance'] * (t['solid'] - t['room'])
        room_out = p['room_conductance'] * (t['room'] - p['room_ambient_temperature'])
        circulation = ci * (t['hot'] - t['cold'])
        room_input = (actual['network'] + actual['local_controller'] + actual['room']
                      + power['rectifier_loss_W'] + power['ups_loss_W'] + solid_air
                      + (1 - fraction) * (actual['intake_pump'] + actual['internal_pump']))
        capacities = {name: min(p[name + '_service_capacity'], actual[name] / p[name + '_nominal_power'])
                      for name in ('compute', 'network', 'storage')}
        delivery = min(p['service_demand'], *capacities.values())
        drain = p['drainage_mass_flow'] if self.floor_mass > 0 else min(p['floor_water_inflow'], p['drainage_mass_flow'])
        return {'power': power, 'lake_pump': lake, 'internal_pump': internal, 'hx': hx,
                'temperatures': t, 'refrigerant': r, 'lake_inlet_K': lake_inlet,
                'condenser_heat_W': condenser, 'solid_coolant_heat_W': solid_coolant,
                'solid_air_heat_W': solid_air, 'room_out_W': room_out,
                'lake_out_W': hx['heat_W'] + lake_pump_heat,
                'drain_kg_s': drain, 'circulation_W': circulation,
                'service': {'demand': p['service_demand'], 'delivered': delivery,
                            'capacities': capacities, 'unserved': p['service_demand'] - delivery},
                'rates_W': {
                    'solid': actual['compute'] - solid_coolant - solid_air,
                    'room': room_input - room_out,
                    'coolant': solid_coolant - condenser,
                    'hot': condenser + actual['storage'] + fraction * actual['internal_pump'] - circulation,
                    'cold': circulation - hx['heat_W'],
                    'ups': -power['ups_depletion_W'], 'fuel': -power['fuel_depletion_W'],
                }}

    def sample_control(self, time_s, point):
        if time_s < self.next_sample:
            return
        p, c = self.p, self.control
        power = point['power']['actual_powers_W']['local_controller']
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
        self.next_sample = time_s + p['control_sample_time']

    def next_physical_event(self, time_s, point):
        times = [self.next_sample]
        if self.generator_mode == 'starting':
            times.append(self.generator_ready)
        for key, depletion in [('ups', point['power']['ups_depletion_W']),
                               ('fuel', point['power']['fuel_depletion_W'])]:
            if depletion > 0 and self.energy[key] > 0:
                times.append(time_s + self.energy[key] / depletion)
        floor_rate = self.p['floor_water_inflow'] - point['drain_kg_s']
        if floor_rate < 0 and self.floor_mass > 0:
            times.append(time_s + self.floor_mass / -floor_rate)
            if self.floor_mass > self.p['access_block_mass']:
                times.append(time_s + (self.floor_mass - self.p['access_block_mass']) / -floor_rate)
        if floor_rate > 0 and self.floor_mass < self.p['access_block_mass']:
            times.append(time_s + (self.p['access_block_mass'] - self.floor_mass) / floor_rate)
        return min(value for value in times if value > time_s)

    def integrate(self, start, end, point):
        dt, p = end - start, self.p
        before = self.energy.copy()
        old_floor, old_total = self.floor_mass, self.stored_energy()
        for name, rate in point['rates_W'].items():
            if rate < 0 and before[name] > 0 and math.isclose(dt, before[name] / -rate,
                                                            rel_tol=1e-12, abs_tol=1e-12) \
                    and name in {'ups', 'fuel'}:
                self.energy[name] = 0.0
                self.events.append({'time_s': end, 'kind': name + '_depleted', 'split_step': True})
            else:
                self.energy[name] += rate * dt
            if not math.isfinite(self.energy[name]) or self.energy[name] < 0:
                raise ValueError('Invalid energy inventory at ' + str(end) + ' s: ' + name)
        floor_rate = p['floor_water_inflow'] - point['drain_kg_s']
        if floor_rate < 0 and math.isclose(dt, old_floor / -floor_rate, rel_tol=1e-12, abs_tol=1e-12):
            self.floor_mass = 0.0
        else:
            self.floor_mass += floor_rate * dt
        if self.floor_mass < 0 or not math.isfinite(self.floor_mass):
            raise ValueError('Invalid floor-water inventory')
        threshold = p['access_block_mass']
        if old_floor < threshold <= self.floor_mass and floor_rate > 0:
            self.floor_access_blocked = True
            self.events.append({'time_s': end, 'kind': 'floor_access_closed', 'split_step': True})
        elif self.floor_mass <= threshold < old_floor and floor_rate < 0:
            self.floor_access_blocked = False
            self.events.append({'time_s': end, 'kind': 'floor_access_opened', 'split_step': True})
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
        floor_out = point['drain_kg_s'] * p['water_specific_heat'] * p['room_ambient_temperature']
        boundary_input = power['grid_draw_W'] + floor_in
        boundary_output = point['lake_out_W'] + point['room_out_W'] + power['generator_waste_W'] + floor_out
        energy_residuals['facility'] = self.stored_energy() - old_total - (boundary_input - boundary_output) * dt
        old_r = point['refrigerant']
        internal_flow = point['internal_pump']['volume_flow_m3_s'] * p['water_density']
        lake_flow = point['lake_pump']['volume_flow_m3_s'] * p['water_density']
        mass_accounts = {
            'refrigerant': {'before_kg': old_r['liquid_mass_kg'] + old_r['vapor_mass_kg'],
                            'after_kg': new_refrigerant['liquid_mass_kg'] + new_refrigerant['vapor_mass_kg'],
                            'in_kg': 0.0, 'out_kg': 0.0},
            'floor_water': {'before_kg': old_floor, 'after_kg': self.floor_mass,
                            'in_kg': p['floor_water_inflow'] * dt, 'out_kg': point['drain_kg_s'] * dt},
            'lake_throughflow': {'before_kg': 0.0, 'after_kg': 0.0,
                                'in_kg': lake_flow * dt, 'out_kg': lake_flow * dt},
        }
        for name, mass in [('internal_hot', p['internal_hot_mass']), ('internal_cold', p['internal_cold_mass'])]:
            mass_accounts[name] = {'before_kg': mass, 'after_kg': mass,
                                  'in_kg': internal_flow * dt, 'out_kg': internal_flow * dt}
        mass_residuals = {name: math.fsum((row['before_kg'], row['in_kg'], -row['out_kg'], -row['after_kg']))
                          for name, row in mass_accounts.items()}
        electrical_residual = power['grid_draw_W'] + power['generator_output_W'] + power['ups_output_W'] \
            - sum(power['actual_powers_W'].values()) - power['rectifier_loss_W']
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
                'storage_before_J': dict(before, floor_water=old_floor * p['water_specific_heat'] * p['room_ambient_temperature']),
                'storage_after_J': dict(self.energy, floor_water=self.floor_mass * p['water_specific_heat'] * p['room_ambient_temperature']),
                'component_energy_rates_W': point['rates_W'],
                'heat_transfers_W': {'solid_to_coolant': point['solid_coolant_heat_W'],
                                     'solid_to_room': point['solid_air_heat_W'],
                                     'coolant_to_internal_water': point['condenser_heat_W'],
                                     'plate_hx_to_lake': point['hx']['heat_W'],
                                     'internal_hot_to_cold_advection': point['circulation_W']},
                'capacity_slack_W': power['capacity_slack_W'],
                'boundary_input_J': boundary_input * dt, 'boundary_output_J': boundary_output * dt,
                'grid_energy_J': power['grid_draw_W'] * dt, 'lake_heat_J': point['lake_out_W'] * dt,
                'ups_output_energy_J': power['ups_output_W'] * dt,
                'ups_loss_energy_J': power['ups_loss_W'] * dt,
                'generator_output_energy_J': power['generator_output_W'] * dt,
                'generator_waste_energy_J': power['generator_waste_W'] * dt,
                'floor_water_inlet_mass_kg': p['floor_water_inflow'] * dt,
                'floor_water_drained_mass_kg': point['drain_kg_s'] * dt,
                'floor_inlet_energy_J': floor_in * dt, 'floor_drain_energy_J': floor_out * dt,
                'room_heat_J': point['room_out_W'] * dt,
                'demand_service_unit_s': point['service']['demand'] * dt,
                'delivered_service_unit_s': point['service']['delivered'] * dt,
                'service_deficit_time_s': point['service']['unserved'] / point['service']['demand'] * dt
                if point['service']['demand'] else 0.0}

    def snapshot(self, time_s, point, workforce):
        p, t = self.p, point['temperatures']
        return {'time_s': time_s, 'domains': {
            'power': point['power'],
            'backup': {'ups_energy_J': self.energy['ups'], 'fuel_energy_J': self.energy['fuel'],
                       'generator_mode': self.generator_mode, 'generator_ready_at_s': self.generator_ready,
                       'backup_tower_mode': 'standby_uncommanded'},
            'facility_cooling': {'hot_temperature_K': t['hot'], 'cold_temperature_K': t['cold'],
                                 'hot_mass_kg': p['internal_hot_mass'], 'cold_mass_kg': p['internal_cold_mass'],
                                 'lake_pump': point['lake_pump'], 'internal_pump': point['internal_pump'],
                                 'internal_mass_flow_kg_s': point['internal_pump']['volume_flow_m3_s'] * p['water_density'],
                                 'lake_mass_flow_kg_s': point['lake_pump']['volume_flow_m3_s'] * p['water_density'],
                                 'lake_hx_inlet_K': point['lake_inlet_K'],
                                 'internal_hx_outlet_K': point['hx']['hot_outlet_K'],
                                 'lake_hx_outlet_K': point['hx']['cold_outlet_K'],
                                 'plate_hx_heat_W': point['hx']['heat_W'],
                                 'condenser_heat_W': point['condenser_heat_W']},
            'equipment_environment': {'solid_temperature_K': t['solid'], 'room_temperature_K': t['room'],
                                      'room_humidity': p['room_humidity'], 'refrigerant': point['refrigerant'],
                                      'solid_coolant_heat_W': point['solid_coolant_heat_W'],
                                      'solid_air_heat_W': point['solid_air_heat_W']},
            'it_service': point['service'], 'control_monitoring': deepcopy(self.control),
            'space_access': {'floor_water_mass_kg': self.floor_mass, 'drain_kg_s': point['drain_kg_s'],
                              'blocked_location_ids': sorted(self.blocked_locations())},
            'people_tools_work': workforce.snapshot(),
        }}


def simulate_scenario(scenario, *, duration_s=None, step_s=None, work_requests=(), boundary_events=()):
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
    timed_inputs = _boundary_events(boundary_events, p_records, duration)
    event_index = 0
    runtime = scenario['runtime']
    table = SaturationTable.from_file(ROOT / runtime['property_table'], expected_sha256=runtime['property_sha256'])
    plant = _Plant(scenario, table)
    workforce = Workforce(scenario, plant.p, work_requests, duration)
    initial_energy = plant.stored_energy()
    time_s, trace, balances = 0.0, [], []
    while True:
        while event_index < len(timed_inputs) and timed_inputs[event_index]['time_s'] <= time_s:
            event = timed_inputs[event_index]
            plant.p[event['parameter_id']] = event['value']
            plant.events.append(dict(event, kind='exogenous_boundary_input'))
            event_index += 1
        plant.discrete(time_s)
        workforce.process(time_s, plant.blocked_locations())
        point = plant.point()
        plant.sample_control(time_s, point)
        point = plant.point()
        trace.append(plant.snapshot(time_s, point, workforce))
        if time_s >= duration:
            break
        next_input = timed_inputs[event_index]['time_s'] if event_index < len(timed_inputs) else duration
        end = min(duration, time_s + step, plant.next_physical_event(time_s, point), next_input,
                  workforce.next_event(time_s))
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
            'state_visibility': 'PRIVATE_PLANT_EVALUATOR_ONLY', 'dispatch_interface': 'NOT_IMPLEMENTED',
            'field_calibration': 'PENDING', 'research_gain_claim': 'NOT_ESTABLISHED',
            'research_trials': 0, 'model_calls': 0, 'training_calls': 0,
            'scenario_sha256': digest(scenario), 'source_config': scenario, 'code_identity': _code_identity(),
            'property_reference': {'sha256': table.sha256, 'source': table.source, 'validity': table.validity},
            'inputs': {'duration_s': duration, 'maximum_step_s': step, 'work_requests': workforce.requests, 'boundary_events': timed_inputs},
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
