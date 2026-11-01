"""Record-only four-part delivery. Never run a simulator or a language model."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'research/2026-11-01-local-reorder'
REMOTE='/share/home/renly/renly-patrol-rsi/runs/20261101-local-reorder/'
sys.path.insert(0,str(ROOT/'src'))
from patrol_rsi.local_score import ScoreExpression,BASE_EXPRESSION


def read(path):return json.loads(path.read_bytes())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf8',newline='\n')
def number(x):return '—' if x is None else f'{x:.3f}'.rstrip('0').rstrip('.') if isinstance(x,float) else str(x)


def summarize(result):
    rows=result['rows'];m=[v['metrics'] for v in rows]
    waits=[v['consequence_weighted_censored_delay_s'] for v in m if v['consequence_weighted_censored_delay_s'] is not None]
    return {'conditions':len(rows),'mean_missed':statistics.mean(v['missed_segments'] for v in m),
        'mean_wait_event_conditions_s':statistics.mean(waits) if waits else None,
        **{'mean_'+k:statistics.mean(v[k] for v in m) for k in ('travel_m','service_s','completed_inspections',
            'current_round_unfinished_obligations','unfinished_committed_tasks','completed_rounds_total')},
        'maximum_gap_s':max(v['maximum_exact_gap_s'] for v in m),
        'gap_violations':sum(v['tasks_violating_exact_gap'] for v in m),
        'numeric_failures':sum(v['numeric_scoring_failures'] for v in m)}


def rank_parent(decision,expression):
    legal=[c for c in decision['candidates'] if c['certificate']['ok']]
    legal.sort(key=lambda c:(not c['original'],c['order']))
    selected=legal[0];score=expression.evaluate(selected['features'])
    for c in legal[1:]:
        x=expression.evaluate(c['features'])
        if x<score-1e-9:selected,score=c,x
    return selected


def make_timeline(qsteps,load_record):
    choices=[]
    for label,step in reversed(list(qsteps.items())):
        if step['candidate'] is None:continue
        expression=ScoreExpression(step['parent']['policy']['score_expression'])
        for row in sorted(step['candidate']['rows'],key=lambda v:v['case_id']):
            if not row['metrics']['anomaly_segments']:continue
            value=load_record(row)
            for d in sorted(value['local_decisions'],key=lambda d:(d['time_s'],d['agent'])):
                parent=rank_parent(d,expression)
                if parent['order']==d['selected_order']:continue
                choices.append((any(p['risk']>1e-9 for p in d['public_tasks']),label,step,row,value,d,parent))
    if not choices:return {'observed':False,'reason':'No same-state action difference from either actual model candidate.'}
    # First actual difference with a positive public cue, otherwise first actual
    # difference. This is a post hoc explanatory illustration, not a new trial.
    _,label,step,row,value,d,parent=next((v for v in choices if v[0]),choices[0])
    selected=next(c for c in d['candidates'] if c['order']==d['selected_order'])
    public={p['task']:p for p in d['public_tasks']};events=[]
    for j in d['selected_order']:
        dispatch=next((v for v in value['local_dispatches'] if v['agent']==d['agent'] and v['round_id']==d['round_id'] and v['task']==j),None)
        finish=next((v for v in value['obligation_events'] if v['agent']==d['agent'] and v['round_id']==d['round_id'] and v['task']==j),None)
        measured=next((v for v in value['inspection_events'] if finish is not None and v['time_s']==finish['time_s'] and v['agent']==d['agent'] and v['task']==j),None)
        events.append({'task':j,'public_at_decision':public[j],
            'dispatch_time_s':dispatch['dispatch_time_s'] if dispatch else None,
            'completion_time_s':finish['time_s'] if finish else None,'actual_measurement':measured,
            'same_state_original_planned_finish_s':next(c for c in d['candidates'] if c['original'])['certificate']['first_completion_s'][str(j)],
            'parent_expression_same_state_planned_finish_s':parent['certificate']['first_completion_s'][str(j)],
            'actual_anomaly_outcomes_evaluation_only':[v for v in value['anomaly_intervals'] if v['task']==j]})
    return {'observed':True,'selection':'Post hoc explanatory first case/time with actual Q-vs-parent same-state order difference and a positive public cue; not another independent experiment.',
        'label':label,'case_id':row['case_id'],'source_record_sha256':row['record_sha256'],'source_record_path':row['record_path'],
        'time_s':d['time_s'],'agent':d['agent'],'round_id':d['round_id'],
        'original_order':d['window'],'parent_same_state_order':parent['order'],'actual_selected_order':d['selected_order'],
        'parent_expression':step['parent']['policy']['score_expression'],
        'model_expression':step['candidate']['policy']['score_expression'],
        'parent_score_on_parent_order':expression.evaluate(parent['features']),
        'parent_score_on_selected_order':expression.evaluate(selected['features']),
        'model_score_on_parent_order':ScoreExpression(step['candidate']['policy']['score_expression']).evaluate(parent['features']),
        'model_score_on_selected_order':selected['score'][0],
        'all_public_tasks':d['public_tasks'],'all_candidate_features_and_safety':d['candidates'],
        'all_planned_completion_deltas_vs_original':d['completion_deltas_vs_original'],
        'actual_inspections':events,'episode_outcome':row['metrics'],
        'causal_limit':'Candidate ranking replay uses only recorded public features. Parent alternative at this exact state is a geometric counterfactual, not another actual rollout. Full-episode task scores come from the completed real simulation; no single favorable alarm proves net benefit.'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();run=a.run.resolve()
    baseline=read(run/'baselines-complete.json');s=read(run/'S-complete.json')
    q={name:read(run/f'{name}-complete.json') for name in ('Q1','Q2')}
    frozen=read(run/'selection-frozen.json');confirmation=read(run/'confirmation-complete.json')
    signature=frozen['execution_signature'];cache={}
    def load_record(row):
        relative=row['record_path'].removeprefix(REMOTE)
        if relative==row['record_path']:raise ValueError('Unexpected record namespace')
        path=run/relative
        if sha(path)!=row['record_sha256']:raise ValueError('Raw hash mismatch')
        if path not in cache:cache[path]=json.loads(gzip.decompress(path.read_bytes()))
        value=cache[path]
        if value['execution_signature']!=signature or value['case_id']!=row['case_id']:raise ValueError('Raw identity mismatch')
        if value['policy']!=row['policy']:raise ValueError('Policy bytes mismatch')
        if not row['audit']['passed']:raise ValueError('Audit not passed')
        return value
    dev={**baseline,**{f'S{v["round"]}':v['candidate'] for v in s['rounds']},
        **{name:step['candidate'] for name,step in q.items() if step['candidate'] is not None}}
    table=[];summary={}
    for partition,methods in [('development',dev),('confirmation',confirmation['methods'])]:
        summary[partition]={name:summarize(result) for name,result in methods.items()}
        for name,result in methods.items():
            if len(result['rows'])!=6:raise ValueError('Six fixed conditions')
            for row in result['rows']:
                value=load_record(row)
                if value['metrics']!=row['metrics']:raise ValueError('Metric receipt mismatch')
                if any(value['metrics'][k]!=0 for k in ('extra_checks','tasks_violating_exact_gap','numeric_scoring_failures')):
                    raise ValueError('Selected experiment constraints failed')
                table.append({'partition':partition,'method':name,'case_id':row['case_id'],
                    'policy_id':row['policy_id'],'expression':row['policy'].get('score_expression',row['policy']['method']),
                    **row['specification'],**row['metrics'],'record_sha256':row['record_sha256'],
                    'record_path':row['record_path'],'execution_signature':row['execution_signature']})
    for name,value in frozen['development_receipts'].items():
        if sha(run/name)!=value:raise ValueError('Selection receipt changed after freeze')
    if confirmation['selection_frozen_sha256']!=sha(run/'selection-frozen.json'):raise ValueError('Confirmation selection binding')
    if frozen['registration_at_freeze_sha256']!=sha(run/'registration-at-freeze.json'):raise ValueError('Fresh registration binding')
    q2_startup=read(run/'model-round-2'/'startup.json')
    if q2_startup['feedback_Q1_receipt_sha256']!=sha(run/'Q1-complete.json'):raise ValueError('Actual Q1 feedback before Q2')
    attempts=[json.loads(line) for line in (run/'environment-attempts.jsonl').read_text().splitlines()]
    calls=[json.loads(line) for line in (run/'model-calls.jsonl').read_text().splitlines()]
    if len(attempts)>90 or len(calls)>4:raise ValueError('Hard experimental cap')
    actual_rows=[read(path) for path in sorted((run/'evaluations').glob('*/complete.json'))]
    current=[row for row in actual_rows if row['execution_signature']==signature]
    unique={(v['execution_signature'],v['case_id'],v['policy_id']) for v in current}
    if len(unique)!=len(current):raise ValueError('Duplicate actual current identity')
    for row in current:load_record(row)
    timeline=make_timeline(q,load_record)
    safety={'actual_current_identities':len(current),'all_raw_hashes_and_metrics_verified':True,
        'all_actual_audits_pass':all(v['audit']['passed'] for v in current),
        'recomputed_candidate_proofs':sum(v['audit']['independent_candidate_proofs'] for v in current),
        'actual_obligation_settlements':sum(v['audit']['actual_obligation_settlements'] for v in current),
        'all_six_Tour_regressions_pass':all(row['legacy_Tour_regression']['passed'] for row in baseline['T']['rows']),
        'candidate_rejections':{},'alternative_decision_count':sum(v['metrics']['decision_points_with_alternative'] for v in current)}
    for row in current:
        for reason,count in row['rejection_counts'].items():safety['candidate_rejections'][reason]=safety['candidate_rejections'].get(reason,0)+count
    model=[]
    for receipt in calls:
        area=run/f'model-round-{receipt["round"]}'/f'call-{receipt["number"]:02d}'
        model.append({'receipt':receipt,'start':read(area/'start.json'),
            'response':read(area/'response.json') if (area/'response.json').exists() else None,
            'accepted_interface':read(area/'accepted-interface.json') if (area/'accepted-interface.json').exists() else None,
            'failure':read(area/'failed.json') if (area/'failed.json').exists() else None})
    actual_children=sum(step['candidate'] is not None for step in q.values())
    budget={'environment_attempts':len(attempts),'environment_cap':90,'real_Qwen_calls':len(calls),'model_cap':4,
        'neural_training_runs':0,'actual_model_children_evaluated':actual_children,'current_completed_identities':len(current),
        'development_identities':sum(v['partition']=='development' for v in current),
        'confirmation_identities':sum(v['partition']=='confirmation' for v in current),
        'superseded_or_failed_actual_attempts':len(attempts)-len(current),
        'logical_table_rows':len(table),'logical_confirmation_methods':5,
        'actual_confirmation_policy_identities':confirmation['actual_confirmation_identities'],
        'jobs':read(run/'job-accounting.json')}
    if budget['jobs']['allocated_CPU_core_minutes']>360:raise ValueError('CPU budget')
    inventory=[{'path':path.relative_to(STAGE).as_posix(),'sha256':sha(path),'bytes':path.stat().st_size}
        for path in sorted(run.rglob('*')) if path.is_file()]
    result={'schema':'local-reorder-delivery-v1','status':'completed_finite_experiment',
        'research_baseline':'4903ed682c4fdbbde391a81829c0774963705c72','actual_execution_base':'109a6c398d31ea09e1c84fa40a63271c319c8f3f',
        'execution_signature':signature,'original_goal':'供电—液冷—自控耦合、部分可观测和异质专业约束下，决定谁在何时去哪里检查什么；本轮仅改固定所属义务的局部顺序。',
        'protocol':read(STAGE/'protocol.json'),'budget':budget,'safety':safety,
        'aggregates':summary,'all_condition_results':table,
        'development_raw_receipts':dev,'simple_search':s,'sequential_Q_rounds':q,
        'model_calls_including_prompts_and_failures':model,
        'frozen_selection':frozen,'confirmation':confirmation,
        'real_public_evidence_to_outcome_timeline':timeline,
        'prior_diagnostic_branch':'Closed; 45 evaluations/2 malformed model proposals and untested model benefit remain unchanged.',
        'interpretation':{
            'safety':'独立安全核及实际复访、账本审计支持当前固定模型中的可行性；不是现场保证。',
            'human_baselines':'T/D/R及S为人工方法；与原Tour的差异不能归为Qwen贡献。',
            'model_task_edits':'Q1/Q2只修改合法排列的评分式；完整分条件成绩与成本见表，选择按预定字典序。',
            'experience':'Q2确实使用Q1真实结果；未做无反馈消融，经验的独立因果增量未测。',
            'meta_improvement':'固定Qwen改进器、CVAE和PPO均未训练；元改进与RSI递归增量未测。'},
        'source_archives':{path.name:read(path) for path in sorted((STAGE/'source').glob('receipt-*.json'))},
        'evidence_inventory':inventory,'historical_NO_GO_changed':False,'F2_or_G1b_started':False}
    report=ROOT/'reports/2026-11-01-局部巡检顺序改进结果.md'
    single=ROOT/'reports/2026-11-01-局部重排单文件汇总.json'
    write(single,result)
    columns=list(dict.fromkeys(k for row in table for k in row))
    with (STAGE/'全条件结果.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows(table)
    def md_table(methods):
        lines=['|方法|平均漏检段|平均等待/s|移动/m|服务/s|完成检查|本轮待完成|未完承诺|最大重访/s|违规|',
            '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
        fields=['mean_missed','mean_wait_event_conditions_s','mean_travel_m','mean_service_s','mean_completed_inspections',
            'mean_current_round_unfinished_obligations','mean_unfinished_committed_tasks','maximum_gap_s','gap_violations']
        for name,value in methods.items():lines.append('|'+name+'|'+'|'.join(number(value[k]) for k in fields)+'|')
        return '\n'.join(lines)
    text=f'''# 公开信息驱动的局部巡检顺序改进：一次有限实验

本轮已实际完成局部重排、三个基线、S两候选和新条件确认。Qwen两轮提案阶段中，{actual_children}个合法子规则进入六条件实评；失败和重复均计费。结论须同时看发现效果和巡检成本，不能把路线改变或合法表达式当作RSI成功。

## 1. 可运行调度器与复现

128机柜、18名执行者、固定专业/所属、1800秒和原重访期限保持。关闭额外检查；每次只排列本轮剩余的前最多3项，执行完承诺段再决策。任务真实完成才移出本轮账本，下一轮重新产生。安全核独立检查局部段、剩余义务和恢复后的完整基础巡回。

采用既有公开风险、读数年龄、期限和路线几何；风险分数不是校准的故障概率。R为`{BASE_EXPRESSION}`。五特征公式、单位、并列规则及复现命令见[原型与复现](../research/2026-11-01-local-reorder/原型与复现.md)。[新旧任务区别](../research/2026-11-01-local-reorder/新旧任务区别.md)限定本轮语义。

## 2. 全部方法、候选和确认结果

开发是已看过的6条件；等待只在4个存在异常的条件取平均，健康条件不记0。漏检按每条件异常段计数。移动、服务、完成和待完成均为每回合全队数；最大重访取六回合最大。完整分条件表包含完整轮次数、截止边界、数值错误和原件SHA。

开发：

{md_table(summary['development'])}

确认：选择冻结后才登记两个未使用种子，采用预定520秒相位、三类既有过程，共6条件。只执行一次，不再改评分式。

{md_table(summary['confirmation'])}

|轮次|表达式|开发决定|
|---|---|---|
'''
    for label,step in [(f'S{v["round"]}',v) for v in s['rounds']]+list(q.items()):
        candidate=step.get('candidate');expr=candidate['policy']['score_expression'] if candidate else '无合法子式'
        text+=f'|{label}|`{expr}`|'+('保留' if step['selection']['accepted'] else '回退父式')+'|\n'
    text+=f'''
冻结S：`{frozen['selected_S'].get('score_expression')}`。冻结Q：`{frozen['selected_Q'].get('score_expression')}`。选择先保证安全/数值合法，再依次最小化平均漏检、异常条件平均等待、平均移动、负完成数；完全持平保留父式。该规则允许代价取舍，分条件退化不得省略。

实际环境评价 **{len(attempts)}/90**，其中当前有效身份{len(current)}、失败/被替代{len(attempts)-len(current)}；真实Qwen **{len(calls)}/4**，神经模型训练 **0**。确认虽有5方法标签，实际策略身份为{confirmation['actual_confirmation_identities']}种；缓存引用不算新独立实验。CPU{number(budget['jobs']['allocated_CPU_core_minutes'])}核分钟、GPU0秒。

六条T均与封存旧Tour逐动作/读数/完成一致；旧成绩没有拼入本轮收益。当前{len(current)}条记录通过实际调度、事件、账本及独立排列证明检查；重访违规0。合成接口测试仅证明接口。回合末待完成义务表示当前周期尚未走完，不能当漏检异常，也不能将其隐去。

[全部条件CSV](../research/2026-11-01-local-reorder/全条件结果.csv) · [完整单文件JSON](2026-11-01-局部重排单文件汇总.json)

## 3. 真实公开证据—排列—检查—结果时间线

'''
    if timeline['observed']:
        t=timeline
        text+=f'''示例来自{t['label']}、{t['case_id']}、执行者{t['agent']}、第{t['round_id']}轮、{number(t['time_s'])}秒。这是事后说明案例，不是额外试验或挑选出的独立验证。

原顺序`{t['original_order']}`；父式在同一公开状态下会选`{t['parent_same_state_order']}`；模型实际承诺`{t['actual_selected_order']}`。完整公开快照、所有候选特征/证明和分数在JSON中。

|任务|当时公开风险|依据/年龄|派发/s|实际完成/s|实际测量报警|
|---|---:|---|---:|---:|---|
'''
        for event in t['actual_inspections']:
            public=event['public_at_decision'];measured=event['actual_measurement']
            text+=f'|{event["task"]}|{number(public["risk"])}|{public["risk_value_source"]} / {number(public["direct_age_s"])}s|{number(event["dispatch_time_s"])}|{number(event["completion_time_s"])}|{measured["alarm"] if measured else "未完成"}|\n'
        text+='\n同刻父式排序是根据真实候选特征进行的记录回放，不是又跑了一条父策略轨迹。异常段真值只用于回合结束后的评价；单个提前检查或报警不能代替整回合净收益。\n'
    else:text+=timeline['reason']+'\n'
    text+='''
## 4. 下一步判断（一页）

安全保证来自独立证明及逐回合审计；T/D/R/S体现人工设计；Q相对R和同预算S的差异才是本轮模型任务修改的观察对象。Q2使用Q1实评，说明经验链执行成功，但未检验“没有反馈”的对照。固定改进器没有改进自身，递归增量尚未测试。

行动空间不再是只有原序：当前真实决策存在合法不同排列。排序目标与代价取舍需要结合上表判断；现有公开信息是否足够，不能仅凭一轮负结果断言。模型是否提出有效修改，应按实际轨迹和任务分数判断，结构合法本身不算有效。

不启动额外窗口、候选、种子、训练、旧F2/G1b或诊断首检支线。下一研究问题须单独预登记，不用这次确认结果反向改式。
'''
    report.write_text(text,encoding='utf8',newline='\n')
    write(STAGE/'交付校验.json',{'passed':True,'record_only_postprocessing':True,'raw_record_count':len(current),
        'table_rows':len(table),'raw_hashes_valid':True,'frozen_development_receipts_valid':True,
        'selected_confirmation_binding_valid':True,'report_path':str(report.relative_to(ROOT)),
        'single_json_sha256':sha(single),'csv_sha256':sha(STAGE/'全条件结果.csv')})
    print(json.dumps({'report':str(report),'raw_records_verified':len(current),'table_rows':len(table),'environment_attempts':len(attempts),'model_calls':len(calls)}))


if __name__=='__main__':main()
