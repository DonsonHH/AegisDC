"""Bounded sensible-water storage and condensation-risk engineering boundaries."""
import math

from .thermodynamics import finite_number


def _liquid_water_saturation_pressure(temperature_K):
    temperature = finite_number(temperature_K, 'Condensation boundary temperature', positive=True)
    if not 273.16 <= temperature <= 333.15:
        raise ValueError('Condensation criterion supports liquid-water temperatures in [273.16,333.15] K only')
    # ASHRAE 2017 Fundamentals ch.1 eq.6 (SI liquid-water branch), verified
    # against the official PsychroLib 2.5.0 source; see primary-source-receipt.
    logarithm = (-5800.2206 / temperature + 1.3914993 - 0.048640239 * temperature
                 + 0.000041764768 * temperature ** 2 - 0.000000014452093 * temperature ** 3
                 + 6.5459673 * math.log(temperature))
    return math.exp(logarithm)


def condensation_risk(air_temperature_K, relative_humidity, surface_temperature_K):
    """Compare a prescribed RH boundary to surface saturation, without moisture flux.

    This does not predict condensate mass, latent heat, wetting, damage or a
    dispatch observation. The facility declares which temperature is its proxy
    for an exposed surface; the criterion itself has no wall/geometry model.
    """
    humidity = finite_number(relative_humidity, 'Relative humidity')
    if not 0 <= humidity <= 1:
        raise ValueError('Relative humidity must stay in [0,1]')
    vapor = humidity * _liquid_water_saturation_pressure(air_temperature_K)
    saturation = _liquid_water_saturation_pressure(surface_temperature_K)
    return {'classification': 'BOUNDARY_RISK_ONLY_NO_CONDENSATE_OR_LATENT_HEAT',
            'air_vapor_pressure_Pa': vapor, 'surface_saturation_pressure_Pa': saturation,
            'margin_Pa': saturation - vapor, 'condensation_risk': vapor >= saturation}


def floor_water_step(mass_kg, energy_J, specific_heat_J_kg_K, inflow_kg_s,
                     inflow_energy_W, drain_kg_s, duration_s):
    """Advance one well-mixed, adiabatic floor-water pool, without evaporation.

    All water uses the same declared constant cp and zero-K sensible reference.
    The caller splits at empty inventory; no negative water or lost heat is
    hidden by clipping. Returned drain heat is an integrated energy boundary.
    """
    mass = finite_number(mass_kg, 'Floor-water mass')
    energy = finite_number(energy_J, 'Floor-water energy')
    cp = finite_number(specific_heat_J_kg_K, 'Water specific heat', positive=True)
    inlet = finite_number(inflow_kg_s, 'Floor-water inflow')
    inlet_power = finite_number(inflow_energy_W, 'Floor-water inlet energy rate')
    drain = finite_number(drain_kg_s, 'Floor-water drain')
    dt = finite_number(duration_s, 'Floor-water interval', positive=True)
    if min(mass, energy, inlet, inlet_power, drain) < 0 or (mass == 0) != (energy == 0):
        raise ValueError('Floor-water mass and sensible energy require a consistent nonnegative inventory')
    if (inlet == 0) != (inlet_power == 0):
        raise ValueError('A positive water inflow requires its positive sensible-energy inflow')
    after_mass = math.fsum([mass, inlet * dt, -drain * dt])
    if after_mass < 0:
        if mass > 0 and drain > inlet and math.isclose(dt, mass / (drain - inlet), rel_tol=1e-12, abs_tol=1e-12):
            after_mass = 0.0  # coordinate roundoff at the declared exact empty event
        else:
            raise ValueError('Split the floor-water interval at exact empty inventory')
    incoming_energy = inlet_power * dt
    if after_mass == 0:
        after_energy = 0.0
    elif drain == 0:
        after_energy = energy + incoming_energy
    elif inlet == 0:
        after_energy = energy * (after_mass / mass)
    elif mass == 0:
        after_energy = after_mass * inlet_power / inlet
    else:
        inlet_temperature = inlet_power / (inlet * cp)
        initial_temperature = energy / (mass * cp)
        net = inlet - drain
        exponent = -inlet * dt / mass if net == 0 else -inlet / net * math.log1p(net * dt / mass)
        temperature = inlet_temperature + (initial_temperature - inlet_temperature) * math.exp(exponent)
        after_energy = after_mass * cp * temperature
    # Integrate the drain boundary directly. Subtracting two large stored
    # energies loses small positive outflows and can forge a negative outflow
    # when the known boundary is exactly zero.
    if drain == 0:
        drained_energy = 0.0
    elif after_mass == 0:
        drained_energy = math.fsum([energy, incoming_energy])
    elif inlet == 0:
        drained_energy = drain * dt * (energy / mass)
    elif mass == 0:
        drained_energy = drain * dt * inlet_power / inlet
    else:
        inlet_specific_energy = inlet_power / inlet
        net = inlet - drain
        exponent = -drain * dt / mass if net == 0 else -drain / net * math.log1p(net * dt / mass)
        drained_energy = math.fsum([drain * dt * inlet_specific_energy,
            (energy - mass * inlet_specific_energy) * -math.expm1(exponent)])
    if not math.isfinite(after_energy) or after_energy < 0 or drained_energy < 0:
        raise ValueError('Floor-water energy is outside the finite sensible-storage domain')
    return {'mass_kg': after_mass, 'energy_J': after_energy,
            'temperature_K': after_energy / (after_mass * cp) if after_mass else None,
            'drained_mass_kg': drain * dt, 'drained_energy_J': drained_energy,
            'inlet_energy_J': incoming_energy}
