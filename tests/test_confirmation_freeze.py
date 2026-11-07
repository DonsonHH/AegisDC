"""Pre-confirmation admission and immutable recorder continuity, without executing held worlds."""

import ast
import json
from pathlib import Path
import subprocess,sys,unittest

ROOT=Path(__file__).resolve().parents[1]


class ConfirmationFreezeTests(unittest.TestCase):
    def test_public_amendment_is_limited_to_two_hydraulic_coordinates(self):
        result=subprocess.run([sys.executable,'-B','-X','utf8','scripts/prepare_confirmation.py','audit-admission'],
            cwd=ROOT,capture_output=True,text=True,encoding='utf-8',check=False)
        self.assertEqual(result.returncode,0,result.stderr)
        facts=json.loads(result.stdout)
        self.assertEqual(facts['status'],'PASS_EXPLICIT_ADMISSION_AMENDMENT')
        self.assertEqual(facts['screened_public_recipes'],24)
        self.assertEqual(facts['nonce_reads'],0)
        original=json.loads((ROOT/'evidence/mainline/engineering/32-execution-freeze/original-public-admission.json').read_bytes())
        self.assertEqual([r['variant'] for r in original['rejected']],['mr-a','am-a'])
        self.assertTrue(all(r['requested_flow_m3_s']>r['nominal_flow_ceiling_m3_s'] for r in original['rejected']))

    def test_confirmation_journal_is_the_tested_development_algorithm(self):
        def capture(path):
            module=ast.parse((ROOT/path).read_text(encoding='utf-8'))
            fn=next(node for node in module.body if isinstance(node,ast.FunctionDef) and node.name=='capture')
            # The only declared difference is that a released confirmation
            # batch reads its96 inputs and checks its one phase nonce.
            for node in ast.walk(fn):
                if isinstance(node,ast.keyword) and node.arg in ('held_inputs_read','held_seed_reads'):
                    node.value=ast.Constant(value=0)
            return ast.dump(fn,include_attributes=False)
        self.assertEqual(capture('scripts/registered_development.py'),capture('scripts/registered_confirmation.py'))
