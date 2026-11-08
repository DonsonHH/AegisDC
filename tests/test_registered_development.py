"""Check the registered development input boundary without physical execution."""

import json
from pathlib import Path
import subprocess
import sys
import unittest
from historical_research_checkout import historical_checkout

ROOT=Path(__file__).resolve().parents[1]
RUNNER=ROOT/'scripts/registered_development.py'


class RegisteredDevelopmentTests(unittest.TestCase):
    def test_plan_pins_development_only_and_rotates_arms_per_world(self):
        with historical_checkout() as historical:
            result=subprocess.run([sys.executable,'-B','-X','utf8','scripts/registered_development.py','plan'],cwd=historical,
                capture_output=True,encoding='utf-8',check=False)
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout)
        self.assertEqual(data['status'],'PASS_DEVELOPMENT_PLAN_ONLY')
        self.assertEqual(data['phase'],'development')
        self.assertEqual(data['budget'],{'attempts':36,'simulated_charge_s':360,'scheduled_decisions':360})
        self.assertEqual(data['registered_research_trials'],0)
        self.assertEqual(data['held_inputs_read'],0)
        rows=data['slots']
        self.assertEqual(len(rows),36)
        self.assertEqual(len({(row['world_id'],row['arm']) for row in rows}),36)
        self.assertEqual([(rows[i]['world_id'],rows[i]['arm']) for i in range(0,36,6)],
            [('development-01','no_human'),('development-02','periodic'),
             ('development-03','fifo'),('development-04','risk_condition_priority_adapted'),
             ('development-05','one_observation_lookahead'),('development-06','evidence_consistent_contingent')])
        self.assertTrue(all(len(row['input_sha256'])==64 and row['duration_s']==10 for row in rows))

    def test_old_lock_refuses_changed_live_source(self):
        result=subprocess.run([sys.executable,'-B','-X','utf8',str(RUNNER),'plan'],cwd=ROOT,
            capture_output=True,encoding='utf-8',check=False)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Frozen protocol, source or working bytes differ',result.stderr)


    def test_journal_rejects_a_started_slot_relabelled_unrun_or_partial_tail(self):
        from tempfile import TemporaryDirectory

        journal=ROOT/'scripts/development_journal.py'
        source='1'*40
        slots=[dict(index=i,world_id=f'development-{i:02}',arm='fifo',duration_s=10,scheduled_decisions=10)
               for i in (1,2)]
        with TemporaryDirectory() as tmp:
            folder=Path(tmp)
            (folder/'batch.json').write_text(json.dumps(dict(slots=slots,execution_commit=source)),encoding='utf-8')
            one=folder/'01-development-01-fifo'
            one.mkdir()
            start=dict(slots[0],status='STARTED',source=source,charged_simulated_s=10,charged_scheduled_decisions=10)
            finish=dict(slots[0],status='FAILED',source=source,physical_call_started=True,physical_returned=False)
            unrun=dict(slots[1],status='UNRUN',source=source)
            (one/'start.json').write_text(json.dumps(start),encoding='utf-8')
            (one/'terminal.json').write_text(json.dumps(finish),encoding='utf-8')

            def check(rows,tail=b''):
                raw=b''.join((json.dumps(dict(row,recorded_at_utc='fixture'))+'\n').encode() for row in rows)+tail
                (folder/'attempts.jsonl').write_bytes(raw)
                return subprocess.run([sys.executable,'-B','-X','utf8',str(journal),str(folder)],cwd=ROOT,
                    capture_output=True,text=True,encoding='utf-8',check=False)

            result=check([start,finish,unrun])
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['total']['started'],1)
            self.assertEqual(json.loads(result.stdout)['total']['charged_simulated_s'],10)
            self.assertEqual(json.loads(result.stdout)['total']['unrun'],1)
            self.assertNotEqual(check([start,dict(slots[0],status='UNRUN',source=source),unrun]).returncode,0)
            self.assertNotEqual(check([start,finish,unrun],b'{"partial":').returncode,0)
