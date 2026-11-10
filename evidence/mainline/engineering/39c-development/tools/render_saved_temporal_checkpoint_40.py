"""Render the saved temporal qualification; no facility code is imported or executed."""
import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import socket
import traceback
import zipfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, obj):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(obj, stream, indent=2, allow_nan=False)
        stream.write('\n')


def draw(plt, positive, cases, output):
    temporal = positive['events'][0]['temporal_endpoints']
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), gridspec_kw={'width_ratios': [1, 1.5]})
    ax = axes[0]
    names = ['fault_reference', 'service_loss_reference', 'intervention_deadline_reference']
    labels = ['Capacity-state sample', 'Whole-service loss sample', 'Declared action deadline']
    colors = ['#0072B2', '#D55E00', '#009E73']
    for y, (name, color) in enumerate(zip(names, colors)):
        reference = temporal[name]
        interval = reference.get('transition_lead_interval_s')
        if interval:
            ax.plot(interval, [y, y], color=color, lw=2.5)
            ax.scatter(interval[0], y, facecolors='white', edgecolors=color, s=55, zorder=4)
        ax.scatter(reference['lead_s'], y, marker='s' if interval is None else 'o', color=color, s=55, zorder=4)
        ax.annotate(f"{reference['lead_s']:+.2f} s", (reference['lead_s'], y), xytext=(0, 15),
                    textcoords='offset points', ha='center', color=color, weight='bold')
    ax.axvline(0, color='#687a88', linestyle='--', lw=1)
    ax.set_yticks(range(3), labels)
    ax.set_ylim(2.5, -.7)
    ax.set_xlim(-2.05, 2.05)
    ax.set_xlabel('Reference minus public confirmation availability (s)')
    ax.set_title('A   Actual confirmation at 1.75 s', loc='left', fontweight='bold')
    ax.grid(axis='x', color='#e3e8ec')
    for side in ('top', 'right', 'left'):
        ax.spines[side].set_visible(False)

    ax = axes[1]
    ax.axis('off')
    status = {
        'NOT_OBSERVED_BY_LAST_SAMPLE': ('Right-censored', '#f0f1f3'),
        'PRESENT_AT_FIRST_SAMPLE': ('Left-censored', '#e5eff8'),
        'FIRST_TRANSITION_SAMPLE': ('Observed transition', '#e4f0e9'),
        'UNMODELED': ('Unmodeled', '#f3e8f2'),
    }
    text, fills = [], []
    for case in cases:
        row, colors_row = [], []
        actual = case['actual']
        for key in ('fault_reference', 'service_loss_reference'):
            ref = actual[key]
            label, color = status[ref['status']]
            row.append(label + ('\nlead unknown' if ref['lead_s'] is None else f"\n{ref['lead_s']:+.2f} s"))
            colors_row.append(color)
        deadline = actual['intervention_deadline_reference']
        row.append('Unmodeled\nlead unknown' if deadline['at_s'] is None else
                   f"Plan {deadline['at_s']:g} s\n" + ('no confirmation' if deadline['lead_s'] is None else f"lead {deadline['lead_s']:+.2f} s"))
        colors_row.append('#f3e8f2' if deadline['at_s'] is None else '#fff1da')
        text.append(row)
        fills.append(colors_row)
    table = ax.table(cellText=text, cellColours=fills, colLabels=['Fault reference', 'Service reference', 'Action deadline'],
                     rowLabels=['Window before fault', 'Fault already present', 'No human confirmation', 'Unknown truth / cutoff'],
                     cellLoc='center', rowLoc='right', bbox=[.22, .06, .78, .83])
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    for cell in table.get_celld().values():
        cell.set_edgecolor('white')
    ax.set_title('B   Four frozen boundary conditions: all passed', loc='left', fontweight='bold')
    fig.suptitle('Temporal references: delay, plan margin and censoring', fontsize=15, fontweight='bold')
    fig.text(.5, .025, 'Engineering qualification. Open/closed interval ends describe sampling brackets, not confidence intervals. Prevention effect remains unmeasured.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=[0, .09, 1, .92], w_pad=2.5)
    for ext in ('png', 'svg'):
        fig.savefig(output/('temporal-leads-and-censoring.' + ext), dpi=220,
                    metadata={'Creator': 'AegisDC saved temporal renderer40'})
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest_bytes = args.manifest.read_bytes()
    manifest = json.loads(manifest_bytes)
    root = Path('/root/private_data/aegisdc-mainline-39c').resolve()
    if (socket.gethostname() != manifest['hostname'] or os.geteuid() != 0
            or platform.python_version() != '3.12.7' or os.environ.get('SLURM_JOB_ID')
            or not Path('/root/private_data').is_mount()
            or args.output.resolve() != Path(manifest['output_root']).resolve()
            or not args.output.resolve().is_relative_to(root)):
        raise SystemExit('Frozen saved temporal rendering host/root differs')
    for name, expected in manifest['software'].items():
        if version(name) != expected:
            raise SystemExit('Frozen renderer distribution differs: ' + name)
    args.output.mkdir(mode=0o700, exist_ok=False)
    terminal = dict(status='FAILED', source=manifest['source_commit'], new_facility_calls=0,
                    new_public_choices=0, new_research_trials=0)
    save(args.output/'attempt.json', dict(source=manifest['source_commit'], manifest_sha256=sha(manifest_bytes),
        started_utc=datetime.now(timezone.utc).isoformat(), hostname=socket.gethostname(),
        software=manifest['software'], classification='SAVED_TEMPORAL_DATA_ONLY_NOT_SIMULATION'))
    try:
        if sha(args.snapshot.read_bytes()) != manifest['snapshot_sha256']:
            raise ValueError('Frozen renderer archive differs')
        with zipfile.ZipFile(args.snapshot) as archive:
            if sorted(archive.namelist()) != sorted(manifest['files']):
                raise ValueError('Frozen renderer source paths differ')
            data = {name: archive.read(name) for name in archive.namelist()}
        for name, record in manifest['files'].items():
            if sha(data[name]) != record['sha256'] or len(data[name]) != record['bytes']:
                raise ValueError('Frozen saved-data file differs: ' + name)
        positive = json.loads(data[manifest['positive']])
        cases = json.loads(data[manifest['qualification']])
        if len(cases) != 4 or not all(case['passed'] for case in cases):
            raise ValueError('Frozen boundary qualification differs')
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'svg.fonttype': 'none'})
        draw(plt, positive, cases, args.output)
        if sha(args.manifest.read_bytes()) != sha(manifest_bytes) or sha(args.snapshot.read_bytes()) != manifest['snapshot_sha256']:
            raise ValueError('Frozen rendering inputs changed')
        terminal['status'] = 'SAVED_TEMPORAL_FIGURE_RENDERED'
    except BaseException as error:
        terminal.update(error=repr(error), traceback=traceback.format_exc())
        raise
    finally:
        terminal.update(finished_utc=datetime.now(timezone.utc).isoformat(),
            output_files={path.name:dict(bytes=path.stat().st_size, sha256=sha(path.read_bytes()))
                          for path in args.output.iterdir() if path.is_file()})
        save(args.output/'terminal.json', terminal)
    print(json.dumps(terminal))


if __name__ == '__main__':
    main()
