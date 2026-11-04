"""Independent v2 error panels, preserving the original negative plots."""
from hashlib import sha256
import json
from pathlib import Path


def render(directory):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    assessment = json.loads((directory / 'assessment.json').read_text(encoding='utf-8'))
    protocol = json.loads((directory / 'protocol-copy.json').read_text(encoding='utf-8'))
    limits = protocol['limits']
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'svg.fonttype': 'none'})
    figure, axes = plt.subplots(2, 2, figsize=(11.5, 8), constrained_layout=True)
    for number, (name, item) in enumerate(assessment['cases'].items()):
        rows = sorted((float(h), row) for h, row in item['comparisons'].items() if float(h) != protocol['fine_reference_s'])
        color = plt.get_cmap('tab10')(number)
        for axis, suffix, label, threshold in [(axes[0, 0], '_K', 'Maximum temperature error (K)', .05),
                (axes[0, 1], '_Pa', 'Maximum pressure error (Pa)', 1000),
                (axes[1, 0], '_W', 'Maximum held heat-flow error (W)', 25000)]:
            values = [max(v for key, v in row['maximum_absolute_series_error'].items() if key.endswith(suffix)) for _, row in rows]
            axis.loglog([h for h, _ in rows], [max(v, 1e-12) for v in values], 'o-', label=name, color=color, markersize=4)
            axis.set_ylabel(label)
            if number == 0:
                axis.axhline(threshold, color='black', linestyle='--', linewidth=.8,
                             label='Candidate heat limit: 25 kW' if suffix == '_W' else None)
                axis.axhline(threshold * .25, color='grey', linestyle=':', linewidth=.8,
                             label='Reference self-check: 6.25 kW' if suffix == '_W' else None)
        ratios = [max(value / limits.get(key, limits['resource_time_s'])
                      for key, value in row['absolute_integral_error'].items()) for _, row in rows]
        axes[1, 1].loglog([h for h, _ in rows], [max(v, 1e-12) for v in ratios], 'o-', color=color, markersize=4)
    axes[1, 1].axhline(1, color='black', linestyle='--', linewidth=.8)
    axes[1, 1].set_ylabel('Integral error / own limit (dimensionless)')
    axes[1, 1].text(.03, .95, 'Dimensionless; event sequences/times reported separately', transform=axes[1, 1].transAxes, va='top', fontsize=8)
    axes[0, 0].legend(fontsize=8)
    axes[1, 0].legend(fontsize=8)
    for axis in axes.flat:
        axis.axvline(.01, color='grey', linestyle='-.', linewidth=.7)
        axis.set_xlabel('Maximum integration step (s)')
        axis.grid(alpha=.2, which='both')
    figure.suptitle('Full V6 refinement: epoch-consistent errors\n0.005 / 0.0025 s reference; causal raw and actual event-time errors retained in data', fontsize=12)
    folder = directory / 'figures'
    folder.mkdir(exist_ok=False)
    for suffix in ('.png', '.svg'):
        figure.savefig(folder / ('refinement' + suffix), dpi=160, bbox_inches='tight', pad_inches=.15)
    plt.close(figure)
    receipt = dict(toolchain=dict(matplotlib=matplotlib.__version__, numpy=np.__version__),
        author_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        inputs={name: sha256((directory / name).read_bytes()).hexdigest() for name in ('assessment.json', 'protocol-copy.json')},
        outputs={path.name: sha256(path.read_bytes()).hexdigest() for path in folder.iterdir()})
    (folder / 'refinement.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8', newline='\n')
    return receipt
