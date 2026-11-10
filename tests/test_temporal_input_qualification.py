"""Temporal input refusals and a conditional censor bound at the run interface."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from patrol_rsi.contracts import digest
from aegis_dc.plant import save_run, simulate_scenario

ROOT = Path(__file__).resolve().parents[1]


class TemporalInputQualificationTests(unittest.TestCase):
    def test_refusals_precede_integration_and_confirmed_censor_bound_is_conditional(self):
        descriptor = json.loads((ROOT/'tests/fixtures/39c-temporal-remaining-41.json').read_bytes())
        output = Path(os.environ['AEGIS_ENGINEERING_RESULT_DIR']) if os.environ.get('AEGIS_ENGINEERING_RESULT_DIR') else None
        self.facility_calls = self.completed_native_horizons = self.returned_decisions = 0
        self.completed_native_duration_s = 0
        rows, identity = [], None

        def save(directory, name, value):
            if directory is not None:
                with (directory/name).open('x', encoding='utf-8', newline='\n') as stream:
                    json.dump(value, stream, indent=2, allow_nan=False)
                    stream.write('\n')

        try:
            for case in descriptor['refusals']:
                row = dict(case=case['id'], passed=False)
                rows.append(row)
                with self.subTest(case=case['id']):
                    data = json.loads((ROOT/descriptor['base_input']).read_bytes())
                    timing = data['business_program']['events'][0]['timing']
                    timing.update(deepcopy(case['timing_patch']))
                    directory = output/case['id'] if output is not None else None
                    if directory is not None:
                        directory.mkdir()
                    save(directory, 'frozen-call-input.json', data)
                    self.facility_calls += 1
                    try:
                        unexpected = simulate_scenario(**data)
                    except ValueError as error:
                        row['actual_error'] = str(error)
                        self.assertEqual(str(error), case['expected_error'])
                        row.update(passed=True, completed_horizons=0, returned_decisions=0)
                    else:
                        self.completed_native_horizons += 1
                        self.completed_native_duration_s += unexpected['summary']['duration_s']
                        self.returned_decisions += len(unexpected['policy_public_decisions'])
                        identity = unexpected['code_identity']
                        if directory is not None:
                            save_run(unexpected, directory/'unexpected-actual-run')
                        self.fail('Invalid temporal input unexpectedly completed a facility run')

            with self.subTest(case='confirmed-service-reference-right-censored'):
                row = dict(case='confirmed-service-reference-right-censored', passed=False)
                rows.append(row)
                data = json.loads((ROOT/descriptor['bound_input']).read_bytes())
                data['duration_s'] = 2
                data['dispatch_program']['decision_times_s'] = [0, 1.75, 2]
                data['boundary_events'] = [e for e in data['boundary_events'] if e['time_s'] <= 2]
                event = data['business_program']['events'][0]
                event['timing']['sample_times_s'] = [0, 1, 1.75, 2]
                event['truth']['source_note'] = descriptor['bound_predicate_note']
                reference = data['business_program']['reference']
                reference['scenario_sha256'] = digest(data['scenario'])
                reference['boundary_events_sha256'] = digest(data['boundary_events'])
                directory = output/'confirmed-bound' if output is not None else None
                if directory is not None:
                    directory.mkdir()
                save(directory, 'frozen-call-input.json', data)
                self.facility_calls += 1
                result = simulate_scenario(**data)
                self.completed_native_horizons += 1
                self.completed_native_duration_s += result['summary']['duration_s']
                self.returned_decisions += len(result['policy_public_decisions'])
                identity = result['code_identity']
                if directory is not None:
                    save_run(result, directory/'actual-run')
                save(directory, 'business-result.json', result['business_evaluation'])
                temporal = result['business_evaluation']['events'][0]['temporal_endpoints']
                row.update(actual=temporal, completed_horizons=1, returned_decisions=3)
                self.assertEqual(temporal['first_public_confirmation_at_s'], 1.75)
                self.assertEqual(temporal['fault_reference']['status'], 'PRESENT_AT_FIRST_SAMPLE')
                service = temporal['service_loss_reference']
                self.assertEqual(service['status'], 'NOT_OBSERVED_BY_LAST_SAMPLE')
                self.assertTrue(service['right_censored'])
                self.assertEqual(service['censor_at_s'], 2)
                self.assertIsNone(service['lead_s'])
                self.assertEqual(service['lead_lower_bound_if_later_event_s'], .25)
                self.assertEqual(temporal['intervention_deadline_reference']['lead_s'], 1.75)
                self.assertEqual(result['summary']['service_deficit_time_s'], 0)
                row['passed'] = True
        finally:
            save(output, 'qualification.json', rows)
            if identity is not None:
                save(output, 'actual-execution-summary.json', dict(code_identity=identity, cases=rows,
                    facility_calls=self.facility_calls, completed_horizons=self.completed_native_horizons,
                    completed_duration_s=self.completed_native_duration_s, returned_decisions=self.returned_decisions))
        self.assertEqual(len(rows), 8)
        self.assertTrue(all(row['passed'] for row in rows))


if __name__ == '__main__':
    unittest.main()
