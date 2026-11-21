"""Run a frozen T2 position, or four-position pilot; all native work is on Slurm."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

sys.path.insert(1,str(Path(__file__).resolve().parent.parent))
from facility_inputs import CLOCK, H, ROOT, fingerprint, read, write
from generator import FAMILIES, SEED, generate

PACKAGE=Path(__file__).resolve().parent
ACTIVITY=Path('/share/home/renly/renly-patrol-rsi/mainline/T2-minute-facility-20261121-v1')
CORE=Path('/share/home/renly/renly-patrol-rsi/mainline/V6-cold-launch-release-v1/source')
ROLES=('P','PERIODIC','ALARM','ORACLE')


def require(ok,detail):
    if not ok:raise ValueError(detail)


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def pinned():
    require(os.environ.get('SLURM_JOB_ID'),'Slurm required')
    pin=read(PACKAGE/'study-freeze.json')
    for name,want in pin['files'].items():
        require(sha(PACKAGE/name)==want,'release drift '+name)
    identity=read(ROOT/'docs/mainline/v6-stage-three-cold-launch-v1/launch-manifest.json')
    require(sha(Path(sys.executable))==identity['python']['sha256'],'interpreter')
    for name,want in identity['core_files'].items():
        require(sha(CORE/name)==want,'core drift '+name)
    require(read(ACTIVITY/'A-readback.json')['passed'],'A qualification absent')
    return pin,identity


def prepare():
    pin,_=pinned()
    out=ACTIVITY/'study-inputs'
    rows=generate(pin['seed'],12,out)
    require(len(rows)==len({r['key'] for r in rows})==48,'draw count')
    # Independent repeat construction inside the approved input job.
    twice=ACTIVITY/'generation-repeat';rep=generate(pin['seed'],12,twice)
    require(rep==rows and all(sha(out/(a['key']+'.json'))==sha(twice/(a['key']+'.json')) for a in rows),'generator reproducibility')
    inputs={a['key']:sha(out/(a['key']+'.json')) for a in rows}
    # Inverse index is private to the evaluator except for the score report.
    manifest=dict(seed=pin['seed'],source_freeze=sha(PACKAGE/'study-freeze.json'),index=sha(out/'index.json'),files=inputs,
             roles=list(ROLES),pilot=pin['pilot'],batches=pin['batches'])
    write(out/'manifest.json',manifest)
    with gzip.open(ACTIVITY/'all-study-inputs.jsonl.gz','wt',encoding='utf8',compresslevel=6) as fp:
        for row in rows:
            fp.write(json.dumps({'key':row['key'],'input':read(out/(row['key']+'.json'))},separators=(',',':'))+'\n')
    print('frozen',sha(out/'manifest.json'),sha(ACTIVITY/'all-study-inputs.jsonl.gz'),flush=True)


def reserve_changes(run):
    result=[];prev=None
    for sample in run['trace']:
        backup=sample['domains']['backup']
        states=backup['reserve_states']
        current={k:v['mode'] for k,v in states.items()}
        if current!=prev:result.append([sample['time_s'],current]);prev=current
    return result


def make_score(run,record,mode):
    from audit_v6_joint import physiology,certificate_from_records
    from aegis_dc.joint_evidence import instances
    actual=physiology(run);prog=run['inputs']['dispatch_program'];cfg=prog['policy_program'];hist=run['policy_public_decisions']
    require(actual['conserved'] and actual['continuous'] and len(hist)==61 and
        [r['view']['time'] for r in hist]==CLOCK,'coverage/conservation')
    require(all(abs(x-y)<=1e-7 for x,y in zip(actual['balance'],actual['rate'])) and
            all(abs(x-y)<=1e-7 for x,y in zip(actual['physical_work'],actual['native_work'])),'accounting')
    first={};ever={};sampled={};issues=[];denials=[];trajectory=[];visible_precursors=[]
    order_ids=set(record['public']['work_orders'])
    for d in hist:
        view,decision=d['view'],d['decision'];t=view['time'];opens=instances(cfg,view)
        require(set(view)=={'time','orders','issued','work','writes','paid','fixed'} and all(
            all(r['at']<=r['arrived']<=t for r in view[channel]) for channel in ('orders','work','writes','paid','fixed')),'public arrival')
        states={k:certificate_from_records(cfg,view,k,v) for k,v in opens.items()}
        require(states==decision['certificates'],'named independent certificate')
        for name,state in states.items():
            if state in ('NO_ACTION_CURRENT','POST_ACTION_VERIFIED_CURRENT'):
                first.setdefault(name,{}).setdefault(state,t);ever.setdefault(name,set()).add(state)
        if t in (900,1800,2700,3600):sampled[str(int(t))]=states
        for row in view['orders']:
            if row['observable']=='alarm' and row['copied_from'] is None and row['arrived']<=t<row['until']:
                visible_precursors.append((row['arrived'],t,row['origin']))
        if decision['request']:issues.append([t,decision['request']['task'],decision['request'].get('patrol_slot')])
        denials.extend([t,*z] for z in decision['admissions'] if z[1]!='ADMITTED')
        # Raw pre-action records, not privileged score fields or condition labels, define comparability.
        trajectory.append(dict(t=t,view=fingerprint(view),issued=decision['request']['task'] if decision['request'] else None))
    require(set(sampled['3600'])==order_ids,'all frozen work orders accounted')
    works=run['work_records']
    require([[r['issued_at_s'],r['id']] for r in works]==[v[:2] for v in issues],'real issue identity')
    paid=run['inspection_public_feedback']
    measured=sorted({r['task'] for r in paid if r['interval'] is not None})
    permitted=set(record['public']['paid_opportunities'])|{record['public']['own_instance'][record['evaluation']['target']]+'/R'}
    require(set(measured)<=permitted and len(measured)<=2,'paid information opportunity bound')
    if mode=='P':require(not works and actual['physical_work']==[0,0],'protection-only P')
    if mode=='PERIODIC':
        slots=[q[2] for q in issues if q[2] is not None]
        require(slots==[v[1] for v in record['public']['duty_route']][:len(slots)],'fixed-route order')
    curve=[];first_loss=None
    for left,right in zip(run['trace'],run['trace'][1:]):
        a,b=left['time_s'],right['time_s'];svc=left['domains']['it_service'];d,y=svc['demand'],svc['delivered']
        if y<d and first_loss is None:first_loss=a
        if curve and curve[-1][2:]==[d,y]:curve[-1][1]=b
        else:curve.append([a,b,d,y])
    first_alert=min(visible_precursors) if visible_precursors else None
    writes=run['intervention_private_audit']['events']
    return dict(L=actual['rate'][0],U=actual['rate'][1],balance=actual['balance'],person_s=actual['physical_work'][0],
        tool_s=actual['physical_work'][1],fee=len(works)*cfg['fee'],first_closure=first,
        ever={k:sorted(v) for k,v in ever.items()},checkpoints=sampled,issues=issues,denials=denials,
        stages=[[r['id'],r['status'],r.get('finished_at_s'),r.get('reason')] for r in works],writes=writes,
        first_precursor=first_alert,first_loss=first_loss,curve=curve,public_history=trajectory,
        paid_observed=measured,local_first_trip=next((s['time_s'] for s in run['trace'] if s['domains']['control_monitoring']['protection_latched']),None),
        original_fixed=[r for r in hist[-1]['view']['fixed']],reserve_transitions=reserve_changes(run),
        public_source_count=len({(r['desk'],r['origin'],r['observable']) for r in prog['order_channel'] if r['observable']!='problem_reported'}),
        max_energy_residual=run['summary']['max_energy_residual_J'],
        max_mass_residual=run['summary']['max_mass_residual_kg'],public_calls=len(hist),intervals=len(run['balances']))


def run_unit(key,mode,manifest_hash):
    if 'T2_CPU_ID' in os.environ:
        os.sched_setaffinity(0,{int(os.environ['T2_CPU_ID'])})
    pin,core=pinned(); require(mode in ROLES,'role')
    ip=ACTIVITY/'study-inputs';require(sha(ip/'manifest.json')==manifest_hash,'manifest pin')
    m=read(ip/'manifest.json');path=ip/(key+'.json');require(sha(path)==m['files'][key],'complete input')
    x=read(path);item=x['native'];public=x['public']
    stage=ACTIVITY/'positions'/(key+'-'+mode);stage.mkdir()
    write(stage/'start.json',dict(job=os.environ['SLURM_JOB_ID'],pid=os.getpid(),key=key,mode=mode,input=sha(path),manifest=manifest_hash))
    sys.path[:0]=[str(CORE/'src'),str(CORE/'scripts')]
    from aegis_dc import joint_session
    from aegis_dc.plant import simulate_scenario
    from baselines import controller
    from oracle import schedule_certificate
    cert=schedule_certificate(x) if mode=='ORACLE' else None
    schedule=cert['plan'] if cert is not None else None
    original=joint_session.JointInspection
    # The ordinary v6 constructor validates field names and target. Apply the explicit
    # common public per-task read rights before any sampling at the physical producer.
    def public_rights(scenario,catalog,program):
        rights=deepcopy(program)
        for binding in rights['bindings']:
            binding['fields']=deepcopy(public['read_rights'][binding['task']])
        return original(scenario,catalog,rights)
    before=time.monotonic();cpu=time.process_time()
    with patch.object(joint_session,'choose',controller(mode,public,schedule)),patch.object(joint_session,'JointInspection',public_rights):
        run=simulate_scenario(**item)
    require(run['code_identity']['source_tree_sha256']==core['core_tree'] and run['source_config']==item['scenario']
            and run['inputs']['dispatch_program']==item['dispatch_program'] and run['inputs']['boundary_events']==item['boundary_events'],
            'returned source/input identity')
    with gzip.open(stage/'original.jsonl.gz','wt',encoding='utf8',compresslevel=1) as fp:
        fp.write(json.dumps({'metadata':{k:v for k,v in run.items() if k not in ('trace','balances')}},separators=(',',':'),allow_nan=False)+'\n')
        for a,b in zip(run['trace'],run['balances']):
            fp.write(json.dumps({'sample':a,'balance':b},separators=(',',':'),allow_nan=False)+'\n')
        fp.write(json.dumps({'sample':run['trace'][-1]},separators=(',',':'),allow_nan=False)+'\n')
    score=make_score(run,x,mode)
    if cert:
        if cert['proof']=='NO_EFFECTIVE_WRITABLE_PARAMETER_HOLD_L_EQUALS_P':
            require(cert['plan']=={} and not score['writes'] and not score['issues'],'invariant singleton trace')
            cert['lower']=score['L']
        cert['attained']=abs(cert['lower']-score['L'])<=1e-7 and abs(cert['lower']-score['U'])<=1e-7
        cert['issued_as_planned']=all([int(t),task] in [v[:2] for v in score['issues']] for t,task in cert['plan'].items())
    score.update(key=key,mode=mode,family=x['evaluation']['family'],input_sha256=sha(path),job=os.environ['SLURM_JOB_ID'],
        pid=os.getpid(),native_sha256=sha(stage/'original.jsonl.gz'),runtime=core['core_tree'],oracle=cert,
        elapsed_s=time.monotonic()-before,process_cpu_s=time.process_time()-cpu)
    write(stage/'result.json',score)
    if cert:
        require(cert['attained'] and cert['issued_as_planned'],'oracle bound not attained: preserve original and stop')
    print(key,mode,score['L'],score['elapsed_s'],flush=True)


def group(name,manifest_hash):
    pin,_=pinned(); ip=ACTIVITY/'study-inputs';require(sha(ip/'manifest.json')==manifest_hash,'frozen inputs')
    if name=='pilot':
        tasks=pin['pilot']
    else:
        gate=read(ACTIVITY/'pilot-account.json')
        require(gate['continue'] and gate['manifest']==manifest_hash,'pilot budget stop')
        tasks=pin['batches'][name]
    cpus=int(os.environ['SLURM_CPUS_PER_TASK']);require(cpus==len(tasks),'one independent CPU per position')
    log=ACTIVITY/'batches'/name;log.mkdir()
    write(log/'started.json',dict(job=os.environ['SLURM_JOB_ID'],manifest=manifest_hash,ordered=tasks,cpus=cpus))
    available=sorted(os.sched_getaffinity(0));require(len(available)>=cpus,'allocated worker affinity')
    group_start=time.monotonic()
    def one(pair):
        ix,(key,mode)=pair
        worker_env=dict(os.environ,T2_CPU_ID=str(available[ix]),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
        with (log/(key+'-'+mode+'.log')).open('x') as out:
            ret=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'unit',key,mode,manifest_hash],
                               stdout=out,stderr=subprocess.STDOUT,env=worker_env)
        return [key,mode,ret.returncode]
    with ThreadPoolExecutor(max_workers=cpus) as pool:results=list(pool.map(one,enumerate(tasks)))
    write(log/'terminal.json',dict(job=os.environ['SLURM_JOB_ID'],entries=results))
    require(all(a[-1]==0 for a in results),'a position failed; retain original and suffix')
    if name=='pilot':
        units=[read(ACTIVITY/'positions'/(k+'-'+m)/'result.json') for k,m in tasks]
        witness=next(u for u in units if u['mode']=='ORACLE')
        require(witness['oracle']['attained'] and witness['oracle']['issued_as_planned'],'unqualified pilot')
        group_wall=time.monotonic()-group_start
        longest=max(group_wall,max(u['elapsed_s'] for u in units))
        # Use the slowest full wall time even with CPU contention and 25% headroom,
        # then round up to whole Slurm minutes. CPU reservations, not just CPUTime, are capped.
        minutes=max(2,math.ceil((longest*1.25+15)/60))
        future=sum(len(v)*minutes*60 for v in pin['batches'].values())
        reserved=pin['input_and_pilot_reserved_CPU_s']+future+pin['readback_reserved_CPU_s']
        ok=(reserved<=16*3600 and len(pin['batches'])+3<=24)
        write(ACTIVITY/'pilot-account.json',dict(manifest=manifest_hash,**{'continue':ok},group_wall_s=group_wall,
            slowest_s=longest,wall_s=[u['elapsed_s'] for u in units],cpu_s=[u['process_cpu_s'] for u in units],
            minutes_per_next_job=minutes,projected_reserved_CPU_s=reserved,planned_jobs=len(pin['batches'])+3,
            pilot_completed=4,remaining_positions=188))
    print(name,results,flush=True)


if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='unit':run_unit(*sys.argv[2:])
    else:group(*sys.argv[1:])
