"""Build the source-backed facility case reading pack, without simulation/training.

Authoring dependencies match the existing paper toolchain: markdown-it-py and
latex2mathml. Generated HTML/SVG/CSV and the verifier require no browser CDN.
"""
from __future__ import annotations

import base64
from collections import Counter
import csv
import hashlib
import html
import importlib.metadata
import io
import json
from pathlib import Path
import re
import sys
import unicodedata

ROOT=Path(__file__).resolve().parents[1]
DEPS=ROOT/'.work/paper-writing-deps'
if DEPS.is_dir():sys.path.insert(0,str(DEPS))
from markdown_it import MarkdownIt
from latex2mathml.converter import convert

PACK=ROOT/'docs/research/20261104/facility-cases'
EVIDENCE=ROOT/'evidence/facility-case-models-20261104'
STATUS={
    'published':('公开资料','#196572','#edf7f6',''),
    'design':('设计资料','#376b32','#f1f8ed',''),
    'model':('发表模型','#536494','#f1f3fa','5 3'),
    'vendor':('厂家声明','#74508f','#f7f1fa',''),
    'assumption':('研究提议','#a36324','#fff5e8','7 5'),
    'missing':('待补数据','#737b85','#f5f6f7','2 5'),
}
COLORS={'power':'#355ab0','heat':'#bd4c37','fluid':'#20788b','signal':'#8b662e','control':'#865698'}
AVAIL={'documented':'有来源记录','missing':'缺失 null','partial':'部分缺失','conflicting':'口径待对齐'}
BASIS_NAMES={'published_site':'公开站点描述','published_model':'发表模型','published_hardware':'官方硬件规格',
             'design_or_capability':'设计/能力','design_capacity':'设计能力','commissioning':'调试记录',
             'model_proposal':'研究提议','official_indexed_text':'官方索引正文'}
MD=MarkdownIt('commonmark',{'html':True}).enable('table')

def esc(value):return html.escape(str(value),quote=True)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(value,encoding='utf-8',newline='\n')
def units(text):return sum(1 if unicodedata.east_asian_width(c) in 'WF' else .57 for c in text)

def svg_diagram(diagram):
    width,height=diagram['width'],diagram['height']
    nodes={n['id']:n for n in diagram['nodes']}
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title-{diagram["id"]} desc-{diagram["id"]}">',
           f'<title id="title-{diagram["id"]}">{esc(diagram["title"])}</title>',f'<desc id="desc-{diagram["id"]}">{esc(diagram["readout"])}</desc>',
           '<defs>']
    for kind,color in COLORS.items():
        parts.append(f'<marker id="arrow-{diagram["id"]}-{kind}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8Z" fill="{color}"/></marker>')
    parts+=['</defs>','<rect width="100%" height="100%" fill="#fff"/>',
            '<style>text{font-family:"Microsoft YaHei","Noto Sans CJK SC",Arial,sans-serif} .edge-label{font-size:12px;font-weight:600;paint-order:stroke;stroke:#fff;stroke-width:5;stroke-linejoin:round}</style>',
            f'<text x="32" y="37" font-size="23" font-weight="700" fill="#142938">{esc(diagram["title"])}</text>',
            f'<text x="32" y="65" font-size="15" fill="#536471">{esc(diagram["subtitle"])}</text>']
    labels=[]
    def port(n,side):
        return {'r':(n['x']+n['w'],n['y']+n['h']/2),'l':(n['x'],n['y']+n['h']/2),
                't':(n['x']+n['w']/2,n['y']),'b':(n['x']+n['w']/2,n['y']+n['h'])}[side]
    for index,edge in enumerate(diagram['edges']):
        start=port(nodes[edge['from']],edge['ports'][0]);end=port(nodes[edge['to']],edge['ports'][1])
        points=[start,*edge.get('via',[]),end]
        color=COLORS[edge['kind']];dash=STATUS[edge['status']][3]
        path='M'+' L'.join(f'{x},{y}' for x,y in points)
        parts.append(f'<path data-edge="{index}" data-status="{edge["status"]}" data-from="{edge["from"]}" data-to="{edge["to"]}" d="{path}" fill="none" stroke="{color}" stroke-width="2.5" stroke-dasharray="{dash}" marker-end="url(#arrow-{diagram["id"]}-{edge["kind"]})"><title>{esc(edge["label"])} · {STATUS[edge["status"]][0]} · {esc(" / ".join(edge["source_refs"]))}</title></path>')
        if edge['label']:
            a,b=max(zip(points,points[1:]),key=lambda pair:(pair[1][0]-pair[0][0])**2+(pair[1][1]-pair[0][1])**2)
            cx,cy=(a[0]+b[0])/2,(a[1]+b[1])/2
            horizontal=abs(b[0]-a[0])>abs(b[1]-a[1])
            text=edge['label'];chunks=[];chunk=''
            limit=max(4.3,abs(b[0]-a[0])/12-1) if horizontal else 12
            for char in text:
                if units(chunk+char)>limit and chunk:chunks.append(chunk);chunk=''
                chunk+=char
            if chunk:chunks.append(chunk)
            for line,chunk in enumerate(chunks):
                x,y=(cx,cy-12-(len(chunks)-1-line)*15) if horizontal else (cx+10,cy+(line-(len(chunks)-1)/2)*15)
                labels.append(f'<text class="edge-label" x="{x}" y="{y}" text-anchor="{"middle" if horizontal else "start"}" fill="{color}">{esc(chunk)}</text>')
    for n in nodes.values():
        status,color,fill,dash=STATUS[n['status']]
        parts.append(f'<g data-node="{n["id"]}" data-status="{n["status"]}"><title>{esc(" / ".join(n["label"]))} · {status} · {esc(" / ".join(n["source_refs"]))}</title>')
        parts.append(f'<rect x="{n["x"]}" y="{n["y"]}" width="{n["w"]}" height="{n["h"]}" rx="10" fill="{fill}" stroke="{color}" stroke-width="1.7" stroke-dasharray="{dash}"/>')
        parts.append(f'<text x="{n["x"]+15}" y="{n["y"]+21}" font-size="11.5" font-weight="700" fill="{color}">{status}</text>')
        for i,line in enumerate(n['label']):
            font=min(17 if i==0 else 14.7,(n['w']-28)/max(units(line),1))
            parts.append(f'<text x="{n["x"]+14}" y="{n["y"]+45+23*i}" font-size="{font:.2f}" font-weight="{650 if i==0 else 400}" fill="#243644">{esc(line)}</text>')
        parts.append('</g>')
    parts.extend(labels)
    # The legend describes epistemic status. Carrier colors are independently named.
    for i,(key,(label,color,fill,dash)) in enumerate(STATUS.items()):
        x=32+i*198
        parts.append(f'<path d="M{x},{height-101}h25" stroke="{color}" stroke-width="2.5" stroke-dasharray="{dash}"/><text x="{x+32}" y="{height-96}" font-size="13.3" fill="#475966">{label}</text>')
    for i,note in enumerate(diagram['notes']):
        parts.append(f'<text x="32" y="{height-65+i*23}" font-size="14" fill="#526471">{esc(note)}</text>')
    parts.append('</svg>')
    return '\n'.join(parts)

def markdown(text):
    formulas=[]
    def replace(match):
        formula=match.group(1).strip()
        converted=convert(formula,display='block')
        formulas.append(converted)
        return f'\n\n<div class="equation">{converted}</div>\n\n'
    rendered=MD.render(re.sub(r'\$\$(.*?)\$\$',replace,text,flags=re.S))
    rendered=re.sub(r'<table>',r'<div class="table-scroll"><table>',rendered)
    rendered=rendered.replace('</table>','</table></div>')
    return rendered,len(formulas)

def csv_text(case):
    stream=io.StringIO(newline='')
    fields=['id','name','reported_text','unit','availability','basis','evidence','model_use_or_gap','calibration_use']
    writer=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n',extrasaction='ignore')
    writer.writeheader()
    for parameter in case['parameters']:writer.writerow(parameter)
    return stream.getvalue()

def md_table(headers,rows):
    def safe(value):return str(value).replace('|','\\|').replace('\n',' ')
    return '\n'.join(['|'+'|'.join(headers)+'|','|'+'|'.join(['---']*len(headers))+'|',*['|'+'|'.join(safe(v) for v in row)+'|' for row in rows]])

def source_links(case,refs):
    return ' '.join(f'<a href="#src-{ref}">{ref}</a>' for ref in refs)

def readable(value):
    text=str(value)
    for key,name in BASIS_NAMES.items():text=text.replace('`'+key+'`',name)
    return MD.renderInline(text.replace('missing','未取得'))

def parameter_table(case):
    rows=[]
    for p in case['parameters']:
        badge=f'<span class="status {p["availability"]}">{AVAIL[p["availability"]]}</span>'
        rows.append(f'<tr data-availability="{p["availability"]}" id="param-{p["id"]}"><th scope="row">{esc(p["name"])}<small>{esc(p["id"])}</small></th><td>{badge}<br>{readable(p["reported_text"])}</td><td>{esc(p["unit"])}</td><td>{readable(p["evidence"])}<br>{source_links(case,p["source_refs"])}</td><td>{readable(p["model_use_or_gap"])}</td></tr>')
    return '<div class="table-scroll"><table class="parameters"><thead><tr><th>参数 / 量</th><th>公开原值 / 缺值</th><th>单位</th><th>性质与出处</th><th>用途 / 缺口影响</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'

def figure_html(diagram,svg):
    return f'<figure id="fig-{diagram["id"]}"><div class="figure-top"><span class="eyebrow">ARCHITECTURE {diagram["id"][:2]}</span><button class="zoom" data-figure="{diagram["id"]}" type="button">放大查看 ↗</button></div><div class="diagram">{svg}</div><figcaption>{esc(diagram["readout"])}</figcaption></figure>'

def main():
    book=json.loads((PACK/'casebook.json').read_text(encoding='utf-8'))
    css=(ROOT/'scripts/facility_cases_report.css').read_text(encoding='utf-8')
    javascript=(ROOT/'scripts/facility_cases_report.js').read_text(encoding='utf-8')
    diagrams=[d for c in book['cases'] for d in c['diagrams']]+book['shared_diagrams']
    svgs={d['id']:svg_diagram(d) for d in diagrams}
    for key,svg in svgs.items():write(PACK/'figures'/f'{key}.svg',svg+'\n')
    csvs={c['id']:csv_text(c) for c in book['cases']}
    for key,value in csvs.items():write(PACK/'parameters'/f'{key}.csv','\ufeff'+value)
    equations,formula_count=markdown((PACK/'state-equations.md').read_text(encoding='utf-8'))
    intro=[];case_sections=[];all_sources=[]
    case_summaries=[]
    for c in book['cases']:
        counts=Counter(p['availability'] for p in c['parameters'])
        intro.append(f'<a class="case-card" href="#{c["id"]}"><span class="eyebrow">{esc(c["id"].upper())}</span><h3>{esc(c["title"])}</h3><p>{esc(c["summary"])}</p><span>{len(c["parameters"])}条参数记录 · {counts["missing"]}条完全缺值 →</span></a>')
        facts=''.join(f'<li>{esc(x)}</li>' for x in c['facts'])
        images=''.join(figure_html(d,svgs[d['id']]) for d in c['diagrams'])
        gaps=''.join(f'<li>{esc(x)}</li>' for x in c['unresolved'])
        csv_uri='data:text/csv;charset=utf-8;base64,'+base64.b64encode(('\ufeff'+csvs[c['id']]).encode()).decode()
        case_sections.append(f'<section id="{c["id"]}" class="case-section"><p class="eyebrow">FACILITY CASE / {esc(c["id"].upper())}</p><h2>{esc(c["title"])}</h2><p class="lead">{esc(c["summary"])}</p><div class="facts"><h3>先记住这三点</h3><ul>{facts}</ul></div>{images}<aside class="mechanism"><strong>为什么这样建模</strong><p>{esc(c["mechanism"])}</p></aside><div class="subhead"><h3>参数与来源边界</h3><a class="button secondary" download="{c["id"]}-parameters.csv" href="{csv_uri}">下载参数 CSV</a></div><p class="hint">有值表示来源给出了某种口径；状态、年代和工况决定它能怎样使用。缺值保留null，不自动转成0。</p>{parameter_table(c)}<div class="gap-box"><h3>闭合方程先补这些数据</h3><ol>{gaps}</ol><p>当前：<code>UNRESOLVED_CLOSURE</code>。下一章给出该站的状态/代数关系与初值要求。</p></div></section>')
        rows=[[p['id'],p['name'],p['reported_text'],p['unit'],AVAIL[p['availability']],p['evidence'],p['model_use_or_gap']] for p in c['parameters']]
        figures_md='\n\n'.join(f'![{d["title"]}](figures/{d["id"]}.svg)\n\n**读图：** {d["readout"]}' for d in c['diagrams'])
        case_md=f'# {c["title"]}\n\n{c["summary"]}\n\n'+ '\n'.join('- '+x for x in c['facts'])+'\n\n'+figures_md+'\n\n## 参数表\n\n'+md_table(['ID','量','公开原值/缺值','单位','状态','来源与性质','模型用途/缺口'],rows)+f'\n\n[CSV](parameters/{c["id"]}.csv) · [本站状态方程](state-equations.md) · [完整来源核查]({c["source_note"]})\n\n## 最小补数\n\n'+'\n'.join('- '+x for x in c['unresolved'])+'\n'
        write(PACK/f'{c["id"]}.md',case_md)
        case_summaries.append([c['title'],len(c['parameters']),counts['missing'],f'[{c["id"]}]({c["id"]}.md)'])
        all_sources.extend(c['sources'].items())
    all_sources.extend(book['general_sources'].items())
    source_items=[]
    for key,source in all_sources:
        access=source['access'];description=source.get('description',source['title'])
        source_items.append(f'<li id="src-{key}"><strong>{key}</strong> <a href="{esc(source["url"])}" target="_blank" rel="noopener noreferrer">{esc(source["title"])}</a><p>{MD.renderInline(description)}</p><small>{MD.renderInline(access)}</small></li>')
    shared=''.join(figure_html(d,svgs[d['id']]) for d in book['shared_diagrams'])
    total=sum(len(c['parameters']) for c in book['cases'])
    book_uri='data:application/json;base64,'+base64.b64encode((PACK/'casebook.json').read_bytes()).decode()
    output=f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><meta name="description" content="AegisDC三设施拓扑、状态方程与参数来源阅读包"><title>三座设施，三套边界 · AegisDC</title><style>{css}</style></head>
<body><a class="skip" href="#content">跳到正文</a><header class="site-head"><a href="#top" class="brand">Aegis<span>DC</span><small>设施研究笔记</small></a><nav aria-label="主要内容"><a href="#cases">三个案例</a><a href="#equations">状态方程</a><a href="#data-gaps">补数顺序</a><a href="#sources">来源</a></nav></header>
<main id="content"><section class="hero" id="top"><div><p class="eyebrow">FACILITY MODELS / 04 NOV 2026</p><h1>三座设施，<br><em>三套清楚的边界。</em></h1><p class="hero-copy">从供电、冷却到计算服务，分别读懂Frontier、El Capitan与郑州曙光8000。图里能确认什么、方程还缺什么、参数来自哪里，都放在同一份台账中。</p><div class="actions"><a href="#cases" class="button">从架构图开始 ↓</a><a download="aegisdc-facility-casebook.json" class="button secondary" href="{book_uri}">下载结构台账 JSON</a></div></div><div class="hero-side"><span class="big">03</span><p>独立工程案例</p><div><strong>{len(diagrams)}</strong><span>原创架构图</span><strong>{total}</strong><span>参数与缺值记录</span></div><small>阶段：结构与方程资料包<br>真实参数校准 · 待补数据</small></div></section>
<section class="reading" aria-labelledby="reading-title"><h2 id="reading-title">这份资料怎样读</h2><div class="three-col"><p><b>01 看系统与接口</b><br>沿电能、流体和热量的箭头看连接；换热器两侧的流体各自闭环。</p><p><b>02 看数字的性质</b><br>运行描述、设计能力、模型近似和厂家声明分别标记；冲突值并列保留。</p><p><b>03 找方程的缺口</b><br>从热容、UA、泵曲线到初值，逐项说明缺什么，以及它阻止哪种计算。</p></div><div class="legend">实线：来源发表的功能/设计关系；虚线：发表模型或研究提议；点线：缺失连接。文字标签与线型共同区分，颜色只作辅助。所有图均为功能抽象，人员访问图另待取得。</div></section>
<section id="cases"><p class="eyebrow">CASE INDEX</p><h2>先看各自的系统，<br>再比较共同的问题。</h2><div class="case-cards">{''.join(intro)}</div></section>
<div class="filterbar"><label for="parameter-filter">参数表显示</label><select id="parameter-filter"><option value="all">全部记录</option><option value="gaps">只看缺值、部分缺失与冲突</option></select><span id="filter-status" aria-live="polite">当前显示全部{total}条记录</span></div>
{''.join(case_sections)}
<section id="equations" class="equations-section"><p class="eyebrow">MODEL FORMULATION</p><h2>让每条边都有守恒关系，<br>让每个缺值都有位置。</h2><p class="lead">以下方程是本研究提出的集中参数近似。A节是共同模块，B/C/D节分别对应三个案例，并列出状态、输入、观测、初值和未闭合项。</p>{shared}<div class="equation-chapter">{equations}</div></section>
<section id="data-gaps"><p class="eyebrow">NEXT DATA PACKAGE</p><h2>先补结构，再做校准。</h2><div class="three-col"><article><span class="step">01</span><h3>确定边界</h3><p>逐站取得单线图、P&amp;ID、介质与供回端口、柜组/负载映射、隔离与备用连接。</p></article><article><span class="step">02</span><h3>补齐物性与动态</h3><p>有效热容、库存、UA、泵阀曲线、相变物性，以及同步负荷/环境/控制时序。</p></article><article><span class="step">03</span><h3>核验服务与证据</h3><p>保护/恢复规程、切换试验、缺陷维修分母、测点误差、现场检查性能与工时。</p></article></div><p>当前三站均未完成动态闭合或现场校准；本轮不训练智能体、不调用科研模型、不启动RSI或新增注册实验。原有风险原型与会前证据继续保留。</p></section>
<section id="sources"><p class="eyebrow">PRIMARY SOURCES</p><h2>来源、年代与读取范围</h2><p>优先使用实验室、作者论文、政府工程文件、厂家/运营方和央视官网。主来源之间的差异保留各自语义；源PDF和工作簿只在本地缓存，公开仓库保存身份与有限核对收据。</p><ol class="sources">{''.join(source_items)}</ol></section>
<footer><strong>AegisDC</strong><p>整理日期2026-11-04 · 独立设施资料包 · SVG与参数表由同一台账生成</p><a href="https://github.com/DonsonHH/AegisDC/tree/main/docs/research/20261104/facility-cases" target="_blank" rel="noopener noreferrer">仓库中的可编辑资料 ↗</a></footer></main>
<dialog id="figure-dialog" aria-labelledby="dialog-title"><div class="dialog-head"><h2 id="dialog-title">架构图</h2><label>缩放 <input id="figure-scale" type="range" min="60" max="150" value="100" aria-label="架构图缩放比例"></label><button id="close-dialog" type="button">关闭 ×</button></div><p class="dialog-hint">可横向/纵向滚动查看；Esc关闭。图中文字与线型对应来源等级。</p><div id="figure-canvas"></div></dialog>
<script>{javascript}</script></body></html>'''
    write(PACK/'report.html',output)
    readme='# 三设施拓扑、状态方程与参数资料包\n\n先打开[离线阅读版](report.html)，查看架构图、参数筛选、公式与主来源。HTML是单文件，可复制到其他目录离线打开；图表和公式均无需CDN。\n\n'+md_table(['案例','参数记录','完全缺值','明细'],case_summaries)+'\n\n共8幅原创SVG。图中实线表示公开功能/设计关系，虚线表示发表模型或研究提议，点线表示缺失连接；热流、流体、电能与信息分型。图不是竣工图或人员通行图。\n\n- [共同模块与各站状态方程](state-equations.md)：SI单位、状态/代数/输入/观测、初值与闭合条件。\n- [机器可读台账](casebook.json)：103条参数记录、逐节点/边来源和绘图布局。\n- [Frontier参数CSV](parameters/frontier.csv)、[El Capitan参数CSV](parameters/el-capitan.csv)、[郑州参数CSV](parameters/zhengzhou.csv)。\n- [源文件与工作簿有限核对](../../../../evidence/facility-case-models-20261104/reference-inspection.json)：关键PDF图页、20MB原始工作簿表头/前19时间戳及SHA。\n\n当前三案例为`UNRESOLVED_CLOSURE`。公开站点描述、设计值、发表模型和厂家声明分别保留；未知字段为null，冲突不靠平均或拼接消除。物理模型的标定先于策略收益评价，智能体与RSI后置。本轮没有新增训练或注册实验。\n'
    # Four parent levels lead from facility-cases back to repository root.
    write(PACK/'README.md',readme)
    source_paths=[PACK/'casebook.json',PACK/'state-equations.md',ROOT/'scripts/build_facility_cases.py',ROOT/'scripts/facility_cases_report.css',ROOT/'scripts/facility_cases_report.js',ROOT/'scripts/verify_facility_cases.py',ROOT/'scripts/check_facility_cases_browser.cjs']
    generated=[PACK/'report.html',PACK/'README.md',*[PACK/f'{c["id"]}.md' for c in book['cases']],*[PACK/'figures'/f'{d["id"]}.svg' for d in diagrams],*[PACK/'parameters'/f'{c["id"]}.csv' for c in book['cases']]]
    manifest={'schema':'aegisdc-facility-case-build-v1','basis':'source-backed reference models and declared modeling proposals','case_count':len(book['cases']),'parameter_records':total,'diagram_count':len(diagrams),'mathml_formulas':formula_count,'external_runtime_resources':0,'sources':{p.relative_to(ROOT).as_posix():sha(p) for p in source_paths},'generated':{p.relative_to(ROOT).as_posix():sha(p) for p in generated},'new_training':0,'new_registered_experiments':0,'field_calibration':'PENDING'}
    manifest['authoring_dependencies']={name:importlib.metadata.version(name) for name in ['markdown-it-py','latex2mathml']}
    write(EVIDENCE/'build-manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:manifest[k] for k in ['case_count','parameter_records','diagram_count','mathml_formulas']},ensure_ascii=False))

if __name__=='__main__':main()
