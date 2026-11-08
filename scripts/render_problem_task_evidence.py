"""Render the saved actual inspection trace; never import or rerun the plant."""
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


def sha256(path):
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
        raise SystemExit('Evidence rendering requires the declared Slurm allocation')
    root = args.manifest.resolve().parent
    manifest_hash = sha256(args.manifest)
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    args.output.mkdir(exist_ok=False)
    save(args.output / 'attempt.json', dict(classification='SAVED_ENGINEERING_VISUALIZATION_NOT_RESEARCH_TRIAL',
        source_commit=manifest['source_commit'], manifest_sha256=manifest_hash,
        started_at_utc=datetime.now(timezone.utc).isoformat(), slurm_job_id=os.environ['SLURM_JOB_ID'],
        node=socket.gethostname(), python=sys.version, facility_calls=0, model_calls=0, new_statistical_units=0))
    terminal = dict(status='FAILED', source_commit=manifest['source_commit'])
    try:
        protocol = json.loads((root / 'protocol.json').read_text(encoding='utf-8'))
        input_root = Path(protocol['input_root'])

        def guard():
            if sha256(args.manifest) != manifest_hash:
                raise ValueError('Frozen render manifest changed')
            for name, record in manifest['files'].items():
                if (root / name).stat().st_size != record['bytes'] or sha256(root / name) != record['sha256']:
                    raise ValueError('Render source/protocol changed: ' + name)
            for name, expected in protocol['inputs'].items():
                if sha256(input_root / name) != expected:
                    raise ValueError('Saved engineering input changed: ' + name)
        guard()
        if sha256(Path(__file__)) != manifest['files']['render_problem_task_evidence.py']['sha256']:
            raise ValueError('Executed renderer differs from its pinned tool')
        summary = json.loads((input_root / 'actual-run-summary.json').read_text(encoding='utf-8'))
        if summary['code_identity']['git_commit'] != protocol['runtime_source'] or summary['code_identity']['implementation_has_changes']:
            raise ValueError('Actual run source differs from the declared runtime revision')
        rows = [json.loads(line) for line in (input_root / 'actual-run/private-state.jsonl').read_text(encoding='utf-8').splitlines()]
        work = summary['work_records'][0]
        measured = next(r for r in summary['inspection_records'] if r['id'] == 'cooling-desk-flow-0')
        if len(summary['work_records']) != 1 or work['status'] != 'completed':
            raise ValueError('Renderer scope requires the single completed investigation')
        movement = work['paths']['worker_cooling'][0]
        os.environ['MPLCONFIGDIR'] = str(root / 'matplotlib-cache')
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
        plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'svg.hashsalt': 'aegisdc39b-slice02'})
        times = [row['time_s'] for row in rows]
        flow = [row['domains']['facility_cooling']['lake_pump']['volume_flow_m3_s'] for row in rows]
        with (args.output / 'plot-data.csv').open('x', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream, lineterminator='\n')
            writer.writerow(['time_s', 'private_intake_volume_flow_m3_s', 'private_delivered_service_rate'])
            writer.writerows((row['time_s'], row['domains']['facility_cooling']['lake_pump']['volume_flow_m3_s'],
                             row['domains']['it_service']['delivered']) for row in rows)
        fig, (ax, timeline) = plt.subplots(2, 1, figsize=(13, 8), gridspec_kw={'height_ratios': [1, 1.4]})
        fig.subplots_adjust(left=.16, right=.96, top=.86, bottom=.12, hspace=.47)
        fig.suptitle('Problem-triggered inspection: actual execution and evidence timing', fontsize=17, x=.10, ha='left', y=.965)
        fig.text(.10, .91, 'Synthetic engineering fixture | one paid investigation | no intervention or gain claim', color='#475569')
        ax.plot(times, flow, color='#2563eb', lw=2.2, label='Private plant signal (evaluator only)')
        ax.scatter([measured['observed_at_s']], [measured['value']], color='#0f766e', s=65, zorder=4, label='Actual handheld sample')
        ax.set(xlim=(-.08, 4.15), ylabel='Intake flow (m³/s)', xlabel='Facility time (s)')
        ax.grid(alpha=.18);ax.legend(loc='lower left', fontsize=10)
        ax.axvline(measured['arrived_at_s'], color='#7c3aed', lw=1.5, ls='--')
        ax.text(measured['arrived_at_s']-.03, .98, 'Public arrival 3.75 s', transform=ax.get_xaxis_transform(), ha='right', va='top', color='#6d28d9', fontsize=10)
        intervals = [('Travel', movement['departs_at_s'], movement['gate_at_s'], '#2563eb'),
                     ('Access', movement['gate_at_s'], movement['arrives_at_s'], '#94a3b8'),
                     ('Measure', work['work_started_at_s'], work['completed_at_s'], '#0f766e')]
        for label, start, end, color in intervals:
            timeline.broken_barh([(start, end-start)], (.25, .65), facecolors=color)
            timeline.text((start+end)/2, .57, label, color='white' if label!='Access' else '#0f172a', ha='center', va='center', fontsize=10, rotation=90 if label=='Access' else 0)
        timeline.broken_barh([(measured['observed_at_s'], measured['arrived_at_s']-measured['observed_at_s'])], (1.35, .65), facecolors='#7c3aed')
        timeline.text(3.5, 1.68, 'Transit', color='white', ha='center', va='center', fontsize=10)
        for instant, text in [(0, 'Issue'), (4, 'Record available;\nno duplicate task')]:
            timeline.scatter([instant], [2.65], color='#111827', s=40, zorder=3)
            timeline.text(instant+.03 if instant==0 else instant-.03, 2.82, text, ha='left' if instant==0 else 'right', va='bottom', fontsize=10)
        for instant, label in [(work['work_started_at_s'], '2.25'), (measured['observed_at_s'], '3.25'), (measured['arrived_at_s'], '3.75')]:
            timeline.axvline(instant, color='#64748b', lw=.8, ls=':', alpha=.7)
            timeline.text(instant, -.13, label, ha='center', va='top', fontsize=9)
        timeline.set(xlim=(-.08, 4.15), ylim=(-.05, 3.6), yticks=[.57, 1.68, 2.65],
                     yticklabels=['Crew / tool', 'Report channel', 'Public decisions'], xlabel='Facility time (s)')
        timeline.grid(axis='x', alpha=.15)
        fig.text(.10, .035, 'Source fe2dd01d | Slurm 133114 | travel 2 person-s, work 1 person-s, access 0.25 person-s | raw trace stays remote', fontsize=10, color='#475569')
        fig.savefig(args.output / 'task-measurement-timeline.svg', metadata={'Date': None})
        fig.savefig(args.output / 'task-measurement-timeline.png', dpi=150)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(14, 8))
        fig.subplots_adjust(left=.02, right=.98, top=.89, bottom=.08)
        ax.set(xlim=(0, 1), ylim=(0, 1));ax.axis('off')
        fig.suptitle('Current implementation: public problem selection and private actual execution', fontsize=17, y=.965)
        for x, title, color in [(.02, 'PUBLIC: arrived records and declared knowledge', '#eff6ff'), (.55, 'PRIVATE: actual state and timed execution', '#f0fdf4')]:
            ax.add_patch(FancyBboxPatch((x, .12), .43, .83, boxstyle='round,pad=.012', facecolor=color, edgecolor='#cbd5e1'))
            ax.text(x+.215, .91, title, ha='center', fontsize=10, fontweight='bold')
        def box(x, y, title, subtitle, color):
            ax.add_patch(FancyBboxPatch((x,y),.36,.11,boxstyle='round,pad=.008',facecolor='white',edgecolor=color,lw=1.5))
            ax.text(x+.18,y+.074,title,ha='center',va='center',fontsize=12,fontweight='bold',color=color)
            ax.text(x+.18,y+.030,subtitle,ha='center',va='center',fontsize=9,color='#334155')
        blue='#1d4ed8';green='#047857'
        box(.055,.74,'Work order + static identities','An unconfirmed claim; no hidden fault label',blue)
        box(.055,.56,'DecisionGateway','Current records only; no future measurement',blue)
        box(.055,.38,'Templates + problem instances','Origin + stable slot + professional task template',blue)
        box(.055,.20,'choose_work','Task intention; execution_permission = false',blue)
        box(.585,.20,'CrewWorkforce','Travel / qualification / tool / access checks',green)
        box(.585,.40,'InspectionSession','Sample after actual completion: 3.25 s',green)
        box(.585,.60,'Arrived evidence ledger','Named report crosses at 3.75 s',green)
        box(.585,.78,'Plant + local protection','Private physical state continues independently',green)
        def arrow(start, end, dashed=False):
            ax.add_patch(FancyArrowPatch(start,end,arrowstyle='-|>',mutation_scale=15,lw=1.5,color='#475569',linestyle='--' if dashed else '-'))
        for y1,y2 in [(.74,.67),(.56,.49),(.38,.31)]:arrow((.235,y1),(.235,y2))
        arrow((.415,.255),(.585,.255));ax.text(.50,.28,'task',ha='center',fontsize=9)
        arrow((.765,.31),(.765,.40));arrow((.765,.51),(.765,.60))
        arrow((.585,.655),(.415,.615));ax.text(.50,.70,'arrived\nrecord',ha='center',fontsize=9)
        arrow((.415,.435),(.585,.455),True);ax.text(.50,.47,'register slots',ha='center',fontsize=8)
        arrow((.945,.835),(.985,.835));arrow((.985,.835),(.985,.455));arrow((.985,.455),(.945,.455))
        ax.text(.977,.73,'private\nsample',ha='right',fontsize=8)
        ax.plot([.50,.50],[.13,.91],color='#94a3b8',ls=':',lw=1)
        fig.text(.05,.03,'Predeclared slots do not issue work or reveal samples. Current slice: one investigation, no physical intervention or risk closure.',fontsize=10,color='#475569')
        fig.savefig(args.output / 'public-private-task-flow.svg', metadata={'Date': None})
        fig.savefig(args.output / 'public-private-task-flow.png', dpi=150)
        plt.close(fig)
        guard()
        save(args.output / 'plot-summary.json', dict(classification=protocol['classification'],
            runtime_source=protocol['runtime_source'], source_slurm_job=protocol['source_slurm_job'],
            rendered_source_commit=manifest['source_commit'], matplotlib=matplotlib.__version__,
            source_row_count=len(rows), source_row_count_is_not_statistical_units=True,
            measurement_record_id=measured['id'], observed_at_s=measured['observed_at_s'],
            arrived_at_s=measured['arrived_at_s'], plot_scope=protocol['scope'],
            facility_calls=0, model_calls=0, new_research_trials=0))
        terminal.update(status='COMPLETED', source_guard='PASS_BEFORE_AND_AFTER',
                        outputs={p.name: dict(bytes=p.stat().st_size,sha256=sha256(p))
                                 for p in args.output.iterdir() if p.is_file()})
        print(json.dumps(dict(status=terminal['status'], rendered_figures=2, facility_calls=0)))
    except BaseException as error:
        terminal.update(error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
        raise
    finally:
        terminal['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        save(args.output / 'terminal.json', terminal)


if __name__ == '__main__':
    main()
