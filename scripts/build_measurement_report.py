"""Four requested deliverables from closed records, no environment/model calls."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path

REMOTE=Path('/share/home/renly/renly-patrol-rsi/runs/20261101-measurement')
SIG='722682d27c29c515433d01762437c34a7257fecf0171c2d20e0a4388cf507018'


def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fmt(v):return '—' if v is None else f'{v:.3f}' if isinstance(v,float) else str(v)


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args()
    root=Path(__file__).resolve().parents[1];stage=root/'research/2026-11-01-measurement-effect';run=a.run.resolve()
    protocol=read(stage/'protocol.json');cases=protocol['cases']
    all_rows=[read(p) for p in sorted((run/'evaluations').glob('episode-*/complete.json'))]
    rows=[r for r in all_rows if r['execution_signature']==SIG]
    assert len(rows)==42 and len({(r['case_id'],r['arm']) for r in rows})==42
    assert all(r['audit']['passed'] and not r['metrics']['tasks_violating_exact_gap'] for r in all_rows)
    by={(r['case_id'],r['arm']):r for r in rows}
    def record(r):
        path=run/Path(r['record_path']).relative_to(REMOTE)
        assert sha(path)==r['record_sha256']
        return json.loads(gzip.decompress(path.read_bytes()))
    annotations=read(run/'policy-input-annotations.json')
    annotated={v['case_id']:v for v in annotations['cases']}
    table=[];facts=[];outcomes=[];timeline=None
    primary=('missed_segments','consequence_weighted_censored_delay_s','travel_m','service_s','selected_detours','tasks_violating_exact_gap')
    for case in cases:
        cid=case['case_id'];b=record(by[cid,'B']);c=record(by[cid,'C']);fixed=record(by[cid,'A'])
        assert b['action_log']==c['action_log']
        assert b['assignments']==c['assignments'] and b['inspection_events']==c['inspection_events']
        assert b['policy_state_final_SHA256']==c['policy_state_final_SHA256']
        assert all(b['metrics'][k]==c['metrics'][k] for k in primary)
        assert annotated[cid]['first_context_hashes_match_actual'] and annotated[cid]['final_state_hashes_match_actual']
        context=c['first_post_measurement_context'];first=c['first_request']['task'] if c['first_request'] else None
        stats={'case_id':cid,'group':case['group'],'first_triggered':context is not None,
            'candidate_estimate_changed_ids':set(),'value_changed_ids':set(),'max_value_delta':0.,
            'rank_order_changed_roots':0,'input_changed_calls':len(annotated[cid]['input_differences']),
            'output_changed_calls':sum(v['output_changed'] for v in annotated[cid]['input_differences']),
            'actual_action_changed':b['action_sha256']!=c['action_sha256']}
        selected_contexts=[];first_changed=None
        for index,comparison in enumerate(c['candidate_comparisons']):
            before={r['task']:r for r in comparison['masked']};after=comparison['visible']
            changed=[]
            for row in after:
                old=before[row['task']]
                if row['task']==first:continue
                delta=abs(row['value']-old['value']);stats['max_value_delta']=max(stats['max_value_delta'],delta)
                if delta>1e-9:stats['value_changed_ids'].add(row['task'])
                if row['current_estimate'] is not None and old['current_estimate'] is not None and (abs(row['current_estimate']-old['current_estimate'])>1e-9 or abs(row['estimate_at_finish']-old['estimate_at_finish'])>1e-9):
                    stats['candidate_estimate_changed_ids'].add(row['task']);changed.append(row['task'])
            order_b=[r['task'] for r in comparison['masked'] if r['task']!=first]
            order_c=[r['task'] for r in after if r['task']!=first]
            stats['rank_order_changed_roots']+=order_b!=order_c
            if index==0:selected_contexts.append(comparison)
            if changed and first_changed is None:
                first_changed=comparison
                if index!=0:selected_contexts.append(comparison)
        if context:
            event=context['first_actual_event'];info=c['optional_chain'][0]['information']
            update=next(v for v in context['visible_state']['latest_update']['visible_references'] if v['event_id']==[event['agent'],event['task'],event['time_s']])
            stats.update(first_time_s=event['time_s'],first_alarm=event['alarm'],first_task=first,
                first_measurement=event['measurement'],first_prior=update,
                simultaneous_remote_same_quantity=info['contemporaneous_remote_same_quantity'],
                first_predicted_professional_signal=c['first_request']['own_signal'])
            for comparison in selected_contexts:
                before={r['task']:r for r in comparison['masked']}
                for row in comparison['visible']:
                    old=before[row['task']]
                    table.append({'case_id':cid,'group':case['group'],'measurement_time_s':event['time_s'],
                        'first_dispatch_time_s':c['optional_chain'][0]['dispatch_time_s'],
                        'first_dispatch_estimate':c['first_request']['current_estimate'],
                        'first_measured_value':update['value'],'first_measurement_source':update['source'],
                        'first_prior_at_measurement_time_nominal':update['prior_same_time_nominal'],
                        'first_prior_at_measurement_time_estimate':update['prior_same_time_estimate'],
                        'first_physical_residual':update['residual'],'first_estimate_innovation':update['innovation'],
                        'decision_time_s':comparison['time_s'],'task':row['task'],'kind':row['kind'],'pod':row['pod'],
                        'candidate_finish_s':row['finish_s'],'lead_s':row['lead_s'],'shift_s':row['shift_s'],
                        'comparison':'Same current state: masked versus visible; not different-time readings',
                        'current_estimate_masked':old['current_estimate'],'current_estimate_visible':row['current_estimate'],
                        'finish_estimate_masked':old['estimate_at_finish'],'finish_estimate_visible':row['estimate_at_finish'],
                        'signal_masked':old['corrected_signal'],'signal_visible':row['corrected_signal'],
                        'value_masked':old['value'],'value_visible':row['value'],'rank_masked':old['rank'],'rank_visible':row['rank'],
                        'public_weight':row['weight'],
                        'value_benefit_masked':old['value_benefit'],'value_benefit_visible':row['value_benefit'],
                        'value_cost_masked':old['value_cost'],'value_cost_visible':row['value_cost'],
                        'hard_safe_candidate':True,
                        'feasibility_source':'Original current options/ReturnPlan mask; actual dispatch rechecked',
                        'workflow_eligible_masked':row['task']!=first and not old['already_alarm'] and old['value']>0,
                        'workflow_eligible_visible':row['task']!=first and not row['already_alarm'] and row['value']>0,
                        'source_visible':row['estimate_source'],'source_cutoff_s':row['input_cutoff_s'],
                        'direct_time_masked_s':old['direct_time_s'],'direct_time_visible_s':row['direct_time_s'],
                        'last_CVAE_input_time_s':max((t for t in c['tool_calls']['policy_visible_times'] if t<=comparison['time_s']),default=None),
                        'dependency':json.dumps(row['dependency'],ensure_ascii=False),
                        'workflow_excludes_first_target':row['task']==first,
                        'actual_parent_C_selection':str(comparison['selected_pair'])})
        for key in ('candidate_estimate_changed_ids','value_changed_ids'):stats[key]=sorted(stats[key])
        facts.append(stats)
        for arm in ('A','B','C','R'):
            value=by.get((cid,arm))
            if value is not None:
                outcomes.append({'case_id':cid,'group':case['group'],'seed':case['specification']['seed'],
                    'scenario':case['specification']['scenario'],'arm':arm,'status':'actual_completed',
                    **{k:value['metrics'][k] for k in primary},'action_sha256':value['action_sha256'],'record_sha256':value['record_sha256']})
        outcomes.append({'case_id':cid,'group':case['group'],'seed':case['specification']['seed'],
            'scenario':case['specification']['scenario'],'arm':'model_child','status':'not_executed_no_legal_proposal',
            **{k:None for k in primary},'action_sha256':None,'record_sha256':None})
        if timeline is None and context and c['metrics']['anomaly_segments']:
            timeline={'case_id':cid,'selection_rule':'First case in protocol order with a first reference and anomaly segments; not selected for score gain',
                'first_measurement':stats,'same_time_pair_context':context,'selected_comparison_windows':selected_contexts,
                'actual_decisions':c['measurement_decisions'],'all_359_action_frames':c['action_log'],
                'all_assignments':c['assignments'],'all_real_qualified_measurements':c['inspection_events'],
                'optional_chain':c['optional_chain'],'full_return_safety':c['dispatch_safety'],
                'task_results':{arm:by[cid,arm]['metrics'] for arm in ('A','B','C')},
                'instrumentation_annotation':annotated[cid],
                'source_C_record':by[cid,'C'],'source_B_record':by[cid,'B']}
    # R is the preserved positive-first flow: verify against prior released metadata.
    prior=read(root/'research/2026-11-01-multistep-workflow/evidence/baselines-complete.json')['rows']
    for i in range(6):
        old=next(v for v in prior if v['case_id']==f'dev-{i:02d}' and v['arm']=='D')
        assert by[f'old-{i:02d}','R']['action_sha256']==old['action_sha256']
    attempts=[]
    for path in run.glob('model*/call-*/start.json'):
        parent=path.parent
        attempts.append({'start':read(path),'response':read(parent/'response.json') if (parent/'response.json').exists() else None,
            'failure':read(parent/'failed.json') if (parent/'failed.json').exists() else None})
    attempts.sort(key=lambda v:v['start']['receipt']['number'])
    assert len(attempts)==2 and all(v['failure'] is not None for v in attempts)
    assert not (run/'child-workflow.json').exists()
    with (run/'accounting.psv').open() as stream:accounting=list(csv.DictReader(stream,delimiter='|'))
    costs={'actual_environment_attempts':len((run/'environment-attempts.jsonl').read_text().splitlines()),
        'main_completed_ABC':36,'reference_completed_R':6,'superseded_pilot_completed':3,
        'real_model_calls':len((run/'model-calls.jsonl').read_text().splitlines()),'legal_model_children':0,
        'model_child_evaluations':0,'new_physical_processes':len(list((run/'processes').glob('*/complete.json'))),
        'CPU_allocated_core_minutes':sum(int(v['ElapsedRaw'])*int(v['AllocCPUS']) for v in accounting)/60,
        'GPU_allocation_seconds':0,'new_training_runs':0,'Slurm':accounting}
    assert costs['actual_environment_attempts']==45<=60 and costs['real_model_calls']==2 and costs['new_physical_processes']==6
    assert costs['CPU_allocated_core_minutes']<=protocol['limits']['CPU_allocated_core_minutes']
    def csv_file(path,values):
        with path.open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(values[0]));writer.writeheader();writer.writerows(values)
    csv_file(stage/'候选状态与排序.csv',table);csv_file(stage/'全条件结果.csv',outcomes)
    (stage/'真实行动时间线.json').write_text(json.dumps(timeline,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8',newline='\n')
    changed_est=sum(bool(v['candidate_estimate_changed_ids']) for v in facts)
    changed_value=sum(bool(v['value_changed_ids']) for v in facts)
    changed_action=sum(v['actual_action_changed'] for v in facts)
    first=timeline['first_measurement'];event=timeline['same_time_pair_context']['first_actual_event']
    illustrative=next((v for v in table if v['case_id']==timeline['case_id'] and v['task']!=first['first_task'] and v['finish_estimate_masked'] is not None and abs(v['finish_estimate_visible']-v['finish_estimate_masked'])>1e-9),None)
    report=['# 首次测量的独立作用：实际机制实验结果','',
        '已完成十二个开发条件的同刻A/B/C比较，保留旧阳性首检参考。新增测量进入了状态估计，也改变了其他候选的温度预测；本批候选任务价值和实际行动均未改变。模型两次输出被结构校验拒绝，未生成或执行子工作流。','',
        '## 1. 更新前后候选状态与排序','',
        '“前/后”是同一当前状态下屏蔽/使用首测的对照，不是两个不同时刻的读数。温度预测可能改变，任务价值仍可保持不变。完整表列出每个条件的首次后续决策，以及首次出现其他候选估计变化的窗口；全部后续候选记录保存在原件包。', '',
        '[候选状态与排序CSV](../research/2026-11-01-measurement-effect/候选状态与排序.csv)','']
    if illustrative:
        report += ['|真实例子|屏蔽首测B|使用首测C|','|---|---:|---:|',
            f"|{illustrative['decision_time_s']:.0f}秒，任务{illustrative['task']}完成时温度预测|{illustrative['finish_estimate_masked']:.6f}℃|{illustrative['finish_estimate_visible']:.6f}℃|",
            f"|任务价值|{illustrative['value_masked']:.6f}|{illustrative['value_visible']:.6f}|",
            f"|排名|{illustrative['rank_masked']}|{illustrative['rank_visible']}|",'',
            '该例两种预测都在实验65℃参考阈值以下，风险分量仍为0，机会成本不变，所以任务价值与选择没有变化。价值为未校准调度分数，不是故障概率。','']
    report += ['## 2. 真实测量—判断—派单—结果时间线','',
        f"示例按固定条件顺序选{timeline['case_id']}，不按收益挑选。首次诊断在{first['first_time_s']:.0f}秒完成，机柜{first['first_task']}实测{first['first_prior']['value']:.2f}℃，结果正常，当前同量遥测不可用。同刻融合先验为{first['first_prior']['prior_same_time_estimate']:.2f}℃，名义先验为{first['first_prior']['prior_same_time_nominal']:.2f}℃。实际检查、工时与评价器确认在B/C均完整保留。",'',
        f"新增数据随后进入固定30秒CVAE帧；成功回放验证{first['input_changed_calls']}个推断时刻的输入不同，输出也不同。回放的首个对照状态和最终策略状态均匹配实际记录哈希；它只补充输入来历，不是新增环境评价或收益试验。",'']
    report += ['具体通路是：机柜26的新测温更新该pod的已测均温特征，240秒定时帧进入冻结CVAE，随后同支路候选29的预测出现上表的小幅变化。该通路复用原观测特征，未把一台机柜的温度残差直接复制给其他设备，也未把同pod解释为故障确认。','']
    for item in timeline['optional_chain']:
        e=item['completed'];key={'thermal':'temperature_c','cooling':'pod_flow_kg_s','electrical':'contact_temperature_c','control':'controller_sensor_error_c'}[e['kind']]
        unit='kg/s' if e['kind']=='cooling' else '℃'
        report.append(f"- {item['dispatch_time_s']:.0f}秒派单，{e['time_s']:.0f}秒完成{e['task_id']}，实测{e['measurement'][key]:.2f}{unit}，{'告警' if e['alarm'] else '正常'}。")
    report += ['', 'C/B随后完整359个决策时刻的动作、真实任务完成与主要指标相同。完整公开对照状态、任务、测量和安全证书见[真实时间线JSON](../research/2026-11-01-measurement-effect/真实行动时间线.json)。','',
        '## 3. 所有条件及模型结果','',
        '每格为“漏检段数/后果加权删失等待秒/额外检查数”。—表示没有异常、等待不适用。A冻结后续偏好；B同刻重规划但屏蔽首测；C同刻重规划并使用首测。主要解释C−B。R仅为旧六条件的原阳性首检参考，不参与这一因果对比。','',
        '|条件|过程|A固定|B屏蔽|C使用|R旧流程|模型子流程|','|---|---|---|---|---|---|---|']
    for case in cases:
        cid=case['case_id'];cells=[]
        for arm in ('A','B','C','R'):
            row=by.get((cid,arm))
            if row:
                m=row['metrics'];cells.append(f"{m['missed_segments']}/{fmt(m['consequence_weighted_censored_delay_s'])}/{m['selected_detours']}")
            else:cells.append('未安排')
        family={'healthy':'健康','coldplate_fouling':'冷板','aux_feeder_loss+cdu_fouling':'供电—液冷耦合'}[case['specification']['scenario']]
        report.append('|'+cid+'|'+family+'|'+'|'.join(cells)+'|未执行：无合法提案|')
    report += ['', 'old为已看过六条件，new为一次预登记的新开发六条件；总共四个种子组。相同种子的三类过程在故障前共享前缀，不能把十二次正常首测当作十二个独立现场样本。移动、服务、重访及原件哈希见[全条件CSV](../research/2026-11-01-measurement-effect/全条件结果.csv)。', '',
        '辅助对比B−A：old-02等待减少约16.46秒，new-02少漏1段且等待减少约11.21秒；new-05等待反而增加约9.56秒。这些是利用更新中的公开信息进行重规划的混合效果，不是首测信息收益；C−B仍全部相同。','',
        '模型使用同一Qwen3-8B、CPU float32/greedy和原紧凑编译器，两次真实调用都把changes输出成字段名列表，缺少字段到新取值的绑定，均被拒绝。提示把changes写成文字说明、没有给出键值对象示例，契约表达不够明确。后续默认提示已静态修正；未追加调用、未从解释文字拼装子流程。模型改进收益未被测试，不能写成“子流程无收益”。','',
        '## 4. 一页结论：问题发生在哪一层','',
        '|层次|实际证据|结论|','|---|---|---|',
        '|数据写入|12次真实首测均完整记录；B只屏蔽策略暴露，实际确认、工时和安全未删除|成功|',
        '|估计使用|12/12条件CVAE输入/输出变化；其他安全候选估计亦有变化|成功贯通，非仅记日志|',
        f'|候选价值/排序|{changed_est}/12条件有其他候选温度变化；{changed_value}/12条件任务价值变化|估计变化未转成价值变化|',
        f'|实际行动|C−B有{changed_action}/12条轨迹变化|本批未改变|',
        '|同预算结果|C与B漏检、等待、移动与服务均相同，重访超期均0|本批无新增任务收益|','',
        '覆盖情况：诊断首检未触发0；同刻同量遥测重复0；正常首测12；阳性首测0；状态变化但行动相同12。正常测量纠正已有高风险预测、阳性首测、C−B行动分叉与变差均未自然观察到，合成接口测试不能补成实测收益。', '',
        '瓶颈是信息的决策相关性。本批首检发生在210/220秒，结果正常；数据确实进入估计器，但传播到其他候选的修正没有改变任务效用。不是再次补估计刷新接口或把检查额度加到3。模型环节另有结构提案失败，未测到子流程效果。', '',
        '**建议停止将当前诊断首检的信息获取支线作为主要创新，不追加额度、换种子或调阈值追求分叉。后续主线保留为利用已有公开信息改进动态调度与经验驱动流程。** 这是本方法、本批数据的资源取舍；阳性首检等自然情形覆盖不足，不能证明所有额外测量普遍无价值。', '',
        f"本轮{costs['actual_environment_attempts']}/60条真实环境尝试（36条A/B/C、6条R、3条旧核试运行），2/2次真实模型调用，合法子流程0、子流程评价0；新物理过程6，模型训练0，GPU0秒，CPU分配{costs['CPU_allocated_core_minutes']:.3f}核分钟。", '',
        '作业状态与研究结果分别记录：一次pilot收据同名写入失败后由原六条件完整配对复核恢复；模型加载准备在真实调用前中止一次；一次输入回放因JSON键序列化比较中止后修正。所有原件、失败和CPU费用保留。旧代码快照、NO-GO及最终集未改动或重开。']
    report += ['', '[执行版本、来源与复现命令](../research/2026-11-01-measurement-effect/复现与版本说明.md)。']
    text='\n'.join(report)+'\n'
    report_path=root/'reports/2026-11-01-测量作用机制实验结果.md';report_path.write_text(text,encoding='utf8',newline='\n')
    summary={'experiment':'measurement-effect-v1','report_markdown':text,'protocol':protocol,'costs':costs,
        'report_generator_sha256':sha(Path(__file__)),
        'reproduction_and_versions_markdown':(stage/'复现与版本说明.md').read_text(encoding='utf8'),
        'interface_gate':read(run/'gate'/SIG/'complete.json'),
        'case_facts':facts,'candidate_table':table,'all_condition_outcomes':outcomes,'actual_rows':rows,
        'complete_selected_timeline':timeline,'policy_input_annotations':annotations,'actual_model_attempts':attempts,
        'model_loop':{'calls':2,'legal_children':0,'child_execution':'not_applicable_no_legal_proposal_after_frozen_two_call_fail_stop',
            'model_skill_improvement_tested':False,'future_prompt_fixed_but_not_real_model_validated':True},
        'execution_signature':SIG,'full_raw_archive_sha256':'f69002af9c0a13c5564bd1b33fb83e59dcea8417fd3bdb941556ffdf8073f7a3',
        'no_old_final_opened':True,'new_training':0,'new_language_calls_beyond_budget':0}
    (root/'reports/2026-11-01-测量作用单文件汇总.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'cases':len(facts),'table_rows':len(table),'estimate_changed_cases':changed_est,
        'value_changed_cases':changed_value,'action_changed_cases':changed_action,'costs':costs},ensure_ascii=False))


if __name__=='__main__':main()
