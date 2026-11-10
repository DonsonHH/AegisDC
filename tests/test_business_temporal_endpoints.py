"""Three temporal references through the agreed complete-facility run interface."""
import json
import os
from pathlib import Path
import unittest

from aegis_dc.plant import save_run, simulate_scenario

ROOT = Path(__file__).resolve().parents[1]


class BusinessTemporalEndpointTests(unittest.TestCase):
    def test_three_references_report_post_fault_delay_and_separate_plan_deadline(self):
        data = json.loads((ROOT/'tests/fixtures/39c-temporal-lead-38.json').read_bytes())
        output = Path(os.environ['AEGIS_ENGINEERING_RESULT_DIR']) if os.environ.get('AEGIS_ENGINEERING_RESULT_DIR') else None

        def save(name, value):
            if output is not None:
                with (output/name).open('x', encoding='utf-8', newline='\n') as stream:
                    json.dump(value, stream, indent=2, allow_nan=False)
                    stream.write('\n')

        save('frozen-call-input.json', data)
        self.facility_calls = 1
        result = simulate_scenario(**data)
        self.returned_decisions = len(result['policy_public_decisions'])
        self.completed_native_horizons = 1
        self.completed_native_duration_s = result['summary']['duration_s']
        if output is not None:
            save_run(result, output/'actual-run')
        evaluation = result['business_evaluation']
        save('business-result.json', evaluation)
        save('actual-execution-summary.json', dict(code_identity=result['code_identity'], summary=result['summary'],
            work_records=result['work_records'], interventions=result['intervention_public_feedback'],
            public_choices=[dict(at_s=row['frame']['as_of_s'], choice=row['choice']['chosen_candidate_id'],
                condition_assessment=row['condition_assessment']) for row in result['policy_public_decisions']]))

        self.assertEqual(evaluation['schema'], 'aegisdc-business-diagnostic-result-v3')
        self.assertEqual(evaluation['visibility'], 'PRIVATE_EVALUATOR_ONLY')
        event, = evaluation['events']
        self.assertEqual(event['first_corroborated_fault_report_at_s'], 1.75)
        self.assertEqual(event['reference_opportunity']['deadline_s'], 2)
        temporal = event['temporal_endpoints']
        fault = temporal['fault_reference']
        self.assertEqual(fault['status'], 'FIRST_TRANSITION_SAMPLE')
        self.assertEqual(fault['sample_at_s'], 1)
        self.assertEqual(fault['previous_non_event_sample_at_s'], 0)
        self.assertEqual(fault['lead_s'], -.75)
        self.assertEqual(fault['transition_lead_interval_s'], [-1.75, -.75])
        self.assertTrue(fault['interval_lower_exclusive'])
        service = temporal['service_loss_reference']
        self.assertEqual(service['status'], 'FIRST_TRANSITION_SAMPLE')
        self.assertEqual(service['sample_at_s'], 1)
        self.assertEqual(service['previous_non_event_sample_at_s'], 0)
        self.assertEqual(service['lead_s'], -.75)
        self.assertEqual(service['transition_lead_interval_s'], [-1.75, -.75])
        self.assertEqual(service['attribution'], 'WHOLE_FACILITY_NOT_CAUSE_ATTRIBUTED')
        deadline = temporal['intervention_deadline_reference']
        self.assertEqual(deadline['status'], 'DECLARED_PLANNED_DEADLINE')
        self.assertEqual(deadline['at_s'], 3.5)
        self.assertEqual(deadline['lead_s'], 1.75)
        self.assertEqual(evaluation['prevention_effect']['status'], 'NOT_IDENTIFIED_NO_PAIRED_COUNTERFACTUAL')
        self.assertEqual([row['choice']['chosen_candidate_id'] for row in result['policy_public_decisions']],
                         ['network-case/inspect-0', None, None, None, None, None])
        self.assertEqual(result['intervention_public_feedback'], [])
        self.assertFalse(any('temporal_endpoints' in row['frame'] or 'timing' in row['frame']
                             for row in result['policy_public_decisions']))
        self.assertEqual(self.returned_decisions, 6)


if __name__ == '__main__':
    unittest.main()
