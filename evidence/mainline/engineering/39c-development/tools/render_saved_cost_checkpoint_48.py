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
    import csv
    by_id = {row['case']: row['costs'] for row in cases}
    records = [('Completed', by_id['completed']), ('Aborted', positive),
               ('Unfinished', by_id['unfinished']), ('No human', by_id['no-human']),
               ('Rejected', by_id['rejected']), ('Shared queue', by_id['shared-queue'])]
    fig, axes = plt.subplots(2, 2, figsize=(13.2, 8.1))
    labels = [name.replace(' ', chr(10)) for name, _ in records]
    values = lambda key: [cost['actual'][key]['value'] for _, cost in records]
    ax = axes[0, 0]
    work, waiting, travel = values('worker_work_person_s'), values('worker_wait_person_s'), values('worker_travel_person_s')
    ax.bar(range(6), work, color='#0072B2', label='Work')
    ax.bar(range(6), waiting, bottom=work, color='#E69F00', label='Waiting (includes gate / queue)')
    ax.bar(range(6), travel, bottom=[a+b for a,b in zip(work,waiting)], color='#009E73', label='Travel')
    for i, (_, cost) in enumerate(records):
        ax.text(i, cost['personnel_total']['value'] + .04, f"{cost['personnel_total']['value']:g}", ha='center', fontsize=9)
    ax.set_xticks(range(6), labels)
    ax.set_ylim(0, 2.25)
    ax.set_ylabel('Actual personnel use (person_s)')
    ax.set_title('A   Exclusive personnel time', loc='left', fontweight='bold')
    ax.legend(fontsize=8, loc='upper left')
    ax.grid(axis='y', color='#e3e8ec')
    ax.set_axisbelow(True)

    ax = axes[0, 1]
    occupation, tool_work = values('tool_occupation_tool_s'), values('tool_work_tool_s')
    ax.bar(range(6), occupation, width=.7, color='#d7e8f4', edgecolor='#0072B2', label='Occupation')
    ax.bar(range(6), tool_work, width=.38, color='#009E73', label='Working subset')
    ax.set_xticks(range(6), labels)
    ax.set_ylim(0, 1.6)
    ax.set_ylabel('Actual tool use (tool_s)')
    ax.set_title('B   Tool work within occupation', loc='left', fontweight='bold')
    ax.legend(fontsize=8, loc='upper right')
    ax.grid(axis='y', color='#e3e8ec')
    ax.set_axisbelow(True)

    ax = axes[1, 0]
    ax.axis('off')
    cells = []
    for name, cost in records:
        state = '; '.join(f"{k}: {v}" for k,v in cost['task_outcomes']['counts'].items()) or 'no issued task'
        fee = cost['issue_fees']['value']
        cells.append([name, state, 'n/a' if fee is None else f'{fee:g}'])
    table = ax.table(cellText=cells, colLabels=['Outcome', 'Task state at horizon', 'Declared issue fee'],
                     cellLoc='left', bbox=[0, .05, 1, .82], colWidths=[.23, .49, .28])
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    for (row,col), cell in table.get_celld().items():
        cell.set_edgecolor('white')
        cell.set_facecolor('#edf4fa' if row == 0 else '#f4f6f8')
    ax.set_title('C   Fees retain their declared unit; n/a stays distinct', loc='left', fontweight='bold')

    ax = axes[1, 1]
    completed = by_id['completed']
    actual, envelope = completed['personnel_total']['value'], completed['admission']['spent_or_reserved']['person_s']
    ax.barh([0, 1], [actual, envelope], color=['#0072B2', '#b4bdc7'])
    ax.set_yticks([0, 1], ['Actual use', 'Admission envelope'])
    ax.invert_yaxis()
    ax.set_xlim(0, 12)
    ax.set_xlabel('Personnel time / commitment (person_s)')
    for i,v in enumerate([actual,envelope]):
        ax.text(v+.15,i,f'{v:g}',va='center')
    ax.set_title('D   Completed task: measured use and reserved window', loc='left', fontweight='bold')
    ax.grid(axis='x',color='#e3e8ec')
    ax.set_axisbelow(True)
    for ax in (axes[0,0],axes[0,1],axes[1,1]):
        for side in ('top','right'):
            ax.spines[side].set_visible(False)
    fig.suptitle('Actual costs: failed work remains in the account', fontsize=15, fontweight='bold')
    fig.text(.5,.018,'Engineering qualification. Issued fees use declared research units. Monetary, distance and uninstrumented internal-call accounts remain unknown.',
             ha='center',fontsize=9)
    fig.tight_layout(rect=[0,.05,1,.95],h_pad=2.6,w_pad=2)
    for ext in ('png','svg'):
        fig.savefig(output/('actual-costs-and-outcomes.'+ext),dpi=220,metadata={'Creator':'AegisDC saved cost renderer48'})
    plt.close(fig)
    with (output/'actual-costs.csv').open('x',encoding='utf-8',newline='') as stream:
        writer=csv.writer(stream)
        writer.writerow(['outcome','work_person_s','wait_person_s','travel_person_s','person_total_s','tool_occupation_s','tool_work_s','issue_fee','fee_status','fee_unit'])
        for name,cost in records:
            writer.writerow([name,*[cost['actual'][k]['value'] for k in ('worker_work_person_s','worker_wait_person_s','worker_travel_person_s')],
                             cost['personnel_total']['value'],cost['actual']['tool_occupation_tool_s']['value'],
                             cost['actual']['tool_work_tool_s']['value'],cost['issue_fees']['value'],cost['issue_fees']['status'],cost['issue_fees']['unit']])


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
        software=manifest['software'], classification='SAVED_COST_DATA_ONLY_NOT_SIMULATION'))
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
        if len(cases) != 5 or not all(case['passed'] for case in cases):
            raise ValueError('Frozen boundary qualification differs')
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'svg.fonttype': 'none'})
        draw(plt, positive, cases, args.output)
        if sha(args.manifest.read_bytes()) != sha(manifest_bytes) or sha(args.snapshot.read_bytes()) != manifest['snapshot_sha256']:
            raise ValueError('Frozen rendering inputs changed')
        terminal['status'] = 'SAVED_COST_FIGURE_RENDERED'
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
