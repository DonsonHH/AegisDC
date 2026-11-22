"""Join actual saved runs. Independent condition bootstrap and main-vs-B and acquisition diagnostics."""
from collections import Counter
from statistics import mean
from common_v3 import *
from bounds import information
from analysis import interval

METHODS=('VSTAR','V_COST')
CONTROLS=('B','PA','PERIODIC','ALARM','BPLUS')
TICKS=('900','1800','2700','3600')
EPS=1e-7


def saved(phase,key,role,original=False):
    base=ACT/'positions'/(phase+'-'+key+'-'+role)
    paths=sorted(base.glob('*/score.json'));check(len(paths)==1,'exactly one returned score '+str(base))
    path=paths[0];s=read(path);d=path.parent;e=read(d/'entry.json');n=read(d/'native-entry.json')
    check(s['entry']==e and (e['phase'],e['key'],e['role'])==(phase,key,role) and n['pid']==e['pid']
        and s['worker_pid']==n['worker_pid'] and s['clocks']==61 and sha(ACT/(phase+'-inputs')/(key+'.json'))==e['input'],'entry and case')
    if original:
        raw=d/'original.jsonl.gz';check(s['raw']==sha(raw),'raw identity')
        with gzip.open(raw,'rt') as fp:record=json.loads(next(fp))
        meta=record['metadata'];dec=meta['policy_public_decisions'];pr=meta['v3_proposals']
        x=read(ACT/(phase+'-inputs')/(key+'.json'))
        if phase=='eng':x=x['case']
        check(meta['source_config']==x['native']['scenario'] and meta['inputs']['dispatch_program']==x['native']['dispatch_program']
              and meta['v3_received_maintenance']==x['maintenance'] and hash_obj(x['attachment'])==meta['t3_received_attachment_sha256'],'actual input')
        check([r['view']['time'] for r in dec]==list(range(0,3601,60)) and len(pr)==61,'clocks')
        if role in BUNDLE_NAMES:
            check(n['worker_pid']!=e['pid'] and hash_obj([[r['at'],r['view'],r['proposal']] for r in pr])==s['IPC'],'detached proposal IPC')
        check(all(q['view']==hash_obj(v['view']) for v,q in zip(dec,pr,strict=True)),'saved public view')
        check(s['maintenance']==meta['v3_maintenance_events'] and all(abs(v-w)<EPS for v,w in zip((s['L'],s['U']),s['integral_balances'],strict=True)),'score readback')
    s['score_sha256']=sha(path);return s


def gates(stage):
    pinned()
    if stage=='engineering':
        build=read(ACT/'eng-inputs/manifest.json')
        out={}
        for k in build['order']:
            s=saved('eng',k,'ENGINEERING',True)
            out[k]={f:s[f] for f in ('L','U','maintenance','locks','entry','raw','score_sha256','requests','expected')}
        item=dict(status='ALL_REGISTERED_NATIVE_FIXTURES_MET',job=job(),units=out,engineering_only=True,isolation=read(ACT/'isolation/result.json'))
        write(ACT/'engineering-accepted-by-checks.json',item)
        print(stage,len(out),flush=True);return
    m=read(ACT/'dev-inputs/manifest.json')
    role_list=('VSTAR',) if stage=='ref' else ('VSTAR','P','ORACLE','PERIODIC','ALARM','PA','B','BPLUS','VSTAR_NOPROBE')
    info={}
    for role in role_list:
        arms=[saved('dev',k,role) for k in m['order']]
        info[role]=dict(n=len(arms),L=mean(a['L'] for a in arms),person=mean(a['person'] for a in arms),
           initial_reads=sum(sum(s.endswith('::I') for _,s in a['requests']) for a in arms),
           wrong_service_exposures=sum(sum(q['until']>q['at'] for q in a['maintenance']) for a in arms),
           realized_lock_refusals=sum(len(a['locks']) for a in arms),scores=[a['score_sha256'] for a in arms])
    write(ACT/(stage+'-complete.json'),dict(job=job(),roles=info,next_rule='predeclared, not chosen from ranks'))
    print(stage,{k:(v['n'],round(v['L'],2),v['wrong_service_exposures']) for k,v in info.items()},flush=True)


def draws(rows,label):
    import numpy as np
    seed=int.from_bytes(hashlib.sha256(('AegisDC/T4c/paired/v1|'+label).encode()).digest()[:16],'big')
    gen=np.random.Generator(np.random.PCG64(seed))
    out=[]
    for fam in sorted({r['family'] for r in rows}):
        ids=np.array([i for i,r in enumerate(rows) if r['family']==fam])
        out.append(ids[gen.integers(0,len(ids),size=(10000,len(ids)))])
    return np.concatenate(out,axis=1)


def metrics(rows,role):
    arms=[r['arms'][role] for r in rows]
    phases=Counter(s.rsplit('::',1)[1] for a in arms for _,s in a['requests'])
    checks={typ:dict(ever=sum(typ in qq for a in arms for qq in a['first'].values()),
        current=[sum(q==typ for a in arms for q in a['checkpoints'][t].values()) for t in TICKS]) for typ in ('NA','PV')}
    return dict(**{k:mean(a[k] for a in arms) for k in ('L','U','person','tool','fee')},phases=dict(phases),
        subjects=sum(len(a['checkpoints']['3600']) for a in arms),closure=checks,
        harmful_periods=sum(sum(q['until']>q['at'] for q in a['maintenance']) for a in arms),
        with_harmful_periods=sum(any(q['until']>q['at'] for q in a['maintenance']) for a in arms),
        attained=sum(abs(a['L']-r['minimum'])<EPS for a,r in zip(arms,rows)),
        worse_than_P=sum(a['L']>r['arms']['P']['L']+EPS for a,r in zip(arms,rows)))


def paired(rows,method,comparator,ix):
    diffs={k:[r['arms'][method][k]-r['arms'][comparator][k] for r in rows] for k in ('L','U','person','tool','fee')}
    signs=[sum(v<-EPS for v in diffs['L']),sum(abs(v)<=EPS for v in diffs['L']),sum(v>EPS for v in diffs['L'])]
    return dict(**{k:interval(v,ix) for k,v in diffs.items()},directions=signs)


def scope(rows,label):
    ix=draws(rows,label)
    return dict(n=len(rows),by_role={r:metrics(rows,r) for r in ROLES},paired={v:{c:paired(rows,v,c,ix)
        for c in (*CONTROLS,v+'_NOPROBE')} for v in METHODS})


def previous():
    with gzip.open(T4/'development-result.json.gz','rt') as src:rows=json.load(src)['rows']
    z=[r for r in rows if r['layer']=='0000']
    return dict(n=len(rows),B_at_min=sum(abs(r['arms']['B']['L']-r['minimum'])<EPS for r in rows),
       B_worse_P=sum(r['arms']['B']['L']>r['arms']['P']['L']+EPS for r in rows),zero_rows=len(z),
       zero_acted=sum(any(s.endswith('::A') for _,s in r['arms']['B']['requests']) for r in z),
       zero_loss=sum(abs(r['arms']['B']['L'])<EPS for r in z),source=sha(T4/'development-result.json.gz'),
       by_family={f:dict(Counter(r['layer'] for r in rows if r['family']==f)) for f in sorted({r['family'] for r in rows})},
       layers=dict(Counter(r['layer'] for r in rows)))


def final():
    pinned();m=read(ACT/'dev-inputs/manifest.json');rows=[];units=[];pids=set()
    for key in m['order']:
        case=read(ACT/'dev-inputs'/(key+'.json'));arms={r:saved('dev',key,r,True) for r in ROLES}
        p=arms['P'];o=arms['ORACLE'];tau=o['oracle']['latest_best'];inf=information(case,p,tau)
        for u in inf['all_paid']:
            check(any(q['subject']==u[2] and q['sampled']==u[4] and q['would_arrive']==u[0] and q['usable']==u[1] and q['fields']
                for q in p['independent_information']),'P-only physically checked paid opportunity')
        check(o['oracle']['native_attained'] and all(a['L']>=o['L']-EPS for a in arms.values()),'all arms above certified legal minimum')
        if 'protected_only' in o['oracle']:check(abs(p['L']-o['oracle']['protected_only'])<EPS,'mechanical no-action result')
        if o['oracle']['proof'].startswith('Both available'):check(p['curve']==o['curve'],'identity-only bound')
        layer=''.join('1' if v else '0' for v in (p['L']>EPS,p['L']>o['L']+EPS,inf['c1'],inf['c2']))
        for role,s in arms.items():
            e=s['entry'];pid=(e['job'],e['pid']);check(pid not in pids,'independent unit');pids.add(pid)
            units.append(dict(key=key,role=role,job=e['job'],attempt=e['attempt'],input=e['input'],raw=s['raw'],score=s['score_sha256'],IPC=s['IPC']))
            for field in ('curve','public_prefix','independent_information'):s.pop(field)
        rows.append(dict(key=key,family=case['evaluation']['family'],layer=layer,minimum=o['L'],deadline=tau,
                         information=inf,duration=case['maintenance']['exposure_s'],arms=arms))
    check(len(rows)==72 and len(units)==792,'full denominators')
    scopes={'overall':scope(rows,'overall')};families=sorted({r['family'] for r in rows});layers=sorted({r['layer'] for r in rows})
    for field,vals in [('family',families),('layer',layers)]:
        for v in vals:
            tag=field+'/'+v;scopes[tag]=scope([r for r in rows if r[field]==v],tag)
    acquisition={}
    for v in METHODS:
        items=[]
        for r in rows:
            arm=r['arms'][v];other=r['arms'][v+'_NOPROBE']
            if any(s.endswith('::I') for _,s in arm['requests']):
                items.append(dict(key=r['key'],family=r['family'],layer=r['layer'],
                    treatment={k:arm[k] for k in ('L','U','person','tool','fee','requests','paid')},
                    ablation={k:other[k] for k in ('L','U','person','tool','fee','requests')},
                    delta={k:arm[k]-other[k] for k in ('L','U','person','tool','fee')}))
        acquisition[v]=dict(rows=items,conditional_means={k:mean(z['delta'][k] for z in items) if items else None for k in ('L','U','person','tool','fee')})
    denominator=sum(r['arms']['P']['L']-r['minimum'] for r in rows)
    out=dict(schema='T4c-seen-development-v3',inputs=m,rows=rows,units=units,scopes=scopes,old_v2=previous(),acquisition=acquisition,
        direct_optimal_positive=[r['key'] for r in rows if r['minimum']+EPS<r['arms']['P']['L'] and abs(r['arms']['B']['L']-r['minimum'])<EPS],
        remaining_gap={v:dict(numerator=sum(r['arms'][v]['L']-r['minimum'] for r in rows),denominator=denominator,
                         ratio=sum(r['arms'][v]['L']-r['minimum'] for r in rows)/denominator if denominator else None) for v in METHODS},
        compare_layers={f:dict(Counter(r['layer'] for r in rows if r['family']==f)) for f in families},
        holdout=dict(user_commitment=None,generated=0,executed=0,results_accessed=0),job=job(),primary='V_COST minus B')
    gzwrite(ACT/'development.json.gz',out)
    from tables_v3 import render
    render(out)
    print('primary',scopes['overall']['paired']['V_COST']['B'],flush=True)

if __name__=='__main__':
    if sys.argv[1]=='final':final()
    else:gates(sys.argv[1])
