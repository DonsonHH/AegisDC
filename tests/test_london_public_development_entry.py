"""Wrapper-only tests using fabricated records. Never import the core model."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

path=Path(__file__).resolve().parents[1]/'scripts/run_london_public_development.py'
spec=importlib.util.spec_from_file_location('entry',path);entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)

def fake_result(common,noncompliant=False):
    calls=[];arms={}
    for arm in entry.ARMS:
        constraints={k:True for k in entry.CONSTRAINTS}
        if noncompliant and arm=='I':constraints['reserved_exit_honored']=False
        score=dict(trace_status='COMPLETE',L=2 if arm=='I' else 5,U=2 if arm=='I' else 5,hard_constraints=constraints,hard_constraints_ok=all(constraints.values()))
        score.update({k:0 for k in entry.COSTS})
        arms[arm]=dict(errors=[],final_audit=dict(time=20,original_input=common),public_trace=[],requests=[],requested_actions=[],score=score,reached=dict(stage='NO_ACTION',verification_result='NOT_REQUESTED'))
        calls.append(dict(kind='constructor',arm=arm))
    return dict(errors=[],arms=arms,calls=calls,counts=dict(constructor_attempts=3,plant_entry_calls=0,policy_calls=0,scorer_calls=0),execution_order=list(entry.ARMS),common_input_sha256=entry.digest(common),isolation=dict(initial_public_equal=True,initial_private_equal=True,input_unchanged=True,all_other_states_unchanged=True,object_ids={'model':{'I':1,'D':2,'P':3}},snapshots=[]))

class EntryTests(unittest.TestCase):
    def test_only_fixed_development_authorized(self):
        data=dict(schema='aegisdc-r3-development-inputs-v1',confirmation=False,treatments=list(entry.ARMS),public_tick_seconds=1,conditions=[dict(condition_id=x,classification='DISCLOSED_DEVELOPMENT',common={'H':20}) for x in entry.IDS])
        entry.validate_input(data,entry.INPUT_SHA)
        with self.assertRaises(ValueError):entry.validate_input(data,'wrong')
        data['schema']='aegisdc-confirmation-inputs-v1'
        with self.assertRaises(ValueError):entry.validate_input(data,entry.INPUT_SHA)

    def test_noncompliance_preserves_raw_difference_not_gain(self):
        actual=fake_result({'H':20},True)
        self.assertEqual(entry.inspect_result(actual,{'H':20},'C01'),[])
        row=entry.summarize('C01',actual,[])
        self.assertEqual(row['delta_L_D_minus_I'],3)
        self.assertFalse(row['valid_comparison'])
        self.assertEqual(row['comparison_status'],'NONCOMPLIANT_NOT_VALID_GAIN')

    def test_scoring_mismatch_is_fatal_and_null_stays_null(self):
        actual=fake_result({'H':20})
        actual['arms']['I']['score'].update(L=None,trace_status='INCOMPLETE_TRACE')
        actual['arms']['I']['score']['hard_constraints']['model_report_agrees']=False
        fatal=entry.inspect_result(actual,{'H':20},'C01')
        self.assertTrue(any('model_report_agrees' in x for x in fatal))
        row=entry.summarize('C01',actual,fatal)
        self.assertIsNone(row['delta_L_D_minus_I'])
        self.assertFalse(row['valid_comparison'])

    def test_fatal_preserves_current_and_does_not_execute_suffix(self):
        data=dict(conditions=[dict(condition_id=x,common={'H':20}) for x in entry.IDS]);calls=[]
        def fake(common,order):
            calls.append(order);result=fake_result(common)
            if len(calls)==2:result['errors']=['FABRICATED_TEST_ERROR']
            return result
        with tempfile.TemporaryDirectory() as temp:
            result=entry.execute_batch(data,fake,Path(temp),{'entry_revision':'test-only'})
            self.assertEqual(len(calls),2)
            self.assertEqual([r['status'] for r in result['rows']],['EXECUTED','ERROR']+['NOT_EXECUTED']*17)
            self.assertTrue((Path(temp)/'C02.json').exists())
            self.assertFalse((Path(temp)/'C03-started.json').exists())
            self.assertEqual(result['status'],'STOPPED_ON_ERROR')

    def test_core_not_imported_and_private_keys_detected(self):
        self.assertNotIn('aegis_dc.london_treatments',sys.modules)
        self.assertEqual(entry.private_fields({'context':{'tF':1}}),{'tF'})
        self.assertIsNone(entry.diff(None,0))

if __name__=='__main__':unittest.main()
