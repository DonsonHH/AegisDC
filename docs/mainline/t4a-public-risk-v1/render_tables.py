"""Format saved T4a estimates, original returns, and paired denominators for the report."""
import gzip
import json
from pathlib import Path
import sys


VERSIONS = ('V1', 'V2', 'V3')
CONTROLS = ('PERIODIC', 'ALARM', 'PA', 'B')
ROLES = VERSIONS + CONTROLS
LABELS = {
    'overall':'全板', 'WATER_HEAT':'水侧／热', 'NETWORK_POWER':'网络／供电',
    'RESERVE_TRANSFER':'有限备用', 'COOLING_ACCESS':'冷却／通行', 'LONDON':'伦敦式',
    'NETHERLANDS':'荷兰式', 'PERIODIC':'周期巡检', 'ALARM':'报警响应',
}


def name(s):
    key = s.rsplit('/', 1)[-1]
    return LABELS.get(key, key)


def num(x):
    return f'{x:.1f}' if abs(x) >= 0.05 else '0.0'


def bound(x):
    return f"{num(x['mean'])} [{num(x['lo'])}, {num(x['hi'])}]"


def ranks(q):
    return '/'.join(str(x) for x in q['directions'])


def table(lines, headers, rows):
    def row(cols):
        return '| ' + ' | '.join(str(c).replace('|', '&#124;') for c in cols) + ' |'
    lines.extend(['', row(headers), row(['---']*len(headers))])
    lines.extend(row(values) for values in rows)
    lines.append('')


def checkpoints(role, closure):
    return '/'.join(map(str, role['closure'][closure]['current']))


def scopes(results):
    for k, s in results['scopes'].items():
        if k == 'overall' or k.startswith(('family/', 'layer/')):
            yield k, s


def appendix(results, inventory):
    lines = ['## 配对结果与资源账', '', '所有差值均为 V 减该对照。L 用归一化服务缺额秒，U 用未交付服务单位·秒。每条条件的全部角色共享同一重抽索引。负的服务差有利于 V。区间由 10,000 次族内配对重抽取得。']
    overall = results['scopes']['overall']
    table(lines, ['版本', '对照', 'ΔL [95% 区间]', 'ΔU [95% 区间]', 'L 较低／同／较高', 'Δ人秒', 'Δ工具秒', 'Δ发行费'],
          ([v, name(c), bound(q['L']), bound(q['U']), ranks(q), num(q['person']['mean']), num(q['tool']['mean']), num(q['fee']['mean'])]
           for v in VERSIONS for c, q in ((k, overall['paired'][v][k]) for k in CONTROLS)))
    lines.extend(['## 四个业务点和工单分母', '', '四联数依次对应 900、1800、2700、3600 秒。NA 表示有合法证据关闭且未处置，PV 表示处置后经过具名复核关闭。每个数字计当前有效的工单实例。同一实例可在不同业务点出现。曾达列在每一类型内各去重一次。'])
    table(lines, ['角色', '平均 L', '平均 U','人秒／行','工具秒／行','发行费／行','工单实例','曾达 NA／PV','当前 NA','当前 PV'],
          ([name(k), num(q['L']), num(q['U']), num(q['person']), num(q['tool']), num(q['fee']), q['work_orders'],
            f"{q['closure']['NA']['ever']}/{q['closure']['PV']['ever']}", checkpoints(q,'NA'), checkpoints(q,'PV')]
           for k,q in ((k,overall['by_role'][k]) for k in (*ROLES,'P','ORACLE'))))
    lines.extend(['## 分族与实际信息层', '', '四位编码顺序为既有保护有损失、存在合法可挽回余量、报警在截止前可用、事前记录或付费读数在截止前可用。一个格内保留原有的族组成和条件数。只有一行或各行全相同时，重抽区间可以退化。'])
    data=[]
    for label,s in scopes(results):
        if label=='overall':continue
        for v in VERSIONS:
            cells=[]
            for c in CONTROLS:
                q=s['paired'][v][c]
                cells.append(bound(q['L']) if q['L']==q['U'] else bound(q['L'])+' / '+bound(q['U']))
            data.append([name(label),s['n'],v,*cells])
    lines.append('下表给出 ΔL／ΔU 及各自区间。两组数值及区间完全相同的单元格合写一次。')
    table(lines,['范围','条件数','版','相对周期巡检','相对报警响应','相对 PA','相对 B'],data)
    lines.extend(['### 各范围的资源与关闭', '', '资源为每行实耗均值，初检与操作是全格的实际计数。各版与四条对照均使用相同的条件和工单分母。'])
    table(lines,['范围','条件／工单','角色','人秒','工具秒','发行费','初检／操作','曾达 NA／PV','当前 NA','当前 PV'],
          ([name(label),f"{s['n']}/{q['work_orders']}",name(role),num(q['person']),num(q['tool']),num(q['fee']),
            f"{q['initial_reads']}/{q['actions']}",f"{q['closure']['NA']['ever']}/{q['closure']['PV']['ever']}",
            checkpoints(q,'NA'),checkpoints(q,'PV')]
           for label,s in scopes(results) if label!='overall' for role,q in ((k,s['by_role'][k]) for k in ROLES)))
    lines.extend(['## 1100 与 0000 的动作复查', '', '1100 有可挽回损失且两类及时信息机会均缺失。0000 的既有保护损失为零。NO_EFFECT 是操作未产生写入，等值写入是收到 APPLIED 而目标值相同。显式分开有费用的核查与物理写入；处置未降低服务缺额也可能产生有效关闭。'])
    data=[]
    for label in ('1100','0000'):
        s=results['scopes'].get('layer/'+label)
        if s is None:
            data.append([label,0,'—','—','—','—','—','—','—','—']);continue
        for role in (*VERSIONS,'PA','B'):
            q=s['by_role'][role]
            rows=[r for r in results['rows'] if r['layer']==label]
            pay=sum(r['arms'][role]['fee']>0 for r in rows)
            noreduce=sum(r['arms'][role]['fee']>0 and r['arms'][role]['L']>=r['arms']['P']['L']-1e-7 for r in rows)
            data.append([label,s['n'],role,pay,noreduce,q['initial_reads'],q['actions'],q['no_effect'],q['equal_writes'],num(q['person'])])
    table(lines,['层','条件','角色','有支出行','有支出且 L 未低于 P 的行','初检','全部处置','NO_EFFECT','等值写入','人秒／行'],data)
    lines.extend(['## 事前登记的三行及伦敦孪生对', '', '三个 T3 目标行和两条同公开前缀的孪生行全部在下。所列时间是派工时刻；付费列分别给采样与合法到达时刻。L* 为该条件的全知合法评价界。'])
    data=[]
    for r in results['rows']:
        if r['key'] not in ('2-02','2-12','5-07','5-04','5-10'):continue
        for v in (*VERSIONS,'PA','B'):
            q=r['arms'][v]
            ops='，'.join(f'{int(t)} {task}' for t,task in q['requests']) or '无'
            arrivals='，'.join(f"{z['task']} {z['sampled']:g}/{z['arrived']:g}" for z in q['paid'] if z['phase']=='I') or '无'
            data.append([r['key'],v,num(q['L']),num(r['minimum']),num(q['person']),ops,arrivals])
    table(lines,['行','版本／对照','实际 L','L*','人秒','实际派工（秒）','初检采样／到达（秒）'],data)
    lines.extend(['## 付费核查的事前选择与后续实际动作', '', '各版按已登记批次、位置和时钟顺序，取第一次实际选中的初检。候选分支数会包括同一条件在多个时点上的评估。预期续决策按合法读数分组；真实到达后按当时全部公共材料重新选择。'])
    data=[]
    for role in VERSIONS:
        q=overall['by_role'][role]
        a=[r['arms'][role]['policy_audit'] for r in results['rows']]
        missing=sum(t['zero_support_ticks'] for t in a)
        branches=sum(t['info_sensitive_candidate_roots'] for t in a)
        x=inventory['first_actual_initial_read'].get(role)
        first='无' if not x else f"{x['key']}，{x['time']:g}s {x['task']}"
        after='—' if not x or not x['first_view_after_arrival'] else f"{x['first_view_after_arrival']['at']:g}s {x['first_view_after_arrival']['chosen']}"
        data.append([role,q['initial_reads'],branches,missing,first,after])
    table(lines,['版本','实际初检次数','有读数依赖的候选分支次数','零支持时点','首个实际初检','读数到达后首个派工点'],data)
    for role,x in inventory['first_actual_initial_read'].items():
        lines.extend([f"**{role} 的第一份初检决策。** 该行 {x['key']} 在 {x['time']:g} 秒选择 {x['task']}。下表为该首步所承诺的条件续决策及其预计全窗损失与人秒。"])
        table(lines,['可能读数','事前概率','条件续处置','预期 L','预期人秒'],
              ([key,f"{leaf['probability']:.4f}",' → '.join(leaf['continue_with']) or '暂缓',num(leaf['cost'][0]),num(leaf['cost'][1])]
               for key,leaf in x['first']['table'].items()))
    lines.extend(['[全部逐条件结果、各指标未舍入区间及族×层交叉格](development-result.json.gz) · [实际授权、源码、输入和每个位置的原件索引](receipt.json)'])
    return '\n'.join(lines)+'\n'


def main(root):
    with gzip.open(root/'development-result.json.gz','rt') as source:
        results=json.load(source)
    inventory=json.loads((root/'attempt-inventory.json').read_bytes())
    with (root/'report-tables.md').open('x',encoding='utf-8') as output:
        output.write(appendix(results,inventory))
    overall=results['scopes']['overall']
    facts=dict(by_role=overall['by_role'],paired=overall['paired'],price_components=results['development_primary_components'],
        rowwise=results['prior_offline_rowwise_best_L'],gap_ratios=results['remaining_gap_ratio'],
        diagnoses={v:{k:len(a) if isinstance(a,list) else a for k,a in d.items()} for v,d in results['diagnoses'].items()},
        scopes={name:{'n':s['n'],'delta':s['paired']['V3']['PA']['L'],'signs':s['paired']['V3']['PA']['directions'],
            'spend':s['paired']['V3']['PA']['person']['mean']} for name,s in scopes(results)},
        below_T3_minimum={v:[r['key'] for r in results['rows'] if r['arms'][v]['L']<r['minimum']-1e-7] for v in (*VERSIONS,'PA','B')},
        refused={v:sum(bool(r['arms'][v]['refusals']) for r in results['rows']) for v in (*VERSIONS,'PA','B')},
        purchased={v:sum(r['arms'][v]['policy_audit']['info_sensitive_candidate_roots'] for r in results['rows']) for v in VERSIONS},
        targets={r['key']:{v:[r['arms'][v]['L'],r['arms'][v]['person']] for v in ROLES} for r in results['rows'] if r['frozen_T4']},
        scoped_paid_examples=inventory['first_actual_initial_read'])
    with (root/'report-facts.json').open('x',encoding='utf-8') as output:
        json.dump(facts,output,ensure_ascii=False,separators=(',',':'),allow_nan=False)


if __name__=='__main__':
    main(Path(sys.argv[1]))
