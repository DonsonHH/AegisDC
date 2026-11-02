"""Build evidence-bound paper assets from saved records; no research executions."""
from __future__ import annotations

import base64
from collections import Counter
import csv
import gzip
import hashlib
import html
import importlib.metadata
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / '.work/paper-writing-deps'
if DEPS.is_dir():
    sys.path.insert(0, str(DEPS))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from markdown_it import MarkdownIt
from latex2mathml.converter import convert

PAPER = ROOT / 'paper'
FIGURES = PAPER / 'figures'
GENERATED = PAPER / 'generated'
RUN = ROOT / 'runs/event-validation-amended-20261102'
EVIDENCE = ROOT / 'evidence/event-validation/final'
for folder in [FIGURES, GENERATED]:
    folder.mkdir(parents=True, exist_ok=True)
sources = {}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    sources[path.relative_to(ROOT).as_posix()] = sha(path.read_bytes())
    if path.suffix == '.gz':
        with gzip.open(path, 'rt', encoding='utf-8') as stream:
            return json.load(stream)
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


def table(headers, rows):
    return '\n'.join(['|'+'|'.join(headers)+'|', '|'+'|'.join(['---']*len(headers))+'|',
                      *['|'+'|'.join(str(x) for x in row)+'|' for row in rows]])


summary = read(EVIDENCE/'summary.json')
rows = read(EVIDENCE/'rows.json')
pairs = read(EVIDENCE/'pairs.json')
protocol = read(EVIDENCE/'protocol.json')
attempts = read(EVIDENCE/'attempts.json')
raw_index = read(EVIDENCE/'local-artifacts.json')
assert summary['total_attempts'] == len(attempts) == 109
assert sum(a['status'] == 'completed' for a in attempts) == len(rows) == 108
assert sum(a['status'] == 'failed' for a in attempts) == 1
assert len({(r['case'], r['method']) for r in rows}) == 108
assert len(pairs) == 36 and len({p['seed'] for p in pairs}) == 12
primary = [p for p in pairs if p['group'] == 'coupled']
assert len(primary) == 12
case_by_id = {c['id']: c for c in protocol['cases']}
main = {}
labels = {'tour': '固定Tour', 'fifo': 'FIFO事件响应', 'shuffled': '同专业位置置乱'}
main_table = []
for method in ['tour', 'fifo', 'shuffled']:
    selected = [r for r in rows if r['group'] == 'coupled' and r['method'] == method]
    result = {key: sum(r[key] for r in selected) for key in
              ['anomaly_segments', 'confirmed_segments', 'missed_segments', 'extra_event_visits']}
    for key in ['travel_m', 'service_s', 'completed_inspections', 'consequence_weighted_censored_delay_s']:
        assert all(r[key] is not None for r in selected)
        result['mean_'+key] = sum(r[key] for r in selected)/len(selected)
    for key in ['confirmed_segments', 'missed_segments', 'anomaly_segments', 'extra_event_visits']:
        assert result[key] == summary['groups']['coupled'][method][key]
    result['confirmation_pct'] = result['confirmed_segments']/result['anomaly_segments']*100
    main[method] = result
    main_table.append([labels[method], f"{result['confirmed_segments']}/{result['anomaly_segments']}",
                       result['missed_segments'], f"{result['mean_consequence_weighted_censored_delay_s']:.2f}",
                       f"{result['mean_travel_m']:.2f}", f"{result['mean_service_s']:.2f}",
                       f"{result['mean_completed_inspections']:.2f}", result['extra_event_visits']])
tables = {'MAIN': table(['方法', '确认/异常段', '漏检', '平均加权截尾等待/秒', '平均移动/米',
                         '平均服务/人秒', '平均完成量', '额外访问合计'], main_table)}

cost_table = []
cost_data = []
for group, label in [('healthy', '健康高噪声'), ('healthy_spurious', '健康＋人工虚假提示'),
                     ('mild', '60秒冷板扰动')]:
    base = summary['groups'][group]['tour']
    for method in ['fifo', 'shuffled']:
        value = summary['groups'][group][method]
        delta = value['mean_travel_m']-base['mean_travel_m']
        count = value['mean_completed_inspections']-base['mean_completed_inspections']
        selected = [r for r in rows if r['group'] == group and r['method'] == method]
        assert all(r['anomaly_segments'] == 0 and r['consequence_weighted_censored_delay_s'] is None for r in selected)
        cost_table.append([label, labels[method], value['cases'], value['extra_event_visits'], f'{delta:.2f}', f'{count:.2f}'])
        cost_data.append(dict(group=group, method=method, cases=value['cases'],
                              extra_visits=value['extra_event_visits'], travel_delta_m=delta, completed_delta=count))
tables['COST'] = table(['条件', '方法', '过程数', '额外访问合计', '相对Tour多走/米', '完成量变化'], cost_table)

life_table = []
for method in ['fifo', 'shuffled']:
    outcomes = summary['groups']['coupled'][method]['event_outcomes']
    life_table.append([labels[method], *[outcomes.get(k, 0) for k in
                      ['normal_measured', 'expired', 'measured_late', 'same_time_measurement', 'prior_signal_measurement']],
                      sum(r['multiple_legal_event_decisions'] for r in rows if r['group'] == 'coupled' and r['method'] == method)])
tables['LIFECYCLE'] = table(['方法', '正常闭合', '过期未测', '晚测', '同刻揭示与测量',
                           '先有信号后测量', '多合法事件竞争决策'], life_table)
for key, value in tables.items():
    (GENERATED/('table_'+key.lower()+'.md')).write_text(value+'\n', encoding='utf-8', newline='\n')
with (GENERATED/'table_main.csv').open('w', encoding='utf-8-sig', newline='') as stream:
    writer = csv.writer(stream, lineterminator='\n')
    writer.writerow(['method', 'confirmed_segments', 'anomaly_segments', 'missed_segments', 'wait_s',
                     'travel_m', 'service_s', 'completed_inspections', 'extra_visits'])
    for method, value in main.items():
        writer.writerow([method, value['confirmed_segments'], value['anomaly_segments'], value['missed_segments'],
                         value['mean_consequence_weighted_censored_delay_s'], value['mean_travel_m'],
                         value['mean_service_s'], value['mean_completed_inspections'], value['extra_event_visits']])

# Read existing online decisions. This is retrospective counting, not an action intervention.
extra, head_legal, episode_sources = 0, 0, []
for case in [c for c in protocol['cases'] if c['group'] == 'coupled']:
    path = RUN/(case['id']+'-fifo.json.gz')
    assert sha(path.read_bytes()) == raw_index[path.name]['sha256']
    record = read(path)
    decisions = {(d['time_s'], d['agent']): d for d in record['decisions']}
    for dispatch in record['dispatches']:
        if not dispatch['extra_event_visit']:
            continue
        extra += 1
        decision = decisions[(dispatch['time_s'], dispatch['agent'])]
        head = next(c for c in decision['candidates'] if c['task'] == decision['routine_head'])
        head_legal += int(head['certificate']['ok'])
    episode_sources.append(path.name)
assert extra == head_legal == 89

timeline = {'case': 'p02-coupled', 'selection': 'Retrospectively selected first primary process with a recorded loss; illustrative paired tasks, not a new independent sample.', 'tasks': {}}
for method in ['tour', 'fifo']:
    path = RUN/('p02-coupled-'+method+'.json.gz')
    assert sha(path.read_bytes()) == raw_index[path.name]['sha256']
    record = read(path)
    for task in [20, 21]:
        item = timeline['tasks'].setdefault(str(task), {})
        item[method] = {
            'interval': next(i for i in record['anomaly_intervals'] if i['task_id'] == f'thermal:{task}'),
            'measurements': [e for e in record['inspection_events'] if e['task'] == task and 620 <= e['time_s'] <= 780],
            'public_events': [e for e in record.get('public_events', []) if e['task'] == task],
            'dispatches': [d for d in record.get('dispatches', []) if d['task'] == task and 620 <= d['time_s'] <= 780],
        }
assert timeline['tasks']['20']['fifo']['interval']['first_confirmation_s'] == 705
assert timeline['tasks']['20']['tour']['interval']['first_confirmation_s'] is None
assert timeline['tasks']['21']['tour']['interval']['first_confirmation_s'] == 695
assert timeline['tasks']['21']['fifo']['interval']['first_confirmation_s'] is None
write(GENERATED/'timeline.json', timeline)

plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.spines.top': False,
                     'axes.spines.right': False, 'svg.fonttype': 'none', 'svg.hashsalt': 'renly-paper-v1',
                     'figure.facecolor': 'white', 'axes.labelcolor': '#17212b', 'text.color': '#17212b'})


def save(fig, name):
    fig.savefig(FIGURES/(name+'.png'), dpi=180, bbox_inches='tight', facecolor='white')
    vector = FIGURES/(name+'.svg')
    fig.savefig(vector, bbox_inches='tight', facecolor='white', metadata={'Date': None})
    vector.write_text('\n'.join(line.rstrip() for line in vector.read_text(encoding='utf-8').splitlines())+'\n',
                      encoding='utf-8', newline='\n')
    plt.close(fig)


fig, ax = plt.subplots(figsize=(11.0, 4.9))
ax.axis('off'); ax.set_xlim(0, 11); ax.set_ylim(0, 5)
def box(x, y, w, h, title, text, color='#edf3fa', dashed=False):
    patch = FancyBboxPatch((x, y), w, h, boxstyle='round,pad=.08,rounding_size=.1',
                          facecolor=color, edgecolor='#44566b', linewidth=1., linestyle='--' if dashed else '-')
    ax.add_patch(patch)
    ax.text(x+w/2, y+h*.7, title, ha='center', va='center', weight='bold', fontsize=10)
    ax.text(x+w/2, y+h*.3, text, ha='center', va='center', fontsize=8.5, linespacing=1.5)
def arrow(start, end, **kwargs):
    ax.annotate('', xy=end, xytext=start, arrowprops=dict(arrowstyle='->', color='#425a70', lw=1.2, **kwargs))
box(.25, 3.25, 2.0, 1.0, 'Public observations', 'Telemetry + qualified\nmeasurements')
box(3.0, 3.25, 2.2, 1.0, 'Two obligations', 'Routine cursor +\npending risk events')
box(6.0, 3.25, 2.2, 1.0, 'Execution boundary', 'Ownership / reservation\nreturn certificate / budget')
box(8.85, 3.25, 1.85, 1.0, 'Execution', 'Travel, service,\nqualified measurement')
arrow((2.35, 3.75), (2.9, 3.75)); arrow((5.3, 3.75), (5.9, 3.75)); arrow((8.3, 3.75), (8.75, 3.75))
ax.annotate('', xy=(1.25, 3.15), xytext=(9.75, 3.15),
            arrowprops=dict(arrowstyle='->', color='#425a70', connectionstyle='bar,fraction=-.08', lw=1.))
ax.text(5.5, 2.55, 'New measurements update public information', ha='center', fontsize=9)
box(.25, .45, 2.65, 1.1, 'Hidden physical process', 'Fault labels and full state\nused only offline', color='#f3f4f5')
box(4.1, .45, 2.65, 1.1, 'Offline evaluation', 'Confirmed / missed intervals\ntravel / service / revisit gaps', color='#f3f4f5')
arrow((3.0, 1.0), (4., 1.0)); arrow((9.8, 3.1), (6.9, 1.5))
box(8.0, .45, 2.7, 1.1, 'RQ3: planned selector', 'Respond or defer\nnot implemented in this study', color='#fff6e9', dashed=True)
ax.text(.25, 4.65, 'Online: only public information enters selection', fontsize=11, weight='bold')
ax.text(.25, 1.85, 'Retrospective truth and future workflow research', fontsize=10, color='#5e6d7b')
save(fig, 'fig01_execution_framework')

fig, ax = plt.subplots(figsize=(8.5, 5.0))
y = list(range(len(primary)))
gains = [p['fifo_minus_tour']['gained'] for p in primary]
losses = [-p['fifo_minus_tour']['lost'] for p in primary]
nets = [p['fifo_minus_tour']['net'] for p in primary]
ax.barh(y, gains, color='#2166ac', height=.62, label='Gained confirmations')
ax.barh(y, losses, color='#b2182b', height=.62, label='Lost confirmations')
ax.scatter(nets, y, color='#151515', s=27, marker='D', zorder=4, label='Net change')
for i, value in enumerate(nets):
    ax.text(max(gains[i], value)+.13, i, f'net {value:+d}', va='center', fontsize=8.5)
ax.axvline(0, color='#48525d', lw=.8)
ax.set_yticks(y, [p['case'].replace('-coupled', '') for p in primary]); ax.invert_yaxis()
ax.set_xlim(-1.65, 8.4); ax.set_xlabel('Confirmed abnormal intervals: FIFO minus Tour')
ax.set_title('Paired gains and losses across 12 predeclared processes', loc='left', pad=17, weight='bold')
ax.xaxis.grid(True, color='#e7ebef'); ax.set_axisbelow(True)
ax.legend(loc='lower right', frameon=False, fontsize=8.5)
fig.text(.135, -.015, 'Total gained 45, lost 3, net +42. One process per row; interval counts are not independent samples.', fontsize=8)
save(fig, 'fig02_paired_confirmations')

fig, axes = plt.subplots(2, 1, figsize=(10.4, 4.7), sharex=True, layout='constrained')
for ax, task in zip(axes, ['20', '21']):
    item = timeline['tasks'][task]; interval = item['fifo']['interval']
    ax.axvspan(interval['onset_s'], interval['end_s'], color='#e5e8eb', zorder=0)
    for method, yval, color in [('tour', 0, '#6b7280'), ('fifo', 1, '#2166ac')]:
        ax.hlines(yval, 620, 780, color=color, alpha=.35, lw=1)
        for d in item[method]['dispatches']:
            ax.plot([d['time_s'], d['certificate']['candidate_finish_s']], [yval, yval], color=color, lw=3.5)
        for e in item[method]['measurements']:
            marker = 'o' if e['alarm'] else 'x'
            ax.scatter(e['time_s'], yval, color=color, marker=marker, s=52, zorder=4)
            ax.text(e['time_s'], yval-.23, f"{e['time_s']:.0f}", ha='center', fontsize=8)
        for e in item[method]['public_events']:
            if 620 <= e['visible_s'] <= 780:
                ax.scatter(e['visible_s'], yval+.34, marker='D', color='#be6d00', s=34, zorder=4)
                ax.text(e['visible_s'], yval+.48, f"public cue {e['visible_s']:.0f}", ha='center', fontsize=8, color='#855000')
    result = 'gained confirmation' if task == '20' else 'lost confirmation'
    ax.set_title(f'Thermal task {task}: {result}', loc='left', fontsize=10.5, weight='bold')
    ax.set_yticks([0, 1], ['Tour', 'FIFO']); ax.set_ylim(-.45, 1.9); ax.set_xlim(620, 780)
    ax.xaxis.grid(True, color='#edf0f2'); ax.set_axisbelow(True)
axes[-1].set_xlabel('Process time (s)')
fig.suptitle('One process, two consequences of event response (p02-coupled)', x=.04, ha='left', fontsize=12, weight='bold')
save(fig, 'fig03_paired_timeline')

metric_snapshot = {'purpose': 'Writing derivatives only; no environment execution, training or model calls.',
                   'main': main, 'costs': cost_data,
                   'primary_paired': primary, 'response_or_routine_opportunities': {
                       'extra_dispatches': extra, 'routine_head_also_certified': head_legal,
                       'independent_processes': 12, 'scope': 'Retrospective same-state feasibility count, not an intervention.'},
                   'source_sha256': sources,
                   'authoring_versions': {name: importlib.metadata.version(name) for name in
                       ['matplotlib', 'markdown-it-py', 'latex2mathml', 'numpy']}}
write(GENERATED/'metrics.json', metric_snapshot)

manuscript_path = PAPER/'manuscript_zh.md'
text = manuscript_path.read_text(encoding='utf-8')
for key, value in tables.items():
    region = f'<!-- GENERATED_TABLE_{key}_START -->\n{value}\n<!-- GENERATED_TABLE_{key}_END -->'
    pattern = rf'<!-- GENERATED_TABLE_{key}_START -->.*?<!-- GENERATED_TABLE_{key}_END -->'
    if '{{TABLE_'+key+'}}' in text:
        text = text.replace('{{TABLE_'+key+'}}', region)
    elif re.search(pattern, text, flags=re.S):
        text = re.sub(pattern, lambda _: region, text, flags=re.S)
    else:
        raise ValueError('Missing generated table region '+key)
assert not re.search(r'\{\{TABLE_', text)
manuscript_path.write_text(text, encoding='utf-8', newline='\n')

# Convert all author-supplied formulas to native MathML before Markdown rendering.
math_count = {'inline': 0, 'block': 0}
def block_math(match):
    value = match.group(1).strip()
    tag = re.search(r'\\tag\{([^}]+)\}', value)
    value = re.sub(r'\\tag\{[^}]+\}', '', value)
    math_count['block'] += 1
    number = f'<span class="equation-number">({html.escape(tag.group(1))})</span>' if tag else ''
    return '\n\n<div class="equation">'+convert(value, display='block')+number+'</div>\n\n'
render_text = re.sub(r'\$\$(.*?)\$\$', block_math, text, flags=re.S)
def inline_math(match):
    math_count['inline'] += 1
    return convert(match.group(1), display='inline')
render_text = re.sub(r'(?<!\\)\$([^$\n]+?)\$', inline_math, render_text)
renderer = MarkdownIt('commonmark', {'html': True}).enable('table')
body = renderer.render(render_text)
for name in ['fig01_execution_framework', 'fig02_paired_confirmations', 'fig03_paired_timeline']:
    data = base64.b64encode((FIGURES/(name+'.png')).read_bytes()).decode()
    body = body.replace('src="figures/'+name+'.png"', 'src="data:image/png;base64,'+data+'"')
toc = []
def heading(match):
    level, content = match.group(1), match.group(2)
    identity = 'section-'+str(len(toc)+1)
    toc.append((level, identity, re.sub('<[^>]*>', '', content)))
    return f'<h{level} id="{identity}">{content}</h{level}>'
body = re.sub(r'<h([23])>(.*?)</h\1>', heading, body, flags=re.S)
links = ''.join(f'<a class="level-{level}" href="#{identity}">{content}</a>' for level, identity, content in toc if level == '2')
css = '''
:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#f3f5f7;color:#18252f;font:17px/1.85 "Microsoft YaHei","Noto Sans CJK SC",sans-serif}
header{max-width:1040px;margin:32px auto 0;padding:24px 48px;background:#203a4c;color:#fff;border-radius:8px 8px 0 0}header p{margin:0;font-size:14px;color:#d5e1ea}
article{max-width:1040px;margin:0 auto 60px;background:white;padding:36px 56px 60px;box-shadow:0 6px 32px #1b304010}h1{font-size:29px;line-height:1.5;margin-top:0}h2{font-size:23px;border-top:1px solid #dce4eb;padding-top:24px;margin-top:40px}h3{font-size:19px;margin-top:26px}
p{margin:16px 0}a{color:#1b5e92;text-decoration-thickness:1px;text-underline-offset:3px}nav{display:flex;flex-wrap:wrap;gap:8px 16px;margin-top:16px}nav a{color:#eef5fa;font-size:13px}table{border-collapse:collapse;width:100%;font-size:13px;line-height:1.6;display:block;overflow-x:auto;margin:22px 0}th,td{padding:9px 10px;text-align:left;border-bottom:1px solid #dce4eb;min-width:65px}th{background:#edf3f8;color:#203b50;white-space:nowrap}tbody tr:nth-child(even){background:#f9fbfd}img{display:block;width:100%;height:auto;margin:24px auto}code{font:13px/1.6 Consolas,monospace;background:#f0f3f6;padding:1px 4px;border-radius:3px}pre{background:#f1f4f7;padding:18px;overflow-x:auto;line-height:1.6}pre code{padding:0;background:none;white-space:pre-wrap}.equation{position:relative;padding:16px 38px 16px 10px;overflow-x:auto;margin:22px 0;background:#fafbfd}.equation-number{position:absolute;right:10px;top:20px;font-size:14px;color:#536675}math{font-family:"Cambria Math",serif}math[display="inline"]{font-size:1.05em}footer{font-size:13px;color:#627180;border-top:1px solid #dce4eb;margin-top:32px;padding-top:16px}
@media(max-width:700px){header,article{margin:0;padding:22px}h1{font-size:25px}body{font-size:16px}th,td{padding:7px;font-size:12px}}@media print{body{background:white}header{color:#18252f;background:white;margin:0}header p{color:#536675}nav{display:none}article{box-shadow:none;padding:16px;max-width:none;margin:0}a{color:inherit}h2,h3{break-after:avoid}img,table,.equation{break-inside:avoid}}
'''
page = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>耦合设施巡检论文工作稿</title><style>'+css+'</style></head><body><header><p>中文工作稿 · 2026-11-02 · RQ1—RQ2已有证据，RQ3研究设计</p><nav>'+links+'</nav></header><article>'+body+'<footer>由可编辑Markdown、封存结果与派生图表生成。公式为原生MathML；图像已嵌入。未新增科研回合。</footer></article></body></html>'
(PAPER/'manuscript_zh.html').write_text(page, encoding='utf-8', newline='\n')
assert page.count('<math ') == sum(math_count.values())
assert 'src="figures/' not in page and 'cdn.' not in page
assert not re.search(r'\$[^$\n]+\$', body)
assert all((FIGURES/(n+'.svg')).is_file() for n in ['fig01_execution_framework', 'fig02_paired_confirmations', 'fig03_paired_timeline'])
validation = {'status': 'PASS', 'successful_research_records_reused': 108, 'new_environment_evaluations': 0,
              'new_model_calls': 0, 'new_training': 0, 'source_files_hashed': len(sources),
              'main_processes': 12, 'main_segments': 89, 'main_confirmations': [main[m]['confirmed_segments'] for m in ['tour', 'fifo', 'shuffled']],
              'mathml_formulas': math_count, 'embedded_figures': 3, 'unresolved_table_placeholders': 0,
              'figures': {p.name: sha(p.read_bytes()) for p in sorted(FIGURES.iterdir())},
              'manuscript_sha256': sha(manuscript_path.read_bytes()),
              'html_sha256': sha((PAPER/'manuscript_zh.html').read_bytes()),
              'scope': 'Numerical provenance, source identity, table and formula conversion. Visual inspection and argument review are separate.'}
write(GENERATED/'validation.json', validation)
print(json.dumps(validation, ensure_ascii=False, indent=2))
