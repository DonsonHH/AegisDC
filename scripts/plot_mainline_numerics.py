"""Plot scientific convergence/representation diagnostics from saved originals."""
from hashlib import sha256
import json
from pathlib import Path


def render(directory):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    assessment = json.loads((directory / 'assessment.json').read_text(encoding='utf-8'))
    index = json.loads((directory / 'runs-index.json').read_text(encoding='utf-8'))
    phase = json.loads((directory / 'phase-domain.json').read_text(encoding='utf-8'))
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9, 'svg.fonttype': 'none'})
    figure, axes = plt.subplots(3, 2, figsize=(11.5, 11), constrained_layout=True)
    for number, (name, item) in enumerate(assessment['cases'].items()):
        rows = sorted(((float(step), row) for step, row in item['comparisons'].items() if float(step) != .01), reverse=True)
        color = plt.get_cmap('tab20')(number)
        for axis, suffix, label in [(axes[0, 0], '_K', 'Temperature error (K)'),
                                    (axes[0, 1], '_Pa', 'Pressure error (Pa)'),
                                    (axes[1, 0], '_W', 'Held heat-flow error (W)')]:
            values = [max(v for key, v in row['maximum_absolute_series_error'].items() if key.endswith(suffix)) for _, row in rows]
            axis.loglog([h for h, _ in rows], [max(v, 1e-12) for v in values], '.-', label=name, linewidth=1, color=color)
            axis.set_ylabel(label)
        values = [max([*row['absolute_integral_error'].values(), row['maximum_switch_time_error_s'] or 0]) for _, row in rows]
        axes[1, 1].loglog([h for h, _ in rows], [max(v, 1e-14) for v in values], '.-', linewidth=1, label=name, color=color)
    axes[0, 0].axhline(.05, color='black', linestyle='--', linewidth=.8)
    axes[0, 1].axhline(1000, color='black', linestyle='--', linewidth=.8)
    axes[1, 0].axhline(25000, color='black', linestyle='--', linewidth=.8)
    axes[1, 1].axhline(.001, color='black', linestyle='--', linewidth=.8)
    axes[1, 1].set_ylabel('Deficit / occupation / switch error (s)')
    axes[1, 1].text(.03, .94, 'Numerical zeros shown at 1e-14 s', transform=axes[1, 1].transAxes, va='top', fontsize=8)
    analytic = sorted((float(h), row['analysis']['metrics']['analytic_max_temperature_error_K'])
                      for h, row in index['isolated-room'].items())
    axes[2, 0].loglog([h for h, _ in analytic], [v for _, v in analytic], 'o-', label='Exact ODE comparison')
    axes[2, 0].loglog([h for h, _ in analytic], [analytic[-1][1] * h / analytic[-1][0] for h, _ in analytic], '--', label='Slope 1 guide')
    axes[2, 0].axhline(.005, color='black', linestyle=':', label='Independent analytic limit')
    axes[2, 0].set_ylabel('Isolated-room analytic error (K)')
    axes[2, 0].legend(fontsize=8)
    for status, color in [('RETURNED', '#136f63'), ('REFUSED', '#bc3f43')]:
        rows = [r for r in phase['neighborhoods'] if r['outcome']['status'] == status]
        axes[2, 1].scatter([r['volume_ulp_offset'] for r in rows],
            [(r['encoded_quality_at_nominal_pressure'] - 1) / np.spacing(1.) for r in rows],
            s=11, alpha=.45, color=color, label=status)
    axes[2, 1].axhline(0, color='black', linewidth=.6)
    axes[2, 1].set_xlabel('Input volume offset (binary64 ULP)')
    axes[2, 1].set_ylabel('Encoded nominal quality excess / ULP(1)')
    axes[2, 1].legend(fontsize=8)
    axes[2, 1].set_title('Five preserved refusals: local representation probes')
    for axis in list(axes.flat)[:5]:
        axis.set_xlabel('Maximum integration step (s)')
        axis.grid(alpha=.2, which='both')
    axes[0, 0].legend(fontsize=7, loc='best')
    figure.suptitle('Same complete V6 facility: finite numerical qualification\n0.01 s comparison reference omitted from upper plots; engineering fixtures', fontsize=13)
    folder = directory / 'figures'
    folder.mkdir(exist_ok=False)
    for suffix in ('.png', '.svg'):
        figure.savefig(folder / ('numerical-qualification' + suffix), dpi=160)
    plt.close(figure)
    receipt = dict(matplotlib=matplotlib.__version__, numpy=np.__version__,
        author_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        inputs={name: sha256((directory / name).read_bytes()).hexdigest() for name in ('assessment.json', 'runs-index.json', 'phase-domain.json')},
        outputs={path.name: sha256(path.read_bytes()).hexdigest() for path in folder.iterdir()})
    (folder / 'numerical-qualification.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8', newline='\n')
    return receipt
