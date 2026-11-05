"""Public facility-run slices for timed heterogeneous crew execution."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from aegis_dc.decision_view import DecisionGateway
from aegis_dc.plant import simulate_scenario
from aegis_dc.scenario import load_scenario
from aegis_dc.workforce_dispatch import prepare_work

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / 'configs/full-facility-mainline-reserve-v6.json'
PUBLIC = ROOT / 'configs/full-facility-decision-v1'

def fixture(times=(0,), records=(), *, scaled=True):
    scenario = load_scenario(MODEL)
    if scaled:
        for parameter in scenario['parameters']:
            if parameter['id'] in {'walk_short','inspection_time'}:parameter['value']=1
            elif parameter['id']=='walk_long':parameter['value']=2
    nominal = json.loads((PUBLIC / 'public-nominal.json').read_bytes())
    ledger = json.loads((PUBLIC / 'common-ledger.json').read_bytes())
    ledger['records'] = list(records)
    plan = dict(schema='aegisdc-public-preparation-plan-v1', id='crew-fixture',
                basis='synthetic_assumption', time_unit='s', decision_times_s=list(times), requests=[])
    gateway = DecisionGateway(nominal, ledger, plan)
    parameters = {p['id']: p['value'] for p in scenario['parameters']}
    profile = dict(schema='aegisdc-workforce-profile-v1', id='V6-crew-engineering',
        facility_id=scenario['id'], nominal_knowledge_id=nominal['id'],
        basis='synthetic_assumption', source_note='Declared engineering timing; not site calibration.',
        time_unit='s', access_check_s=.25 if scaled else 1, feedback_latency_s=.5 if scaled else 2,
        walk_times_s={e['id']: parameters[e['duration_parameter']] for e in scenario['graphs']['access']},
        work_times_s={w['id']: parameters[w['duration_parameter']] for d in scenario['domains'] for w in d['work_interfaces']},
        shifts={e['id']: [0, parameters['shift_end_time']] for e in scenario['entities'] if e['kind']=='worker'})
    return scenario, profile, gateway

def task(identifier='team', crew=('worker_cooling','worker_control'), target='plate_hx'):
    return dict(id=identifier, work_interface_id='inspect_facility_cooling', target_id=target,
        crew=[dict(worker_id=w, qualification_id='qualified_cooling_inspection') for w in crew],
        tool_carrier_id=crew[0], deadline_s=200,
        source_note='Engineering-only work; no repair or measurement result.')

def program(profile, *submissions):
    return dict(schema='aegisdc-work-program-v1', id='crew-program', profile=profile,
                submissions=[dict(frame=f, task=t) for f,t in submissions])

class DispatchWorkforceTests(unittest.TestCase):
    def test_crew_meets_after_travel_then_works_together(self):
        scenario, profile, gateway = fixture()
        result = simulate_scenario(scenario, duration_s=3, step_s=.01,
            work_program=program(profile,(gateway.next_frame(),task())))
        record = result['work_records'][0]
        self.assertEqual(record['status'], 'completed')
        self.assertEqual(record['work_started_at_s'], 1.25)
        self.assertEqual(record['completed_at_s'], 2.25)
        self.assertAlmostEqual(result['summary']['worker_travel_person_s'],1)
        self.assertAlmostEqual(result['summary']['worker_wait_person_s'],1.5)
        self.assertAlmostEqual(result['summary']['access_check_person_s'],.5)
        self.assertAlmostEqual(result['summary']['rendezvous_wait_person_s'],1)
        self.assertAlmostEqual(result['summary']['worker_work_person_s'],2)
        self.assertAlmostEqual(result['summary']['tool_work_tool_s'],1)
        self.assertAlmostEqual(result['summary']['tool_occupation_tool_s'],2.25)
        self.assertEqual(record['effect'],'ENGINEERING_WORK_RECORD_ONLY_NO_REPAIR_OR_EVIDENCE')
        self.assertEqual(result['workforce_public_feedback'][-1]['arrived_at_s'],2.75)

    def test_later_issue_queues_for_shared_tool_without_restarting_plant(self):
        scenario, profile, gateway = fixture((0,.5))
        first=task('first',('worker_cooling',), 'plate_hx')
        second=task('second',('worker_control',), 'internal_water')
        result=simulate_scenario(scenario,duration_s=4,step_s=.01,
            work_program=program(profile,(gateway.next_frame(),first),(gateway.next_frame(),second)))
        records={r['id']:r for r in result['work_records']}
        self.assertEqual(records['first']['completed_at_s'],1.25)
        self.assertEqual(records['second']['issued_at_s'],.5)
        self.assertEqual(records['second']['started_at_s'],1.25)
        self.assertEqual(records['second']['completed_at_s'],3.5)
        self.assertAlmostEqual(records['second']['queue_wait_s'],.75)
        self.assertAlmostEqual(result['summary']['worker_wait_person_s'],1.25)

    def test_hidden_closed_gate_costs_travel_and_feedback_arrives_after_check(self):
        scenario,profile,gateway=fixture();frame=gateway.next_frame()
        intention=task('it-gate',('worker_cooling',),'room')
        intention['work_interface_id']='inspect_equipment_environment'
        closed=deepcopy(scenario)
        for parameter in closed['parameters']:
            if parameter['id']=='it_access_permit':parameter['value']=0
        self.assertTrue(prepare_work(frame,profile,intention)['legal_for_planning'])
        open_run=simulate_scenario(scenario,duration_s=3.5,step_s=.01,work_program=program(profile,(frame,intention)))
        closed_run=simulate_scenario(closed,duration_s=3.5,step_s=.01,work_program=program(profile,(frame,intention)))
        record=closed_run['work_records'][0]
        self.assertEqual(record['status'],'aborted')
        self.assertEqual(record['finished_at_s'],2.5)
        self.assertAlmostEqual(closed_run['summary']['worker_travel_person_s'],2)
        self.assertEqual(closed_run['trace'][-1]['domains']['people_tools_work']['workers']['worker_cooling']['location_id'],'loc_control')
        self.assertEqual(closed_run['workforce_public_feedback'][0]['arrived_at_s'],3)
        self.assertEqual(open_run['work_records'][0]['work_started_at_s'],2.5)
        self.assertTrue(all(r['arrived_at_s']>=3 for r in closed_run['workforce_public_feedback']))

    def test_queued_task_expires_while_worker_is_busy(self):
        scenario,profile,gateway=fixture((0,.5))
        first=task('first',('worker_cooling',))
        second=task('expires',('worker_cooling',),'internal_water');second['deadline_s']=.75
        run=simulate_scenario(scenario,duration_s=1,step_s=.01,
            work_program=program(profile,(gateway.next_frame(),first),(gateway.next_frame(),second)))
        expired=run['work_records'][1]
        self.assertEqual(expired['status'],'rejected')
        self.assertEqual(expired['finished_at_s'],.75)
        self.assertEqual(expired['reason'],'deadline_expired_in_queue')

    def test_nominal_qualification_rejection_has_no_movement(self):
        scenario,profile,gateway=fixture();frame=gateway.next_frame()
        intention=task('unqualified',('worker_it',))
        self.assertFalse(prepare_work(frame,profile,intention)['legal_for_planning'])
        run=simulate_scenario(scenario,duration_s=.1,step_s=.01,work_program=program(profile,(frame,intention)))
        self.assertEqual(run['work_records'][0]['status'],'rejected')
        self.assertEqual(run['summary']['worker_travel_person_s'],0)
        self.assertEqual(run['summary']['tool_occupation_tool_s'],0)

    def test_later_public_restriction_prevents_only_the_later_intention(self):
        _,_,base=fixture();nominal=base.next_frame()['nominal_knowledge']
        constraint=next(c for c in nominal['reported_constraints'] if c['location_id']=='loc_it')
        report=dict(id='late-access',source_id=constraint['source_id'],target_id=constraint['target_id'],
            observable_id=constraint['observable_id'],unit='1',value=constraint['blocking_value'],
            observed_at_s=.25,arrived_at_s=.5,valid_until_s=2,
            quality=dict(status='reported',error_bound=None,note='Declared remote gate report.'),
            provenance=dict(origin_id='late-access',copied_from_record_id=None))
        scenario,profile,gateway=fixture((0,.5),[report])
        early=task('before',('worker_cooling',),'room');early['work_interface_id']='inspect_equipment_environment'
        late=deepcopy(early);late['id']='after'
        first_frame,second_frame=gateway.next_frame(),gateway.next_frame()
        self.assertTrue(prepare_work(first_frame,profile,early)['legal_for_planning'])
        self.assertFalse(prepare_work(second_frame,profile,late)['legal_for_planning'])
        run=simulate_scenario(scenario,duration_s=.75,step_s=.01,
            work_program=program(profile,(first_frame,early),(second_frame,late)))
        self.assertEqual(run['work_records'][0]['status'],'travelling')
        self.assertEqual(run['work_records'][1]['status'],'rejected')
        self.assertEqual(run['work_records'][1]['public_assessment']['considered_record_ids'],['late-access'])

    def test_duplicate_open_work_is_not_executed_twice(self):
        scenario,profile,gateway=fixture((0,.5))
        run=simulate_scenario(scenario,duration_s=2,step_s=.01,work_program=program(profile,
            (gateway.next_frame(),task('one',('worker_cooling',))),
            (gateway.next_frame(),task('duplicate',('worker_control',)))))
        self.assertEqual(run['work_records'][1]['reason'],'duplicate_open_work')
        self.assertAlmostEqual(run['summary']['worker_work_person_s'],1)

    def test_shift_and_static_route_qualification_refuse_before_movement(self):
        scenario,profile,gateway=fixture();profile['shifts']['worker_control']=[0,1]
        run=simulate_scenario(scenario,duration_s=.25,step_s=.01,
            work_program=program(profile,(gateway.next_frame(),task('too-late',('worker_control',)))))
        self.assertEqual(run['work_records'][0]['reason'],'shift_or_deadline_unavailable')
        self.assertEqual(run['summary']['worker_travel_person_s'],0)

        scenario,profile,gateway=fixture();intention=task('no-route',('worker_cooling',),'loc_electrical')
        intention['work_interface_id']='inspect_space_access'
        run=simulate_scenario(scenario,duration_s=.25,step_s=.01,work_program=program(profile,(gateway.next_frame(),intention)))
        self.assertEqual(run['work_records'][0]['reason'],'static_access_unreachable')
        self.assertEqual(run['summary']['worker_travel_person_s'],0)

    def test_cli_loads_the_same_closed_work_program(self):
        scenario,profile,gateway=fixture()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);model=root/'scenario.json';inputs=root/'program.json'
            model.write_text(json.dumps(scenario),encoding='utf-8')
            inputs.write_text(json.dumps(program(profile,(gateway.next_frame(),task('cli',('worker_cooling',))))),encoding='utf-8')
            command=[sys.executable,'-B','-X','utf8','-m','aegis_dc','simulate','--model',str(model),
                     '--duration','2','--step','.01','--work-program',str(inputs)]
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,env=dict(os.environ,PYTHONPATH=str(ROOT/'src')))
            self.assertEqual(result.returncode,0,result.stderr)
            saved=json.loads(result.stdout)
            self.assertEqual(saved['work_records'][0]['completed_at_s'],1.25)
            self.assertEqual(saved['workforce_public_feedback'][0]['arrived_at_s'],1.75)

    def test_heterogeneous_assistant_and_independent_electrical_work_run_in_parallel(self):
        scenario,profile,gateway=fixture();frame=gateway.next_frame()
        team=task('cooling-control');team['crew'][1]['qualification_id']='qualified_control_inspection'
        electrical=task('electrical',('worker_electrical',),'rectifier')
        electrical['work_interface_id']='inspect_power';electrical['crew'][0]['qualification_id']='qualified_electrical_inspection'
        run=simulate_scenario(scenario,duration_s=3,step_s=.01,work_program=program(profile,(frame,team),(frame,electrical)))
        records={r['id']:r for r in run['work_records']}
        self.assertEqual(records['electrical']['completed_at_s'],1.25)
        self.assertEqual(records['cooling-control']['completed_at_s'],2.25)
        self.assertAlmostEqual(run['summary']['worker_work_person_s'],3)
        self.assertAlmostEqual(run['summary']['tool_work_tool_s'],2)

    def test_specialist_assistant_uses_its_declared_role_while_carrier_qualifies_for_work(self):
        scenario,profile,gateway=fixture();frame=gateway.next_frame()
        team=task('cooling-it',('worker_cooling','worker_it'))
        team['crew'][1]['qualification_id']='qualified_it_inspection'
        self.assertTrue(prepare_work(frame,profile,team)['legal_for_planning'])
        run=simulate_scenario(scenario,duration_s=4,step_s=.01,work_program=program(profile,(frame,team)))
        self.assertEqual(run['work_records'][0]['completed_at_s'],3.5)

    def test_future_submission_is_not_admitted_before_its_issue_frame(self):
        scenario,profile,gateway=fixture((0,1))
        early=gateway.next_frame();late=gateway.next_frame()
        run=simulate_scenario(scenario,duration_s=.75,step_s=.01,
            work_program=program(profile,(early,task('early',('worker_cooling',)))))
        self.assertEqual([r['id'] for r in run['work_records']],['early'])
        with self.assertRaisesRegex(ValueError,'Issue time outside'):
            simulate_scenario(scenario,duration_s=.75,step_s=.01,
                work_program=program(profile,(late,task('future',('worker_control',)))))

    def test_waiting_crew_stops_when_its_occupied_zone_becomes_unsafe(self):
        scenario,profile,gateway=fixture()
        # Two specialists start in different safe zones. The IT worker is already at target.
        intention=task('waiting-safety',('worker_cooling','worker_it'),'room')
        intention['work_interface_id']='inspect_equipment_environment'
        intention['crew'][1]['qualification_id']='qualified_it_inspection'
        run=simulate_scenario(scenario,duration_s=1,step_s=.01,
            work_program=program(profile,(gateway.next_frame(),intention)),
            boundary_events=[dict(time_s=.5,parameter_id='it_access_permit',value=0,
                source_note='Synthetic closure after onsite crew check; private safety only.')])
        record=run['work_records'][0]
        self.assertEqual(record['status'],'aborted')
        self.assertEqual(record['finished_at_s'],.5)
        self.assertEqual(record['reason'],'onsite_safety_stop')
        self.assertEqual(run['workforce_public_feedback'][0]['arrived_at_s'],1)

if __name__ == '__main__':
    unittest.main()
