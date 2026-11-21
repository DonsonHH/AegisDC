"""Trusted execution/retention. The facility process and the policy interpreter are never the same process."""
from concurrent.futures import ThreadPoolExecutor
import gzip
import math
import os
import subprocess
import sys
import time
from unittest.mock import patch
from bridge import *


def retain(path,run,attachment):
    with gzip.open(path,'xt',encoding='utf8',compresslevel=1) as fp:
        def emit(v):fp.write(json.dumps(v,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n')
        emit(dict(metadata={k:v for k,v in run.items() if k not in ('trace','balances')},terminal=attachment))
        for a,b in zip(run['trace'],run['balances'],strict=False):emit(dict(sample=a,balance=b))
        emit(dict(sample=run['trace'][-1]))


def audit_choices(x,run,role,gate):
    pub=x['native']['dispatch_program']['public'];subs=gate.entries(pub)
    comps={};decision_reasons={};reads_sensitive=0;reviews=0;unresolved=0;root_order=[]
    for d in run['policy_public_decisions']:
        v=d['view'];a=d['decision'];r=a['request'];why=a['rationale']
        if r:
            real,detail=gate.admit(pub,v,subs[r['subject']],r['phase'],r['patrol_slot'])
            require(real==r and detail=='ALLOW','request failed unmodified T3 admission')
            code=r['phase'];comps[code]=comps.get(code,0)+1
            if code=='R':reviews+=1
        done={p['task'] for p in v['issued']}
        mandatory=sorted((s for s in pub['routes'] if s+'::A' in done and s+'::R' not in done),key=lambda s:(subs[s]['read_window'][1],s))
        due=next((item for s in mandatory if (item:=gate.admit(pub,v,subs[s],'R')[0])),None)
        require(not due or due==r,'obligation displaced')
        if role=='B':require(r is None or r['phase'] in ('A','R','X'),'unregistered B acquisition')
        if role.startswith('V'):
            reason=why['reason'];decision_reasons[reason]=decision_reasons.get(reason,0)+1
            unresolved+=int(why['posterior']['model_conflict'])
            for e in why['continuation_table']:
                p=sum(q['probability'] for q in e['table'].values())
                require(abs(p-1)<1e-8,'branch distribution')
                l,h,f,j=e['vector'];require(abs(j-l-why['price']*(h+30*f))<1e-6,'mixed objective')
                if e['first'] and e['first'][1]=='I' and len({tuple(q['continue_with']) for q in e['table'].values()})>1:reads_sensitive+=1
            if why['reason']=='VALUE' and r:require(why['winning_first']==[r['subject'],r['phase']],'first step not supported')
        root_order.append([v['time'],r['task'] if r else None])
    return dict(actual_phases=comps,decision_reasons=decision_reasons,info_sensitive_candidate_roots=reads_sensitive,
                zero_support_ticks=unresolved,own_reviews=reviews,root_order_digest=digest(root_order))


def action_effects(x,run):
    params={i['id']:i['value'] for i in x['native']['scenario']['parameters']};cfg=x['attachment'] or {}
    last={'clean_filter':params['filter_resistance_multiplier'],'restore_network':params['network_service_capacity'],
          'revise_shared':cfg.get('logic')=='SHARED_CONTACT','restore_path':bool(cfg.get('b_connected')),
          'prestart':False,'relieve_group':bool(cfg.get('group_relocated')),'commission_backup':not cfg.get('construction',True)}
    ev=sorted(x['native']['boundary_events'],key=lambda b:b['time_s']);p=0;result=[]
    for w in run['intervention_public_feedback']:
        t=w['at'];op=w['operation']
        while p<len(ev) and ev[p]['time_s']<=t:
            k={'filter_resistance_multiplier':'clean_filter','network_service_capacity':'restore_network'}.get(ev[p]['parameter_id'])
            if k:last[k]=ev[p]['value']
            p+=1
        changed=w['outcome']=='APPLIED' and (op=='restart_pump' or last.get(op)!=1)
        if w['outcome']=='APPLIED':last[op]=1
        result.append([w['task'],op,t,w['outcome'],bool(changed)])
    return result


def unit(key,role):
    if 'T4A_CPU' in os.environ:os.sched_setaffinity(0,{int(os.environ['T4A_CPU'])})
    spec,pin=frozen();bundle=check_bundle(spec)
    witness=read(ACTIVITY/'isolation/result.json')
    require(witness['bundle']==bundle and witness['freeze']==sha(PK/'freeze.json') and witness['status']=='PUBLIC_BOUNDARY_WITNESSED','no verified public boundary')
    m=inputs();expected=m['files'][key];source=PREVIOUS/'development-inputs'/(key+'.json')
    require(sha(source)==expected and role in ARMS,'development slot')
    x=read(source);out=ACTIVITY/'positions'/(key+'-'+role);out.mkdir()
    entry=dict(key=key,role=role,input_sha256=expected,study_manifest=sha(T3/'development-inputs.json'),
               method_release=sha(PK/'freeze.json'),public_bundle=bundle,job=os.environ['SLURM_JOB_ID'],pid=os.getpid())
    write(out/'entry.json',entry)
    sys.path[:0]=[str(T3),str(CORE/'src'),str(CORE/'scripts')]
    import native,public_work
    from score_saved import score
    child=PublicProcess(role,out/'public-worker.stderr');started=time.monotonic();cpu=time.process_time();bad=True
    try:
        # Complete handshake on the same public schema before the first native start.
        public=x['native']['dispatch_program']['public']
        require(child.message({'public':public})=={'ready':True,'role':role},'handshake')
        child.static=digest(public)
        write(out/'native-entry.json',dict(**entry,worker_pid=child.child.pid,static_public=child.static))
        with patch.object(native,'choose',child.choose):
            run,attachment=native.native_run(x,role)
        bad=False
    finally:child.close(failed=bad)
    raw=out/'original.jsonl.gz';retain(raw,run,attachment)
    require(len(child.events)==61 and child.child.pid!=os.getpid() and run['code_identity']['source_tree_sha256']==pin['core_tree'] and
            run['t3_unpurchased_evaluator_only']==[],'runtime, isolation and number of calls')
    ticks=run['policy_public_decisions']
    require(child.events==[[d['view']['time'],digest(d['view']),digest(d['decision'])] for d in ticks],'IPC versus actual work decisions')
    summary=score(x,run,attachment,role)
    methods=audit_choices(x,run,role,public_work);acts=action_effects(x,run)
    log=dict(key=key,role=role,entry=entry,worker_pid=child.child.pid,static_public=child.static,IPC_sha256=digest(child.events),
        source_runtime=summary['runtime'],L=summary['L'],U=summary['U'],balance=summary['integral_balances'],
        person=summary['person'],tool=summary['tool'],fee=summary['fee'],first=summary['first'],checkpoints=summary['checkpoints'],
        closure_changes=summary['closure_changes'],requests=summary['requests'],refusals=summary['refusals'],work=summary['work'],
        paid=summary['paid'],writes=summary['writes'],curve=summary['curve'],actual_actions=acts,policy_audit=methods,
        public_calls=summary['clocks'],raw_sha256=sha(raw),elapsed_s=time.monotonic()-started,facility_process_cpu_s=time.process_time()-cpu)
    write(out/'result.json',log)
    print(key,role,log['L'],log['person'],log['elapsed_s'],flush=True)


def group(name):
    spec,_=frozen();check_bundle(spec);require((ACTIVITY/'isolation/result.json').is_file(),'missing isolation witness')
    if name=='pilot':pairs=spec['pilot']
    else:
        paid=read(ACTIVITY/'pilot-budget.json')
        require(paid['continue'] and paid['freeze']==sha(PK/'freeze.json'),'pilot budget stop')
        stage=int(name[1]);pairs=spec['batches'][name]
        if stage>1:
            previous=read(ACTIVITY/f'stage-{stage-1}.json')
            require(previous['complete'] and previous['next_version']=='V'+str(stage),'missing documented development diagnosis')
    n=int(os.environ['SLURM_CPUS_PER_TASK']);cpus=sorted(os.sched_getaffinity(0))
    require(len(pairs)==n<=len(cpus),'CPU admission')
    dest=ACTIVITY/'batches'/name;dest.mkdir()
    write(dest/'start.json',dict(job=os.environ['SLURM_JOB_ID'],freeze=sha(PK/'freeze.json'),positions=pairs,cpus=n))
    start=time.monotonic()
    def one(i_and_pair):
        i,(k,role)=i_and_pair;env=dict(os.environ,T4A_CPU=str(cpus[i]),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
        with (dest/(k+'-'+role+'.log')).open('x') as fp:
            rc=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'unit',k,role],env=env,stdout=fp,stderr=subprocess.STDOUT).returncode
        return [k,role,rc]
    with ThreadPoolExecutor(max_workers=n) as pool:out=list(pool.map(one,enumerate(pairs)))
    write(dest/'terminal.json',dict(job=os.environ['SLURM_JOB_ID'],entries=out,wall=time.monotonic()-start))
    require(all(q[-1]==0 for q in out),'retained nonreturn; inspect before suffix')
    if name=='pilot':
        data=[read(ACTIVITY/'positions'/(k+'-'+r)/'result.json') for k,r in pairs]
        wall=max([time.monotonic()-start]+[q['elapsed_s'] for q in data]);minutes=math.ceil((wall*1.25+15)/60)
        reserved=spec['fixed_reserved_cpu_s']+354*minutes*60
        jobs=2+len(spec['batches'])+len(spec['analysis_jobs'])
        write(ACTIVITY/'pilot-budget.json',dict(freeze=sha(PK/'freeze.json'),**{'continue':reserved<=108000 and jobs<=40},
            pilot=pairs,unique_native_positions=6,longest_complete_wall_s=wall,position_times=[q['elapsed_s'] for q in data],
            requested_minutes_per_remaining=minutes,remaining_positions=354,projected_reserved_cpu_s=reserved,projected_jobs=jobs))
    print(name,len(out),'complete',flush=True)


if __name__=='__main__':
    if sys.argv[1]=='unit':unit(*sys.argv[2:])
    else:group(sys.argv[1])
