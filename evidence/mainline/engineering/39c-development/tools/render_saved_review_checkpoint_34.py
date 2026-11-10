"""Render saved review qualification only; no project runtime, inference or facility calls."""

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import socket
import sys
import traceback
import zipfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save_json(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def qualification_figure(plt, rows, result, output):
    colors = {'FALSE_ALARM_REVIEWED': '#009E73', 'RISK_ACCEPTED': '#0072B2',
              'ESCALATED': '#D55E00', 'OPEN_UNCONFIRMED': '#777777', 'INPUT_REFUSED': '#CC79A7'}
    labels = {'FALSE_ALARM_REVIEWED': 'False alarm reviewed', 'RISK_ACCEPTED': 'Risk accepted',
              'ESCALATED': 'Escalated; open', 'OPEN_UNCONFIRMED': 'Open; unconfirmed',
              'INPUT_REFUSED': 'Declaration refused'}
    states = list(colors)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), gridspec_kw={'width_ratios': [1, 1.2]})
    ax = axes[0]
    counts = [result['status_counts'].get(state, 0) for state in states]
    ax.barh(range(len(states)), counts, color=[colors[s] for s in states], height=.6)
    ax.set_yticks(range(len(states)), [labels[s] for s in states])
    ax.invert_yaxis()
    ax.set_xlim(0, max(counts) + 3)
    ax.set_xticks([0, 4, 8, 12, 16, 20])
    ax.set_xlabel('Declared qualification conditions (count)')
    ax.set_title('A   All 24 frozen conditions', loc='left', fontweight='bold')
    for y, value in enumerate(counts):
        ax.text(value + .3, y, str(value), va='center', fontsize=11)
    ax.grid(axis='x', color='#dddddd', zorder=0)
    ax.set_axisbelow(True)
    for side in ('top', 'right', 'left'):
        ax.spines[side].set_visible(False)

    ax = axes[1]
    selected = [row for row in rows if row['historical_event_count']]
    assert len(selected) == 3
    for y, row in enumerate(selected):
        event, = row['historical_dispositions']
        prior_time = event['arrived_at_s']
        ax.plot([prior_time, 8], [y, y], color='#bdbdbd', lw=2)
        ax.scatter([prior_time], [y], marker='o', color='#009E73', s=60, zorder=3)
        ax.scatter([8], [y], marker='x', color='#777777', s=65, zorder=3)
        ax.text(prior_time - .015, y + .18, 'historical review valid', ha='right', fontsize=8)
        ax.text(8 + .015, y + .18, 'current open', ha='left', fontsize=8)
    ax.set_yticks(range(3), [row['case'].replace('_', ' ') for row in selected])
    ax.invert_yaxis()
    ax.set_ylim(2.6, -.5)
    ax.set_xlim(7.38, 8.19)
    ax.set_xticks([7.5, 7.75, 8])
    ax.set_xlabel('Public evidence time (s)')
    ax.set_title('B   History retained; current closure rejected', loc='left', fontweight='bold')
    ax.grid(axis='x', color='#dddddd')
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    fig.suptitle('Instance review: saved engineering qualification', fontsize=15, fontweight='bold')
    fig.text(.5, .02, 'One qualification cohort; 24 public calls; 0 facility runs. Counts are not research sample sizes or gains.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=[0, .09, 1, .91], w_pad=2.5)
    for ext in ('png', 'svg'):
        fig.savefig(output / ('review-qualification.' + ext), dpi=220,
                    metadata={'Creator': 'AegisDC saved-result renderer'})
    plt.close(fig)


def architecture_figure(plt, output):
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis('off')

    def box(x, y, w, h, text, color):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.12',
                                   facecolor=color, edgecolor='#405060', linewidth=1))
        ax.text(x + w / 2, y + h / 2, text, ha='center', va='center', fontsize=10, linespacing=1.45)

    def arrow(start, end, text=None):
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle='-|>', mutation_scale=13,
                                    color='#405060', linewidth=1.3))
        if text:
            ax.text((start[0] + end[0])/2, (start[1] + end[1])/2 + .12,
                    text, ha='center', fontsize=8)

    ax.text(6, 7.7, 'Public review and physical verification remain separate', ha='center',
            fontsize=16, fontweight='bold')
    box(.35, 6.35, 3.1, .75, 'Private eight-domain plant\nLocal automatic protection', '#eeeeee')
    box(4.2, 6.35, 3.1, .75, 'Arrived public records\nSource / clock / provenance', '#e3f1fb')
    box(8.05, 6.35, 3.4, .75, 'Actual question instance\nOrigin / trigger / opening / slot', '#e3f1fb')
    arrow((3.6, 6.72), (4.05, 6.72))
    arrow((7.45, 6.72), (7.9, 6.72))
    box(.45, 3.95, 4.8, 1.3,
        'Physical sampled verification\nOwn completed action + own recheck\nCondition AND service samples / declared span', '#dff0e7')
    box(6.35, 3.95, 5.1, 1.3,
        'Management review\nExact record + instance + valid authority\nFALSE_ALARM additionally needs original + dossier', '#fff0dc')
    arrow((9.1, 6.18), (8.9, 5.4))
    arrow((8.1, 6.18), (3.2, 5.4))
    box(.45, 2.0, 3.2, .9, 'VERIFIED_CLOSED\nDeclared evidence criteria met', '#dff0e7')
    box(4.3, 2.0, 3.1, .9, 'ACCEPT_RISK / FALSE_ALARM\nManagement question closed', '#e3f1fb')
    box(8.05, 2.0, 3.4, .9, 'ESCALATE\nQuestion stays open', '#fde5dc')
    arrow((2.7, 3.8), (2.05, 3.05))
    arrow((8, 3.8), (5.9, 3.05))
    arrow((9.8, 3.8), (9.8, 3.05))
    box(.5, .35, 5.25, .75, 'Current question status -> stage gate -> shared resource budget\nA past valid decision does not close the current question', '#f1f4f7')
    box(6.5, .35, 4.9, .75, 'Historical projection: actual identity at public arrival clock\nStored separately; no private truth or physical effect', '#f1f4f7')
    arrow((2.05, 1.85), (2.8, 1.25))
    arrow((5.7, 1.85), (4.0, 1.25))
    arrow((9.8, 1.85), (5.2, 1.25))
    ax.text(8.9, 1.45, 'All management dispositions keep risk_closed=false\nNo physical-restoration claim; escalation has precedence',
            ha='center', fontsize=8, color='#405060')
    fig.text(.5, .01, 'Runtime architecture for the finite 39c review slice. Engineering qualification is not a measured service gain.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=[0, .035, 1, 1])
    for ext in ('png', 'svg'):
        fig.savefig(output / ('review-architecture.' + ext), dpi=220,
                    metadata={'Creator': 'AegisDC saved-result renderer'})
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
            or platform.python_version() != '3.12.7'
            or not Path('/root/private_data').is_mount() or os.environ.get('SLURM_JOB_ID')
            or args.output.resolve() != Path(manifest['output_root']).resolve()
            or not args.output.resolve().is_relative_to(root)):
        raise SystemExit('Frozen figure environment/output identity differs')
    for name, expected in manifest['software'].items():
        if version(name) != expected:
            raise SystemExit('Frozen figure package version differs: ' + name)
    args.output.mkdir(mode=0o700, exist_ok=False)
    terminal = dict(status='FAILED', source=manifest['source_commit'], new_facility_calls=0,
                    new_public_choice_calls=0, new_research_trials=0)
    save_json(args.output / 'attempt.json', dict(
        manifest_sha256=sha(manifest_bytes), source=manifest['source_commit'],
        started_utc=datetime.now(timezone.utc).isoformat(), hostname=socket.gethostname(),
        software=manifest['software'], classification='SAVED_ONLY_FIGURES_NOT_RESEARCH'))
    try:
        snapshot_bytes = args.snapshot.read_bytes()
        if sha(snapshot_bytes) != manifest['snapshot_sha256']:
            raise ValueError('Figure source archive differs')
        with zipfile.ZipFile(args.snapshot) as archive:
            if sorted(archive.namelist()) != sorted(manifest['files']):
                raise ValueError('Declared figure source paths differ')
            sources = {name: archive.read(name) for name in archive.namelist()}
        for name, spec in manifest['files'].items():
            if len(sources[name]) != spec['bytes'] or sha(sources[name]) != spec['sha256']:
                raise ValueError('Figure input hash differs: ' + name)
        result = json.loads(sources[manifest['summary']])
        rows = json.loads(sources[manifest['conditions']])
        if result['conditions'] != len(rows) or result['conditions'] != 24 or not all(row['passed'] for row in rows):
            raise ValueError('Frozen saved qualification summary differs')
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                             'svg.fonttype': 'none', 'axes.titlesize': 11})
        qualification_figure(plt, rows, result, args.output)
        architecture_figure(plt, args.output)
        if sha(args.manifest.read_bytes()) != sha(manifest_bytes) or sha(args.snapshot.read_bytes()) != manifest['snapshot_sha256']:
            raise ValueError('Frozen figure inputs changed during rendering')
        terminal['status'] = 'SAVED_FIGURES_RENDERED'
    except BaseException as error:
        terminal.update(error=repr(error), traceback=traceback.format_exc())
        raise
    finally:
        terminal.update(finished_utc=datetime.now(timezone.utc).isoformat(),
                        output_files={path.name: dict(bytes=path.stat().st_size, sha256=sha(path.read_bytes()))
                                      for path in args.output.iterdir() if path.is_file()})
        save_json(args.output / 'terminal.json', terminal)
    print(json.dumps(terminal))


if __name__ == '__main__':
    main()
