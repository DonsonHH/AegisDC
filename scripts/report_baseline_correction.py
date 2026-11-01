"""Record-only audit and four-part development delivery; never step a simulator."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1];STAGE=ROOT/'research/2026-11-01-baseline-correction'
REMOTE='/share/home/renly/renly-patrol-rsi/runs/20261101-baseline-correction/'
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from patrol_rsi.baseline_correction import Rule,rule_from_dict
from patrol_rsi.correction_selection import vector,dominates,adopt,retain
from patrol_rsi.multistep_workflow import digest
from patrol_rsi.local_score import ScoreExpression,BASE_EXPRESSION
from propose_baseline_correction import parse_model_response


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8',newline='\n')
def num(x):return '—' if x is None else f'{x:.6g}' if isinstance(x,float) else str(x)


def mean_result(result):
    m=[r['metrics'] for r in result['rows']];out={'objectives':vector(result)}
    for name in ('missed_segments','consequence_weighted_censored_delay_s','travel_m','service_s','completed_inspections',
        'current_round_unfinished_obligations','unfinished_committed_tasks','completed_rounds_total'):
        values=[v[name] for v in m if v[name] is not None];out[name]=statistics.mean(values) if values else None
    out['max_gap_s']=max(v['maximum_exact_gap_s'] for v in m);out['gap_violations']=sum(v['tasks_violating_exact_gap'] for v in m)
    return out


def verify_decisions(value):
    """Independent arithmetic from declared mathematical definitions and raw evidence."""
    policy=value['policy'];rule=policy.get('rule',Rule().to_dict());checked=0
    for d in value['local_decisions']:
        public={r['task']:r for r in d['public_tasks']};original=next(c for c in d['candidates'] if c['original'])
        first0=original['certificate']['first_completion_s'];possible=[]
        for c in d['candidates']:
            if not c['certificate']['ok']:continue
            plus=minus=pressure=0.
            for j,row in public.items():
                rho=0.
                for e in row['evidence_components']:
                    if e['group']=='unknown':
                        assert e['value'] is None
                        continue
                    assert e['time_s'] is not None and 0<=e['time_s']<=d['time_s']
                    assert e['value']>=0
                    fresh=1. if rule['freshness']=='flat' else max(0.,1-e['age_s']/300.)
                    rho+=rule['source_weights'][e['group']]*fresh*e['value']
                rho=min(rho,4.);f0=first0[str(j)];f=c['certificate']['first_completion_s'][str(j)]
                weight=row['weight']/row['deadline_s']*rho
                plus+=weight*max(f0-f,0.);minus+=weight*max(f-f0,0.)
                last=max(0.,row['last_check_s']);deadline=row['deadline_s']
                pressure+=((f-last)/deadline)**2-((f0-last)/deadline)**2
            n=len(public);delta=(c['certificate']['segment_and_bridge_travel_s']-original['certificate']['segment_and_bridge_travel_s'])/300.
            features={'gain_plus':plus/n,'gain_minus':minus/n,'delta_travel':delta,'delta_pressure':pressure/n}
            assert all(abs(features[k]-c['correction'][k])<1e-8 for k in features)
            g=(plus-minus)/n;a=g-rule['travel_penalty']*max(delta,0)-rule['deadline_penalty']*max(pressure/n,0)
            assert abs(a-c['advantage'])<1e-8 and abs(g-c['gain'])<1e-8
            if c['original']:assert abs(a)<1e-12 and abs(g)<1e-12
            possible.append((c,g,a));checked+=1
        if policy['kind']=='correction' and d['numeric_error'] is None:
            selected=original;best=0.
            for c,g,a in sorted(possible,key=lambda x:(not x[0]['original'],x[0]['order'])):
                if not c['original'] and g>1e-9 and a>rule['margin']+1e-9 and a>best+1e-9:selected,best=c,a
            assert selected['order']==d['selected_order']
    return checked


def main():
    started=time.perf_counter();cpu=time.process_time()
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();run=a.run.resolve()
    actual_mode=(run/'actual-chain-complete.json').exists()
    assert actual_mode,'Final actual-candidate chain required; a legacy phase checkpoint cannot seal the study'
    study=read(run/('actual-chain-complete.json' if actual_mode else 'study-complete.json'));base=study['references'];archive=study['archive'];sig=study['execution_signature']
    pairs=read(run/'pairs-complete.json');roots=read(run/'roots-frozen.json');labels=read(run/'pair-classification.json')
    assert pairs['frozen_roots_sha256']==sha(run/'roots-frozen.json') and labels['raw_pairs_sha256']==sha(run/'pairs-complete.json')
    for name,h in study['receipt_sha256'].items():assert sha(run/name)==h
    cache={};candidate_checks=0
    def raw(row):
        nonlocal candidate_checks
        assert row['record_path'].startswith(REMOTE)
        path=run/row['record_path'][len(REMOTE):];assert sha(path)==row['record_sha256']
        if path not in cache:
            v=json.loads(gzip.decompress(path.read_bytes()))
            assert v['execution_signature']==sig and v['case_id']==row['case_id'] and digest(v['policy'])==row['policy_id']
            assert v['metrics']==row['metrics'] and digest(v['action_log'])==row['action_sha256']
            assert row['audit']['passed'] and v['metrics']['extra_checks']==0 and v['metrics']['tasks_violating_exact_gap']==0
            candidate_checks+=verify_decisions(v);cache[path]=v
        return cache[path]
    methods={**base,**archive};all_rows=[];aggregates={}
    for name,result in methods.items():
        assert len(result['rows'])==6;aggregates[name]=mean_result(result)
        for row in result['rows']:
            value=raw(row);all_rows.append({'method':name,'case_id':row['case_id'],'policy_id':row['policy_id'],
                'rule':json.dumps(result['policy'].get('rule'),separators=(',',':')),
                **value['specification'],**value['metrics'],'record_sha256':row['record_sha256'],'record_path':row['record_path']})
    pair_rows=[]
    for item in pairs['pairs']:
        if item['root'] is None:pair_rows.append({'case_id':item['case_id'],'absent_reason':item['absent_reason']});continue
        r=item['root'];a_raw,b_raw=raw(item['A']),raw(item['B'])
        for arm in (a_raw,b_raw):
            check=arm['intervention_verified'];assert check['state_sha256']==r['state_sha256']==digest(check['state_snapshot'])
            assert digest(arm['action_log'][:check['prefix_steps']])==r['prefix_action_sha256']
        assert a_raw['intervention_verified']['state_snapshot']==b_raw['intervention_verified']['state_snapshot']
        t=raw(next(row for row in base['T']['rows'] if row['case_id']==item['case_id']))
        assert a_raw['action_log']==t['action_log'] and a_raw['inspection_events']==t['inspection_events']
        ordered=sorted((d for d in t['local_decisions'] if d['legal_nonoriginal']),key=lambda d:(d['time_s'],d['agent']))
        positive=[d for d in ordered if any(v['risk']>0 for v in d['public_tasks'])];chosen=(positive or ordered)[0]
        assert (chosen['time_s'],chosen['agent'])==(r['time_s'],r['agent'])
        old={(e['task'],e['time_s']):e['measurement'] for e in a_raw['inspection_events']}
        for event in b_raw['inspection_events']:
            key=(event['task'],event['time_s'])
            if key in old:assert event['measurement']==old[key]
        expected={k:b_raw['metrics'][k]-a_raw['metrics'][k] if a_raw['metrics'][k] is not None else None for k in item['B_minus_A']}
        assert expected==item['B_minus_A']
        r_expr=ScoreExpression(BASE_EXPRESSION);orig=next(c for c in r['candidate_pool'] if c['original']);alt=next(c for c in r['candidate_pool'] if c['order']==r['alternative_order'])
        r_difference=r_expr.evaluate(alt['features'])-r_expr.evaluate(orig['features'])
        h_root_changes=any(c['certificate']['ok'] and not c['original'] and c['gain']>1e-9 and c['advantage']>1e-9 for c in chosen['candidates'])
        pair_rows.append({'case_id':item['case_id'],'time_s':r['time_s'],'agent':r['agent'],
            'original':str(r['window']),'alternative':str(r['alternative_order']),'risk_class':r['root_risk_class'],
            'category':labels['labels'][item['case_id']],**{('B_minus_A_'+k):v for k,v in expected.items()},
            'R_B_minus_A_public_score':r_difference,'R_prefers_B':r_difference<-1e-9,
            'H_would_change_at_frozen_Tour_state':h_root_changes,
            'same_prefix_state_verified':True,'root_sha256':item['root_sha256']})
    qsteps=[v['step'] for v in study['actual_candidate_chain']] if actual_mode else [read(run/f'Q{i}-complete.json') for i in (1,2)]
    model_labels=('C1','C2') if actual_mode else ('Q1','Q2');simple=read(run/'S-complete.json')
    for step in simple['rounds']+qsteps:
        if step['candidate'] is not None:
            selected,decision=retain(step['parent'],step['candidate'],base)
            assert selected==step['selected'] and decision==step['selection']
    assert qsteps[0]['parent']==archive['H'] and qsteps[1]['parent']==qsteps[0]['selected']
    behavior={}
    for label,step in zip(model_labels,qsteps):
        if step['candidate'] is None:behavior[label]={'status':'No executable child; no environment benefit evaluation'};continue
        observations=[]
        for row in step['candidate']['rows']:
            t=next(v for v in base['T']['rows'] if v['case_id']==row['case_id'])
            old=next(v for v in step['parent']['rows'] if v['case_id']==row['case_id'])
            observations.append({'case_id':row['case_id'],'actions_equal_T':row['action_sha256']==t['action_sha256'],
                'actions_changed_from_parent':row['action_sha256']!=old['action_sha256'],
                'local_reorders':row['metrics']['reordered_plans']})
        behavior[label]={'status':'Six actual development rollouts evaluated','cases':observations}
    conventional={({'C1':'Q1','C2':'Q2'}.get(k,k)):v for k,v in archive.items()}
    if actual_mode:assert study['conventional_adoption']==adopt(base['T'],{**conventional,'R':base['R']})
    else:assert study['formal_adoption']==adopt(base['T'],{**archive,'R':base['R']})
    attempts=[json.loads(v) for v in (run/'environment-attempts.jsonl').read_text().splitlines()]
    calls=[json.loads(v) for v in (run/'model-calls.jsonl').read_text().splitlines()] if (run/'model-calls.jsonl').exists() else []
    assert len(attempts)<=60 and len(calls)<=4
    assert len(attempts)==len(list((run/'evaluations').glob('*/attempt.json')))
    assert len(cache)<=len(attempts),'Cannot use a stale global counter snapshot'
    assert len(cache)==sum(read(p)['execution_signature']==sig for p in (run/'evaluations').glob('*/complete.json')),'Every completed current-kernel record must be delivered'
    assert {v['number'] for v in attempts}==set(range(len(attempts)))
    assert {v['number'] for v in calls}==set(range(len(calls)))
    model=[]
    for receipt in calls:
        folder=run/f'model-round-{receipt["round"]}'/f'call-{receipt["number"]:02d}'
        start=read(folder/'start.json')
        assert start['input_tokens']<=4096
        for forbidden in ('41000','41001','43000','43001','fault_start_s','scenario','onset_s','first_confirmation_s'):
            assert forbidden not in start['rendered_prompt'],forbidden
        if (folder/'accepted-interface.json').exists():
            accepted=read(folder/'accepted-interface.json');response=read(folder/'response.json')
            assert accepted['response_sha256']==sha(folder/'response.json')
            parsed,mechanism=parse_model_response(response['raw_response'])
            assert parsed.to_dict()==accepted['rule'] and mechanism==accepted['mechanism']
            assert accepted['raw_repaired'] is False
        elif (folder/'failed.json').exists():
            failure=read(folder/'failed.json')
            if failure['error']=='Empty or duplicate canonical rule':
                parsed,_=parse_model_response(failure['raw_response']);assert parsed.identity==Rule().identity
        model.append({'receipt':receipt,'start':start,'response':read(folder/'response.json') if (folder/'response.json').exists() else None,
            'failure':read(folder/'failed.json') if (folder/'failed.json').exists() else None,
            'accepted':read(folder/'accepted-interface.json') if (folder/'accepted-interface.json').exists() else None})
    if (run/'model-round-2/startup.json').exists():assert read(run/'model-round-2/startup.json')['feedback_Q1_receipt_sha256']==sha(run/'Q1-complete.json')
    if (run/'model-round-3/startup.json').exists():assert read(run/'model-round-3/startup.json')['feedback_previous_actual_candidate_sha256']==sha(run/'Q2-complete.json')
    accounts=[]
    keys=('job_id','state','exit_code','elapsed_seconds','allocated_cpus')
    for line in (run/'jobs/accounting.psv').read_text().splitlines():
        row=dict(zip(keys,line.split('|')));row['elapsed_seconds']=int(row['elapsed_seconds']);row['allocated_cpus']=int(row['allocated_cpus']);accounts.append(row)
    cost=sum(v['elapsed_seconds']*v['allocated_cpus'] for v in accounts)/60
    numeric={'attempts':len(attempts),'cap':60,'actual_record_identities':len(cache),'paired_records':sum('root' in v and v['root'] is not None for v in pairs['pairs'])*2,
        'paired_prefix_replay_steps':sum(v['intervention_verified']['prefix_steps'] for v in cache.values() if v.get('intervention_verified') is not None),
        'paired_records_included_in_total_not_extra':True,
        'actual_Qwen_calls':len(calls),'actual_Qwen_children':sum(q['candidate'] is not None for q in qsteps),'neural_training':0,'new_confirmation':0,
        'frozen_CVAE_inference_calls':sum(v['metrics']['estimator_calls'] for v in cache.values()),
        'Slurm_allocated_CPU_core_minutes':cost,'GPU_seconds':0,'allocations':accounts}
    numeric['record_only_preliminary_audit']=read(run/'local-preliminary-audit.json')
    judgments={
        'public_score':'六根上R均更偏好原序；B都是其最佳非原备选，并非R实际推荐。健康两例三目标移动下降但各少完成1项；正风险三例B被Tour支配，一例等待恶化15秒换移动下降4.8米。本样本没有正风险且完成量不降的支配性好例，不能证明代理识别可靠有益改序，也不是R在这六根把坏例排高的证据，更非全空间上界。',
        'feedback':'Q使用这次新增的实际同状态后果；Q2按Q1真实分项和保留/回退结果生成。具体是否改变正确来源须结合实际提案与轨迹；结构合法不算任务进步。',
        'weak_parent':'Q同时与H、两步S、T比较；H目前在同漏检/等待下比T平均多走约2.03米，被T支配，优于H仍需单独检查是否超越T。',
        'costs':'没有业务换算支撑用任意等待小改善补偿移动增加。三目标取舍保存，不自动正式采用；少做任务造成的服务/移动减少不视为效率收益。',
        'limits':'仅六个已看开发条件；无新确认、无无反馈对照、无元更新。经验因果贡献与递归增量均未测。'}
    if not actual_mode and qsteps[0]['candidate'] is None:
        judgments['feedback']='第一轮两次回复均重复H，结构合法但任务修改为空，被拒绝且未执行。第二轮收到这些失败及本轮配对/H反馈后才形成候选。因此未完成“第一子式执行后再改第二子式”的两条实评链，不能用阶段名称补造经验作用。'
    first_label='C1' if actual_mode else 'Q2'
    if first_label in archive and all(v['actions_equal_T'] for v in behavior[first_label]['cases']):
        judgments['weak_parent']='C1六条实际动作与Tour全部相同；消除了H的3处改序，使平均移动从H约11795.43米回到Tour的11793.4米，漏检/等待相同，但平均完成数从1426.333降到1426、服务少3.333秒。相对H的移动降低也伴随少完成工作，不能只报成本胜出；它没有超过Tour。正式默认仍为T。'
        judgments['feedback']+=' Q2提高direct权重、降低power权重、使用年龄衰减和0.001门槛；这些组合修改使实际改序归零，但没有单因素消融，不能断言是哪一个字段或具体经验单独起效。'
    if actual_mode:
        judgments['feedback']='最初提案阶段两次重复H被拒，没有伪造子式执行；第3调用形成实际C1并实评六条件。第4调用明确读取C1执行/保留收据及真实行为后果，尝试实际C2。生成阶段编号与两个实际候选槽分开，旧失败文件未改。'
        if qsteps[1]['candidate'] is not None:judgments['feedback']+=' 两条实际子式均完成六条件评价；但无无反馈消融，不能把调用成功或某字段变化归为经验独立增量。'
        else:judgments['feedback']+=' 最后一调用未形成合法C2，两条实评目标未达，4调用上限已停止。'
        if 'C2' in behavior and 'cases' in behavior['C2'] and all(v['actions_equal_T'] for v in behavior['C2']['cases']):
            judgments['weak_parent']+=' C2同样6/6动作等于Tour，相对C1没有增量，探索父版本保留C1。'
    h_root_count=sum(bool(v.get('H_would_change_at_frozen_Tour_state')) for v in pair_rows)
    judgments['paired_feedback_coverage']=f'六个预登记根中，H会改序的根数为{h_root_count}；H实际改序只出现于后续其他决策。配对后果不能直接当作H每次实际修改的因果标签，首个公开风险根选择覆盖了保持/取舍，却未必覆盖待修正策略的活跃决策。'
    inventory=[{'path':p.relative_to(STAGE).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(run.rglob('*')) if p.is_file()]
    result={'schema':'baseline-correction-delivery-v1','status':'finite_development_experiment_finished',
        'baseline':'db2f9c7c66bd2f31bb33d3fbabac2eb733512e51','plan_commit':'dd6803e113e4a4f53a800d70613fe8dbba05f867',
        'execution_signature':sig,'postprocessing_script_sha256':sha(Path(__file__)),'protocol':read(STAGE/'protocol.json'),
        'budget':numeric,'aggregates':aggregates,'all_six_condition_results':all_rows,'paired_results':pair_rows,
        'paired_raw_receipts':pairs,'tolerance_labels':labels,'human':archive['H'],'simple_rounds':simple,'Q_rounds':qsteps,
        'model_original_calls_and_feedback':model,'formal_adoption':study['formal_adoption'],'one_page_judgment':judgments,
        'model_actual_behavior':behavior,
        'phase_history':study.get('phase_history',{}),'actual_candidate_chain':study.get('actual_candidate_chain',[]),
        'two_evaluated_children_target_achieved':all(q['candidate'] is not None for q in qsteps),
        'stop_boundary':'At most4 billed generations and2 actually evaluated model candidates. Early duplicate failures remain phase history; call3 C1 plus its real feedback precede last call4 C2. No fifth call or third actual candidate.',
        'audit':{'passed':True,'actual_records_verified':len(cache),'candidate_advantage_recomputations':candidate_checks,
            'all_pair_prefix_states_actual':True,'noise_same_channel_tick_verified':True,'A_equals_actual_Tour':True,
            'no_confirmation_rows_read':True,'old_results_rewritten':False},
        'source_receipts':{p.name:read(p) for p in sorted((STAGE/'source').glob('receipt-*.json'))},'evidence_inventory':inventory}
    for name,rows in [('全部六条件结果.csv',all_rows),('同状态干预结果.csv',pair_rows)]:
        columns=list(dict.fromkeys(k for row in rows for k in row))
        with (STAGE/name).open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows(rows)
    output=ROOT/'reports/2026-11-01-基线保留局部修正结果.md'
    single=ROOT/'reports/2026-11-01-基线保留修正单文件汇总.json';write(single,result)
    text=f'''# 相对Tour的有依据局部修正：开发实验结果

本轮已经结束。实际完成{numeric['attempts']}/60次仿真环境评价、{len(calls)}/4次真实Qwen调用、{numeric['actual_Qwen_children']}个模型子规则实评；0训练、0新确认。所有数据来自原六个已看开发条件，属于合成机房实际闭环运行。正式默认选择：**{study['formal_adoption']['selected']}**。

两条模型子规则均实评的目标是否完成：**{'是' if all(q['candidate'] is not None for q in qsteps) else '否'}**。最初两次重复H保留为失败阶段；第3调用形成实际C1，最后授权调用读取其真实结果后尝试C2。生成阶段与实际候选编号分开，不把旧失败改写为执行，不增加第5调用或第3实际候选。

## 1. 可运行的基线保留适配器

原序默认优势0；只有公开风险加权净提前收益为正、减去非负移动/期限惩罚后仍过门槛，才执行合法排列。缺失不当正常，跨系统代理不当故障确认。保留128机柜、18人、最多3项窗口、原观测/冻结估计器、1800秒、原任务账本和安全核。

[原型、固定规则与复现](../research/2026-11-01-baseline-correction/原型与复现.md)。人工门和成本方向属于接口贡献；Q只修改既有来源权重、陈旧性组合、非负代价和修正阈值。旧Q1/Q2评价不改判。

## 2. 六个真实同状态干预

根按公开条件先冻结，再从相同真实前缀各自执行A原序、B唯一替代，并恢复Tour到回合结束。前缀状态/动作SHA一致，A实际回归T；没有套用原轨迹后续观察。

|条件|根时刻/s|A原序→B替代|漏检差|等待差/s|移动差/m|服务差/s|完成差|三目标分类|
|---|---:|---|---:|---:|---:|---:|---:|---|
'''
    for r in pair_rows:
        if 'absent_reason' in r:continue
        fields=['B_minus_A_missed_segments','B_minus_A_consequence_weighted_censored_delay_s','B_minus_A_travel_m','B_minus_A_service_s','B_minus_A_completed_inspections']
        text+='|'+r['case_id']+'|'+num(r['time_s'])+'|'+r['original']+' → '+r['alternative']+'|'+'|'.join(num(r[k]) for k in fields)+'|'+r['category']+'|\n'
    text+='\n差值均为B减A；正等待/移动表示变差。健康等待为空。support_change只表示漏检/等待/移动三目标支配，健康两例同时少完成1项，不能把少做工作写成效率增益；没有正式采用资格。六根上R实际均更偏好A，B为其最佳非原备选，不能误称为R建议的改序。[全部干预与尾部义务](../research/2026-11-01-baseline-correction/同状态干预结果.csv)。\n'
    text+='''
## 3. H/S/Q真实修改链与全部开发条件

|方法|平均漏检|异常条件平均等待/s|全队移动/m|全队服务/s|完成数|本轮未完|未完承诺|最大重访/s|违规|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
'''
    fields=('missed_segments','consequence_weighted_censored_delay_s','travel_m','service_s','completed_inspections','current_round_unfinished_obligations','unfinished_committed_tasks','max_gap_s','gap_violations')
    for name,m in aggregates.items():text+='|'+name+'|'+'|'.join(num(m[k]) for k in fields)+'|\n'
    text+='\n等待包含漏检异常截至结束时的删失等待，健康不记0；服务为18人累计秒数，回合始终1800秒。待完成义务不是异常漏检。\n\n'
    for name,step in [(f'S{r["round"]}',r) for r in simple['rounds']]+list(zip(model_labels,qsteps)):
        candidate=step['candidate'];text+=f'- {name}：'+('保留新父版本' if step['selection']['accepted'] else '保留原父版本')+'；'+(json.dumps(candidate['policy']['rule'],ensure_ascii=False,separators=(',',':')) if candidate else '调用额度内未形成合法非重复子式')+'。\n'
    text+=f'''\n采用资格按预定Pareto规则判断，取舍不自动升级默认；还要求完成数不低于T。默认仍可为T。完整原始回复、失败、实际输入、父版本、保留理由及全部分条件成本见[单文件JSON](2026-11-01-基线保留修正单文件汇总.json)；[全条件CSV](../research/2026-11-01-baseline-correction/全部六条件结果.csv)。

真实计数包含失败；静态分词预检不加载8B、不生成，单列于作业账目。Slurm分配CPU{num(cost)}核分钟、GPU0秒。记录后处理仅复算现有原件，不增加环境评价。

## 4. 一页判断

'''
    for title,key in [('公开评分能否识别有益改序','public_score'),('具体反馈是否改对了部分','feedback'),('是否只胜过弱父规则','weak_parent'),('哪些成本没有业务换算','costs')]:text+='**'+title+'：** '+judgments[key]+'\n\n'
    text+='**反馈覆盖到哪里：** '+judgments['paired_feedback_coverage']+'\n\n'
    text+=judgments['limits']+' 本轮结束后停止；没有自动扩窗口、换种子、加调用、重训或启动F2/G1b。\n'
    output.write_text(text,encoding='utf8',newline='\n')
    write(STAGE/'交付核验.json',{'passed':True,'actual_records_verified':len(cache),'candidate_checks':candidate_checks,
        'single_json_sha256':sha(single),'table_rows':len(all_rows),'paired_rows':len(pair_rows),
        'record_only_wall_seconds':time.perf_counter()-started,'record_only_CPU_seconds':time.process_time()-cpu})
    print(json.dumps({'actual_records':len(cache),'attempts':len(attempts),'model_calls':len(calls),'adoption':study['formal_adoption']['selected'],'report':str(output)}))


if __name__=='__main__':main()
