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


    def test_held_blueprints_never_read_seed_material_and_pair_robustness_levels(self):
        source = ROOT / 'docs/mainline/30-comparison-protocol-v1.json'
        catalog = ROOT / 'configs/full-facility-comparison-held-blueprints-v1.json'

        def audit(path):
            return subprocess.run([sys.executable,'-B','-X','utf8',str(CLI),'audit-blueprints',
                str(source),str(path)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',check=False)

        result = audit(catalog)
        self.assertEqual(result.returncode,0,result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt['confirmation_blueprints'],16)
        self.assertEqual(receipt['ablation_blueprints'],8)
        self.assertEqual(receipt['robustness_blocks'],4)
        self.assertEqual(receipt['held_inputs_materialized'],0)
        with TemporaryDirectory() as folder:
            edited = Path(folder) / 'bad.json'
            blueprint = json.loads(catalog.read_bytes())
            blueprint['confirmation']['network-restorable'][1] = blueprint['confirmation']['network-restorable'][0]
            edited.write_text(json.dumps(blueprint),encoding='utf-8')
            result = audit(edited)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Reused blueprint',result.stderr)


    def test_outcome_arithmetic_keeps_the_original_denominator_and_counts_wait_once(self):
        protocol = json.loads((ROOT/'docs/mainline/30-comparison-protocol-v1.json').read_bytes())
        rows = []
        for world in protocol['phases']['confirmation']['worlds']:
            baseline = {'service_deficit_time_s':2,'worker_travel_person_s':1,'worker_work_person_s':1,
                        'worker_wait_person_s':.25,'access_check_person_s':.25,'tool_occupation_tool_s':1.25}
            candidate = dict(baseline,service_deficit_time_s=1,worker_work_person_s=1.5,
                             access_check_person_s=.75,tool_occupation_tool_s=1.75)
            rows.append({'world_id':world['id'],'baseline':baseline,'candidate':candidate,
                         'identified_first_difference':True,'hard_violations':[]})
        analyzer = ROOT/'scripts/summarize_comparison_facts.py'
        with TemporaryDirectory() as folder:
            facts = Path(folder)/'facts.json'

            def run():
                facts.write_text(json.dumps({'schema':'aegisdc-comparison-analysis-facts-v1','pairs':rows}),
                                 encoding='utf-8')
                result = subprocess.run([sys.executable,'-B','-X','utf8',str(analyzer),
                    str(ROOT/'docs/mainline/30-comparison-protocol-v1.json'),str(facts)],
                    cwd=ROOT,capture_output=True,text=True,encoding='utf-8',check=False)
                self.assertEqual(result.returncode,0,result.stderr)
                return json.loads(result.stdout)

            result = run()
            self.assertEqual(result['status'],'PRACTICAL_GAIN')
            self.assertEqual(result['mean_extra_paid_person_s'],.5)
            self.assertEqual(result['mean_service_delta_s'],1)
            rows[-1]['candidate'] = None
            result = run()
            self.assertEqual(result['status'],'INCOMPLETE')
            self.assertEqual(result['planned_denominator'],16)
            self.assertEqual(result['mean_service_delta_bounds_s'],[.4375,1.0625])
            self.assertEqual(result['completed_primary_pairs'],15)
            self.assertEqual(result['source_verification'],'REQUIRED_SEPARATELY')


    def test_semantic_audit_rejects_early_release_and_omitted_safety_rules(self):
        protocol_path=ROOT/'docs/mainline/30-comparison-protocol-v1.json'
        with TemporaryDirectory() as folder:
            target=Path(folder)/'unsafe.json'
            for change in ('early-release','negative-gain','missing-stops','missing-rules'):
                plan=json.loads(protocol_path.read_bytes())
                if change=='early-release':
                    plan['phases']['confirmation']['release']='IMMEDIATE'
                elif change=='negative-gain':
                    plan['comparison']['minimum_worthwhile_gain_s']=-1
                elif change=='missing-stops':
                    plan['attempt_policy']['stop_conditions']=[]
                else:
                    del plan['comparison']['outcome_rules']
                target.write_text(json.dumps(plan),encoding='utf-8')
                result=subprocess.run([sys.executable,'-B','-X','utf8',str(CLI),'audit-plan',str(target)],
                    cwd=ROOT,capture_output=True,text=True,encoding='utf-8',check=False)
                self.assertNotEqual(result.returncode,0,change)
                self.assertIn('semantic',result.stderr.lower())


    def test_nonce_commitment_and_release_refusal_do_not_expose_a_held_seed(self):
        gate=ROOT/'scripts/comparison_release.py'
        with TemporaryDirectory() as folder:
            nonce=Path(folder)/'synthetic-nonce.bin'
            nonce.write_bytes(bytes(range(32)))
            command=[sys.executable,'-B','-X','utf8',str(gate),'audit-nonce',str(nonce),
                     '--sha256','630dcd2966c4336691125448bbb25b4ff412a49c732db2c8abc1b8581bd710dd']
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',check=False)
            self.assertEqual(result.returncode,0,result.stderr)
            receipt=json.loads(result.stdout)
            self.assertEqual(receipt['status'],'PASS_COMMITMENT')
            self.assertEqual(receipt['held_inputs_materialized'],0)
            self.assertNotIn('0001020304',result.stdout)
            command[-1]='0'*64
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',check=False)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('commitment',result.stderr.lower())
            result=subprocess.run([sys.executable,'-B','-X','utf8',str(gate),'audit-release',
                '--phase','confirmation','--stage','prepare','--lock',str(Path(folder)/'absent-lock.json'),
                '--nonce',str(Path(folder)/'absent-nonce.bin')],
                cwd=ROOT,capture_output=True,text=True,encoding='utf-8',check=False)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('accepted ticket 30',result.stderr.lower())


    def test_confirmation_can_prepare_before_32_but_execute_only_its_reviewed_source(self):
        from hashlib import sha256
        import ast
        import shutil

        gate=ROOT/'scripts/comparison_release.py'
        source=ast.parse(gate.read_text(encoding='utf-8'))
        keys={'PINS','PROTOCOL','LOCK','AUTHORITY','FROZEN_STATUS','HELD'}
        cli={}
        for statement in source.body:
            if isinstance(statement,ast.Assign) and isinstance(statement.targets[0],ast.Name):
                name=statement.targets[0].id
                if name in keys:
                    cli[name]=(['docs/mainline/30-comparison-protocol-v1.json',*[
                        ast.literal_eval(node) for node in statement.value.elts[1:]]] if name=='PINS'
                        else ast.literal_eval(statement.value))
        digest=lambda data: sha256(data).hexdigest()
        protocol_file=cli['PROTOCOL']
        lock_file=cli['LOCK']
        authority_file=cli['AUTHORITY']
        with TemporaryDirectory() as folder:
            base=Path(folder)
            repo=base/'synthetic-repo'
            repo.mkdir()

            def git(*args):
                return subprocess.check_output(['git','-c','core.autocrlf=false','-c','user.name=Fixture',
                    '-c','user.email=fixture@example.invalid',*args],cwd=repo,encoding='utf-8').strip()

            def write(path,value):
                out=repo/path
                out.parent.mkdir(parents=True,exist_ok=True)
                out.write_bytes(json.dumps(value,indent=2).encode()+b'\n')

            def commit(message):
                git('add','--','.')
                git('commit','-qm',message)
                return git('rev-parse','HEAD')

            def audit(stage):
                return subprocess.run([sys.executable,'-B','-X','utf8',str(repo/'scripts/comparison_release.py'),
                    'audit-release','--phase','confirmation','--stage',stage,'--lock',str(repo/lock_file),
                    '--nonce',str(nonce),'--input-directory',str(input_dir),'--output',str(base/'unused-output')],
                    cwd=repo,capture_output=True,text=True,encoding='utf-8',check=False)

            git('init','-q')
            for name in cli['PINS']:
                out=repo/name
                out.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(ROOT/name,out)
            runtime='src/aegis_dc/fixture.py'
            (repo/runtime).parent.mkdir()
            (repo/runtime).write_bytes(b'# static gate fixture, never executed\n')
            plan=json.loads((repo/protocol_file).read_bytes())
            plan['status']=cli['FROZEN_STATUS']
            write(protocol_file,plan)
            design=commit('Frozen draft')
            nonces={name:bytes([i])*32 for i,name in enumerate(cli['HELD'],1)}
            nonce=base/'test-only-confirmation.bin'
            nonce.write_bytes(nonces['confirmation'])
            pins={name:digest((repo/name).read_bytes()) for name in (*cli['PINS'],runtime)}
            write(lock_file,dict(schema='aegisdc-comparison-source-lock-v1',status='FROZEN_INPUT_DESIGN',
                protocol_id=plan['id'],design_commit=design,pins=pins,
                commitments_sha256={phase:digest(raw) for phase,raw in nonces.items()},
                held_inputs_materialized=0,registered_research_trials=0))
            lock_sha=digest((repo/lock_file).read_bytes())
            write(authority_file,dict(status='ACCEPTED',ticket='30',design_commit=design,
                protocol_lock=lock_file,protocol_lock_sha256=lock_sha))
            write('docs/mainline/evidence/31-root.json',dict(status='ACCEPTED',ticket='31'))
            commit('Accepted 30 and 31')
            input_dir=base/'synthetic-byte-fixtures'
            result=audit('prepare')
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['held_inputs_materialized'],0)
            result=audit('execute')
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Requires accepted ticket 32',result.stderr)

            runner=repo/'scripts/fixture_runner.py'
            runner.write_bytes(b'# Frozen runner identity only\n')
            execution=commit('Frozen execution source')
            phase=plan['phases']['confirmation']
            inputs={}
            for world in phase['worlds']:
                for arm in phase['arms']:
                    name=world['id']+'/'+arm+'.json'
                    path=input_dir/name
                    path.parent.mkdir(parents=True,exist_ok=True)
                    raw=json.dumps({'fixture_byte_identity_only':name}).encode()
                    path.write_bytes(raw)
                    inputs[name]=digest(raw)
            code={name:digest((repo/name).read_bytes())
                  for role in ('src','scripts','configs')
                  for name in git('ls-files','--',role).splitlines() if name.endswith(('.py','.json'))}
            execution_lock='docs/mainline/evidence/30-confirmation-execution-lock.json'
            write(execution_lock,dict(schema='aegisdc-comparison-execution-lock-v1',
                status='REVIEWED_FOR_EXECUTION',phase='confirmation',design_lock_sha256=lock_sha,
                execution_source=execution,execution_pins=code,interpreter_sha256=digest(Path(sys.executable).read_bytes()),
                input_hashes=inputs,budget=phase['budget']))
            write('docs/mainline/evidence/32-root.json',dict(status='ACCEPTED',ticket='32',
                execution_lock=execution_lock,execution_lock_sha256=digest((repo/execution_lock).read_bytes())))
            governance=commit('Accepted 32, no executable changes')
            result=audit('execute')
            self.assertEqual(result.returncode,0,result.stderr)
            verdict=json.loads(result.stdout)
            self.assertEqual(verdict['execution_source'],execution)
            self.assertEqual(verdict['checked_commit'],governance)
            self.assertEqual(verdict['facility_calls'],0)
            runner.write_bytes(b'# Unauthorized code change\n')
            commit('Change executable after freeze')
            result=audit('execute')
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Executable files differ',result.stderr)
