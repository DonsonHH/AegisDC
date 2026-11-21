"""Build display tables solely from sealed P, PERIODIC, ALARM and evaluator scores."""
from collections import Counter
from pathlib import Path
from statistics import mean,median
import gzip
import json
import os

ACTIVITY=Path('/share/home/renly/renly-patrol-rsi/mainline/T2-minute-facility-20261121-v1')
ROLES=('P','PERIODIC','ALARM')
ROLE={'P':'P','PERIODIC':'固定巡检','ALARM':'报警响应'}
FAMILY={'WATER_HEAT':'水侧与热库存','NETWORK_POWER':'网络与供电','RESERVE_TRANSFER':'有限备用','COOLING_ACCESS':'主备冷却与到场'}
EPS=1.e-7


def fmt(x):
    if x is None:return '—'
    if abs(x)<EPS:return '0'
    if abs(x-round(x))<EPS:return str(int(round(x)))
    return ('%.3f'%x).rstrip('0').rstrip('.')


def compact(items):
    return '、'.join(items) if items else '无'


def table(columns,rows):
    return '\n'.join(['| '+' | '.join(columns)+' |','|'+'|'.join(['---']*len(columns))+'|',*['| '+' | '.join(str(v) for v in r)+' |' for r in rows]])


def grouped(rows):
    out=[]
    for label,block in [('全部',rows)]+[(label,[r for r in rows if r['family']==f]) for f,label in FAMILY.items()]:
        for role in ROLES:
            n=len(block);gap=[u['gaps'][role] for u in block];vals=[r[role] for r in block]
            named=sum(r['work_order_count'] for r in block)
            ever=sum(len(v['ever']) for v in vals)
            pv=sum(sum('POST_ACTION_VERIFIED_CURRENT' in t for t in v['ever'].values()) for v in vals)
            na=sum(sum('NO_ACTION_CURRENT' in t for t in v['ever'].values()) for v in vals)
            final=sum(sum(z in ('POST_ACTION_VERIFIED_CURRENT','NO_ACTION_CURRENT') for z in v['checkpoints']['3600'].values()) for v in vals)
            out.append([label,n,ROLE[role],*[fmt(mean(v[k] for v in vals)) for k in ('L','U','person_s','tool_s','fee')],
                f'{ever}/{named} ({na}/{pv})',f'{final}/{named}',sum(v>EPS for v in gap),'/'.join(fmt(f(gap)) for f in (min,median,max))])
    return table(['族','条件数','基线','平均 L','平均 U','平均人员秒','平均工具秒','平均费用','曾关闭／工单 (NA/PV)','H末关闭／工单','差距>0 行','差距最小/中位/最大'],out)


def main():
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Slurm required')
    with gzip.open(ACTIVITY/'study-results.json.gz','rt') as fp:data=json.load(fp)
    rows=[r for r in data['rows'] if r['selected']]
    census=[]
    for fam,label in FAMILY.items():
        p=data['population'][fam];n=sum(p.values())
        for layer in sorted(set(p)|{k for k,v in data['quotas'][fam].items() if v}):
            count=p.get(layer,0)
            census.append([label,layer,data['quotas'][fam].get(layer,0),count,f'{100*count/n:.1f}%',
                sum(x['family']==fam and x['layer']==layer for x in rows)])
    subgroup=[]
    for group in data['groups']:
        for role,v in group['baselines'].items():
            subgroup.append([FAMILY[group['family']],group['layer'],group['n'],ROLE[role],
                 *[fmt(v[k]['mean']) for k in ('L','U','person_s','tool_s','fee')],
                 v['ever_named_instances'],v['final_verified'],
                 v['gap']['positive'],'/'.join(fmt(v['gap'][z]) for z in ('min','median','max'))])
    targets=[r for r in rows if r['complete_rescue_target']]
    strict=[u['key'] for u in targets if all(u[m]['L']>=u['P']['L']-EPS for m in ('PERIODIC','ALARM'))]
    partial=[u['key'] for u in rows if u['Lstar']>EPS and all(u['gaps'][m]>EPS for m in ROLES)]
    trows=[[r['key'],FAMILY[r['family']],r['layer'],*[fmt(r[k]['L']) for k in (*ROLES,'ORACLE')],
            fmt(r['precursor'][0]),fmt(r['last_start']),r['key'] in strict] for r in targets]
    counters=[]
    allidx={r['key']:r for r in rows}
    for fam in FAMILY:
        ids=data['counterexamples'].get(fam,[])
        if not ids:raise ValueError('Missing positive-loss counterexample '+fam)
        r=allidx[ids[0]]
        counters.append([FAMILY[fam],r['key'],fmt(r['P']['L']),fmt(r['Lstar']),r['proof'],compact(ids)])
    levels=[]
    for r in rows:
        ls=[fmt(r[v]['L']) for v in ROLES];gap=[fmt(r['gaps'][v]) for v in ROLES]
        levels.append([r['key'],FAMILY[r['family']],r['layer'],' / '.join(ls),fmt(r['Lstar']),' / '.join(gap),
            fmt(r['precursor'][0]) if r['precursor'] else '—',fmt(r['last_start'])])
    distribution={k:dict(Counter(u['layer'] for u in rows)) for k in ('layers',)}
    distribution.update(target=len(targets),early_target=len(data['full_rescue_with_early_precursor']),
        neither_reduced=strict,partial_all=partial,draws=data['generated'],selected=len(rows),
        any_positive_P=sum(r['a'] for r in rows),headroom=sum(r['b'] for r in rows),early=sum(r['c'] for r in rows),
        all_unique_missed={m:sum(r['gaps'][m]>EPS for r in rows) for m in ROLES},
        family_directed={f:{'total':sum(v['family']==f for v in rows),'full_rescue_target':sum(v['family']==f for v in targets),
        'counterexamples':data['counterexamples'][f]} for f in FAMILY})
    out=dict(overview=distribution,census=table(['族','实际层 abc','设计名额','抽得','占该族','最终入层'],census),
        family=grouped(rows),
        strata=table(['族','层','行','基线','平均 L','平均 U','平均人员秒','平均工具秒','平均费用','曾关闭数','H末关闭数','正差行','差距最小/中位/最大'],subgroup),
        target=table(['条件','族','层','P L','巡检 L','报警 L','合法最小 L','前兆到达秒','整链最晚启动秒','两人工均未减损'],trows) if trows else '无符合全部条件的行。',
        counter=table(['族','代表条件','P L','合法最小 L','证书','同族全部反例'],counters),
        condition=table(['条件','族','层','P / 巡检 / 报警 L=U','合法最小 L','三种基线减最小 L','前兆到达秒','最晚启动秒'],levels),
        mixed=data['ambiguous_pair'],rescue=data['full_rescue_target'],early_rescue=data['full_rescue_with_early_precursor'])
    # Separate private topological state from published fixed and work reports in every file.
    with (ACTIVITY/'report-tables.json').open('x',encoding='utf8') as fp:json.dump(out,fp,ensure_ascii=False)
    print('report assembled',len(rows),'rows',len(targets),'targets',flush=True)


if __name__=='__main__':main()
