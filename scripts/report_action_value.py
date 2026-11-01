"""Audit actual artifacts and report fixed OOF results. Never refit or step an environment."""
import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[1];STAGE=ROOT/'research/2026-11-01-action-value'
REMOTE='/share/home/renly/renly-patrol-rsi/runs/20261101-action-value/'
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from patrol_rsi.multistep_workflow import digest
from patrol_rsi.action_value_features import features,FEATURE_NAMES
from patrol_rsi.action_value_data import outcomes,event_pairs,objective,dominates,task_improvement
from patrol_rsi.action_value_learning import weights,predict,HEADS
from patrol_rsi.action_value_evaluation import head_errors,pair_rankings


def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8',newline='\n')
def num(x):return '—' if x is None else f'{x:.6g}' if isinstance(x,(float,np.floating)) else str(x)


def main():
    start=time.perf_counter();cpu=time.process_time();p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();run=a.run.resolve()
    data=read(run/'dataset.json');seal=read(run/'dataset-seal.json');rows=data['samples'];sig=data['execution_signature']
    need=lambda value,message:None if value else (_ for _ in ()).throw(RuntimeError(message))
    need(sha(run/'dataset.json')==seal['dataset_sha256'],'Sealed dataset bytes')
    attempts=[json.loads(s) for s in (run/'environment-attempts.jsonl').read_text().splitlines()]
    fits=[json.loads(s) for s in (run/'fit-attempts.jsonl').read_text().splitlines()]
    need(len(attempts)<=180 and len(fits)==4,'Actual budgets')
    need({f['fold'] for f in fits}==set(range(4)) and {f['heldout_group'] for f in fits}==set(data['all_development_groups']),'Four unique declared leave-group runs')
    need(not(run/'model-calls.jsonl').exists(),'Zero Qwen calls')
    complete=[read(p) for p in sorted((run/'evaluations').glob('*/complete.json'))]
    need(len(complete)==len(attempts) and len({v['evaluation_key'] for v in complete})==len(complete),'All attempts completed, no duplicate actual identities')
    raw_paths={}
    def raw(row):
        need(row['record_path'].startswith(REMOTE),'Current-run namespace only')
        path=run/row['record_path'].removeprefix(REMOTE);need(sha(path)==row['record_sha256'],'Raw SHA')
        value=json.loads(gzip.decompress(path.read_bytes()))
        need(value['execution_signature']==sig==row['execution_signature'] and value['evaluation_key']==row['evaluation_key'],'Raw execution/identity')
        need(value['metrics']==row['metrics'] and digest(value['action_log'])==row['action_sha256'],'Actual actions/metrics')
        need(len(value['action_log'])==359 and row['audit']['passed'] and value['metrics']['extra_checks']==0 and value['metrics']['tasks_violating_exact_gap']==0,'Full unchanged safe closed loop')
        need(value['raw_cvae_call_times']==list(map(float,range(30,1801,30))),'Raw CVAE copies from original call schedule only')
        raw_paths[row['evaluation_key']]=row['record_sha256'];return value
    roots=read(run/'roots-frozen.json');branches=read(run/'branches-complete.json');tours=read(run/'tours-complete.json')
    need(len(roots['roots'])<=24 and branches['frozen_roots_sha256']==sha(run/'roots-frozen.json'),'Pre-frozen roots')
    original_tour={};root_selection_checks=0
    for receipt in tours['rows']:
        v=raw(receipt);decisions=sorted([d for d in v['local_decisions'] if d['legal_nonoriginal']],key=lambda d:(d['time_s'],d['agent']))
        aa=next((d for d in decisions if d['shadow_H']!=d['window'] or d['shadow_R']!=d['window']),None)
        others=[d for d in decisions if aa is None or (d['time_s'],d['agent'])!=(aa['time_s'],aa['agent'])]
        maximum=max((d['discrimination'] for d in others),default=0.)
        bb=next((d for d in others if maximum>1e-9 and d['discrimination']>=maximum-1e-9),None)
        for kind,expected in [('A',aa),('B',bb)]:
            selected=next((r for r in roots['roots'] if r['case_id']==receipt['case_id'] and r['root_type']==kind),None)
            need((selected is None)==(expected is None),'Missing root semantics')
            if selected is not None:
                need((selected['time_s'],selected['agent'])==(expected['time_s'],expected['agent']),'First shadow/global public maximum tie rule')
                root_selection_checks+=1
        original_tour[receipt['case_id']]={'actions':v['action_sha256'],'events':digest(v['inspection_events'])}
    groups={r['root_id']:r for r in branches['groups']};dataset_roots={r['root_id'] for r in rows};need(set(groups)==dataset_roots,'Every root group used')
    state_checks=0;noise_checks=0;prefix_steps=0
    for root in roots['roots']:
        group=groups[root['root_id']];safe={tuple(c['order']):c for c in root['candidates'] if c['certificate']['ok']}
        need(len(group['rows'])==len(safe)<=6 and {tuple(r['intervention']['execute_order']) for r in group['rows']}==set(safe),'All and only safe actions once, no H gate')
        original=next(r for r in group['rows'] if r['intervention']['execute_order']==root['window']);base=raw(original)
        need(base['action_sha256']==original_tour[root['case_id']]['actions'] and digest(base['inspection_events'])==original_tour[root['case_id']]['events'],'Actual original branch equals Tour')
        prior={(e['task'],e['time_s']):e['measurement'] for e in base['inspection_events']}
        samples={tuple(r['order']):r for r in rows if r['root_id']==root['root_id']}
        original_cert=safe[tuple(root['window'])]['certificate']
        for receipt in group['rows']:
            v=raw(receipt);iv=v['intervention_verified']
            need(iv['state_sha256']==digest(iv['state_snapshot'])==root['state_sha256'],'Real complete state equality')
            need(digest(v['action_log'][:iv['prefix_steps']])==root['prefix_action_sha256'],'Real prefix actions')
            state_checks+=1
            prefix_steps+=iv['prefix_steps']
            for event in v['inspection_events']:
                key=(event['task'],event['time_s'])
                if key in prior:need(event['measurement']==prior[key],'Channel/time paired noise');noise_checks+=1
            sample=samples[tuple(receipt['intervention']['execute_order'])]
            need(sample['record_sha256']==receipt['record_sha256'],'Sample actual source')
            calculated=outcomes(base,v);need(sample['y']==calculated['y'] and sample['relative_outcomes']==calculated['relative_outcomes'] and sample['wait_valid']==calculated['wait_valid'],'True relative labels, no null-to-zero')
            need(sample['confirmation_events_labels_only']==event_pairs(base,v,root['time_s']),'Full confirmation/loss correspondence')
            x=features(root['feature_rows'],original_cert,safe[tuple(sample['order'])]['certificate'],root['time_s'])
            need(np.allclose(x,sample['x'],rtol=0,atol=1e-12),'Public-only frozen36')
    need(len(raw_paths)==len(complete),'Every actual record represented in audit')
    prediction_by_id={};fold_results=[];stationarity=[]
    for fold in range(4):
        folder=run/'fits'/f'fold-{fold}';done=read(folder/'complete.json');model=read(folder/'model.json');oof=read(folder/'oof.json')
        need(done['model_sha256']==sha(folder/'model.json') and done['oof_sha256']==sha(folder/'oof.json') and model['dataset_sha256']==sha(run/'dataset.json'),'Actual fitted artifact hashes')
        need(model['lambda']==1. and model['fit_intercept'] is False and model['centering'] is False and model['feature_names']==list(FEATURE_NAMES),'Single fixed method and feature order')
        need(model['fit_signature']==done['fit_signature']==fits[fold]['fit_signature'],'Fit-time fixed source')
        held=model['heldout_group'];train=[r for r in rows if r['group_id']!=held];test=[r for r in rows if r['group_id']==held]
        need(set(model['training_groups'])=={r['group_id'] for r in train} and held not in model['training_groups'],'Whole seed held out')
        need(not(set(model['training_roots'])&{r['root_id'] for r in test}),'No candidate/root split leakage')
        x=np.asarray([r['x'] for r in train]);w=weights(train);mu=np.sum(w[:,None]*x,axis=0);scale=np.sqrt(np.sum(w[:,None]*(x-mu)**2,axis=0));scale[scale<=1e-12]=1.
        need(np.allclose(mu,model['mean'],rtol=0,atol=1e-12) and np.allclose(scale,model['scale'],rtol=0,atol=1e-12),'Train-only scaling')
        residuals=[]
        for h,head in enumerate(model['heads']):
            valid=[r for r in train if r['y'][h] is not None];beta=np.asarray(head['coefficient'])
            if head['status']=='ridge_fitted':
                z=np.asarray([r['x'] for r in valid])/scale;y=np.asarray([r['y'][h] for r in valid]);vw=weights(valid)
                # Check optimality without solving or fitting a fifth time.
                residual=z.T@(vw*(z@beta-y))+beta
                relative=float(np.max(abs(residual))/max(1.,np.max(abs(z.T@(vw*y)))))
                need(relative<1e-7,'Fixed ridge normal-equation residual');residuals.append(relative)
            else:need(np.array_equal(beta,np.zeros(36)),'Explicit zero head')
        stationarity.append({'fold':fold,'relative_residuals':residuals,'verification_did_not_refit':True})
        predicted=predict(model,[r['x'] for r in test]);mapped={r['sample_id']:r for r in oof}
        need(set(mapped)=={r['sample_id'] for r in test},'Complete held-out predictions')
        for r,pred in zip(test,predicted):
            need(mapped[r['sample_id']]['group_id']==held and np.allclose(pred,mapped[r['sample_id']]['prediction'],rtol=1e-12,atol=1e-10),'OOF actual only heldout model, cross-BLAS tolerance')
            prediction_by_id[r['sample_id']]=pred.tolist()
        fold_results.append(done)
    need(len(prediction_by_id)==len(rows),'OOF coverage')
    values=[prediction_by_id[r['sample_id']] for r in rows];errors=head_errors(rows,values);zero=head_errors(rows,[[0.]*4 for r in rows]);ranks=pair_rankings(rows,values)
    pareto_gains=[];gain_rank=Counter();event_status=Counter()
    for r in rows:
        event_status.update(e['status'] for e in r['confirmation_events_labels_only'])
        baseline=[0,None if r['y'][1] is None else 0,0,0]
        if not r['original'] and dominates(objective(r['y']),objective(baseline)):
            pp=prediction_by_id[r['sample_id']];pp=[pp[0],None if r['y'][1] is None else pp[1],pp[2],pp[3]]
            status='correct' if dominates(objective(pp),objective(baseline)) else 'reversed' if dominates(objective(baseline),objective(pp)) else 'undistinguished'
            gain_rank[status]+=1;pareto_gains.append({'root_id':r['root_id'],'sample_id':r['sample_id'],'y':r['y'],'OOF_relation_to_original':status})
    worst=[]
    for h,name in enumerate(HEADS):
        valid=[r for r in rows if r['y'][h] is not None]
        if valid:
            r=max(valid,key=lambda r:abs(prediction_by_id[r['sample_id']][h]-r['y'][h]));model=read(run/'fits'/f"fold-{data['all_development_groups'].index(r['group_id'])}"/'model.json')
            contributions=np.asarray(r['x'])/np.asarray(model['scale'])*np.asarray(model['heads'][h]['coefficient']);j=int(np.argmax(abs(contributions)))
            worst.append({'head':name,'sample_id':r['sample_id'],'root_id':r['root_id'],'actual':r['y'][h],'prediction':prediction_by_id[r['sample_id']][h],
                'largest_term':{'feature':FEATURE_NAMES[j],'input':r['x'][j],'train_scale':model['scale'][j],'train_max':model['training_feature_max'][j],'contribution':float(contributions[j])}})
    categories=dict(Counter(r['category'] for r in data['root_assessments']));benefit_roots={p['root_id'] for p in pareto_gains};detection_roots={r['root_id'] for r in rows if task_improvement(r['y'])}
    shadow_choices={}
    for method in ('shadow_R','shadow_H'):
        counts=Counter()
        for root_id,context in data['public_root_contexts'].items():
            chosen=next(r for r in rows if r['root_id']==root_id and r['order']==context[method])
            baseline=[0,None if chosen['y'][1] is None else 0,0,0]
            category='original' if chosen['original'] else 'Pareto_gain' if dominates(objective(chosen['y']),objective(baseline)) else 'worse' if dominates(objective(baseline),objective(chosen['y'])) else 'tradeoff_or_equal'
            counts[category]+=1
        shadow_choices[method]=dict(counts)
    audit={'passed':True,'all_records':len(raw_paths),'actual_full_state_comparisons':state_checks,'root_selection_checks':root_selection_checks,
        'shared_channel_time_measurements':noise_checks,'all_safe_actions_complete':True,'all_event_labels_verified':True,
        'no_leakage_in_scalers_or_groups':True,'fit_optimality_without_refitting':stationarity,'large_network_training':0,'Qwen_calls':0}
    accounts=[]
    for line in (run/'jobs/accounting.psv').read_text().splitlines():
        fields=line.split('|');accounts.append({'job_id':fields[0],'state':fields[1],'exit':fields[2],'seconds':int(fields[3]),'cpus':int(fields[4])})
    budget={'environment_attempts':len(attempts),'Tour_records':len(tours['rows']),'actual_branches':len(rows),'formal_grouped_fits':len(fits),
        'paired_prefix_replay_steps_included_in_branches':prefix_steps,'actual_virtual_steps':len(complete)*359,
        'frozen_CVAE_forward_calls':len(complete)*60,
        'Qwen_calls':0,'CVAE_PPO_LLM_training':0,'new_processes':0,'new_confirmation':0,'Slurm_CPU_core_minutes':sum(v['seconds']*v['cpus'] for v in accounts)/60,
        'GPU_seconds':0,'allocations':accounts,'static_record_audit_CPU_seconds_before_export':time.process_time()-cpu}
    probe=read(run/('cost-probe-'+sig[:12]+'.json'))
    need(probe['evaluation_key']==tours['rows'][0]['evaluation_key'] and probe['record_sha256']==tours['rows'][0]['record_sha256'],'Cost pilot exactly reused, not an extra sample')
    budget['cache_references']={'pilot_to_Tour_list':1,'counts_as_additional_environment':False,'branches_cached_in_this_first_pass':0,'formal_fits_cached_in_this_first_pass':0}
    judgments={'decision':'D为主；成本侧有公开可辨别的机会，但固定岭工具尚不可靠，暂不进入学习调度闭环',
        'opportunity':f'{len(benefit_roots)}根有成本型Pareto改进：发现和完成量不变、少走1.6米。无无代价检测改进（{len(detection_roots)}根），另有8根取舍、3根全部替代劣于原序。存在少漏1段但多走9.3/11.3米且少完成1次的取舍，不能事后改权重宣布全面胜出。',
        'learning':'四包确实拟合；完成量头仅MAE改善，RMSE仍更差。漏检、等待、移动的MAE/RMSE均不如零增量。13个成本型好动作对原序，岭模型全部未区分；既有R影子却选中了这13个正例，说明这些状态的公开几何信息可用，不能把学习器失败归成公开信息本质无用。R的单次选择正确也不证明其完整在线策略更优。',
        'ranking':'304个真实可比动作对中，ridge原始正确109、反转9、未区分186；按种子/根等权有序覆盖40.4%，有序部分准确约93.1%，全部可比对正确约37.6%。不能单报93.1%；这些对也不是304个独立物理样本。',
        'specific_gap':'留出42001的dev-11-B有2个严重外推点：风险提前特征约2.390e-4，训练最大仅7.725e-7（约309倍），训练尺度7.399e-8使该项对等待贡献约925秒，实际等待变化0。保留原预测、不裁剪、不再拟合。问题定位在采样/特征分布覆盖和低方差缩放后的外推，而不是缺少更多代价系数。',
        'scope':'仅4个已看开发种子、固定相位335秒和原布局；24根都是热巡检，没有其他专业动作价值覆盖。数据是单次改序后恢复Tour的实现后果，不是POMDP期望Q、全局上界或新确认。没有在线学习调度闭环、经验消融或元改进，不能称任务收益或RSI成功。',
        'abcd':'A的检测改善与可靠学习证据不足，仅有成本侧机会；B只能限定为本表征/模型失败，不能断言全部公开信息不可区分；整体C不成立（有13个成本正例），检测子目标尚无无代价改善；D确有8根代价取舍。下一步先处理已定位的训练覆盖/数值外推问题，需另立验证协议，本轮不改模型补成绩。',
        'stop':'本轮结束，不增加根/窗口/过程/模型族/正则/训练次数。保留数据与错误模型作为下一轮针对覆盖和表示的证据，不盲调手写代价权重。'}
    inventory=[{'path':p.relative_to(STAGE).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(run.rglob('*')) if p.is_file()]
    result={'schema':'action-value-preexperiment-delivery-v1','completion_date':'2026-11-02','status':'completed_fixed_development_experiment',
        'protocol':read(STAGE/'protocol.json'),'budget':budget,'dataset_seal':seal,'data_contract':{'feature_names':list(FEATURE_NAMES),'only_model_input':'x numeric36',
            'heads':list(HEADS),'wait_null':'Label mask only, never inference input','grouping':'Whole underlying seed held out including all processes/roots/actions',
            'metadata_not_inputs':['seed','scenario','root_id','root_type','event intervals','branch outcomes','wait_valid']},
        'root_classifications':data['root_assessments'],'category_counts':categories,'Pareto_improvements_over_original':pareto_gains,
        'cost_gain_vs_original_rankings':dict(gain_rank),'public_shadow_choice_outcomes':shadow_choices,'qualified_detection_improvement_roots':len(detection_roots),
        'OOF_errors':errors,'zero_baseline_errors':zero,'OOF_rankings':ranks,'fold_results':fold_results,
        'fitted_model_packages':{f'fold-{i}':read(run/'fits'/f'fold-{i}'/'model.json') for i in range(4)},
        'worst_errors':worst,'event_change_counts':dict(event_status),'dataset':data,'audit':audit,'one_page_judgment':judgments,
        'postprocessing_script_sha256':sha(Path(__file__)),'source_receipts':{p.name:read(p) for p in sorted((STAGE/'source').glob('receipt-*.json'))},'evidence_inventory':inventory}
    output=ROOT/'reports/2026-11-02-局部动作价值学习预实验.md';single=ROOT/'reports/2026-11-02-动作价值数据与学习单文件汇总.json';write(single,result)
    table=[]
    for r,pred in zip(rows,values):
        table.append({'root_id':r['root_id'],'case_id':r['case_id'],'audit_group_id':r['group_id'],'action_order':str(r['order']),
            'original':r['original'],'wait_valid_label_only':r['wait_valid'],**r['relative_outcomes'],
            **{('OOF_'+name):pred[h] for h,name in enumerate(HEADS)},'H_preference':r['H_preference'],'H_advantage':r['H_advantage'],
            'record_sha256':r['record_sha256'],**dict(zip(FEATURE_NAMES,r['x']))})
    with (STAGE/'全合法动作价值表.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
    write(STAGE/'数据契约.json',result['data_contract'])
    example=next(r for r in rows if r['group_id']==data['all_development_groups'][0] and not r['original']);write(STAGE/'预测输入示例.json',{'x':example['x']})
    text=f'''# 全合法局部动作后果与轻量价值学习预实验

已完成 **{len(attempts)}/180次环境尝试、24根×6=144条真实分支、4/4次分组岭回归拟合、0次Qwen调用**。12个条件来自4个已登记开发种子；未生成新过程、未训练CVAE/PPO/LLM。完成日期2026年11月2日。正式巡检默认仍为Tour，学习工具未上线。

## 1. 可复用数据集与契约

[数据集原件](../research/2026-11-01-action-value/evidence/run/dataset.json)包含144个状态—动作—实际后果样本、来源SHA、公开连续读数/原始CVAE/名义估计/年龄/掩码及事件对应；[数据契约](../research/2026-11-01-action-value/数据契约.json)明确只有36维x进入模型，seed/根ID/未来事件/标签mask只用于审计、划分或离线评价。

健康等待保持null。每个动作只执行一个承诺段后恢复Tour，后续观察/估计真实重新生成。该数据不是一般期望动作价值或全局上界。[接口、分组与复现说明](../research/2026-11-01-action-value/原型与复现.md)。

## 2. 全部合法动作的有限后果

所有24个根均有6个安全合法排列，含原序；没有用H正风险门筛动作。12条Tour和144条分支全部通过原安全/账本审计，完整状态/前缀、原序=Tour及同通道同时刻噪声已复核。

13根有成本型Pareto改进，每次少走1.6米而检测/完成量不变；8根存在取舍，3根所有替代均劣于原序。未发现同时改善检测且移动不增、完成不减的动作。不能因此称“没有有益动作”：成本型正例真实存在，少漏1段但多走路/少完成工作的动作也有业务取舍。

[144行全动作价值表](../research/2026-11-01-action-value/全合法动作价值表.csv)保留所有分项后果、服务/末尾义务、来源和OOF预测。新增/失去确认事件在dataset的标签区逐项保存；少做工作造成的移动减少不当效率收益。

## 3. 已拟合工具与四折留组结果

固定36维、λ=1、无截距、float64岭回归；每折整组留出一个seed，标准差只由训练3组拟合，健康等待不填0。4包模型均已实际拟合四个输出头，没有第5次全数据重拟合。[模型目录](../research/2026-11-01-action-value/evidence/run/fits)与复现说明提供load/predict命令。

下表是预测“相对后果变化”的误差，不是学习策略的巡检运行得分；本轮未按预测在线派单。

|相对后果头|有效样本|岭回归OOF MAE|零增量MAE|岭回归RMSE|零增量RMSE|
|---|---:|---:|---:|---:|---:|
'''
    for name in HEADS:
        label={'missed':'漏检段变化','wait_s':'等待变化/s','travel_m':'移动变化/m','completed':'完成量变化'}[name]
        m=errors[name]['all_valid'];z=zero[name]['all_valid'];text+='|'+label+'|'+str(m['n'])+'|'+'|'.join(num(v) for v in (m['mae'],z['mae'],m['rmse'],z['rmse']))+'|\n'
    text+='''
完成量头仅MAE下降、RMSE却上升：典型绝对误差小一些，极端错误更重；其他三头两项指标均更差。等待变化标签16个中的MAE有所下降，但不能据此隐藏大多数零变化样本上的误差与极端外推。完整逐折、变化子集及正/负/零方向混淆见单文件JSON。

|排序器|真实可比对数|正确/反转/未分（原始数）|加权有序覆盖|有序部分准确率|全部可比对正确率|
|---|---:|---|---:|---:|---:|
'''
    for name,v in ranks.items():
        c=v['raw_counts'];text+=f'|{name}|{v["comparable_pairs"]}|{c["correct"]}/{c["reversed"]}/{c["undistinguished"]}|{num(v["ordered_coverage"])}|{num(v["conditional_accuracy"])}|{num(v["all_comparable_correct_fraction"])}|\n'
    text+=f'''
不能单报约93.1%的条件准确率：模型只区分约40.4%的可比对，且13个成本型好动作对原序全部未区分。H的100%条件准确率也只来自极低覆盖。可比对不是独立物理样本。

作为数据诊断，既有R的影子建议选中了这13个成本型正例，H因门控大多保持原序。它证明这些状态中公开几何信息已有可用性，不能把岭模型失败说成“没有任何可用信息”；也不代表重复执行R的完整策略会变好。

最严重错误在留出42001的dev-11-B：实际等待变化0，预测约913.876秒；风险提前特征超出训练最大值约309倍，经极小训练标准差缩放后贡献约925秒。保留原系数/预测，不裁剪、不调λ、不重训。各折训练范围与外推行数均已保存。

Slurm分配CPU{num(budget['Slurm_CPU_core_minutes'])}核分钟、GPU0秒。参数最优性仅检查正规方程残差，没有重新拟合；工具保存/加载预测与原OOF一致。

## 4. 一页研究判断

**{judgments['decision']}。**

**行动机会：** {judgments['opportunity']}

**公开信息与学习：** {judgments['learning']}

**具体缺口：** {judgments['specific_gap']}

**A/B/C/D如何落地：** {judgments['abcd']}

**范围与停止：** {judgments['scope']} {judgments['stop']}

[单文件JSON：数据、四折、错误与全部来源](2026-11-02-动作价值数据与学习单文件汇总.json)。已有结果和NO-GO未修改。
'''
    output.write_text(text,encoding='utf8',newline='\n')
    write(STAGE/'交付核验.json',{'passed':True,**audit,'dataset_sha256':sha(run/'dataset.json'),'single_json_sha256':sha(single),
        'report_sha256':sha(output),'value_table_sha256':sha(STAGE/'全合法动作价值表.csv'),
        'record_only_wall_seconds':time.perf_counter()-start,'record_only_CPU_seconds':time.process_time()-cpu})
    print(json.dumps({'records':len(raw_paths),'samples':len(rows),'fits':len(fits),'decision':judgments['decision'],'report':str(output)}))


if __name__=='__main__':main()
