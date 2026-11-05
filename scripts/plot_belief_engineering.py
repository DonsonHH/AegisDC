"""Draw ticket 18 SVGs directly from the two saved engineering outputs."""
from hashlib import sha256
from html import escape
import json


def svg(data, title, subtitle, width, height):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        f'<title>{escape(title)}</title>',
        f'<metadata>Engineering data SHA-256 {sha256(data).hexdigest()}</metadata>',
        '<rect width="100%" height="100%" fill="#f7f9fc"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#162b42}.title{font-size:25px;font-weight:bold}.label{font-size:16px;font-weight:bold}.tick{font-size:13px}.note{font-size:15px;fill:#456079}</style>',
        label(36, 39, title, 'title'),
        label(36, 66, subtitle, 'note'),
    ]


def label(x, y, value, style='tick', align='start'):
    return f'<text x="{x}" y="{y}" class="{style}" text-anchor="{align}">{escape(str(value))}</text>'


def line(x1, y1, x2, y2):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#c6d2e1"/>'


def points(coordinates):
    return ' '.join(f'{x:.3f},{y:.3f}' for x, y in coordinates)


def encode(lines):
    return ('\n'.join([*lines, '</svg>']) + '\n').encode('utf-8')


def archive_figure(raw):
    archive = json.loads(raw)
    frames = archive['frames']
    output = svg(raw, 'Archived V6 public observations | belief trajectory',
                 f"{len(frames)} saved decision instants from {archive['input_record_count']:,} public records · synthetic facility",
                 1070, 616)
    states = [('nominal', 'Nominal', '#007b9c'), ('cooling-limited', 'Cooling-limited', '#8448a4'),
              ('power-limited', 'Power-limited', '#b45319'), ('other', 'Other / compound', '#287d57')]
    for index, (state, name, color) in enumerate(states):
        left, top = 82 + index % 2 * 510, 111 + index // 2 * 224
        width, height = 406, 154
        right, bottom = left + width, top + height

        def x(time):
            return left + time / 242 * width

        def y(probability):
            return bottom - probability * height

        output.append(label(left, top - 10, name, 'label'))
        for tick in (0, .25, .50, .75, 1):
            output += [line(left, y(tick), right, y(tick)), label(left - 8, y(tick) + 4, f'{tick:.2f}', align='end')]
        for tick in (0, 60, 120, 180, 240):
            output += [line(x(tick), top, x(tick), bottom), label(x(tick), bottom + 20, tick, align='middle')]
        band = [(x(row['as_of_s']), y(row['assumption_envelope'][state][1])) for row in frames]
        band += [(x(row['as_of_s']), y(row['assumption_envelope'][state][0])) for row in reversed(frames)]
        posterior = [(x(row['as_of_s']), y(row['posterior'][state])) for row in frames]
        output += [
            f'<polygon points="{points(band)}" fill="{color}" opacity="0.19"/>',
            f'<polyline points="{points(posterior)}" fill="none" stroke="{color}" stroke-width="2.4"/>',
        ]
        output += [f'<circle cx="{cx:.3f}" cy="{cy:.3f}" r="2.6" fill="{color}"/>' for cx, cy in posterior]
    output += [
        label(536, 543, 'Decision time (s)', 'label', 'middle'),
        label(36, 573, 'Points show saved posterior probabilities. Connecting lines guide the eye.', 'note'),
        label(36, 595, 'Bands show the range across declared likelihood variants. Field calibration is pending.', 'note'),
    ]
    return encode(output)


def calibration_figure(raw):
    data = json.loads(raw)
    scores = data['true_law_weighted_multiclass_brier']
    wrong = data['deliberately_wrong_comparators']
    output = svg(raw, 'Exact finite generator | weighted multiclass Brier score',
                 f"{data['atom_count']} weighted atoms · {len(data['pattern_rows'])} conditional report patterns · lower score is better",
                 1020, 422)
    rows = [
        ('No reports arrived', scores['no-reports']['inference'], '#657992'),
        ('Delayed hot report arrived', scores['arrived-hot-only']['inference'], '#42849a'),
        ('Both eligible reports arrived', scores['both-arrived']['inference'], '#007b9c'),
        ('Wrong epoch for delayed report', wrong['late-hot-at-current']['weighted_multiclass_brier_decimal'], '#b45319'),
        ('Copy counted as independent', wrong['duplicate-hot-as-independent']['weighted_multiclass_brier_decimal'], '#b45319'),
    ]
    left, right = 340, 908

    def x(value):
        return left + value / .75 * (right - left)

    for tick in (0, .15, .30, .45, .60, .75):
        output += [line(x(tick), 91, x(tick), 338), label(x(tick), 361, f'{tick:.2f}', align='middle')]
    for index, (name, value, color) in enumerate(rows):
        y = 116 + index * 49
        output += [
            label(left - 16, y + 5, name, 'label', 'end'),
            f'<rect x="{left}" y="{y - 10}" width="{x(value) - left:.3f}" height="20" fill="{color}"/>',
            label(x(value) + 8, y + 5, f'{value:.6f}'),
        ]
    output.append(label(36, 397, 'All five scores use the same declared generating law. Orange marks deliberate error checks.', 'note'))
    return encode(output)


def render(directory):
    return {
        'archived-posterior.svg': archive_figure((directory / 'archived-trajectory.json').read_bytes()),
        'finite-calibration.svg': calibration_figure((directory / 'calibration.json').read_bytes()),
    }
