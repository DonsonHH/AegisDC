"""Read-only audit/report of the registered response/defer search stop branch."""
from collections import Counter
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/response-defer-search-20261102'
OUT=ROOT/'evidence/response-defer'
OUT.mkdir(exist_ok=True)

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(data):return hashlib.sha256(data).hexdigest()
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def compressed(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:return json.load(f)

summary,protocol,seal=(read(RUN/name) for name in ['summary.json','protocol.json','seal.json'])
proposals=read(RUN/'proposals.json');attempts=read(RUN/'attempts.json')
assert summary['next_action']=='stop_no_improvement_found_in_registered_search'
assert len(attempts)==108 and all(r['status']=='completed' for r in attempts)
assert len(proposals)==12 and len({p['rule_sha256'] for p in proposals})==9
assert not any(p['aggregate']['eligible'] for p in proposals)
assert all(s['selected_proposal'] is None for s in summary['selections'])
assert sha((RUN/'protocol.json').read_bytes())==seal['protocol_sha256']
for name,h in seal['source_sha256'].items():assert sha((RUN/'source'/name).read_bytes())==h
baseline_index=read(ROOT/protocol['baseline']['index_path'])
baselines={}
for case in protocol['development']:
    path=RUN/'baseline'/(case['id']+'-fifo.json.gz')
    assert sha(path.read_bytes())==baseline_index[path.name]['sha256']
    baselines[case['id']]=compressed(path)
unique={};measurement_count=0
for proposal in proposals:
    for ref in proposal['records']:
        if ref['file'] in unique:continue
        r=compressed(RUN/ref['file']);b=baselines[ref['case']]
        assert r['process_sha256']==b['process_sha256']
        identity=lambda rec:{(x['task_id'],x['onset_s'],x['end_s']) for x in rec['anomaly_intervals']}
        assert identity(r)==identity(b)
        assert r['response_config']['response_rule']==proposal['rule']
        assert r['response_config']['extra_dispatched']<=12
        assert all(r['metrics'][k]==0 for k in ['tasks_violating_exact_gap','invalid_assignments','duplicate_reservations'])
        decisions={(x['time_s'],x['agent']):x for x in r['decisions']}
        for gate in r['binary_decisions']:
            d=decisions[(gate['time_s'],gate['agent'])]
            if gate['selected'] is not None:
                chosen=next(c for c in d['candidates'] if c['task']==gate['selected'])
                assert chosen['certificate']['ok'] and chosen['budget_allowed']
            if gate['reason']=='rule':
                event=next(c for c in d['candidates'] if c['task']==gate['event_task'])
                head=next(c for c in d['candidates'] if c['task']==gate['routine_head'])
                assert event['certificate']['ok'] and head['certificate']['ok'] and event['budget_allowed']
                assert gate['event_task']!=gate['routine_head']
                score=proposal['rule']['bias']+sum(proposal['rule']['weights'][k]*v for k,v in gate['features'].items())
                assert abs(score-gate['score'])<1e-12
                assert gate['choice']==('respond' if score>=0 else 'defer')
                assert gate['selected']==(gate['event_task'] if score>=0 else gate['routine_head'])
                if gate['choice']=='defer':
                    event_state=r['public_events'][event['event_id']]
                    assert event_state['visible_s']<=gate['time_s']<=event_state['expires_s']
                    assert event_state['measurement_s'] is None or event_state['measurement_s']>gate['time_s']
        events=r['inspection_events'];measurement_count+=len(events)
        for gap in r['exact_task_gaps']:
            times=[0.]+sorted(e['time_s'] for e in events if e['task']==gap['task'])+[1800.]
            maximum=max(y-x for x,y in zip(times,times[1:]))
            assert maximum<= (300 if gap['task_id'].startswith('thermal:') else 600)
            assert maximum==gap['maximum_gap_including_initial_and_terminal_s']
        unique[ref['file']]=r
assert len(unique)==108
rows=[]
for p in proposals:
    a=p['aggregate'];counts=Counter();different=0
    for ref in p['records']:
        r=unique[ref['file']];b=baselines[ref['case']]
        counts.update(d['choice'] for d in r['binary_decisions'] if d['reason']=='rule')
        different+=r['action_sha256']!=b['action_sha256']
    rows.append({'chain':p['chain'],'proposal':p['proposal'],'rule_sha256':p['rule_sha256'],
        'confirmed_segments':70+a['net'],'gained':a['gained'],'lost':a['lost'],'net':a['net'],
        'mean_wait_s':a['mean_wait_s'],'mean_travel_delta_pct':a['mean_travel_delta_pct'],
        'mean_completion_loss_pct':a['mean_completion_loss_pct'],'changed_process_actions':different,
        'defer_decisions':counts['defer'],'respond_decisions':counts['respond'],
        'cached_case_records':sum(x['cached'] for x in p['records']),'eligible':a['eligible']})
for name in ['summary.json','proposals.json','attempts.json','seal.json','protocol.json','selected-search.json']:
    shutil.copyfile(RUN/name,OUT/name)
write(OUT/'audit.json',{'status':'PASS','unique_records':108,'historical_baseline_records':12,
    'unique_rules':9,'proposal_opportunities':12,'measurements_in_unique_records':measurement_count,
    'scope':'Identity, paired process/intervals, canonical rules, certified choices, gate signs, deferred event lifetime and complete actual gaps; no environment or model rerun.'})
with (OUT/'results.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
write(OUT/'local-artifacts.json',{p.relative_to(RUN).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())}
    for p in RUN.rglob('*') if p.is_file()})
text='''# 响应／暂缓搜索：未找到超过FIFO的已登记规则

本包按预先登记的停止分支结束。完成3条搜索链、每链4次候选机会；存在3次跨链重复规则，因此实际为9条不同规则×12个已见开发过程＝108次新环境评价，而不是144份不同规则执行。12份旧FIFO原件按字节复用，不算新执行。失败0，研究模型调用0，训练0；新确认条件未执行。

## 结果

原FIFO在这些过程确认70/89段。搜索规则覆盖风险阈值、15—90秒年龄阈值及风险—耗时—返回余量组合。候选确认28—60段，均未达到“相对FIFO总净增至少1段、移动增加≤5%、完成量损失≤2%、安全违规零”的开发保留条件；三个链均保留FIFO。

|链|规则族|确认/89段|新增/丢失（相对FIFO）|净增|平均截尾等待/秒|移动变化/%|完成量损失/%|暂缓决策|与FIFO动作不同的过程|缓存复用条件数|
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
'''
for r in rows:
    text+=f"|{r['chain']}|{r['proposal']}|{r['confirmed_segments']}|{r['gained']}/{r['lost']}|{r['net']}|{r['mean_wait_s']:.2f}|{r['mean_travel_delta_pct']:.3f}|{r['mean_completion_loss_pct']:.3f}|{r['defer_decisions']}|{r['changed_process_actions']}|{r['cached_case_records']}|\n"
text+='''
成本均值的分母为12个开发过程，比较基准是FIFO。负的完成量损失表示完成次数增加；次数增加和较短路程不能补偿本协议中的确认损失。暂缓是决策次数，同一个待处理事件可能多次被考虑；不是新的独立样本。

## 怎样解释这个负结果

这些候选实际改变了动作：除一条规则在11个过程不同，其余均在12个过程不同。因此结果不是“没有决策机会”或规则从未生效。当前最好的候选确认60段，较FIFO少10段；有些候选新增2—3段确认，但同时丢失更多段。

该结果限定为所登记的9条不同规则和12个已见开发过程。它不证明整个线性规则空间无解，也不等于模型反馈已经被检验无效。搜索前已规定：若没有规则通过开发保留条件，则不继续花费模型调用，不读取新确认结果。现按该分支停止，不追加规则、修改阈值或重开旧确认包。

## 接口与工程证据

响应规则只读取四个公开数值特征。零规则与旧FIFO逐项派单及专业测量一致；暂缓执行合法头并保留事件，只在完成例行头时推进游标。单边合法动作由固定选择器处理，规则不能空等、改变TTL、资格或返回检查。

工程验收与这108次开发评价分开：使用已见种子及候选夹具完成87项测试；零研究模型调用。只读审计检查108份唯一执行的规则身份、动作证书、符号语义、暂缓事件生命周期和实际完整重访间隔，见[audit.json](audit.json)。

## 复核材料

[冻结方案](protocol.json) · [12次候选及全部开发配对](proposals.json) · [108次尝试](attempts.json) · [结果CSV](results.csv) · [源码封存](seal.json) · [原件SHA索引](local-artifacts.json)。本地完整目录：`runs/response-defer-search-20261102`。

只读交付脚本：`python scripts/deliver_response_search.py`。这一步不重跑环境。后续研究若改变规则空间、反馈门槛或预算，需要作为新协议明确记录；当前保留的12个新确认过程仍未被执行。
'''
(OUT/'README.md').write_text(text,encoding='utf-8',newline='\n')
parser=argparse.ArgumentParser()
parser.add_argument('--package-output')
args=parser.parse_args()
if args.package_output:
    folder=Path(args.package_output);folder.mkdir(parents=True,exist_ok=False)
    archive=folder/'response-defer-search-20261102.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for p in RUN.rglob('*'):
            if p.is_file():z.write(p,'run/'+p.relative_to(RUN).as_posix())
        for p in OUT.iterdir():
            if p.is_file() and p.name not in ('package.json','publication.json'):
                z.write(p,'report/'+p.name)
        z.write(Path(__file__),'scripts/deliver_response_search.py')
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name,identity in read(OUT/'local-artifacts.json').items():
            assert sha(z.read('run/'+name))==identity['sha256']
    receipt={'name':archive.name,'bytes':archive.stat().st_size,'sha256':sha(archive.read_bytes())}
    write(folder/'package.json',receipt);write(OUT/'package.json',receipt)
print(json.dumps({'audit':'PASS','unique_records':108,'unique_rules':9,'measurement_count':measurement_count,'decision':summary['next_action']}))
