"""Online candidate behavior through the advancing public facility boundary."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import os
import subprocess
import sys
import unittest
from uuid import uuid4

from aegis_dc.plant import simulate_scenario,save_run
from test_dispatch_policy import lookahead_run_fixture
from test_evidence_consistent_policy import informative_fixture

ROOT=Path(__file__).resolve().parents[1]


def online_fixture(policy_name='evidence_consistent_contingent',period=10):
    model,_=lookahead_run_fixture();frame,policy,_=informative_fixture()
    policy['policy']=policy_name
    projection=policy['evidence_projection'];projection.update(schema='aegisdc-evidence-projection-v3',
        valuation_mass_basis='EXACT_FINITE_PUBLIC_BELIEF_CONTEXT_V1')
    sensors=json.loads((ROOT/'configs/full-facility-sensor-channels-v1.json').read_bytes())
    sensors['measurements']=[m for m in sensors['measurements'] if m['id']=='rectifier-meter']
    sensors['channels']=[c for c in sensors['channels'] if c['measurement_id']=='rectifier-meter']
    sensors['measurements'][0].update(period_s=period,declared_bias_bound=0,declared_noise_bound=0,
        quantization_bound=0,declared_dropout_probability=0)
    projection['background_sensor_profile']=deepcopy(sensors)
    registry=frame['evidence']['static_knowledge']
    ledger=dict(schema='aegisdc-evidence-ledger-v1',id=frame['evidence']['ledger_id'],facility_id=frame['facility_id'],
        basis='synthetic_assumption',time_unit='s',**deepcopy(registry),records=[])
    _,original=lookahead_run_fixture();inspection=deepcopy(original['inspection_program'])
    inspection['profile']=deepcopy(projection['inspection_profile'])
    program=dict(schema='aegisdc-policy-run-program-v3',id='candidate26-online-engineering',policy_program=policy,
        nominal_knowledge=frame['nominal_knowledge'],evidence_ledger=ledger,decision_times_s=[1,2.5,2.75,4.5],
        inspection_program=inspection,intervention_program=deepcopy(policy['intervention_declaration']),
        sensor_program=dict(profile=sensors,realization=dict(schema='aegisdc-private-observation-realization-v1',seed=26,
            biases={'rectifier-meter':0},noise_bounds={'rectifier-meter':0},dropout_probabilities={'rectifier-meter':0})),
        closure_program=None,preparation_requests=deepcopy(policy['options']['preparation_requests']))
    return model,program


def development_inputs(model,program,*,label,duration=6):
    """Save complete current inputs/runtime before a development invocation."""
    folder=ROOT/'.work/26-online-development'/(label+'-'+uuid4().hex);folder.mkdir(parents=True,exist_ok=False)
    identity=dict(classification='DEVELOPMENT_ENGINEERING_TEST_NOT_FROZEN_CAPTURE_OR_RESEARCH_TRIAL',
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        source_files={p.relative_to(ROOT).as_posix():sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'src').rglob('*.py'))},
        executable=sys.executable,python=sys.version,duration_s=duration,maximum_step_s=.01)
    (folder/'attempt.json').write_text(json.dumps(identity,indent=2)+'\n',encoding='utf-8')
    for name,value in (('model.json',model),('dispatch-program.json',program)):
        (folder/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    for name,expected in identity['source_files'].items():
        raw=(ROOT/name).read_bytes();assert sha256(raw).hexdigest()==expected
        snapshot=folder/'runtime-source'/name;snapshot.parent.mkdir(parents=True,exist_ok=True);snapshot.write_bytes(raw)
    tools={p.name:sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),ROOT/'tests/test_evidence_consistent_policy.py',
        ROOT/'tests/test_dispatch_policy.py',ROOT/'tests/test_action_value.py',ROOT/'tests/test_verified_closure.py')}
    for name in tools:
        destination=folder/'test-tools'/name;destination.parent.mkdir(exist_ok=True);destination.write_bytes((ROOT/'tests'/name).read_bytes())
    (folder/'test-tools.json').write_text(json.dumps(tools,indent=2)+'\n',encoding='utf-8')
    return folder


def development_run(model,program,*,label,duration=6):
    """Retain each actual development call and its identity, including failures."""
    folder=development_inputs(model,program,label=label,duration=duration)
    terminal=dict(status='STARTED',physical_attempts=1)
    try:
        result=simulate_scenario(model,duration_s=duration,step_s=.01,dispatch_program=program)
        save_run(result,folder/'original')
        terminal.update(status='PHYSICAL_CALL_COMPLETED_NOT_TEST_ACCEPTANCE',result_source=result['code_identity'])
    except Exception as error:
        terminal.update(status='FAILED',error_type=type(error).__name__,error=str(error));raise
    finally:
        (folder/'terminal.json').write_text(json.dumps(terminal,indent=2)+'\n',encoding='utf-8')
        print('development_original '+str(folder),flush=True)
    return result


class EvidenceConsistentExecutionTests(unittest.TestCase):
    def test_v4_cli_preserves_the_real_run_and_refuses_overwriting_its_original_output(self):
        model,program=online_fixture();folder=development_inputs(model,program,label='candidate-cli')
        output=folder/'original';command=[sys.executable,'-B','-X','utf8','-m','aegis_dc','simulate',
            '--model',str(folder/'model.json'),'--dispatch-program',str(folder/'dispatch-program.json'),
            '--duration','6','--step','.01','--output',str(output)]
        env=dict(os.environ,PYTHONPATH=str(ROOT/'src'))
        (folder/'terminal.json').write_text(json.dumps(dict(status='STARTED_CLI_OUTCOME_PENDING',public_cli_invocations=1,argv=command),indent=2)+'\n',encoding='utf-8')
        completed=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True)
        (folder/'stdout.txt').write_text(completed.stdout,encoding='utf-8')
        (folder/'stderr.txt').write_text(completed.stderr,encoding='utf-8')
        terminal=dict(status='PHYSICAL_CALL_COMPLETED_NOT_TEST_ACCEPTANCE' if completed.returncode==0 else 'FAILED',
            public_cli_invocations=1,returncode=completed.returncode,argv=command)
        (folder/'terminal.json').write_text(json.dumps(terminal,indent=2)+'\n',encoding='utf-8')
        print('development_original '+str(folder),flush=True)
        self.assertEqual(completed.returncode,0,completed.stderr)
        result=json.loads((output/'run.json').read_bytes())
        self.assertEqual(result['dispatch_interface'],'PUBLIC_SELECTION_WITH_PRIVATE_EXECUTION')
        self.assertEqual([r['choice']['chosen_candidate_id'] for r in result['policy_public_decisions']],['first-inspection',None,'first-action',None])
        self.assertEqual(result['policy_public_resource_ledger']['spent_or_reserved'],dict(person_s=20,tool_s=20,cost=2))
        before={p.name:sha256(p.read_bytes()).hexdigest() for p in output.iterdir()}
        rejected_folder=development_inputs(model,program,label='candidate-cli-overwrite-refused')
        (rejected_folder/'terminal.json').write_text(json.dumps(dict(status='STARTED_CLI_OUTCOME_PENDING',public_cli_invocations=1,argv=command),indent=2)+'\n',encoding='utf-8')
        rejected=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True)
        (rejected_folder/'stdout.txt').write_text(rejected.stdout,encoding='utf-8')
        (rejected_folder/'stderr.txt').write_text(rejected.stderr,encoding='utf-8')
        (rejected_folder/'terminal.json').write_text(json.dumps(dict(status='REJECTED_EXISTING_OUTPUT',public_cli_invocations=1,
            returncode=rejected.returncode,argv=command,original_directory=output.relative_to(ROOT).as_posix()),indent=2)+'\n',encoding='utf-8')
        print('development_original '+str(rejected_folder),flush=True)
        self.assertNotEqual(rejected.returncode,0)
        self.assertIn('Output directory already exists',rejected.stderr)
        self.assertEqual({p.name:sha256(p.read_bytes()).hexdigest() for p in output.iterdir()},before)

    def test_closest_v4_baseline_uses_the_same_public_profiles_and_only_arrived_closure_feedback(self):
        from test_verified_closure import fixture as closure_fixture
        model,program=online_fixture('one_observation_lookahead');_,closure,registry,_=closure_fixture()
        closure['intervention_feedback']=[];closure['intervention_declaration']=deepcopy(program['intervention_program'])
        nominal=program['nominal_knowledge']['id']
        closure['profile']['nominal_knowledge_id']=nominal;closure['risk_catalog']['nominal_knowledge_id']=nominal
        closure['belief_model']['scope']['nominal_knowledge_id']=nominal
        rule=closure['profile']['rules'][0];rule.update(task_id='lookahead-action',operation_id=program['intervention_program']['bindings'][0]['operation_id'])
        rule['checks'][0].update(source_ids=['portable-intake-meter'],accepted_interval=[.07,.08])
        for field in ('sources','observables'):
            known={r['id'] for r in program['evidence_ledger'][field]}
            program['evidence_ledger'][field].extend(deepcopy(r) for r in registry[field] if r['id'] not in known)
        program['closure_program']=closure
        result=development_run(model,program,label='closest-baseline-closure')
        decisions=result['policy_public_decisions']
        self.assertEqual([r['choice']['chosen_candidate_id'] for r in decisions],['first-inspection',None,'first-action',None])
        self.assertEqual([r['completed_at_s'] for r in result['work_records']],[2.25,4])
        self.assertEqual(decisions[2]['choice']['question_lifecycle']['questions'][0]['status'],'OPEN_UNCONFIRMED')
        question=decisions[3]['choice']['question_lifecycle']['questions'][0]
        self.assertEqual(question['status'],'ACTION_COMPLETED_PENDING_VERIFICATION')
        self.assertFalse(question['risk_closed'])
        self.assertEqual(result['policy_public_resource_ledger']['spent_or_reserved'],dict(person_s=20,tool_s=20,cost=2))
        self.assertEqual(result['summary']['worker_work_person_s'],2)
        self.assertEqual(result['summary']['service_deficit_time_s'],4.5)
        for decision in decisions:
            self.assertEqual(decision['choice']['valuation_mass_basis'],'EXACT_FINITE_PUBLIC_BELIEF_CONTEXT_V1')

    def test_online_constant_report_law_can_prefer_direct_action_without_claiming_information_gain(self):
        model,program=online_fixture();options=program['policy_program']['options']
        for variant in options['belief_model']['variants']:
            variant['positive_likelihood']['lookahead-flow-channel']=[.5,.5,.5,.5]
        for variant in options['value_model']['question_models'][0]['variants']:
            variant['positive_likelihood']=dict.fromkeys(variant['positive_likelihood'],.5)
        result=development_run(model,program,label='constant-report-direct')
        choices=[r['choice'] for r in result['policy_public_decisions']]
        self.assertEqual([c['chosen_candidate_id'] for c in choices],['first-action',None,None,None])
        self.assertEqual(choices[0]['prospective_evidence_audit'][0]['classification'],'INFORMATIVE_COMPATIBLE_WITH_DECLARED_UPDATER')
        plans={p['kind']:p for p in choices[0]['forecast_plans'][0]['alternatives']}
        self.assertAlmostEqual(plans['direct_intervention']['expected_service_deficit_s'],17/16)
        self.assertEqual(plans['inspect_then_act']['expected_service_deficit_s'],1.5)
        self.assertEqual(result['work_records'][0]['completed_at_s'],2.25)
        self.assertEqual(result['inspection_public_snapshot']['records'],[])
        self.assertEqual(result['summary']['worker_work_person_s'],1)
        self.assertEqual(result['policy_public_resource_ledger']['spent_or_reserved'],dict(person_s=10,tool_s=10,cost=1))

    def test_online_zero_modeled_impairment_allows_defer_without_creating_a_tour(self):
        model,program=online_fixture()
        for variant in program['policy_program']['options']['belief_model']['variants']:variant['prior']=[.5,0,.25,.25]
        result=development_run(model,program,label='zero-modeled-deficit-defer')
        self.assertEqual([r['choice']['chosen_candidate_id'] for r in result['policy_public_decisions']],[None]*4)
        self.assertTrue(all(not r['choice']['generated_tour'] for r in result['policy_public_decisions']))
        self.assertEqual(result['work_records'],[])
        self.assertEqual(result['inspection_public_snapshot']['records'],[])
        self.assertEqual(result['intervention_private_audit']['events'],[])
        self.assertEqual(result['summary']['worker_work_person_s'],0)
        self.assertEqual(result['policy_public_resource_ledger']['spent_or_reserved'],dict(person_s=0,tool_s=0,cost=0))
        self.assertEqual(result['summary']['service_deficit_time_s'],4.5)

    def test_known_pending_fixed_report_keeps_the_contingent_value_unknown_but_direct_work_defined(self):
        model,program=online_fixture(period=1);program['decision_times_s']=[1]
        result=development_run(model,program,label='known-pending-fixed')
        decision=result['policy_public_decisions'][0];choice=decision['choice']
        self.assertEqual(choice['chosen_candidate_id'],'first-action')
        self.assertEqual(choice['prospective_evidence_audit'][0]['classification'],'UNMODELED')
        self.assertIn('BACKGROUND_ARRIVAL_JOINT_LAW_UNMODELED',choice['prospective_evidence_audit'][0]['reasons'])
        plans={p['kind']:p for p in choice['forecast_plans'][0]['alternatives']}
        self.assertIsNone(plans['inspect_then_act']['expected_service_deficit_s'])
        self.assertTrue(plans['direct_intervention']['eligible'])
        self.assertTrue(plans['defer']['eligible'])
        self.assertEqual(result['work_records'][0]['completed_at_s'],2.25)
        self.assertEqual(result['intervention_private_audit']['events'][0]['applied_at_s'],2.25)
        self.assertEqual(result['inspection_public_snapshot']['records'],[])
        self.assertEqual([r['polled_at_s'] for r in result['policy_sensor_private_audit']],[0,1,2,3,4,5,6])
        self.assertEqual(result['summary']['service_deficit_time_s'],4.5)

    def test_actual_unsuitable_measurement_remains_missing_in_spite_of_the_forecast_support_domain(self):
        model,program=online_fixture()
        program['inspection_program']['profile']['bindings'][0]['condition_range']=[0,.01]
        program['policy_program']['evidence_projection']['inspection_profile']=deepcopy(program['inspection_program']['profile'])
        result=development_run(model,program,label='actual-unsuitable')
        decisions=result['policy_public_decisions']
        self.assertEqual(decisions[0]['choice']['chosen_candidate_id'],'first-inspection')
        self.assertEqual(decisions[0]['choice']['prospective_evidence_audit'][0]['forecast_assumption'],
            'EVERY_MODELED_OUTCOME_COMPLETES_SUITABLY_AT_DECLARED_TIME_WITH_DECISIVE_BINARY_REPORT')
        reading=next(r for r in decisions[2]['frame']['evidence']['records'] if r['id']=='post-clean-flow')
        self.assertEqual((reading['observed_at_s'],reading['arrived_at_s']),(2.25,2.75))
        self.assertIsNone(reading['value'])
        self.assertEqual(reading['availability'],'missing')
        self.assertEqual(reading['quality']['status'],'unknown')
        self.assertEqual(reading['provenance']['origin_id'],'post-clean-flow')
        self.assertEqual(result['inspection_private_audit']['events'][0]['disposition'],'CONDITION_OUTSIDE_DECLARED_RANGE')
        self.assertEqual(result['inspection_public_feedback'][0]['confirmation'],'UNCONFIRMED')
        self.assertFalse(result['inspection_public_feedback'][0]['current_confirmation'])
        self.assertEqual(decisions[2]['choice']['chosen_candidate_id'],'first-action')
        self.assertFalse(result['intervention_public_feedback'][0]['risk_closed'])

    def test_online_v4_inherits_the_public_action_declaration_and_task_kind_gates(self):
        for mismatch,reason in (('action','Policy and actual executor must share the same public intervention declaration'),
            ('kind','Declared policy intention kind differs from its execution binding')):
            model,program=online_fixture();program['decision_times_s']=[0]
            if mismatch=='action':
                program['policy_program']['intervention_declaration']['bindings'][0]['setting']=3
            else:program['policy_program']['candidates'][0]['kind']='intervene'
            with self.subTest(mismatch=mismatch),self.assertRaisesRegex(ValueError,reason):
                development_run(model,program,label='inherited-'+mismatch,duration=.01)

    def test_online_v4_rejects_public_projection_profile_mismatch_before_deciding(self):
        for name in ('one_observation_lookahead','evidence_consistent_contingent'):
            for mismatch in ('inspection','background','background-null','actual-background-null'):
                model,program=online_fixture(name);program['decision_times_s']=[0]
                projection=program['policy_program']['evidence_projection']
                if mismatch=='inspection':projection['inspection_profile']['source_note']='Different public inspection declaration.'
                elif mismatch=='background':projection['background_sensor_profile']['measurements'][0]['period_s']=11
                elif mismatch=='background-null':projection['background_sensor_profile']=None
                else:program['sensor_program']=None
                with self.subTest(policy=name,mismatch=mismatch),self.assertRaisesRegex(ValueError,'Projection public profiles must match the actual execution declarations'):
                    development_run(model,program,label='profile-mismatch-'+mismatch,duration=.01)

    def test_v4_candidate_checks_and_acts_with_live_sparse_sensors_on_one_facility_clock(self):
        model,program=online_fixture()
        result=development_run(model,program,label='first-online')
        decisions=result['policy_public_decisions']
        self.assertEqual([d['choice']['chosen_candidate_id'] for d in decisions],['first-inspection',None,'first-action',None])
        self.assertEqual([d['frame']['as_of_s'] for d in decisions],[1,2.5,2.75,4.5])
        fixed=[r for r in decisions[0]['frame']['evidence']['records'] if r['source_id']=='rectifier-meter-record']
        self.assertEqual([(r['observed_at_s'],r['arrived_at_s']) for r in fixed],[(0,.5)])
        self.assertEqual(len(result['policy_sensor_private_audit']),1)
        self.assertEqual(result['policy_sensor_private_audit'][0]['poll_index'],0)
        self.assertEqual([r['completed_at_s'] for r in result['work_records']],[2.25,4])
        self.assertEqual([r['work_started_at_s'] for r in result['work_records']],[1.25,3])
        handheld=[r for r in decisions[2]['frame']['evidence']['records'] if r['source_id']=='portable-intake-meter'][0]
        self.assertEqual((handheld['observed_at_s'],handheld['arrived_at_s']),(2.25,2.75))
        self.assertEqual(handheld['provenance']['origin_id'],'post-clean-flow')
        self.assertAlmostEqual(handheld['value']**2,1/340)
        self.assertFalse(any(r['source_id']=='portable-intake-meter' for r in decisions[1]['frame']['evidence']['records']))
        effect=result['intervention_private_audit']['events'][0]
        self.assertEqual((effect['applied_at_s'],effect['old_value'],effect['new_value']),(4,4,2))
        self.assertEqual((result['intervention_public_feedback'][0]['observed_at_s'],result['intervention_public_feedback'][0]['arrived_at_s']),(4,4.5))
        self.assertFalse(result['intervention_public_feedback'][0]['risk_closed'])
        self.assertEqual(result['summary']['demand_service_unit_s'],6)
        self.assertEqual(result['summary']['delivered_service_unit_s'],1.5)
        self.assertEqual(result['summary']['service_deficit_time_s'],4.5)
        self.assertEqual(result['summary']['worker_work_person_s'],2)
        self.assertEqual(result['policy_public_resource_ledger']['spent_or_reserved'],dict(person_s=20,tool_s=20,cost=2))
        self.assertEqual(result['dispatch_interface'],'PUBLIC_SELECTION_WITH_PRIVATE_EXECUTION')
        self.assertEqual(decisions[0]['choice']['forecast_window_s'],[1,7])


if __name__=='__main__':unittest.main()
