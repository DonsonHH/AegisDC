"""Real inspection completion through the same full facility run interface."""
from copy import deepcopy
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest
from aegis_dc.decision_view import DecisionGateway
from aegis_dc.plant import simulate_scenario
from aegis_dc.scenario import load_scenario

ROOT=Path(__file__).resolve().parents[1]
def fixture():
    scenario=load_scenario(ROOT/'configs/full-facility-mainline-reserve-v6.json')
    for p in scenario['parameters']:
        if p['id'] in {'walk_short','inspection_time'}:p['value']=1
        elif p['id']=='walk_long':p['value']=2
    public=ROOT/'configs/full-facility-decision-v1'
    nominal=json.loads((public/'public-nominal.json').read_bytes())
    ledger=json.loads((public/'common-ledger.json').read_bytes())
    plan=dict(schema='aegisdc-public-preparation-plan-v1',id='inspection22',basis='synthetic_assumption',time_unit='s',decision_times_s=[0],requests=[])
    frame=DecisionGateway(nominal,ledger,plan).next_frame()
    params={p['id']:p['value'] for p in scenario['parameters']}
    wp=dict(schema='aegisdc-workforce-profile-v1',id='scaled22',facility_id=scenario['id'],nominal_knowledge_id=nominal['id'],basis='synthetic_assumption',source_note='Declared legal short engineering timing, not site data.',time_unit='s',access_check_s=.25,feedback_latency_s=.5,walk_times_s={e['id']:params[e['duration_parameter']] for e in scenario['graphs']['access']},work_times_s={w['id']:params[w['duration_parameter']] for d in scenario['domains'] for w in d['work_interfaces']},shifts={e['id']:[0,params['shift_end_time']] for e in scenario['entities'] if e['kind']=='worker'})
    task=dict(id='inspect-flow',work_interface_id='inspect_facility_cooling',target_id='internal_pump',crew=[dict(worker_id='worker_cooling',qualification_id='qualified_cooling_inspection')],tool_carrier_id='worker_cooling',deadline_s=10,source_note='Actual timed flow inspection, no repair.')
    work=dict(schema='aegisdc-work-program-v1',id='work22',profile=wp,submissions=[dict(frame=frame,task=task)])
    nonfixed=json.loads((ROOT/'configs/full-facility-nonfixed-evidence-v1.json').read_bytes())
    nonfixed['registry']['id']='inspection22-ledger'
    nonfixed['registry']['sources'].append(dict(id='handheld-flow-meter',kind='handheld',basis='synthetic_assumption',target_ids=['internal_pump'],observable_ids=['flow'],dependency_group='portable-flow-chain',source_note='Synthetic portable meter bound to existing physical flow tool.'))
    nonfixed['models'].append(dict(source_id='handheld-flow-meter',target_id='internal_pump',observable_id='flow',instrument_id='portable-flow-meter',model=dict(schema='aegisdc-handheld-model-v1',id='portable-flow',kind='numeric',signal_id='internal_pump.volume_flow',unit='m3/s',reported_error_bound=.001,quality_note='Declared synthetic error bound; not field calibration.',basis='synthetic_assumption',source_note='Portable flow measurement, finite engineering model.')))
    binding=dict(task_id=task['id'],model_id='portable-flow',tool_id='tool_flow_meter',qualification_id='qualified_cooling_inspection',minimum_work_s=1,condition_range=[0,10],confirmation_threshold=.5,record_id='flow-inspection-22',arrival_latency_s=.5,validity_s=5,provenance=dict(origin_id='flow-inspection-22',copied_from_record_id=None))
    profile=dict(schema='aegisdc-inspection-profile-v1',id='inspection22-profile',facility_id=scenario['id'],basis='synthetic_assumption',source_note='Declared inspection coverage and suitability.',nonfixed_profile=nonfixed,bindings=[binding])
    ip=dict(schema='aegisdc-inspection-program-v1',profile=profile,realizations={task['id']:dict(seed=22,bias=0,noise_half_width=0)})
    return scenario,work,ip

class InspectionExecutionTests(unittest.TestCase):
    def test_measurement_comes_from_actual_completion_not_dispatch(self):
        scenario,work,inspection=fixture()
        result=simulate_scenario(scenario,duration_s=2,step_s=.01,work_program=work,inspection_program=inspection)
        reading=result['inspection_public_snapshot']['records'][0]
        self.assertEqual(reading['observed_at_s'],1.25)
        self.assertEqual(reading['arrived_at_s'],1.75)
        point=next(r for r in result['trace'] if r['time_s']==1.25)
        self.assertEqual(reading['value'],point['domains']['facility_cooling']['internal_pump']['volume_flow_m3_s'])
        self.assertEqual(reading['target_id'],'internal_pump')
        self.assertEqual(result['inspection_private_audit']['events'][0]['task_status'],'completed')
        before=simulate_scenario(scenario,duration_s=1,step_s=.01,work_program=work,inspection_program=inspection)
        self.assertEqual(before['inspection_public_snapshot']['records'],[])
        self.assertEqual(before['work_records'][0]['status'],'working')

    def test_out_of_condition_is_timed_unconfirmed_not_a_success_or_private_reason(self):
        scenario,work,inspection=fixture()
        inspection['profile']['bindings'][0]['condition_range']=[5,10]
        result=simulate_scenario(scenario,duration_s=2,step_s=.01,work_program=work,inspection_program=inspection)
        record=result['inspection_public_snapshot']['records'][0]
        self.assertIsNone(record['value'])
        self.assertEqual(record['quality']['status'],'unknown')
        self.assertNotIn('CONDITION',record['quality']['note'])
        self.assertEqual(record['observed_at_s'],1.25)
        self.assertEqual(record['arrived_at_s'],1.75)
        self.assertEqual(result['inspection_private_audit']['events'][0]['disposition'],'CONDITION_OUTSIDE_DECLARED_RANGE')

    def test_professional_threshold_confirmation_is_separate_from_arrival_and_reading(self):
        scenario,work,inspection=fixture()
        result=simulate_scenario(scenario,duration_s=2,step_s=.01,work_program=work,inspection_program=inspection)
        feedback=result['inspection_public_feedback'][0]
        self.assertEqual(feedback['observed_at_s'],1.25)
        self.assertEqual(feedback['arrived_at_s'],1.75)
        self.assertEqual(feedback['confirmation'],'CONFIRMED_BELOW_THRESHOLD')
        self.assertEqual(feedback['scope'],'NAMED_SIGNAL_THRESHOLD_ONLY_NOT_FAULT_DIAGNOSIS')
        unknown=deepcopy(inspection)
        unknown['profile']['bindings'][0]['confirmation_threshold']=result['inspection_public_snapshot']['records'][0]['value']
        ambiguous=simulate_scenario(scenario,duration_s=2,step_s=.01,work_program=work,inspection_program=unknown)
        self.assertEqual(ambiguous['inspection_public_feedback'][0]['confirmation'],'UNCONFIRMED')
        unfinished=simulate_scenario(scenario,duration_s=1,step_s=.01,work_program=work,inspection_program=inspection)
        self.assertEqual(unfinished['inspection_public_feedback'],[])
        self.assertEqual(unfinished['inspection_private_audit']['attempts'][0]['task_status'],'working')

    def test_actual_signal_changes_during_work_and_only_completion_value_is_used(self):
        scenario,work,inspection=fixture()
        event=dict(time_s=.75,parameter_id='internal_pump_pressure_rise',value=0,source_note='Declared engineering change during real inspection.')
        run=simulate_scenario(scenario,duration_s=2,step_s=.01,work_program=work,inspection_program=inspection,boundary_events=[event])
        before=next(r for r in run['trace'] if r['time_s']==0)['domains']['facility_cooling']['internal_pump']['volume_flow_m3_s']
        final=run['inspection_public_snapshot']['records'][0]['value']
        self.assertLess(final,before)
        self.assertEqual(final,next(r for r in run['trace'] if r['time_s']==1.25)['domains']['facility_cooling']['internal_pump']['volume_flow_m3_s'])

    def test_abort_at_completion_instant_prevents_measurement(self):
        scenario,work,inspection=fixture()
        # Same professional/tool, but measured target is inside the IT access zone.
        work['submissions'][0]['task']['work_interface_id']='inspect_equipment_environment'
        work['submissions'][0]['task']['target_id']='immersion'
        binding=inspection['profile']['bindings'][0]
        binding.update(model_id='coolant-numeric',condition_range=[250,400],confirmation_threshold=305)
        event=dict(time_s=3.5,parameter_id='it_access_permit',value=0,source_note='Closure exactly when the real work would complete.')
        result=simulate_scenario(scenario,duration_s=4,step_s=.01,work_program=work,inspection_program=inspection,boundary_events=[event])
        self.assertEqual(result['inspection_public_snapshot']['records'],[])
        self.assertEqual(result['work_records'][0]['status'],'aborted')
        self.assertEqual(result['inspection_private_audit']['events'][0]['task_status'],'aborted')

    def test_qualification_wrong_tool_and_unmeasured_target_cannot_make_readings(self):
        scenario,work,inspection=fixture()
        work['submissions'][0]['task']['crew']=[dict(worker_id='worker_it',qualification_id='qualified_it_inspection')]
        work['submissions'][0]['task']['tool_carrier_id']='worker_it'
        refused=simulate_scenario(scenario,duration_s=.5,step_s=.01,work_program=work,inspection_program=inspection)
        self.assertEqual(refused['inspection_public_snapshot']['records'],[])
        self.assertEqual(refused['inspection_private_audit']['events'][0]['task_status'],'rejected')
        for change in ('tool','target','qualification'):
            scenario,work,inspection=fixture()
            binding=inspection['profile']['bindings'][0]
            if change=='tool':binding['tool_id']='tool_it_diagnostic'
            elif change=='target':work['submissions'][0]['task']['target_id']='filter'
            else:binding['qualification_id']='qualified_it_inspection'
            with self.subTest(change=change),self.assertRaises(ValueError):
                simulate_scenario(scenario,duration_s=.5,step_s=.01,work_program=work,inspection_program=inspection)

    def test_too_short_work_is_not_a_measurement_and_late_validity_is_not_refreshed(self):
        scenario,work,inspection=fixture()
        inspection['profile']['bindings'][0]['minimum_work_s']=2
        result=simulate_scenario(scenario,duration_s=2,step_s=.01,work_program=work,inspection_program=inspection)
        self.assertEqual(result['inspection_public_snapshot']['records'],[])
        self.assertEqual(result['inspection_private_audit']['events'][0]['disposition'],'WORK_INTERVAL_TOO_SHORT')
        scenario,work,inspection=fixture()
        inspection['profile']['bindings'][0].update(arrival_latency_s=1,validity_s=.5)
        late=simulate_scenario(scenario,duration_s=2.5,step_s=.01,work_program=work,inspection_program=inspection)
        row=late['inspection_public_snapshot']['records'][0]
        self.assertEqual(row['observed_at_s'],1.25)
        self.assertEqual(row['valid_until_s'],1.75)
        self.assertEqual(row['arrived_at_s'],2.25)
        self.assertEqual(row['availability'],'expired')

    def test_operator_cli_uses_real_completion_and_refuses_fixture_tokens(self):
        scenario,work,inspection=fixture()
        with tempfile.TemporaryDirectory() as folder:
            paths=[Path(folder)/name for name in ('scenario.json','work.json','inspection.json')]
            for p,v in zip(paths,(scenario,work,inspection)):p.write_text(json.dumps(v),encoding='utf-8')
            cmd=[sys.executable,'-B','-X','utf8','-m','aegis_dc','simulate','--model',str(paths[0]),'--duration','2','--step','.01',
                 '--work-program',str(paths[1]),'--inspection-program',str(paths[2])]
            completed=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(completed.returncode,0,completed.stderr)
            self.assertEqual(json.loads(completed.stdout)['inspection_public_snapshot']['records'][0]['observed_at_s'],1.25)
            inspection['completion_requests']=[dict(status='COMPLETED',completed_at_s=0)]
            paths[2].write_text(json.dumps(inspection),encoding='utf-8')
            refused=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(refused.returncode,2)
            self.assertEqual(refused.stdout,'')
            self.assertNotIn('Traceback',refused.stderr)

    def test_binary_private_realization_cannot_bypass_numeric_model_or_change_public_quality(self):
        scenario,work,inspection=fixture()
        task=work['submissions'][0]['task'];task.update(work_interface_id='inspect_equipment_environment',target_id='immersion')
        b=inspection['profile']['bindings'][0];b.update(model_id='threshold-miss',condition_range=[250,400],confirmation_threshold=290)
        inspection['realizations'][task['id']]['bias']=1
        with self.assertRaises(ValueError):
            simulate_scenario(scenario,duration_s=.5,step_s=.01,work_program=work,inspection_program=inspection)

    def test_public_metadata_carries_professional_timing_and_finite_confirmation_definition(self):
        scenario,work,inspection=fixture()
        run=simulate_scenario(scenario,duration_s=.5,step_s=.01,work_program=work,inspection_program=inspection)
        models=run['inspection_public_models']
        self.assertEqual(models['schema'],'aegisdc-inspection-public-models-v1')
        self.assertEqual(models['bindings'][0]['tool_id'],'tool_flow_meter')
        self.assertEqual(models['bindings'][0]['minimum_work_s'],1)
        self.assertEqual(models['bindings'][0]['confirmation_threshold'],.5)
        self.assertNotIn('realizations',models)
        self.assertNotIn('seed',json.dumps(models))

    def test_threshold_reports_keep_declared_quality_and_numeric_error_is_not_truth(self):
        scenario,work,inspection=fixture()
        inspection['realizations']['inspect-flow'].update(bias=.0005,noise_half_width=0)
        result=simulate_scenario(scenario,duration_s=2,step_s=.01,work_program=work,inspection_program=inspection)
        row=result['inspection_public_snapshot']['records'][0]
        audit=result['inspection_private_audit']['events'][0]
        self.assertAlmostEqual(row['value']-audit['authorized_raw_signal'],.0005)
        self.assertTrue(audit['declared_bound_contains_signal'])
        self.assertNotIn('actual_error',json.dumps(row))
        scenario,work,inspection=fixture()
        work['submissions'][0]['task'].update(work_interface_id='inspect_equipment_environment',target_id='immersion')
        binding=inspection['profile']['bindings'][0]
        binding.update(model_id='threshold-miss',condition_range=[250,400],confirmation_threshold=290)
        result=simulate_scenario(scenario,duration_s=4,step_s=.01,work_program=work,inspection_program=inspection)
        self.assertIs(result['inspection_public_snapshot']['records'][0]['value'],False)
        self.assertEqual(result['inspection_public_feedback'][0]['confirmation'],'UNCONFIRMED')
        # Same output channel and declared note under another private realization.
        inspection['realizations']['inspect-flow']['seed']=999
        changed=simulate_scenario(scenario,duration_s=4,step_s=.01,work_program=work,inspection_program=inspection)
        self.assertEqual(result['inspection_public_snapshot']['records'][0]['quality'],changed['inspection_public_snapshot']['records'][0]['quality'])
        self.assertEqual(result['inspection_public_snapshot']['records'][0]['id'],changed['inspection_public_snapshot']['records'][0]['id'])

    def test_live_session_repeated_snapshots_do_not_resample_and_reject_future(self):
        from aegis_dc.inspection_execution import InspectionSession
        from aegis_dc.workforce_dispatch import CrewWorkforce
        scenario,work,inspection=fixture()
        params={p['id']:p['value'] for p in scenario['parameters']}
        executor=CrewWorkforce(scenario,params,work,2)
        session=InspectionSession(scenario,work,inspection)
        # Currentpoint supplied only by the private evaluator, same authorized signal whitelist.
        for t in (0,.25,1.25):
            executor.process(t,set())
            session.process(t,executor,dict(time_s=t,domains={'facility_cooling':{'internal_pump':{'volume_flow_m3_s':.12}}}))
        self.assertEqual(session.snapshot(1.25)['records'],[])
        for t in (1.75,2):
            executor.process(t,set())
            session.process(t,executor,dict(time_s=t,domains={'facility_cooling':{'internal_pump':{'volume_flow_m3_s':999}}}))
        first=session.snapshot(2)
        self.assertEqual(first,session.snapshot(2))
        self.assertEqual(first['records'][0]['value'],.12)
        self.assertEqual(len(session.private_audit()['events']),1)
        with self.assertRaises(ValueError):session.snapshot(3)
        with self.assertRaises(ValueError):session.public_feedback(float('nan'))
        with self.assertRaises(ValueError):session.snapshot(True)

    def test_no_record_identity_is_claimed_for_insufficient_observation(self):
        scenario,work,inspection=fixture()
        inspection['profile']['bindings'][0]['minimum_work_s']=2
        result=simulate_scenario(scenario,duration_s=2,step_s=.01,work_program=work,inspection_program=inspection)
        self.assertIsNone(result['inspection_private_audit']['attempts'][0]['measurement_record_id'])

    def test_real_record_enters_only_arrived_public_frame_and_belief(self):
        from aegis_dc.evidence_ledger import RECORD_FIELDS
        from aegis_dc.belief import infer_belief
        scenario,work,inspection=fixture()
        work['submissions'][0]['task'].update(work_interface_id='inspect_equipment_environment',target_id='immersion')
        binding=inspection['profile']['bindings'][0]
        binding.update(model_id='coolant-numeric',condition_range=[250,400],confirmation_threshold=305)
        profile=inspection['profile']['nonfixed_profile']
        common=json.loads((ROOT/'configs/full-facility-decision-v1/common-ledger.json').read_bytes())
        for field in ('sources','observables'):
            known={r['id'] for r in profile['registry'][field]}
            profile['registry'][field].extend(r for r in common[field] if r['id'] not in known)
        fixed=json.loads((ROOT/'configs/full-facility-sensor-channels-v1.json').read_bytes())
        for field in ('sources','observables'):
            known={r['id'] for r in profile['registry'][field]}
            profile['registry'][field].extend(r for r in fixed['registry'][field] if r['id'] not in known)
        run=simulate_scenario(scenario,duration_s=4,step_s=.01,work_program=work,inspection_program=inspection)
        reading=run['inspection_public_snapshot']['records'][0]
        ledger=deepcopy(profile['registry']);ledger['records']=[{k:reading[k] for k in RECORD_FIELDS}]
        nominal=work['submissions'][0]['frame']['nominal_knowledge']
        plan=dict(schema='aegisdc-public-preparation-plan-v1',id='22-to18',basis='synthetic_assumption',time_unit='s',decision_times_s=[3.9999999999999996,4],requests=[])
        gateway=DecisionGateway(nominal,ledger,plan)
        before,after=gateway.next_frame(),gateway.next_frame()
        self.assertEqual(before['evidence']['records'],[])
        self.assertEqual(after['evidence']['records'][0]['id'],reading['id'])
        belief=json.loads((ROOT/'configs/full-facility-belief-model-v1.json').read_bytes())
        belief['scope']['ledger_id']=ledger['id']
        self.assertEqual(infer_belief(before,belief)['status'],'PRIOR_PREDICTION')
        self.assertEqual(infer_belief(after,belief)['information_updates'],[reading['id']])

if __name__=='__main__':unittest.main()
