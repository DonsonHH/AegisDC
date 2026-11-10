"""Historical projection must retain the prefix of simultaneously opened instances."""

import json
import os
from pathlib import Path
import unittest

from aegis_dc.dispatch_policy import choose_work
from aegis_dc.evidence_ledger import EvidenceLedger, RECORD_FIELDS

ROOT = Path(__file__).resolve().parents[1]


class InstanceReviewSimultaneousOpeningsTests(unittest.TestCase):
    def test_invalid_review_for_second_new_instance_does_not_break_slot_history(self):
        data = json.loads((ROOT / 'evidence/mainline/engineering/39c-development/slice-24/'
                           'protocol24-green-frozen-public-call-input.json').read_bytes())
        frame, policy, history, closure = (
            data[key] for key in ('frame', 'program', 'history', 'closure_program')
        )
        history.update(issued=[], work_feedback=[], question_instances=[], intervention_feedback=[])
        closure['intervention_feedback'] = []
        closure['profile']['authorizations'][0]['expires_at_s'] = 5.5
        snapshot = frame['evidence']
        records = [{key: row[key] for key in sorted(RECORD_FIELDS)}
                   for row in snapshot['records'] if row['id'] != 'flow-after-clean']
        ledger = dict(schema='aegisdc-evidence-ledger-v1', id=snapshot['ledger_id'],
                      facility_id=frame['facility_id'], basis='synthetic_assumption',
                      time_unit='s', **snapshot['static_knowledge'], records=records)
        frame['evidence'] = EvidenceLedger(ledger).snapshot(5.5)
        output = os.environ.get('AEGIS_ENGINEERING_RESULT_DIR')

        def save(name, value):
            if output:
                with (Path(output) / name).open('x', encoding='utf-8', newline='\n') as stream:
                    json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False, sort_keys=True)
                    stream.write('\n')

        save('frozen-public-call-input.json', data)
        self.public_choice_calls = 1
        choice = choose_work(frame, policy, history,
                             intervention_declaration=policy['intervention_declaration'],
                             closure_program=closure)
        save('actual-public-choice.json', choice)
        self.assertEqual([(row['slot'], row['opened_at_s']) for row in choice['question_instances']],
                         [(0, 5.5), (1, 5.5)])
        questions = choice['question_lifecycle']['questions']
        self.assertEqual([row['status'] for row in questions], ['OPEN_UNCONFIRMED', 'OPEN_UNCONFIRMED'])
        self.assertTrue(all(not row['question_closed'] and not row['risk_closed'] for row in questions))
        self.assertEqual(questions[1].get('historical_dispositions', []), [])
        self.assertEqual(choice['chosen_candidate_id'], 'cooling-direct/action-0')


if __name__ == '__main__':
    unittest.main()
