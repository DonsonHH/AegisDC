"""Render pinned, saved execution witnesses in Slurm; never rerun the plant."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import traceback


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or socket.gethostname().split('.')[0] == 'mu01':
        raise SystemExit('Saved-data rendering requires a Slurm compute allocation')
    root = args.manifest.resolve().parent
    manifest_sha = digest(args.manifest)
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    args.output.mkdir(exist_ok=False)
    terminal = dict(status='FAILED', source_commit=manifest['source_commit'])
    save(args.output / 'attempt.json', dict(classification='SAVED_ENGINEERING_VISUALIZATION_NOT_RESEARCH_TRIAL',
        slurm_job_id=os.environ['SLURM_JOB_ID'], node=socket.gethostname(),
        source_commit=manifest['source_commit'], manifest_sha256=manifest_sha,
        started_at_utc=datetime.now(timezone.utc).isoformat(),
        facility_calls=0, model_calls=0, new_statistical_units=0))
    try:
        protocol = json.loads((root / 'protocol.json').read_text(encoding='utf-8'))

        def guard():
            if digest(args.manifest) != manifest_sha:
                raise ValueError('Render manifest changed')
            for name, record in manifest['files'].items():
                if (root / name).stat().st_size != record['bytes'] or digest(root / name) != record['sha256']:
                    raise ValueError('Render source/protocol changed: ' + name)
            for record in protocol['inputs'].values():
                path = Path(record['path'])
                if path.stat().st_size != record['bytes'] or digest(path) != record['sha256']:
                    raise ValueError('Saved input changed: ' + path.name)
        guard()
        if digest(Path(__file__)) != manifest['files']['render_problem_action_evidence.py']['sha256']:
            raise ValueError('Execute the pinned renderer')
        inputs = protocol['inputs']
        summaries = {key: json.loads(Path(inputs[key]['path']).read_text(encoding='utf-8'))
                     for key in ('network_summary', 'direct_summary', 'expiry_summary')}
        for key, summary in summaries.items():
            if summary['code_identity']['git_commit'] != inputs[key]['runtime_source'] or summary['code_identity']['implementation_has_changes']:
                raise ValueError('Saved runtime identity differs: ' + key)
        network = summaries['network_summary']
        direct = summaries['direct_summary']
        rows = {key: [json.loads(line) for line in Path(inputs[key]['path']).read_text(encoding='utf-8').splitlines()]
                for key in ('network_state', 'direct_state')}
        os.environ['MPLCONFIGDIR'] = str(root / 'matplotlib-cache')
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
        plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'svg.fonttype': 'none',
                             'svg.hashsalt': 'aegisdc39b-action-witnesses'})
        for key, data in rows.items():
            with (args.output / (key + '.csv')).open('x', encoding='utf-8', newline='') as stream:
                writer = csv.writer(stream, lineterminator='\n')
                writer.writerow(['facility_time_s', 'delivered_service_rate', 'demand_service_rate',
                                 'network_available_capacity', 'intake_volume_flow_m3_s'])
                writer.writerows((r['time_s'], r['domains']['it_service']['delivered'], r['domains']['it_service']['demand'],
                                  r['domains']['it_service']['capacities']['network'],
                                  r['domains']['facility_cooling']['lake_pump']['volume_flow_m3_s']) for r in data)

        def timeline(ax, summary, prefix, labels, end):
            tasks = {r['id']: r for r in summary['work_records']}
            for index, (suffix, label) in enumerate(labels):
                task = tasks[prefix + '/' + suffix + '-0']
                start, finish = task['work_started_at_s'], task['completed_at_s']
                ax.broken_barh([(start, finish - start)], (index - .23, .46), facecolors='#0f766e')
                ax.text((start + finish) / 2, index, label, color='white', ha='center', va='center', fontsize=10)
                if suffix in ('inspect', 'recheck'):
                    record = next(r for r in summary['inspection_records'] if r['observed_at_s'] == finish)
                    arrival = record['arrived_at_s']
                else:
                    arrival = next(r for r in summary['intervention_feedback'] if r['task_id'] == task['id'])['arrived_at_s']
                ax.broken_barh([(finish, arrival - finish)], (index - .23, .46), facecolors='#7c3aed')
                ax.scatter([task['issued_at_s']], [index], color='#334155', s=27, zorder=4)
                ax.text(finish, index + .32, f'{finish:g} sample' if suffix != 'action' else f'{finish:g} effect',
                        ha='center', va='top', fontsize=9, color='#0f766e')
                ax.text(arrival, index - .34, f'{arrival:g} arrived', ha='center', va='bottom', fontsize=9, color='#6d28d9')
            ax.set(xlim=(-.1, end), yticks=range(len(labels)), yticklabels=[label for _, label in labels],
                   xlabel='Facility time (s)', ylim=(-.75, len(labels) - .15))
            ax.invert_yaxis()
            ax.grid(axis='x', alpha=.15)

        data = rows['network_state']
        times = [r['time_s'] for r in data]
        delivered = [r['domains']['it_service']['delivered'] for r in data]
        demand = [r['domains']['it_service']['demand'] for r in data]
        fig, (ax, lower) = plt.subplots(2, 1, figsize=(13.5, 8.5), gridspec_kw={'height_ratios': [1, 1.7]})
        fig.subplots_adjust(left=.14, right=.96, top=.84, bottom=.13, hspace=.43)
        fig.suptitle('An arrived measurement opens a paid action and a genuine recheck', fontsize=17, y=.965)
        fig.text(.14, .90, 'Actual synthetic engineering trace | Slurm 133131 | capacity remains below full recovery', color='#475569')
        ax.plot(times, demand, color='#64748b', ls='--', label='External demand')
        ax.plot(times, delivered, color='#2563eb', lw=2.2, label='Actual delivered service')
        ax.fill_between(times, delivered, demand, alpha=.12, color='#dc2626', label='Unserved demand')
        ax.scatter([1.25, 4.75], [.25, .75], color='#0f766e', zorder=5, s=45, label='Paid capacity samples')
        ax.axvline(3, color='#0f766e', ls=':', lw=1.3)
        ax.set(xlim=(-.1, 5.65), ylim=(0, 1.12), ylabel='Service units / s', xlabel='Facility time (s)')
        ax.legend(loc='lower right', ncol=2, fontsize=9); ax.grid(alpha=.15)
        timeline(lower, network, 'network-case', [('inspect', 'Inspect'), ('action', 'Act'), ('recheck', 'Recheck')], 5.65)
        fig.text(.14, .045, '5.5 s horizon: demand 5.5, delivered 2.625, deficit 2.875 | work 3 person-s, access 0.75 person-s', color='#334155')
        fig.text(.14, .020, 'Green = actual work; purple = report transit; dots = issued intentions. No automatic risk closure.', fontsize=10, color='#475569')
        fig.savefig(args.output / 'network-action-recheck.png', dpi=150)
        fig.savefig(args.output / 'network-action-recheck.svg', metadata={'Date': None})
        plt.close(fig)

        data = rows['direct_state']
        times = [r['time_s'] for r in data]
        flow = [r['domains']['facility_cooling']['lake_pump']['volume_flow_m3_s'] for r in data]
        record = direct['inspection_records'][0]
        fig, (ax, lower) = plt.subplots(2, 1, figsize=(13.5, 7.8), gridspec_kw={'height_ratios': [1, 1.2]})
        fig.subplots_adjust(left=.14, right=.96, top=.84, bottom=.14, hspace=.5)
        fig.suptitle('Authorized direct cleaning retains residual resistance and pays for recheck', fontsize=16, y=.965)
        fig.text(.14, .90, 'Actual synthetic engineering trace | Slurm 133132 | initial inspection remains unissued', color='#475569')
        ax.plot(times, flow, color='#2563eb', lw=2.2, label='Actual intake flow')
        ax.axhline(.1, color='#64748b', ls='--', label='Nominal clean working point')
        ax.scatter([record['observed_at_s']], [record['value']], color='#0f766e', s=50, zorder=4, label='Actual recheck sample')
        ax.set(xlim=(-.1, 6.2), ylim=(.045, .108), ylabel='Intake flow (m³/s)', xlabel='Facility time (s)')
        ax.grid(alpha=.15); ax.legend(loc='upper left', fontsize=10)
        timeline(lower, direct, 'cooling-direct', [('action', 'Clean'), ('recheck', 'Recheck')], 6.2)
        fig.text(.14, .045, 'Filter multiplier 4 → 2 | actual recheck = 0.0745356 m³/s | work 2, travel 2, access 0.5 person-s', color='#334155')
        fig.text(.14, .020, 'The reading confirms the named physical signal only. It is neither full recovery nor verified risk closure.', fontsize=10, color='#475569')
        fig.savefig(args.output / 'direct-filter-residual.png', dpi=150)
        fig.savefig(args.output / 'direct-filter-residual.svg', metadata={'Date': None})
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(14, 8.5))
        fig.subplots_adjust(left=.02, right=.98, top=.87, bottom=.09)
        ax.set(xlim=(0, 1), ylim=(0, 1)); ax.axis('off')
        fig.suptitle('One public question, separate task stages, private actual execution', fontsize=18, y=.96)
        fig.text(.06, .90, 'v2 instance workflow | model/AI calls 0 | personnel are domain actors | closure criteria remain a later gate', color='#475569')
        def box(x, y, title, lines, color):
            ax.add_patch(FancyBboxPatch((x, y), .39, .13, boxstyle='round,pad=.012', facecolor='white', edgecolor=color, lw=1.6))
            ax.text(x+.195, y+.092, title, ha='center', va='center', fontweight='bold', fontsize=12, color=color)
            ax.text(x+.195, y+.038, lines, ha='center', va='center', fontsize=10, color='#334155')
        blue, green = '#1d4ed8', '#047857'
        box(.035, .79, 'Arrived claims + declared knowledge', 'No private state or future readings', blue)
        box(.035, .55, 'Stable question / stage identities', 'Inspect → conditional or direct act → recheck', blue)
        box(.035, .31, 'Common admission and public gates', 'Crew / tool / access / authority / budget', blue)
        box(.035, .07, 'Public choice: intention only', 'execution_permission = false; can defer', blue)
        box(.575, .07, 'Actual CrewWorkforce', 'Travel, access, qualification and paid work', green)
        box(.575, .31, 'Private named operation executor', 'Current completion + valid authority; once', green)
        box(.575, .55, 'Actual inspection / delayed reports', 'New sample only after real work completes', green)
        box(.575, .79, 'Plant + autonomous local protection', 'Actual physical state and service accounting', green)
        def arrow(start, end, dashed=False):
            ax.add_patch(FancyArrowPatch(start, end, arrowstyle='-|>', mutation_scale=15, lw=1.5,
                                         color='#475569', linestyle='--' if dashed else '-'))
        for top, bottom in [(.79, .68), (.55, .44), (.31, .20)]: arrow((.23, top), (.23, bottom))
        arrow((.425, .135), (.575, .135))
        arrow((.77, .20), (.77, .31)); arrow((.77, .44), (.77, .55))
        arrow((.575, .615), (.425, .615))
        ax.text(.50, .68, 'arrived\nrecords / feedback', ha='center', fontsize=9)
        arrow((.965, .855), (.99, .855)); arrow((.99, .855), (.99, .615)); arrow((.99, .615), (.965, .615))
        ax.plot([.50, .50], [.05, .93], color='#94a3b8', ls=':', lw=1)
        ax.text(.23, .98, 'PUBLIC', ha='center', color=blue, fontweight='bold')
        ax.text(.77, .98, 'PRIVATE', ha='center', color=green, fontweight='bold')
        fig.text(.06, .035, 'Consistent APPLIED + arrived completed-work ACK open recheck. Failed / unknown / normal / no-human stay distinct; risk stays unclosed.', fontsize=10, color='#334155')
        fig.savefig(args.output / 'question-action-architecture.png', dpi=150)
        fig.savefig(args.output / 'question-action-architecture.svg', metadata={'Date': None})
        plt.close(fig)
        guard()
        save(args.output / 'plot-summary.json', dict(classification='SAVED_SYNTHETIC_ENGINEERING_WITNESSES',
            render_source=manifest['source_commit'], runtime_sources={k: v['code_identity']['git_commit'] for k, v in summaries.items()},
            raw_row_counts={k: len(v) for k, v in rows.items()}, rows_are_not_statistical_units=True,
            matplotlib=matplotlib.__version__, facility_calls=0, model_calls=0, new_research_trials=0,
            figure_count=3, scope=protocol['scope']))
        terminal.update(status='COMPLETED', source_guard='PASS_BEFORE_AND_AFTER',
                        outputs={p.name: dict(bytes=p.stat().st_size, sha256=digest(p)) for p in args.output.iterdir() if p.is_file()})
        print(json.dumps(dict(status=terminal['status'], figures=3, facility_calls=0)))
    except BaseException as error:
        terminal.update(error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
        raise
    finally:
        terminal['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        save(args.output / 'terminal.json', terminal)


if __name__ == '__main__':
    main()
