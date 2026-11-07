"""Admission checks for the fixed V6 water path before a declared run."""
from fractions import Fraction

from .heat_transfer import valve_loop_operating_point
from .reserve import RESERVE_MODEL
from .scenario import validate_scenario
from .thermodynamics import finite_number
from .time_coordinates import same_time

WATER_EVENT_PARAMETERS = frozenset({
    'internal_hot_leak_mass_flow', 'lake_valve_opening', 'internal_valve_opening',
    'pump_pressure_rise', 'internal_pump_pressure_rise', 'filter_resistance_multiplier',
})


def _epochs(events, rows, horizon):
    if type(events) not in (list, tuple):
        raise ValueError('Declare a sequence of water boundary events')
    ordered = []
    for event in events:
        if type(event) is not dict or set(event) != {'time_s','parameter_id','value','source_note'}:
            raise ValueError('Declare the water event parameter, value, time and source note')
        name = event['parameter_id']
        if not isinstance(name,str) or name not in WATER_EVENT_PARAMETERS:
            raise ValueError('Unsupported water envelope event parameter')
        time = finite_number(event['time_s'], 'Water event time')
        value = finite_number(event['value'], 'Water event value')
        lower, upper = rows[name]['valid_range']
        if not 0 <= time <= horizon or not lower <= value <= upper:
            raise ValueError('Water event outside the declared time or scalar domain')
        if not isinstance(event['source_note'],str) or not event['source_note'].strip():
            raise ValueError('Water event requires a source note')
        ordered.append((time,name,value))
    grouped = []
    for time, name, value in sorted(ordered):
        if not grouped or not same_time(time,grouped[-1][0]):
            grouped.append((time,{}))
        current = grouped[-1][1]
        if name in current:
            raise ValueError('Conflicting water inputs at one processing epoch')
        current[name] = value
    return grouped


def _head_points(p):
    loops = {
        'lake': (p['pump_pressure_rise'], p['lake_hydraulic_resistance'] * p['filter_resistance_multiplier'],
                 p['lake_valve_open_resistance'], p['lake_valve_opening'], p['pump_efficiency']),
        'internal': (p['internal_pump_pressure_rise'], p['internal_hydraulic_resistance'],
                     p['internal_valve_open_resistance'], p['internal_valve_opening'], p['internal_pump_efficiency']),
    }
    points = {}
    for name, values in loops.items():
        point = valve_loop_operating_point(*values, 1)
        fluid_heat = p['pump_fluid_heat_fraction'] * point['electric_power_W']
        if point['hydraulic_power_W'] > 0 and p['pump_fluid_heat_fraction'] < values[-1]:
            raise ValueError(f'{name} fluid heat excludes part of the hydraulic dissipation when its pump can run')
        points[name] = {key: point[key] for key in (
            'volume_flow_m3_s','pressure_rise_Pa','hydraulic_power_W','electric_power_W','closed_valve_interlock',
        )}
        points[name]['fluid_heat_W'] = fluid_heat
    return points


def assess_water_envelope(scenario, *, horizon_s, events=()):
    """Check inventory and possible pump dissipation, without asserting actual delivery."""
    validate_scenario(scenario)
    if scenario.get('runtime',{}).get('model') != RESERVE_MODEL:
        raise ValueError('The water envelope is declared only for the complete V6 facility')
    rows = {row['id']:row for row in scenario['parameters']}
    p = {name:row['value'] for name,row in rows.items()}
    horizon = finite_number(horizon_s, 'Water envelope horizon', positive=True)
    low, high = rows['duration']['valid_range']
    if not low <= horizon <= high:
        raise ValueError('Water envelope horizon outside the declared V6 run range')
    groups = _epochs(events,rows,horizon)
    if groups and same_time(0.0,groups[0][0]):
        _, changes = groups.pop(0)
        p.update(changes)
    stages = [(0.0,{})] + groups
    loss = Fraction(0)
    trace = []
    for i,(start,changes) in enumerate(stages):
        p.update(changes)
        end = stages[i+1][0] if i+1 < len(stages) else horizon
        rate = p['internal_hot_leak_mass_flow']
        loss += Fraction(rate) * (Fraction(end) - Fraction(start))
        trace.append(dict(start_s=start,end_s=end,leak_kg_s=rate,
                          maximum_command_requested_pumps=_head_points(p)))
    initial = Fraction(p['internal_hot_mass'])
    minimum = Fraction(p['minimum_internal_hot_mass'])
    terminal = initial-loss
    if terminal < minimum:
        raise ValueError('Declared hot-water inventory would fall below the hydraulic minimum before the horizon')
    return dict(status='STATIC_WATER_ENVELOPE_ONLY',horizon_s=horizon,regimes=trace,
        hot_inventory=dict(initial_hot_mass_kg=float(initial),minimum_hot_mass_kg=float(minimum),
                           declared_loss_kg=float(loss),terminal_hot_mass_kg=float(terminal),
                           margin_kg=float(terminal-minimum)),
        scope='Requested maximum-speed points and declared piecewise leak inventory only; actual power, thermal and timed feasibility require a run.')
