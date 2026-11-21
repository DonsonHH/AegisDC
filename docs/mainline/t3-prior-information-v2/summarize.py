"""Join sealed returns only. Form strata from P, oracle and timed information before joining either human baseline."""
from collections import Counter,defaultdict
from fractions import Fraction
import gzip
import json
from statistics import median,mean
import sys
from common import *
from bounds import EPS,information,starts,entries,duration,london_loss,netherlands_loss

def position(k,role,manifest,files):
    d=REMOTE/'positions'/(k+'-'+role);e=load(d/'entry.json');a=load(d/'result.json')
    insist(a['passed'] and e['input']==a['input_sha256']==files[k] and e['manifest']==a['manifest']==manifest
          and (k,role,e['job'],e['pid'])==(a['key'],a['role'],a['job'],a['pid']) and a['clocks']==61,'position '+k+role)
    raw=d/'original.jsonl.gz';insist(sha(raw)==a['raw_sha256'],'stored original '+k+role)
    a['score_sha256']=sha(d/'result.json')
    return a


def incident_options(x):
    c=x['attachment'];pub=x['native']['dispatch_program']['public'];subs=entries(pub);out={}
    if not c:return out
    for sid,s in subs.items():
        ts=starts(pub,s);d=duration(pub,s,s['start'])
        if c['kind']=='LONDON':
            base=london_loss(c);can=[t for t in ts if c['fault_at'] is not None and t+d<c['fault_at']]
            best=london_loss(c,s['operation']) if can else base
        else:
            base=netherlands_loss(c,{})
            if sid=='NC':ts=[t for t in ts if c['handover'] and t>=90]
            if sid=='NP':ts=[t for t in ts if c['fault_at'] is not None and t>=c['restore_at']+15]
            best=min([base]+[netherlands_loss(c,{sid:t+d}) for t in ts])
        out[s['operation']]=dict(best_alone_L=best,reduces_relative_to_P=best<base-EPS)
    return out


def dist(values):
    return dict(min=min(values),median=median(values),max=max(values),mean=mean(values),positive=sum(v>EPS for v in values))


def metrics(group):
    out={}
    for mode in ROLES:
        arms=[r['arms'][mode] for r in group];h={}
        for typ in ('NA','PV'):
            h[typ]=dict(ever=sum(typ in phases for arm in arms for phases in arm['first'].values()),
                current_by_business_tick=[sum(v==typ for arm in arms for v in arm['checkpoints'][str(t)].values()) for t in BIZ])
        out[mode]=dict(**{k:dist([arm[k] for arm in arms]) for k in ('L','U','person','tool','fee')},
            closure=h,work_order_denominator=sum(len(arm['checkpoints']['3600']) for arm in arms),
            gap=dist([r['arms'][mode]['L']-r['minimum'] for r in group]))
    return out


def main(mh):
    slurm();folder=REMOTE/'development-inputs';m=load(folder/'manifest.json')
    insist(sha(folder/'manifest.json')==mh and m['freeze']==sha(PK/'freeze.json') and
         m['holdout_commitment']==load(PK/'holdout-commitment.json')['seed_sha256'],'frozen panel')
    rows=[];pids=set();pairs=defaultdict(list);prior_law=defaultdict(lambda:[0,0]);role_ids=Counter()
    assembly=load(PK/'freeze.json')
    def minimal(a):
        return {k:v for k,v in a.items() if k not in ('public_prefix','fixed')}
    for k in m['definitions']['order']:
        f=folder/(k+'.json');insist(sha(f)==m['files'][k],'whole condition '+k);x=load(f);ev=x['evaluation']
        p=position(k,'P',mh,m['files']);o=position(k,'ORACLE',mh,m['files']);cert=o['oracle']
        insist(cert['attained'] and cert['applied_as_planned'] and p['L']+EPS>=o['L'],'certified minimum '+k)
        if 'protected_only' in cert:insist(abs(cert['protected_only']-p['L'])<EPS,'independent P bound '+k)
        if cert['proof'].startswith('all permitted'):insist(p['curve']==o['curve'],'no-effect proof')
        tau=cert['latest_best'];info=information(x,p,tau)
        unpaid=p['counterfactual_paid']
        insist(len(unpaid)==len(info['all_paid']) and all(any(
            z['subject']==u[2] and z['sampled']==u[4] and z['would_arrive']==u[0] and z['usable']==u[1] and z['fields']
            for z in unpaid) for u in info['all_paid']),'lawful evaluator-only paid sample '+k)
        a=p['L']>EPS;b=p['L']-o['L']>EPS
        c1=info['c1'];c2=info['c2'];layer=''.join(str(int(z)) for z in (a,b,c1,c2))
        if not b:insist(not c1 and not c2 and tau is None,'timing without headroom')
        rows.append(dict(key=k,family=ev['family'],draw=ev['draw'],cell=ev['cell'],degraded=ev['degraded'],context=ev['context'],
            layer=layer,a=a,b=b,c1=c1,c2=c2,info=info,minimum=cert['lower'],latest=tau,
            partial=bool(b and o['L']>EPS),scope=cert['proof'],certified_plan=cert['plan'],looser_last_gain=cert['latest_possible_gain'],
            native_P_first_loss=p['first_loss'],prior_records=[r for r in x['native']['dispatch_program']['channel'] if r['kind']=='prior'],
            incident_single_action_bounds=incident_options(x),unpaid_native_no_action_projection=unpaid,arms={'P':minimal(p),'ORACLE':minimal(o)}))
        if ev['pair']:
            pairs[ev['family']].append(dict(key=k,config=digest(x['native']['dispatch_program']['public']),
               scheduled_prior=digest(x['native']['dispatch_program']['channel']),private=digest([x['native']['scenario'],x['attachment']]),
               view=p['public_prefix'],plan=cert['plan'],L=p['L'],Lstar=o['L']))
        for q in ev['prior_draw']:
            z=prior_law[(ev['family'],q['type'],q['degraded'],q['context'],q['p'])];z[0]+=1;z[1]+=int(q['appears'])
    targets=[];subtargets=[];full=[];denom=Counter();reasons=Counter()
    for r in rows:
        k=r['key']
        for mode in ('PERIODIC','ALARM'):r['arms'][mode]=minimal(position(k,mode,mh,m['files']))
        for mode,arm in r['arms'].items():
            insist((arm['job'],arm['pid']) not in pids and arm['L']+EPS>=r['minimum'],'duplicate PID or bound')
            pids.add((arm['job'],arm['pid']));role_ids[mode]+=1
        r['gaps']={mode:arm['L']-r['minimum'] for mode,arm in r['arms'].items()}
        positive=all(r['arms'][mode]['L']>EPS for mode in ('P','PERIODIC','ALARM'))
        strict=all(r['gaps'][mode]>EPS for mode in ('P','PERIODIC','ALARM'))
        r['T4']=bool(positive and r['b'] and r['c2'] and not r['c1'])
        r['all_baselines_above_bound']=strict
        if r['T4']:
            targets.append(k)
            if strict:subtargets.append(k)
            if not r['partial']:full.append(k)
        for label,val in [('three_positive',positive),('oracle_headroom',r['b']),('earlier_c2',r['c2']),('alarm_late_or_absent',not r['c1'])]:
            reasons[label]+=int(val)
        denom[(r['family'],r['layer'])]+=1
    pair_table=[]
    for fam,pair in pairs.items():
        insist(len(pair)==2,'two paired worlds '+fam);l,h=pair
        insist(l['private']!=h['private'] and l['config']==h['config'] and l['scheduled_prior']==h['scheduled_prior'],
            'different private worlds same public program '+fam)
        first=next((a[0] for a,b in zip(l['view'],h['view'],strict=True) if a[1]!=b[1]),None)
        insist(first is None or first>0,'shared legitimate earlier prefix')
        # Record the actual complete or partial public prefix for each pair; the panel requires at least one full match.
        pair_table.append(dict(family=fam,keys=[l['key'],h['key']],first_different_public_tick=first,
            whole_P_public_history_identical=first is None,public_config_sha256=l['config'],channel_sha256=l['scheduled_prior'],
            private_input_sha256=[l['private'],h['private']],legal_schedules=[l['plan'],h['plan']],
            plans_differ=l['plan']!=h['plan'],P_losses=[l['L'],h['L']],minimum_L=[l['Lstar'],h['Lstar']]))
    insist(any(v['whole_P_public_history_identical'] for v in pair_table),'at least one fully matched public history')
    insist(len(rows)==72 and len(pids)==288 and all(role_ids[r]==72 for r in ROLES),'declared positions')
    families=load(PK/'settings.json')['development_families']
    grouped=[dict(family=fam,layer=layer,n=n,share_within_family=n/12,keys=[r['key'] for r in rows if r['family']==fam and r['layer']==layer],
        metrics=metrics([r for r in rows if (r['family'],r['layer'])==(fam,layer)])) for (fam,layer),n in sorted(denom.items())]
    law=[dict(family=f,record_type=n,degraded=d,availability=c,p=p,number=v[0],seen=v[1]) for (f,n,d,c,p),v in sorted(prior_law.items())]
    result=dict(schema='t3-development-results-v2',manifest=mh,source_freeze=m['freeze'],seed=m['seed'],holdout_commitment=m['holdout_commitment'],
        families=families,condition_count=len(rows),roles=dict(role_ids),all_optima_attained=True,readback_job=slurm(),business_ticks=list(BIZ),
        overall=metrics(rows),family_stats={fam:metrics([r for r in rows if r['family']==fam]) for fam in families},
        groups=grouped,joint_strata=dict(Counter(r['layer'] for r in rows)),prior_distribution=law,paired_worlds=pair_table,
        T4=targets,T4_full=full,T4_partial=[k for k in targets if k not in full],T4_all_three_above_optimum=subtargets,
        criteria_counts=dict(reasons),rows=rows,holdout_generated=0,holdout_runs=0,new_method_runs=0)
    with (REMOTE/'development-result.json.gz').open('xb') as fp:
        fp.write(gzip.compress((json.dumps(result,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode(),compresslevel=6,mtime=0))
    print('72 conditions',dict(role_ids),'T4',targets,'pairs',[(p['family'],p['plans_differ']) for p in pair_table],flush=True)
    print(sha(REMOTE/'development-result.json.gz'),flush=True)


if __name__=='__main__':main(sys.argv[1])
