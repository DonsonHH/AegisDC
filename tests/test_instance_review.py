"""An arrived authorized management disposition is distinct from physical closure."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from aegis_dc.dispatch_policy import choose_work
from aegis_dc.evidence_ledger import EvidenceLedger,RECORD_FIELDS

ROOT=Path(__file__).resolve().parents[1]


class InstanceReviewTests(unittest.TestCase):
    def test_arrived_authorized_acceptance_closes_only_its_instance_without_physical_claim(self):
        seed=json.loads((ROOT/'tests/fixtures/39c-two-instance-public-seed-21.json').read_bytes())
        frame=deepcopy(seed['frame']);program=deepcopy(seed['program']);history=deepcopy(seed['history'])
        closure=deepcopy(seed['closure_program']);closure['schema']='aegisdc-instance-closure-program-v2'
        profile=closure['profile'];profile['schema']='aegisdc-instance-closure-profile-v2'
        profile['authorizations']=[dict(id='research-risk-owner-21',source_id='instance-review-owner-21',
            question_ids=['cooling-direct/question-1'],dispositions=['ACCEPT_RISK'],starts_at_s=0,expires_at_s=8,
            basis='synthetic_assumption',source_note='Finite synthetic management authority; no field equipment permission.')]
        profile['review_channels']=[dict(id='instance1-review-21',question_id='cooling-direct/question-1',
            source_id='instance-review-owner-21',target_id='intake_pump',observable_id='instance-disposition-21',
            authorization_id='research-risk-owner-21',record_id='accept-risk-instance1-21')]
        profile['false_alarm_reviews']=[]
        snapshot=frame['evidence'];static=deepcopy(snapshot['static_knowledge'])
        static['observables'].append(dict(id='instance-disposition-21',quantity='category',value_type='text',unit='1'))
        static['sources'].append(dict(id='instance-review-owner-21',kind='human_report',basis='synthetic_assumption',
            target_ids=['intake_pump'],observable_ids=['instance-disposition-21'],dependency_group=None,
            source_note='Hand-authored public management record for finite engineering qualification, not a real site instruction.'))
        records=[{key:row[key] for key in RECORD_FIELDS} for row in snapshot['records']]
        records.append(dict(id='accept-risk-instance1-21',source_id='instance-review-owner-21',target_id='intake_pump',
            observable_id='instance-disposition-21',unit='1',value='ACCEPT_RISK',observed_at_s=5.5,arrived_at_s=5.5,
            valid_until_s=8,quality=dict(status='reported',error_bound=None,note='Explicit synthetic management disposition.'),
            provenance=dict(origin_id='accept-risk-instance1-21',copied_from_record_id=None)))
        ledger=dict(schema='aegisdc-evidence-ledger-v1',id=snapshot['ledger_id'],facility_id=frame['facility_id'],
            basis='synthetic_assumption',time_unit='s',**static,records=records)
        frame['evidence']=EvidenceLedger(ledger).snapshot(5.5)
        output=Path(os.environ['AEGIS_ENGINEERING_RESULT_DIR']) if os.environ.get('AEGIS_ENGINEERING_RESULT_DIR') else None
        def save(name,value):
            if output is not None:
                with (output/name).open('x',encoding='utf-8',newline='\n') as stream:
                    json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
        save('frozen-public-call-input.json',dict(frame=frame,program=program,history=history,closure_program=closure))
        self.public_choice_calls=1
        choice=choose_work(frame,program,history,intervention_declaration=program['intervention_declaration'],closure_program=closure)
        save('actual-public-choice.json',choice)
        questions={row['question_id']:row for row in choice['question_lifecycle']['questions']}
        self.assertEqual(questions['cooling-direct/question-0']['status'],'VERIFIED_CLOSED')
        reviewed=questions['cooling-direct/question-1']
        self.assertEqual(reviewed['status'],'RISK_ACCEPTED')
        self.assertTrue(reviewed['question_closed'])
        self.assertFalse(reviewed['risk_closed'])
        self.assertFalse(reviewed['physical_restoration_claim'])
        self.assertFalse(reviewed['own_recheck']['passed'])
        self.assertEqual(reviewed['disposition_record_ids'],['accept-risk-instance1-21'])
        self.assertEqual(reviewed['supporting_record_ids'],[])
        self.assertIsNone(choice['chosen_candidate_id'])
        public=next(row for row in choice['questions'] if row['id']=='cooling-direct/question-1')
        self.assertTrue(public['question_closed'])
        self.assertFalse(public['risk_closed'])
        self.assertIsNone(public['fault_probability'])


if __name__=='__main__':unittest.main()
