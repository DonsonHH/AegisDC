"""Checker self-checks, separate from engineering qualification units."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('e14_checker',Path(__file__).resolve().parents[1]/'scripts/qualify_london_e14.py')
checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)


class CheckerTests(unittest.TestCase):
    def test_literal_type_and_missing_field(self):
        self.assertFalse(checker.literal_matches(True,1))
        self.assertFalse(checker.literal_matches({'value':0},{'value':0,'source':'x'}))

    def test_observation_snapshot_is_detached(self):
        original={'history':[{'value':0}]};copy=checker.detached(original)
        original['history'][0]['value']=1
        self.assertEqual(copy,{'history':[{'value':0}]})

    def test_balances_reject_incorrect_report(self):
        a=dict(segments=[dict(start=0,end=2,power=1,demand=1,service=0,source='UPS')],time=2,load_energy=2,ups_energy=2,original_input={'E0':3},E=1,L=2,U=2)
        self.assertTrue(all(checker.independent_balances(a).values()))
        a['L']=0
        self.assertFalse(checker.independent_balances(a)['loss'])


if __name__=='__main__':unittest.main()
