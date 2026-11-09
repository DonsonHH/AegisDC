"""Source-pinned saved-result figures; never import the facility or a policy."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import traceback


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def check(path, record):
    if path.stat().st_size != record['bytes'] or sha(path) != record['sha256']:
        raise ValueError('Saved rendering input differs: ' + str(path))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or socket.gethostname().split('.')[0] == 'mu01':
        raise SystemExit('Saved research figures require the declared Slurm allocation')
    args.output.mkdir(exist_ok=False)
    terminal = dict(status='FAILED', source_commit=args.source_commit, facility_calls=0,
                    public_choice_calls=0, model_calls=0, new_research_trials=0)
    save(args.output / 'attempt.json', dict(classification='SAVED_RESULT_RENDERING_ONLY',
        source_commit=args.source_commit, manifest_sha256=sha(args.manifest) if args.manifest.is_file() else None,
        slurm_job_id=os.environ['SLURM_JOB_ID'], started_at_utc=datetime.now(timezone.utc).isoformat()))
    try:
        manifest = json.loads(args.manifest.read_text())
        if manifest['source_commit'] != args.source_commit:
            raise ValueError('Saved renderer actual source argument differs from frozen manifest')
        check(Path(__file__), manifest['renderer'])
        rows = []
        native_root = Path('/share/home/renly/renly-patrol-rsi/mainline/39c-development').resolve()
        for source in manifest['inputs']:
            path = Path(source['path'])
            if not path.resolve().is_relative_to(native_root):
                raise ValueError('Figure source escapes the declared private namespace')
            check(path, source)
            data = json.loads(path.read_text())
            if data['visibility'] != 'PRIVATE_EVALUATOR_ONLY' or len(data['episodes']) != 1:
                raise ValueError('Use one saved finite engineering event per declared variant')
            rows.append(dict(source=source, data=data, event=data['episodes'][0]))
        if len(rows) != 4:
            raise ValueError('Keep all four declared variants in the figure')
        fields = ['case_id', 'source_job', 'source_case_status', 'window_end_s',
                  'actual_action_completed_at_s', 'action_report_arrived_at_s',
                  'first_verified_closed_at_s', 'closure_censor_at_s',
                  'last_assessed_at_s', 'status_at_horizon']
        with (args.output / 'endpoints.csv').open('x', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n');writer.writeheader()
            for row in rows:
                event, source, data = row['event'], row['source'], row['data']
                writer.writerow(dict(case_id=source['id'], source_job=source['job'],
                    source_case_status=source['case_status'], window_end_s=data['window_end_s'],
                    **{name:event[name] for name in fields[4:]}))
        with (args.output / 'assessments.csv').open('x', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=['case_id', 'as_of_s', 'status', 'risk_closed'], lineterminator='\n')
            writer.writeheader()
            for row in rows:
                for point in row['event']['assessments']:
                    writer.writerow(dict(case_id=row['source']['id'], **{k:point[k] for k in
                        ('as_of_s', 'status', 'risk_closed')}))

        os.environ['MPLCONFIGDIR'] = str(args.manifest.parent / 'runtime-matplotlib-cache')
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.lines import Line2D
        from matplotlib.patches import FancyArrowPatch, Rectangle
        from matplotlib.text import Text
        plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':12,
                             'svg.hashsalt':'aegisdc-39c-closure-endpoints', 'axes.spines.top':False,
                             'axes.spines.right':False, 'axes.titlesize':17})
        colors = dict(work='#0f766e', report='#7c3aed', closed='#2563eb', pending='#a16207',
                      open='#64748b', ink='#0f172a', light='#cbd5e1')
        figures = []
        fig, (ax, notes) = plt.subplots(1, 2, figsize=(14, 8), gridspec_kw={'width_ratios':[4, 1.8]}, sharey=True)
        fig.subplots_adjust(left=.17, right=.98, bottom=.2, top=.73, wspace=.07)
        fig.suptitle('Actual work, reports and sampled verification', x=.51, y=.97, fontsize=21)
        fig.text(.17, .9, 'Four declared engineering variants | saved results only | time in seconds', fontsize=12, color=colors['open'])
        labels = []
        for index, row in enumerate(rows):
            y = 3 - index;event = row['event'];end = row['data']['window_end_s']
            labels.append(row['source']['label'])
            ax.hlines(y, 0, end, color=colors['light'], linewidth=1.4, zorder=0)
            ax.plot(end, y, '|', color=colors['ink'], markersize=16)
            for point in event['assessments']:
                closed = point['status'] == 'VERIFIED_CLOSED'
                color = colors['closed'] if closed else colors['pending'] if point['status'] != 'OPEN_UNCONFIRMED' else colors['open']
                ax.scatter(point['as_of_s'], y, marker='*' if closed else 'o',
                           facecolors='none' if point['status']=='OPEN_UNCONFIRMED' else color,
                           edgecolors=color, s=145 if closed else 32, zorder=3)
            for key, marker, color, offset in [('actual_action_completed_at_s','D',colors['work'],-.2),
                                                ('action_report_arrived_at_s','s',colors['report'],.2)]:
                time = event[key]
                if time is not None:
                    ax.scatter(time, y + offset, marker=marker, color=color, s=50, zorder=4)
                    ax.annotate(f'{time:g}', (time, y + offset), xytext=(0, -18 if offset < 0 else 9),
                                textcoords='offset points', ha='center', fontsize=11, color=color)
            if event['closure_right_censored']:
                ax.scatter(event['closure_censor_at_s'], y+.28, marker='>', facecolors='none',
                           edgecolors=colors['ink'], linewidths=1.5, s=150, zorder=5)
            first = event['first_verified_closed_at_s']
            summary = ('No verified closure\n' + f"Censored at {event['closure_censor_at_s']:g}") if first is None else f'First verified: {first:g}\n'
            if first is not None:
                summary += 'Horizon: unassessed' if event['status_at_horizon'] == 'NOT_ASSESSED_AT_HORIZON' else 'Horizon: pending again'
            notes.text(.02, y, summary, va='center', color=colors['ink'], fontsize=12)
        ax.set_yticks([3,2,1,0], labels=labels)
        ax.set_ylim(-.65, 3.65);ax.set_xlim(0,10.3);ax.set_xticks(range(11))
        ax.set_xlabel('Facility time (s)', labelpad=10);ax.grid(axis='x', alpha=.16)
        ax.tick_params(axis='y', length=0, pad=12);notes.axis('off')
        legend = [Line2D([],[],marker='D',linestyle='None',color=colors['work'],label='Actual work completed'),
                  Line2D([],[],marker='s',linestyle='None',color=colors['report'],label='Action report arrived'),
                  Line2D([],[],marker='*',linestyle='None',color=colors['closed'],markersize=12,label='Verified assessment'),
                  Line2D([],[],marker='o',linestyle='None',markerfacecolor='none',color=colors['open'],label='Open assessment'),
                  Line2D([],[],marker='o',linestyle='None',color=colors['pending'],label='Pending verification'),
                  Line2D([],[],marker='>',linestyle='None',markerfacecolor='none',color=colors['ink'],label='Right-censored closure')]
        fig.legend(handles=legend, loc='upper left', bbox_to_anchor=(.16,.86), ncol=3, frameon=False, fontsize=10)
        fig.text(.17,.08,'Dots/stars are discrete public assessments. Lines show run windows; states are not interpolated.',fontsize=11,color=colors['open'])
        fig.text(.17,.035,'The 8 s trace is the passed case retained from failed batch 133195. Original batch failures remain recorded.',fontsize=10,color=colors['open'])
        figures.append(('closure-times-and-censoring',fig))

        fig, ax = plt.subplots(figsize=(14,8));fig.subplots_adjust(left=.03,right=.97,bottom=.12,top=.85)
        ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off')
        fig.suptitle('Public decisions and private business evaluation',y=.97,fontsize=21)
        fig.text(.06,.9,'Endpoint evaluation runs after the complete facility run; the original selection and closure rules remain.',fontsize=12,color=colors['open'])
        def box(x,y,w,h,text,public=False):
            ax.add_patch(Rectangle((x,y),w,h,facecolor='#eff6ff' if public else '#f8fafc',edgecolor=colors['ink'],linewidth=1.2))
            ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=13,color=colors['ink'])
        def arrow(start,end):
            ax.add_patch(FancyArrowPatch(start,end,arrowstyle='-|>',mutation_scale=15,linewidth=1.3,color=colors['open']))
        box(.04,.69,.25,.17,'Arrived records\nand declared knowledge',True)
        box(.37,.69,.25,.17,'Public selection\nand closure criteria',True)
        box(.70,.69,.25,.17,'Actual decisions\nand public assessments',True)
        arrow((.29,.775),(.37,.775));arrow((.62,.775),(.70,.775))
        box(.04,.27,.25,.17,'Eight-domain plant\ncrew, tools and actions')
        box(.37,.07,.25,.14,'Private endpoint\nevent bindings')
        box(.70,.27,.25,.17,'Private business\nendpoint evaluator')
        box(.70,.02,.25,.14,'Saved endpoint data\nCSV and figures')
        arrow((.165,.44),(.165,.69));ax.text(.185,.56,'Declared\nchannels only',fontsize=11,va='center',color=colors['open'])
        arrow((.29,.355),(.70,.355));ax.text(.49,.385,'Actual work/completion records',ha='center',fontsize=11,color=colors['open'])
        arrow((.825,.69),(.825,.44));ax.text(.84,.56,'Read-only\npublic trace',fontsize=11,va='center',color=colors['open'])
        arrow((.62,.14),(.70,.30));arrow((.825,.27),(.825,.16))
        fig.text(.06,.045,'Personnel are domain actors. Sampled verification and actual restoration remain different claims.',fontsize=11,color=colors['open'])
        figures.append(('public-private-endpoint-architecture',fig))

        geometry = []
        for name, fig in figures:
            fig.canvas.draw();canvas = fig.bbox
            outside = []
            for artist in fig.findobj(Text):
                if not artist.get_visible() or not artist.get_text().strip():continue
                bounds = artist.get_window_extent(fig.canvas.get_renderer())
                if bounds.x0 < canvas.x0 - 1 or bounds.y0 < canvas.y0 - 1 or bounds.x1 > canvas.x1 + 1 or bounds.y1 > canvas.y1 + 1:
                    outside.append(artist.get_text())
            if outside:
                raise ValueError('Visible text outside figure: ' + repr(outside))
            for extension in ['png','svg']:
                metadata = {'Date':None,'Creator':'AegisDC frozen saved-result renderer'} if extension == 'svg' else None
                fig.savefig(args.output / (name+'.'+extension),dpi=150,metadata=metadata,facecolor='white')
            geometry.append(dict(figure=name,text_outside_canvas=0))
            plt.close(fig)
        for source in manifest['inputs']:check(Path(source['path']),source)
        if sha(args.manifest) != json.loads((args.output/'attempt.json').read_text())['manifest_sha256']:
            raise ValueError('Frozen renderer manifest changed during rendering')
        check(Path(__file__),manifest['renderer'])
        save(args.output/'geometry-qa.json',dict(status='AUTOMATED_BOUNDS_PASS_REQUIRES_ACTUAL_VISUAL_INSPECTION',figures=geometry,
            units='s',missing_csv_cells='Explicitly not observed, never zero',native_or_policy_or_model_calls=0))
        terminal.update(status='PASS',figure_count=2,source_variants=4,visual_inspection='PENDING')
    except BaseException as error:
        terminal.update(error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc())
        raise
    finally:
        terminal['finished_at_utc']=datetime.now(timezone.utc).isoformat()
        terminal['output_files']={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in args.output.iterdir() if p.is_file()}
        save(args.output/'terminal.json',terminal)
        print(json.dumps(terminal))


if __name__=='__main__':main()
