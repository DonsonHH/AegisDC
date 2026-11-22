"""Execute the preregistered positions; account for each call before entering the frozen simulator."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import math
import subprocess
import time
from workpackage import *
from public_adapter import Worker
from bounds import certificate_for
import native_v3
import public_work
from run_panel import retain
from score_saved import score


def acceptance_gate(group,plan,m):
    must(group in plan['groups'] and (ACT/'isolation/result.json').is_file(),'group or public witness')
    must(read(ACT/'isolation/result.json')['inputs']==filehash(ACT/'inputs/manifest.json'),'same input as witness')
    if group!='pilot':
        g=read(ACT/'pilot.json')
        must(g['continue'] and g['inputs']==filehash(ACT/'inputs/manifest.json') and group in g['group_minutes'],'valid budget gate')


def certify(case,observed,certificate,inherited):
    must(inherited['oracle']['native_attained'],'parent lower bound')
    # In the identity-only reserve case, both eligible writes preserve their targets. The old P
    # trajectory is an independent numerical reference, unaffected by the new action-only costs.
    lower=certificate['lower']
    if lower is None:
        cfg={x['id']:x['value'] for x in case['native']['scenario']['parameters']}
        must(cfg['network_service_capacity']==cfg['filter_resistance_multiplier']==1 and not certificate['plan'] and
             not any(e['parameter_id'] in ('network_service_capacity','filter_resistance_multiplier') for e in case['native']['boundary_events']),
             'missing structural basis for lower bound')
        lower=inherited['P_L']
    chain=all([int(t),task] in observed['requests'] and any(w['task']==task and w['outcome']=='APPLIED' for w in observed['writes']) and
              any(q['task']==task[:-1]+'R' and q['fields'] and q['execution'] for q in observed['paid']) for t,task in certificate['plan'].items())
    attained=chain and max(abs(observed[k]-lower) for k in ('L','U'))<=1e-7
    return dict(plan=certificate['plan'],reason=certificate['proof'],independent_lower=lower,native_L=observed['L'],native_U=observed['U'],
        actual_own_chain=chain,status='ATTAINED' if attained else 'UNRESOLVED',certified_min=lower if attained else None)


def unit(group,mode,key,role):
    os.sched_setaffinity(0,{int(os.environ['T4D_CPU'])})
    release=verify_source();m=manifest();plan=spec();acceptance_gate(group,plan,m)
    batch=read(ACT/'batches'/group/'entry.json')
    must(batch['job']==job() and batch['positions']==plan['groups'][group]['positions'] and [mode,key,role] in batch['positions']
         and batch['source']==os.environ['T4D_SOURCE'] and batch['inputs']==os.environ['T4D_INPUTS'],'registered execution')
    ip=case_file(mode,key);ident=m['items'][mode][key];must(filehash(ip)==ident['sha256'],'bound complete case')
    case=read(ip);out=ACT/'positions'/mode/(key+'-'+role)
    out.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    pub=case['native']['dispatch_program']['public']
    e=dict(mode=mode,key=key,role=role,group=group,attempt='a1',job=job(),host=os.uname().nodename,pid=os.getpid(),input=ident['sha256'],
        prior_input=ident['prior_sha256'],source=os.environ['T4D_SOURCE'],input_manifest=os.environ['T4D_INPUTS'])
    save(out/'entry.json',e)
    oracle=certificate_for(case) if role=='ORACLE' else None
    child=Worker(mode,role,m,out/'worker.stderr') if role!='ORACLE' else None
    parent=None;clean=False
    if oracle is not None:
        old=unpack(C/'development.json.gz');row=next(x for x in old['rows'] if x['key']==key)
        parent=dict(oracle=row['arms']['ORACLE']['oracle'],P_L=row['arms']['P']['L'])
    try:
        if child:child.start(pub)
        n=dict(**e,worker_pid=child.child.pid if child else None,bundle=child.identity if child else None,public=digest(pub))
        save(out/'native-entry.json',n)
        run,terminal=native_v3.native_run(case,role,oracle['plan'] if oracle else {},(),decider=child.choose if child else public_work.choose)
        clean=True
    finally:
        if child:child.close(failed=not clean)
    retain(out/'original.jsonl.gz',run,terminal)
    scored=score(case,run,terminal,role)
    cert=certify(case,scored,oracle,parent) if oracle is not None else None
    must(scored['runtime']==release['core_tree'] and scored['clocks']==61 and not run['t3_unpurchased_evaluator_only']
         and run['v3_received_maintenance']==case['maintenance'],'native source/parameters/clock')
    if child:
        must(n['worker_pid']!=e['pid'] and child.events==[[q['at'],q['view'],q['proposal']] for q in run['v3_proposals']],'worker replies vs actual proposals')
    if role in ('B_COST','V_COST_NOPROBE','B'):
        must(not any(task.endswith('::I') for _,task in scored['requests']),'unauthorized initial probe')
    if role=='B_COST':
        must(not any(q['external_refusal'] for q in run['v3_proposals']),'baseline contemplated illegal write')
    values={k:scored[k] for k in ('L','U','person','tool','fee','integral_balances','first','checkpoints','closure_changes','requests','refusals',
                                     'work','paid','writes','curve','clocks','runtime')}
    values.update(entry=e,worker=n,oracle=cert,raw_sha256=filehash(out/'original.jsonl.gz'),proposal_transcript=digest(child.events) if child else None,
                  public_ipc=digest(child.ipc) if child else None,maintenance=run['v3_maintenance_events'],elapsed_s=time.monotonic()-start)
    save(out/'score.json',values)
    print(mode,key,role,scored['L'],round(values['elapsed_s'],2),flush=True)


def group(name):
    verify_source();m=manifest();plan=spec();acceptance_gate(name,plan,m)
    registration=plan['groups'][name];n=registration['cpus'];slots=registration['positions']
    affinity=sorted(os.sched_getaffinity(0))
    must(n==int(os.environ['SLURM_CPUS_PER_TASK']) and n<=len(affinity),'allocation')
    dest=ACT/'batches'/name;dest.mkdir()
    save(dest/'entry.json',dict(job=job(),positions=slots,cpus=n,source=os.environ['T4D_SOURCE'],inputs=os.environ['T4D_INPUTS']))
    begin=time.monotonic()
    def lane(i):
        returned=[]
        for mode,key,role in slots[i::n]:
            with (dest/(mode+'-'+key+'-'+role+'.log')).open('x') as out:
                ret=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'unit',name,mode,key,role],stdout=out,stderr=subprocess.STDOUT,
                    env=dict(os.environ,T4D_CPU=str(affinity[i]),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1'))
            returned.append([mode,key,role,ret.returncode])
        return returned
    with ThreadPoolExecutor(max_workers=n) as pool:returns=[a for b in pool.map(lane,range(n)) for a in b]
    elapsed=time.monotonic()-begin;save(dest/'return.json',dict(job=job(),entries=returns,wall_s=elapsed))
    must(all(v[-1]==0 for v in returns),'stored failed attempt; stop suffix')
    if name=='pilot':
        durations=[read(ACT/'positions'/mode/(k+'-'+r)/'score.json')['elapsed_s'] for mode,k,r in slots]
        longest=max(elapsed,*durations)
        minutes={k:math.ceil(((math.ceil(len(v['positions'])/v['cpus']))*(1.2*longest+8)+6)/60)
                 for k,v in plan['groups'].items() if k!='pilot'}
        fixed=plan['fixed_allocations']
        total=sum(a*b*60 for a,b in fixed.values())+sum(60*t*plan['groups'][k]['cpus'] for k,t in minutes.items())
        count=len(fixed)+len(minutes)
        save(ACT/'pilot.json',dict(**{'continue':total<=plan['max_reserved_cpu_s'] and count<=plan['max_jobs']},
             job=job(),inputs=os.environ['T4D_INPUTS'],positions=slots,complete_wall_s=longest,unit_times=durations,
             group_minutes=minutes,projected_jobs=count,projected_reserved_cpu_s=total))
    print(name,len(returns),round(elapsed,2),flush=True)

if __name__=='__main__':
    if sys.argv[1]=='unit':unit(*sys.argv[2:])
    else:group(sys.argv[1])
