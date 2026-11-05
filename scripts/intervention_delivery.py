"""Frozen engineering intervention capture; verification never reruns physics."""
import argparse
from hashlib import sha256
from html import escape
import json
import math
import os
from pathlib import Path
import sys

from inspection_delivery import git,hashes,require,read,digest,write,durable,unchanged

ROOT=Path(__file__).resolve().parents[1]
PROTOCOL='docs/mainline/23-intervention-engineering-protocol.json'
PACKAGE='evidence/mainline/engineering/23-interventions'

def pins(protocol,revision):
    names=git('ls-tree','-rz','--name-only',revision,'src','configs',PACKAGE+'/development',PACKAGE+'/reference').decode().strip('\0').split('\0')
    groups=dict(runtime=[n for n in names if n.startswith('src/') and n.endswith('.py')],
        tools=[protocol['authoring_tool'],protocol['helper_tool'],protocol['input_preparation_tool']],
        inputs=[PROTOCOL,protocol['contract'],protocol['input_fixture'],
            *[n for n in names if n.startswith(PACKAGE+'/') or n.startswith('configs/full-facility') or n==protocol['reference_property']]])
    return {role:hashes(revision,paths) for role,paths in groups.items()}

def declared(protocol):
    return set(protocol['durable_root'])|{case['id']+'/'+n for case in protocol['cases'] for n in protocol['durable_per_case']}

def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]

def check_saved(folder,protocol):
    checked={};tol=protocol['absolute_tolerance']
    for case in protocol['cases']:
        path=folder/case['id'];run=read(path/'run.json');trace=rows(path/'private-state.jsonl');balances=rows(path/'balances.jsonl')
        expected=case['expected'];summary=run['summary'];events=run['intervention_private_audit']['events']
        require(len(events)==1,'Expected one terminal intervention: '+case['id'])
        event=events[0];feedback=run['intervention_public_feedback']
        require(event['outcome']==expected['outcome'],'Outcome differs: '+case['id'])
        if 'reason' in expected:require(event['reason']==expected['reason'],'Reason differs: '+case['id'])
        def close(actual,wanted,name):
            require(math.isclose(actual,wanted,abs_tol=tol,rel_tol=0),case['id']+': '+name+' differs')
        if 'applied_at_s' in expected:
            close(event['applied_at_s'],expected['applied_at_s'],'actual completion')
            require(run['work_records'][0]['status']=='completed','Effect without actual completion')
        require(len(feedback)==1 and not feedback[0]['risk_closed'],'Task-local feedback cannot close risk')
        require(feedback[0]['outcome']==event['outcome'] and feedback[0]['observed_at_s']==event['observed_at_s'],'Feedback event mismatch')
        require(feedback[0]['arrived_at_s']>feedback[0]['observed_at_s'],'Expected positive frozen feedback latency')
        # Reconstruct only the declared produced channel; no extra physical call.
        before=math.nextafter(feedback[0]['arrived_at_s'],-math.inf)
        require([f for f in feedback if f['arrived_at_s']<=before]==[],'Future feedback available early')
        close(summary['demand_service_unit_s'],case['duration_s'],'offered demand retained')
        for key in ('delivered','deficit'):
            if key in expected:close(summary[{'delivered':'delivered_service_unit_s','deficit':'service_deficit_time_s'}[key]],expected[key],key)
        require(abs(summary['whole_run_energy_residual_J'])<protocol['energy_tolerance_J'],'Whole energy residual')
        require(summary['max_mass_residual_kg']<=protocol['mass_tolerance_kg'],'Mass residual')
        require(run['research_trials']==run['model_calls']==run['training_calls']==0 and run['field_calibration']=='PENDING','Engineering classification changed')
        require(len(trace)==len(balances)+1 and trace[0]['time_s']==0 and trace[-1]['time_s']==case['duration_s'],'Incomplete actual trace')
        require(all(0<b['end_s']-b['start_s']<=protocol['maximum_step_s']+tol for b in balances),'Invalid integration interval')
        for n,identity in run['artifacts'].items():require(digest((path/n).read_bytes())==identity['sha256'],'Physical artifact bytes differ')
        actual=dict(outcome=event['outcome'],event=event,summary=summary,trace_points=len(trace),public_feedback=feedback)
        if 'compute_energy_J' in expected:
            energy=math.fsum((b['end_s']-b['start_s'])*point['domains']['power']['actual_powers_W']['compute'] for b,point in zip(balances,trace))
            close(energy,expected['compute_energy_J'],'actual compute electrical integral');actual['compute_energy_J']=energy
            require(trace[0]['domains']['power']['actual_powers_W']['compute']==2000000,'Compute starting power differs')
            require(next(p for p in trace if p['time_s']==event['applied_at_s'])['domains']['power']['actual_powers_W']['compute']==1000000,'Compute final power differs')
        if 'before_flow_squared' in expected:
            flow=lambda p:p['domains']['facility_cooling']['lake_pump']['volume_flow_m3_s']
            before_flow=flow(trace[0]);after_flow=flow(next(p for p in trace if p['time_s']==event['applied_at_s']))
            close(before_flow**2,expected['before_flow_squared'],'original hydraulic law')
            close(after_flow**2,expected['after_flow_squared'],'residual hydraulic law')
            require(before_flow<after_flow<.1,'Residual flow must remain below fully clean .1')
            record=run['inspection_public_snapshot']['records'][0]
            close(record['value'],math.sqrt(expected['after_flow_squared']),'actual later measurement')
            close(record['observed_at_s'],expected['inspection_observed_at_s'],'inspection completion')
            close(record['arrived_at_s'],expected['inspection_arrived_at_s'],'inspection arrival')
            actual.update(before_flow_m3_s=before_flow,after_flow_m3_s=after_flow,later_actual_inspection=record)
        if 'backup_fan_energy_J' in expected:
            points={p['time_s']:p for p in trace};state=points[expected['controller_request_s']]['domains']['backup']['reserve_states']['cooling']
            require(points[event['applied_at_s']]['domains']['backup']['backup_tower_mode']=='primary','Unexpected extra PLC sample')
            close(state['requested_at_s'],expected['controller_request_s'],'PLC request time')
            close(state['ready_at_s'],expected['backup_ready_s'],'transfer readiness')
            require(points[expected['backup_ready_s']]['domains']['backup']['backup_tower_mode']=='active','Backup not active')
            close(summary['backup_fan_energy_J'],expected['backup_fan_energy_J'],'paid fan energy')
            require(summary['backup_water_heat_J']>0,'No actual backup heat rejected')
        checked[case['id']]=actual
    return dict(status='PASS',cases=checked,physical_runs=len(checked),registered_research_trials=0,
        scope='Finite engineering response, independent literal integrals, timing, actual later measurement and conservation only')

def figures(folder,checks):
    def label(x,y,value,cls='n'):return f'<text x="{x}" y="{y}" class="{cls}">{escape(str(value))}</text>'
    def start(title,subtitle):return ['<svg xmlns="http://www.w3.org/2000/svg" width="1360" height="760" viewBox="0 0 1360 760">',
        '<metadata>Saved checks SHA256 '+digest(json.dumps(checks,sort_keys=True).encode())+'</metadata>',
        '<rect width="1360" height="760" fill="#f4f7fb"/><style>text{font-family:Arial,sans-serif;fill:#20334d}.h{font-size:26px;font-weight:bold}.s{font-size:19px;font-weight:bold}.n{font-size:15px}.tiny{font-size:13px}</style>',
        label(34,42,title,'h'),label(34,73,subtitle)]
    data=start('Authorized intervention: actual saved physical response','Eight engineering fixtures / V6 / max step 0.01 s / no policy or field effectiveness claim')
    def panel(left,top,title,series,horizon,ymax,unit):
        data.extend([f'<rect x="{left}" y="{top}" width="630" height="270" rx="8" fill="white" stroke="#c6d2df"/>',label(left+18,top+28,title,'s')])
        x=lambda t:left+62+t/horizon*530
        y=lambda v:top+203-v/ymax*140
        data.append(f'<path d="M{x(0)} {y(ymax)}V{y(0)}H{x(horizon)}" fill="none" stroke="#aab9ca"/>')
        for t in (0,horizon/2,horizon):data.append(label(round(x(t)-9,2),top+224,f'{t:g} s','tiny'))
        data.extend([label(left+6,y(0),0,'tiny'),label(left+6,y(ymax),f'{ymax:g}','tiny'),label(left+16,top+50,unit,'tiny')])
        for index,(name,color,points) in enumerate(series):
            coords=' '.join(f'{x(t):.3f},{y(v):.3f}' for t,v in points)
            data.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2.4"/>')
            data.extend([f'<rect x="{left+18+index*195}" y="{top+244}" width="16" height="3" fill="{color}"/>',label(left+40+index*195,top+250,name,'tiny')])
    trace=lambda case:rows(folder/case/'private-state.jsonl')
    panel(30,105,'A  Service after full, residual or aborted work',
        [(name,color,[(p['time_s'],p['domains']['it_service']['delivered']) for p in trace(case)]) for case,name,color in
         [('network-full','Full','#007b9c'),('network-residual','Residual','#a66b21'),('network-aborted','Aborted','#ae4555')]],3,1,'Delivered reference units / s')
    panel(700,105,'B  Filter response, then actual later inspection',
        [('Actual intake flow','#007b9c',[(p['time_s'],p['domains']['facility_cooling']['lake_pump']['volume_flow_m3_s']) for p in trace('filter-later-inspection')])],6,.1,'Flow (m3/s); clean reference = 0.1')
    panel(30,400,'C  Compute power changes; offered demand stays',
        [('Actual compute','#007b9c',[(p['time_s'],p['domains']['power']['actual_powers_W']['compute']/1000000) for p in trace('compute-power')])],3,2,'Actual electrical power (MW)')
    panel(700,400,'D  Backup waits for PLC sample and transfer',
        [('Backup active','#007b9c',[(p['time_s'],int(p['domains']['backup']['backup_tower_mode']=='active')) for p in trace('backup-request')])],6.25,1,'Request 3.5 s / sample 4 s / active 6 s')
    data.extend([label(34,704,'Full deficit 0.9375 s; residual 1.8125 s; aborted 2.25 s. Previous loss is never reset.'),
        label(34,734,'Filter 4 -> 2 at 3.25 s; handheld reads at 5.25 s, arrives 5.75 s. Completion alone leaves risk open.'),'</svg>'])
    arch=start('Intervention execution and information boundary','One complete synthetic facility; four relation graphs share entity identities; actual state stays private')
    boxes=[(30,125,'1  Public proposal',['Current arrived evidence','Declared static knowledge','Qualification / tools / authority','No actual-state feasibility oracle']),
        (365,125,'2  Actual crew execution',['Private access / safety check','Travel, waiting and occupied tools','Professional work, then completion','Abort and rejection remain costly']),
        (700,125,'3  Named physical effect',['Current authority rechecked','One closed parameter operation','Residual response, no energy reset','Settle protection; no extra PLC tick']),
        (1035,125,'4  Later allowed evidence',['Task-local delayed feedback','Actual later handheld inspection','Shared origin and arrival times','Risk remains open for ticket24'])]
    for left,top,title,lines in boxes:
        arch.extend([f'<rect x="{left}" y="{top}" width="295" height="235" rx="8" fill="white" stroke="#aabbd0"/>',label(left+14,top+30,title,'s')])
        arch.extend(label(left+14,top+72+i*36,line,'tiny') for i,line in enumerate(lines))
    arch.extend(['<path d="M325 240H365M660 240H700M995 240H1035" stroke="#007b9c" stroke-width="3"/>',
        label(36,416,'At each event instant','s'),label(36,456,'External inputs + existing protection -> access safety -> crew completion -> eligible effect'),
        label(36,494,'-> physical / reserve settlement (sampled=False) -> safety update -> snapshot and inspection -> next interval'),
        label(36,559,'Checks from saved originals','s'),label(36,597,'Independent service and power integrals / residual hydraulic law / paid backup fan / strict authorization expiry'),
        label(36,637,'Decimal clock repair preserves full work at .2 -> 1.2 s. Original independent failure remains retained.'),
        label(36,704,'Engineering verification only. Research trials = 0; AI / RSI gain not established; field calibration pending.'),'</svg>'])
    return {'intervention-data.svg':('\n'.join(data)+'\n').encode(),'intervention-architecture.svg':('\n'.join(arch)+'\n').encode()}

def append(path,value):
    with path.open('a',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(value,ensure_ascii=False,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())

def capture(folder,protocol):
    require(not git('status','--porcelain'),'Execution checkout must be clean')
    require(Path(os.environ.get('PYTHONPATH','')).resolve()==ROOT/'src','Set PYTHONPATH=src')
    source=git('rev-parse','HEAD').decode().strip();identities=pins(protocol,source)
    require(unchanged(source,identities),'Pinned source differs before capture')
    folder.mkdir(exist_ok=False)
    write(folder/'attempt.json',dict(classification='ENGINEERING_ONLY',execution_commit=source,argv=sys.argv,
        executable=sys.executable,python=sys.version,executable_sha256=digest(Path(sys.executable).read_bytes()),
        declared_physical_runs=protocol['declared_physical_runs'],registered_research_trials=0,llm_calls=0,training_calls=0))
    receipt=dict(schema='aegisdc-intervention-engineering-receipt-v1',execution_commit=source,pinned=identities,
        physical_attempts=0,physical_completed=0,failures=0,global_regression_gate='PENDING_ROOT_INTEGRATED_FULL',field_calibration='PENDING')
    try:
        from aegis_dc.plant import simulate_scenario,save_run
        for case in protocol['cases']:
            require(unchanged(source,identities),'Source changed before case')
            inputs=read(ROOT/case['input']);receipt['physical_attempts']+=1
            append(folder/'attempts.jsonl',dict(case=case['id'],status='STARTED',execution_commit=source))
            try:
                result=simulate_scenario(inputs['model'],duration_s=case['duration_s'],step_s=protocol['maximum_step_s'],
                    work_program=inputs['work_program'],intervention_program=inputs['intervention_program'],
                    inspection_program=inputs['inspection_program'],boundary_events=inputs['boundary_events'])
                save_run(result,folder/case['id']);receipt['physical_completed']+=1
                # A completed physical call can still violate its frozen oracle.
                # Audit its saved original before spending the next attempt.
                check_saved(folder,dict(protocol,cases=[case]))
                append(folder/'attempts.jsonl',dict(case=case['id'],status='COMPLETED',execution_commit=source))
            except Exception as error:
                append(folder/'attempts.jsonl',dict(case=case['id'],status='FAILED',error_type=type(error).__name__,error=str(error)));raise
        checks=check_saved(folder,protocol);write(folder/'checks.json',checks)
        for name,raw in figures(folder,checks).items():write(folder/name,raw)
        require(durable(folder)==declared(protocol),'Durable output set differs')
        receipt['status']='PASS'
    except Exception as error:
        receipt.update(status='FAIL',failures=1,error_type=type(error).__name__,error=str(error));raise
    finally:
        receipt['source_head_and_bytes_unchanged']=unchanged(source,identities)
        if not receipt['source_head_and_bytes_unchanged']:receipt['status']='FAIL'
        receipt['artifacts']={name:digest((folder/name).read_bytes()) for name in sorted(durable(folder))}
        write(folder/'receipt.json',receipt)
    require(receipt['source_head_and_bytes_unchanged'],'Source changed during capture')
    return dict(status=receipt['status'],execution=source,physical_attempts=receipt['physical_attempts'],physical_completed=receipt['physical_completed'],artifacts=len(receipt['artifacts']))

def verify(folder,protocol,delivery):
    require(git('rev-parse','HEAD').decode().strip()==delivery and not git('status','--porcelain'),'Use clean requested fresh checkout')
    receipt=read(folder/'receipt.json');source=receipt['execution_commit']
    require(receipt['status']=='PASS' and receipt['source_head_and_bytes_unchanged'],'Original engineering capture failed')
    require(receipt['physical_attempts']==receipt['physical_completed']==protocol['declared_physical_runs'] and receipt['failures']==0,'Attempt accounting differs')
    require(set(receipt['artifacts'])==declared(protocol) and durable(folder)==declared(protocol)|{'receipt.json'},'Durable files differ')
    for name,wanted in hashes(delivery,[(folder/n).relative_to(ROOT).as_posix() for n in durable(folder)]).items():
        require(digest((ROOT/name).read_bytes())==wanted,'Delivery blob differs: '+name)
    for name,wanted in receipt['artifacts'].items():require(digest((folder/name).read_bytes())==wanted,'Original file differs')
    require(receipt['pinned']==pins(protocol,source),'Execution pin set differs')
    for role,identities in receipt['pinned'].items():
        require(identities==hashes(delivery,identities) and all(digest((ROOT/n).read_bytes())==h for n,h in identities.items()),'Execution/delivery source differs: '+role)
    ledger=rows(folder/'attempts.jsonl')
    require(len(ledger)==2*len(protocol['cases']),'Attempt ledger count differs')
    for index,case in enumerate(protocol['cases']):
        pair=ledger[index*2:index*2+2]
        require([r['case'] for r in pair]==[case['id']]*2 and [r['status'] for r in pair]==['STARTED','COMPLETED'],'Attempt order differs')
        run=read(folder/case['id']/'run.json')
        require(run['code_identity']['git_commit']==source and not run['code_identity']['implementation_has_changes'],'Execution revision differs')
    checks=check_saved(folder,protocol);require(checks==read(folder/'checks.json'),'Saved check differs')
    for name,raw in figures(folder,checks).items():require(raw==(folder/name).read_bytes(),'Saved figure bytes differ')
    return dict(status='PASS',execution=source,delivery=delivery,physical_attempts=receipt['physical_attempts'],
        artifacts=len(receipt['artifacts']),pins={k:len(v) for k,v in receipt['pinned'].items()},
        physical_rerun=False,full_regression_rerun=False,inference_rerun=False,runtime_caches_required=0)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['capture','verify'])
    parser.add_argument('--capture',type=Path,required=True);parser.add_argument('--delivery');args=parser.parse_args()
    folder=(ROOT/args.capture).resolve();require(folder.parent==ROOT/PACKAGE,'Use unique declared intervention output')
    protocol=read(ROOT/PROTOCOL)
    print(json.dumps(capture(folder,protocol) if args.mode=='capture' else verify(folder,protocol,args.delivery),ensure_ascii=False))
