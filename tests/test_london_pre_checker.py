"""Checker evidence integrity regressions, separate from v2 model qualification."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

SPEC=importlib.util.spec_from_file_location('r2_checker',Path(__file__).resolve().parents[1]/'scripts/qualify_london_pre.py')
CHECKER=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class CheckerEvidenceTests(unittest.TestCase):
    def ledger(self):
        return dict(executed_units=0,constructor_attempts=0,model_entry_calls=0,executed_assertions=0)

    def test_returned_alias_cannot_rewrite_an_earlier_capture(self):
        class MutableOutput:
            def __init__(self,world):self.value={'sequence':-1}
            def mechanics(self):
                self.value['sequence']+=1
                return self.value
        case=dict(id='alias',source_refs=['checker-only'],kind='physical',input={'world':{}},steps=[
            dict(label='first',op='mechanics',args={},expected={'sequence':0}),
            dict(label='second',op='mechanics',args={},expected={'sequence':1})])
        result=CHECKER.run_case(SimpleNamespace(PhysicalWorld=MutableOutput),case,self.ledger())
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['steps'][0]['actual'],{'sequence':0})

    def test_non_json_return_preserves_actual_entry_counts(self):
        class InvalidOutput:
            def __init__(self,world):pass
            def mechanics(self):return float('nan')
        case=dict(id='bad',source_refs=['checker-only'],kind='physical',input={'world':{}},steps=[
            dict(label='call',op='mechanics',args={},expected=0)])
        ledger=self.ledger()
        result=CHECKER.run_case(SimpleNamespace(PhysicalWorld=InvalidOutput),case,ledger)
        self.assertEqual(result['status'],'FAIL')
        self.assertEqual((ledger['executed_units'],ledger['constructor_attempts'],ledger['model_entry_calls']),(1,1,1))
        self.assertIn('error',result['steps'][0])
        CHECKER.canonical(result)

    def test_semantic_replay_ignores_only_explicitly_unselected_private_fields(self):
        a=dict(actual=dict(state={'vA':0},runtime_id='run-a'),selected_fields=['state'])
        b=dict(actual=dict(state={'vA':0},runtime_id='run-b'),selected_fields=['state'])
        self.assertEqual(CHECKER.semantic_result(a),CHECKER.semantic_result(b))
        a.pop('selected_fields');b.pop('selected_fields')
        self.assertNotEqual(CHECKER.semantic_result(a),CHECKER.semantic_result(b))


if __name__=='__main__':unittest.main()
