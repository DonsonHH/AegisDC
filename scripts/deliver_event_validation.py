"""Audit saved executions and build the final report; no policy/process reruns."""
import csv
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import zipfile
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from patrol_rsi.active_inspection import graph_for, measured_anomaly
from patrol_rsi.aisles import build_agents, DEADLINES
from patrol_rsi.facility_observation import eligible

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(data):return hashlib.sha256(data).hexdigest()
def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

run=ROOT/'runs/event-validation-amended-20261102'
out=ROOT/'evidence/event-validation/final';out.mkdir(parents=True,exist_ok=True)
protocol=read(run/'protocol.json');summary=read(run/'summary.json');attempts=read(run/'attempts.json')
rows=read(run/'rows.json');pairs=read(run/'pairs.json');seal=read(run/'seal.json')
assert len(attempts)==109 and sum(a['status']=='completed' for a in attempts)==108
assert sum(a['status']=='failed' for a in attempts)==1
assert len(rows)==108 and len(pairs)==36 and len(list(run.glob('*.json.gz')))==108
assert len({(r['case'],r['method']) for r in rows})==108
assert sha((run/'protocol.json').read_bytes())==seal['protocol_sha256']
for name,h in seal['source_sha256'].items():assert sha((run/'source'/name).read_bytes())==h
for name,v in read(run/'prior-index.json').items():
    assert sha((run/'prior'/name).read_bytes())==v['sha256']
for row in read(run/'prior/rows.json'):
    assert (run/row['record']).read_bytes()==(run/'prior'/row['record']).read_bytes()

graph=graph_for(128,'open');tasks=graph.tasks;agents=build_agents(graph,'provisioned')
total_measurements=0;role_totals={};raw={};checks=[]
for row in rows:
    with gzip.open(run/row['record'],'rt',encoding='utf-8') as f:r=json.load(f)
    raw[(row['case'],row['method'])]=r
    events=r['inspection_events'];intervals=r['anomaly_intervals'];metrics=r['metrics']
    assert len(events)==metrics['completed_inspections']==row['completed_inspections']
    total_measurements+=len(events)
    by_task={j:[] for j in range(len(tasks))}
    event_keys=set()
    for e in events:
        j=e['task'];agent=agents[e['agent']]
        assert j in agent['tour'] and eligible(agent['role'],tasks[j])
        assert e['role']==agent['role'] and e['service_s']==tasks[j].service_s and e['calibrated']
        assert bool(measured_anomaly(tasks[j],e['measurement']))==e['alarm']
        by_task[j].append(e['time_s']);event_keys.add((e['agent'],j,e['time_s']))
    assert len(event_keys)==len(events)
    for j,times in by_task.items():
        ordered=[0.]+sorted(times)+[1800.]
        assert max(b-a for a,b in zip(ordered,ordered[1:]))<=DEADLINES[tasks[j].kind]+1e-9
    for interval in intervals:
        found=[e['time_s'] for e in events if e['task']==interval['task'] and e['alarm']
               and interval['onset_s']<e['time_s']<=interval['end_s']]
        assert interval['first_confirmation_s']==(min(found) if found else None)
        assert interval['detected']==bool(found)
    assert sum(i['detected'] for i in intervals)==metrics['confirmed_segments']==row['confirmed_segments']
    assert len(intervals)-sum(i['detected'] for i in intervals)==row['missed_segments']
    dispatches=r.get('dispatches',r.get('local_dispatches'))
    positions={a['id']:a['position'] for a in agents};free={a['id']:0. for a in agents}
    travel=service=0.;dispatch_keys=set()
    for d in dispatches:
        i,j=d['agent'],d['task'];start=d.get('time_s',d.get('dispatch_time_s'))
        cert=d['certificate'];assert cert['ok']
        finish=cert['candidate_finish_s'] if 'candidate_finish_s' in cert else cert['segment_completion_s'][0]
        distance=graph.path(positions[i],tasks[j].position_m)[0]
        assert finish==start+math.ceil((distance+tasks[j].service_s)/5-1e-10)*5
        assert start>=free[i] and (i,j,finish) in event_keys
        free[i]=finish;positions[i]=tasks[j].position_m
        travel+=distance;service+=tasks[j].service_s;dispatch_keys.add((i,j,finish))
    assert dispatch_keys==event_keys
    assert abs(travel-metrics['travel_m'])<1e-6 and abs(service-metrics['service_s'])<1e-6
    if row['method']!='tour':
        assert sum(d['extra_event_visit'] for d in dispatches)<=protocol['extra_visit_budget']
        assert sum(e['extra_event_visit'] for e in events)==row['extra_event_visits']
    for kind in ['thermal','electrical','cooling','control']:
        key=(row['group'],row['method'],kind);subtotal=role_totals.setdefault(key,[0,0])
        subtotal[0]+=sum(i['kind']==kind for i in intervals)
        subtotal[1]+=sum(i['kind']==kind and i['detected'] for i in intervals)
    checks.append({'record':row['record'],'measurements':len(events),'status':'PASS'})
for p in pairs:
    t,f,s=(raw[(p['case'],m)] for m in ['tour','fifo','shuffled'])
    assert len({r['process_sha256'] for r in [t,f,s]})==1
    def detected(r):return {(i['task_id'],i['onset_s'],i['end_s']) for i in r['anomaly_intervals'] if i['detected']}
    for name,other in [('fifo_minus_tour',t),('fifo_minus_shuffled',s)]:
        a,b=detected(f),detected(other)
        assert (len(a-b),len(b-a),len(a)-len(b))==tuple(p[name][k] for k in ['gained','lost','net'])
for group,methods in summary['groups'].items():
    for method,aggregate in methods.items():
        selected=[r for r in rows if r['group']==group and r['method']==method]
        for key in ['anomaly_segments','confirmed_segments','missed_segments','extra_event_visits']:
            assert aggregate[key]==sum(r[key] for r in selected)
for contrast in ['fifo_minus_tour','fifo_minus_shuffled']:
    values=np.asarray([p[contrast]['net'] for p in pairs if p['group']=='coupled'])
    rng=np.random.default_rng(protocol['bootstrap_seed'])
    resampled=values[rng.integers(0,len(values),(protocol['bootstrap_replicates'],len(values)))].mean(axis=1)
    stat=summary['primary_comparisons'][contrast]['net_confirmations']
    assert stat['mean']==float(values.mean())
    assert np.allclose(stat['percentile95'],np.quantile(resampled,[.025,.975]),atol=1e-12)
audit={'status':'PASS','records':108,'actual_attempts':109,'failed_attempts_preserved':1,'reused_records_byte_identical':9,
       'measurements_checked':total_measurements,'checks':checks,
       'scope':'Saved measurement alarm and interval confirmation, ownership/qualification, no overlapping agent executions, dispatch completion timing, travel/service totals, all initial/intermediate/terminal gaps, insertion caps, paired outcomes and source hashes. Physical process was not rerun.',
       'by_role':[{'group':g,'method':m,'kind':k,'segments':v[0],'confirmed':v[1]} for (g,m,k),v in role_totals.items()]}
write(out/'audit.json',audit)
for name in ['summary.json','rows.json','pairs.json','results.csv','attempts.json','seal.json','protocol.json','inheritance.json']:
    shutil.copyfile(run/name,out/name)
index={str(p.relative_to(run)).replace('\\','/'):{'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in run.rglob('*') if p.is_file()}
write(out/'local-artifacts.json',index)

lines=['# 有限验证完成：在预定热—冷耦合条件中通过收益与成本门槛','',
       '本包结束，冻结FIFO事件响应为该适用域的研究基线。默认工程示例仍为Tour。此次没有模型调用或训练，结果不证明反馈或RSI增益。','',
       '按用户确认的修订累计109次尝试：108次成功、1次原失败。9份成功旧记录按字节复用，补跑99次，无新增失败。前9份保留旧源码封存，其余使用修订源码；两种来源在原件包中分别保留。','',
       '主分析按12个独立过程种子配对，每个只有一个预定复合故障条件；89个异常段不是89个独立样本。另有12个轻微扰动、6个健康高噪声与6个人工虚假提示条件，全部报告。','',
       '## 主比较：12个复合故障过程','',
       '|方法|确认/异常段|漏检|平均截尾等待/秒|平均移动/米|平均服务/人秒|平均完成量|额外访问合计|',
       '|---|---:|---:|---:|---:|---:|---:|---:|']
for method,label in [('tour','Tour'),('fifo','FIFO'),('shuffled','同专业目标置乱')]:
    m=summary['groups']['coupled'][method]
    waits=[r['consequence_weighted_censored_delay_s'] for r in rows if r['group']=='coupled' and r['method']==method]
    lines.append(f"|{label}|{m['confirmed_segments']}/{m['anomaly_segments']}|{m['missed_segments']}|{sum(waits)/len(waits):.2f}|{m['mean_travel_m']:.2f}|{m['mean_service_s']:.2f}|{m['mean_completed_inspections']:.2f}|{m['extra_event_visits']}|")
lines+=['','|配对比较|平均净增确认/过程|探索性95%区间|正/零/负过程|新增/丢失总段数|','|---|---:|---|---|---|']
for key,label in [('fifo_minus_tour','FIFO − Tour'),('fifo_minus_shuffled','FIFO − 置乱')]:
    m=summary['primary_comparisons'][key];n=m['net_confirmations']
    lines.append(f"|{label}|{n['mean']:.2f}|[{n['percentile95'][0]:.2f}, {n['percentile95'][1]:.2f}]|{n['positive']}/{n['zero']}/{n['negative']}|{round(m['gained']*12)}/{round(m['lost']*12)}|")
lines+=['','区间用预先规定的10000次过程级bootstrap计算；不代表总体泛化或经过功效校准的试验。FIFO相对Tour净增42段，由新增45段、丢失3段构成，不能说每个对象都改善。','',
        '移动平均增加58.92米（0.50%），平均少完成4.67次（0.33%）。服务时间减少伴随完成量下降，不单独称效率提升。各组重访、资格与预约冲突检查为零；另外从108份原件复核实际完成时刻、专业资格、执行区间、移动/服务总量和完整重访间隔，见[audit.json](audit.json)。','',
        '## 非主比较条件的成本','',
        '|条件|方法|条件数|评价异常段|额外访问合计|相对Tour平均多走/米|平均完成量变化|','|---|---|---:|---:|---:|---:|---:|']
for group,label in [('healthy','健康高噪声'),('healthy_spurious','健康＋人工虚假提示'),('mild','60秒冷板扰动')]:
    base=summary['groups'][group]['tour']
    for method in ['fifo','shuffled']:
        m=summary['groups'][group][method]
        lines.append(f"|{label}|{method}|{m['cases']}|{m['anomaly_segments']}|{m['extra_event_visits']}|{m['mean_travel_m']-base['mean_travel_m']:.2f}|{m['mean_completed_inspections']-base['mean_completed_inspections']:.2f}|")
lines+=['','这些条件未形成评价异常段，异常等待不填零。人工虚假提示是受控压力测试，不估计真实设备误报率；轻微扰动引发的正常测量也不直接命名为错误报警。','',
        '## 事件生命周期与机会','',
        '|复合故障方法|正常闭合|过期未测|晚测|同刻揭示与测量|有先前信号的测量|多个合法事件竞争决策|','|---|---:|---:|---:|---:|---:|---:|']
for method in ['fifo','shuffled']:
    m=summary['groups']['coupled'][method]['event_outcomes']
    competition=sum(r['multiple_legal_event_decisions'] for r in rows if r['group']=='coupled' and r['method']==method)
    lines.append('|'+method+'|'+'|'.join(str(m.get(k,0)) for k in ['normal_measured','expired','measured_late','same_time_measurement','prior_signal_measurement'])+f'|{competition}|')
lines+=['','同刻揭示的记录不能算提前响应；过期及晚测是事件账本状态，不等同于异常段的漏检或确认。TTL是派单有效期，不是120秒完成保证。','',
        '## 逐过程保留取舍','',
        '|过程|定位锚点机柜/故障pod|锚点远程测温|相位/秒|异常段|FIFO新增/丢失（相对Tour）|净增|移动变化/米|完成量变化|','|---|---|---|---:|---:|---|---:|---:|---:|']
case_by_id={c['id']:c for c in protocol['cases']}
for p in pairs:
    if p['group']!='coupled':continue
    s=case_by_id[p['case']]['spec'];d=p['fifo_minus_tour'];rack=s['fault_rack']
    lines.append(f"|{p['case']}|{rack}/{rack//8}|{'有' if rack%4==0 else '无'}|{s['fault_start_s']}|{p['anomaly_segments']}|{d['gained']}/{d['lost']}|{d['net']}|{d['travel_delta_m']:.2f}|{d['completed_delta']}|")
lines+=['','复合故障实际作用于pod，锚点机柜仅确定所属pod；每个pod均有两个远程测温点。锚点有无测点不等于整个故障区域有无遥测，不能据此声称已验证无遥测pod的泛化。轻微冷板扰动才直接作用于指定单机柜。等待先在各过程内按后果权重计算并对漏检截尾，再平均12个过程。','',
        '专业分项：热异常77段，Tour/FIFO/置乱分别确认23/59/21段；制冷异常12段，分别确认5/11/4段。电气与自控未形成评价异常段。','',
        '## 决策与边界','',
        '预定门槛全部通过：平均净增≥1段且区间下界>0、平均移动增加≤5%、平均完成量损失≤2%、安全违规为零、至少8个主过程形成异常。FIFO相对置乱也通过同一确认增益门槛，支持正确风险位置在本包条件下的任务价值。','',
        '两个事件组共用每回合12次补查上限，实际访问为89与81次，不能声称严格等成本。置乱保留专业和所属任务，但会改变距离、可行性及后续观测；它检验的是风险位置干预下的整套在线机制，不把全部差异归于一个孤立的信息分量。','',
        '适用域为合成热—冷耦合、确定通道和服务时间、固定所属、名义估计；不主张四专业全面泛化、现场效果或算法新颖性。所有条件现为已见材料。停止本包，不追加种子或改变优先级。下一项只准备“现在插入／暂缓”的有限后果反馈协议，另定共同输入和推理预算、失败计费、多链与新确认集。','',
        '## 复核与原件','',
        '[108次逐条件CSV](results.csv) · [36条件配对增减](pairs.json) · [封存协议](protocol.json) · [109次尝试账本](attempts.json) · [完整原件SHA索引](local-artifacts.json)。',
        '生成与只读复核：`python scripts/deliver_event_validation.py --package-output runs/new-delivery-directory`，使用新输出目录。本地完整目录：`runs/event-validation-amended-20261102`。']
(out/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
parser=argparse.ArgumentParser()
parser.add_argument('--package-output',required=True)
args=parser.parse_args()
delivery=Path(args.package_output);delivery.mkdir(parents=True,exist_ok=False)
archive=delivery/'event-validation-20261102.zip'
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
    for p in run.rglob('*'):
        if p.is_file():z.write(p,'run/'+str(p.relative_to(run)).replace('\\','/'))
    for p in out.iterdir():
        if p.is_file() and p.name!='package.json':z.write(p,'report/'+p.name)
    z.write(Path(__file__),'scripts/deliver_event_validation.py')
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for name,v in index.items():assert sha(z.read('run/'+name))==v['sha256']
package={'name':archive.name,'bytes':archive.stat().st_size,'sha256':sha(archive.read_bytes())}
write(delivery/'package.json',package);write(out/'package.json',package)
print(json.dumps({'audit':'PASS','records':108,'measurements_checked':total_measurements,'package':package},ensure_ascii=False))
