"""Frozen temporal boundary cases at the complete-facility run seam."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from patrol_rsi.contracts import digest
from aegis_dc.plant import save_run, simulate_scenario

ROOT = Path(__file__).resolve().parents[1]


class TemporalEndpointQualificationTests(unittest.TestCase):
    def test_left_right_censor_missing_confirmation_and_unknown_references(self):
        descriptor = json.loads((ROOT/'tests/fixtures/39c-temporal-qualification-39.json').read_bytes())
        base = json.loads((ROOT/descriptor['base_input']).read_bytes())
        output = Path(os.environ['AEGIS_ENGINEERING_RESULT_DIR']) if os.environ.get('AEGIS_ENGINEERING_RESULT_DIR') else None
        self.facility_calls = self.completed_native_horizons = self.returned_decisions = 0
        self.completed_native_duration_s = 0
        rows = []
        identity = None

        def save(directory, name, value):
            if directory is not None:
                with (directory/name).open('x', encoding='utf-8', newline='\n') as stream:
                    json.dump(value, stream, indent=2, allow_nan=False)
                    stream.write('\n')

        for case in descriptor['cases']:
            row = dict(case=case['id'], passed=False)
            rows.append(row)
            with self.subTest(case=case['id']):
                data = deepcopy(base)
                data['duration_s'] = case['duration_s']
                data['dispatch_program']['decision_times_s'] = case['decision_times_s']
                data['dispatch_program']['policy_program']['policy'] = case['policy']
                data['boundary_events'] = [event for event in data['boundary_events'] if event['time_s'] <= data['duration_s']]
                if case['initial_fault']:
                    next(item for item in data['scenario']['parameters'] if item['id'] == 'network_service_capacity')['value'] = .25
                    data['boundary_events'] = []
                program = data['business_program']
                program['id'] += '-' + case['id']
                event = program['events'][0]
                event['timing']['sample_times_s'] = case['sample_times_s']
                if not case['truth_modeled']:
                    event['truth'] = dict(kind='UNMODELED', source_note='Private truth intentionally undeclared in this qualification; public capacity evidence alone does not fill this label.')
                if not case['deadline_modeled']:
                    event['timing']['intervention_deadline'] = dict(status='UNMODELED', at_s=None,
                        source_note='No prospective intervention cutoff declared; keep unknown instead of substituting confirmation cutoff.')
                program['reference']['scenario_sha256'] = digest(data['scenario'])
                program['reference']['boundary_events_sha256'] = digest(data['boundary_events'])
                directory = output/case['id'] if output is not None else None
                if directory is not None:
                    directory.mkdir()
                save(directory, 'frozen-call-input.json', data)
                self.facility_calls += 1
                result = simulate_scenario(**data)
                self.completed_native_horizons += 1
                self.completed_native_duration_s += result['summary']['duration_s']
                self.returned_decisions += len(result['policy_public_decisions'])
                if directory is not None:
                    save_run(result, directory/'actual-run')
                save(directory, 'business-result.json', result['business_evaluation'])
                if identity is None:
                    identity = result['code_identity']
                self.assertEqual(result['code_identity'], identity)
                temporal = result['business_evaluation']['events'][0]['temporal_endpoints']
                row.update(actual=temporal, duration_s=result['summary']['duration_s'],
                           returned_decisions=len(result['policy_public_decisions']),
                           public_conditions=[decision['condition_assessment']['conditions'][0]['status']
                                              for decision in result['policy_public_decisions']])
                for path, expected in case['expected'].items():
                    actual = temporal
                    for key in path.split('.'):
                        actual = actual[key]
                    self.assertEqual(actual, expected, path)
                self.assertEqual(result['business_evaluation']['prevention_effect']['status'],
                                 'NOT_IDENTIFIED_NO_PAIRED_COUNTERFACTUAL')
                self.assertFalse(any('temporal_endpoints' in d['frame'] or 'timing' in d['frame']
                                     for d in result['policy_public_decisions']))
                row['passed'] = True
        save(output, 'qualification.json', rows)
        save(output, 'actual-execution-summary.json', dict(code_identity=identity,
            cases=rows, facility_calls=self.facility_calls, completed_horizons=self.completed_native_horizons,
            completed_duration_s=self.completed_native_duration_s, returned_decisions=self.returned_decisions))
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row['passed'] for row in rows))


if __name__ == '__main__':
    unittest.main()
