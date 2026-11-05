"""Physical intervention behavior through the public full-facility run seam."""
from copy import deepcopy
import json
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

if __name__=='__main__':unittest.main()
