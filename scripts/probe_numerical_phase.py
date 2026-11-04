"""Finite frozen-input representation/domain and same-EOS reference checks."""
from copy import deepcopy
import json
import math
from pathlib import Path

from aegis_dc.thermodynamics import SaturationTable

TABLE = 'configs/materials/reference-r134a-saturation.json'
PRIOR = 'evidence/mainline/engineering/04-06-root-acceptance/endpoint-representation/probe-result-01.json'
EOS = 'evidence/mainline/engineering/06-phase/eos-reference-01/direct-eos-reference.json'


def shifted(value, count):
    for _ in range(abs(count)):
        value = math.nextafter(value, math.inf if count > 0 else -math.inf)
    return value


def probe(root):
    table = SaturationTable.from_file(root / TABLE)
    prior = json.loads((root / PRIOR).read_text(encoding='utf-8'))
    cases, changed, neighborhoods = [], [], []

    def outcome(inventory):
        try:
            state = table.flash(**inventory)
            return dict(status='RETURNED', pressure_Pa=state['pressure_Pa'], quality=state['quality'],
                        specific_energy_residual_J_kg=state['specific_energy_residual_J_kg'])
        except ValueError as error:
            return dict(status='REFUSED', error=str(error))

    for index, item in enumerate(prior['all_outcomes']):
        actual = outcome(item['inputs'])
        if actual['status'] != item['outcome']['status']:
            changed.append(index)
        cases.append(dict(index=index, inputs=item['inputs'], inputs_float_hex=item['inputs_float_hex'],
                          nominal_pressure_Pa=item['nominal_pressure_Pa'], nominal_quality=item['nominal_quality'],
                          encoded_quality_at_nominal_pressure=item['representation_observation']['reconstructed_quality'], outcome=actual))
        if item['outcome']['status'] == 'REFUSED':
            row = item['frozen_row_primitives']
            for delta_v in range(-8, 9):
                for delta_u in (-1, 0, 1):
                    inventory = dict(item['inputs'], volume_m3=shifted(item['inputs']['volume_m3'], delta_v),
                                     internal_energy_J=shifted(item['inputs']['internal_energy_J'], delta_u))
                    quality = ((inventory['volume_m3'] / inventory['mass_kg'] - row['v_l_m3_kg'])
                               / (row['v_v_m3_kg'] - row['v_l_m3_kg']))
                    neighborhoods.append(dict(prior_index=index, volume_ulp_offset=delta_v, energy_ulp_offset=delta_u,
                        inputs=inventory, inputs_float_hex={key: float(value).hex() for key, value in inventory.items()},
                        encoded_quality_at_nominal_pressure=quality, outcome=outcome(inventory)))
    if changed:
        raise ValueError('Frozen 432-case representation outcomes changed: ' + str(changed))
    frozen = json.loads((root / EOS).read_text(encoding='utf-8'))
    eos_checks = []
    for history in frozen['fixed_volume_histories']:
        for item in history['states']:
            inventory = dict(history['initial_MUV'], internal_energy_J=item['internal_energy_J'])
            actual, expected = table.flash(**inventory), item['expected_EOS']
            errors = dict(pressure_relative=abs(actual['pressure_Pa'] / expected['pressure_Pa'] - 1),
                temperature_abs_K=abs(actual['temperature_K'] - expected['temperature_K']),
                quality_abs=abs(actual['quality'] - expected['quality']))
            if any(value > frozen['predeclared_limits'][key] for key, value in errors.items()):
                raise ValueError('Frozen same-EOS comparison failed')
            eos_checks.append(dict(history=history['id'], net_heat_J=item['net_heat_J'], errors=errors))
    # Domain-envelope samples follow fixed V/M and frozen rows directly. These
    # are thermodynamic mixture bounds, not a second flash implementation.
    profile = json.loads((root / 'configs/full-facility-mainline-reserve-v6.json').read_text(encoding='utf-8'))
    p = {row['id']: row['value'] for row in profile['parameters']}
    envelope = []
    for row in table.rows:
        quality = (p['coolant_control_volume'] / p['coolant_inventory'] - row['v_l_m3_kg']) / (row['v_v_m3_kg'] - row['v_l_m3_kg'])
        if 0 <= quality <= 1:
            energy = p['coolant_inventory'] * ((1 - quality) * row['u_l_J_kg'] + quality * row['u_v_J_kg'])
            envelope.append(dict(pressure_Pa=row['p_Pa'], quality=quality, internal_energy_J=energy))
    return dict(schema='aegisdc-numerical-phase-domain-v1', classification='FINITE_NUMERICAL_NOT_EMPIRICAL',
        unchanged_frozen_cases=len(cases), frozen_refusals=sum(row['outcome']['status'] == 'REFUSED' for row in cases),
        frozen_outcomes=cases, neighborhoods=neighborhoods, same_EOS_checks=eos_checks,
        same_EOS_maximum_errors={key: max(row['errors'][key] for row in eos_checks) for key in eos_checks[0]['errors']},
        nominal_V6_fixed_volume_frozen_row_envelope=envelope,
        interpretation='Nominal construction is not encoded admissibility. Neighbors are diagnostics, not clipping rules or proof for all masses/pressures. Strict five original refusals retained. Fixed-volume mixture envelope is sampled at frozen rows; no single-phase extension. Same-EOS comparisons are numerical consistency, never empirical validation.',
        research_trials=0, model_calls=0, training_calls=0)
