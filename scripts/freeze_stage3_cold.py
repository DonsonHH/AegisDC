"""Author public cold input documents. No candidate policy, evaluator or facility imports."""
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
import gzip
import hashlib
import json
import os
import sys

ROOT=Path(__file__).resolve().parents[1]
PK='docs/mainline/v6-stage-three-cold-v2'
OLD='docs/mainline/v6-joint-engineering-v1'
SOURCE_SHA='d7f3a8e1bd681427e05ea5072cf10b94df9ddc88ffed49a9f5fbc268385e5ea9'


def packed(v):
    return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()


def sha(b):
    return hashlib.sha256(b).hexdigest()


def doc(p):
    return json.loads(p.read_bytes())


def write(p,data):
    with p.open('xb') as stream:stream.write(data)


def input_doc(old,row,method):
    x=deepcopy(old['S12']);p={r['id']:r for r in x['scenario']['parameters']}
    for name,field in [('filter_resistance_multiplier','filter'),('network_service_capacity','network'),
                       ('storage_service_capacity','storage'),('rectifier_capacity','rectifier_input_W')]:
        p[name]['value']=row[field]
    prog=x['dispatch_program'];cfg=prog['policy_program'];law=row.get('law',row.get('public_law'))
    donor={'COZERO':'P03-J','EXZERO':'P04-J','EX50':'P06-J','BOTH':'P05-J','N_EQ':'S03'}[law]
    template=old[donor]
    orig=template['program'] if 'program' in template else template['dispatch_program']['policy_program']
    cfg.update(method=method,caps=deepcopy(row['budget']),worlds=deepcopy(orig['worlds']))
    expiry=row.get('N_expiry',12);cfg['types']['N']['write']=[0,expiry]
    cfg['types']['N']['require_probe']=row.get('require_probe',row.get('N_write')=='positive_probe')
    for grant in prog['intervention_program']['profile']['authorizations']:
        if grant['id']=='grant-N':grant['expires_at_s']=expiry
    for r in prog['order_channel']:
        t=.5 if row['opening']=='SYNC_HALF' else (0 if r['target']=='network' else 1)
        r.update(at=t,arrived=t)
    x['private_physical_audit']=True
    return x


def snapshot(doc,case):
    cfg=deepcopy(doc['dispatch_program']['policy_program']);cfg['method']=case['method']
    if case['setup']=='one_order':cfg['types']['N']['write']=[0,2]
    t=case['time'];orders=deepcopy([r for r in doc['dispatch_program']['order_channel'] if r['arrived']<=t])
    view=dict(time=t,orders=orders,issued=[],work=[],writes=[],paid=[],fixed=[])
    if case['setup']=='pending_N':
        view['issued']=[dict(task='N/n0/A',at=0,release=0,planned_end=1.25,planned_ack=1.75)]
    if case['setup']=='supply_read':
        task='N/n0/I';bundle=task+'@1.75'
        view['issued']=[dict(task=task,at=.5,release=.5,planned_end=1.75,planned_ack=2.25)]
        view['work']=[dict(task=task,status='completed',at=1.75,arrived=2.25,worker='worker_it',tool='tool_it_diagnostic',
                           location='loc_it',origin='workforce:'+task)]
        for field,value in [('g',1),('e',.25)]:
            view['paid'].append(dict(task=task,instance='N/n0',phase='I',field=field,target='network',unit='1',interval=[value,value],
                at=1.75,arrived=2.25,until=9.75,bundle=bundle,origin='paid:'+bundle,source='onsite-N',disposition='MEASURED'))
    return dict(config=cfg,view=view)


def projection(physics_m,network,storage=100):
    return dict(params=[physics_m,network],flow=[.05 if physics_m==4 else .1,.12],heat=10 if physics_m==4 else 20,
        service=[1,network,1,network,1],protection=[False,True],stocks={'cold':storage,'hot':150,'solid':10,'coolant':50})


def sample_score(effects=(),cert=False):
    points=[];m=4;g=.25;profile=[];L=Fraction(0)
    for t in range(13):
        left=projection(m,g)
        for when,k,old,new in effects:
            if t==when:
                if k=='C':m=new
                else:g=new
        right=projection(m,g)
        points.append(dict(t=t,left=left,before=deepcopy(left),right=right,dt=1,tol=.01))
        if t<12:
            L+=1-Fraction(g)
            if profile and profile[-1][-1]==g:profile[-1][1]=t+1
            else:profile.append([t,t+1,1,g])
    opens={'C/c0':0,'N/n0':0}
    states={str(t):{name:'OPEN' for name in opens} for t in (0,5,7.5,12)}
    if cert:states['7.5']['N/n0']='POST_ACTION_VERIFIED_CURRENT'
    return dict(status='OK',physical_id='paired-stub',public_id='same-design',runtime='saved-stub',horizon=12,
        audit=points,effects=[list(e) for e in effects if e[2]!=e[3]],unknown_effects=[],
        service=dict(balance=[str(L)]*2,rate=[str(L)]*2,curve=profile),resources=[2,2,2],opened=opens,
        states=states,first={'N/n0':{'PV':7.5}} if cert else {},decisions=[],violations=[])


def evaluator_fixtures():
    common=(2,'N',.25,1);different=(8,'C',4,1)
    a=sample_score([common,different]);b=sample_score([common])
    # A shared discrete update between the true left and pre-manual faces.
    for stub in (a,b):
        stub['audit'][8]['before']['heat']+=2
        stub['audit'][8]['right']['heat']+=2
    cases={}
    def pair(key,l,r,expect):
        cases[key]=dict(op='pair',left=deepcopy(l),right=deepcopy(r),expected=expect)
    pair('left-good',a,b,dict(category='SAME',t_star=2,t_delta=8,through=8))
    bad=deepcopy(a);bad['audit'][8]['left']['stocks']['cold']+=1
    pair('left-wrong',bad,b,dict(category='NUMERIC_UNRESOLVED',reason='PREFIX_STATE',time=8,face='left'))
    bad=deepcopy(a);del bad['audit'][8]['left']
    pair('left-absent',bad,b,dict(category='NUMERIC_UNRESOLVED',reason='MISSING_FACE',time=8,face='left'))
    bad=deepcopy(a);bad['audit'][8]['before']['stocks']['cold']+=1
    pair('before-wrong',bad,b,dict(category='NUMERIC_UNRESOLVED',reason='PREFIX_STATE',time=8,face='before'))
    bad=deepcopy(a);del bad['audit'][8]['before']
    pair('before-absent',bad,b,dict(category='NUMERIC_UNRESOLVED',reason='MISSING_FACE',time=8,face='before'))
    bad=deepcopy(a);bad['audit'][4]['right']['stocks']['hot']+=1
    pair('drift-after-common',bad,b,dict(category='NUMERIC_UNRESOLVED',reason='PREFIX_STATE',time=4,face='right'))
    bad=deepcopy(a);bad['audit'][2]['right']['heat']+=1
    pair('common-right',bad,b,dict(category='NUMERIC_UNRESOLVED',reason='PREFIX_STATE',time=2,face='right'))
    nothing=sample_score([(1,'C',4,4)]);bad=deepcopy(nothing);bad['audit'][11]['left']['stocks']['solid']+=1
    pair('late-noop-drift',bad,nothing,dict(category='NUMERIC_UNRESOLVED',reason='PREFIX_STATE',time=11,face='left',t_delta=None))
    bad=deepcopy(a);extra=deepcopy(bad['audit'][3]);extra['t']=3.25;bad['audit'].insert(4,extra)
    pair('unmatched-mesh',bad,b,dict(category='NUMERIC_UNRESOLVED',reason='PENDING_TRANSFER_GRID'))
    l=sample_score();r=sample_score(cert=True);l['states']['7.5']['N/n0']='NO_ACTION_CURRENT';l['first']={'N/n0':{'NA':7.5}}
    l['service']['balance']=[str(Fraction(9)+Fraction(1,2**40))]*2;l['resources']=[1,3,1]
    pair('tie-tail-and-typed-loss',l,r,dict(category='SAME',resources='MIXED',closures_preserved=False,t_star=None,t_delta=None,through=12))
    cases['different-curves-zero']=dict(op='service',left=dict(balance=['6','6'],rate=['6','6'],curve=[[0,6,1,0],[6,12,1,1]]),
        right=dict(balance=['6','6'],rate=['6','6'],curve=[[0,6,1,1],[6,12,1,0]]),expected={'category':'SAME'})
    cases['conflicting-directions']=dict(op='service',left=dict(balance=['6','6'],rate=['6','6'],curve=[[0,6,1,0],[6,12,1,1]]),
        right=dict(balance=[str(Fraction(6)+Fraction(1,2**40))]*2,rate=[str(Fraction(6)-Fraction(1,2**40))]*2,curve=[[0,6,1,1],[6,12,1,0]]),
        expected={'category':'NUMERIC_UNRESOLVED'})
    bad=deepcopy(a);bad['violations']=['physical action outside its grant']
    pair('hard-violation',bad,b,dict(category='NONCOMPLIANT'))
    bad=deepcopy(a);bad['unknown_effects']=['undeclared manual physical effect']
    pair('unknown-side-effect',bad,b,dict(category='NUMERIC_UNRESOLVED',reason='PENDING_TRANSFER_EFFECT'))
    return cases


def build(out):
    out.mkdir(exist_ok=False);plan=doc(ROOT/PK/'engineering-plan.json');matrix=doc(ROOT/PK/'conditions.json')
    raw=(ROOT/OLD/'inputs.json.gz').read_bytes()
    if sha(raw)!=SOURCE_SHA:raise ValueError('Historical public engineering freeze mismatch')
    old=json.loads(gzip.decompress(raw))
    eng={g['id']+'-'+m:input_doc(old,g,m) for g in plan['groups'] for m in g['arms']}
    study={r['id']+'-'+m:input_doc(old,r,m) for r in matrix['core_rows'] for m in r['arms']}
    rows={r['id']:r for r in matrix['core_rows']}
    direct={c['id']:snapshot(input_doc(old,rows[c['row']],c['method']),c) for c in plan['direct']}
    expected=dict(arms=plan['arms'],chains=plan['chains'],pairs=plan['pairs'],direct=plan['direct'],
                  evaluators=evaluator_fixtures(),schedule=plan['jobs'],limits=plan['limits'],counts=plan['scheduled'])
    def order_case(key, prefix, timings, admitted, wanted):
        seqs=[['C/c0/A','N/n0/A'],['N/n0/A','C/c0/A']]
        options=[]
        for seq,chain,ok in zip(seqs,timings,admitted):
            release={k[:-1]+'R':end+.5 for k,t,end in chain if k.endswith('/A')}
            steps=[dict(task=k,at=t,planned_end=end,planned_ack=end+.5,release=release.get(k,0)) for k,t,end in chain]
            options.append(dict(seq=seq,plan=dict(steps=steps,admitted=ok)))
        return dict(id=key,config=dict(types={k:{f:t[f] for f in ('asset','work_s')} for k,t in direct['D5']['config']['types'].items()}),options=options,wanted=wanted,prefix=prefix)
    common=[('N/n0/I',0,1.25)]
    arms1=[common+[('C/c0/A',1.75,5),('N/n0/A',2,3.25),('N/n0/R',3.75,5),('C/c0/R',5.5,6.75)],
           common+[('N/n0/A',1.75,3),('C/c0/A',2,5.25),('N/n0/R',3.5,4.75),('C/c0/R',5.75,7)]]
    arms2=[[('C/c0/A',1,4.25),('N/n0/A',1.25,2.5),('N/n0/R',3,4.25),('C/c0/R',4.75,6)],
           [('N/n0/A',1.25,2.5),('C/c0/A',1.5,4.75),('N/n0/R',3,4.25),('C/c0/R',5.25,6.5)]]
    expected['order_cases']=[order_case('O-branch-travel','common paid probe',arms1,[True,True],'N/C'),
        order_case('O-first-ready','none',arms2,[True,True],'C/N'),order_case('O-only-feasible','none',arms2,[False,True],'N/C')]
    # These are standalone post-admission order reductions, not plant or budget examples.
    expected['mock_runner']=dict(order=['r1','r2','r3'],scripted_returns=['OK','EXCEPTION'],started=['r1','r2'],
        missing=['r3'],reuse='REFUSED',purpose='ENGINEERING_STUB',denials=['STUDY_UNAUTHORIZED','INPUT_HASH'])
    expected['panel_fixture']=dict(primary={'A01':'BETTER','A02':'WORSE','A03':'SAME','A04':'NUMERIC_UNRESOLVED','A05':'NONCOMPLIANT'},
        mechanism={'A01-J_NO_PROBE':'SAME'},counts={'BETTER':1,'WORSE':1,'SAME':1,'NUMERIC_UNRESOLVED':1,'NONCOMPLIANT':1,'NO_PAIR':19},
        denominators={'J/B':24,'J_OPEN':4,'J_NO_PROBE':10,'J_ORDER':4},planned=66,dominance=False)
    for name,items in [('engineering-inputs',eng),('study-inputs',study)]:
        write(out/(name+'.json.gz'),gzip.compress(packed(items),mtime=0))
    write(out/'direct.json',packed(direct));write(out/'expected.json',packed(expected))
    by_doc={name:sha((out/name).read_bytes()) for name in ('engineering-inputs.json.gz','study-inputs.json.gz','direct.json','expected.json')}
    manifest=dict(purpose='PREIMPLEMENTATION_INPUT_FREEZE',engineering={k:sha(packed(v)) for k,v in eng.items()},
        study={k:sha(packed(v)) for k,v in study.items()},direct={k:sha(packed(v)) for k,v in direct.items()},files=by_doc,
        plan_sha256=sha((ROOT/PK/'engineering-plan.json').read_bytes()),matrix_sha256=sha((ROOT/PK/'conditions.json').read_bytes()),author_sha256=sha(Path(__file__).read_bytes()))
    if len(eng)!=16 or len(study)!=66 or len(direct)!=9:raise ValueError('Frozen denominators')
    write(out/'input-freeze.json',packed(manifest))
    return direct,plan


def start_freeze(out,release_sha):
    release=ROOT/'release.json'
    if sha(release.read_bytes())!=release_sha:raise ValueError('Materialization release identity')
    pin=doc(release)
    if (pin['purpose']!='PUBLIC_ENGINEERING' or out.resolve()!=Path(pin['activity'])/'F0'/'frozen'
            or os.environ.get('SLURM_CPUS_PER_TASK')!='1'):raise PermissionError('Incorrect F0 activity or allocation')
    for f,h in pin['files'].items():
        if sha((ROOT/f).read_bytes())!=h:raise ValueError('F0 file differs: '+f)
    phase=out.parent
    write(phase/'started.lock',packed(dict(job=os.environ['SLURM_JOB_ID'],revision=pin['revision'],release=release_sha)))
    journal=phase/'calls.jsonl';counts=dict(component=0,direct=0,facility=0,internal=0);rows=[]
    def enter(key,kind):
        with journal.open('a') as stream:stream.write(json.dumps([key,kind])+'\n')
        counts[kind]+=1
    try:
        enter('freeze','component');direct,plan=build(out);rows.append(['freeze','OK'])
        from aegis_dc import joint_policy
        if Path(joint_policy.__file__).resolve() != (ROOT/'src/aegis_dc/joint_policy.py').resolve():
            raise ValueError('Old policy module path differs from frozen export')
        for name in plan['red']:
            enter(name,'direct')
            try:joint_policy.choose(direct[name]['config'],direct[name]['view'])
            except ValueError as e:
                if str(e)!='Joint token':raise
                rows.append([name,'Joint token'])
            else:raise ValueError('Old version accepted a new method')
    except Exception as exc:
        write(phase/'result.json',packed(dict(status='FAILED',error=repr(exc),rows=rows,counts=counts,
             job=os.environ['SLURM_JOB_ID'],revision=pin['revision'],uncompleted=[k for k in ['freeze','D1','D4','D5'] if k not in {r[0] for r in rows}])))
        raise
    receipt=dict(status='EXPECTED_PRIOR_REJECTIONS',counts=counts,rows=rows,uncompleted=[],job=os.environ['SLURM_JOB_ID'],revision=pin['revision'],release_sha256=release_sha)
    write(out/'red.json',packed(receipt));write(phase/'result.json',packed(receipt))


if __name__=='__main__':
    if not os.environ.get('SLURM_JOB_ID'):raise PermissionError('Use the frozen F0 allocation')
    start_freeze(Path(sys.argv[1]),sys.argv[2])
