"""Prepare or check the pure-fluid initial inventory at the fixed V6 geometry."""
from copy import deepcopy
from hashlib import sha256
import math
from pathlib import Path

from patrol_rsi.contracts import strict_json

from .scenario import validate_scenario
from .thermodynamics import SaturationTable, finite_number

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / 'configs/full-facility-mainline-reserve-v6.json'
BASELINE_SHA256 = '08a591d305412702906e360983342d383c5022e33a96771e78322c0a9fe89085'
MASS = 'coolant_inventory'
VOLUME = 'coolant_control_volume'
ENERGY = 'coolant_initial_energy'


def _parameters(scenario):
    return {row['id']: row for row in scenario['parameters']}


def _reference(scenario):
    validate_scenario(scenario)
    raw = BASELINE.read_bytes()
    if sha256(raw).hexdigest() != BASELINE_SHA256:
        raise ValueError('Fixed V6 reference source differs')
    baseline = strict_json(raw.decode('utf-8'))
    if scenario['id'] != baseline['id'] or any(
        scenario['runtime'].get(name) != baseline['runtime'][name]
        for name in ('model', 'topology_sha256', 'property_table', 'property_sha256')
    ):
        raise ValueError('Refrigerant initialization requires the fixed V6 property and topology reference')
    rows, nominal = _parameters(scenario), _parameters(baseline)
    if rows[VOLUME]['value'] != nominal[VOLUME]['value']:
        raise ValueError('Refrigerant initialization must keep the fixed V6 control volume')
    table = SaturationTable.from_file(ROOT / baseline['runtime']['property_table'],
                                     expected_sha256=baseline['runtime']['property_sha256'])
    return rows, nominal, table


def _in_range(value, parameter):
    lower, upper = parameter['valid_range']
    if not lower <= value <= upper:
        raise ValueError(parameter['id'] + ' is outside the frozen V6 scalar range')


def _recover(table, rows):
    phase = table.flash(rows[MASS]['value'], rows[ENERGY]['value'], rows[VOLUME]['value'])
    return {
        name: phase[name] for name in (
            'pressure_Pa', 'temperature_K', 'quality', 'mass_kg', 'volume_m3',
            'internal_energy_J', 'liquid_mass_kg', 'vapor_mass_kg', 'specific_energy_residual_J_kg',
        )
    }


def assess_refrigerant_initialization(scenario):
    """Validate a supplied fixed-geometry inventory, without advancing the plant."""
    rows, nominal, table = _reference(scenario)
    for key in (MASS, ENERGY):
        _in_range(rows[key]['value'], nominal[key])
    return _recover(table, rows)


def prepare_refrigerant_initialization(scenario, *, mass_kg, pressure_Pa):
    """Use one pressure and mass to derive a consistent interior two-phase inventory."""
    rows, nominal, table = _reference(scenario)
    mass = finite_number(mass_kg, 'Requested refrigerant mass', positive=True)
    _in_range(mass, nominal[MASS])
    props = table.at_pressure(pressure_Pa)
    liquid_volume, vapor_volume = props['v_l_m3_kg'], props['v_v_m3_kg']
    specific_volume = rows[VOLUME]['value'] / mass
    quality = (specific_volume - liquid_volume) / (vapor_volume - liquid_volume)
    if not 0 < quality < 1:
        raise ValueError('Requested pressure and mass do not form an interior two-phase state at the fixed volume')
    liquid_energy, vapor_energy = props['u_l_J_kg'], props['u_v_J_kg']
    energy = mass * (liquid_energy + quality * (vapor_energy - liquid_energy))
    _in_range(energy, nominal[ENERGY])
    candidate = deepcopy(scenario)
    prepared = _parameters(candidate)
    prepared[MASS].update(value=mass, basis='synthetic_assumption', source_refs=['R0'],
                          source_note='Declared synthetic fill charge at the fixed V6 geometry.')
    prepared[ENERGY].update(value=energy, basis='derived_reference', source_refs=['Rrun','Rprop'],
                            source_note='Derived from the frozen saturation table and the same fixed-volume two-phase mixture.')
    validate_scenario(candidate)
    state = _recover(table, prepared)
    if not math.isclose(state['pressure_Pa'], props['pressure_Pa'], rel_tol=1e-10) or not math.isclose(
        state['quality'], quality, rel_tol=0, abs_tol=1e-12
    ):
        raise ValueError('Recovered initial phase does not match the declared pressure and mixture')
    return dict(status='INITIALIZATION_ONLY', scenario=candidate, initialization=state, property_sha256=table.sha256,
                visibility='FACILITY_INITIALIZATION_NOT_A_DISPATCH_INPUT', field_calibration='PENDING')
