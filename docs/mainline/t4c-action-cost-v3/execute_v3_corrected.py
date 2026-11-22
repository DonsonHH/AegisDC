"""Allocate one fresh facility and one detached decision process per registered role and row."""
from concurrent.futures import ThreadPoolExecutor
import math
import subprocess
import time
from common_v3 import *

def runner_identity():
    record=read(PK/'runtime-repair-1.json')
    check(sha(Path(__file__))==record['corrected_runner_sha256'] and sha(PK/'runtime-repair-1.json')==os.environ['T4C_REPAIR_LOCK'],'actual authorized runner identity')
    return record['corrected_runner_sha256']

import native_v3
import public_work
from bounds import certificate_for,information
from score_saved import score
from isolation_v3 import Child
from run_panel import retain


def check_oracle(case, result, cert):
    if cert['lower'] is None:
        cfg={r['id']:r['value'] for r in case['native']['scenario']['parameters']}
        check(cfg['network_service_capacity']==cfg['filter_resistance_multiplier']==1 and
              not any(z['parameter_id'] in ('network_service_capacity','filter_resistance_multiplier') for z in case['native']['boundary_events'])
              and not cert['plan'] and not result['requests'],'identity target in masked reserve')
        cert['proof']='Both available target parameters equal 1 throughout the untreated native trajectory. Their writes can only preserve them and add a nonnegative restriction. No-action attains the legal minimum.'
        cert['lower']=result['L']
    check(abs(cert['lower']-result['L'])<1e-7 and abs(cert['lower']-result['U'])<1e-7,'native does not attain independent relaxed bound')
    for t,task in cert['plan'].items():
        check([t,task] in result['requests'] and any(w['task']==task and w['outcome']=='APPLIED' for w in result['writes']) and
            any(q['task']==task[:-1]+'R' and q['fields'] and q['execution'] for q in result['paid']),'oracle work and own verification')
    cert['native_attained']=True


def expected_engineering(metrics, expected, maintenance, locks):
    a=expected
    events=[(t,s) for t,s in metrics['requests'] if s.endswith('::A')]
    check(abs(a['L']-metrics['L'])<1e-7 and abs(a['U']-metrics['U'])<1e-7,'independent engineering L/U')
    check([list(z) for z in events]==a['issued_A'] and locks==a['lock_refusal'],'independent work/denial identity')
    event=next(r for r in maintenance if r['task']==a['write_first']+'::A')
    if a['first_time'] is not None:check(event['at']==a['first_time'],'actual write time')
    if 'indicated' in a:
        check(event['indicated']==a['indicated'] and event['until']==a['penalty_until'],'precondition and service interval')


def check_stage(phase,name):
    check((ACT/'isolation/result.json').is_file() and phase==('eng' if name.startswith('eng') else 'dev'),'registered phase and isolation')
    if phase=='dev':
        check((ACT/'engineering-accepted-by-checks.json').is_file(),'engineering gate')
        if name!='pilot':check(read(ACT/'pilot-budget.json')['continue'],'pilot budget stop')
        if name.startswith(('ctrl','new')):check((ACT/'ref-complete.json').is_file(),'frozen reference first')
        if name.startswith('new'):check((ACT/'controls-complete.json').is_file(),'controls complete')


def unit(phase,key,role,manifest_id,attempt,name):
    if 'T4C_CPU' in os.environ:os.sched_setaffinity(0,{int(os.environ['T4C_CPU'])})
    spec=pinned();actual_runner=runner_identity()
    bundle=read(ACT/'bundles.json')
    froot=ACT/(phase+'-inputs')
    check(sha(froot/'manifest.json')==manifest_id,'input version')
    m=sealed_manifest(phase);file=froot/(key+'.json')
    check_stage(phase,name)
    group_entry=read(ACT/'batches'/name/attempt/'entry.json')
    check(group_entry['job']==job() and group_entry['manifest']==manifest_id and group_entry['positions']==spec['groups'][name]
          and [key,role] in group_entry['positions'] and attempt==('a2' if phase=='eng' else 'a1'),'bound Slurm group membership')
    check(sha(file)==m['files'][key] and m['source_freeze']==sha(PK/'freeze.json'),'input and pre-role rules')
    x=read(file)
    engineering=phase=='eng'
    case=x['case'] if engineering else x
    out=ACT/'positions'/(phase+'-'+key+'-'+role)/attempt
    out.mkdir(parents=True,exist_ok=False)
    entry=dict(key=key,role=role,phase=phase,attempt=attempt,job=job(),pid=os.getpid(),manifest=manifest_id,
               input=sha(file),freeze=sha(PK/'freeze.json'),launch_code=actual_runner,runtime_code=sha(PK/'native_v3.py'))
    write(out/'entry.json',entry);started=time.monotonic()
    public=case['native']['dispatch_program']['public']
    cert=certificate_for(case) if role=='ORACLE' else None
    plan={int(t):s for t,s in x['plan'].items()} if engineering else cert['plan'] if cert is not None else {}
    diag=information(case,None,None)['all_paid'] if role=='P' else ()
    child=None;success=False
    if role in BUNDLE_NAMES:
        root=OLD_BUNDLE if role in ('VSTAR','PA','B') else BUNDLE
        dictionary=bundle['original'] if root==OLD_BUNDLE else bundle['files']
        check(all(sha(root/k)==v for k,v in dictionary.items()),'worker bundle')
        child=Child(role,out/'worker.stderr')
        child.start(public)
    try:
        write(out/'native-entry.json',dict(**entry,worker_pid=child.child.pid if child else None,
              public_program=hash_obj(public),bundle=bundle['old' if role in ('VSTAR','PA','B') else 'new'] if child else None))
        run,terminal=native_v3.native_run(case,role,plan,diag,decider=child.choose if child else public_work.choose)
        success=True
    finally:
        if child:child.close(failed=not success)
    raw=out/'original.jsonl.gz'
    retain(raw,run,terminal)
    metrics=score(case,run,terminal,role)
    d=run['policy_public_decisions'];proposals=run['v3_proposals'];maintenance=run['v3_maintenance_events']
    check(run['v3_received_maintenance']==case['maintenance'] and len(d)==len(proposals)==61,'physical/direct identity')
    if child:
        check(child.events==[[r['at'],r['view'],r['proposal']] for r in proposals] and child.child.pid!=os.getpid(),'worker vs plant transcript')
    check(role=='P' or not run['t3_unpurchased_evaluator_only'],'private diagnostic data entered another arm')
    actual=[a['decision']['request'] for a in d if a['decision']['request'] and a['decision']['request']['phase']=='A']
    check(all(right['at']>=left['planned_end']+case['maintenance']['recovery'] for left,right in zip(actual,actual[1:])),'plant allowed overlapping maintenance')
    locks=[[q['at'],q['requested']['subject']] for q in proposals if q['external_refusal']]
    if cert is not None:check_oracle(case,metrics,cert)
    if engineering:expected_engineering(metrics,x['expected'],maintenance,locks)
    if 'NOPROBE' in role:check(all(not s.endswith('::I') for t,s in metrics['requests']),'ablation purchased a read')
    if role=='P':
        check(len(diag)==len(run['t3_unpurchased_evaluator_only']) and all(q['fields'] is not None for q in run['t3_unpurchased_evaluator_only']),'P-only information opportunity')
    summary={k:metrics[k] for k in ('L','U','integral_balances','person','tool','fee','first','checkpoints','closure_changes','requests',
                                     'refusals','work','paid','writes','curve','clocks','runtime')}
    summary.update(entry=entry,worker_pid=child.child.pid if child else None,public_calls=61,IPC=hash_obj(child.events) if child else None,
        public_prefix=metrics['public_prefix'],expected=x['expected'] if engineering else None,maintenance=maintenance,
        locks=locks,oracle=cert,independent_information=run['t3_unpurchased_evaluator_only'],raw=sha(raw),elapsed=time.monotonic()-started)
    write(out/'score.json',summary)
    print(key,role,summary['L'],round(summary['elapsed'],2),flush=True)


def minutes(pilot_seconds,waves):
    return math.ceil((waves*(1.20*pilot_seconds+8)+6)/60)


def group(phase,name,attempt='a1'):
    runner_identity();plan=pinned();schema=sealed_manifest(phase);mhash=sha(ACT/(phase+'-inputs')/'manifest.json')
    check(schema['source_freeze']==sha(PK/'freeze.json') and (ACT/'isolation/result.json').exists(),'pre-run material')
    slots=plan['groups'][name]
    check_stage(phase,name);check(attempt==('a2' if phase=='eng' else 'a1'),'registered position attempt')
    n=int(os.environ['SLURM_CPUS_PER_TASK']);cpus=sorted(os.sched_getaffinity(0))
    check(len(cpus)>=n and n==plan['cpus'][name],'allocation')
    out=ACT/'batches'/name/attempt;out.mkdir(parents=True,exist_ok=False)
    write(out/'entry.json',dict(job=job(),positions=slots,cores=n,manifest=mhash))
    begin=time.monotonic()
    def lane(i):
        done=[]
        for index in range(i,len(slots),n):
            k,r=slots[index]
            env=dict(os.environ,T4C_CPU=str(cpus[i]),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
            with (out/(k+'-'+r+'.log')).open('x') as fp:
                ret=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'unit',phase,k,r,mhash,attempt,name],
                                   stdout=fp,stderr=subprocess.STDOUT,env=env)
            done.append([k,r,ret.returncode])
        return done
    with ThreadPoolExecutor(max_workers=n) as pool:done=[v for lane_done in pool.map(lane,range(n)) for v in lane_done]
    write(out/'return.json',dict(job=job(),positions=done,elapsed=time.monotonic()-begin))
    check(all(q[2]==0 for q in done),'preserved failed unit; inspect its logs')
    if name=='pilot':
        t=time.monotonic()-begin
        mins={k:minutes(t,math.ceil(len(v)/plan['cpus'][k])) for k,v in plan['groups'].items() if k.startswith(('ref','ctrl','new'))}
        proj=plan['dev_fixed_reserved_s']+sum(60*mins[k]*plan['cpus'][k] for k in mins)
        jobs=plan['dev_fixed_jobs']+len(mins)
        write(ACT/'pilot-budget.json',dict(**{'continue':proj<=144000 and jobs<=50},job=job(),longest_complete_wall=t,
              pilot=slots,minutes=mins,projected_jobs=jobs,projected_reserved_s=proj,
              per_unit=[read(ACT/'positions'/('dev-'+k+'-'+r)/attempt/'score.json')['elapsed'] for k,r in slots]))
    print(name,len(done),round(time.monotonic()-begin,1),flush=True)

if __name__=='__main__':
    if sys.argv[1]=='unit':unit(*sys.argv[2:])
    else:group(*sys.argv[1:])
