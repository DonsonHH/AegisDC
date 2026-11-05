"""Prepare explicit engineering inputs only; never execute a facility run."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
spec=importlib.util.spec_from_file_location('development_fixture',ROOT/'tests/test_intervention_execution.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
from aegis_dc.decision_view import DecisionGateway

def write(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def prepare():
    folder=ROOT/'evidence/mainline/engineering/23-interventions/reference'
    folder.mkdir(exist_ok=False)
    cases=[]
    definitions=[('network-full','restore_network_capacity',1,3),
        ('network-residual','restore_network_capacity',.5,3),
        ('network-aborted','restore_network_capacity',1,3),
        ('filter-later-inspection','clean_filter',2,6),
        ('compute-power','adjust_compute_request',1000000,3),
        ('backup-request','request_backup_cooling',1,6.25),
        ('decimal-completion','restore_network_capacity',1,3),
        ('expired-authority','restore_network_capacity',1,3)]
    expected={
        'network-full':dict(outcome='APPLIED',applied_at_s=1.25,delivered=2.0625,deficit=.9375),
        'network-residual':dict(outcome='APPLIED',applied_at_s=1.25,delivered=1.1875,deficit=1.8125),
        'network-aborted':dict(outcome='NO_EFFECT',reason='actual_work_not_completed',delivered=.75,deficit=2.25),
        'filter-later-inspection':dict(outcome='APPLIED',applied_at_s=3.25,before_flow_squared=1/340,after_flow_squared=1/180,inspection_observed_at_s=5.25,inspection_arrived_at_s=5.75),
        'compute-power':dict(outcome='APPLIED',applied_at_s=1.25,delivered=2.125,deficit=.875,compute_energy_J=4250000),
        'backup-request':dict(outcome='APPLIED',applied_at_s=3.5,controller_request_s=4,backup_ready_s=6,backup_fan_energy_J=5000),
        'decimal-completion':dict(outcome='APPLIED',applied_at_s=1.2,delivered=2.1,deficit=.9),
        'expired-authority':dict(outcome='NO_EFFECT',reason='authorization_unavailable_at_completion',delivered=.75,deficit=2.25)}
    for name,kind,setting,duration in definitions:
        scenario,work,actions=module.fixture(kind,setting)
        task=work['submissions'][0]['task'];op=actions['profile']['operations'][0]
        events=[];inspection=None
        if kind=='clean_filter':
            next(p for p in scenario['parameters'] if p['id']=='filter_resistance_multiplier')['value']=4
            task.update(target_id='filter',work_interface_id='inspect_facility_cooling',
                crew=[dict(worker_id='worker_cooling',qualification_id='qualified_cooling_inspection')],tool_carrier_id='worker_cooling')
            op['target_id']='filter';actions['profile']['authorizations'][0]['target_ids']=['filter']
            later=deepcopy(work['submissions'][0]);frame=later['frame']
            ledger=dict(schema='aegisdc-evidence-ledger-v1',id=frame['evidence']['ledger_id'],facility_id=frame['facility_id'],
                basis='synthetic_assumption',time_unit='s',**frame['evidence']['static_knowledge'],records=[])
            plan=dict(schema='aegisdc-public-preparation-plan-v1',id='post-clean-check',basis='synthetic_assumption',time_unit='s',decision_times_s=[4],requests=[])
            later['frame']=DecisionGateway(frame['nominal_knowledge'],ledger,plan).next_frame()
            later['task'].update(id='verify-intake',target_id='intake_pump');work['submissions'].append(later)
            profile=json.loads((ROOT/'configs/full-facility-nonfixed-evidence-v1.json').read_bytes())
            profile['registry']['id']='post-clean-measurement'
            profile['registry']['sources'].append(dict(id='portable-intake-meter',kind='handheld',basis='synthetic_assumption',
                target_ids=['intake_pump'],observable_ids=['flow'],dependency_group='portable-intake-chain',source_note='Declared synthetic post-action physical flow meter.'))
            profile['models'].append(dict(source_id='portable-intake-meter',target_id='intake_pump',observable_id='flow',instrument_id='flow_meter',
                model=dict(schema='aegisdc-handheld-model-v1',id='intake-flow',kind='numeric',signal_id='intake_pump.volume_flow',unit='m3/s',
                    reported_error_bound=0,quality_note='Zero-error finite engineering witness; not field calibration.',basis='synthetic_assumption',source_note='Independent hydraulic witness.')))
            inspection=dict(schema='aegisdc-inspection-program-v1',profile=dict(schema='aegisdc-inspection-profile-v1',id='post-filter-inspection',
                facility_id=scenario['id'],basis='synthetic_assumption',source_note='Timed actual post-action inspection.',nonfixed_profile=profile,
                bindings=[dict(task_id='verify-intake',model_id='intake-flow',tool_id='tool_flow_meter',qualification_id='qualified_cooling_inspection',
                    minimum_work_s=1,condition_range=[0,1],confirmation_threshold=.08,record_id='post-clean-flow',arrival_latency_s=.5,validity_s=5,
                    provenance=dict(origin_id='post-clean-flow',copied_from_record_id=None))]),realizations={'verify-intake':dict(seed=23,bias=0,noise_half_width=0)})
        elif kind=='adjust_compute_request':
            next(p for p in scenario['parameters'] if p['id']=='network_service_capacity')['value']=1
            task['target_id']='compute';op.update(target_id='compute',unit='W');actions['profile']['authorizations'][0]['target_ids']=['compute']
        elif kind=='request_backup_cooling':
            task.update(target_id='backup_tower',work_interface_id='inspect_backup',
                crew=[dict(worker_id='worker_electrical',qualification_id='qualified_electrical_inspection')],tool_carrier_id='worker_electrical')
            op['target_id']='backup_tower';actions['profile']['authorizations'][0]['target_ids']=['backup_tower']
        if name=='network-aborted':events=[dict(time_s=.75,parameter_id='it_access_permit',value=0,source_note='Frozen synthetic safety closure during work.')]
        if name=='decimal-completion':work['profile']['access_check_s']=.2
        if name=='expired-authority':actions['profile']['authorizations'][0]['expires_at_s']=1.25
        path=folder/(name+'.json')
        write(path,dict(classification='ENGINEERING_ONLY',model=scenario,work_program=work,intervention_program=actions,inspection_program=inspection,boundary_events=events))
        cases.append(dict(id=name,input=path.relative_to(ROOT).as_posix(),duration_s=duration,expected=expected[name]))
    protocol=dict(schema='aegisdc-intervention-engineering-protocol-v1',classification='ENGINEERING_ONLY',ticket='23',
        authoring_tool='scripts/intervention_delivery.py',helper_tool='scripts/inspection_delivery.py',
        input_preparation_tool='scripts/prepare_intervention_inputs.py',input_fixture='tests/test_intervention_execution.py',
        contract='docs/mainline/23-intervention-contract.md',reference_model='configs/full-facility-mainline-reserve-v6.json',
        reference_property='configs/materials/reference-r134a-saturation.json',cases=cases,maximum_step_s=.01,
        declared_physical_runs=8,total_simulated_duration_s=30.25,absolute_tolerance=1e-9,energy_tolerance_J=1e-4,mass_tolerance_kg=1e-9,
        retry_rule='One attempt per frozen case. Stop on failure; preserve all partial files and terminal receipt. No automatic retries. A correction needs a new frozen protocol and directory.',
        durable_root=['attempt.json','attempts.jsonl','checks.json','intervention-data.svg','intervention-architecture.svg'],
        durable_per_case=['run.json','scenario.json','private-state.jsonl','balances.jsonl'],terminal_receipt='receipt.json',
        full_regression='ROOT_INTEGRATED_ONLY',registered_research_trials=0,llm_calls=0,training_calls=0,field_calibration='PENDING',
        interpretation='Literal finite timed-operation, service-integral and conservation checks only. No policy efficacy, scientific gain, verified risk closure or field claim.',
        expectation_basis='Pre-existing independent capacity/power/filter witnesses, explicit backup PLC schedule, and independent decimal review counterexample. Input fixture is engineering preparation, not an independent oracle.')
    write(ROOT/'docs/mainline/23-intervention-engineering-protocol.json',protocol)
    print(json.dumps(dict(prepared_inputs=len(cases),physical_runs=0)))

if __name__=='__main__':prepare()
