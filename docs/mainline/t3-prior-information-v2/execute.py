"""Remote input author, gated native executions and pilot accounting. Never opens a holdout seed."""
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from common import PK,ROOT,REMOTE,CORE,BIZ,CLOCK,ROLES,load,write,sha,digest,insist,slurm,templates
from generator_v2 import SEED,FAMILIES,dev_case
from qualification_cases import engineering_a,engineering_c

TOL=1e-7


def pinned():
    slurm();m=load(PK/'freeze.json')
    for f,h in m['source_sha256'].items():insist(sha(PK/f)==h,'T3 freeze '+f)
    for f,h in m['previous_sha256'].items():insist(sha(ROOT/f)==h,'original local material '+f)
    core=load(ROOT/'docs/mainline/v6-stage-three-cold-launch-v1/launch-manifest.json')
    insist(sha(Path(sys.executable))==core['python']['sha256'],'frozen interpreter')
    for f,h in core['core_files'].items():insist(sha(CORE/f)==h,'frozen runtime '+f)
    return m,core


def prepare(phase):
    spec,_=pinned()
    engineering=phase=='engineering';src=templates()
    if not engineering:
        insist(load(REMOTE/'A-terminal.json')['passed'] and load(REMOTE/'C-terminal.json')['passed'],'both gates')
    folder=REMOTE/(phase+'-inputs');folder.mkdir()
    rows={};definitions={}
    if engineering:
        for gate,cases in [('A',engineering_a(src)),('C',engineering_c(src))]:
            definitions[gate]=[]
            for name,(x,plan,expect) in cases.items():
                key=gate+'-'+name
                rows[key]=dict(input=x,plan=plan,expect=expect);definitions[gate].append(key)
    else:
        for draw in range(12):
            for n,fam in enumerate(FAMILIES,1):
                key=f'{n}-{draw+1:02d}';x=dev_case(SEED,draw,fam,src)
                insist(digest(dev_case(SEED,draw,fam,src))==digest(x),'reproducible dev construction')
                rows[key]=x
        definitions=dict(order=list(rows),pilot=spec['pilot'],groups=spec['groups'])
    files={}
    with gzip.open(REMOTE/(phase+'-inputs.jsonl.gz'),'xt',encoding='utf8',compresslevel=6) as out:
        for key,x in rows.items():
            path=folder/(key+'.json');write(path,x);files[key]=sha(path)
            out.write(json.dumps({'key':key,'value':x},separators=(',',':'),ensure_ascii=False)+'\n')
    manifest=dict(purpose=phase,seed=SEED if not engineering else None,freeze=sha(PK/'freeze.json'),
            holdout_commitment=load(PK/'holdout-commitment.json')['seed_sha256'],files=files,definitions=definitions,
            zipped=sha(REMOTE/(phase+'-inputs.jsonl.gz')),job=slurm())
    write(folder/'manifest.json',manifest)
    print(phase,len(files),sha(folder/'manifest.json'),manifest['zipped'],flush=True)


def retain(path,run,attachment):
    with gzip.open(path,'xt',encoding='utf8',compresslevel=1) as fp:
        def save(x):fp.write(json.dumps(x,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n')
        save(dict(metadata={k:v for k,v in run.items() if k not in ('trace','balances')},terminal=attachment))
        for left,b in zip(run['trace'],run['balances']):save(dict(sample=left,balance=b))
        save(dict(sample=run['trace'][-1]))


def a_checks(result,expected):
    target=expected['subject'];first=next((r for r in result['paid'] if r['task']==expected['required_sample']),None)
    renew=next((r for r in result['paid'] if r['task']==expected['renewal']),None)
    firsts=result['first'].get(target,{})
    verdict={'business_points':[result['checkpoints'][str(t)][target] for t in BIZ]==expected['states'],
        'real_primary':bool(first and first['sampled']==expected['primary_sample_end'] and first['arrived']==expected['primary_sample_arrival']
                       and first['fields'] is not None),
        'first_after_two_samples':bool(firsts and expected['earliest_legal_first']<=min(firsts.values())<=900)}
    if 'physical_witness' in expected:
        t,which,want=expected['physical_witness'];verdict['family_mechanism_reached']=result['physical_checkpoints'][t][which]==want
    if expected['renewal']:
        verdict['paid_renewal']=bool(renew and renew['sampled']==expected['renewal_sample_end'] and renew['arrived']==expected['renewal_arrival']
             and renew['parent']==expected['required_sample'] and renew['fields'] is not None and renew['until']>3600)
        if expected['states'][0]=='PV':
            a=next((q for q in result['writes'] if q['outcome']=='APPLIED' and q['subject']==target),None)
            verdict['actual_action_parent']=bool(a and a['at']==expected['first_action_end'] and first and renew and
                     first['execution']==renew['execution']==a['execution'] and first['physical_epoch']==renew['physical_epoch']==a['epoch'])
    else:
        verdict['real_expiry']=bool(first and first['until']==expected['expiry'] and not any(r['phase']=='X' for r in result['paid']))
    return verdict


def c_checks(result,expected):
    ev=result['attachment']['events']
    verdict={'full_LU':all(abs(v-expected['L'])<=TOL for v in (result['L'],result['U'])),
             'onset':result['first_loss']==expected['first'],'conservation':abs(result['attachment']['account']['residual_J'])<TOL}
    if 'submitted' in expected:verdict['explicit_hold']=not result['requests']
    for s,outcome in expected.get('writes',{}).items():
        verdict[s]=any(r['task']==s and r['outcome']==outcome for r in result['writes'])
    for s,fields in expected.get('reads',{}).items():
        verdict['read-'+s]=any(r['task']==s and r['fields'] and all(r['fields'].get(k)==v for k,v in fields.items()) for r in result['paid'])
    for item in expected.get('refused',[]):verdict['reject-'+str(item[0])]=item in result['refusals']
    for t,values in expected['at'].items():
        state=[z for z in ev if z['t']<=int(t)][-1]
        for k,v in values.items():verdict[t+'-'+k]=(state.get(k)==v)
    return verdict


def unit(phase,key,role,mh):
    if 'T3_CPU' in os.environ:os.sched_setaffinity(0,{int(os.environ['T3_CPU'])})
    spec,core=pinned();eng=phase=='engineering';inputs=REMOTE/(phase+'-inputs')
    insist(sha(inputs/'manifest.json')==mh,'committed complete input manifest')
    m=load(inputs/'manifest.json');f=inputs/(key+'.json')
    insist(m['freeze']==sha(PK/'freeze.json') and sha(f)==m['files'][key],'frozen source and input')
    data=load(f);x=data['input'] if eng else data
    from bounds import certificate_for,information
    from native import native_run
    from score_saved import score
    dest=REMOTE/'positions'/(key if eng else key+'-'+role);dest.mkdir()
    job=slurm();write(dest/'entry.json',dict(key=key,role=role,input=sha(f),manifest=mh,pid=os.getpid(),job=job,purpose=phase))
    cert=certificate_for(x) if role=='ORACLE' else None
    plan={int(t):v for t,v in data['plan'].items()} if eng else (cert['plan'] if cert else None)
    info=information(x,None,None) if role=='P' and not eng else None
    t0=time.monotonic();cpu=time.process_time()
    run,attached=native_run(x,role,plan,info['all_paid'] if info else ())
    raw=dest/'original.jsonl.gz';retain(raw,run,attached)
    result=score(x,run,attached,role)
    insist(result['runtime']==core['core_tree'],'native implementation identity')
    checks={}
    if eng:checks=a_checks(result,data['expect']) if key.startswith('A-') else c_checks(result,data['expect'])
    if cert:
        if cert['lower'] is None:
            # Only an identity network write is permissible and C cannot complete inside its grant.
            params={v['id']:v['value'] for v in x['native']['scenario']['parameters']}
            public=x['native']['dispatch_program']['public']
            insist(params['network_service_capacity']==1 and next(v['write_window'] for v in public['subjects'] if v['id']=='C/c0')==[1,2]
                   and not result['requests'],'no-effect physical bound')
            cert['lower']=result['L']
        cert['attained']=max(abs(result['L']-cert['lower']),abs(result['U']-cert['lower']))<=TOL
        cert['applied_as_planned']=all([t,task] in result['requests'] and
            any(q['task']==task and q['outcome']=='APPLIED' for q in result['writes'])
            and any(r['task']==task[:-1]+'R' and r['fields'] is not None for r in result['paid']) for t,task in cert['plan'].items())
        checks.update(legal_lower_bound=cert['attained'],real_own_chain=cert['applied_as_planned'])
    result.update(key=key,role=role,job=job,pid=os.getpid(),purpose=phase,manifest=mh,input_sha256=sha(f),raw_sha256=sha(raw),
           checks=checks,passed=all(checks.values()),oracle=cert,counterfactual_paid=run['t3_unpurchased_evaluator_only'],
           elapsed_s=time.monotonic()-t0,cpu_s=time.process_time()-cpu)
    write(dest/'result.json',result)
    print(key,role,result['L'],[k for k,v in checks.items() if not v],flush=True)
    if not result['passed']:raise SystemExit(2)


def batch(name,mh):
    spec,_=pinned();eng=name in ('A','C');phase='engineering' if eng else 'development'
    inputs=REMOTE/(phase+'-inputs');insist(sha(inputs/'manifest.json')==mh,'whole manifest')
    definition=load(inputs/'manifest.json')['definitions']
    if name=='C':insist(load(REMOTE/'A-terminal.json')['passed'],'A gate')
    if eng:tasks=[[k,'ENGINEERING'] for k in definition[name]]
    else:
        insist(load(REMOTE/'C-terminal.json')['passed'] and load(REMOTE/'A-terminal.json')['passed'],'engineering')
        tasks=definition['pilot'] if name=='pilot' else definition['groups'][name]
        if name!='pilot':insist(load(REMOTE/'pilot-account.json')['continue'],'pilot budget exceeded')
    n=int(os.environ['SLURM_CPUS_PER_TASK']);cpus=sorted(os.sched_getaffinity(0))
    insist(len(tasks)==n<=len(cpus),'registered CPUs')
    out=REMOTE/'batches'/name;out.mkdir()
    write(out/'started.json',dict(job=slurm(),manifest=mh,slots=tasks,cpus=n));started=time.monotonic()
    def one(pair):
        i,(key,role)=pair;env=dict(os.environ,T3_CPU=str(cpus[i]),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
        with (out/(key+'-'+role+'.log')).open('x') as fp:
            ret=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'unit',phase,key,role,mh],env=env,stdout=fp,stderr=subprocess.STDOUT)
        return [key,role,ret.returncode]
    with ThreadPoolExecutor(max_workers=n) as pool:results=list(pool.map(one,enumerate(tasks)))
    verdict=dict(job=slurm(),batch=name,manifest=mh,entries=results,passed=all(t[-1]==0 for t in results))
    write(out/'terminal.json',verdict)
    if eng:write(REMOTE/(name+'-terminal.json'),verdict)
    if not verdict['passed']:print(verdict,flush=True);raise SystemExit(2)
    if name=='pilot':
        parts=[load(REMOTE/'positions'/(k+'-'+r)/'result.json') for k,r in tasks]
        longest=max([time.monotonic()-started]+[v['elapsed_s'] for v in parts])
        mins=math.ceil((1.25*longest+15)/60)
        cpu_s=spec['dev_initial_reserved_CPU_s']+mins*60*282+spec['dev_read_reserved_CPU_s']
        jobs=len(definition['groups'])+3
        write(REMOTE/'pilot-account.json',dict(manifest=mh,**{'continue':jobs<=24 and cpu_s<=72000},
            pilot=tasks,elapsed=[v['elapsed_s'] for v in parts],cpu=[v['cpu_s'] for v in parts],
            max_wall_s=longest,limit_minutes=mins,projected_CPU_s=cpu_s,projected_jobs=jobs))
    print(verdict,flush=True)


if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare(sys.argv[2])
    elif sys.argv[1]=='unit':unit(*sys.argv[2:])
    else:batch(*sys.argv[1:])
