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
tables['COST'] = ('访问列为全部过程累加；移动与完成量列为每过程差值的平均。各行范围由过程数给出。\n\n'+
                  table(['条件', '方法', '过程数', '访问合计/次', '移动差均值/米', '完成量差均值/次'], cost_table))

life_table, life_cross, life_data = [], [], {}
for method in ['fifo', 'shuffled']:
    outcomes = summary['groups']['coupled'][method]['event_outcomes']
    all_events, event_decisions, competing = [], 0, 0
    for case in [c for c in protocol['cases'] if c['group'] == 'coupled']:
        path = RUN/(case['id']+'-'+method+'.json.gz')
        assert sha(path.read_bytes()) == raw_index[path.name]['sha256']
        record = read(path); all_events.extend(record['public_events'])
        for decision in record['decisions']:
            pool = [c for c in decision['candidates'] if c['certificate']['ok'] and
                    c.get('budget_allowed', True) and c['event_id'] is not None]
            event_decisions += int(bool(pool)); competing += int(len(pool) > 1)
    status = Counter(e['status'] for e in all_events)
    measured_total = status['measured']+status['measured_late']
    assert sum(status.values()) == len(all_events)
    assert sum(status[k] for k in ['measured', 'expired', 'measured_late', 'pending']) == len(all_events)
    assert competing == sum(r['multiple_legal_event_decisions'] for r in rows if r['group'] == 'coupled' and r['method'] == method)
    life_table.append([labels[method], len(all_events), status['measured'], status['expired'],
                       status['measured_late'], status['pending']])
    life_cross.append([labels[method], f"{outcomes.get('normal_measured',0)}/{status['measured']}",
                       f"{outcomes.get('same_time_measurement',0)}/{measured_total}",
                       f"{outcomes.get('prior_signal_measurement',0)}/{measured_total}",
                       f'{competing}/{event_decisions}'])
    life_data[method] = dict(total_events=len(all_events), status=dict(status),
                             event_available_decisions=event_decisions, multiple_legal_decisions=competing)
tables['LIFECYCLE'] = ('范围为12个主过程内各方法的全部风险事件；下表状态互斥，可相加到事件总数。\n\n'+
    table(['方法', '事件总数', '有效期内测量闭合', '过期未测', '晚测闭合', '回合末待处理'], life_table)+
    '\n\n下表为交叉属性及决策统计，不能与上表或彼此相加：正常闭合的分母为有效期内测量；同刻／先有信号的分母为全部已测（含晚测）；竞争的分母为存在合法且预算允许事件的决策。\n\n'+
    table(['方法', '正常/有效期内测量', '同刻/全部已测', '先有信号/全部已测', '多事件竞争/事件可选决策'], life_cross))
search_summary = read(ROOT/'evidence/response-defer/summary.json')
search_proposals = read(ROOT/'evidence/response-defer/proposals.json')
assert search_summary['next_action'] == 'stop_no_improvement_found_in_registered_search'
assert search_summary['environment_attempts'] == 108 and search_summary['model_calls'] == 0
unique_search = {p['rule_sha256']:p for p in search_proposals}
assert len(unique_search)==9 and max(70+p['aggregate']['net'] for p in unique_search.values())==60
tables['SEARCH'] = table(['链', '规则', '确认/89段', '新增/丢失（相对FIFO）', '净增', '开发保留'],
    [[p['chain'],p['proposal'],70+p['aggregate']['net'],f"{p['aggregate']['gained']}/{p['aggregate']['lost']}",
      p['aggregate']['net'],'是' if p['aggregate']['eligible'] else '否'] for p in search_proposals])
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

timeline = {'case': 'p02-coupled', 'agent': 1,
            'selection': 'Retrospective same-owner trajectory comparison: task17 gained on a routine visit, task21 lost. Not a single-insertion counterfactual.',
            'common_anchor': {'task': 11, 'completion_s': 605}, 'tasks': {}, 'agent_chains': {}}
policy_records = {}
for method in ['tour', 'fifo']:
    path = RUN/('p02-coupled-'+method+'.json.gz')
    assert sha(path.read_bytes()) == raw_index[path.name]['sha256']
    record = read(path)
    policy_records[method] = record
    timeline['agent_chains'][method] = [e for e in record['inspection_events']
                                      if e['agent'] == 1 and 600 <= e['time_s'] <= 770]
    for task in [17, 21]:
        item = timeline['tasks'].setdefault(str(task), {})
        dispatches = record.get('dispatches', record.get('local_dispatches', []))
        item[method] = {
            'interval': next(i for i in record['anomaly_intervals'] if i['task_id'] == f'thermal:{task}'),
            'measurements': [e for e in record['inspection_events'] if e['task'] == task and 600 <= e['time_s'] <= 780],
            'public_events': [e for e in record.get('public_events', []) if e['task'] == task],
            'dispatches': [{'time_s': d.get('time_s', d.get('dispatch_time_s')),
                            'task': d['task'], 'agent': d['agent'],
                            'routine_head': d.get('routine_head'),
                            'extra_event_visit': d.get('extra_event_visit', False),
                            'finish_s': d['certificate'].get('candidate_finish_s', d['certificate'].get('segment_completion_s', [None])[0])}
                           for d in dispatches if d['task'] == task and
                           600 <= d.get('time_s', d.get('dispatch_time_s')) <= 780],
        }
assert timeline['tasks']['17']['fifo']['interval']['first_confirmation_s'] == 690
assert timeline['tasks']['17']['tour']['interval']['first_confirmation_s'] is None
assert timeline['tasks']['21']['tour']['interval']['first_confirmation_s'] == 695
assert timeline['tasks']['21']['fifo']['interval']['first_confirmation_s'] is None
for item in timeline['tasks'].values():
    for trajectory in item.values():
        assert all(e['agent'] == 1 for e in trajectory['measurements'])
prefix = lambda record: [(e['time_s'], e['task']) for e in record['inspection_events']
                         if e['agent'] == 1 and e['time_s'] <= 605]
assert prefix(policy_records['tour']) == prefix(policy_records['fifo'])
assert prefix(policy_records['fifo'])[-1] == (605, 11)
routine_gain = next(e for e in timeline['tasks']['17']['fifo']['measurements'] if e['time_s'] == 690)
assert not routine_gain['extra_event_visit'] and routine_gain['alarm']
timeline['common_anchor']['scope'] = 'Identical completed own-task prefix and own route position; global observations need not be identical.'
timeline['verified_own_prefix'] = prefix(policy_records['fifo'])
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
box(8.0, .45, 2.7, 1.1, 'RQ3: optional rule selector', 'Respond or defer interface\nfeedback gain not evaluated', color='#fff6e9', dashed=True)
ax.text(.25, 4.65, 'Online: only public information enters selection', fontsize=11, weight='bold')
ax.text(.25, 1.85, 'Offline evaluation and optional workflow interface', fontsize=10, color='#5e6d7b')
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

fig, axes = plt.subplots(3, 1, figsize=(10.4, 7.2), sharex=True, layout='constrained')
chain = axes[0]
for method, yval, color in [('tour', 0, '#6b7280'), ('fifo', 1, '#2166ac')]:
    chain.hlines(yval, 595, 775, color=color, alpha=.3)
    for e in timeline['agent_chains'][method]:
        focus = '#2166ac' if e['task'] == 17 else '#b2182b' if e['task'] == 21 else color
        chain.scatter(e['time_s'], yval, marker='o' if e['alarm'] else 'x', color=focus, s=34)
        chain.text(e['time_s'], yval+.18, f"{e['task']}@{e['time_s']:.0f}", ha='center', fontsize=7.7, color=focus)
chain.axvline(605, color='#8c939a', ls='--', lw=.8)
chain.plot([605, 635], [1, 1], color='#be6d00', lw=3.5)
chain.text(620, .65, 'insert task 23\n(routine head 9)', ha='center', va='center', color='#855000', fontsize=8)
chain.set_title('Same inspector (agent 1): own-task prefix agrees through task 11 at 605 s', loc='left', fontsize=10, weight='bold')
chain.set_yticks([0, 1], ['Tour', 'FIFO']); chain.set_ylim(-.4, 1.65)
chain.xaxis.grid(True, color='#edf0f2'); chain.set_axisbelow(True)
for ax, task in zip(axes[1:], ['17', '21']):
    item = timeline['tasks'][task]; interval = item['fifo']['interval']
    ax.axvspan(interval['onset_s'], interval['end_s'], color='#e5e8eb', zorder=0)
    for method, yval, color in [('tour', 0, '#6b7280'), ('fifo', 1, '#2166ac')]:
        ax.hlines(yval, 595, 775, color=color, alpha=.35, lw=1)
        for d in item[method]['dispatches']:
            ax.plot([d['time_s'], d['finish_s']], [yval, yval], color=color, lw=3.5)
        for e in item[method]['measurements']:
            marker = 'o' if e['alarm'] else 'x'
            ax.scatter(e['time_s'], yval, color=color, marker=marker, s=52, zorder=4)
            ax.text(e['time_s'], yval-.23, f"{e['time_s']:.0f}", ha='center', fontsize=8)
        for e in item[method]['public_events']:
            if 595 <= e['visible_s'] <= 775:
                ax.scatter(e['visible_s'], yval+.34, marker='D', color='#be6d00', s=34, zorder=4)
                ax.text(e['visible_s'], yval+.48, f"public cue {e['visible_s']:.0f}", ha='center', fontsize=8, color='#855000')
    result = 'gained on a routine visit' if task == '17' else 'lost confirmation'
    ax.set_title(f'Thermal task {task}: {result}', loc='left', fontsize=10.5, weight='bold')
    ax.set_yticks([0, 1], ['Tour', 'FIFO']); ax.set_ylim(-.45, 1.9); ax.set_xlim(595, 775)
    ax.xaxis.grid(True, color='#edf0f2'); ax.set_axisbelow(True)
axes[-1].set_xlabel('Process time (s)')
fig.suptitle('Same-owner phase changes under two complete policies (p02-coupled)', x=.04, ha='left', fontsize=12, weight='bold')
save(fig, 'fig03_paired_timeline')

metric_snapshot = {'purpose': 'Writing derivatives only; no environment execution, training or model calls.',
                   'main': main, 'costs': cost_data,
                   'lifecycle_denominators': life_data,
                   'response_search': {'actual_development_evaluations':108,'proposal_opportunities':12,
                                       'unique_rules':9,'best_confirmed_segments':60,'baseline_confirmed_segments':70,
                                       'model_calls':0,'new_confirmation_evaluations':0},
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

# Shared static preview renderer; all formulas are converted before Markdown.
def render_preview(source_text, title, subtitle):
    counts = {'inline': 0, 'block': 0}
    def block_math(match):
        value = match.group(1).strip()
        tag = re.search(r'\\tag\{([^}]+)\}', value)
        value = re.sub(r'\\tag\{[^}]+\}', '', value)
        counts['block'] += 1
        number = f'<span class="equation-number">({html.escape(tag.group(1))})</span>' if tag else ''
        return '\n\n<div class="equation">'+convert(value, display='block')+number+'</div>\n\n'
    rendered = re.sub(r'\$\$(.*?)\$\$', block_math, source_text, flags=re.S)
    def inline_math(match):
        counts['inline'] += 1
        return convert(match.group(1), display='inline')
    rendered = re.sub(r'(?<!\\)\$([^$\n]+?)\$', inline_math, rendered)
    body = MarkdownIt('commonmark', {'html': True}).enable('table').render(rendered)
    for name in ['fig01_execution_framework', 'fig02_paired_confirmations', 'fig03_paired_timeline']:
        data = base64.b64encode((FIGURES/(name+'.png')).read_bytes()).decode()
        body = body.replace('src="figures/'+name+'.png"', 'src="data:image/png;base64,'+data+'"')
    for name in ['manuscript_zh', 'model-appendix', 'supplement']:
        body = body.replace('href="'+name+'.md"', 'href="'+name+'.html"')
    toc = []
    def heading(match):
        level, content = match.group(1), match.group(2)
        identity = 'section-'+str(len(toc)+1)
        toc.append((level, identity, re.sub('<[^>]*>', '', content)))
        return f'<h{level} id="{identity}">{content}</h{level}>'
    body = re.sub(r'<h([23])>(.*?)</h\1>', heading, body, flags=re.S)
    links = ''.join(f'<a href="#{identity}">{content}</a>' for level, identity, content in toc if level=='2')
    page = ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" '
            'content="width=device-width,initial-scale=1"><title>'+html.escape(title)+'</title><style>'+css+
            '</style></head><body><header><p>'+html.escape(subtitle)+'</p><nav>'+links+'</nav></header><article>'+body+
            '<footer>可编辑Markdown与封存证据的静态预览。公式为MathML；未新增科研回合。</footer></article></body></html>')
    assert page.count('<math ') == sum(counts.values())
    assert 'src="figures/' not in page and 'cdn.' not in page
    assert not re.search(r'\$[^$\n]+\$', body)
    return page, counts

css = '''
:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#f3f5f7;color:#18252f;font:17px/1.85 "Microsoft YaHei","Noto Sans CJK SC",sans-serif}
header{max-width:1040px;margin:32px auto 0;padding:24px 48px;background:#203a4c;color:#fff;border-radius:8px 8px 0 0}header p{margin:0;font-size:14px;color:#d5e1ea}
article{max-width:1040px;margin:0 auto 60px;background:white;padding:36px 56px 60px;box-shadow:0 6px 32px #1b304010}h1{font-size:29px;line-height:1.5;margin-top:0}h2{font-size:23px;border-top:1px solid #dce4eb;padding-top:24px;margin-top:40px}h3{font-size:19px;margin-top:26px}
p{margin:16px 0}a{color:#1b5e92;text-decoration-thickness:1px;text-underline-offset:3px}nav{display:flex;flex-wrap:wrap;gap:8px 16px;margin-top:16px}nav a{color:#eef5fa;font-size:13px}table{border-collapse:collapse;width:100%;font-size:13px;line-height:1.6;display:block;overflow-x:auto;margin:22px 0}th,td{padding:9px 10px;text-align:left;border-bottom:1px solid #dce4eb;min-width:65px}th{background:#edf3f8;color:#203b50;white-space:nowrap}tbody tr:nth-child(even){background:#f9fbfd}img{display:block;width:100%;height:auto;margin:24px auto}code{font:13px/1.6 Consolas,monospace;background:#f0f3f6;padding:1px 4px;border-radius:3px}pre{background:#f1f4f7;padding:18px;overflow-x:auto;line-height:1.6}pre code{padding:0;background:none;white-space:pre-wrap}.equation{position:relative;padding:16px 38px 16px 10px;overflow-x:auto;margin:22px 0;background:#fafbfd}.equation-number{position:absolute;right:10px;top:20px;font-size:14px;color:#536675}math{font-family:"Cambria Math",serif}math[display="inline"]{font-size:1.05em}footer{font-size:13px;color:#627180;border-top:1px solid #dce4eb;margin-top:32px;padding-top:16px}
@media(max-width:700px){header,article{margin:0;padding:22px}h1{font-size:25px}body{font-size:16px}th,td{padding:7px;font-size:12px}}@media print{body{background:white}header{color:#18252f;background:white;margin:0}header p{color:#536675}nav{display:none}article{box-shadow:none;padding:16px;max-width:none;margin:0}a{color:inherit}h2,h3{break-after:avoid}img,table,.equation{break-inside:avoid}}
'''
page, math_count = render_preview(text, '耦合设施巡检论文工作稿', '中文工作稿 · 2026-11-02 · RQ1—RQ2已有证据，RQ3补强中')
(PAPER/'manuscript_zh.html').write_text(page, encoding='utf-8', newline='\n')
auxiliary = {}
for name, title in [('model-appendix', '附录A 合成模型'), ('supplement', '补充材料')]:
    path = PAPER/(name+'.md')
    preview, counts = render_preview(path.read_text(encoding='utf-8'), title, '论文附录 · 方程形式、数值设定与证据身份')
    (PAPER/(name+'.html')).write_text(preview, encoding='utf-8', newline='\n')
    auxiliary[name] = {'source_sha256': sha(path.read_bytes()), 'html_sha256': sha(preview.encode()), 'mathml_formulas': counts}
assert all((FIGURES/(n+'.svg')).is_file() for n in ['fig01_execution_framework', 'fig02_paired_confirmations', 'fig03_paired_timeline'])
validation = {'status': 'PASS', 'successful_research_records_reused': 108, 'new_environment_evaluations': 0,
              'new_model_calls': 0, 'new_training': 0, 'source_files_hashed': len(sources),
              'main_processes': 12, 'main_segments': 89, 'main_confirmations': [main[m]['confirmed_segments'] for m in ['tour', 'fifo', 'shuffled']],
              'mathml_formulas': math_count, 'auxiliary_previews': auxiliary, 'embedded_figures': 3, 'unresolved_table_placeholders': 0,
              'figures': {p.name: sha(p.read_bytes()) for p in sorted(FIGURES.iterdir())},
              'manuscript_sha256': sha(manuscript_path.read_bytes()),
              'html_sha256': sha((PAPER/'manuscript_zh.html').read_bytes()),
              'scope': 'Numerical provenance, source identity, table and formula conversion. Visual inspection and argument review are separate.'}
write(GENERATED/'validation.json', validation)
print(json.dumps(validation, ensure_ascii=False, indent=2))
