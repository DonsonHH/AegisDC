"""Build the four-screen offline briefing from frozen evidence and paper figures.

This stdlib-only authoring command never imports or runs the research simulator.
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import html
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / 'paper'
SOURCES: dict[str, str] = {}


def read_bytes(relative: str) -> bytes:
    data = (ROOT / relative).read_bytes()
    SOURCES[relative] = hashlib.sha256(data).hexdigest()
    return data


def read_json(relative: str):
    return json.loads(read_bytes(relative).decode('utf-8'))


def paragraphs(text: str) -> str:
    return '\n'.join(f'<p>{html.escape(p.strip())}</p>'
                     for p in text.strip().split('\n\n') if p.strip())


def main() -> None:
    read_bytes('scripts/build_supervisor_briefing.py')
    metrics = read_json('paper/generated/metrics.json')
    summary = read_json('evidence/event-validation/final/summary.json')
    rows = read_json('evidence/event-validation/final/rows.json')
    pairs = read_json('evidence/event-validation/final/pairs.json')
    proposals = read_json('evidence/response-defer/proposals.json')
    search = read_json('evidence/response-defer/summary.json')
    timeline = read_json('paper/generated/timeline.json')
    validation = read_json('paper/generated/validation.json')
    paper_scope = read_json('paper/evidence-map.json')['paper_scope']
    manuscript = read_bytes('paper/manuscript_zh.md')
    assert validation['manuscript_sha256'] == hashlib.sha256(manuscript).hexdigest()
    assert paper_scope['route'] == 'mechanism_discussion'
    assert paper_scope['primary_questions'] == ['RQ1', 'RQ2']
    assert not paper_scope['feedback_in_core_claims']

    primary = [p for p in pairs if p['group'] == 'coupled']
    assert len(primary) == summary['primary_paired_processes'] == 12
    main_results = {}
    for method in ['tour', 'fifo', 'shuffled']:
        selected = [r for r in rows if r['group'] == 'coupled' and r['method'] == method]
        assert len(selected) == len(primary)
        segments = sum(r['anomaly_segments'] for r in selected)
        confirmed = sum(r['confirmed_segments'] for r in selected)
        assert (segments, confirmed) == (metrics['main'][method]['anomaly_segments'],
                                        metrics['main'][method]['confirmed_segments'])
        assert confirmed == summary['groups']['coupled'][method]['confirmed_segments']
        main_results[method] = (confirmed, segments, confirmed / segments * 100)
    assert len(rows) == summary['evaluations'] == 108
    safety = {key: sum(r[key] for r in rows) for key in
              ['tasks_violating_exact_gap', 'invalid_assignments', 'duplicate_reservations']}
    assert all(value == 0 for value in safety.values())
    assert summary['gates']['all_safety_zero']
    gained = sum(p['fifo_minus_tour']['gained'] for p in primary)
    lost = sum(p['fifo_minus_tour']['lost'] for p in primary)
    net = main_results['fifo'][0] - main_results['tour'][0]
    assert gained - lost == net
    comparison = summary['primary_comparisons']['fifo_minus_tour']
    assert gained / len(primary) == comparison['gained']
    assert lost / len(primary) == comparison['lost']
    for source_key, pair_key in [('travel_delta_pct', 'travel_delta_pct'),
                                 ('completed_loss_pct', 'completed_loss_pct')]:
        assert abs(sum(p['fifo_minus_tour'][pair_key] for p in primary) / len(primary)
                   - comparison[source_key]) < 1e-9

    unique_rules = {p['rule_sha256']: p for p in proposals}
    assert len(unique_rules) == metrics['response_search']['unique_rules'] == 9
    assert len(proposals) == search['candidate_opportunities'] == 12
    assert sum(not r['cached'] for p in proposals for r in p['records']) == search['environment_attempts'] == 108
    assert search['successful_environment_evaluations'] == 108
    assert search['model_calls'] == search['training'] == 0
    assert search['next_action'] == 'stop_no_improvement_found_in_registered_search'
    assert metrics['response_search']['new_confirmation_evaluations'] == 0
    confirmations = [main_results['fifo'][0] + p['aggregate']['net'] for p in unique_rules.values()]
    assert max(confirmations) < main_results['fifo'][0]
    assert not any(p['aggregate']['eligible'] for p in unique_rules.values())

    # Check the displayed four timestamps against the actual two trajectories.
    index = read_json('evidence/event-validation/final/local-artifacts.json')
    raw = {}
    for method in ['tour', 'fifo']:
        filename = f'p02-coupled-{method}.json.gz'
        data = read_bytes(f'runs/event-validation-amended-20261102/{filename}')
        assert hashlib.sha256(data).hexdigest() == index[filename]['sha256']
        raw[method] = json.loads(gzip.decompress(data))
    assert timeline['case'] == 'p02-coupled' and timeline['agent'] == 1
    time_values = {}
    for task in ['17', '21']:
        for method in ['tour', 'fifo']:
            part = timeline['tasks'][task][method]
            interval = part['interval']
            assert interval in raw[method]['anomaly_intervals']
            measurement = part['measurements'][0]
            assert measurement in raw[method]['inspection_events']
            assert measurement['agent'] == 1
            time_values[f'T{task}_{method.upper()}'] = str(int(measurement['time_s']))
            time_values[f'T{task}_ONSET'] = str(int(interval['onset_s']))
            time_values[f'T{task}_END'] = str(int(interval['end_s']))
    t17 = timeline['tasks']['17']['fifo']
    assert not t17['measurements'][0]['extra_event_visit']
    assert t17['dispatches'][0]['time_s'] == 665
    assert t17['public_events'][0]['visible_s'] == 685

    figures = {}
    for key, name, title, caption in [
        ('framework', 'fig01_execution_framework.png', '图1 受约束事件确认机制',
         '公开信息用于在线派单。例行义务与确认事件分别记账，额外访问经过资格和返回可行性检查。'),
        ('paired', 'fig02_paired_confirmations.png', '图2 十二个主过程的新增与丢失',
         'FIFO相对Tour，新增45段、丢失3段、净增42段。11个过程净增为正，1个为零。'),
        ('timeline', 'fig03_paired_timeline.png', '图3 同一负责人的两条策略轨迹',
         '同一过程的agent 1。灰区为事后异常，实心点为异常测量，叉号为正常测量，菱形为公开风险。机柜17的690秒确认来自例行访问。完整策略比较不是单次插入的反事实消融。'),
    ]:
        data = read_bytes(f'paper/figures/{name}')
        assert hashlib.sha256(data).hexdigest() == validation['figures'][name]
        figures[key] = {'src': 'data:image/png;base64,' + base64.b64encode(data).decode('ascii'),
                        'title': title, 'caption': caption}

    talk = read_bytes('paper/supervisor-talk.md').decode('utf-8')
    notes = []
    for number in range(1, 5):
        match = re.search(rf'^## {number} ([^\n]+)\n(.*?)(?=^## |\Z)', talk, flags=re.M | re.S)
        assert match, f'Missing talk section {number}'
        notes.append(f'<section class="notes-section" data-note="{number}"><h3>'
                     + html.escape(match[1]) + '</h3>' + paragraphs(match[2]) + '</section>')
    faq_section = talk.split('## 追问准备\n', 1)[1].split('\n## 会后阅读', 1)[0]
    faqs = re.findall(r'^### ([^\n]+)\n(.*?)(?=^### |\Z)', faq_section, flags=re.M | re.S)
    assert len(faqs) == 7
    faq_html = '\n'.join('<details><summary>' + html.escape(title) + '</summary>'
                         + paragraphs(body) + '</details>' for title, body in faqs)
    ci = comparison['net_confirmations']
    values = {
        'PROCESSES': str(len(primary)), 'SEGMENTS': str(main_results['fifo'][1]),
        'GAINED': str(gained), 'LOST': str(lost), 'NET': str(net),
        'POSITIVE': str(ci['positive']), 'ZERO': str(ci['zero']),
        'MEAN_NET': f"{ci['mean']:.2f}", 'CI_LOWER': f"{ci['percentile95'][0]:.2f}",
        'CI_UPPER': f"{ci['percentile95'][1]:.2f}",
        'TRAVEL_PCT': f"{comparison['travel_delta_pct']:.2f}",
        'COMPLETION_LOSS_PCT': f"{comparison['completed_loss_pct']:.2f}",
        'RULES': str(len(unique_rules)), 'RULE_MIN': str(min(confirmations)),
        'RULE_MAX': str(max(confirmations)), 'SEARCH_EVALUATIONS': str(search['environment_attempts']),
        'NOTES': '\n'.join(notes), 'FAQ': faq_html,
        'FIGURE_FRAMEWORK': figures['framework']['src'], 'FIGURE_TIMELINE': figures['timeline']['src'],
        'FIGURE_DATA': json.dumps(figures, ensure_ascii=False).replace('</', '<\\/'),
        'SOURCE_BASE': 'https://github.com/DonsonHH/Zhinengti-RSI/blob/d011e3229d65c03da1ebd0765e1c1c6fe829fff3',
        **time_values,
    }
    for method, result in main_results.items():
        values[method.upper()] = str(result[0])
        values[method.upper() + '_PCT'] = f'{result[2]:.1f}'
    template = read_bytes('paper/briefing-template.html').decode('utf-8')
    output = re.sub(r'\{\{([A-Z0-9_]+)\}\}', lambda match: values[match[1]], template)
    assert '{{' not in output and output.count('class="slide') == 4
    destination = PAPER / 'supervisor-briefing.html'
    destination.write_text(output, encoding='utf-8', newline='\n')
    manifest = {
        'purpose': 'Four-screen supervisor briefing, derived from existing frozen evidence.',
        'screens': 4, 'planned_seconds': [60, 90, 60, 90],
        'main_processes': len(primary), 'main_segments': main_results['fifo'][1],
        'main_confirmations': {method: result[0] for method, result in main_results.items()},
        'gained': gained, 'lost': lost, 'net': net, 'successful_run_safety_totals': safety,
        'search_unique_rules': len(unique_rules), 'search_confirmation_range': [min(confirmations), max(confirmations)],
        'search_actual_development_evaluations': search['environment_attempts'],
        'timeline_raw_records_checked': 2, 'embedded_figures': 3, 'faq_items': len(faqs),
        'new_environment_evaluations': 0, 'new_research_model_calls': 0, 'new_training': 0,
        'html_sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
        'source_sha256': SOURCES,
        'scope': 'Numerical and source checks. Browser rendering and interaction are checked separately.',
    }
    (PAPER / 'generated/briefing-manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(f'Built {destination.relative_to(ROOT)}: 4 screens, 3 embedded figures, 7 FAQs; no new research runs.')


if __name__ == '__main__':
    main()
