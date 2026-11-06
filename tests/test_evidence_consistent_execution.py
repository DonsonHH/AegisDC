"""Online candidate behavior through the advancing public facility boundary."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
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


def development_run(model,program,*,label,duration=6):
    """Retain each actual development call and its identity, including failures."""
    folder=ROOT/'.work/26-online-development'/(label+'-'+uuid4().hex);folder.mkdir(parents=True,exist_ok=False)
    identity=dict(classification='DEVELOPMENT_ENGINEERING_TEST_NOT_FROZEN_CAPTURE_OR_RESEARCH_TRIAL',
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        source_files={p.relative_to(ROOT).as_posix():sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'src').rglob('*.py'))},
        executable=sys.executable,python=sys.version,duration_s=duration,maximum_step_s=.01)
    (folder/'attempt.json').write_text(json.dumps(identity,indent=2)+'\n',encoding='utf-8')
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
