"""Public preregistration CLI refuses changes outside the primary policy field."""

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'scripts/registered_comparison.py'
REFERENCE = ROOT / 'evidence/mainline/engineering/26-candidate/reference'


class RegisteredComparisonTests(unittest.TestCase):
    def test_historical_pair_reuses_the_entire_common_world(self):
        left = REFERENCE / 'online-baseline-inspect.json'
        right = REFERENCE / 'online-candidate-inspect.json'

        def audit(candidate):
            return subprocess.run(
                [sys.executable, '-B', '-X', 'utf8', str(CLI), 'audit-pair', str(left), str(candidate)],
                cwd=ROOT, capture_output=True, text=True, encoding='utf-8', check=False,
            )

        result = audit(right)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt['allowed_difference'], 'dispatch_program.policy_program.policy')
        self.assertEqual(receipt['shared_input_sha256'], '12ae64aa679a0d0fe08e160ff0cb0849b843884533f372907e50401463947f02')
        self.assertEqual(receipt['facility_calls'], 0)
        with TemporaryDirectory() as folder:
            edited = Path(folder) / 'edited.json'
            candidate = json.loads(right.read_bytes())
            candidate['dispatch_program']['decision_times_s'][0] += .125
            edited.write_text(json.dumps(candidate), encoding='utf-8')
            result = audit(edited)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Another pair input differs', result.stderr)

    def test_registry_rejects_a_cross_split_world_and_an_unbudgeted_arm(self):
        source = ROOT / 'docs/mainline/30-comparison-protocol-v1.json'

        def audit(path):
            return subprocess.run(
                [sys.executable, '-B', '-X', 'utf8', str(CLI), 'audit-plan', str(path)],
                cwd=ROOT, capture_output=True, text=True, encoding='utf-8', check=False,
            )

        result = audit(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt['worlds'], {'development':6,'confirmation':16,'ablation':8,'robustness':8})
        self.assertEqual(receipt['attempts'], 180)
        self.assertEqual(receipt['simulated_charge_s'], 1800)
        self.assertEqual(receipt['research_trials'], 0)
        with TemporaryDirectory() as folder:
            altered = Path(folder) / 'altered.json'
            original = json.loads(source.read_bytes())
            mutated = json.loads(source.read_bytes())
            mutated['phases']['confirmation']['worlds'][0]['id'] = original['phases']['development']['worlds'][0]['id']
            altered.write_text(json.dumps(mutated), encoding='utf-8')
            result = audit(altered)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('World IDs overlap', result.stderr)
            original['phases']['development']['budget']['attempts'] += 1
            altered.write_text(json.dumps(original), encoding='utf-8')
            result = audit(altered)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('budget differs', result.stderr)


    def test_development_materializes_a_shared_real_action_without_releasing_held_inputs(self):
        compiler = ROOT / 'scripts/prepare_comparison_worlds.py'
        with TemporaryDirectory() as folder:
            def build(world, method, name):
                target = Path(folder) / name
                run = subprocess.run([sys.executable,'-B','-X','utf8',str(compiler),
                    '--world',world,'--method',method,'--output',str(target)],
                    cwd=ROOT,capture_output=True,text=True,encoding='utf-8',check=False)
                return run,target

            first,left = build('development-01','one_observation_lookahead','base.json')
            second,right = build('development-01','evidence_consistent_contingent','candidate.json')
            self.assertEqual(first.returncode,0,first.stderr)
            self.assertEqual(second.returncode,0,second.stderr)
            admitted = json.loads(first.stdout)
            self.assertEqual(admitted['facility_calls'],0)
            self.assertEqual(admitted['selector_calls'],0)
            self.assertEqual(admitted['public_initial_eligible_paid_tasks'],2)
            pair = subprocess.run([sys.executable,'-B','-X','utf8',str(CLI),'audit-pair',str(left),str(right)],
                cwd=ROOT,capture_output=True,text=True,encoding='utf-8',check=False)
            self.assertEqual(pair.returncode,0,pair.stderr)
            document = json.loads(left.read_bytes())
            params = {p['id']:p['value'] for p in document['model']['parameters']}
            self.assertEqual(params['network_service_capacity'],.25)
            self.assertEqual(params['service_demand'],1)
            intervention = document['dispatch_program']['intervention_program']
            self.assertEqual(intervention['profile']['operations'][0]['kind'],'restore_network_capacity')
            self.assertEqual(intervention['bindings'][0]['setting'],.75)
            self.assertNotIn('network_service_capacity', json.dumps(document['dispatch_program']))
            held,path = build('confirmation-01','one_observation_lookahead','held.json')
            self.assertNotEqual(held.returncode,0)
            self.assertIn('Held phase is not released',held.stderr)
            self.assertFalse(path.exists())
