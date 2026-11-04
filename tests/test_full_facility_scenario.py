"""Scenario loading is a public contract, not a physical simulation test."""
import json
import os
from copy import deepcopy
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

from aegis_dc.scenario import describe_scenario, load_scenario

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / 'configs/full-facility-mainline-v1.json'


class FullFacilityScenarioTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads(SCENARIO.read_text(encoding='utf-8'))

    def load_changed(self, changed):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'scenario.json'
            file.write_text(json.dumps(changed, allow_nan=True), encoding='utf-8')
            return load_scenario(file)

    def test_research_scenario_declares_all_domains_and_relation_views(self):
        scenario = load_scenario(SCENARIO)
        self.assertEqual({domain['id'] for domain in scenario['domains']}, {
            'power', 'backup', 'facility_cooling', 'equipment_environment',
            'it_service', 'control_monitoring', 'space_access', 'people_tools_work',
        })
        self.assertEqual(set(scenario['graphs']), {
            'physical', 'functional', 'control_information', 'access',
        })
        summary = describe_scenario(scenario)
        self.assertEqual(summary['status'], 'STRUCTURE_DEFINED_NOT_SIMULATED')
        self.assertEqual(summary['basis'], 'zhengzhou_inspired_synthetic')
        self.assertFalse(summary['dynamic_model_executed'])
        self.assertEqual(summary['field_calibration'], 'PENDING')

    def test_each_operational_domain_requires_a_behavior_and_work_contract(self):
        missing = deepcopy(self.raw)
        missing['domains'].pop()
        with self.assertRaisesRegex(ValueError, 'eight operational domains'):
            self.load_changed(missing)
        for field in ['states', 'inputs', 'outputs', 'behaviors', 'work_interfaces']:
            changed = deepcopy(self.raw)
            changed['domains'][0][field] = []
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, field):
                self.load_changed(changed)

    def test_active_parameters_require_finite_SI_values_ranges_and_provenance(self):
        cases = [
            ('value', None), ('value', True), ('value', float('inf')),
            ('value', float('nan')), ('value', 10**400), ('value', -1), ('value', 30000),
            ('unit', 'kV'), ('quantity', 'unknown_quantity'),
            ('valid_range', [20000, 1000]), ('valid_range', [True, 20000]),
            ('source_note', ''), ('source_refs', ['not_a_source']),
            ('basis', 'assumed_site_measurement'),
        ]
        for field, value in cases:
            changed = deepcopy(self.raw)
            changed['parameters'][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.load_changed(changed)

    def test_shared_identities_and_relationship_roles_are_checked(self):
        for collection in ['entities', 'parameters']:
            changed = deepcopy(self.raw)
            changed[collection].append(deepcopy(changed[collection][0]))
            with self.subTest(duplicate=collection), self.assertRaisesRegex(ValueError, 'Duplicate'):
                self.load_changed(changed)
        mutations = [
            ('physical', 'to', 'unlisted_asset'),
            ('functional', 'kind', 'electric'),
            ('control_information', 'kind', 'fluid'),
            ('access', 'to', 'compute'),
        ]
        for graph, field, value in mutations:
            changed = deepcopy(self.raw)
            changed['graphs'][graph][0][field] = value
            with self.subTest(graph=graph, field=field), self.assertRaises(ValueError):
                self.load_changed(changed)
        changed = deepcopy(self.raw)
        changed['entities'][0]['location_id'] = 'compute'
        with self.assertRaisesRegex(ValueError, 'location'):
            self.load_changed(changed)

    def test_physical_ports_separate_carriers_media_and_voltage_levels(self):
        cases = [
            ('w_hx', {'to_port': 'internal_in'}),
            ('w_hx', {'from_port': 'in'}),
            ('w_hx', {'to_port': 'not_a_port'}),
            ('p_compute', {'kind': 'heat'}),
            ('p_compute', {'to': 'network'}),
        ]
        for identifier, updates in cases:
            changed = deepcopy(self.raw)
            edge = next(e for e in changed['graphs']['physical'] if e['id'] == identifier)
            edge.update(updates)
            with self.subTest(edge=identifier, updates=updates), self.assertRaisesRegex(ValueError, 'port|carrier|medium'):
                self.load_changed(changed)

    def test_workers_tools_and_work_entries_have_compatible_qualified_references(self):
        cases = [
            ('worker_electrical', 'qualification_ids', ['unlisted_qualification']),
            ('worker_electrical', 'qualification_ids', ['qualified_it_inspection']),
            ('worker_electrical', 'tool_ids', ['compute']),
            ('worker_electrical', 'tool_ids', ['tool_it_diagnostic']),
            ('point_flow', 'target_id', 'worker_it'),
        ]
        for identifier, field, value in cases:
            changed = deepcopy(self.raw)
            next(e for e in changed['entities'] if e['id'] == identifier)[field] = value
            with self.subTest(entity=identifier, field=field), self.assertRaises(ValueError):
                self.load_changed(changed)
        for field, value in [('target_ids', ['unlisted_asset']),
                             ('qualification_id', 'qualified_it_inspection'),
                             ('duration_parameter', 'grid_capacity')]:
            changed = deepcopy(self.raw)
            changed['domains'][0]['work_interfaces'][0][field] = value
            with self.subTest(work_field=field), self.assertRaises(ValueError):
                self.load_changed(changed)

    def test_electrical_ports_require_compatible_nominal_voltage_parameters(self):
        for reference in ['grid_capacity', 'mv_voltage']:
            changed = deepcopy(self.raw)
            compute = next(e for e in changed['entities'] if e['id'] == 'compute')
            compute['ports']['power']['parameter_ref'] = reference
            with self.subTest(reference=reference), self.assertRaisesRegex(ValueError, 'voltage'):
                self.load_changed(changed)

    def test_site_gaps_and_source_identity_cannot_be_promoted_to_active_facts(self):
        for field, value in [('schema', 'unknown_schema'), ('basis', 'as_built_zhengzhou'),
                             ('hidden_simulator_state', {'fault': True})]:
            changed = deepcopy(self.raw)
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.load_changed(changed)
        changed = deepcopy(self.raw)
        changed['site_gaps'][0]['value'] = 0
        with self.assertRaisesRegex(ValueError, 'gap'):
            self.load_changed(changed)
        changed = deepcopy(self.raw)
        changed['sources']['Z1']['uri'] = ''
        with self.assertRaisesRegex(ValueError, 'source'):
            self.load_changed(changed)

    def test_duplicate_json_fields_are_rejected_before_interpreting_the_scenario(self):
        text = json.dumps(self.raw).replace('"mv_voltage",', '"mv_voltage", "id": "overwritten",', 1)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'duplicate.json'
            path.write_text(text, encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Duplicate JSON object key'):
                load_scenario(path)

    def test_cli_inspects_the_structural_contract_without_claiming_a_run(self):
        process = subprocess.run([sys.executable, '-m', 'aegis_dc', 'scenario'], cwd=ROOT,
                                 env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')),
                                 capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        summary = json.loads(process.stdout)
        self.assertEqual(summary['scenario_id'], 'zz-inspired-research-v1')
        self.assertEqual(summary['domain_count'], 8)
        self.assertEqual(summary['entity_count'], 38)
        self.assertEqual(summary['behavior_status'], 'DECLARED_NOT_EXECUTED')
        self.assertEqual(summary['research_gain_claim'], 'NOT_ESTABLISHED')
        self.assertFalse(summary['dynamic_model_executed'])
        self.assertEqual(summary['site_gaps'][0]['value'], None)

    def test_cli_rejects_an_invalid_scenario_before_outputting_a_valid_summary(self):
        changed = deepcopy(self.raw)
        changed['parameters'][0]['value'] = None
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'invalid.json'
            path.write_text(json.dumps(changed), encoding='utf-8')
            process = subprocess.run([sys.executable, '-m', 'aegis_dc', 'scenario', '--model', str(path)],
                                     cwd=ROOT, env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')),
                                     capture_output=True, text=True)
        self.assertNotEqual(process.returncode, 0)
        self.assertIn('missing is not zero', process.stderr)
        self.assertEqual(process.stdout, '')

    def test_malformed_symbolic_fields_fail_as_contract_errors(self):
        paths = [
            ('sources', 'R0', 'classification'),
            ('parameters', 0, 'quantity'),
            ('entities', 0, 'kind'),
            ('graphs', 'physical', 0, 'from_port'),
            ('graphs', 'access', 0, 'duration_parameter'),
        ]
        for keys in paths:
            changed = deepcopy(self.raw)
            row = changed
            for key in keys[:-1]:
                row = row[key]
            row[keys[-1]] = []
            with self.subTest(path=keys), self.assertRaises(ValueError):
                self.load_changed(changed)

    def test_undeclared_numeric_shortcuts_cannot_bypass_parameter_metadata(self):
        for keys in [('entities', 0), ('domains', 0), ('graphs', 'access', 0), ('parameters', 0)]:
            changed = deepcopy(self.raw)
            row = changed
            for key in keys:
                row = row[key]
            row['untyped_capacity'] = 1000
            with self.subTest(path=keys), self.assertRaisesRegex(ValueError, 'fields'):
                self.load_changed(changed)


if __name__ == '__main__':
    unittest.main()
