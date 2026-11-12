"""Full business inputs survive recording, reading and exact recorded replay."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest

from aegis_dc import replay as replay_api
from patrol_rsi.contracts import digest

ROOT = Path(__file__).resolve().parents[1]


class BusinessRecordedReplayTests(unittest.TestCase):
    def test_reverse_order_business_input_is_recorded_read_replayed_and_semantically_equal(self):
        spec = json.loads((ROOT/'tests/fixtures/39c-business-record-replay-57.json').read_bytes())
        call = json.loads((ROOT/spec['base_input']).read_bytes())
        inputs = dict(schema=spec['replay_input_schema'], seed=None,
            exogenous_events=deepcopy(call['boundary_events']), action_commands=[], work_requests=[],
            dispatch_program=deepcopy(call['dispatch_program']), business_program=deepcopy(call['business_program']))
        temporary = None
        if os.environ.get('AEGIS_ENGINEERING_RESULT_DIR'):
            output = Path(os.environ['AEGIS_ENGINEERING_RESULT_DIR'])
        else:
            temporary = tempfile.TemporaryDirectory()
            output = Path(temporary.name)
            self.addCleanup(temporary.cleanup)

        def save(name, value):
            with (output/name).open('x', encoding='utf-8', newline='\n') as stream:
                json.dump(value, stream, indent=2, allow_nan=False)
                stream.write('\n')

        save('frozen-record-call.json', dict(scenario=call['scenario'], inputs=inputs,
            duration_s=call['duration_s'], step_s=call['step_s']))
        original = output/'recorded'
        first = replay_api.run_recorded(call['scenario'], original, inputs=inputs,
            duration_s=call['duration_s'], step_s=call['step_s'])
        save('original-record-result.json', first)
        self.assertEqual(first['status'], 'COMPLETED', first.get('failure'))
        before = replay_api.read_attempt(original)
        self.assertEqual(before['inputs'], inputs)
        self.assertEqual([e['time_s'] for e in before['inputs']['exogenous_events']], [2, 1])
        self.assertEqual([e['time_s'] for e in before['run']['inputs']['boundary_events']], [1, 2])
        self.assertEqual(before['run']['inputs']['business_program'], inputs['business_program'])
        self.assertEqual(before['run']['business_evaluation']['business_program_sha256'], digest(inputs['business_program']))
        replayed = output/'replayed'
        second = replay_api.replay_attempt(original, replayed)
        save('replay-record-result.json', second)
        self.assertEqual(second['status'], 'COMPLETED', second.get('failure'))
        after = replay_api.read_attempt(replayed)
        self.assertEqual(after['inputs'], before['inputs'])
        self.assertEqual(second['replay_of']['attempt_sha256'], before['record_sha256'])
        self.assertEqual(second['replay_source_rule'], 'EXACT_RUNTIME_BYTES_AND_INTERPRETER')
        self.assertEqual(second['replay_revision_relationship'], 'SAME_COMMIT')
        for label, saved in (('original', before), ('replay', after)):
            run = saved['run']
            evaluation = run['business_evaluation']
            save(label+'-business-result.json', evaluation)
            save(label+'-actual-summary.json', dict(code_identity=run['code_identity'], summary=run['summary'],
                work_records=run['work_records'], actual_inputs=run['inputs']))
            self.assertEqual(evaluation['schema'], 'aegisdc-business-composite-result-v1')
            self.assertEqual(set(evaluation['components']), {'diagnostic', 'instance_closure', 'costs'})
            self.assertEqual(run['summary']['duration_s'], 6)
            self.assertEqual(len(run['policy_public_decisions']), 8)
            self.assertAlmostEqual(run['summary']['service_deficit_time_s'], 3.5)
            self.assertEqual(evaluation['components']['diagnostic']['events'][0]['first_corroborated_fault_report_at_s'], .5)
            episodes = {e['question_id']:e for e in evaluation['components']['instance_closure']['episodes']}
            old, new = (episodes['cooling-direct/question-'+str(i)] for i in (0,1))
            self.assertIsNone(old['first_verified_closed_at_s'])
            self.assertEqual(old['actual_recheck_completed_at_s'], 5)
            self.assertEqual(old['recheck_report_arrived_at_s'], 5.5)
            self.assertTrue(old['assessments'][-1]['own_recheck']['passed'])
            self.assertEqual(new['first_risk_accepted_at_s'], 5.75)
            self.assertFalse(new['assessments'][-1]['risk_closed'])
            cost = evaluation['components']['costs']
            self.assertAlmostEqual(cost['personnel_total']['value'], 4.5)
            self.assertAlmostEqual(cost['actual']['tool_occupation_tool_s']['value'], 4.5)
            self.assertEqual(cost['issue_fees']['value'], 2)
            self.assertEqual(evaluation['run_binding']['boundary_events_sha256'], digest(run['inputs']['boundary_events']))
            self.assertEqual(evaluation['components']['diagnostic']['reference']['boundary_events_sha256'], digest(inputs['exogenous_events']))
        comparison = replay_api.compare_attempts(original, replayed)
        save('semantic-comparison.json', comparison)
        self.assertEqual(comparison['schema'], 'aegisdc-recorded-semantic-comparison-v1')
        self.assertEqual(comparison['status'], 'EXACT_REPLAY_SEMANTICS_MATCH')
        self.assertTrue(comparison['strict_values_match'])
        self.assertEqual(comparison['original_attempt_sha256'], before['record_sha256'])
        self.assertEqual(comparison['replay_attempt_sha256'], after['record_sha256'])
        self.assertEqual(replay_api.read_attempt(original)['record_sha256'], before['record_sha256'])
        save('qualification.json', dict(status='PASS', direct_record_calls=1, direct_replay_calls=1,
            direct_read_calls=3, direct_comparison_calls=1, original_status=first['status'], replay_status=second['status'],
            registered_research_trials=0, original54_status='FAILED_RETAINED'))
