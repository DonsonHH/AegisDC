"""Render precomputed paired estimates into the registered public report appendix."""
from workpackage import ACT,save

LABEL={'V_COST':'V\\*\\*','V_COST_NOPROBE':'V\\*\\*−probe','B_COST':'B_cost','PA':'PA','B':'B',
       'WATER_HEAT':'水侧／热','NETWORK_POWER':'网络／供电','RESERVE_TRANSFER':'有限备用','COOLING_ACCESS':'冷却／通行','LONDON':'伦敦式','NETHERLANDS':'荷兰式',
       'overall':'全板','BASE36':'原 v3 同一 36 条'}
def lab(name):return LABEL.get(name,name)
def num(x):return '未定义' if x is None else f'{x:.2f}'
def interval(q):return f"{num(q['mean'])} [{num(q['lo'])}, {num(q['hi'])}]"
def sign(q):return '／'.join(map(str,q['directions']))
def tab(lines,names,values):
    def row(v):return '| '+' | '.join(map(str,v))+' |'
    lines.extend(['',row(names),row(['---']*len(names))]);lines.extend(row(z) for z in values);lines.append('')
def scope(k):return ('维护 '+k.split('/')[1]+' 秒') if k.startswith('duration/') else lab(k.rsplit('/',1)[-1])


def render(r):
    lines=['## B_cost 在 72 条原 v3 条件上的配对比较','',
        '本节差值为 B_cost 减所列对照。L 为归一化缺额秒，U 为未交付服务单位秒；每条的人员、工具为实际占用秒，费用为发行费单位。方括号为双侧 95% 族内配对重抽区间。']
    table_rows=[]
    for k,s in r['base'].items():
        for c in ('V_COST','V_COST_NOPROBE','B','PA'):
            a=s['paired'][c]
            table_rows.append([scope(k),s['n'],lab(c),interval(a['L']),interval(a['U']),sign(a),interval(a['person']),interval(a['tool']),interval(a['fee'])])
    tab(lines,['范围','N','对照','ΔL [95%]','ΔU [95%]','L 较低／同／较高','Δ人秒 [95%]','Δ工具秒 [95%]','Δ费用 [95%]'],table_rows)
    lines+=['### 原设置的绝对均值与关闭','',
            '各阶段当前有效 NA（未处置且有证据关闭）与 PV（处置后具名复核关闭）分别按 900、1800、2700、3600 秒排列。工单为跨条件的具名实例数，曾达按类型在每个实例内去重。']
    tab(lines,['范围','条件／工单','角色','L','U','人秒','工具秒','费用','曾达 NA／PV','四时点 NA','四时点 PV'],
        ([scope(k),f"{s['n']}/{v['instances']}",lab(role),*[num(v[z]) for z in ('L','U','person','tool','fee')],
          f"{v['closures']['NA']['ever']}/{v['closures']['PV']['ever']}",*['／'.join(map(str,v['closures'][typ]['current'])) for typ in ('NA','PV')]]
         for k,s in r['base'].items() for role,v in s['by_role'].items()))
    lines+=['## 同一 36 条条件下的参数敏感性','',
        '本节差值为 V\\*\\* 减所列对照。原 v3 一列另据相同 36 个键从已存结果取出。所有设置共享私有原因及外生时钟。']
    tab(lines,['设置','条件','对照','ΔL [95%]','ΔU [95%]','较低／同／较高','Δ人秒 [95%]','Δ工具秒 [95%]','Δ费用 [95%]'],
      ([lab(k),o['n'],lab(c),interval(q['L']),interval(q['U']),sign(q),interval(q['person']),interval(q['tool']),interval(q['fee'])]
       for k,v in r['sensitivity'].items() for o in (v['scopes']['overall'],) for c,q in o['paired'].items()))
    tab(lines,['设置','有原生认证的最小值／36','Σ(V\\*\\*−L*)','Σ(P−L*)','剩余比例','未决条件'],
      ([lab(k),str(36-len(g['unresolved']))+'/36',num(g['numerator']),num(g['denominator']),
        '未定义' if g['ratio'] is None else f"{100*g['ratio']:.2f}%",'、'.join(g['unresolved']) or '无']
       for k,v in r['sensitivity'].items() for g in (v['gap'],)))
    lines+=['### S0 中 V\\*\\* 服务较差的实际条件','']
    if r['S0_worse']:
        tab(lines,['条件','族','V\\*\\* L','B L','多出的缺额秒'],([z['key'],lab(z['family']),num(z['V']),num(z['B']),num(z['delta'])] for z in r['S0_worse']))
    else:lines.append('36 行均未出现 V\\*\\* 比 B 服务较差的情况。')
    lines+=['[逐位置输入、实际请求、评分及统计结果](development-result.json.gz) · [完整性及作业回执](receipt.json)']
    with (ACT/'report-tables.md').open('x',encoding='utf8') as out:out.write('\n'.join(lines)+'\n')
    out=dict(capture=r['capture'],base=r['base']['overall'],families={k:v['paired'] for k,v in r['base'].items() if k.startswith(('family/','layer/','duration/'))},
        settings={k:dict(pairs=v['scopes']['overall']['paired'],gap=v['gap']) for k,v in r['sensitivity'].items()},S0_worse=r['S0_worse'])
    save(ACT/'headline.json',out)
