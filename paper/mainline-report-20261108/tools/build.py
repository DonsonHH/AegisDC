"""Build a concise source-bound baseline report from saved results only."""
import base64,csv,hashlib,html,io,json,re,subprocess,sys,traceback
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'paper/mainline-report-20261108'
CUTOFF='2ba22965119615b157bb7f3a302875bf05e4989b'
git=lambda *a:subprocess.check_output(['git',*a],cwd=ROOT)
sha=lambda b:hashlib.sha256(b).hexdigest()
inputs={}

def source(name):
    raw=(ROOT/name).read_bytes();assert raw==git('cat-file','blob',CUTOFF+':'+name),name
    inputs[name]=dict(sha256=sha(raw),bytes=len(raw));return raw

def save(name,value):
    path=OUT/name;path.parent.mkdir(parents=True,exist_ok=True)
    raw=value if isinstance(value,bytes) else (json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    path.write_bytes(raw)

def table(headers,rows):return '\n'.join(['|'+'|'.join(headers)+'|','|'+'|'.join(['---']*len(headers))+'|',*['|'+'|'.join(map(str,r))+'|' for r in rows]])

def inline(text):
    text=html.escape(text)
    text=re.sub(r'`([^`]+)`',r'<code>\1</code>',text)
    text=re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',text)
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',r'<a href="\2">\1</a>',text)

def markup(text,figures,cards,downloads):
    output=[];paragraph=[];lines=text.splitlines();i=0;section=0;appendix=False
    def flush():
        if paragraph:output.append('<p>'+inline(' '.join(paragraph))+'</p>');paragraph.clear()
    while i<len(lines):
        line=lines[i].strip()
        if not line:flush();i+=1;continue
        if line.startswith('# '):flush();output.append('<h1>'+inline(line[2:])+'</h1>')
        elif line.startswith('## '):
            flush();section+=1
            if line[3:].startswith('附录'):
                output.append(f'<details id="section-{section}" class="appendix"><summary>{inline(line[3:])}</summary>');appendix=True
            else:output.append(f'<h2 id="section-{section}">{inline(line[3:])}</h2>')
        elif line=='{{metrics}}':flush();output.append(cards)
        elif line=='{{downloads}}':flush();output.append(downloads)
        elif line.startswith('{{figure:'):
            flush();output.append(figures[line[9:-2]])
        elif line.startswith('|'):
            flush();rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                cells=[c.strip() for c in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r'[-: ]+',c) for c in cells):rows.append(cells)
                i+=1
            output.append('<div class="table-scroll" tabindex="0" aria-label="数据对照表，可横向滚动"><table><thead><tr>'+''.join('<th>'+inline(c)+'</th>' for c in rows[0])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+inline(c)+'</td>' for c in row)+'</tr>' for row in rows[1:])+'</tbody></table></div>');continue
        else:paragraph.append(line)
        i+=1
    flush()
    if appendix:output.append('</details>')
    return '\n'.join(output)

def build():
    author=git('rev-parse','HEAD').decode().strip();content=(OUT/'content.md').read_bytes()
    assert git('cat-file','blob',author+':paper/mainline-report-20261108/content.md')==content
    assert git('cat-file','blob',author+':paper/mainline-report-20261108/tools/build.py')==Path(__file__).read_bytes()
    history=OUT/'builds';history.mkdir(exist_ok=True);index=len(list(history.glob('build-*.start.json')))+1
    save(f'builds/build-{index:02}.start.json',dict(source=author,scientific_cutoff=CUTOFF,tool_sha256=sha(Path(__file__).read_bytes()),content_sha256=sha(content),new_project_calls=0))
    try:
        primary=json.loads(source('evidence/mainline/research/34-paired-analysis/results.json'))
        ablation=json.loads(source('evidence/mainline/research/35-ablation/results.json'))
        robust=json.loads(source('evidence/mainline/research/36-robustness/analysis-01/results.json'))
        protocol=json.loads(source('docs/mainline/30-comparison-protocol-v1.json'))
        model=json.loads(source('configs/full-facility-mainline-reserve-v6.json'))
        readouts=json.loads(source('evidence/mainline/engineering/pre36-readout/readout-01/method-summary.json'))
        phases=[]
        for label,folder in [('开发','31-development'),('主要确认','33-confirmation'),('机制消融','35-ablation'),('稳健性','36-robustness')]:
            receipt=json.loads(source('evidence/mainline/research/'+folder+'/capture-01/receipt.json'));total=receipt['total']
            assert total['failed']==total['interrupted']==total['unrun']==0
            phases.append(dict(label=label,**total))
        assert sum(p['completed'] for p in phases)==180 and sum(p['charged_simulated_s'] for p in phases)==1800
        assert len(model['domains'])==8 and len(model['entities'])==45 and len(model['parameters'])==113
        assert primary['status']=='NO_PRACTICAL_GAIN' and primary['mean_service_delta_s']==.03515625
        assert abs(robust['mean_over_eight_designed_worlds_service_delta_s']+.084375)<1e-12
        confirmation={r['arm']:r for r in readouts if r['phase']=='confirmation'}
        assert confirmation['evidence_consistent_contingent']['historical_named_threshold_findings']==9
        assert confirmation['one_observation_lookahead']['historical_named_threshold_findings']==12
        assert all(r['endpoint_current_named_threshold_findings']==0 for r in confirmation.values())
        source('docs/meetings/2026-11-03-research-reset.md');source('docs/mainline/audits/20261108-pre36/audit-report.md')
        source('evidence/mainline/research/36-robustness/README.md');source('paper/mentor-review-20261108/claims.json')
        save('data/primary.json',source('evidence/mainline/research/34-paired-analysis/results.json'))
        save('data/ablation.json',source('evidence/mainline/research/35-ablation/results.json'))
        save('data/robustness.json',source('evidence/mainline/research/36-robustness/analysis-01/results.json'))
        save('data/robustness-paired.csv',source('evidence/mainline/research/36-robustness/analysis-01/paired.csv'))
        params=source('paper/mentor-review-20261108/model-parameters.csv');assert len(list(csv.DictReader(io.StringIO(params.decode('utf-8-sig')))))==113
        save('data/model-parameters.csv',params)
        save('data/metric-coverage.json',source('evidence/mainline/engineering/pre36-readout/readout-01/metric-coverage.json'))
        figure_specs=[
          ('facility','mentor-facility-systems','供电、有限后备、湖侧与设备侧排热，以及关键服务共同瓶颈。'),
          ('architecture','35-facility-and-evaluation-architecture','完整设施与证据限定决策、专业执行和独立评价的关系；后台状态不直接提供给策略。'),
          ('value','mentor-value-frozen','100秒有限工程价值演算：预测后果与人工代价分开，不属于注册效果样本。'),
          ('loop','27-actual-loop','实际工程闭环：服务4秒自动恢复、清滤6秒完成、8.5秒验证关闭。'),
          ('confirmation','34-confirmation-paired-service-cost','16个独立确认工况的服务差与实际代价；保留所有正、负和零差值。'),
          ('families','34-confirmation-family-effects','四个故障族的方向不同；单一平均值不能代替失效条件。'),
          ('ablation','35-ablation-service-cost','规划者信息/选项消融，实际设施和执行能力保持；服务与代价分列。'),
          ('robustness','36-robustness-service-cost','四个配对区组。服务差=参照−候选，正值较好；人工差=候选−参照，负值表示减少。')]
        figure_html={};figure_md={};figure_index=[]
        for number,(key,name,caption) in enumerate(figure_specs,1):
            parent='evidence/mainline/research/36-robustness/figures-v3' if key=='robustness' else 'paper/mentor-review-20261108/figures'
            png=source(parent+'/'+name+'.png');svg=source(parent+'/'+name+'.svg');stem=f'{number:02}-{key}'
            save('figures/'+stem+'.png',png);save('figures/'+stem+'.svg',svg)
            uri='data:image/png;base64,'+base64.b64encode(png).decode();svguri='data:image/svg+xml;base64,'+base64.b64encode(svg).decode()
            figure_html[key]=f'<figure id="figure-{number}"><div class="figure-scroll"><img src="{uri}" alt="{html.escape(caption)}" loading="lazy"></div><figcaption>图{number}　{html.escape(caption)} <a href="{uri}" download="{stem}.png">PNG</a> · <a href="{svguri}" download="{stem}.svg">可编辑SVG</a></figcaption></figure>'
            figure_md[key]=f'![图{number}：{caption}](figures/{stem}.png)\n\n图{number}　{caption}'
            figure_index.append(dict(id=key,number=number,caption=caption,input=parent+'/'+name,png_sha256=sha(png),svg_sha256=sha(svg)))
        tables={}
        tables['facility']=table(['对象','实际模型内容'],[
            ['供配电 / 后备能源','容量与功率分配、整流/直流支路、有限储能、发电与切换'],
            ['设施冷却 / 设备冷却与环境','泵、滤阻、阀、换热、水与相变状态、房间/泄漏影响'],
            ['计算网络存储 / 控制监测','外生需求、实际执行功率与发热、共同服务瓶颈、本地保护'],
            ['空间保障 / 异质人员工具','独立访问图、访问与安全限制、资质、移动、占用、等待和协作'],
            ['模型规模','8个行为域、45个实体、113项参数；四图共用身份']])
        tables['evidence']=table(['信息来源','决策使用规则'],[['资产/历史、报障/工单','保留来源、对象、获取时间和质量说明'],['稀疏固定测点、现场手持结果','按观测与到达时刻开放；未覆盖和未到达保持未知'],['复制/相关、过期/冲突记录','共享来源不重复乘证据；历史读数与当前授权分开']])
        tables['primary']=table(['指标及差值定义','16工况平均值','解释'],[
            ['服务缺额：参照−候选',f"{primary['mean_service_delta_s']:.8f} 秒",f"未达{protocol['comparison']['minimum_worthwhile_gain_s']}秒门槛"],
            ['人工：候选−参照',f"{primary['mean_extra_paid_person_s']:.5f} 人秒",'平均减少；不等同服务增益'],
            ['行走 / 工具：候选−参照',f"{primary['mean_extra_travel_person_s']:.2f} 人秒 / {primary['mean_extra_tool_occupation_s']:.6f} 工具秒",'量纲分列，不混成总分'],
            ['实际硬约束违反','0','针对本次已记录规则，不作现场安全保证']])
        labels={'without_nonfixed_context':'屏蔽非固定线索','without_dependency_context':'屏蔽依赖关系/后果','without_joint_crew_planning':'屏蔽联合团队选项'}
        tables['ablation']=table(['屏蔽项','缺额：屏蔽−完整（秒）','人工：完整−屏蔽（人秒）'],[[labels[k],f"{v['mask_minus_full_deficit_s']:+.6f}",f"{v['full_minus_mask_paid_person_s']:+.5f}"] for k,v in ablation['summary'].items()])
        names={'load-level':'需求0.75→1.25','sensor-coverage':'固定表计启用→停用','reserve-path':'UPS在役→下线','model-error':'预测容量0.75→1'}
        meanings={'load-level':'高载候选较差0.30秒；人工相同','sensor-coverage':'服务相同；1.25人秒节省消失','reserve-path':'两法绝对缺额均增至7.375秒','model-error':'两法共同改变选择，实际容量不变'}
        tables['robustness']=table(['条件变化','服务差：参照条件→变体（秒）','观察'],[[names[c['family']],f"{c['reference']['delta_service_s']:.3f} → {c['perturbed']['delta_service_s']:.3f}",meanings[c['family']]] for c in robust['contrasts']])
        tables['alignment']=table(['会后要求','本轮回答','状态'],[['按问题触发','选择检查、处置或暂缓；固定周期只作对照','方向符合'],['稀疏多源信息','已有测点、历史/人工与现场结果统一记时和来源','有限接口已验证'],['完整设施','八域实际耦合；四图和共同瓶颈进入执行','合成范围完成'],['模型先于风险','守恒/容量/数值见证，情景/后果与检查价值演算','未现场标定'],['AI/RSI后置','注册策略没有LLM或训练调用','增量未测'],['业务价值','服务、人力、工具、硬约束分别评价','误报/漏报/预防/正式关闭未测'],['可追溯方法','冻结协议、版本、原件与失败；01–35修正及36新完整守卫','证据边界明确']])
        purpose=['开发诊断；6工况×6方法','主要确认；16独立工况×6方法','信息/选项消融；8工况×4视图','4配对区组×2条件×2方法']
        tables['runs']=table(['阶段','实际运行','仿真秒','用途'],[[p['label'],p['completed'],p['charged_simulated_s'],purpose[i]] for i,p in enumerate(phases)])
        cards=f'<div class="metrics"><div><span>主要确认平均服务改善</span><strong>{primary["mean_service_delta_s"]:.4f}<small>秒</small></strong></div><div><span>预定实际收益门槛</span><strong>{protocol["comparison"]["minimum_worthwhile_gain_s"]:.2f}<small>秒</small></strong></div><div><span>平均人工差额</span><strong>{primary["mean_extra_paid_person_s"]:.4f}<small>人秒</small></strong></div></div>'
        downloadable=[('primary.json','主要确认原始分析JSON'),('ablation.json','消融原始分析JSON'),('robustness.json','稳健性分析JSON'),('robustness-paired.csv','稳健性配对CSV'),('model-parameters.csv','113项参数CSV'),('metric-coverage.json','18项指标状态JSON')]
        links=[];md_links=[]
        for name,label in downloadable:
            raw=(OUT/'data'/name).read_bytes();mime='text/csv' if name.endswith('.csv') else 'application/json'
            links.append(f'<a class="download" href="data:{mime};base64,{base64.b64encode(raw).decode()}" download="{name}">{label}</a>');md_links.append(f'[{label}](data/{name})')
        text=content.decode()
        for key,value in tables.items():text=text.replace('{{table:'+key+'}}',value)
        body=markup(text,figure_html,cards,'<div class="downloads">'+''.join(links)+'</div>')
        md=text.replace('{{metrics}}','180次注册运行 · 8个行为域 · 主要确认16个独立工况').replace('{{downloads}}',' · '.join(md_links))
        for key,value in figure_md.items():md=md.replace('{{figure:'+key+'}}',value)
        save('report.md',md.encode())
        css=(OUT/'tools/report.css').read_text(encoding='utf-8')
        titles=['设施模型','风险与任务','实际执行','主要结果','消融与稳健性','会后要求','附录与数据']
        nav=''.join(f'<a href="#section-{i}">{title}</a>' for i,title in enumerate(titles,1))
        page='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AegisDC · 会后研究报告</title><style>'+css+'</style></head><body><header><div class="brand">AegisDC <span>基线研究 · 可复算</span></div><nav aria-label="报告目录">'+nav+'</nav></header><main>'+body+'</main><footer>数据截点 '+CUTOFF[:8]+' · 合成研究设施 · 现场标定PENDING</footer></body></html>'
        save('AegisDC-会后研究报告.html',page.encode())
        facts=dict(schema='aegisdc-baseline-report-facts-v1',source_cutoff=CUTOFF,phases=phases,total_runs=180,total_simulated_s=1800,
            primary={k:primary[k] for k in ['status','planned_denominator','mean_service_delta_s','mean_extra_paid_person_s','mean_extra_travel_person_s','mean_extra_tool_occupation_s']},
            ablation_summary=ablation['summary'],robustness_paired=robust['paired'],robustness_mean=robust['mean_over_eight_designed_worlds_service_delta_s'],
            parameter_count=113,entity_count=45,domain_count=8,formal_closure='NOT_EVALUATED',generic_false_miss_rates='NOT_OPERATIONALIZED',prevention='NOT_TESTED',AI_RSI='NOT_MEASURED',new_project_calls=0)
        save('facts.json',facts);save('figure-sources.json',figure_index)
        save('source-manifest.json',dict(scientific_cutoff=CUTOFF,authoring_source=author,inputs=inputs,
            tools={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in [Path(__file__),OUT/'tools/report.css',OUT/'content.md']}))
        assert not any(n.startswith('aegis_dc') for n in sys.modules)
        save(f'builds/build-{index:02}.terminal.json',dict(status='PASS_SAVED_REPORT_BUILD',source=author,figures=8,downloads=6,new_physical_calls=0,new_inference=0,new_trials=0,
            html_sha256=sha((OUT/'AegisDC-会后研究报告.html').read_bytes()),markdown_sha256=sha((OUT/'report.md').read_bytes())))
        return dict(status='PASS_SAVED_REPORT_BUILD',figures=8,data_downloads=6,total_runs=180)
    except BaseException as exc:
        save(f'builds/build-{index:02}.failure.txt',traceback.format_exc().encode());save(f'builds/build-{index:02}.terminal.json',dict(status='FAILED_REPORT_BUILD',source=author,error_type=type(exc).__name__,error=str(exc),new_trials=0));raise

if __name__=='__main__':print(json.dumps(build(),ensure_ascii=False))
