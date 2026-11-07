"""Pre-confirmation admission and immutable recorder continuity, without executing held worlds."""

import ast
import json
from pathlib import Path
import subprocess,sys,unittest
from hashlib import sha256
from tempfile import TemporaryDirectory

ROOT=Path(__file__).resolve().parents[1]


class ConfirmationFreezeTests(unittest.TestCase):
    def test_failed_confirmation_is_not_classified_without_failure_audit(self):
        # A saved failure can be a protection or qualification breach.  A
        # classifier must refuse until its cause has been independently audited.
        source='1'*40
        slot=dict(index=1,world_id='confirmation-01',family='fixture',arm='fifo',
                  duration_s=10,scheduled_decisions=10)
        start=dict(slot,status='STARTED',source=source,charged_simulated_s=10,
                   charged_scheduled_decisions=10)
        terminal=dict(slot,status='FAILED',source=source,physical_call_started=True,
                      physical_returned=True,error_type='ValueError',error='Execution overrode local protection')
        with TemporaryDirectory() as tmp:
            folder=Path(tmp);run=folder/'01-confirmation-01-fifo';run.mkdir()
            (folder/'batch.json').write_text(json.dumps(dict(execution_commit=source,slots=[slot],pins={})),encoding='utf-8')
            (run/'start.json').write_text(json.dumps(start),encoding='utf-8')
            (run/'terminal.json').write_text(json.dumps(terminal),encoding='utf-8')
            (folder/'attempts.jsonl').write_text(''.join(json.dumps(dict(r,recorded_at_utc='fixture'))+'\n'
                                                       for r in (start,terminal)),encoding='utf-8')
            artifacts={p.relative_to(folder).as_posix():sha256(p.read_bytes()).hexdigest()
                       for p in folder.rglob('*') if p.is_file()}
            total=dict(started=1,completed=0,failed=1,interrupted=0,unrun=0,
                       charged_simulated_s=10,charged_scheduled_decisions=10,returned_decisions=0)
            (folder/'receipt.json').write_text(json.dumps(dict(source_unchanged=True,execution_commit=source,
                artifacts=artifacts,total=total,status='STOPPED')),encoding='utf-8')
            result=subprocess.run([sys.executable,'-B','-X','utf8','scripts/analyze_registered_confirmation.py',
                str(folder),'--output',str(folder/'analysis')],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Failed or interrupted confirmation requires an explicit failure audit',result.stderr)
            self.assertFalse((folder/'analysis').exists())

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
