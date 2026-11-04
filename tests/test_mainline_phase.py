"""Phase engineering behavior at the public property and facility-run seams."""
import json
from pathlib import Path
import unittest

from aegis_dc.plant import simulate_scenario
from aegis_dc.scenario import load_scenario
from aegis_dc.thermodynamics import SaturationTable

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / 'configs/materials/reference-r134a-saturation.json'
REFERENCE = ROOT / 'evidence/mainline/engineering/06-phase/eos-reference-01/direct-eos-reference.json'


def scenario_with(**values):
    scenario = load_scenario(ROOT / 'configs/full-facility-mainline-v2.json')
    for parameter in scenario['parameters']:
        if parameter['id'] in values:
            parameter.update(value=values[parameter['id']], basis='synthetic_assumption',
                             source_note='Controlled ticket 06 engineering input; not field data.')
    return scenario


class PhaseDomainTests(unittest.TestCase):
    def test_frozen_EOS_saturation_endpoints_are_usable_without_quality_clipping(self):
        reference = json.loads(REFERENCE.read_text(encoding='utf-8'))
        table = SaturationTable.from_file(TABLE, expected_sha256=reference['property_table_sha256'])
        for record in reference['saturation_endpoint_cases']:
            with self.subTest(pressure=record['given_pressure_Pa'], quality=record['given_quality']):
                state = table.flash(**record['MUV'])
                self.assertAlmostEqual(state['pressure_Pa'], record['given_pressure_Pa'], delta=1e-6)
                self.assertAlmostEqual(state['quality'], record['given_quality'], delta=1e-12)
                self.assertGreaterEqual(state['quality'], 0.0)
                self.assertLessEqual(state['quality'], 1.0)

    def test_signed_heat_and_extreme_fill_match_frozen_direct_EOS_inputs(self):
        reference = json.loads(REFERENCE.read_text(encoding='utf-8'))
        table = SaturationTable.from_file(TABLE)
        limits = reference['predeclared_limits']
        for history in reference['fixed_volume_histories']:
            initial = history['initial_MUV']
            for record in history['states']:
                with self.subTest(filling=history['id'], net_heat_J=record['net_heat_J']):
                    state = table.flash(initial['mass_kg'], record['internal_energy_J'], initial['volume_m3'])
                    expected = record['expected_EOS']
                    self.assertAlmostEqual(state['pressure_Pa'] / expected['pressure_Pa'], 1.0,
                                           delta=limits['pressure_relative'])
                    self.assertAlmostEqual(state['temperature_K'], expected['temperature_K'],
                                           delta=limits['temperature_abs_K'])
                    self.assertAlmostEqual(state['quality'], expected['quality'], delta=limits['quality_abs'])
                    self.assertAlmostEqual(state['liquid_mass_kg'] + state['vapor_mass_kg'],
                                           initial['mass_kg'], delta=1e-9)

    def test_single_phase_and_outside_pressure_inputs_are_refused_without_endpoint_clipping(self):
        reference = json.loads(REFERENCE.read_text(encoding='utf-8'))
        table = SaturationTable.from_file(TABLE)
        for record in reference['refused_cases']:
            with self.subTest(case=record['id']), self.assertRaisesRegex(ValueError, 'exactly one domain-valid root'):
                table.flash(**record['MUV'])
        # A finite 0.1 J/kg excursion exceeds floating-point endpoint tolerance.
        # The domain cannot be extended by holding pressure at its endpoint.
        for record, heat in ((reference['saturation_endpoint_cases'][3], -0.1),
                             (reference['saturation_endpoint_cases'][-1], 0.1)):
            inventory = dict(record['MUV'])
            inventory['internal_energy_J'] += heat
            with self.subTest(pressure=record['given_pressure_Pa'], heat_J=heat), \
                    self.assertRaisesRegex(ValueError, 'exactly one domain-valid root'):
                table.flash(**inventory)

    def test_zero_nonfinite_and_boolean_inventory_are_refused(self):
        table = SaturationTable.from_file(TABLE)
        for mass, energy, volume in ((0, 1e6, 1), (-1, 1e6, 1), (1, 1e6, 0),
                                     (True, 1e6, 1), (1, False, 1), (1, 1e6, True),
                                     (float('inf'), 1e6, 1), (1, float('nan'), 1),
                                     (1, 1e6, float('inf')), (10**1000, 1e6, 1)):
            with self.subTest(mass=mass, energy=energy, volume=volume), self.assertRaisesRegex(ValueError, 'finite'):
                table.flash(mass, energy, volume)
        with self.assertRaisesRegex(ValueError, 'exactly one domain-valid root'):
            table.flash(1, 0, 1)

    def test_nonunique_equilibrium_is_refused_instead_of_selecting_a_pressure(self):
        # Algebraic rejection fixture only, not a material table: every pressure
        # has x=1/2, u=200 J/kg at v=2 m3/kg, so no unique state can be returned.
        table = SaturationTable({'schema': 'aegisdc-reference-saturation-v1',
                                 'source': {'kind': 'algebraic-engineering-fixture'},
                                 'validity': {'material_model': False},
                                 'rows': [{'p_Pa': pressure, 'T_sat_K': temperature,
                                           'v_l_m3_kg': 1, 'v_v_m3_kg': 3,
                                           'u_l_J_kg': 100, 'u_v_J_kg': 300}
                                          for pressure, temperature in ((100000, 300), (200000, 310))]},
                                'algebraic-fixture-only')
        with self.assertRaisesRegex(ValueError, 'Nonunique two-phase flash'):
            table.flash(1, 200, 2)


class PhaseRunTests(unittest.TestCase):
    def test_two_MJ_heat_changes_pressure_and_phase_inventory_once(self):
        # Independent hand case: the declared initial 4 K solid/refrigerant
        # difference and 0.5 MW/K interface deliver 2 MJ over the first second.
        # Closing the condenser removes its transfer, with no latent-heat term.
        result = simulate_scenario(scenario_with(condenser_conductance=0), duration_s=1)
        before = result['trace'][0]['domains']['equipment_environment']['refrigerant']
        after = result['trace'][-1]['domains']['equipment_environment']['refrigerant']
        self.assertEqual(len(result['trace'][-1]['domains']), 8)
        self.assertAlmostEqual(after['internal_energy_J'], 518335850.31469756, delta=1e-6)
        self.assertAlmostEqual(after['internal_energy_J'] - before['internal_energy_J'], 2000000, delta=1e-6)
        self.assertEqual(after['mass_kg'], 2000)
        self.assertEqual(after['volume_m3'], before['volume_m3'])
        self.assertGreater(after['pressure_Pa'], before['pressure_Pa'])
        self.assertGreater(after['vapor_mass_kg'], before['vapor_mass_kg'])
        self.assertLess(after['liquid_mass_kg'], before['liquid_mass_kg'])
        reference = json.loads(REFERENCE.read_text(encoding='utf-8'))
        expected = reference['fixed_volume_histories'][0]['states'][2]['expected_EOS']
        self.assertAlmostEqual(after['pressure_Pa'] / expected['pressure_Pa'], 1.0, delta=1e-5)
        self.assertAlmostEqual(after['quality'], expected['quality'], delta=5e-6)

    def test_warm_water_returns_heat_through_the_signed_condenser_interface(self):
        parameters = {'solid_coolant_conductance': 0,
                      'initial_cold_temperature': 310, 'initial_hot_temperature': 310}
        coupled = simulate_scenario(scenario_with(**parameters), duration_s=1)
        closed = simulate_scenario(scenario_with(**parameters, condenser_conductance=0), duration_s=1)
        before = coupled['balances'][0]['storage_before_J']
        after = coupled['balances'][0]['storage_after_J']
        closed_after = closed['balances'][0]['storage_after_J']
        refrigerant_gain = after['coolant'] - before['coolant']
        water_difference = after['hot'] + after['cold'] - closed_after['hot'] - closed_after['cold']
        self.assertGreater(refrigerant_gain, 0)
        self.assertLess(coupled['trace'][0]['domains']['facility_cooling']['condenser_heat_W'], 0)
        self.assertAlmostEqual(water_difference, -refrigerant_gain, delta=1e-5)

    def test_stopped_water_flow_removes_condenser_transfer_but_retains_stored_solid_heat(self):
        result = simulate_scenario(scenario_with(internal_pump_pressure_rise=0), duration_s=1)
        before = result['trace'][0]['domains']
        after = result['trace'][-1]['domains']
        self.assertEqual(before['facility_cooling']['internal_mass_flow_kg_s'], 0)
        self.assertEqual(before['facility_cooling']['condenser_heat_W'], 0)
        self.assertEqual(before['it_service']['delivered'], 0)
        self.assertAlmostEqual(after['equipment_environment']['refrigerant']['internal_energy_J'],
                               518335850.31469756, delta=1e-6)

    def test_run_stops_when_heat_leaves_the_frozen_pressure_domain(self):
        reference = json.loads(REFERENCE.read_text(encoding='utf-8'))
        endpoint = reference['saturation_endpoint_cases'][10]['MUV']  # 3 MPa, x=1/2, M=1 kg.
        scenario = scenario_with(coolant_inventory=2000,
                                 coolant_initial_energy=2000 * endpoint['internal_energy_J'],
                                 coolant_control_volume=2000 * endpoint['volume_m3'],
                                 initial_solid_temperature=370,
                                 condenser_conductance=0)
        # The initial state is a legal table endpoint. Stored solid heat moves
        # it beyond the domain during the first 0.01 s; no successful clipped
        # trajectory may be returned.
        with self.assertRaisesRegex(ValueError, 'exactly one domain-valid root'):
            simulate_scenario(scenario, duration_s=0.01, step_s=0.01)

    def test_closed_liquid_and_vapor_rich_runs_preserve_phase_and_total_inventory(self):
        reference = json.loads(REFERENCE.read_text(encoding='utf-8'))
        for history in reference['fixed_volume_histories'][1:]:
            initial = history['initial_MUV']
            with self.subTest(filling=history['id']):
                result = simulate_scenario(scenario_with(coolant_inventory=initial['mass_kg'],
                                            coolant_initial_energy=initial['internal_energy_J'],
                                            coolant_control_volume=initial['volume_m3'],
                                            solid_coolant_conductance=0, condenser_conductance=0),
                                           duration_s=1)
                before = result['trace'][0]['domains']['equipment_environment']['refrigerant']
                after = result['trace'][-1]['domains']['equipment_environment']['refrigerant']
                self.assertEqual(after, before)
                self.assertAlmostEqual(after['liquid_mass_kg'] + after['vapor_mass_kg'], 2000, delta=1e-9)
                account = result['balances'][0]['mass_accounts_kg']['refrigerant']
                self.assertEqual(account['in_kg'], 0)
                self.assertEqual(account['out_kg'], 0)
                expected = history['states'][1]['expected_EOS']
                self.assertAlmostEqual(after['pressure_Pa'] / expected['pressure_Pa'], 1.0, delta=1e-5)
                self.assertAlmostEqual(after['quality'], expected['quality'], delta=5e-6)

    def test_two_MJ_condensation_enters_the_same_water_interface_once(self):
        # A companion run differs only by the condenser interface. At the
        # declared initial working point that interface transfers exactly 2 MJ.
        coupled = simulate_scenario(scenario_with(solid_coolant_conductance=0), duration_s=1)
        closed = simulate_scenario(scenario_with(solid_coolant_conductance=0,
                                                 condenser_conductance=0), duration_s=1)
        before = coupled['trace'][0]['domains']['equipment_environment']['refrigerant']
        after = coupled['trace'][-1]['domains']['equipment_environment']['refrigerant']
        self.assertAlmostEqual(after['internal_energy_J'], 514335850.31469756, delta=1e-6)
        self.assertAlmostEqual(before['internal_energy_J'] - after['internal_energy_J'], 2000000, delta=1e-6)
        water_coupled = coupled['balances'][0]['storage_after_J']
        water_closed = closed['balances'][0]['storage_after_J']
        self.assertAlmostEqual((water_coupled['hot'] + water_coupled['cold'])
                               - (water_closed['hot'] + water_closed['cold']), 2000000, delta=1e-6)
        self.assertAlmostEqual(coupled['balances'][0]['heat_transfers_W']['coolant_to_internal_water'],
                               2000000, delta=1e-6)
        self.assertLess(after['pressure_Pa'], before['pressure_Pa'])
        self.assertLess(after['vapor_mass_kg'], before['vapor_mass_kg'])
        self.assertGreater(after['liquid_mass_kg'], before['liquid_mass_kg'])
        self.assertAlmostEqual(after['liquid_mass_kg'] + after['vapor_mass_kg'], 2000, delta=1e-9)
        reference = json.loads(REFERENCE.read_text(encoding='utf-8'))
        expected = reference['fixed_volume_histories'][0]['states'][0]['expected_EOS']
        self.assertAlmostEqual(after['pressure_Pa'] / expected['pressure_Pa'], 1.0, delta=1e-5)
        self.assertAlmostEqual(after['quality'], expected['quality'], delta=5e-6)


if __name__ == '__main__':
    unittest.main()
