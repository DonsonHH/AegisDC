"""A new public instance cannot inherit a different instance's evidence closure."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from aegis_dc.dispatch_policy import choose_work
from aegis_dc.evidence_ledger import EvidenceLedger,RECORD_FIELDS

ROOT=Path(__file__).resolve().parents[1]


class InstanceCrossScopeTests(unittest.TestCase):
    def test_new_instance_cannot_borrow_the_old_instances_verified_closure(self):
        seed=json.loads((ROOT/'tests/fixtures/39c-instance-public-seed-20.json').read_bytes())
        frame=deepcopy(seed['frame']);program=deepcopy(seed['policy_program']);history=deepcopy(seed['history'])
        closure=deepcopy(seed['closure_program'])
        self.assertEqual(frame['as_of_s'],5.5)
        template=program['templates'][0]
        self.assertEqual(template['id'],'cooling-direct')
        template['max_instances']=2
        declarations=program['inspection_declaration']['bindings']
        for row in list(declarations):
            binding=deepcopy(row)
            binding['task_id']=binding['task_id'][:-1]+'1'
            binding['record_id']+='-instance1'
            binding['provenance']=dict(origin_id=binding['record_id'],copied_from_record_id=None)
            declarations.append(binding)
        action=deepcopy(program['intervention_declaration']['bindings'][0])
        action['task_id']='cooling-direct/action-1'
        program['intervention_declaration']['bindings'].append(action)
        closure['intervention_declaration']=deepcopy(program['intervention_declaration'])
        closure['intervention_feedback']=deepcopy(history['intervention_feedback'])
        snapshot=frame['evidence']
        records=[{key:row[key] for key in RECORD_FIELDS} for row in snapshot['records']]
        original=next(row for row in records if row['id']==history['question_instances'][0]['trigger_record_id'])
        claim=deepcopy(original)
        claim.update(id='cooling-second-origin-20',observed_at_s=5.25,arrived_at_s=5.5,valid_until_s=10,
            provenance=dict(origin_id='cooling-second-origin-20',copied_from_record_id=None))
        records.append(claim)
        ledger=dict(schema='aegisdc-evidence-ledger-v1',id=snapshot['ledger_id'],facility_id=frame['facility_id'],
            basis='synthetic_assumption',time_unit='s',**snapshot['static_knowledge'],records=records)
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
        old=questions['cooling-direct/question-0'];new=questions['cooling-direct/question-1']
        self.assertEqual(old['status'],'VERIFIED_CLOSED')
        self.assertTrue(old['risk_closed'])
        self.assertEqual(new['status'],'OPEN_UNCONFIRMED')
        self.assertFalse(new['risk_closed'])
        self.assertFalse(new['question_closed'])
        self.assertEqual((new['opened_at_s'],new['task_id'],new['recheck_task_id']),
            (5.5,'cooling-direct/action-1','cooling-direct/recheck-1'))
        self.assertFalse(new['own_recheck']['passed'])
        self.assertEqual(new['supporting_record_ids'],[])
        self.assertEqual(new['checks'],[])
        public={row['id']:row for row in choice['questions']}
        self.assertIsNone(public['cooling-direct/question-1']['fault_probability'])
        self.assertFalse(public['cooling-direct/question-1']['risk_closed'])
        self.assertEqual(len(choice['question_instances']),2)


if __name__=='__main__':unittest.main()
