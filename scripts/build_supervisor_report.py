"""Build the static self-reading supervisor report from saved files only."""
from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
DEPS=ROOT/'.work/paper-writing-deps'
if DEPS.is_dir():sys.path.insert(0,str(DEPS))
from markdown_it import MarkdownIt
from report_diagrams import build_report_diagrams
from supplement_report import substitutions as supplement_substitutions
from report_text_export import export_review_text

PAPER=ROOT/'paper'
SOURCES={}
REMOTE='https://github.com/DonsonHH/Zhinengti-RSI/blob/'
BASE='2db2adf146357ec35306503ed15183c0c4100d20'
BRANCH='donson/restart-alignment'


def read(relative):
    value=(ROOT/relative).read_bytes();SOURCES[relative]=hashlib.sha256(value).hexdigest()
    return value


def load(relative):return json.loads(read(relative).decode('utf-8'))


def write_json(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def resolve_source_link(target,*,current=False):
    target=target.removeprefix('<').removesuffix('>')
    if target.startswith(('#','https:','http:','data:')):return target
    path=(PAPER/target).resolve().relative_to(ROOT).as_posix()
    if path.endswith('.html'):path=path[:-5]+'.md'
    latest=current or '/research/' in path or path in ('paper/supplement-study-methods.md','paper/source-data/estimation-confirmation-gap.json') or path.startswith('evidence/supplement-study/')
    return REMOTE+(BRANCH if latest else BASE)+'/'+path


def table(headers,rows,kind):
    cell=lambda tag,value:f'<{tag}>'+html.escape(str(value))+f'</{tag}>'
    return '<div class="table-wrap"><table data-table="'+kind+'"><thead><tr>'+''.join(cell('th',v) for v in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(cell('td',v) for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'


def comparison_table(comparison):
    headings='<thead><tr><th rowspan="2">方法</th><th colspan="3">状态估计</th><th rowspan="2">适配idleness<br>加权年龄↓</th><th colspan="3">异常任务</th><th colspan="3">成本与效率</th><th rowspan="2">本任务状态</th></tr><tr><th>RMSE<br>°C↓</th><th>加权RMSE<br>°C↓</th><th>R²↑</th><th>确认段数<br>（比例）↑</th><th>截尾等待<br>秒↓</th><th>硬重访<br>违规</th><th>移动变化<br>%</th><th>完成量变化<br>%</th><th>单步推理<br>ms</th></tr></thead>'
    labels={'tour':'固定巡回Tour','shuffled':'名义估计＋风险位置置乱','S1-age':'线性暂缓①：等待15秒','S2-risk_time':'线性暂缓②：多特征','fifo':'名义估计＋返回保护FIFO'}
    rows=[]
    for method in comparison['method_order']:
        if method in comparison['aggregates']:
            item=comparison['aggregates'][method]
            change=sum((c['methods'][method]['completed_inspections']/c['methods']['tour']['completed_inspections']-1)*100 for c in comparison['cases'])/len(comparison['cases'])
            values=[labels[method],'未留帧','未留帧','未留帧',f"{item['mean_weighted_normalized_age']:.6f}",
                    f"{item['confirmed_segments']}/{item['anomaly_segments']}（{100*item['confirmation_ratio']:.1f}%）",
                    f"{item['mean_consequence_weighted_censored_delay_s']:.2f}",item['revisit_violating_task_episode_pairs'],
                    f"{item['mean_travel_change_vs_tour_pct']:+.2f}",f'{change:+.2f}','未计时',
                    '已运行·开发并列60' if method.startswith('S') else '已运行·主比较']
            state='development' if method.startswith('S') else 'primary'
        else:
            item=comparison['unrun_methods'][method]
            values=[item['label'],*['旧包未运行']*10,'历史封存状态；新结果见补充基准'];state='not_run'
            assert item['all_metric_values'] is None and not item['trained_or_training_claim_supported']
        cells=''.join('<td>'+html.escape(str(value))+'</td>' for value in values)
        rows.append(f'<tr data-comparison-method="{method}" data-result-state="{state}">'+cells+'</tr>')
    return '<div class="table-wrap"><table class="comparison-table" data-table="method-comparison">'+headings+'<tbody>'+''.join(rows)+'</tbody></table></div>'


def main():
    read('paper/report-readability-spec-20261103.md')
    for source in ['scripts/build_supervisor_report.py','scripts/report_diagrams.py','scripts/briefing_diagrams.py','scripts/report_text_export.py','scripts/analyze_estimation_confirmation_gap.py']:
        read(source)
    summary=load('evidence/event-validation/final/summary.json')
    protocol=load('evidence/event-validation/final/protocol.json')
    assert protocol['extra_visit_budget']==12 and protocol['ttl_s']==120
    rows=load('evidence/event-validation/final/rows.json')
    pairs=load('evidence/event-validation/final/pairs.json')
    metrics=load('paper/generated/metrics.json')
    proposals=load('evidence/response-defer/proposals.json')
    legacy=load('paper/briefing-history/2db2adf1/briefing-chart-data.json')
    engineering=load('paper/source-data/engineering-snapshot-500.json')
    fifo=load('paper/source-data/fifo-decision-p01-470.json')
    kinds=load('paper/source-data/primary-anomaly-kinds.json')
    method_evidence=load('paper/source-data/report-method-evidence.json')
    rule_diagnosis=load('paper/source-data/report-rule-diagnosis.json')
    comparison=load('paper/source-data/report-comparison-metrics.json')
    supplement=load('paper/source-data/supplement-study.json')
    supplement_example=load('paper/source-data/supplement-example.json')
    assert supplement['example']['sha256']==SOURCES['paper/source-data/supplement-example.json']
    supplement_narrative=load('paper/source-data/supplement-narrative.json')
    gap_diagnosis=load('paper/source-data/estimation-confirmation-gap.json')
    assert gap_diagnosis['counts']=={'comparisons':144,'lost':8,'gained':2,'changed':8}
    assert gap_diagnosis['model_mean_net_confirmation_difference']==-2
    assert supplement_narrative['analysis_sha256']==SOURCES['paper/source-data/supplement-study.json']
    assert supplement['test_episode_count']==1080 and supplement['audit']['all_passed']
    for source in ['scripts/analyze_supplement_study.py','scripts/supplement_figures.py','scripts/supplement_diagrams.py','scripts/supplement_report.py',
                   'paper/supplement-study-methods.md','evidence/supplement-study/analysis-receipt.json','evidence/supplement-study/test-rows.json',
                   'evidence/supplement-study/protocol.json','evidence/supplement-study/seal.json','evidence/supplement-study/amendments.json',
                   'evidence/supplement-study/test-checkpoint-lock.json','evidence/supplement-study/checkpoints.zip']:
        read(source)
    for source in ['evidence/supplement-study/source-executed.json','evidence/supplement-study/source-executed.zip']:
        read(source)
    engineering_alignment=load('paper/source-data/report-engineering-alignment.json')
    visual_sample=load('paper/source-data/pid-visual-sample.json')
    images={key:read(identity['path']) for key,identity in visual_sample['assets'].items()}
    for key,raw in images.items():assert hashlib.sha256(raw).hexdigest()==visual_sample['assets'][key]['sha256']
    for source in ['report-engineering-alignment-20261103.md','report-pid-interface-20261103.md','report-comparison-metrics-20261103.md']:
        read('paper/research/'+source)
    read('paper/report-focus-spec-20261103.md')
    read('paper/report-structure-spec-20261103.md')
    read('paper/research/report-method-formulas-20261103.md')
    read('paper/research/report-rule-diagnosis-20261103.md')
    assert kinds['counts']=={'thermal':77,'cooling':12}
    archive=load('paper/briefing-history/2db2adf1/baseline.json')
    for identity in archive['files'].values():assert hashlib.sha256(read(identity['archived_as'])).hexdigest()==identity['sha256']
    read('paper/research/mentor-engineering-reference-20261103.md')
    original=read('paper/research/original-paper-metrics-20261103.md').decode('utf-8')
    read('paper/model-appendix.md')
    read('paper/mentor-requests.md')
    for source in ['src/patrol_rsi/risk_response.py','src/patrol_rsi/active_inspection.py','src/patrol_rsi/facility.py','src/patrol_rsi/facility_observation.py','src/patrol_rsi/aisles.py','src/patrol_rsi/coverage_plan.py','src/patrol_rsi/response_rule.py','src/patrol_rsi/inspection_metrics.py','src/patrol_rsi/inspection_contracts.py']:
        read(source)
    primary=[p for p in pairs if p['group']=='coupled']
    assert len(primary)==summary['primary_paired_processes']==12
    assert legacy['racks']==128 and legacy['inspectors']==18
    assert (legacy['tasks']['17']['fifo']['dispatch_s'],legacy['tasks']['17']['fifo']['visible_s'],legacy['tasks']['17']['fifo']['finish_s'])==(665,685,690)
    assert (legacy['tasks']['21']['fifo']['visible_s'],legacy['tasks']['21']['fifo']['dispatch_s'],legacy['tasks']['21']['fifo']['finish_s'])==(650,705,725)
    main_results={}
    for method in ['tour','fifo','shuffled']:
        selected=[r for r in rows if r['group']=='coupled' and r['method']==method]
        assert len(selected)==12
        result={'confirmed':sum(r['confirmed_segments'] for r in selected),
                'segments':sum(r['anomaly_segments'] for r in selected)}
        assert result['confirmed']==metrics['main'][method]['confirmed_segments']==summary['groups']['coupled'][method]['confirmed_segments']
        assert result['segments']==89
        main_results[method]=result
    assert all(sum(r[key] for r in rows)==0 for key in ['tasks_violating_exact_gap','invalid_assignments','duplicate_reservations'])
    gained=sum(p['fifo_minus_tour']['gained'] for p in primary)
    lost=sum(p['fifo_minus_tour']['lost'] for p in primary)
    assert (gained,lost)==(45,3) and main_results['fifo']['confirmed']-main_results['tour']['confirmed']==gained-lost
    comp=summary['primary_comparisons']['fifo_minus_tour']
    registered={}
    for proposal in proposals:
        assert proposal['status']=='completed' and len(proposal['paired'])==12
        assert sum(p['net'] for p in proposal['paired'])==proposal['aggregate']['net']
        row={'rule_sha256':proposal['rule_sha256'],'confirmed':main_results['fifo']['confirmed']+proposal['aggregate']['net'],'rule':proposal['rule']}
        if row['rule_sha256'] in registered:assert registered[row['rule_sha256']]==row
        registered[row['rule_sha256']]=row
    assert len(registered)==9 and max(row['confirmed'] for row in registered.values())==60
    assert [(r['rule_sha256'],r['confirmed']) for r in registered.values()]==[(r['rule_sha256'],r['confirmed']) for r in legacy['registered_rules']]
    assert [(r['rule_sha256'],r['confirmed'],r['rule']) for r in registered.values()]==[(r['canonical_rule_sha256'],r['confirmed'],r['rule']) for r in rule_diagnosis['unique_rules']]
    assert method_evidence['primary_processes']['anomaly_segments_by_role']=={'thermal':77,'electrical':0,'cooling':12,'control':0}
    assert rule_diagnosis['unique_rules'][0]['binary_decision_counts']['rule:defer']==229
    assert all(row['action_log_identical'] for row in rule_diagnosis['s0_risk_matches_existing_tour'])
    assert len(engineering['public_thermal_risk'])==len(engineering['offline_temperature_c'])==128
    assert sum(v is not None for v in engineering['remote_temperature_c'])==32
    assert engineering['kind']=='engineering_explanation_not_research_gain' and engineering['method']=='tour'
    assert [(r['task'],r['visible_s']) for r in fifo['queue']]==[(10,450),(8,455)]
    assert fifo['queue'][0]['risk_at_decision']<fifo['queue'][1]['risk_at_decision']
    assert all(r['certificate_ok'] and r['budget_allowed'] for r in fifo['queue'])
    assert [(r['task'],r['completion_s']) for r in fifo['actual_dispatches']]==[(10,500),(8,515),(0,540)]
    assert [(r['projected_return_finish_s'],r['minimum_full_cycle_slack_s']) for r in fifo['checks']]==[(525,20),(540,5)]
    assert fifo['previous_routine_completion_s']+fifo['revisit_limit_s']==fifo['routine_due_s']==545
    paper=[]
    for method in ['DRL＋Myopic','DRL＋VAE','Greedy＋VAE','Greedy＋Myopic']:
        line=next(line for line in original.splitlines() if line.startswith('|'+method+'|'))
        values=line.strip('|').split('|')
        parse=lambda value:dict(zip(['mean','ci95_half_width'],map(float,value.strip().split(' ± '))))
        paper.append({'method':method,'wqp':parse(values[1]),'algae':parse(values[2])})
    assert paper[0]['wqp']['mean']==.484 and paper[1]['wqp']['mean']==.462
    data={'main':main_results,'primary_comparisons':comp,'engineering':engineering,'fifo':fifo,
          'main_costs':metrics['main'],'decision_thresholds':protocol['decision_thresholds'],
          'registered_rules':list(registered.values()),
          'fault_cases':method_evidence['primary_processes']['cases'],
          'method_basis':method_evidence['method_basis'],
          'rule_diagnosis_example':rule_diagnosis['trace_examples']['p00_first_difference_and_loss'],
          'comparison':comparison['aggregates'],'comparison_definition':comparison['definitions'],
          'comparison_unrun_methods':comparison['unrun_methods'],'engineering_alignment':engineering_alignment,'visual_sample':visual_sample,
          'primary_anomaly_kinds':kinds['counts'],
          'paper_scores':paper,'paper_metric_scope':'Original water-task score; not directly comparable to professional anomaly confirmation.',
          'supplement':supplement,'new_environment_evaluations':supplement['environment_attempts'],
          'neural_estimator_predictions':supplement['neural_prediction_accounting'],
          'trained_checkpoints':9,'external_language_model_calls':0}
    inherited={}
    for name in ['confirmations','paired-net','execution-chain','task-17','task-21']:
        inherited[name]=read('paper/figures/briefing-v3/'+name+'.svg').decode('utf-8')
    # Keep numerical encodings tied to the primary records, not merely to old prose.
    bar_root=ET.fromstring(inherited['confirmations'])
    encoded={e.attrib['data-method']:int(e.attrib['data-count']) for e in bar_root.iter() if 'data-method' in e.attrib}
    assert encoded=={key:value['confirmed'] for key,value in main_results.items()}
    net_root=ET.fromstring(inherited['paired-net'])
    encoded_net={e.attrib['data-case']:int(e.attrib['data-net']) for e in net_root.iter() if 'data-net' in e.attrib}
    assert encoded_net=={p['case']:p['fifo_minus_tour']['net'] for p in primary}
    drawings=build_report_diagrams(data,inherited,images)
    from supplement_figures import build as build_supplement_figures
    from supplement_diagrams import build as build_supplement_diagrams
    drawings.update(build_supplement_figures(supplement,supplement_example))
    drawings.update(build_supplement_diagrams())
    folder=PAPER/'figures/supervisor-report';folder.mkdir(parents=True,exist_ok=True)
    figure_hashes={}
    for name,drawing in drawings.items():
        ET.fromstring(drawing)
        path=folder/(name+'.svg');path.write_text(drawing,encoding='utf-8',newline='\n')
        figure_hashes[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    figure_notes={
        'model':'本项目集中参数模型的供电、双回路液冷与局部控制计算关系。',
        'public-risk':'已有工程回看：固定巡回，500秒；风险分由公开观测和名义估计计算。',
        'estimated-temperature':'已有工程回看500秒的公开温度估计；与右图同一色标，红框叠加原热风险提示。',
        'offline-temperature':'同一工程过程500秒的事后设备代表温度。',
        'pid-visual-sample':'PID项目既有户外电气样例，同图精修、显示域；三张原图逐字节保留，数值计量按独立测温通道处理。',
        'visual-interface':'已实现的参考元数据入口与合成接点测量分层表示；虚线标出RGB推理、选点及现场仪器桥接。',
        'fifo-cycle':'每名执行者空闲时从本人合法请求中选择；完成量测后进入下一轮。',
        'inspection-architecture':'根据本项目已实现接口重绘总体架构；上方在线决策只用公开信息，下方真值与日志用于事后评分。',
        'fifo-actions':'主验证第2个过程，一名热巡检员的实际记录；色块宽度表示移动与服务时间。',
        'outcome-costs':'历史耦合工况A的FIFO相对Tour比较；区间、代价与探索性门槛均来自封存记录。',
        'registered-rules':'本项目9个唯一规则的得分式；R、A、E、S分别对应正文中的归一风险、等待、额外耗时与余量差。',
        'rule-diagnosis':'主过程01的完整策略轨迹对照，机柜4；等待规则为图中06号，按记录重绘。',
        'original-paper-scores':'原文表8／9均值±95%CI。两种Greedy的藻华终值相同，按原表保留。',
        'confirmations':'历史耦合工况A：12个过程，共89段异常；三列为各策略的有效确认量。',
        'paired-net':'过程01—12为预登记的12个配对过程；11个净增、1个持平。',
        'execution-chain':'p02-coupled，同一巡检员1，关键任务完成链；中间部分访问省略。',
        'task-17':'17号665秒派出的是例行访问；其公开风险685秒才出现。',
        'task-21':'21号650秒见风险，705秒额外派单，725秒完成，异常在710秒已结束。',
        'supplement-unet':'本次真实训练的温度残差CVAE-U-Net。公开输入57通道，295,777个参数；训练后验只用于监督，在线取条件先验均值。',
        'supplement-crossed-design':'估计器与调度器的共同候选、约束和执行接口。PPO使用公开奖励训练，原始异常标签留给离线评价。',
        'supplement-methods':'48个故障条件，先平均三个模型种子、再等权四故障族；误差线按12组独立测试集计算95%区间。等待对有异常的条件计算。',
        'supplement-professions':'四专业异常段的描述性确认比例，数字为确认数／专业异常总数；小数来自三个模型种子的平均。',
        'supplement-estimation':'两种估计器读取同一份Tour观测记录，并用相同的新测温度校正；盲区误差排除当前新测位置，误差线为12组独立测试集的95%区间。',
        'supplement-estimator-training':'三个训练种子的真实30轮开发曲线，空心点为各自开发集最优checkpoint；测试集不参与选择。',
        'supplement-ppo-training':'六个PPO的公开奖励训练曲线；细线表示训练种子，粗线为种子均值，采用10回合滑动窗口。',
        'supplement-contrasts':'预登记的配对比较，按独立测试集自举计算95%区间。确认、等待、年龄与误差分别解释；区间不包含完整训练不确定性。',
        'supplement-seed-blocks':'逐组展示独立测试集内的确认差，四种故障等权；编号是登记身份。',
        'supplement-latency':'主要故障条件的逐回合p95均值，实测包含转换和CUDA同步。估计阶段已包含于完整控制周期，不能重复相加。',
        'supplement-heatmaps':'按编号选取首个测试条件、训练种子271和注入后90秒；名义与CVAE使用相同Tour观测流，三图共用45—75°C色标。',
        'supplement-process':'与温度图同一编号示例。阴影为故障注入窗口，点表示当前新温度量测；温度和流量阈值采用研究设定。',
        'supplement-scale':'每规模三种子×健康／耦合两工况的纯物理过程实测；带tracemalloc开销，范围为六次实测最小—最大，未作大规模学习调度。',
    }
    def figure(name):
        assert name in drawings
        return '<figure id="figure-'+name+'"><span class="wide-hint">宽图可左右滑动查看</span><div class="figure-frame">'+drawings[name]+'</div><figcaption>'+html.escape(figure_notes[name])+'</figcaption></figure>'
    queue_table=table(['本人的待确认请求','首次提示时间','470秒时风险分','当下检查','本次选择'],[
        [f"机柜{r['task']}热检查",f"{r['visible_s']:g}秒",f"{r['risk_at_decision']:.4f}",'资格、可行性和预算均通过','先查' if r['task']==fifo['selected'] else '继续等待'] for r in fifo['queue']], 'fifo-queue')
    return_table=table(['重新决策时刻','批准的加查','预计完成加查','随后按原循环返回0号','0号截止','完整循环最小余量'],[
        [f"{r['decision_s']:g}秒",r['selected_task'],f"{r['finish_s']:g}秒",f"{r['projected_return_finish_s']:g}秒",f"{r['routine_due_s']:g}秒",f"{r['minimum_full_cycle_slack_s']:g}秒"] for r in fifo['checks']], 'return-budget')
    hotspot_table=table(['机柜','当时公开风险分','名义估计温度／°C','事后代表温度／°C','固定温度遥测点'],[
        [r,f"{engineering['public_thermal_risk'][r]:.4f}",f"{engineering['public_estimated_temperature_c'][r]:.2f}",f"{engineering['offline_temperature_c'][r]:.2f}",'是' if engineering['remote_temperature_c'][r] is not None else '否'] for r in [64,67,70]],'hotspot-values')
    task_table=table(['专业','完成检查后得到什么','人数','每次服务','最大重访间隔'],[
        [name,measurement,fifo['task_contract'][kind]['inspectors'],f"{fifo['task_contract'][kind]['service_s']:g}秒",f"{fifo['task_contract'][kind]['revisit_limit_s']:g}秒"]
        for kind,name,measurement in [('thermal','热检查','该机柜代表温度'),('electrical','电气检查','该组电气接触温度'),('cooling','制冷检查','该组冷却液流量'),('control','自控检查','传感读数误差（完成校验后）')]], 'task-contract')
    fault_table=table(['过程','种子','目标柜号／设备组','故障开始→结束／秒','热／冷异常段'],[
        [f'{index+1:02d}',row['seed'],f"{row['fault_anchor_rack_index']}号／第{row['fault_pod_index']+1}组",
         f"{row['fault_start_s']:g}→{row['fault_end_s_exclusive']:g}",
         f"{row['anomaly_segments_by_role']['thermal']}／{row['anomaly_segments_by_role']['cooling']}"]
        for index,row in enumerate(method_evidence['primary_processes']['cases'])],'fault-cases')
    substitutions={'QUEUE_TABLE':queue_table,'RETURN_TABLE':return_table,'HOTSPOT_TABLE':hotspot_table,'TASK_TABLE':task_table,'FAULT_TABLE':fault_table,'COMPARISON_TABLE':comparison_table(comparison),
        'VISIT_BUDGET':str(protocol['extra_visit_budget']),
        'GAINED':str(gained),'LOST':str(lost),'NET':str(gained-lost),'MEAN_NET':f"{comp['net_confirmations']['mean']:.2f}",
        'CI_LOW':f"{comp['net_confirmations']['percentile95'][0]:.2f}",'CI_HIGH':f"{comp['net_confirmations']['percentile95'][1]:.2f}"}
    substitutions.update(supplement_substitutions(supplement))
    substitutions.update(supplement_narrative['substitutions'])
    multi_choice=[100*row['choice_sets_with_alternatives']/row['task_choices'] for row in supplement['policy_training_costs']]
    substitutions['PPO_MULTI_CHOICE_RANGE']=f'{min(multi_choice):.2f}%—{max(multi_choice):.2f}%'
    example=next(row for row in gap_diagnosis['changes'] if row['case']['id']=='test04-cooling' and row['model_seed']==271)
    timing_rows=[]
    for direction in ('gained','lost'):
        for row in example[direction]:
            task,kind,start,end=row['key'];values=[]
            for method in ('nominal','cvae'):
                details=row[method];cue=details['cues'][0]['visible_s']
                first=min(e['time_s'] for e in details['nearby_measurements'] if e['time_s']>start)
                values.append(f'{cue:g}→{first:g}秒')
            timing_rows.append([f'{task}号热检查',f'{start:g}—{end:g}秒',*values,'CVAE新增' if direction=='gained' else 'CVAE丢失'])
    substitutions['GAP_TIMING_TABLE']=table(['任务','原评价段','名义FIFO：提示→完成','CVAE-FIFO：提示→完成','确认变化'],timing_rows,'estimation-confirmation-gap')
    source=read('paper/supervisor-report.md').decode('utf-8')
    for key,value in substitutions.items():source=source.replace('{{'+key+'}}',value)
    md=MarkdownIt('commonmark',{'html':True}).enable('table')
    parts=re.split(r'<!-- section:([a-z-]+) -->',source)
    title=md.render(parts[0]);sections=[];navigation=[]
    labels={'overview':'0. 导读概览','model':'1. 设施模型','hotspots':'2. 感知估计','fifo':'3. 巡检决策','comparison':'4. 实验结果','roadmap':'5. 结论规划','appendix':'6. 技术附录'}
    for index in range(1,len(parts),2):
        identity,body=parts[index:index+2]
        body=re.sub(r'\{\{FIGURE:([a-z0-9-]+)\}\}',lambda m:'\n\n'+figure(m[1])+'\n\n',body)
        body=re.sub(r'\{\{PAIR:([a-z0-9-]+),([a-z0-9-]+)\}\}',lambda m:'\n\n<div class="figure-pair">'+figure(m[1])+figure(m[2])+'</div>\n\n',body)
        rendered=md.render(body)
        def optional_case(match):
            return '<details class="case-appendix"><summary>展开技术细节：计算、执行记录、规则诊断与文献图</summary><div class="appendix-body">'+match[1]+'</div></details>'
        rendered=re.sub(r'<!-- optional-case:start -->(.*?)<!-- optional-case:end -->',optional_case,rendered,flags=re.S)
        assert '{{' not in rendered
        sections.append('<section id="'+identity+'" data-report-section="'+identity+'">'+rendered+'</section>')
        navigation.append('<a href="#'+identity+'">'+labels[identity]+'</a>')
    content=title+'<nav class="contents" aria-label="报告目录">'+''.join(navigation)+'</nav>'+''.join(sections)
    # Source links remain useful when only this one HTML file is shared.
    content=re.sub(r'href="([^"]+)"',lambda m:'href="'+resolve_source_link(m[1])+'"',content)
    template=read('paper/briefing-template.html').decode('utf-8')
    output=template.replace('{{REPORT_BODY}}',content)
    assert '{{' not in output and '<script' not in output.lower() and 'data-stage-' not in output
    destination=PAPER/'supervisor-briefing.html';destination.write_text(output,encoding='utf-8',newline='\n')
    text_export=export_review_text(source,figure_notes,labels,PAPER,resolve_source_link,hashlib.sha256(destination.read_bytes()).hexdigest())
    data_path=PAPER/'generated/supervisor-report-data.json';write_json(data_path,data)
    write_json(PAPER/'generated/briefing-chart-data.json',data)
    core=re.sub(r'<details\b.*?</details>','',content,flags=re.S)
    main_figures=re.findall(r'<figure id="figure-([^"]+)"',core)
    all_figures=re.findall(r'<figure id="figure-([^"]+)"',content)
    assert len(all_figures)==len(set(all_figures))==len(drawings)
    manifest={'version':10,'mode':'self_reading_report','previous_version':'17e1f7a3e1fdda5c739bd608050dbe26d3af966e','animations':False,'presenter_controls':False,
        'main_figure_ids':main_figures,'appendix_figure_ids':[name for name in all_figures if name not in main_figures],
        'sections':list(labels),'primary_processes':12,'primary_condition_count':48,
        'primary_anomaly_segments':supplement['primary_aggregates']['nominal_tour']['total_unique_anomaly_segments'],
        'historical_primary_anomaly_segments':89,'historical_main_results':main_results,'main_results':supplement['primary_aggregates'],
        'engineering_frame_scope':engineering['kind'],'fifo_example_case':fifo['case'],
        'new_environment_evaluations':supplement['environment_attempts'],'new_physical_scale_runs':supplement['physical_scale_attempts'],
        'test_episode_count':1080,'independent_test_seed_blocks':12,'unique_test_physical_processes':60,
        'neural_estimator_predictions':data['neural_estimator_predictions'],
        'trained_checkpoints':9,'external_language_model_calls':0,'html_sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),
        'data_sha256':hashlib.sha256(data_path.read_bytes()).hexdigest(),'figure_sha256':figure_hashes,'source_sha256':SOURCES,
        'text_export':text_export,'posthoc_estimation_confirmation_diagnosis':gap_diagnosis['counts'],
        'scope':'Report derivation and source identity. It does not replace independent visual/source verification.'}
    write_json(PAPER/'generated/briefing-manifest.json',manifest)
    print(f'Built self-reading static report: {len(labels)} visible sections, {len(drawings)} source-backed diagrams, no animation or presenter controls.')


if __name__=='__main__':main()
