"""Physical intervention behavior through the public full-facility run seam."""
from copy import deepcopy
import json
import math
from pathlib import Path
import unittest
from aegis_dc.decision_view import DecisionGateway
from aegis_dc.plant import simulate_scenario
from aegis_dc.scenario import load_scenario

ROOT=Path(__file__).resolve().parents[1]

def fixture(kind='restore_network_capacity',setting=1):
    scenario=load_scenario(ROOT/'configs/full-facility-mainline-reserve-v6.json')
    for row in scenario['parameters']:
        if row['id'] in {'walk_short','inspection_time'}:row['value']=1
        elif row['id']=='walk_long':row['value']=2
        elif row['id']=='network_service_capacity':row['value']=.25
    folder=ROOT/'configs/full-facility-decision-v1'
    nominal=json.loads((folder/'public-nominal.json').read_bytes());ledger=json.loads((folder/'common-ledger.json').read_bytes())
    plan=dict(schema='aegisdc-public-preparation-plan-v1',id='intervention23',basis='synthetic_assumption',time_unit='s',decision_times_s=[0],requests=[])
    frame=DecisionGateway(nominal,ledger,plan).next_frame();p={r['id']:r['value'] for r in scenario['parameters']}
    timing=dict(schema='aegisdc-workforce-profile-v1',id='23-scaled-engineering',facility_id=scenario['id'],nominal_knowledge_id=nominal['id'],
        basis='synthetic_assumption',source_note='Positive legal scaled engineering timing; no site calibration.',time_unit='s',access_check_s=.25,feedback_latency_s=.5,
        walk_times_s={e['id']:p[e['duration_parameter']] for e in scenario['graphs']['access']},
        work_times_s={w['id']:p[w['duration_parameter']] for d in scenario['domains'] for w in d['work_interfaces']},
        shifts={e['id']:[0,p['shift_end_time']] for e in scenario['entities'] if e['kind']=='worker'})
    task=dict(id='restore-network',work_interface_id='inspect_it_service',target_id='network',
        crew=[dict(worker_id='worker_it',qualification_id='qualified_it_inspection')],tool_carrier_id='worker_it',deadline_s=10,
        source_note='Explicit synthetic authorized repair work, not field certification.')
    work=dict(schema='aegisdc-work-program-v1',id='23-work',profile=timing,submissions=[dict(frame=frame,task=task)])
    operation=dict(id='network-restore',kind=kind,target_id='network',unit='1',minimum_work_s=1,
        source_note='Declared service-capacity repair with a residual ceiling; not a job success oracle.')
    grant=dict(id='research-grant',operation_ids=[operation['id']],target_ids=['network'],starts_at_s=0,expires_at_s=10,
        basis='synthetic_assumption',source_note='Research authority only; not authority over real equipment.')
    profile=dict(schema='aegisdc-intervention-profile-v1',id='23-intervention',facility_id=scenario['id'],nominal_knowledge_id=nominal['id'],
        basis='synthetic_assumption',source_note='Bounded named-operation research authority.',time_unit='s',feedback_latency_s=.5,
        operations=[operation],authorizations=[grant])
    interventions=dict(schema='aegisdc-intervention-program-v1',profile=profile,
        bindings=[dict(task_id=task['id'],operation_id=operation['id'],setting=setting,authorization_id=grant['id'])])
    return scenario,work,interventions

class InterventionExecutionTests(unittest.TestCase):
    def test_actual_completion_restores_capacity_after_costly_work(self):
        scenario,work,actions=fixture()
        result=simulate_scenario(scenario,duration_s=3,step_s=.01,work_program=work,intervention_program=actions)
        effect=result['intervention_private_audit']['events'][0]
        self.assertEqual(effect['applied_at_s'],1.25)
        self.assertEqual(effect['old_value'],.25)
        self.assertEqual(effect['new_value'],1)
        self.assertAlmostEqual(result['summary']['delivered_service_unit_s'],33/16)
        self.assertAlmostEqual(result['summary']['service_deficit_time_s'],15/16)
        self.assertEqual(result['intervention_public_feedback'][0]['arrived_at_s'],1.75)
        before=simulate_scenario(scenario,duration_s=1,step_s=.01,work_program=work,intervention_program=actions)
        self.assertEqual(before['intervention_private_audit']['events'],[])
        self.assertEqual(before['intervention_public_feedback'],[])

    def test_residual_and_failed_operations_preserve_elapsed_service_deficit(self):
        scenario,work,actions=fixture(setting=.5)
        result=simulate_scenario(scenario,duration_s=3,step_s=.01,work_program=work,intervention_program=actions)
        self.assertAlmostEqual(result['summary']['delivered_service_unit_s'],19/16)
        self.assertAlmostEqual(result['summary']['service_deficit_time_s'],29/16)
        for mode in ('aborted','unfinished','expired','minimum-work'):
            s,w,a=fixture()
            kwargs={}
            if mode=='aborted':kwargs['boundary_events']=[dict(time_s=.75,parameter_id='it_access_permit',value=0,source_note='Declared closure during actual work.')]
            elif mode=='unfinished':w['profile']['work_times_s']['inspect_it_service']=4
            elif mode=='expired':a['profile']['authorizations'][0]['expires_at_s']=1.25
            else:a['profile']['operations'][0]['minimum_work_s']=2
            if mode=='unfinished':
                for parameter in s['parameters']:
                    if parameter['id']=='inspection_time':parameter['value']=4
                w['profile']['work_times_s']={key:4 for key in w['profile']['work_times_s']}
            with self.subTest(mode=mode):
                r=simulate_scenario(s,duration_s=3,step_s=.01,work_program=w,intervention_program=a,**kwargs)
                self.assertAlmostEqual(r['summary']['delivered_service_unit_s'],3/4)
                self.assertAlmostEqual(r['summary']['service_deficit_time_s'],9/4)
                self.assertFalse(any(e['outcome']=='APPLIED' for e in r['intervention_private_audit']['events']))
                self.assertTrue(all(not e['risk_closed'] for e in r['intervention_public_feedback']))

    def test_filter_cleaning_applies_declared_residual_resistance_only_after_work(self):
        scenario,work,actions=fixture('clean_filter',2)
        for parameter in scenario['parameters']:
            if parameter['id']=='filter_resistance_multiplier':parameter['value']=4
        task=work['submissions'][0]['task'];task.update(target_id='filter',work_interface_id='inspect_facility_cooling',
            crew=[dict(worker_id='worker_cooling',qualification_id='qualified_cooling_inspection')],tool_carrier_id='worker_cooling')
        actions['profile']['operations'][0]['target_id']='filter'
        actions['profile']['authorizations'][0]['target_ids']=['filter']
        result=simulate_scenario(scenario,duration_s=4,step_s=.01,work_program=work,intervention_program=actions)
        event=result['intervention_private_audit']['events'][0]
        self.assertEqual((event['applied_at_s'],event['old_value'],event['new_value']),(3.25,4,2))
        first=result['trace'][0]['domains']['facility_cooling']['lake_pump']['volume_flow_m3_s']
        after=next(row for row in result['trace'] if row['time_s']==3.25)['domains']['facility_cooling']['lake_pump']['volume_flow_m3_s']
        self.assertAlmostEqual(first,math.sqrt(1/340))
        self.assertAlmostEqual(after,math.sqrt(1/180))
        self.assertLess(after,.1) # Residual is not the nominal fully clean loop.
        self.assertLessEqual(result['summary']['max_mass_residual_kg'],1e-9)

    def test_compute_request_adjustment_changes_actual_power_heat_and_service_not_demand(self):
        scenario,work,actions=fixture('adjust_compute_request',1000000)
        for parameter in scenario['parameters']:
            if parameter['id']=='network_service_capacity':parameter['value']=1
        task=work['submissions'][0]['task'];task['target_id']='compute'
        operation=actions['profile']['operations'][0];operation.update(target_id='compute',unit='W')
        actions['profile']['authorizations'][0]['target_ids']=['compute']
        result=simulate_scenario(scenario,duration_s=3,step_s=.01,work_program=work,intervention_program=actions)
        event=result['intervention_private_audit']['events'][0]
        self.assertEqual((event['applied_at_s'],event['old_value'],event['new_value']),(1.25,2000000,1000000))
        before=result['trace'][0]['domains']['power']['actual_powers_W']['compute']
        after=next(row for row in result['trace'] if row['time_s']==1.25)['domains']['power']['actual_powers_W']['compute']
        self.assertEqual((before,after),(2000000,1000000))
        self.assertEqual(result['summary']['demand_service_unit_s'],3)
        self.assertAlmostEqual(result['summary']['delivered_service_unit_s'],17/8)
        self.assertAlmostEqual(result['summary']['service_deficit_time_s'],7/8)
        self.assertLess(abs(result['summary']['whole_run_energy_residual_J']),1e-4)

    def test_backup_request_retains_paid_controller_sample_and_transfer_delay(self):
        scenario,work,actions=fixture('request_backup_cooling',1)
        task=work['submissions'][0]['task'];task.update(target_id='backup_tower',work_interface_id='inspect_backup',
            crew=[dict(worker_id='worker_electrical',qualification_id='qualified_electrical_inspection')],tool_carrier_id='worker_electrical')
        actions['profile']['operations'][0]['target_id']='backup_tower'
        actions['profile']['authorizations'][0]['target_ids']=['backup_tower']
        result=simulate_scenario(scenario,duration_s=6.25,step_s=.01,work_program=work,intervention_program=actions)
        self.assertEqual(result['intervention_private_audit']['events'][0]['applied_at_s'],3.5)
        points={r['time_s']:r for r in result['trace']}
        self.assertEqual(points[3.5]['domains']['backup']['backup_tower_mode'],'primary')
        state=points[4]['domains']['backup']['reserve_states']['cooling']
        self.assertEqual((state['mode'],state['requested_at_s'],state['ready_at_s']),('switching',4,6))
        self.assertEqual(points[6]['domains']['backup']['backup_tower_mode'],'active')
        self.assertEqual(result['summary']['backup_fan_energy_J'],5000)
        self.assertGreater(result['summary']['backup_water_heat_J'],0)
        self.assertLess(abs(result['summary']['whole_run_energy_residual_J']),1e-4)

    def test_public_proposal_refuses_static_setting_domains_before_any_physical_query(self):
        from aegis_dc.intervention_execution import prepare_intervention
        scenario,work,actions=fixture()
        frame=work['submissions'][0]['frame'];task=work['submissions'][0]['task']
        for setting in (-.1,3,float('inf'),True):
            binding=deepcopy(actions['bindings'][0]);binding['setting']=setting
            with self.subTest(setting=setting),self.assertRaises(ValueError):
                prepare_intervention(frame,work['profile'],task,actions['profile'],binding)
        changed=deepcopy(actions['profile']);changed['operations'][0]['minimum_work_s']=2
        assessment=prepare_intervention(frame,work['profile'],task,changed,actions['bindings'][0])
        self.assertFalse(assessment['legal_for_planning'])
        self.assertIn('declared_professional_work_too_short',assessment['public_reasons'])
        bad=deepcopy(actions['profile']);bad['authorizations'][0]['operation_ids']=[{}]
        with self.assertRaises(ValueError):prepare_intervention(frame,work['profile'],task,bad,actions['bindings'][0])

if __name__=='__main__':unittest.main()
