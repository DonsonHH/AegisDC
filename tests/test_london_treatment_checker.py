"""Input-purpose and record utilities; no runner, model or confirmation import."""
import importlib.util
from pathlib import Path
import sys
import unittest

scripts=Path(__file__).resolve().parents[1]/'scripts';sys.path.insert(0,str(scripts))
spec=importlib.util.spec_from_file_location('treatment_checker',scripts/'qualify_london_treatments.py');checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)

class CheckerTests(unittest.TestCase):
    def test_research_and_confirmation_headers_rejected(self):
        for schema in ['aegisdc-r3-development-inputs-v1','aegisdc-confirmation-inputs-v1']:
            with self.assertRaises(ValueError):checker.validate_engineering({'schema':schema,'classification':'ENGINEERING_ONLY'})

    def test_empty_expectations_rejected(self):
        x={'schema':'aegisdc-idp-engineering-v1','classification':'ENGINEERING_ONLY','public_tick_seconds':1,'units':[{'id':'x','kind':'triplet','expected':{'I':{},'D':{},'P':{}}}],'pairs':[{}]}
        with self.assertRaises(ValueError):checker.validate_engineering(x)

    def test_nested_private_keys_are_found(self):
        self.assertEqual(checker.private_keys({'context':{'next_private_event':3,'item':{'condition_id':'secret'}}}),['condition_id','next_private_event'])
        self.assertEqual(checker.private_keys({'records':[{'value':'LEGACY_LINE'}]}),[])

if __name__=='__main__':unittest.main()
