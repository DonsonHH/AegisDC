"""Format saved T3 scientific results and coverage. No new simulator/evaluator call."""
from collections import Counter,defaultdict
import gzip
import json
import os
from common import *

F={'WATER_HEAT':'水侧与热库存','NETWORK_POWER':'网络／供电','RESERVE_TRANSFER':'有限备用',
   'COOLING_ACCESS':'主备冷却／通行','LONDON':'伦敦式','NETHERLANDS':'荷兰式'}
M={'P':'P','PERIODIC':'固定巡检','ALARM':'报警响应','ORACLE':'全知见证'}
OP={'clean_filter':'清滤','restore_network':'恢复网络配置','revise_shared':'修正共享判断','prestart':'预启动',
    'restore_path':'恢复获准路径','relieve_group':'重分组','restart_pump':'重启泵','commission_backup':'备冷复役'}


def fmt(v):
    if v is None:return '—'
    if abs(v)<1e-7:return '0'
    if abs(v-round(v))<1e-7:return str(round(v))
    return f'{v:.3f}'.rstrip('0').rstrip('.')


def table(cols,rows):
    return '\n'.join(['| '+' | '.join(cols)+' |','|'+'|'.join('---' for _ in cols)+'|',
        *['| '+' | '.join(str(z) for z in row)+' |' for row in rows]])


def label(v):return '是' if v else '否'
def listing(items):return '、'.join(items) if items else '无'


def plans(plan):
    return ' → '.join(f'{t}s {v}' for t,v in sorted(plan.items(),key=lambda p:int(p[0]))) or '无人工工作'


def rowstats(group,m):
    s=group[m];cl=s['closure']
    return [M[m],*[fmt(s[f]['mean']) for f in ('L','U','person','tool','fee')],
        f"{cl['NA']['ever']}/{cl['PV']['ever']}",'/'.join(str(v) for v in cl['NA']['current_by_business_tick']),
        '/'.join(str(v) for v in cl['PV']['current_by_business_tick']),s['work_order_denominator'],
        str(s['gap']['positive']),'/'.join(fmt(s['gap'][k]) for k in ('min','median','max'))]


def main():
    slurm()
    with gzip.open(REMOTE/'development-result.json.gz','rt') as f:x=json.load(f)
    rows=x['rows'];index={r['key']:r for r in rows};families=x['families'];targets=[index[k] for k in x['T4']]
    cols=['基线','平均 L','平均 U','平均人秒','平均工具秒','平均费','曾达 NA/PV','NA 四个时点','PV 四个时点','工单数','正差行','差距小/中/大']
    fam_table=table(['族','条件数',*cols],[[family,n,*rowstats(v,m)] for family,n,v in
        [('全板',72,x['overall'])]+[(F[f],12,x['family_stats'][f]) for f in families] for m in ('P','PERIODIC','ALARM')])
    layer_table=table(['族','层 a b c1 c2','条件数','族内比例',*cols],[[F[g['family']],g['layer'],g['n'],f"{100*g['share_within_family']:.1f}%",*rowstats(g['metrics'],m)]
        for g in x['groups'] for m in ('P','PERIODIC','ALARM')])
    contrasts=[]
    for q in x['paired_worlds']:
        left,right=q['legal_schedules'];a,b=q['keys']
        diff_acq=[]
        l={v['subject']:v['fields'] for v in index[a]['unpaid_native_no_action_projection']}
        h={v['subject']:v['fields'] for v in index[b]['unpaid_native_no_action_projection']}
        for name in sorted(l.keys()&h.keys()):
            if l[name]!=h[name]:diff_acq.append(name)
        contrasts.append([F[q['family']],a+'／'+b,'全 61 点相同' if q['whole_P_public_history_identical'] else
            '首次不同 @'+fmt(q['first_different_public_tick']),plans(left),plans(right),label(q['plans_differ']),listing(diff_acq)])
    pair_table=table(['族','配对','P 的合法公共帧','左侧最优实际计划','右侧最优实际计划','计划有别','付费才可区分的主体'],contrasts)
    target_table=table(['条件','族','层','P/巡检/报警 L','L*','全部可救','三臂均高于 L*','首个报警','首条事前记录','可购结果最早到达','τ'],[
        [r['key'],F[r['family']],r['layer'],' / '.join(fmt(r['arms'][m]['L']) for m in ('P','PERIODIC','ALARM')),fmt(r['minimum']),
        label(not r['partial']),label(r['all_baselines_above_bound']),fmt(r['info']['alarm'][0]) if r['info']['alarm'] else '—',
        fmt(r['info']['prior'][0]) if r['info']['prior'] else '—',fmt(r['info']['paid'][0]) if r['info']['paid'] else '—',fmt(r['latest'])] for r in targets]) if targets else '无满足四项条件的行。'
    incident=[]
    for r in rows:
        if r['family'] not in ('LONDON','NETHERLANDS'):continue
        s=r['incident_single_action_bounds'];which=[OP[k] for k,a in s.items() if a['reduces_relative_to_P']]
        i=r['info'];record=i['prior'][0] if i['prior'] else None;paid=i['paid'][0] if i['paid'] else None
        incident.append([r['key'],F[r['family']],r['cell'],label(r['a']),fmt(r['arms']['P']['L']),fmt(r['native_P_first_loss']),
            fmt(record),fmt(paid),fmt(i['alarm'][0]) if i['alarm'] else '—',fmt(r['latest']),fmt(r['minimum']),
            listing(which),plans(r['certified_plan'])])
    inc_table=table(['条件','族','合成背景','P 有事故','P L','首损秒','事前记录秒','可购读数秒','报警秒','τ 秒','L*',
        '可单独减损的合规操作¹','实际达界计划'],incident)
    prob=defaultdict(lambda:dict(exposure=[0,0],appearance=[0,0]))
    for q in x['prior_distribution']:
        k=(q['family'],q['record_type']);idx=int(not q['degraded']);prob[k]['exposure'][idx]+=q['number'];prob[k]['appearance'][idx]+=q['seen']
    model=load(PK/'settings.json')['information_law']
    law_table=table(['族','记录／来源','退化概率','无退化概率','采样/到达/到期秒','实发/退化行','实发/无退化行'],[
        [F[f],typ+' / '+source,fmt(pd),fmt(pn),'/'.join(map(str,[at,at+delay,at+ttl])),
         f"{prob[f,typ]['appearance'][0]}/{prob[f,typ]['exposure'][0]}", f"{prob[f,typ]['appearance'][1]}/{prob[f,typ]['exposure'][1]}"]
        for f in families for typ,source,pd,pn,at,delay,ttl in model[f]])
    comparison=Counter();identifiable=Counter();counts=Counter()
    for r in rows:
        for ix in ('a','b','c1','c2','T4'):
            counts[ix]+=int(r[ix])
        if r['T4']:
            comparison[F[r['family']]]+=1
            identifiable['prior']+=int(r['info']['from_record']);identifiable['paid']+=int(r['info']['from_paid'])
            identifiable['both']+=int(r['info']['from_record'] and r['info']['from_paid'])
    ac_data=[]
    for gate in ('A','C'):
        q=load(REMOTE/f'engineering-{gate}-readback.json')[gate]
        for row in q['rows']:
            exp=row['expected']
            if gate=='A':
                sid=exp['subject'];ac_data.append([gate,row['key'],sid,str(row['first'].get(sid,{})),
                    ' / '.join(row['checkpoints'][str(t)][sid] for t in BIZ),f"{fmt(row['L'])}/{fmt(row['U'])}",label(row['passed'])])
            else:
                ac_data.append([gate,row['key'],'／'.join(r['operation']+' '+r['outcome'] for r in row['writes']) or '仅保护',
                    '首损 '+fmt(row['first_loss']),'独立状态断言 '+str(len(row['checks'])),f"{fmt(row['L'])}/{fmt(row['U'])}",label(row['passed'])])
    ac_table=table(['关','见证','主体／物理操作','首次关闭或损失','业务点／状态检查','L/U','通过'],ac_data)
    all_table=table(['条件','层','P/巡检/报警 L=U','合法最小 L','P/巡检/报警减最小','τ','c2 来自'],[
        [r['key'],r['layer'],' / '.join(fmt(r['arms'][m]['L']) for m in ('P','PERIODIC','ALARM')),fmt(r['minimum']),
        ' / '.join(fmt(r['gaps'][m]) for m in ('P','PERIODIC','ALARM')),fmt(r['latest']),
        listing([k for k,yes in [('记录',r['info']['from_record']),('可购检查',r['info']['from_paid'])] if yes])] for r in rows])
    write(REMOTE/'tables.json',dict(family=fam_table,layers=layer_table,pairs=pair_table,targets=target_table,incidents=inc_table,
        priors=law_table,engineering=ac_table,all_rows=all_table,counts=dict(counts),target_families=dict(comparison),sources=dict(identifiable),
        t4=x['T4'],full=x['T4_full'],partial=x['T4_partial'],strict=x['T4_all_three_above_optimum'],overall=x['overall'],layers_observed=x['joint_strata']))
    print('tables',len(rows),len(x['groups']),len(targets),flush=True)


if __name__=='__main__':main()
