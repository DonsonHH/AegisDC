"""Sampled local protection, independent of supervisory dispatch and true state."""
import math

from .thermodynamics import finite_number

CONTROL_PROFILE = 'aegisdc-local-control-faults-v1'
CONTROL_QUANTITIES = {
    'local_temperature_bias': 'temperature_offset',
    'local_internal_flow_bias': 'volume_flow_offset',
    'local_temperature_sensor_valid': 'fraction',
    'local_internal_flow_sensor_valid': 'fraction',
    'supervisory_link_available': 'fraction',
}
CONTROL_BINARY_PARAMETERS = frozenset(CONTROL_QUANTITIES) - {
    'local_temperature_bias', 'local_internal_flow_bias'}


def validate_control_profile(runtime, parameters):
    """Validate the only implemented nonideal profile and explicit SI records."""
    if 'local_control_profile' not in runtime:
        return
    if runtime['local_control_profile'] != CONTROL_PROFILE:
        raise ValueError('Unsupported local control profile in the closed contract')
    for name, quantity in CONTROL_QUANTITIES.items():
        if name not in parameters or parameters[name]['quantity'] != quantity:
            raise ValueError('Local control profile requires SI parameter ' + name + ' of quantity ' + quantity)
        if name in CONTROL_BINARY_PARAMETERS:
            row = parameters[name]
            if row['value'] not in (0, 1) or any(limit not in (0, 1) for limit in row['valid_range']):
                raise ValueError('Local control availability must have binary 0/1 value and range: ' + name)


def _finite_report(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def sample_local_control(previous, parameters, measurement, *, controller_power_W):
    """Take one powered local sample; the caller owns its explicit sample clock.

    Only reported quantities are accepted, never a plant/evaluator object or
    future failure label. Invalid channels latch compute off at full pump command.
    A restored valid sample must satisfy the thermal-reset and flow gates.
    Supervisory communication has no authority to disable local protection.
    """
    p = {name: finite_number(parameters[name], 'Local control ' + name) for name in (
        'controller_power', 'protection_temperature', 'protection_reset_temperature',
        'minimum_internal_volume_flow', 'cooling_setpoint', 'control_hysteresis', 'pump_min_speed')}
    if min(p.values()) < 0 or not 0 <= p['pump_min_speed'] <= 1 \
            or not 0 < p['protection_reset_temperature'] < p['protection_temperature'] \
            or p['cooling_setpoint'] <= 0:
        raise ValueError('Local controller settings outside their declared domain')
    power = finite_number(controller_power_W, 'Supplied controller power')
    time_s = finite_number(measurement['observed_at_s'], 'Local measurement time')
    if min(power, time_s) < 0 or type(previous['protection_latched']) is not bool:
        raise ValueError('Local control requires nonnegative power/time and a boolean latch')
    command = finite_number(previous['pump_speed_command'], 'Held pump command')
    if not p['pump_min_speed'] <= command <= 1:
        raise ValueError('Held pump command outside declared actuator bounds')
    for flag in ('temperature_valid', 'flow_valid', 'supervisory_connected'):
        if type(measurement[flag]) is not bool:
            raise ValueError('Local measurement validity and connection flags must be boolean')
    temperature, flow = measurement['temperature_K'], measurement['internal_volume_flow_m3_s']
    temperature_finite = _finite_report(temperature)
    flow_finite = _finite_report(flow)
    powered = p['controller_power'] > 0 and power >= p['controller_power']
    temperature_valid = measurement['temperature_valid'] and temperature_finite and temperature > 0
    flow_valid = measurement['flow_valid'] and flow_finite and flow >= 0
    valid = powered and temperature_valid and flow_valid
    reasons = ([] if temperature_valid else ['temperature_channel_invalid']) + \
              ([] if flow_valid else ['flow_channel_invalid'])
    local = {'observed_at_s': time_s if powered else None, 'sampled_at_s': time_s,
             'temperature_K': temperature if powered and temperature_finite else None,
             'internal_volume_flow_m3_s': flow if powered and flow_finite else None,
             'temperature_valid': bool(powered and temperature_valid),
             'flow_valid': bool(powered and flow_valid), 'valid': bool(valid),
             'invalid_reasons': reasons if powered else ['controller_unpowered'],
             'controller_power_W': power, 'visibility': 'LOCAL_PLANT_ONLY'}
    state = dict(previous, local_measurement=local,
                 supervisory_mode='connected' if measurement['supervisory_connected'] else 'autonomous')
    if not powered:
        return dict(state, mode='unpowered_fail_safe', compute_permitted=False, pump_speed_command=1.0)
    if not valid:
        return dict(state, mode='sensor_invalid_fail_safe', protection_latched=True,
                    compute_permitted=False, pump_speed_command=1.0)
    trip = temperature >= p['protection_temperature'] or flow < p['minimum_internal_volume_flow']
    if trip:
        state['protection_latched'] = True
    elif temperature <= p['protection_reset_temperature'] and flow >= p['minimum_internal_volume_flow']:
        state['protection_latched'] = False
    state.update(mode='protected' if state['protection_latched'] else 'normal',
                 compute_permitted=not state['protection_latched'])
    if temperature >= p['cooling_setpoint']:
        state['pump_speed_command'] = 1.0
    elif temperature <= p['cooling_setpoint'] - p['control_hysteresis']:
        state['pump_speed_command'] = p['pump_min_speed']
    return state
