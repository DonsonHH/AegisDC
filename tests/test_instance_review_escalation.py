"""An arrived, authorized escalation keeps an instance open despite risk acceptance."""

import json
import os
from pathlib import Path
import unittest

from aegis_dc.dispatch_policy import choose_work
from aegis_dc.evidence_ledger import EvidenceLedger, RECORD_FIELDS


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / (
    'evidence/mainline/engineering/39c-development/slice-24/'
    'protocol24-green-frozen-public-call-input.json'
)


class InstanceReviewEscalationTests(unittest.TestCase):
    def test_escalation_takes_precedence_and_keeps_instance_open(self):
        data = json.loads(FIXTURE.read_bytes())
        frame, policy, history, closure = (
            data[k] for k in ('frame', 'program', 'history', 'closure_program')
        )
        question_id = 'cooling-direct/question-1'
        escalation_id = 'escalation-question-1-28'
        source_id = 'escalation-review-source-28'
        observable_id = 'escalation-disposition-28'
        grant_id = 'escalation-authority-28'
        snapshot = frame['evidence']
        static = snapshot['static_knowledge']
        static['sources'].append(dict(
            id=source_id, kind='human_report', basis='synthetic_assumption',
            target_ids=['intake_pump'], observable_ids=[observable_id], dependency_group=None,
            source_note='Synthetic management escalation channel for a finite engineering witness.'))
        static['observables'].append(dict(
            id=observable_id, quantity='category', value_type='text', unit='1'))
        records = [{key: row[key] for key in RECORD_FIELDS} for row in snapshot['records']]
        records.append(dict(
            id=escalation_id, source_id=source_id, target_id='intake_pump',
            observable_id=observable_id, unit='1', value='ESCALATE',
            observed_at_s=5.5, arrived_at_s=5.5, valid_until_s=8,
            quality=dict(status='reported', error_bound=None, note='Escalate the open management question.'),
            provenance=dict(origin_id=escalation_id, copied_from_record_id=None)))
        ledger = dict(schema='aegisdc-evidence-ledger-v1', id=snapshot['ledger_id'],
                      facility_id=frame['facility_id'], basis='synthetic_assumption',
                      time_unit='s', **static, records=records)
        frame['evidence'] = EvidenceLedger(ledger).snapshot(5.5)
        profile = closure['profile']
        profile['authorizations'].append(dict(
            id=grant_id, source_id=source_id, question_ids=[question_id],
            dispositions=['ESCALATE'], starts_at_s=5, expires_at_s=8,
            basis='synthetic_assumption', source_note='Management authority only.'))
        # List escalation first so a last-channel-wins implementation would fail.
        profile['review_channels'].insert(0, dict(
            id='escalation-channel-28', question_id=question_id, source_id=source_id,
            target_id='intake_pump', observable_id=observable_id,
            authorization_id=grant_id, record_id=escalation_id))

        output = os.environ.get('AEGIS_ENGINEERING_RESULT_DIR')

        def save(name, value):
            if output:
                with (Path(output) / name).open('x', encoding='utf-8', newline='\n') as stream:
                    json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
                    stream.write('\n')

        save('frozen-public-call-input.json', data)
        self.public_choice_calls = 1
        choice = choose_work(frame, policy, history,
                             intervention_declaration=policy['intervention_declaration'],
                             closure_program=closure)
        save('actual-public-choice.json', choice)

        questions = {row['question_id']: row for row in choice['question_lifecycle']['questions']}
        self.assertEqual(questions['cooling-direct/question-0']['status'], 'VERIFIED_CLOSED')
        current = questions[question_id]
        self.assertEqual(current['status'], 'ESCALATED')
        self.assertIs(current['question_closed'], False)
        self.assertIs(current['risk_closed'], False)
        self.assertIs(current['physical_restoration_claim'], False)
        self.assertEqual(current['disposition_record_ids'], ['accept-risk-instance1-21', escalation_id])
        self.assertEqual([(row['record_id'], row['disposition'], row['arrived_at_s'])
                          for row in current['trace']],
                         [('accept-risk-instance1-21', 'ACCEPT_RISK', 5.5),
                          (escalation_id, 'ESCALATE', 5.5)])
        stages = {row['task_id']: row['prerequisites_met'] for row in choice['stage_gates']}
        self.assertIs(stages['cooling-direct/action-1'], True)
        self.assertIs(stages['cooling-direct/inspect-1'], True)
        self.assertIsNone(choice['chosen_candidate_id'])  # Existing shared budget remains spent.


if __name__ == '__main__':
    unittest.main()
