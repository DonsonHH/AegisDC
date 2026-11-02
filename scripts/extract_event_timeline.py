"""Extract paired historical successes and regressions; never rerun policies."""
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
run = ROOT / 'runs/risk-response-20261102'
output = ROOT / 'evidence/risk-response'
records = {}
sources = {}
for method in ['T', 'E120']:
    source = run / f'confirmation-2-{method}.json.gz'
    sources[method] = {'file': source.name, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
    with gzip.open(source, 'rt', encoding='utf-8') as stream:
        records[method] = json.load(stream)
cases = []
for task in [87, 86]:
    pair = {}
    for method, record in records.items():
        interval = next(i for i in record['anomaly_intervals'] if i['task_id'] == f'thermal:{task}')
        measurements = [e for e in record['inspection_events'] if e['task'] == task and 750 <= e['time_s'] <= 980]
        pair[method] = {'interval': interval, 'measurements': measurements}
    assert pair['T']['interval']['onset_s'] == pair['E120']['interval']['onset_s']
    assert pair['T']['interval']['end_s'] == pair['E120']['interval']['end_s']
    events = [e for e in records['E120']['public_events'] if e['task'] == task]
    decisions = []
    for decision in records['E120']['decisions']:
        if not 780 <= decision['time_s'] <= 960:
            continue
        candidate = next((c for c in decision['candidates'] if c['task'] == task), None)
        if candidate:
            decisions.append({'time_s': decision['time_s'], 'agent': decision['agent'],
                              'selected': decision['selected'], 'candidate': candidate})
    cases.append({'task': task, 'paired': pair, 'public_events': events, 'decisions': decisions})
assert not cases[0]['paired']['T']['interval']['detected'] and cases[0]['paired']['E120']['interval']['detected']
assert cases[1]['paired']['T']['interval']['detected'] and not cases[1]['paired']['E120']['interval']['detected']
data = {'scope': 'Historical confirmation-2, selected paired examples, not independent replications.',
        'sources': sources, 'cases': cases}
(output / 'paired-timeline.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
lines = ['# 同一条件中的成功与退化时间线', '',
         '从旧版原件直接提取，未重跑策略。两例来自同一复合故障条件，不是两个独立过程。异常区间属于事后真值，未提供给在线派单。', '',
         '|对象|事后异常区间/秒|Tour首次有效确认|事件响应首次有效确认|结论|',
         '|---|---|---|---|---|']
for case in cases:
    a, b = (case['paired'][m]['interval'] for m in ['T', 'E120'])
    lines.append(f"|机柜{case['task']}|{a['onset_s']:g}—{a['end_s']:g}|{a['first_confirmation_s']}|{b['first_confirmation_s']}|{'新增确认' if b['detected'] else '丢失确认'}|")
lines += ['', '`None`表示该异常区间未被有效确认。', '']
for case in cases:
    lines += [f"## 机柜{case['task']}", '', '|时间/秒|记录|', '|---|---|']
    rows = []
    for e in case['public_events']:
        rows.append((e['visible_s'], f"公开风险事件{e['event_id']}出现；截止{e['expires_s']:g}秒；最终状态{e['status']}"))
    for method, pair in case['paired'].items():
        for e in pair['measurements']:
            rows.append((e['time_s'], f"{method}完成专业测量，alarm={e['alarm']}，额外事件访问={e.get('extra_event_visit', False)}"))
    for d in case['decisions']:
        cert = d['candidate']['certificate']
        label = f"可执行，预计{cert['candidate_finish_s']:g}秒完成" if cert['ok'] else '拒绝：'+cert['reason']
        rows.append((d['time_s'], f"E120候选检查：{label}；本次实际选择任务{d['selected']}"))
    for time, label in sorted(rows):
        lines.append(f'|{time:g}|{label}|')
    lines.append('')
lines += ['本表解释已发生轨迹上的机会与取舍，不证明全局最优或绝对不可达。T为固定巡回，E120为120秒事件响应。', '',
          '完整字段、来源文件及SHA：[paired-timeline.json](paired-timeline.json)。生成命令：`python scripts/extract_event_timeline.py`。']
(output / 'paired-timeline.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
print('Verified and extracted paired success (87) and regression (86).')
