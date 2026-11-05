"""Standard-library SVG diagnostics from captured observation outputs only."""
from html import escape
from hashlib import sha256
import json
from pathlib import Path


def _canvas(width, height, title, detail):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="#f7f9fc"/>',
            '<style>text{font-family:Arial,sans-serif;fill:#17283e}</style>',
            f'<text x="34" y="38" font-size="23" font-weight="bold">{escape(title)}</text>',
            f'<text x="34" y="65" font-size="12">{escape(detail)}</text>']


def _polyline(rows, points, color, width=1.6):
    segment = []
    for point in points + [None]:
        if point is None:
            if segment:
                rows.append(f'<polyline points="{" ".join(segment)}" fill="none" stroke="{color}" stroke-width="{width}"/>')
                segment = []
        else:
            segment.append(f'{point[0]:.3f},{point[1]:.3f}')


def render(folder):
    profile = json.loads((folder / 'profile-copy.json').read_text(encoding='utf-8'))
    primary = json.loads((folder / 'cli-primary/production-private.json').read_text(encoding='utf-8'))
    mismatch = json.loads((folder / 'mismatch-production-private.json').read_text(encoding='utf-8'))
    output = folder / 'figures'
    output.mkdir(exist_ok=False)
    rows = _canvas(1400, 1040, 'Private saved signal and transferred instrument values',
        'Same complete V6, same external trace/draws; calibration mismatch is an engineering diagnostic, not a method gain.')
    for index, (measurement, channel, title, unit) in enumerate([
            ('coolant-probe', 'coolant-transfer', 'Coolant probe', 'K'),
            ('lake-flow', 'flow-transfer', 'Lake intake mass flow', 'kg/s'),
            ('rectifier-meter', 'power-transfer', 'Rectifier input meter', 'W')]):
        top, left, width, height = 110 + index * 285, 125, 1190, 205
        audit = [row for row in primary['private_audit'] if row['measurement_id'] == measurement]
        normal = [row for row in primary['ledger']['records'] if row['id'].startswith(channel + ':')]
        changed = [row for row in mismatch['ledger']['records'] if row['id'].startswith(channel + ':')]
        values = [row['private_signal'] for row in audit] + [row['value'] for row in normal + changed if row['value'] is not None]
        low, high = min(values), max(values)
        pad = max((high - low) * .12, .1)
        low, high = low - pad, high + pad
        x = lambda time: left + time / 240 * width
        y = lambda value: top + height - (value - low) / (high - low) * height
        rows.append(f'<text x="34" y="{top - 13}" font-size="17" font-weight="bold">{escape(title)} ({unit})</text>')
        for tick in range(0, 241, 40):
            rows += [f'<path d="M{x(tick)} {top}V{top + height}" stroke="#d9e1eb"/>',
                     f'<text x="{x(tick)}" y="{top + height + 20}" font-size="11" text-anchor="middle">{tick} s</text>']
        for fraction in (0, .5, 1):
            value = low + fraction * (high - low)
            rows += [f'<path d="M{left} {y(value)}H{left + width}" stroke="#e3e9f1"/>',
                     f'<text x="{left - 10}" y="{y(value) + 4}" font-size="11" text-anchor="end">{value:.6g}</text>']
        _polyline(rows, [(x(row['source_observed_at_s']), y(row['private_signal'])) for row in audit], '#6e7b89', 2.2)
        for series, color in [(normal, '#2479ae'), (changed, '#bd523e')]:
            _polyline(rows, [None if row['value'] is None else (x(row['observed_at_s']), y(row['value'])) for row in series], color)
    rows += ['<text x="125" y="986" font-size="13">Gray: private reference at observation epochs. Blue: nominal reported values. Red: private calibration mismatch.</text>',
             '<text x="125" y="1010" font-size="12">Missing readings break lines; curves join samples for display only. Actual delivery times are separate; dispatch never receives this private reference.</text>', '</svg>']
    (output / 'signal-and-error.svg').write_text('\n'.join(rows) + '\n', encoding='utf-8', newline='\n')

    rows = _canvas(1400, 650, 'Observed, transferred and missing controller/instrument records',
        'Actual captured epochs in 174-184 s. Circle=source observation; square=arrival; hollow arrival=missing reading.')
    x = lambda time: 330 + (time - 174) / 10 * 1020
    for tick in range(174, 185, 2):
        rows += [f'<path d="M{x(tick)} 100V555" stroke="#d5dfeb"/>',
                 f'<text x="{x(tick)}" y="91" font-size="12" text-anchor="middle">{tick} s</text>']
    for index, channel in enumerate(profile['channels']):
        y = 130 + index * 72
        selected = [row for row in primary['ledger']['records'] if row['id'].startswith(channel['id'] + ':')
                    and 174 <= row['observed_at_s'] <= 180]
        rows.append(f'<text x="25" y="{y + 4}" font-size="12">{escape(channel["id"])}</text>')
        for row in selected:
            a, b = x(row['observed_at_s']), x(row['arrived_at_s'])
            fill = 'white' if row['value'] is None else '#ca7430'
            rows += [f'<path d="M{a} {y}H{b}" stroke="#8ea4bd" stroke-width="2"/>',
                     f'<circle cx="{a}" cy="{y}" r="4" fill="#2479ae"/>',
                     f'<rect x="{b - 4}" y="{y - 4}" width="8" height="8" fill="{fill}" stroke="#ca7430"/>']
    rows += ['<text x="330" y="594" font-size="13">Invalid reported temperature remains missing; its reported validity is False, not numeric zero.</text>',
             '<text x="330" y="620" font-size="12">Arrival never refreshes source age. Same-report fields share an origin; no future point is interpolated.</text>', '</svg>']
    (output / 'delivery-and-missing.svg').write_text('\n'.join(rows) + '\n', encoding='utf-8', newline='\n')

    rows = _canvas(1400, 650, 'Static sparse coverage and explicit observation channels',
        '45 shared V6 entity IDs; 3 physical fixed points and 1 authorized reported-control group. This is not a health mask.')
    for index, measurement in enumerate(profile['measurements']):
        top = 112 + index * 120
        streams = [row for row in profile['channels'] if row['measurement_id'] == measurement['id']]
        title = measurement['target_id'] + ' / ' + measurement['signal']
        rows += [f'<rect x="35" y="{top}" width="510" height="76" rx="8" fill="#dfeaf7" stroke="#7596bc"/>',
                 f'<text x="52" y="{top + 27}" font-size="15" font-weight="bold">{escape(title)}</text>',
                 f'<text x="52" y="{top + 53}" font-size="12">Declared poll {measurement["period_s"]:g} s; static enabled={measurement["enabled"]}</text>']
        text = ', '.join(stream['observable_id'] for stream in streams)
        rows += [f'<path d="M545 {top + 38}H615" stroke="#5279b2" stroke-width="2"/>',
                 f'<rect x="615" y="{top}" width="740" height="76" rx="8" fill="white" stroke="#7596bc"/>',
                 f'<text x="633" y="{top + 27}" font-size="13">{escape(text)}</text>',
                 f'<text x="633" y="{top + 53}" font-size="12">{len(streams)} transfer streams; source/model assumptions do not reveal realized errors.</text>']
    rows += ['<text x="35" y="618" font-size="13">Other catalogued entities are not automatically observed. Raw/threshold packets of one probe share a measurement root.</text>', '</svg>']
    (output / 'static-coverage.svg').write_text('\n'.join(rows) + '\n', encoding='utf-8', newline='\n')
    names = ['profile-copy.json', 'cli-primary/production-private.json', 'mismatch-production-private.json']
    receipt = dict(author_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                   inputs={name: sha256((folder / name).read_bytes()).hexdigest() for name in names},
                   outputs={p.name: sha256(p.read_bytes()).hexdigest() for p in output.glob('*.svg')},
                   scope='PRIVATE_ENGINEERING_DIAGNOSTICS_NOT_DISPATCH_VIEW_OR_METHOD_GAIN')
    (folder / 'figure-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8', newline='\n')
    return receipt
