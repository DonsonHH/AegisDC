"""Low-order replaceable hydraulic and heat-exchanger engineering boundaries."""
import math

from .thermodynamics import finite_number


def counterflow_exchange(conductance_W_K, hot_capacity_W_K, cold_capacity_W_K,
                         hot_inlet_K, cold_inlet_K):
    """Mass-separated, zero-wall-storage counterflow epsilon/NTU exchanger."""
    ua = finite_number(conductance_W_K, 'Exchanger conductance')
    ch = finite_number(hot_capacity_W_K, 'Hot capacity rate')
    cc = finite_number(cold_capacity_W_K, 'Cold capacity rate')
    th = finite_number(hot_inlet_K, 'Hot inlet temperature', positive=True)
    tc = finite_number(cold_inlet_K, 'Cold inlet temperature', positive=True)
    if min(ua, ch, cc) < 0:
        raise ValueError('Heat exchanger conductance and capacity rates must be nonnegative')
    effectiveness = 0.0
    if min(ch, cc) > 0:
        ntu = ua / min(ch, cc)
        ratio = min(ch, cc) / max(ch, cc)
        if ratio == 1:
            effectiveness = ntu / (1 + ntu)
        else:
            decay = math.exp(-ntu * (1 - ratio))
            effectiveness = -math.expm1(-ntu * (1 - ratio)) / (1 - ratio * decay)
    heat = effectiveness * min(ch, cc) * (th - tc)
    return {'heat_W': heat, 'effectiveness': effectiveness,
            'hot_outlet_K': th - heat / ch if ch else th,
            'cold_outlet_K': tc + heat / cc if cc else tc}


def pump_operating_point(head_Pa, resistance_Pa_s2_m6, efficiency, speed,
                         *, available_power_W=None):
    """Ideal speed-controlled fixed head against K q^2, with electrical limits.

    A zero command or zero head gives zero flow and power. Full electrical power
    is later allocated as heat once; hydraulic power must not be added again.
    """
    head = finite_number(head_Pa, 'Pump head')
    resistance = finite_number(resistance_Pa_s2_m6, 'Hydraulic resistance', positive=True)
    eta = finite_number(efficiency, 'Pump efficiency', positive=True)
    n = finite_number(speed, 'Pump speed')
    if head < 0 or not 0 <= n <= 1 or eta > 1:
        raise ValueError('Pump head/speed/efficiency outside declared hydraulic model')
    q = n * math.sqrt(head / resistance)
    pressure = head * n * n
    requested = pressure * q / eta
    if available_power_W is not None:
        available = finite_number(available_power_W, 'Available pump power')
        if available < 0:
            raise ValueError('Available pump power must be nonnegative')
        if requested > available:
            n *= (available / requested) ** (1 / 3)
            q = n * math.sqrt(head / resistance)
            pressure = head * n * n
    return {'volume_flow_m3_s': q, 'pressure_rise_Pa': pressure,
            'speed': n, 'hydraulic_power_W': pressure * q,
            'electric_power_W': pressure * q / eta, 'requested_power_W': requested}
