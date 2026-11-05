"""Frozen policy-interface capture and saved-only delivery verification."""
import argparse
from copy import deepcopy
from html import escape
import json
import math
import os
from pathlib import Path
import sys
from inspection_delivery import git,hashes,require,read,digest,write,durable,unchanged

ROOT=Path(__file__).resolve().parents[1]
PROTOCOL='docs/mainline/25-policy-engineering-protocol.json'
PACKAGE='evidence/mainline/engineering/25-baselines'


def pins(protocol,revision):
    paths=git('ls-tree','-rz','--name-only',revision,'src','tests','configs',PACKAGE+'/development',PACKAGE+'/reference',
        'evidence/mainline/engineering/18-beliefs/capture-01','evidence/mainline/engineering/23-interventions/reference').decode().strip('\0').split('\0')
    inputs=[PROTOCOL,protocol['contract'],protocol['literature_note'],PACKAGE+'/.gitattributes',
        *[n for n in paths if n.startswith(('tests/',PACKAGE+'/', 'configs/full-facility','configs/materials/',
            'evidence/mainline/engineering/18-beliefs/capture-01/','evidence/mainline/engineering/23-interventions/reference/'))
            and '__pycache__' not in n and not n.endswith(('.pyc','.pyo'))]]
    groups=dict(runtime=[n for n in paths if n.startswith('src/') and n.endswith('.py')],
        tools=[protocol['authoring_tool'],protocol['helper_tool'],protocol['input_preparation_tool']],inputs=inputs)
    return {role:hashes(revision,names) for role,names in groups.items()}


def declared(protocol):
    return set(protocol['durable_root'])|{c['id']+'/'+n for c in protocol['cases'] for n in protocol['durable_case']}


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def check_case(folder,case,protocol):
    path=folder/case['id'];run=read(path/'run.json');expected=case['expected'];inputs=read(ROOT/case['input'])
    trace=rows(path/'private-state.jsonl');balances=rows(path/'balances.jsonl');summary=run['summary']
    decisions=run['policy_public_decisions'];program=inputs['dispatch_program'];tol=protocol['absolute_tolerance']
    def close(actual,wanted,name):
        require(math.isclose(actual,wanted,abs_tol=tol,rel_tol=0),case['id']+': '+name+' differs')
    require(read(path/'scenario.json')==inputs['model'] and run['inputs']['dispatch_program']==program,'Saved input differs')
    require([r['frame']['as_of_s'] for r in decisions]==program['decision_times_s'],'Decision schedule differs')
    chosen=[r['choice']['chosen_candidate_id'] for r in decisions]
    if 'chosen' in expected:require(chosen==expected['chosen'],'Literal selection sequence differs: '+case['id'])
    if 'forbidden_first' in expected:
        require(chosen[0]!=expected['forbidden_first'],'Known unavailable continuation was selected')
        plan=next(a for a in decisions[0]['choice']['forecast_plans'][0]['alternatives'] if a['kind']=='inspect_then_act')
        require(not plan['eligible'] and expected['forecast_block'] in plan['planning_reasons'],'Missing frozen forecast refusal')
    for decision in decisions:
        frame=decision['frame'];choice=decision['choice'];now=frame['as_of_s']
        require(choice['as_of_s']==now and choice['facility_id']==frame['facility_id'],'Choice clock/identity differs')
        require(not choice['execution_permission'] and not choice['generated_tour'],'Choice cannot authorize execution or create Tour')
        require(all(r['observed_at_s']<=r['arrived_at_s']<=now for r in frame['evidence']['records']),'Future evidence entered decision')
        require(all(r['observed_at_s']<=r['arrived_at_s']<=now for r in decision['history']['work_feedback']),'Future work report entered decision')
    work=run['work_records'];completed=[r['completed_at_s'] for r in work if r['status']=='completed']
    effects=[r for r in run.get('intervention_private_audit',{}).get('events',[]) if r['outcome']=='APPLIED']
    require(completed==expected['completed_at_s'] and [r['applied_at_s'] for r in effects]==expected['effect_at_s'],'Actual completion/effect timing differs')
    if 'work_status' in expected:require([r['status'] for r in work]==expected['work_status'],'Actual work status differs')
    require(all(not r['risk_closed'] for r in run.get('intervention_public_feedback',[])),'Action report closed risk')
    if expected.get('empty_work_feedback'):require(run['workforce_public_feedback']==[],'Paid hidden discovery arrived early')
    if case['id']=='hidden-closed':require(summary['access_check_person_s']>0,'Hidden gate discovery was free')
    if 'rejection_observed_at_s' in expected:
        require(decisions[1]['history']['work_feedback']==[],'Refusal was disclosed before declared arrival')
        report=decisions[2]['history']['work_feedback'][0]
        require(report['status']=='rejected' and report['reason']=='DECLARED_TASK_ADMISSION_REFUSAL'
            and report['location_id'] is None,'Refusal leaked private cause/location')
        close(report['observed_at_s'],expected['rejection_observed_at_s'],'rejection observed')
        close(report['arrived_at_s'],expected['rejection_arrived_at_s'],'rejection arrived')
    if 'sensor_polls' in expected:
        polls=run['policy_sensor_private_audit'];require(len(polls)==expected['sensor_polls'],'Decimal sensor prefix count differs')
        require(polls[-1]['poll_index']==expected['last_poll_index'],'Decimal counter identity differs')
        close(polls[-1]['polled_at_s'],expected['last_polled_at_s'],'Decimal prefix endpoint')
    if 'fixed_records_per_decision' in expected:
        actual=[[[r['observed_at_s'],r['arrived_at_s']] for r in d['frame']['evidence']['records']
            if r['source_id']=='rectifier-meter-record'] for d in decisions]
        require(actual==expected['fixed_records_per_decision'],'Literal fixed-sensor arrivals differ')
        require([p['polled_at_s'] for p in run['policy_sensor_private_audit']]==expected['sensor_poll_epochs_s'],'Literal sensor epochs differ')
        measured=[[r for r in d['frame']['evidence']['records'] if r['source_id']=='portable-intake-meter'] for d in decisions]
        require([len(records) for records in measured]==expected['handheld_records_per_decision'],'Literal handheld availability differs')
        if expected['handheld_measurement'] is not None:
            reference=expected['handheld_measurement'];numerator,denominator=reference['value_squared_ratio']
            for records in measured:
                for record in records:
                    close(record['observed_at_s'],reference['observed_at_s'],'Handheld measurement time')
                    close(record['arrived_at_s'],reference['arrived_at_s'],'Handheld arrival time')
                    close(record['value'],math.sqrt(numerator/denominator),'Independent initial filter flow')
                    require(record['provenance']['origin_id']=='post-clean-flow','Handheld origin differs')
        require(run['policy_public_resource_ledger']['spent_or_reserved']==expected['final_spent_or_reserved'],'Literal cumulative budget differs')
    if 'closure_status' in expected:
        question=decisions[-1]['choice']['question_lifecycle']['questions'][0]
        require(question['status']==expected['closure_status'] and not question['risk_closed'],'Action completion fabricated verification')
    for key in ('delivered_service_unit_s','service_deficit_time_s','demand_service_unit_s'):close(summary[key],expected[key],key)
    require(abs(summary['whole_run_energy_residual_J'])<protocol['energy_tolerance_J'],'Whole energy residual')
    require(summary['max_mass_residual_kg']<=protocol['mass_tolerance_kg'],'Mass residual')
    require(len(trace)==len(balances)+1 and trace[0]['time_s']==0 and trace[-1]['time_s']==case['duration_s'],'Incomplete private trace')
    require(all(0<b['end_s']-b['start_s']<=protocol['maximum_step_s']+tol for b in balances),'Invalid integration step')
    require(run['research_trials']==run['model_calls']==run['training_calls']==0 and run['field_calibration']=='PENDING','Engineering classification differs')
    for name,identity in run['artifacts'].items():require(digest((path/name).read_bytes())==identity['sha256'],'Original run member differs')
    return dict(status='PASS',chosen=chosen,completed_at_s=completed,effect_at_s=[r['applied_at_s'] for r in effects],
        summary=summary,decision_count=len(decisions),trace_points=len(trace),actual_work_status=[r['status'] for r in work],
        declared_cost_basis=run.get('policy_public_resource_ledger',{}).get('basis'))


def check_saved(folder,protocol):
    checked={c['id']:check_case(folder,c,protocol) for c in protocol['cases']}
    documents={c['id']:read(ROOT/c['input']) for c in protocol['cases']}
    common=[]
    for name in protocol['same_world_cases']:
        document=deepcopy(documents[name]);p=document['dispatch_program']['policy_program'];p.pop('policy');p.pop('options');common.append(document)
    require(all(document==common[0] for document in common),'Five policies changed common facility/information/resource declarations')
    left,right=protocol['hidden_public_equal_cases']
    require(read(folder/left/'run.json')['policy_public_decisions']==read(folder/right/'run.json')['policy_public_decisions'],
        'Hidden access changed a pre-arrival decision')
    return dict(status='PASS',cases=checked,physical_runs=len(checked),same_world_declarations_equal=True,
        hidden_pair_public_decisions_equal=True,registered_research_trials=0,scope=protocol['scope'])


def figures(folder,checks,protocol):
    def label(x,y,value,cls='n'):return f'<text x="{x}" y="{y}" class="{cls}">{escape(str(value))}</text>'
    def start(title):return ['<svg xmlns="http://www.w3.org/2000/svg" width="1380" height="840" viewBox="0 0 1380 840">',
        '<metadata>Saved checks SHA256 '+digest(json.dumps(checks,sort_keys=True).encode())+'</metadata>',
        '<rect width="1380" height="840" fill="#f4f7fb"/><style>text{font-family:Arial,sans-serif;fill:#20334d}.h{font-size:26px;font-weight:bold}.s{font-size:19px;font-weight:bold}.n{font-size:16px}.tiny{font-size:14px}</style>',label(34,43,title,'h')]
    chart=start('Five transparent policies | actual saved decision timeline')
    chart +=[label(34,78,'Same eight-domain synthetic plant, arrived information, actual crew/tools and common admission caps.'),
        label(34,108,'Finite interface witnesses: 13 physical calls / 30 simulated seconds / no effect-comparison claim.')]
    colors={'first-inspection':'#007c99','first-action':'#bd7431',None:'#a9b8c8'}
    for index,name in enumerate(protocol['same_world_cases']):
        top=150+index*91;run=read(folder/name/'run.json')
        chart +=[f'<rect x="28" y="{top}" width="1320" height="78" rx="6" fill="white"/>',label(42,top+32,name,'s')]
        for row in run['policy_public_decisions']:
            x=330+row['frame']['as_of_s']/4*910;candidate=row['choice']['chosen_candidate_id']
            text={'first-inspection':'inspect','first-action':'act',None:'defer'}[candidate]
            chart +=[f'<circle cx="{x}" cy="{top+27}" r="8" fill="{colors[candidate]}"/>',label(x-18,top+60,text,'tiny')]
    chart +=[label(322,636,'0 s'),label(644,636,'1.5 s'),label(702,661,'1.75 s'),label(1222,636,'4 s')]
    chart +=[label(34,704,'Actual inspection ends 1.25 s; observation arrives 1.75 s; selected action ends 3 s.'),
        label(34,742,'Periodic due time is 2 s; its next declared decision is 4 s. No completed work is credited at this horizon.'),
        label(34,782,'Network bottleneck remains 0.25: each 4 s case delivers 1 unit-s and has 3 s service deficit.'),
        label(34,816,'Different selections prove interface behavior here; they do not establish an effective research policy.'),'</svg>']
    boundary=start('Public decisions and private execution share one advancing clock')
    boxes=[(30,'Arrived public inputs',['Static facility / task declarations','Sparse fixed sensor records','History / manual / work orders','Paid onsite inspection reports']),
        (480,'Transparent choice',['No human / FIFO / explicit periodic','Condition-risk / bounded lookahead','Exact cumulative admission account','Candidate / refusal / model-call audit']),
        (930,'Private execution',['Existing protection and access safety','Actual crew, tools and paid work','Named intervention after completion','Delayed task-local public feedback'])]
    for left,title,lines in boxes:
        boundary +=[f'<rect x="{left}" y="150" width="420" height="265" rx="8" fill="white" stroke="#afc0d4"/>',label(left+18,187,title,'s')]
        boundary +=[label(left+18,234+i*42,line) for i,line in enumerate(lines)]
    boundary +=['<path d="M450 280H480M900 280H930M1140 415V467H240V415" stroke="#007c99" stroke-width="3" fill="none"/>',
        label(445,498,'Only arrived allowed evidence returns to the next decision'),label(34,562,'Saved boundary witnesses','s'),
        label(34,607,'Hidden open/closed gate: identical decisions before the paid access report arrives.'),
        label(34,647,'Rejected task: generic acknowledgment at 0.5 s; no private location or refusal cause disclosed.'),
        label(34,687,'Exact continuation envelopes and half-open future authorization can block an otherwise valuable plan.'),
        label(34,727,'Completion and restoration are separate: actual action report leaves verification pending.'),
        label(34,786,'Plant truth, private error realization, evaluator traces and diagnostic wall time are never selector inputs.'),
        label(34,820,'Registered effect trials = 0; field calibration pending; AI / RSI eligibility remains a later gate.'),'</svg>']
    return {'policy-decisions.svg':('\n'.join(chart)+'\n').encode(),'policy-boundary.svg':('\n'.join(boundary)+'\n').encode()}


def append(path,value):
    with path.open('a',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(value,ensure_ascii=False,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())


def capture(folder,protocol):
    require(not git('status','--porcelain'),'Use clean frozen execution checkout')
    require(Path(os.environ.get('PYTHONPATH','')).resolve()==ROOT/'src','Set PYTHONPATH=src')
    source=git('rev-parse','HEAD').decode().strip();identities=pins(protocol,source);require(unchanged(source,identities),'Source pin differs')
    folder.mkdir(exist_ok=False)
    write(folder/'attempt.json',dict(classification=protocol['classification'],execution_commit=source,argv=sys.argv,
        executable=sys.executable,python=sys.version,executable_sha256=digest(Path(sys.executable).read_bytes()),
        declared_physical_runs=protocol['physical_runs'],declared_simulated_duration_s=protocol['total_simulated_duration_s']))
    receipt=dict(schema='aegisdc-policy-engineering-receipt-v1',execution_commit=source,pinned=identities,
        physical_attempts=0,physical_completed=0,validated_cases=0,failures=0,simulated_duration_attempted_s=0,
        registered_research_trials=0,llm_calls=0,training_calls=0,field_calibration='PENDING',global_regression_gate='PENDING_ROOT_INTEGRATED_FULL')
    try:
        from aegis_dc.plant import simulate_scenario,save_run
        for case in protocol['cases']:
            require(unchanged(source,identities),'Source changed before case');inputs=read(ROOT/case['input'])
            receipt['physical_attempts']+=1;receipt['simulated_duration_attempted_s']+=case['duration_s']
            append(folder/'attempts.jsonl',dict(case=case['id'],status='STARTED',execution_commit=source,duration_s=case['duration_s']))
            try:
                result=simulate_scenario(inputs['model'],duration_s=case['duration_s'],step_s=protocol['maximum_step_s'],dispatch_program=inputs['dispatch_program'])
                save_run(result,folder/case['id']);receipt['physical_completed']+=1
                check_case(folder,case,protocol);receipt['validated_cases']+=1
                append(folder/'attempts.jsonl',dict(case=case['id'],status='COMPLETED',execution_commit=source))
            except Exception as error:
                append(folder/'attempts.jsonl',dict(case=case['id'],status='FAILED',error_type=type(error).__name__,error=str(error)));raise
        checks=check_saved(folder,protocol);write(folder/'checks.json',checks)
        for name,raw in figures(folder,checks,protocol).items():write(folder/name,raw)
        require(durable(folder)==declared(protocol),'Durable output set differs');receipt['status']='PASS'
    except Exception as error:
        receipt.update(status='FAIL',failures=1,error_type=type(error).__name__,error=str(error));raise
    finally:
        receipt['source_head_and_bytes_unchanged']=unchanged(source,identities)
        if not receipt['source_head_and_bytes_unchanged']:
            receipt.update(status='FAIL',failures=1,source_guard_error='Source changed during capture')
            receipt.setdefault('error_type','SourceGuardError');receipt.setdefault('error','Source changed during capture')
        receipt['artifacts']={n:digest((folder/n).read_bytes()) for n in sorted(durable(folder))};write(folder/'receipt.json',receipt)
    require(receipt['source_head_and_bytes_unchanged'],'Source changed during capture')
    return dict(status=receipt['status'],execution=source,physical_runs=receipt['physical_attempts'],simulated_duration_s=receipt['simulated_duration_attempted_s'],artifacts=len(receipt['artifacts']))


def verify(folder,protocol,delivery):
    require(git('rev-parse','HEAD').decode().strip()==delivery and not git('status','--porcelain'),'Use clean requested delivery checkout')
    receipt=read(folder/'receipt.json');source=receipt['execution_commit']
    require(receipt['status']=='PASS' and receipt['source_head_and_bytes_unchanged'] and receipt['failures']==0,'Original capture failed')
    require(receipt['physical_attempts']==receipt['physical_completed']==receipt['validated_cases']==protocol['physical_runs'],'Attempt totals differ')
    require(receipt['simulated_duration_attempted_s']==protocol['total_simulated_duration_s'],'Simulated duration budget differs')
    require(set(receipt['artifacts'])==declared(protocol) and durable(folder)==declared(protocol)|{'receipt.json'},'Durable declaration differs')
    for n,h in hashes(delivery,[(folder/n).relative_to(ROOT).as_posix() for n in durable(folder)]).items():require(digest((ROOT/n).read_bytes())==h,'Committed delivery blob differs')
    for n,h in receipt['artifacts'].items():require(digest((folder/n).read_bytes())==h,'Original artifact differs')
    require(receipt['pinned']==pins(protocol,source),'Execution pin roles differ')
    for role,identities in receipt['pinned'].items():
        require(identities==hashes(delivery,identities) and all(digest((ROOT/n).read_bytes())==h for n,h in identities.items()),'Execution/delivery source differs: '+role)
    ledger=rows(folder/'attempts.jsonl');require(len(ledger)==2*len(protocol['cases']),'Ledger row count differs')
    for index,case in enumerate(protocol['cases']):
        pair=ledger[index*2:index*2+2]
        require([r['status'] for r in pair]==['STARTED','COMPLETED'] and all(r['case']==case['id'] and r['execution_commit']==source for r in pair),'Ledger order/source differs')
        run=read(folder/case['id']/'run.json')
        require(run['code_identity']['git_commit']==source and not run['code_identity']['implementation_has_changes'],'Actual execution revision differs')
    checks=check_saved(folder,protocol);require(checks==read(folder/'checks.json'),'Saved check output differs')
    for name,raw in figures(folder,checks,protocol).items():require(raw==(folder/name).read_bytes(),'Saved figure differs')
    return dict(status='PASS',execution=source,delivery=delivery,physical_attempts=receipt['physical_attempts'],
        artifacts=len(receipt['artifacts']),pins={role:len(group) for role,group in receipt['pinned'].items()},
        physical_rerun=False,full_regression_rerun=False,inference_rerun=False,runtime_caches_required=0)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['capture','verify'])
    parser.add_argument('--capture',type=Path,required=True);parser.add_argument('--delivery');args=parser.parse_args()
    folder=(ROOT/args.capture).resolve();require(folder.parent==ROOT/PACKAGE,'Use unique declared policy output');protocol=read(ROOT/PROTOCOL)
    print(json.dumps(capture(folder,protocol) if args.mode=='capture' else verify(folder,protocol,args.delivery),ensure_ascii=False))
