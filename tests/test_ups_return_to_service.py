"""One native UPS signal/action slice through the accepted complete-facility seam."""
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import unittest

from aegis_dc.decision_view import DecisionGateway
from aegis_dc.evidence_ledger import EvidenceLedger
from aegis_dc.intervention_execution import prepare_intervention
from aegis_dc.nonfixed_evidence import SavedRunSignals
from aegis_dc.plant import save_run,simulate_scenario
from aegis_dc.scenario import load_scenario

ROOT=Path(__file__).resolve().parents[1]


def fixture():
    scenario=load_scenario(ROOT/'configs/full-facility-mainline-reserve-v6.json')
    for row in scenario['parameters']:
        if row['id'] in {'walk_short','inspection_time'}:row['value']=1
        elif row['id']=='walk_long':row['value']=2
        elif row['id']=='ups_in_service':row['value']=0
    folder=ROOT/'configs/full-facility-decision-v1'
    nominal=json.loads((folder/'public-nominal.json').read_bytes())
    ledger=json.loads((folder/'common-ledger.json').read_bytes())
    plan=dict(schema='aegisdc-public-preparation-plan-v1',id='UPS-A2',basis='synthetic_assumption',time_unit='s',decision_times_s=[0,2,4],requests=[])
    gateway=DecisionGateway(nominal,ledger,plan);frames=[gateway.next_frame() for _ in range(3)]
    p={r['id']:r['value'] for r in scenario['parameters']}
    timing=dict(schema='aegisdc-workforce-profile-v1',id='UPS-A2-timing',facility_id=scenario['id'],nominal_knowledge_id=nominal['id'],
        basis='synthetic_assumption',source_note='Short engineering fixture only;no field timing or observation probability.',time_unit='s',access_check_s=.25,feedback_latency_s=.5,
        walk_times_s={e['id']:p[e['duration_parameter']] for e in scenario['graphs']['access']},
        work_times_s={w['id']:p[w['duration_parameter']] for d in scenario['domains'] for w in d['work_interfaces']},
        shifts={e['id']:[0,p['shift_end_time']] for e in scenario['entities'] if e['kind']=='worker'})
    tasks=[dict(id=name,work_interface_id='inspect_backup',target_id='ups',
        crew=[dict(worker_id='worker_electrical',qualification_id='qualified_electrical_inspection')],tool_carrier_id='worker_electrical',
        deadline_s=10,source_note='Synthetic completed professional work;no real equipment authority.') for name in ('read-before','restore-ups','read-after')]
    work=dict(schema='aegisdc-work-program-v1',id='UPS-A2-work',profile=timing,submissions=[dict(frame=f,task=t) for f,t in zip(frames,tasks)])
    nonfixed=json.loads((ROOT/'configs/full-facility-nonfixed-evidence-v1.json').read_bytes())
    nonfixed['registry']['id']='UPS-A2-ledger'
    nonfixed['registry']['observables'].append(dict(id='ups_in_service',quantity='fraction',value_type='number',unit='1'))
    nonfixed['registry']['sources'].append(dict(id='UPS-status-reader',kind='handheld',basis='synthetic_assumption',target_ids=['ups'],
        observable_ids=['ups_in_service'],dependency_group='UPS-A2-status',source_note='Fixture exact status read;not field accuracy or battery test.'))
    model=dict(schema='aegisdc-handheld-model-v1',id='UPS-state',kind='numeric',signal_id='ups.in_service',unit='1',reported_error_bound=0,
        quality_note='Engineering bit fixture;not a calibrated instrument.',basis='synthetic_assumption',source_note='Read-only native input gate,not remaining energy or service. ')
    nonfixed['models'].append(dict(source_id='UPS-status-reader',target_id='ups',observable_id='ups_in_service',instrument_id='tool_electrical_meter',model=model))
    bindings=[dict(task_id=t['id'],model_id=model['id'],tool_id='tool_electrical_meter',qualification_id='qualified_electrical_inspection',minimum_work_s=1,
        condition_range=[0,1],confirmation_threshold=.5,record_id='record-'+t['id'],arrival_latency_s=.5,validity_s=10,
        provenance=dict(origin_id='UPS-A2-'+t['id'],copied_from_record_id=None)) for t in (tasks[0],tasks[2])]
    inspections=dict(schema='aegisdc-inspection-program-v1',profile=dict(schema='aegisdc-inspection-profile-v1',id='UPS-A2-read',facility_id=scenario['id'],
        basis='synthetic_assumption',source_note='Actual professional completion only.',nonfixed_profile=nonfixed,bindings=bindings),
        realizations={t['id']:dict(seed=20261111,bias=0,noise_half_width=0) for t in (tasks[0],tasks[2])})
    op=dict(id='UPS-return',kind='restore_ups_service',target_id='ups',unit='1',minimum_work_s=1,
        source_note='Synthetic scoped release/restoration authority;does not repair a battery or bypass protection.')
    grant=dict(id='UPS-release',operation_ids=[op['id']],target_ids=['ups'],starts_at_s=0,expires_at_s=10,
        basis='synthetic_assumption',source_note='Declared release for this synthetic UPS task only;not a real maintenance clearance.')
    actions=dict(schema='aegisdc-intervention-program-v1',profile=dict(schema='aegisdc-intervention-profile-v1',id='UPS-A2-restore',facility_id=scenario['id'],
        nominal_knowledge_id=nominal['id'],basis='synthetic_assumption',source_note='Named authorized UPS gate restoration.',time_unit='s',feedback_latency_s=.5,
        operations=[op],authorizations=[grant]),bindings=[dict(task_id=tasks[1]['id'],operation_id=op['id'],setting=1,authorization_id=grant['id'])])
    return scenario,work,inspections,actions


class UPSReturnToServiceTests(unittest.TestCase):
    def test_native_read_restore_authority_and_verification_boundary(self):
        output=os.environ.get('AEGIS_A2_RESULTS_DIR');case_records=[]
        def run(name,s,w,i,a):
            record=dict(case=name,status='ENTERED');case_records.append(record)
            result=simulate_scenario(s,duration_s=6,step_s=.01,work_program=w,inspection_program=i,intervention_program=a)
            self.assertEqual(result['trace'][-1]['time_s'],6)
            record.update(status='COMPLETED',window_s=6,work=[dict(id=t['id'],status=t['status']) for t in result['work_records']],
                readings=[dict(value=r['value'],observed_at_s=r['observed_at_s'],arrived_at_s=r['arrived_at_s']) for r in result['inspection_public_snapshot']['records']],
                actions=result['intervention_public_feedback'])
            if output:save_run(result,Path(output)/name)
            return result
        try:
            s,w,i,a=fixture();original=deepcopy(s)
            valid=run('authorized',s,w,i,a)
            records=valid['inspection_public_snapshot']['records']
            self.assertEqual([(r['value'],r['observed_at_s'],r['arrived_at_s']) for r in records],[(0,1.25,1.75),(1,5.25,5.75)])
            ledger=EvidenceLedger(i['profile']['nonfixed_profile']['registry'])
            for reading in records:ledger.ingest({k:v for k,v in reading.items() if k not in {'age_s','availability'}})
            self.assertEqual(ledger.snapshot(1.5)['records'],[])
            self.assertEqual([r['value'] for r in ledger.snapshot(2)['records']],[0])
            event=valid['intervention_private_audit']['events'][0]
            self.assertEqual((event['parameter_id'],event['old_value'],event['new_value'],event['applied_at_s']),('ups_in_service',0,1,3.25))
            self.assertEqual(valid['intervention_public_feedback'][0]['arrived_at_s'],3.75)
            self.assertTrue(all(not r['risk_closed'] for r in valid['intervention_public_feedback']))
            self.assertEqual(s,original)
            self.assertTrue(all(r['domains']['backup']['ups_energy_J']==18_000_000 for r in valid['trace']))
            self.assertEqual(valid['summary']['demand_service_unit_s'],6)
            with tempfile.TemporaryDirectory() as folder:
                directory=Path(folder)/'saved';save_run(valid,directory)
                sample=dict(completed_at_s=1.25,signal_id='ups.in_service',target_id='ups',facility_id=s['id'])
                reader=SavedRunSignals(directory);first=reader.sample_at(**sample);first['value']=1
                self.assertEqual(reader.sample_at(**sample)['value'],0)
                with self.assertRaises(ValueError):reader.sample_at(**dict(sample,completed_at_s=1.251))
                rows=[json.loads(line) for line in (directory/'private-state.jsonl').read_text().splitlines()]
                next(r for r in rows if r['time_s']==1.25)['domains']['backup']['ups_in_service']=.5
                raw=''.join(json.dumps(r)+'\n' for r in rows).encode();(directory/'private-state.jsonl').write_bytes(raw)
                manifest=json.loads((directory/'run.json').read_bytes());manifest['artifacts']['private-state.jsonl']['sha256']=sha256(raw).hexdigest()
                (directory/'run.json').write_text(json.dumps(manifest),encoding='utf-8')
                with self.assertRaisesRegex(ValueError,'UPS.*0.*1'):SavedRunSignals(directory).sample_at(**sample)
            for mode in ('not-yet-authorized','expired-at-completion','too-short'):
                s,w,i,a=fixture()
                if mode=='not-yet-authorized':a['profile']['authorizations'][0]['starts_at_s']=4
                elif mode=='expired-at-completion':a['profile']['authorizations'][0]['expires_at_s']=3.25
                else:a['profile']['operations'][0]['minimum_work_s']=2
                r=run(mode,s,w,i,a)
                self.assertEqual([x['value'] for x in r['inspection_public_snapshot']['records']],[0,0])
                self.assertTrue(all(x['outcome']=='NO_EFFECT' and not x['risk_closed'] for x in r['intervention_public_feedback']))
            s,w,i,a=fixture()
            for setting in (0,.5,2,True,None,float('inf')):
                binding=dict(a['bindings'][0],setting=setting)
                with self.assertRaises(ValueError):prepare_intervention(w['submissions'][1]['frame'],w['profile'],w['submissions'][1]['task'],a['profile'],binding)
            for setting in (.5,True,2):
                s,w,i,a=fixture();next(r for r in s['parameters'] if r['id']=='ups_in_service')['value']=setting
                with self.assertRaises(ValueError):run('invalid-state-'+str(setting),s,w,i,a)
                case_records[-1]['status']='EXPECTED_INVALID_PHYSICAL_INPUT_REJECTED'
        finally:
            if output:
                Path(output,'metrics.json').write_text(json.dumps(dict(facility_entries=len(case_records),completed_windows=sum(r['status']=='COMPLETED' for r in case_records),
                    completed_simulated_s=sum(r.get('window_s',0) for r in case_records),cases=case_records,
                    public_choice_calls=0,returned_decisions=0,new_model_calls=0,new_research_runs=0),indent=2)+'\n',encoding='utf-8')
