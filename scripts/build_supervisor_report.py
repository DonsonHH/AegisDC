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


def table(headers,rows,kind):
    cell=lambda tag,value:f'<{tag}>'+html.escape(str(value))+f'</{tag}>'
    return '<div class="table-wrap"><table data-table="'+kind+'"><thead><tr>'+''.join(cell('th',v) for v in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(cell('td',v) for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'


def main():
    for source in ['scripts/build_supervisor_report.py','scripts/report_diagrams.py','scripts/briefing_diagrams.py']:
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
    assert kinds['counts']=={'thermal':77,'cooling':12}
    archive=load('paper/briefing-history/2db2adf1/baseline.json')
    for identity in archive['files'].values():assert hashlib.sha256(read(identity['archived_as'])).hexdigest()==identity['sha256']
    read('paper/research/mentor-engineering-reference-20261103.md')
    original=read('paper/research/original-paper-metrics-20261103.md').decode('utf-8')
    read('paper/model-appendix.md')
    read('paper/mentor-requests.md')
    for source in ['src/patrol_rsi/risk_response.py','src/patrol_rsi/active_inspection.py','src/patrol_rsi/facility.py','src/patrol_rsi/facility_observation.py','src/patrol_rsi/aisles.py']:
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
        row={'rule_sha256':proposal['rule_sha256'],'confirmed':main_results['fifo']['confirmed']+proposal['aggregate']['net']}
        if row['rule_sha256'] in registered:assert registered[row['rule_sha256']]==row
        registered[row['rule_sha256']]=row
    assert len(registered)==9 and max(row['confirmed'] for row in registered.values())==60
    assert [(r['rule_sha256'],r['confirmed']) for r in registered.values()]==[(r['rule_sha256'],r['confirmed']) for r in legacy['registered_rules']]
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
          'primary_anomaly_kinds':kinds['counts'],
          'paper_scores':paper,'paper_metric_scope':'Original water-task score; not directly comparable to professional anomaly confirmation.',
          'new_environment_evaluations':0,'new_research_model_calls':0,'new_training':0}
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
    drawings=build_report_diagrams(data,inherited)
    folder=PAPER/'figures/supervisor-report';folder.mkdir(parents=True,exist_ok=True)
    figure_hashes={}
    for name,drawing in drawings.items():
        ET.fromstring(drawing)
        path=folder/(name+'.svg');path.write_text(drawing,encoding='utf-8',newline='\n')
        figure_hashes[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    figure_notes={
        'model':'计算职责示意；CDU、泵阀与仪表在工程设备中可集成。当前参数仍是合成设定。',
        'public-risk':'已有工程回看：固定巡回，500秒。风险为公开估计的合成代理，不是概率。',
        'offline-temperature':'同一工程过程的事后内部温度，不是现场空气实测；未传入在线选择。',
        'fifo-cycle':'程序只从该执行者自己的合规请求中选择；移动和测量不会被新提示中断。',
        'inspection-architecture':'根据本项目已实现接口重绘总体架构；上方在线决策只用公开信息，下方真值与日志用于事后评分。',
        'fifo-actions':'主验证包p01-coupled的实际记录；色块宽度按移动＋服务的仿真耗时绘制。',
        'outcome-costs':'本项目12个主过程的FIFO相对Tour比较；区间、代价与探索性门槛均来自封存记录。',
        'registered-rules':'本项目已有开发负结果，按规则内容去重保留9条；没有新增仿真、训练或模型调用。',
        'original-paper-scores':'原文表8／9均值±95%CI。两种Greedy的藻华终值相同，按原表保留。',
        'confirmations':'当前机房任务：12个主过程，共89段异常；三列为各策略的有效确认量。',
        'paired-net':'过程01—12对应p00—p11；11个净增、1个不变，不是新增独立样本。',
        'execution-chain':'p02-coupled，同一巡检员1，关键任务完成链；中间部分访问省略。',
        'task-17':'17号665秒派出的是例行访问；其公开风险685秒才出现。',
        'task-21':'21号650秒见风险，705秒额外派单，725秒完成，异常在710秒已结束。',
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
    substitutions={'QUEUE_TABLE':queue_table,'RETURN_TABLE':return_table,'HOTSPOT_TABLE':hotspot_table,'TASK_TABLE':task_table,
        'VISIT_BUDGET':str(protocol['extra_visit_budget']),
        'GAINED':str(gained),'LOST':str(lost),'NET':str(gained-lost),'MEAN_NET':f"{comp['net_confirmations']['mean']:.2f}",
        'CI_LOW':f"{comp['net_confirmations']['percentile95'][0]:.2f}",'CI_HIGH':f"{comp['net_confirmations']['percentile95'][1]:.2f}"}
    source=read('paper/supervisor-report.md').decode('utf-8')
    for key,value in substitutions.items():source=source.replace('{{'+key+'}}',value)
    md=MarkdownIt('commonmark',{'html':True}).enable('table')
    parts=re.split(r'<!-- section:([a-z-]+) -->',source)
    title=md.render(parts[0]);sections=[];navigation=[]
    labels={'overview':'要求回应','model':'模型与规模','hotspots':'风险热点','fifo':'FIFO流程','results':'当前结果','comparison':'原文指标与对照','sources':'来源'}
    for index in range(1,len(parts),2):
        identity,body=parts[index:index+2]
        body=re.sub(r'\{\{FIGURE:([a-z0-9-]+)\}\}',lambda m:'\n\n'+figure(m[1])+'\n\n',body)
        body=re.sub(r'\{\{PAIR:([a-z0-9-]+),([a-z0-9-]+)\}\}',lambda m:'\n\n<div class="figure-pair">'+figure(m[1])+figure(m[2])+'</div>\n\n',body)
        rendered=md.render(body)
        def optional_case(match):
            detail=re.sub(r'<h3>.*?</h3>','',match[1],count=1,flags=re.S)
            return '<details class="case-appendix"><summary>补充案例：同一巡检员为什么有得也有失（可展开）</summary><div class="appendix-body">'+detail+'</div></details>'
        rendered=re.sub(r'<!-- optional-case:start -->(.*?)<!-- optional-case:end -->',optional_case,rendered,flags=re.S)
        assert '{{' not in rendered
        sections.append('<section id="'+identity+'" data-report-section="'+identity+'">'+rendered+'</section>')
        navigation.append('<a href="#'+identity+'">'+labels[identity]+'</a>')
    content=title+'<nav class="contents" aria-label="报告目录">'+''.join(navigation)+'</nav>'+''.join(sections)
    # Source links remain useful when only this one HTML file is shared.
    def link(match):
        target=match[1]
        if target.startswith(('#','https:','http:','data:')):return match[0]
        path=(PAPER/target).resolve().relative_to(ROOT).as_posix()
        if path.endswith('.html'):path=path[:-5]+'.md'
        reference=BRANCH if '/research/' in path else BASE
        return 'href="'+REMOTE+reference+'/'+path+'"'
    content=re.sub(r'href="([^"]+)"',link,content)
    template=read('paper/briefing-template.html').decode('utf-8')
    output=template.replace('{{REPORT_BODY}}',content)
    assert '{{' not in output and '<script' not in output.lower() and 'data-stage-' not in output
    destination=PAPER/'supervisor-briefing.html';destination.write_text(output,encoding='utf-8',newline='\n')
    data_path=PAPER/'generated/supervisor-report-data.json';write_json(data_path,data)
    write_json(PAPER/'generated/briefing-chart-data.json',data)
    manifest={'version':4,'mode':'self_reading_report','previous_version':BASE,'animations':False,'presenter_controls':False,
        'sections':list(labels),'primary_processes':12,'primary_anomaly_segments':89,'main_results':main_results,
        'engineering_frame_scope':engineering['kind'],'fifo_example_case':fifo['case'],'new_environment_evaluations':0,
        'new_research_model_calls':0,'new_training':0,'html_sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),
        'data_sha256':hashlib.sha256(data_path.read_bytes()).hexdigest(),'figure_sha256':figure_hashes,'source_sha256':SOURCES,
        'scope':'Report derivation and source identity. It does not replace independent visual/source verification.'}
    write_json(PAPER/'generated/briefing-manifest.json',manifest)
    print(f'Built self-reading static report: 7 visible sections, {len(drawings)} source-backed diagrams, no animation or presenter controls.')


if __name__=='__main__':main()
