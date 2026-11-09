"""Public evidence seam: an unqualified later record cannot erase a usable sample."""
import json
import os
from pathlib import Path
import unittest

from aegis_dc.condition_assessment import assess_conditions
from aegis_dc.decision_view import DecisionGateway

ROOT=Path(__file__).resolve().parents[1]


class ConditionRecordSelectionTests(unittest.TestCase):
    def test_newer_unknown_sample_keeps_latest_qualified_observation_and_its_age(self):
        data=json.loads((ROOT/'tests/fixtures/39c-condition-record-selection-05.json').read_bytes())
        dispatch=json.loads((ROOT/data['base_fixture']).read_bytes())['dispatch_program']
        profile=json.loads((ROOT/data['profile_descriptor']).read_bytes())['public_profile']
        ledger=dispatch['evidence_ledger'];ledger['records']+=data['records']
        plan=dict(schema='aegisdc-public-preparation-plan-v1',id='39c-public-selection-plan',
            basis='synthetic_assumption',time_unit='s',decision_times_s=[data['as_of_s']],requests=[])
        frame=DecisionGateway(dispatch['nominal_knowledge'],ledger,plan).next_frame()
        output=Path(os.environ['AEGIS_ENGINEERING_RESULT_DIR']) if os.environ.get('AEGIS_ENGINEERING_RESULT_DIR') else None
        def save(name,value):
            if output is not None:
                with (output/name).open('x',encoding='utf-8',newline='\n') as stream:
                    json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
        save('public-call-input.json',dict(frame=frame,profile=profile))
        assessment=assess_conditions(frame,profile)
        save('public-assessment.json',assessment)
        row=assessment['conditions'][0]
        self.assertEqual(row['status'],'ABNORMAL')
        self.assertEqual(row['observed_at_s'],0.5)
        self.assertEqual(row['latest_source_arrival_at_s'],0.75)
        self.assertEqual(row['supporting_record_ids'],['qualified-old'])
        self.assertEqual(row['blocking_record_ids'],['unknown-new'])
        self.assertEqual(row['available_at_s'],2)
        self.assertEqual(assessment['private_truth_used'],False)


if __name__=='__main__':unittest.main()
