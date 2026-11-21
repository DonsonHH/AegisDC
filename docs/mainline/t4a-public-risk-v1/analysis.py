"""Predeclared paired condition bootstrap. Reads only scored development material on Slurm."""
from collections import Counter
import gzip
import hashlib
import os
import sys
import json
import numpy as np
from bridge import *

VERSIONS=('V1','V2','V3')
CONTROLS=('PERIODIC','ALARM','PA','B')
TICKS=('900','1800','2700','3600')
EPS=1e-7
ROOT_SEED='AegisDC/T4a/paired-bootstrap/v1|'


def source():
    with gzip.open(T3/'development-result.json.gz','rt') as f:return json.load(f)


def saved(key,role):
    path=ACTIVITY/'positions'/(key+'-'+role)
    score=read(path/'result.json');entry=read(path/'native-entry.json')
    require(score['role']==role and score['key']==key and score['entry']['input_sha256']==inputs()['files'][key]
            and score['entry']['job']==entry['job'] and score['entry']['pid']==entry['pid'] and
            entry['worker_pid']==score['worker_pid'] and score['public_calls']==61
            and score['entry']['method_release']==sha(PK/'freeze.json'),'record identity '+key+role)
    return score


def records(upto):
    panel=source();out=[]
    for r in panel['rows']:
        arms={k:r['arms'][k] for k in ('P','PERIODIC','ALARM','ORACLE')}
        arms.update({k:saved(r['key'],k) for k in ('PA','B',*VERSIONS[:upto])})
        out.append(dict(key=r['key'],family=r['family'],layer=r['layer'],minimum=r['minimum'],frozen_T4=r['T4'],arms=arms))
    return out


def diagnostic(rows,version):
    more=[];worse=[];noops=[];nohead=[];missed=[];waiting=0
    for r in rows:
        v=r['arms'][version];p=r['arms']['PA'];k=r['key']
        if v['person']>p['person']+EPS:more.append(k)
        if v['L']>p['L']+EPS:worse.append(k)
        if any(a[-2]=='NO_EFFECT' or not a[-1] for a in v['actual_actions']):noops.append(k)
        if v['fee'] and r['arms']['P']['L']<=EPS:nohead.append(k)
        if v['L']>r['minimum']+EPS:missed.append(k)
        waiting+=v['policy_audit']['zero_support_ticks']
    return dict(higher_person_than_PA=more,higher_loss_than_PA=worse,ineffective_or_equal_write_rows=noops,
                paid_with_zero_P_loss=nohead,above_oracle=missed,unsupported_public_ticks=waiting)


def interstage(number):
    rows=records(number);v=VERSIONS[number-1];d=diagnostic(rows,v)
    why=('V1 diagnoses excess work, equal writes and paid work where P has no loss. V2 increases the prior price to test cost suppression.'
         if number==1 else 'V2 diagnoses service left unserved at high price and residual ineffective work. V3 is the prior-designated intermediate price.')
    result=dict(stage=number,complete=True,conditions=[r['key'] for r in rows],current_version=v,
        diagnosis=d,change_basis=why,next_version=VERSIONS[number],only_edit='lambda',next_price=4 if number==1 else 1,
        source_sha256=sha(PK/'freeze.json'),version_results={r['key']:sha(ACTIVITY/'positions'/(r['key']+'-'+v)/'result.json') for r in rows})
    write(ACTIVITY/f'stage-{number}.json',result)
    print(v,{k:len(vals) if isinstance(vals,list) else vals for k,vals in d.items()},flush=True)


def indices(rows,scope):
    seed=int.from_bytes(hashlib.sha256((ROOT_SEED+scope).encode()).digest()[:16],'big')
    rng=np.random.Generator(np.random.PCG64(seed));families=sorted({r['family'] for r in rows})
    draws=[]
    for f in families:
        ids=np.asarray([i for i,r in enumerate(rows) if r['family']==f])
        draws.append(ids[rng.integers(0,len(ids),size=(10000,len(ids)))])
    return np.concatenate(draws,axis=1)


def interval(values,draws):
    v=np.asarray(values,dtype=float);means=v[draws].mean(axis=1)
    return dict(mean=float(v.mean()),lo=float(np.percentile(means,2.5,method='linear')),hi=float(np.percentile(means,97.5,method='linear')))


def operations(arm):
    if 'actual_actions' in arm:return len(arm['actual_actions'])
    return sum(1 for t,task in arm['requests'] if task.endswith('::A'))


def stat(rows,arm):
    values=[r['arms'][arm] for r in rows]
    metrics={k:float(np.mean([q[k] for q in values])) for k in ('L','U','person','tool','fee')}
    metrics['actions']=sum(operations(q) for q in values)
    metrics['initial_reads']=sum(sum(1 for _,s in q['requests'] if s.endswith('::I')) for q in values)
    metrics['work_orders']=sum(len(q['checkpoints']['3600']) for q in values)
    metrics['closure']={typ:dict(ever=sum(typ in types for q in values for types in q['first'].values()),
        current=[sum(z==typ for q in values for z in q['checkpoints'][t].values()) for t in TICKS]) for typ in ('NA','PV')}
    metrics['above_minimum']=sum(q['L']>r['minimum']+EPS for q,r in zip(values,rows))
    metrics['mean_gap']=float(np.mean([q['L']-r['minimum'] for q,r in zip(values,rows)]))
    if all('actual_actions' in q for q in values):
        metrics['no_effect']=sum(a[3]=='NO_EFFECT' for q in values for a in q['actual_actions'])
        metrics['equal_writes']=sum(a[3]=='APPLIED' and not a[4] for q in values for a in q['actual_actions'])
    return metrics


def scope_result(rows,label,versions=VERSIONS):
    n=len(rows);draws=indices(rows,label)
    roles=(*CONTROLS,*versions,'P','ORACLE')
    record=dict(scope=label,n=n,keys=[r['key'] for r in rows],by_role={a:stat(rows,a) for a in roles},paired={})
    for v in versions:
        record['paired'][v]={}
        for c in CONTROLS:
            vals={k:[r['arms'][v][k]-r['arms'][c][k] for r in rows] for k in ('L','U','person','tool','fee')}
            pair={k:interval(vs,draws) for k,vs in vals.items()}
            pair['directions']=[sum(d < -EPS for d in vals['L']),sum(abs(d)<=EPS for d in vals['L']),sum(d>EPS for d in vals['L'])]
            record['paired'][v][c]=pair
    return record


def ratios(rows,v):
    numerator=sum(r['arms'][v]['L']-r['minimum'] for r in rows)
    answer={}
    for k in ('P','PA'):
        denom=sum(r['arms'][k]['L']-r['minimum'] for r in rows)
        answer[k]=dict(numerator=numerator,denominator=denom,ratio=numerator/denom if denom>EPS else None)
    return answer


def final():
    rows=records(3);family=sorted({r['family'] for r in rows});layers=sorted({r['layer'] for r in rows})
    scopes=[('overall',rows)]+[('family/'+f,[r for r in rows if r['family']==f]) for f in family]
    scopes.extend(('layer/'+l,[r for r in rows if r['layer']==l]) for l in layers)
    # Also preserve disaggregated intersections, including diagnosis of a family-level single-row re-sample.
    for f in family:
        for l in layers:
            rr=[r for r in rows if r['layer']==l and r['family']==f]
            if rr:scopes.append(('family-layer/'+f+'/'+l,rr))
    metrics={name:scope_result(items,name) for name,items in scopes}
    avgs=metrics['overall']['by_role'];primary=metrics['overall']['paired']['V3']['PA']
    rowwise=sum(min(r['arms']['PERIODIC']['L'],r['arms']['ALARM']['L']) for r in rows)/len(rows)
    include=('key','role','entry','worker_pid','static_public','IPC_sha256','source_runtime','L','U','balance','person','tool','fee',
             'first','checkpoints','closure_changes','requests','refusals','work','paid','writes','actual_actions','policy_audit','public_calls','raw_sha256','elapsed_s')
    published=[]
    for r in rows:
        out={k:v for k,v in r.items() if k!='arms'}
        out['arms']={}
        for k,v in r['arms'].items():
            out['arms'][k]={f:v[f] for f in include if f in v}
            if k in ARMS:out['arms'][k]['score_sha256']=sha(ACTIVITY/'positions'/(r['key']+'-'+k)/'result.json')
        published.append(out)
    results=dict(schema='T4a-public-development-v1',scope='72 previously disclosed development conditions',order=[r['key'] for r in rows],
        unique_positions=360,bootstrap=dict(repeats=10000,unit='condition within family',percentiles=[2.5,97.5],seed_text=ROOT_SEED),
        prior_offline_rowwise_best_L=rowwise,scopes=metrics,diagnoses={v:diagnostic(rows,v) for v in VERSIONS},
        frozen_main='V3',development_primary_components=dict(upper_CI_below_zero=primary['L']['hi']<0,person_no_higher=avgs['V3']['person']<=avgs['PA']['person']),
        remaining_gap_ratio={v:ratios(rows,v) for v in VERSIONS},rows=published,holdout_runs=0,RSI_runs=0)
    with (ACTIVITY/'development-result.json.gz').open('xb') as out:
        out.write(gzip.compress((json.dumps(results,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode(),compresslevel=6,mtime=0))
    print('paired primary',primary,'observed',results['development_primary_components'],'rowwise',rowwise,flush=True)


if __name__=='__main__':
    frozen()
    if sys.argv[1]=='final':final()
    else:interstage(int(sys.argv[1]))
