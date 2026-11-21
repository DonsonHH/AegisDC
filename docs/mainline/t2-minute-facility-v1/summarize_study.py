"""Read saved T2 positions once. Classify by P, certified minimum and time, before reading baseline outcomes."""
from collections import Counter,defaultdict
from fractions import Fraction
import gzip
import hashlib
import json
import os
from pathlib import Path

ROOT=Path('/share/home/renly/renly-patrol-rsi/mainline/T2-minute-facility-20261121-v1')
INPUTS=ROOT/'study-inputs'
SRC=ROOT/'C-source/docs/mainline/t2-minute-facility-v1'
EPS=1e-7


def load(p):return json.loads(p.read_bytes())


def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def need(v,label):
    if not v:raise ValueError(label)


def position(row,mode,bindings):
    p=ROOT/'positions'/(row+'-'+mode);x=load(p/'result.json');entry=load(p/'start.json')
    need(x['key']==entry['key']==row and x['mode']==entry['mode']==mode and
         x['input_sha256']==entry['input']==bindings[row] and x['pid']==entry['pid'] and
         x['job']==entry['job'] and x['public_calls']==61,'position identity')
    need(sha(p/'original.jsonl.gz')==x['native_sha256'],'private original digest')
    x['score_sha256']=sha(p/'result.json')
    return x


def brief(x):
    return {k:v for k,v in x.items() if k not in ('public_history','original_fixed')}


def distribution(v):
    seq=sorted(v)
    if not seq:return {'n':0}
    n=len(seq);mid=(seq[(n-1)//2]+seq[n//2])/2
    return dict(n=n,min=seq[0],median=mid,max=seq[-1],mean=sum(seq)/n,positive=sum(q>EPS for q in seq))


def main():
    need(os.environ.get('SLURM_JOB_ID'),'Slurm only')
    source=load(SRC/'study-freeze.json');m=load(INPUTS/'manifest.json')
    index=load(INPUTS/'index.json')['ordered'];quotas=source['stratum_quotas'];hist=Counter()
    pops=defaultdict(Counter);rows=[];used=[];summary=defaultdict(list);amb=[]
    # No periodic/alarm score or win participates in the inventory, selection or target quota.
    for unit in index:
        k=unit['key'];x=load(INPUTS/(k+'.json'));fam=x['evaluation']['family']
        p=position(k,'P',m['files']);o=position(k,'ORACLE',m['files']);cert=o['oracle']
        need(cert is not None and cert['attained'] and cert['issued_as_planned'] and
             abs(o['L']-cert['lower'])<=EPS and abs(o['U']-cert['lower'])<=EPS and p['L']+EPS>=o['L'],'unattained bound '+k)
        used.extend([(p['job'],p['pid']),(o['job'],o['pid'])]);a=p['L']>EPS;b=p['L']-o['L']>EPS
        first=p['first_precursor'];last=cert['last_start']
        c=bool(a and b and o['L']<=EPS and last is not None and first and first[0]<last)
        if not a:why='P_HAS_NO_LOSS'
        elif not b:why='NO_LEGAL_SERVICE_HEADROOM'
        elif o['L']>EPS:why='IRREDUCIBLE_LOSS_NO_FULL_AVOIDANCE_DEADLINE'
        elif last is None:why='NO_CERTIFIED_LAST_START'
        else:why='ARRIVAL_STRICTLY_BEFORE' if c else 'ARRIVAL_AT_OR_AFTER'
        layer=''.join('1' if z else '0' for z in (a,b,c));pops[fam][layer]+=1
        if x['evaluation']['ambiguous_pair']:
            amb.append(dict(row=k,physical=x['evaluation']['group'],public=x['public'],actual=p['original_fixed'],
                            history=[v['view'] for v in p['public_history']]))
        keep=hist[(fam,layer)]<quotas[fam].get(layer,0)
        if keep:hist[(fam,layer)]+=1
        rows.append(dict(key=k,family=fam,draw=x['evaluation']['draw'],layer=layer,a=a,b=b,c=c,selected=keep,
            reason=why,precursor=first,last_start=last,proof=cert['proof'],Lstar=cert['lower'],
            work_order_count=len(x['public']['work_orders']),optional_paid_initial=len(x['public']['paid_opportunities']),
            public_record_count=sum(z['observable']!='problem_reported' for z in x['native']['dispatch_program']['order_channel'])
             +len(x['native']['dispatch_program']['policy_program']['fixed_epochs'])*len(x['native']['dispatch_program']['policy_program']['fixed_on']),
            P=brief(p),ORACLE=brief(o)))
    selection_complete=all(hist[(fam,layer)]==n for fam,ls in quotas.items() for layer,n in ls.items())
    need(len(amb)==2 and amb[0]['physical']!=amb[1]['physical'] and amb[0]['public']==amb[1]['public']
         and amb[0]['actual']==amb[1]['actual'] and amb[0]['history']==amb[1]['history'],'ambiguous public pair not witnessed')
    target=[];target_with_early=[];partial=[];counter=defaultdict(list)
    # Baseline columns are joined only after all diagnostic strata have been selected.
    for x in rows:
        k=x['key'];s=x['Lstar'];family=x['family']
        for role in ('PERIODIC','ALARM'):
            pos=position(k,role,m['files']);used.append((pos['job'],pos['pid']))
            x[role]=brief(pos)
        x['gaps']={role:x[role]['L']-s for role in ('P','PERIODIC','ALARM')}
        for val in x['gaps'].values():need(val>=-EPS,'observed baseline beats certified optimum '+k)
        x['complete_rescue_target']=bool(x['a'] and s<=EPS and all(x[role]['L']>EPS for role in ('PERIODIC','ALARM')))
        x['residual_margin_all_baselines']=all(v>EPS for v in x['gaps'].values())
        if x['complete_rescue_target']:
            target.append(k)
            if x['c']:target_with_early.append(k)
        if x['residual_margin_all_baselines'] and not x['complete_rescue_target']:partial.append(k)
        if x['P']['first_precursor'] and not x['b'] and x['a']:
            counter[family].append(k)
        if x['selected']:summary[(family,x['layer'])].append(x)
    need(len(set(used))==len(used)==192,'process isolation')
    result_groups=[]
    for (fam,layer),group in sorted(summary.items()):
        values={}
        for role in ('P','PERIODIC','ALARM'):
            a=[r[role] for r in group]
            values[role]={field:distribution([one[field] for one in a]) for field in ('L','U','person_s','tool_s','fee')}
            values[role]['gap']=distribution([r['gaps'][role] for r in group])
            values[role]['ever_named_instances']=sum(len(one['ever']) for one in a)
            values[role]['final_verified']=sum(sum(s in ('POST_ACTION_VERIFIED_CURRENT','NO_ACTION_CURRENT') for s in one['checkpoints']['3600'].values()) for one in a)
        result_groups.append(dict(family=fam,layer=layer,n=len(group),conditions=[r['key'] for r in group],baselines=values))
    report=dict(schema='t2-minute-status-quo-v1',seed=m['seed'],generated=len(rows),selected=sum(r['selected'] for r in rows),
        selection_complete=selection_complete,population={k:dict(v) for k,v in pops.items()},quotas=quotas,
        positions=len(used),baseline_positions=144,native_oracle_witnesses=48,real_public_decisions=len(used)*61,
        all_optima_certified=True,ambiguous_pair=[a['row'] for a in amb],counterexamples=dict(counter),
        full_rescue_target=target,full_rescue_with_early_precursor=target_with_early,partial_only=partial,
        groups=result_groups,rows=rows)
    with (ROOT/'study-results.json.gz').open('xb') as fp:
        fp.write(gzip.compress((json.dumps(report,separators=(',',':'),allow_nan=False)+'\n').encode(),mtime=0))
    flat={k:v for k,v in report.items() if k not in ('rows','groups')}
    print(json.dumps(flat,separators=(',',':')),flush=True)
    print(sha(ROOT/'study-results.json.gz'),flush=True)


if __name__=='__main__':main()
