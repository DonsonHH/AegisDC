"""Reproducible standard-library SVGs from the frozen ticket-14 input stream."""
import argparse
from collections import Counter
from html import escape
import json
from pathlib import Path


def _svg(width, height, title, subtitle):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="#f6f8fc"/>',
            '<style>text{font-family:Arial,sans-serif;fill:#17243a} .muted{fill:#52647b}</style>',
            f'<text x="32" y="40" font-size="23" font-weight="bold">{escape(title)}</text>',
            f'<text x="32" y="67" font-size="13" class="muted">{escape(subtitle)}</text>']


def render(document, output):
    records = document['records']
    rows = _svg(1320, 200 + 46 * len(records), 'Evidence arrival and observation time',
                'Engineering input stream. Display window [-5, 30] s; arrows mark either off-scale end. Exact seconds appear in each row.')
    minimum, maximum, left, scale = -5, 30, 350, 25

    def x(value):
        return left + (max(minimum, min(maximum, value)) - minimum) * scale

    def marker(value, y, color, shape):
        position = x(value)
        if value < minimum or value > maximum:
            direction = -1 if value < minimum else 1
            tip, base = position + direction * 2, position - direction * 6
            rows.append(f'<path d="M{base} {y - 6}L{tip} {y}L{base} {y + 6}Z" fill="{color}"/>')
            if value > maximum:
                rows.append(f'<text x="{position + 10}" y="{y + 4}" font-size="11" fill="{color}">{value:g} s</text>')
        elif shape == 'circle':
            rows.append(f'<circle cx="{position}" cy="{y}" r="5" fill="{color}"/>')
        elif shape == 'square':
            rows.append(f'<rect x="{position - 5}" y="{y - 5}" width="10" height="10" fill="{color}"/>')
        else:
            rows.append(f'<path d="M{position} {y - 8}V{y + 8}" stroke="{color}" stroke-width="2"/>')

    bottom = 110 + 46 * len(records)
    for tick in range(-5, 31, 5):
        position = x(tick)
        rows += [f'<path d="M{position} 100V{bottom}" stroke="#d7e0ed"/>',
                 f'<text x="{position}" y="92" font-size="12" text-anchor="middle">{tick} s</text>']
    for index, record in enumerate(records):
        y = 124 + index * 46
        observed, arrived, until = record['observed_at_s'], record['arrived_at_s'], record['valid_until_s']
        label = record['id'] + (' (missing)' if record['value'] is None else '')
        rows.append(f'<text x="32" y="{y + 4}" font-size="13">{escape(label)}</text>')
        rows.append(f'<path d="M{x(observed)} {y}H{x(arrived)}" stroke="#5279b2" stroke-width="3"/>')
        marker(observed, y, '#5279b2', 'circle')
        marker(arrived, y, '#d06e2b', 'square')
        if until is not None:
            marker(until, y, '#ab3a52', 'bar')
        detail = f'observed {observed:g}; arrived {arrived:g}; expires ' + ('never' if until is None else f'{until:g}')
        rows.append(f'<text x="350" y="{y + 19}" font-size="10" class="muted">{escape(detail)}</text>')
    rows.append(f'<text x="32" y="{bottom + 39}" font-size="13">Blue = observed; orange = arrived; red = exclusive expiry. Arrival never resets age.</text>')
    rows.append(f'<text x="32" y="{bottom + 61}" font-size="13">Arrows indicate off-scale times, not the -5 s or 30 s tick; exact times are printed per row.</text>')
    rows.append('</svg>')
    (output / 'arrival-timeline.svg').write_text('\n'.join(rows) + '\n', encoding='utf-8', newline='\n')

    counts = Counter(source['kind'] for source in document['sources'])
    architecture = _svg(1320, 650, 'Declared sources to decision-time evidence',
                        f'{len(document["entity_ids"])} shared V6 entity IDs; {counts["fixed_sensor"]} fixed sources; static engineering fixture only.')
    for index, (kind, count) in enumerate(counts.items()):
        y = 103 + index * 64
        architecture += [f'<rect x="32" y="{y}" width="270" height="46" rx="7" fill="#e0eaf8" stroke="#b8cae3"/>',
                         f'<text x="48" y="{y + 28}" font-size="15">{escape(kind)} ({count} declared)</text>',
                         f'<path d="M302 {y + 23}H360V325H410" fill="none" stroke="#7a92b5"/>']
    for x0, width, title, lines in [
        (410, 240, 'Closed SI ledger', ['Target / observable / source', 'Observed / arrived / validity', 'Value / quality / carried origin']),
        (710, 240, 'Strict as-of gate', ['Observed <= decision time', 'Arrived <= decision time', 'No epsilon; no future scan']),
        (1010, 278, 'Detached public snapshot', ['Current + audit records', 'Visible-only relations / conflicts', 'No plant, seed or input digest']),
    ]:
        architecture += [f'<rect x="{x0}" y="260" width="{width}" height="146" rx="9" fill="white" stroke="#5279b2" stroke-width="2"/>',
                         f'<text x="{x0 + 14}" y="287" font-size="17" font-weight="bold">{title}</text>']
        for index, line in enumerate(lines):
            architecture.append(f'<text x="{x0 + 14}" y="{318 + index * 28}" font-size="12">{escape(line)}</text>')
        if x0 < 1010:
            architecture.append(f'<path d="M{x0 + width} 325H{x0 + width + 60}" stroke="#5279b2" stroke-width="2"/>')
    architecture += ['<text x="410" y="475" font-size="15" font-weight="bold">Copy token survives a work order arriving before its alarm.</text>',
                     '<text x="410" y="503" font-size="13" class="muted">Shared provenance is visible; independent samples are not presumed.</text>',
                     '<text x="410" y="565" font-size="14">Private plant and future faults do not enter this interface.</text>', '</svg>']
    (output / 'source-architecture.svg').write_text('\n'.join(architecture) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    render(json.loads(args.fixture.read_text(encoding='utf-8')), args.output)
