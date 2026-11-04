"""Finite, separately powered reserve actors and a paid sensible heat boundary.

These are synthetic engineering components, not site settings or real tower
performance. Callers integrate the independently reported energy rates and split
at the returned connection/depletion times.
"""
import math

from .heat_transfer import counterflow_exchange
from .thermodynamics import finite_number


def _binary(value, label):
    value = finite_number(value, label)
    if value not in (0, 1):
        raise ValueError(label + ' must be the exact numeric 0/1 state')
    return value


def _previous(previous, time_s, initial, modes):
    time = finite_number(time_s, 'Reserve time')
    state = dict(previous) if previous is not None else {'mode': initial, 'ready_at_s': None,
                                                        'requested_at_s': None, 'updated_at_s': 0.0}
    if time < 0 or state['mode'] not in modes or time < state['updated_at_s']:
        raise ValueError('Invalid reserve mode or backwards time')
    if state['ready_at_s'] is not None:
        finite_number(state['ready_at_s'], 'Reserve connection deadline')
    state['updated_at_s'] = time
    return state, time


def ups_transition(previous, *, time_s, needed, available, transfer_ok, energy_J,
                   control_power_W, nominal_control_power_W, delay_s):
    """UPS-internal actor; main PLC power is deliberately not an input.

    Supplied control power must come from the electrical budget. A disconnected
    protected output does not remove this separate finite-energy control path.
    """
    state, time = _previous(previous, time_s, 'bypass',
                            {'bypass', 'waiting', 'supplying', 'maintenance',
                             'depleted', 'unpowered', 'transfer_failed'})
    available, transfer_ok = _binary(available, 'UPS availability'), _binary(transfer_ok, 'UPS transfer')
    energy = finite_number(energy_J, 'UPS energy')
    control = finite_number(control_power_W, 'Supplied UPS control power')
    nominal = finite_number(nominal_control_power_W, 'UPS nominal control power', positive=True)
    delay = finite_number(delay_s, 'UPS connection delay')
    if min(energy, control, delay) < 0 or type(needed) is not bool:
        raise ValueError('UPS requires nonnegative energy/power/delay and a boolean local need')
    blocked = ('maintenance' if not available else 'depleted' if energy == 0
               else 'unpowered' if control < nominal else 'bypass' if not needed
               else 'transfer_failed' if state['mode'] == 'transfer_failed' and not transfer_ok else None)
    if blocked:
        state.update(mode=blocked, ready_at_s=None, requested_at_s=None)
    else:
        if state['mode'] not in {'waiting', 'supplying'}:
            state.update(mode='waiting', ready_at_s=time + delay, requested_at_s=time)
        if state['mode'] == 'waiting' and time >= state['ready_at_s']:
            state.update(mode='supplying' if transfer_ok else 'transfer_failed', ready_at_s=None)
        elif state['mode'] == 'supplying' and not transfer_ok:
            state.update(mode='transfer_failed', ready_at_s=None)
    state['request_actor'] = 'UPS_INTERNAL_CONTROL'
    return state


def generator_transition(previous, *, time_s, mains_present, available, start_ok,
                         transfer_ok, fuel_energy_J, starter_energy_J,
                         control_power_W, nominal_control_power_W,
                         start_delay_s, transfer_delay_s):
    """Separately powered genset sequencer; connection is later than readiness."""
    state, time = _previous(previous, time_s, 'off',
        {'off', 'starting', 'transferring', 'supplying', 'maintenance', 'fuel_exhausted',
         'starter_depleted', 'unpowered', 'start_failed', 'transfer_failed'})
    available = _binary(available, 'Diesel availability')
    start_ok, transfer_ok = _binary(start_ok, 'Diesel start'), _binary(transfer_ok, 'Diesel transfer')
    fuel = finite_number(fuel_energy_J, 'Fuel energy')
    starter = finite_number(starter_energy_J, 'Starter energy')
    control = finite_number(control_power_W, 'Supplied generator control power')
    nominal = finite_number(nominal_control_power_W, 'Generator control power', positive=True)
    start = finite_number(start_delay_s, 'Generator start delay')
    transfer = finite_number(transfer_delay_s, 'Generator transfer delay')
    if min(fuel, starter, control, start, transfer) < 0 or type(mains_present) is not bool:
        raise ValueError('Generator requires finite nonnegative stores/power/delays and a boolean mains record')
    blocked = ('off' if mains_present else 'maintenance' if not available
               else 'fuel_exhausted' if fuel == 0 else 'starter_depleted'
               if starter == 0 and state['mode'] != 'supplying' else 'unpowered' if control < nominal
               else 'start_failed' if state['mode'] == 'start_failed' and not start_ok
               else 'transfer_failed' if state['mode'] == 'transfer_failed' and not transfer_ok else None)
    if blocked:
        state.update(mode=blocked, ready_at_s=None, requested_at_s=None)
    else:
        if state['mode'] not in {'starting', 'transferring', 'supplying'}:
            state.update(mode='starting', ready_at_s=time + start, requested_at_s=time)
        if state['mode'] == 'starting' and time >= state['ready_at_s']:
            state.update(mode='transferring' if start_ok else 'start_failed',
                         ready_at_s=time + transfer if start_ok else None)
        if state['mode'] == 'transferring' and time >= state['ready_at_s']:
            state.update(mode='supplying' if transfer_ok else 'transfer_failed', ready_at_s=None)
        elif state['mode'] == 'supplying' and not transfer_ok:
            state.update(mode='transfer_failed', ready_at_s=None)
    state['request_actor'] = 'GENERATOR_INTERNAL_CONTROL'
    return state


def paid_backup_exchange(parameters, *, water_capacity_W_K, water_inlet_K,
                         external_inlet_K, fan_power_W, connected=True):
    """Zero-hold-up sensible surrogate; fan heat leaves through the air once.

    The proportional actual-power map is an explicit research approximation,
    not an evaporative tower/fan curve or inferred site performance.
    """
    nominal = finite_number(parameters['backup_fan_nominal_power'], 'Nominal fan power', positive=True)
    air_nominal = finite_number(parameters['backup_air_capacity_rate'], 'Air capacity rate', positive=True)
    ua_nominal = finite_number(parameters['backup_conductance'], 'Backup conductance')
    cap = finite_number(parameters['backup_heat_capacity'], 'Backup heat capacity')
    fan = finite_number(fan_power_W, 'Actual fan power')
    water = finite_number(water_capacity_W_K, 'Water capacity rate')
    tw = finite_number(water_inlet_K, 'Water inlet temperature', positive=True)
    ta = finite_number(external_inlet_K, 'External air temperature', positive=True)
    if min(ua_nominal, cap, fan, water) < 0 or fan > nominal or type(connected) is not bool:
        raise ValueError('Backup exchanger power/capacity/connection outside declared domain')
    fraction = fan / nominal
    air, ua = fraction * air_nominal, fraction * ua_nominal
    raw = counterflow_exchange(ua, water, air, tw, ta)['heat_W'] if connected else 0.0
    heat = math.copysign(min(abs(raw), cap), raw)
    return {'heat_W': heat, 'outside_heat_W': heat + fan, 'fan_power_W': fan,
            'water_outlet_K': tw - heat / water if water else tw,
            'air_hx_outlet_K': ta + heat / air if air else None,
            'air_outlet_K': ta + (heat + fan) / air if air else None,
            'air_capacity_W_K': air, 'conductance_W_K': ua, 'capacity_fraction': fraction}


def cooling_transition(previous, *, time_s, sampled, requested, available,
                       transfer_ok, controller_power_W, nominal_controller_power_W, delay_s):
    """Only a paid main-PLC sample accepts a new selector command.

    An active selector can hold its accepted position without a new command;
    interrupted switching returns to its declared passive primary position.
    """
    state, time = _previous(previous, time_s, 'primary',
                            {'primary', 'switching', 'active', 'maintenance', 'transfer_failed'})
    requested, available = _binary(requested, 'Cooling request'), _binary(available, 'Cooling availability')
    transfer_ok = _binary(transfer_ok, 'Cooling transfer')
    power = finite_number(controller_power_W, 'Supplied main controller power')
    nominal = finite_number(nominal_controller_power_W, 'Nominal main controller power', positive=True)
    delay = finite_number(delay_s, 'Cooling connection delay')
    if min(power, delay) < 0 or type(sampled) is not bool:
        raise ValueError('Cooling transition requires nonnegative power/delay and a boolean sample')
    powered = power >= nominal
    if not available:
        state.update(mode='maintenance', ready_at_s=None, requested_at_s=None)
    elif state['mode'] == 'active' and not transfer_ok:
        state.update(mode='transfer_failed', ready_at_s=None)
    elif state['mode'] == 'switching' and not powered:
        state.update(mode='primary', ready_at_s=None, requested_at_s=None)
    elif sampled and powered:
        if not requested:
            state.update(mode='primary', ready_at_s=None, requested_at_s=None)
        elif state['mode'] not in {'switching', 'active'} \
                and not (state['mode'] == 'transfer_failed' and not transfer_ok):
            state.update(mode='switching', ready_at_s=time + delay, requested_at_s=time)
    if state['mode'] == 'switching' and powered and time >= state['ready_at_s']:
        state.update(mode='active' if transfer_ok else 'transfer_failed', ready_at_s=None)
    state['request_actor'] = 'POWERED_MAIN_PLC_SAMPLE'
    return state
