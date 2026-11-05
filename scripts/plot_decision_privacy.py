"""Data SVGs read only the frozen private engineering audit and public inputs."""
import argparse
from collections import Counter
from html import escape
import json
from pathlib import Path


def document(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def canvas(width, height, title, subtitle):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f5f7fb"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#17243a}.muted{fill:#52647b}</style>',
        f'<text x="32" y="40" font-size="24" font-weight="bold">{escape(title)}</text>',
        f'<text x="32" y="67" font-size="13" class="muted">{escape(subtitle)}</text>']


def text(rows, x, y, value, size=14, **attributes):
    attrs = ' '.join(f'{key.replace("_", "-")}="{escape(str(value))}"' for key, value in attributes.items())
    rows.append(f'<text x="{x}" y="{y}" font-size="{size}" {attrs}>{escape(str(value))}</text>')


def render(directory, output):
    directory, output = Path(directory), Path(output)
    summary = document(directory / 'audit/audit-summary.json')
    nominal = document(directory / 'fixture-copy/public-nominal.json')
    plan = document(directory / 'fixture-copy/public-plan.json')
    traces = {(world, stream): document(directory / f'audit/evaluator-traces/{world}/{stream}/private-decision-trace.json')
              for world in ('A', 'B') for stream in ('common', 'open', 'closed')}
    rows = canvas(1360, 840, 'Hidden worlds differ; current public inputs stay equal',
        'Actual full V6 engineering runs, 7 s at maximum step 0.01 s. Evaluator-only results; no policy effect or research gain.')
    text(rows, 32, 110, 'PRIVATE PLANT WITNESSES', 16, font_weight='bold')
    for index, world in enumerate(('A', 'B')):
        result = summary['private_worlds'][world]
        y = 154 + index * 130
        text(rows, 32, y, f'World {world}', 17, font_weight='bold')
        service = result['delivered_service_unit_s']
        rows.append(f'<rect x="170" y="{y-19}" width="{max(service * 80, 2)}" height="27" fill="{"#247f75" if world == "A" else "#c45b54"}"/>')
        text(rows, 750, y, f'{service:g} service unit s delivered', 16)
        text(rows, 170, y + 36, f'Floor water: {result["floor_mass_kg"]:g} kg; compute permit: {str(result["compute_permitted"]).lower()}; domains: {len(result["domain_ids"])}; state points: {result["state_points"]}')
        reason = result['job'].get('reason')
        text(rows, 170, y + 62, f'Private work: {result["job"]["status"]}' + (f' ({reason})' if reason else '') + f'; local mode: {result["local_control_mode"]}')
    text(rows, 32, 421, 'PUBLIC CURRENT-FRAME TRACE', 16, font_weight='bold')
    times = plan['decision_times_s']
    text(rows, 32, 451, 'Public ticks do not include private events at ' + ', '.join(f'{time:g} s' for time in summary['private_event_times']), 13)
    columns = [375 + index * 150 for index in range(len(times))]
    labels = [repr(time) + ' s' for time in times]
    for x, label in zip(columns, labels):
        text(rows, x, 488, label, 12, text_anchor='middle')
    for index, stream in enumerate(('common', 'open', 'closed')):
        y = 536 + index * 72
        text(rows, 32, y, stream + ': A = B at every tick', 14)
        for x, step in zip(columns, traces['A', stream]['steps']):
            choice = step['options']['demo_choice_id']
            it = choice == 'intent-it-check'
            rows.append(f'<rect x="{x-61}" y="{y-23}" width="122" height="38" rx="7" fill="{"#d5ece7" if it else "#f7dfbb"}"/>')
            text(rows, x, y, 'IT check' if it else 'Filter check', 13, text_anchor='middle')
            text(rows, x, y+32, f'{len(step["frame"]["evidence"]["records"])} arrived records', 11, text_anchor='middle')
    text(rows, 32, 776, 'Only the arrived, hand-authored restriction at 6 s changes the closed-stream planning intention. Crossed world/stream inputs follow the same records.', 13)
    text(rows, 32, 804, 'All options: execution_permission = false; physical_feasibility = UNVERIFIED. Actual M1 safety remains private and unchanged.', 13)
    rows.append('</svg>')
    (output / 'hidden-world-witness.svg').write_text('\n'.join(rows) + '\n', encoding='utf-8', newline='\n')

    domains = Counter(row['domain'] for row in nominal['entities'])
    rows = canvas(1360, 920, 'One facility identity; separate evaluator and consumer inputs',
        f'{len(nominal["entities"])} canonical V6 entities; {len(nominal["domain_ids"])} operational domains; {len(nominal["graphs"])} relation graphs. Counts come from the delivered inputs/results.')
    boxes = [(32, 108, 404, 244, 'Independent canonical public nominal'),
             (476, 108, 374, 244, 'Evaluator-owned clock and ledger'),
             (890, 108, 438, 244, 'Pure consumer: current JSON frame')]
    for x, y, width, height, title in boxes:
        rows.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="12" fill="#ffffff" stroke="#bfccde"/>')
        text(rows, x+18, y+31, title, 16, font_weight='bold')
    text(rows, 50, 171, 'No current parameter overrides or events')
    for index, (kind, edges) in enumerate(nominal['graphs'].items()):
        direction = f'; {sum(row["bidirectional"] for row in edges)} bidirectional' if kind == 'access' else ''
        text(rows, 50, 205+index*29, f'{kind}: {len(edges)} relations{direction}', 13)
    ledger = document(directory / 'fixture-copy/common-ledger.json')
    text(rows, 494, 171, f'{len(ledger["sources"])} sources; {len(ledger["observables"])} observables')
    text(rows, 494, 205, f'{len(times)} fixed public ticks per stream')
    text(rows, 494, 239, 'Only evaluator advances next_frame()')
    text(rows, 494, 273, 'Sparse records retain time and provenance')
    text(rows, 494, 307, 'No consumer future-time query handle')
    text(rows, 908, 171, f'{len(plan["requests"])} predeclared preparation intentions')
    text(rows, 908, 205, 'decision_options(frame)')
    text(rows, 908, 239, 'public_feasibility(frame, request_id)')
    text(rows, 908, 273, 'Nominal capability + current report mask')
    text(rows, 908, 307, 'No execution permission or plant object')
    for x in (446, 860):
        rows.append(f'<path d="M{x} 230h25m-7-7 7 7-7 7" fill="none" stroke="#247f75" stroke-width="3"/>')
    rows.append('<rect x="32" y="390" width="1296" height="150" rx="12" fill="#e6edf6" stroke="#a9bcd4"/>')
    text(rows, 50, 424, 'PRIVATE EVALUATOR / PLANT: actual state, local automatic protection, real access and private work occupation', 16, font_weight='bold')
    text(rows, 50, 458, f'{summary["physical_runs"]} distinct full-facility runs + {summary["offline_trace_commands"]} isolated public-input CLI traces; no world object is a consumer argument.')
    text(rows, 50, 492, 'No automatic state-to-record or rejection-to-report path. Tickets 16/17 and later execution must declare an observation channel and arrival time.')
    text(rows, 50, 520, 'Saved plant runs and accumulated hindsight traces are evaluator artifacts, rejected by the current-frame consumer interface.', 13)
    text(rows, 32, 585, 'Shared identities across all eight domains', 17, font_weight='bold')
    for index, name in enumerate(nominal['domain_ids']):
        column, row = index % 2, index // 2
        y, x = 625 + row * 48, 50 + column * 646
        text(rows, x, y, name, 14)
        count = domains[name]
        rows.append(f'<rect x="{x+285}" y="{y-17}" width="{count*20}" height="22" fill="#5279b2"/>')
        text(rows, x+300+count*20, y, str(count), 14)
    text(rows, 32, 851, 'Hand-authored public streams are engineering inputs, not sensor/worker observations generated from these runs. Inspection/action/effect mechanisms remain later work.', 13)
    text(rows, 32, 883, 'Registered research trials = 0; model calls = 0; training calls = 0. M3 and the complete-facility research objective remain active.', 13)
    rows.append('</svg>')
    (output / 'decision-boundary-architecture.svg').write_text('\n'.join(rows) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    render(args.directory, args.output)
