"""Format existing condition estimates from the Slurm readback into the consolidated report."""
from common_v3 import ACT
from collections import Counter

NAMES={'V_COST':'V**','VSTAR':'冻结 V*','V_COST_NOPROBE':'V**−probe','VSTAR_NOPROBE':'旧 V*−probe','BPLUS':'B+',
       'PERIODIC':'巡检','ALARM':'报警','ORACLE':'合法全知','WATER_HEAT':'水侧／热','NETWORK_POWER':'网络／供电',
       'RESERVE_TRANSFER':'有限备用','COOLING_ACCESS':'冷却／通行','LONDON':'伦敦式','NETHERLANDS':'荷兰式'}
def name(k):return NAMES.get(k,k)
def f(x):return '未定义' if x is None else f'{x:.2f}'
def ci(z):return f"{f(z['mean'])} [{f(z['lo'])}, {f(z['hi'])}]"
def table(lines,header,rows):
    def make(c):return '| '+' | '.join(map(str,c))+' |'
    lines.extend(['',make(header),make(['---']*len(header))])
    lines.extend(make(row) for row in rows)
    lines.append('')
def render(r):
    scopes=r['scopes'];all_=scopes['overall'];lines=['## 全板配对与覆盖','',
        '负的服务差表示左侧方法缺额更低。区间为 10000 次族内按条件配对重抽。单位依次为归一化服务缺额秒、未交付服务单位秒、人员秒、工具秒与发行费。']
    table(lines,['方法','对照','ΔL [95%]','ΔU [95%]','L 较低／同／较高','Δ人秒','Δ工具秒','Δ费用'],
      ([name(v),name(c),ci(q['L']),ci(q['U']),'/'.join(map(str,q['directions'])),f(q['person']['mean']),f(q['tool']['mean']),f(q['fee']['mean'])]
       for v,comp in all_['paired'].items() for c,q in comp.items()))
    lines+=['### 各族与各层的配对均差','',
            '若 ΔL 与 ΔU 的均值及区间完全相同，单元格合写一份；不同时按 L / U 分列。完整精度和资源差区间见机器可读结果。']
    def dual(q):return ci(q['L']) if q['L']==q['U'] else ci(q['L'])+' / '+ci(q['U'])
    table(lines,['范围','N','方法','相对 B','相对 PA','相对巡检','相对报警','相对 B+','相对消融'],
        ([name(k.split('/')[-1]),g['n'],name(v),*[dual(q[c]) for c in ('B','PA','PERIODIC','ALARM','BPLUS',v+'_NOPROBE')]]
         for k,g in scopes.items() if k!='overall' for v,q in g['paired'].items()))
    lines+=['### 资源、服务与四个业务点的有效关闭','',
        'L、U 和资源按条件取平均；工单和当前关闭按具名实例计数。NA 为未处置且有证据关闭，PV 为处置后经本人复核关闭。四联数分别为 900、1800、2700、3600 秒。']
    table(lines,['范围','条件／工单','角色','L','U','人秒','工具秒','费用','曾达 NA／PV','当前 NA','当前 PV','初检／处置','有错作暴露行'],
        ([name(k.split('/')[-1]),f"{g['n']}/{q['subjects']}",name(v),*[f(q[m]) for m in ('L','U','person','tool','fee')],
          f"{q['closure']['NA']['ever']}/{q['closure']['PV']['ever']}",*['/'.join(map(str,q['closure'][z]['current'])) for z in ('NA','PV')],
          f"{q['phases'].get('I',0)}/{q['phases'].get('A',0)}",q['with_harmful_periods']] for k,g in scopes.items() for v,q in g['by_role'].items()))
    lines+=['## v2 与 v3 的实际分层比例','',
      '四位依次为既有保护有损失、有合法余量、报警及时、事前记录或付费读数及时。下面的分母为全板 72 或每族 12。相同条件编号在两代是各自的抽取位置，两代比例作描述性对照。']
    olds=r['old_v2']['by_family'];news=r['compare_layers'];layers=sorted(set(r['old_v2']['layers'])|{l for x in news.values() for l in x})
    pairs=[('全板',72,r['old_v2']['layers'],dict(Counter(z['layer'] for z in r['rows'])))]
    pairs.extend((name(k),12,olds[k],v) for k,v in news.items())
    table(lines,['范围','N','层','v2 条数（占比）','v3 条数（占比）'],
        ([k,n,l,f"{a.get(l,0)} ({100*a.get(l,0)/n:.1f}%)",f"{b.get(l,0)} ({100*b.get(l,0)/n:.1f}%)"]
         for k,n,a,b in pairs for l in layers))
    lines+=['## 真实关闭初检的逐行消融','',
       '列出每个实际购买初检的条件。配对消融在自己的设施上重新依据可见材料决策，保留必要复核。该子组按购买行为定义，不从其均差推断所有条件。']
    for v,a in r['acquisition'].items():
        lines.append(f"**{name(v)}** 购买初检的条件数为 {len(a['rows'])}/72。买入子组平均 ΔL 为 {f(a['conditional_means']['L'])}，全板平均 ΔL 为 {f(all_['paired'][v][v+'_NOPROBE']['L']['mean'])}。")
        def sequence(t):return '、'.join(f'{at:g}s {s}' for at,s in t) or '无'
        table(lines,['条件','族／层','有初检 L／无初检 L','ΔL／ΔU','Δ人秒／工具秒／费','完整方法实际派工','消融实际派工'],
          ([z['key'],name(z['family'])+'／'+z['layer'],f"{f(z['treatment']['L'])} / {f(z['ablation']['L'])}",
            f"{f(z['delta']['L'])} / {f(z['delta']['U'])}",' / '.join(f(z['delta'][k]) for k in ('person','tool','fee')),
            sequence(z['treatment']['requests']),sequence(z['ablation']['requests'])] for z in a['rows']))
    lines+=['[完整开发记录](development.json.gz) · [单份作业和完整性回执](receipt.json)']
    with (ACT/'tables.md').open('x',encoding='utf8') as fp:fp.write('\n'.join(lines)+'\n')
