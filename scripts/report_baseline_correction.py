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
from patrol_rsi.correction_selection import vector,dominates,adopt
from patrol_rsi.multistep_workflow import digest


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
    study=read(run/'study-complete.json');base=study['references'];archive=study['archive'];sig=study['execution_signature']
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
        pair_rows.append({'case_id':item['case_id'],'time_s':r['time_s'],'agent':r['agent'],
            'original':str(r['window']),'alternative':str(r['alternative_order']),'risk_class':r['root_risk_class'],
            'category':labels['labels'][item['case_id']],**{('B_minus_A_'+k):v for k,v in expected.items()},
            'same_prefix_state_verified':True,'root_sha256':item['root_sha256']})
    qsteps=[read(run/f'Q{i}-complete.json') for i in (1,2)];simple=read(run/'S-complete.json')
    assert study['formal_adoption']==adopt(base['T'],{**archive,'R':base['R']})
    attempts=[json.loads(v) for v in (run/'environment-attempts.jsonl').read_text().splitlines()]
    calls=[json.loads(v) for v in (run/'model-calls.jsonl').read_text().splitlines()] if (run/'model-calls.jsonl').exists() else []
    assert len(attempts)<=60 and len(calls)<=4
    model=[]
    for receipt in calls:
        folder=run/f'model-round-{receipt["round"]}'/f'call-{receipt["number"]:02d}'
        start=read(folder/'start.json')
        assert start['input_tokens']<=4096
        for forbidden in ('41000','41001','43000','43001','fault_start_s','scenario','onset_s','first_confirmation_s'):
            assert forbidden not in start['rendered_prompt'],forbidden
        model.append({'receipt':receipt,'start':start,'response':read(folder/'response.json') if (folder/'response.json').exists() else None,
            'failure':read(folder/'failed.json') if (folder/'failed.json').exists() else None,
            'accepted':read(folder/'accepted-interface.json') if (folder/'accepted-interface.json').exists() else None})
    if (run/'model-round-2/startup.json').exists():assert read(run/'model-round-2/startup.json')['feedback_Q1_receipt_sha256']==sha(run/'Q1-complete.json')
    accounts=[]
    keys=('job_id','state','exit_code','elapsed_seconds','allocated_cpus')
    for line in (run/'jobs/accounting.psv').read_text().splitlines():
        row=dict(zip(keys,line.split('|')));row['elapsed_seconds']=int(row['elapsed_seconds']);row['allocated_cpus']=int(row['allocated_cpus']);accounts.append(row)
    cost=sum(v['elapsed_seconds']*v['allocated_cpus'] for v in accounts)/60
    numeric={'attempts':len(attempts),'cap':60,'actual_record_identities':len(cache),'paired_records':sum('root' in v and v['root'] is not None for v in pairs['pairs'])*2,
        'actual_Qwen_calls':len(calls),'actual_Qwen_children':sum(q['candidate'] is not None for q in qsteps),'neural_training':0,'new_confirmation':0,
        'Slurm_allocated_CPU_core_minutes':cost,'GPU_seconds':0,'allocations':accounts}
    judgments={
        'public_score':'六个预登记单次干预中：健康两例仅三目标移动下降，但各少完成1项；正风险三例改序被Tour支配，一例等待恶化15秒换移动下降4.8米。不能据此声称已识别可靠有益改序，更不是整个排列空间上界。',
        'feedback':'Q使用这次新增的实际同状态后果；Q2按Q1真实分项和保留/回退结果生成。具体是否改变正确来源须结合实际提案与轨迹；结构合法不算任务进步。',
        'weak_parent':'Q同时与H、两步S、T比较；H目前在同漏检/等待下比T平均多走约2.03米，被T支配，优于H仍需单独检查是否超越T。',
        'costs':'没有业务换算支撑用任意等待小改善补偿移动增加。三目标取舍保存，不自动正式采用；少做任务造成的服务/移动减少不视为效率收益。',
        'limits':'仅六个已看开发条件；无新确认、无无反馈对照、无元更新。经验因果贡献与递归增量均未测。'}
    inventory=[{'path':p.relative_to(STAGE).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(run.rglob('*')) if p.is_file()]
    result={'schema':'baseline-correction-delivery-v1','status':'finite_development_experiment_finished',
        'baseline':'db2f9c7c66bd2f31bb33d3fbabac2eb733512e51','plan_commit':'dd6803e113e4a4f53a800d70613fe8dbba05f867',
        'execution_signature':sig,'postprocessing_script_sha256':sha(Path(__file__)),'protocol':read(STAGE/'protocol.json'),
        'budget':numeric,'aggregates':aggregates,'all_six_condition_results':all_rows,'paired_results':pair_rows,
        'paired_raw_receipts':pairs,'tolerance_labels':labels,'human':archive['H'],'simple_rounds':simple,'Q_rounds':qsteps,
        'model_original_calls_and_feedback':model,'formal_adoption':study['formal_adoption'],'one_page_judgment':judgments,
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
    text+='\n差值均为B减A；正等待/移动表示变差。健康等待为空。support_change只表示漏检/等待/移动三目标支配，健康两例同时少完成1项，不能把少做工作写成效率增益；没有正式采用资格。[全部干预与尾部义务](../research/2026-11-01-baseline-correction/同状态干预结果.csv)。\n'
    text+='''
## 3. H/S/Q真实修改链与全部开发条件

|方法|平均漏检|异常条件平均等待/s|全队移动/m|全队服务/s|完成数|本轮未完|未完承诺|最大重访/s|违规|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
'''
    fields=('missed_segments','consequence_weighted_censored_delay_s','travel_m','service_s','completed_inspections','current_round_unfinished_obligations','unfinished_committed_tasks','max_gap_s','gap_violations')
    for name,m in aggregates.items():text+='|'+name+'|'+'|'.join(num(m[k]) for k in fields)+'|\n'
    text+='\n等待包含漏检异常截至结束时的删失等待，健康不记0；服务为18人累计秒数，回合始终1800秒。待完成义务不是异常漏检。\n\n'
    for name,step in [(f'S{r["round"]}',r) for r in simple['rounds']]+[(f'Q{i}',q) for i,q in enumerate(qsteps,1)]:
        candidate=step['candidate'];text+=f'- {name}：'+('保留新父版本' if step['selection']['accepted'] else '保留原父版本')+'；'+(json.dumps(candidate['policy']['rule'],ensure_ascii=False,separators=(',',':')) if candidate else '调用额度内未形成合法非重复子式')+'。\n'
    text+=f'''\n采用资格按预定Pareto规则判断，取舍不自动升级默认；还要求完成数不低于T。默认仍可为T。完整原始回复、失败、实际输入、父版本、保留理由及全部分条件成本见[单文件JSON](2026-11-01-基线保留修正单文件汇总.json)；[全条件CSV](../research/2026-11-01-baseline-correction/全部六条件结果.csv)。

真实计数包含失败；静态分词预检不加载8B、不生成，单列于作业账目。Slurm分配CPU{num(cost)}核分钟、GPU0秒。记录后处理仅复算现有原件，不增加环境评价。

## 4. 一页判断

'''
    for title,key in [('公开评分能否识别有益改序','public_score'),('具体反馈是否改对了部分','feedback'),('是否只胜过弱父规则','weak_parent'),('哪些成本没有业务换算','costs')]:text+='**'+title+'：** '+judgments[key]+'\n\n'
    text+=judgments['limits']+' 本轮结束后停止；没有自动扩窗口、换种子、加调用、重训或启动F2/G1b。\n'
    output.write_text(text,encoding='utf8',newline='\n')
    write(STAGE/'交付核验.json',{'passed':True,'actual_records_verified':len(cache),'candidate_checks':candidate_checks,
        'single_json_sha256':sha(single),'table_rows':len(all_rows),'paired_rows':len(pair_rows),
        'record_only_wall_seconds':time.perf_counter()-started,'record_only_CPU_seconds':time.process_time()-cpu})
    print(json.dumps({'actual_records':len(cache),'attempts':len(attempts),'model_calls':len(calls),'adoption':study['formal_adoption']['selected'],'report':str(output)}))


if __name__=='__main__':main()
