"""Show four saved reference windows without new facility or endpoint evaluation."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import traceback


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def main():
    if sys.flags.optimize:
        raise SystemExit('Optimized saved evidence rendering is forbidden')
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(os.environ.get('SLURM_JOB_ID') and socket.gethostname().split('.')[0] != 'mu01', 'Use a Slurm compute allocation')
    root = args.manifest.resolve().parent
    manifest = json.loads(args.manifest.read_bytes())
    manifest_sha = sha(args.manifest)
    args.output.mkdir(exist_ok=False)
    save(args.output / 'attempt.json', dict(classification='SAVED_ONLY_FIGURE_RENDER_NOT_RESEARCH',
        source_commit=manifest['source_commit'], manifest_sha256=manifest_sha,
        slurm_job_id=os.environ['SLURM_JOB_ID'], interpreter_optimize=0,
        started_at_utc=datetime.now(timezone.utc).isoformat(), new_facility_calls=0, new_model_calls=0, new_research_trials=0))
    terminal = dict(status='FAILED', source_commit=manifest['source_commit'], new_facility_calls=0, new_model_calls=0, new_research_trials=0)
    try:
        def guard():
            require(sha(args.manifest) == manifest_sha, 'Frozen manifest changed')
            require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip() == manifest['source_commit'], 'Render source changed')
            for name, record in manifest['files'].items():
                path = root / name
                require(path.resolve().is_relative_to(root) and not path.is_symlink(), 'Input path escaped')
                require(path.stat().st_size == record['bytes'] and sha(path) == record['sha256'], 'Frozen input differs: ' + name)
        guard()
        base = root / 'evidence/mainline/engineering/39c-development'
        specs = [
            ('unmodeled', 'Reference unassessed', 'slice-10/13-unmodeled-reference-green', '133310', '4fce17d050c6c33291ef971cc1dcbb5ce1a2a808', 'UNMODELED', 2),
            ('unavailable', 'Access unavailable', 'slice-11/14-unavailable-reference-green', '133326', '986f3fa50493e78cf589745ee2c45d466ddb4614', 'UNAVAILABLE', 2),
            ('too-late', 'Reference too late', 'slice-12/15-too-late-reference-green', '133335', 'b1d7f05c5b434eace80f41386ef526f51ad1f7cf', 'TOO_LATE', 2),
            ('deferred', 'One actual defer', 'slice-13/16-deliberate-defer-green', '133340', 'd575f15de8047280331ee82923a6a64f8790301c', 'ELIGIBLE', 2.5),
        ]
        rows = []
        for identifier, label, directory, job, source, status, horizon in specs:
            folder = base / directory
            result_path = folder / 'business-result.json'
            result = json.loads(result_path.read_bytes())
            original_terminal = json.loads((folder / 'terminal.json').read_bytes())
            original_manifest = json.loads((folder / 'source-manifest.json').read_bytes())
            require((folder / 'slurm-job-id.txt').read_text().strip() == job, 'Original job differs')
            require(original_terminal['source_commit'] == original_manifest['source_commit'] == source, 'Original source differs')
            require(original_terminal['status'] == 'GREEN_BEHAVIOR_PASSED', 'Original terminal did not pass')
            record = original_terminal['output_files']['business-result.json']
            require(result_path.stat().st_size == record['bytes'] and sha(result_path) == record['sha256'], 'Business result differs from original terminal')
            identity = result['execution_code_identity']
            require(identity['git_commit'] == source and identity['implementation_has_changes'] is False, 'Actual runtime differs')
            for name, digest in identity['files'].items():
                require(digest == original_manifest['files'][name]['sha256'], 'Actual runtime file differs: ' + name)
            require(result['window_end_s'] == horizon and len(result['events']) == 1, 'Original window or event count differs')
            event = result['events'][0]
            opportunity = event['reference_opportunity']
            require(event['initial_truth'] == 'FAULT' and opportunity['status'] == status and opportunity['deadline_s'] == 2, 'Declared state/reference differs')
            rate = result['rates']['missed_confirmation']
            rows.append(dict(case_id=identifier, label=label, original_job=job, source_commit=source,
                initial_truth=event['initial_truth'], reference_status=status, horizon_s=horizon,
                confirmation_cutoff_s=2, earliest_reference_report_s=opportunity['earliest_report_at_s'],
                actual_first_confirmation_s=event['first_corroborated_fault_report_at_s'],
                eligible_fault_events=rate['denominator'], missed_fault_events=rate['numerator'], missed_confirmation_rate=rate['value'],
                rate_unavailable_reason=rate['unavailable_reason'], saved_business_sha256=sha(result_path)))
        with (args.output / 'reference-windows.csv').open('x', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
            writer.writeheader()
            writer.writerows(rows)
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.lines import Line2D
        plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'svg.fonttype': 'none', 'axes.spines.top': False, 'axes.spines.right': False})
        figure = plt.figure(figsize=(15, 8))
        axis = figure.add_axes([.225, .36, .475, .41])
        table_axis = figure.add_axes([.755, .36, .215, .41])
        axis.set_xlim(-.04, 2.85)
        axis.set_ylim(3.6, -.65)
        axis.set_yticks(range(4), [row['label'] for row in rows])
        axis.tick_params(axis='y', length=0, pad=14)
        axis.set_xticks([0, .5, 1, 1.5, 1.75, 2, 2.25, 2.5], ['0', '0.5', '1', '1.5', '1.75', '2', '2.25', '2.5'])
        axis.tick_params(axis='x', labelsize=9)
        axis.set_xlabel('Elapsed time / s', labelpad=10)
        axis.axvline(2, color='#bc7053', lw=1.5, ls='--', zorder=1)
        for index, row in enumerate(rows):
            axis.plot([0, row['horizon_s']], [index, index], color='#dde5ec', lw=10, solid_capstyle='butt', zorder=1)
            axis.plot(row['horizon_s'], index, '|', ms=18, color='#78909f', zorder=2)
            reference = row['earliest_reference_report_s']
            actual = row['actual_first_confirmation_s']
            if reference is not None:
                axis.plot(reference, index, 'D', ms=9, mfc='white', mec='#477a9b', mew=2, zorder=3)
                axis.annotate(f'{reference:g} planned', (reference, index), xytext=(0, -23), textcoords='offset points', ha='center', fontsize=9, color='#477a9b')
            if actual is not None:
                axis.plot(actual, index, '*', ms=16, color='#bd6c48', zorder=4)
                axis.annotate(f'{actual:g} actual', (actual, index), xytext=(3, 16), textcoords='offset points', ha='center', fontsize=9, color='#99563b')
            if reference is None:
                axis.text(.09, index - .19, 'reference time null', fontsize=9, color='#5f7585')
        axis.spines['left'].set_visible(False)
        axis.set_title('Observed windows and declared reference', loc='left', pad=24, fontsize=12, fontweight='bold')
        table_axis.set_xlim(-.5, 2.5)
        table_axis.set_ylim(3.6, -.65)
        table_axis.axis('off')
        table_axis.set_title('Applicable event counts', loc='left', pad=24, fontsize=12, fontweight='bold')
        for col, label in enumerate(['Eligible N', 'Missed N', 'Rate']):
            table_axis.text(col, -.5, label, ha='center', va='center', fontsize=9, color='#5a7181')
        for index, row in enumerate(rows):
            values = [str(row['eligible_fault_events']), str(row['missed_fault_events']), 'n/a' if row['missed_confirmation_rate'] is None else f"{row['missed_confirmation_rate']:g}"]
            for col, value in enumerate(values):
                table_axis.text(col, index, value, ha='center', va='center', fontsize=14, color='#183d53')
        figure.text(.04, .94, 'Reference opportunities and actual late confirmation', fontsize=21, fontweight='bold', color='#16384c')
        figure.text(.04, .88, 'Four saved engineering cases; all keep the initial fault. Confirmation cutoff = 2 s.', fontsize=11, color='#526c7d')
        legend = [Line2D([0], [0], color='#dde5ec', lw=7, label='Observed run window'),
                  Line2D([0], [0], marker='D', mfc='white', mec='#477a9b', mew=2, ms=8, ls='', label='Declared reference (planned)'),
                  Line2D([0], [0], marker='*', color='#bd6c48', ms=13, ls='', label='Actual public confirmation'),
                  Line2D([0], [0], color='#bc7053', ls='--', label='Confirmation cutoff')]
        figure.legend(handles=legend, loc='center left', bbox_to_anchor=(.04, .25), ncol=2, frameon=False, columnspacing=3, handletextpad=1.1, fontsize=10)
        figure.text(.04, .137, 'The 2.5 s reference in the 2 s case is a declared future time, not an observed arrival. The deferred case actually confirms at 2.25 s.', fontsize=10, color='#345368')
        figure.text(.04, .089, 'No applicable denominator: rate is null (shown as n/a). Blank time fields in the CSV are null, never zero.', fontsize=10, color='#345368')
        figure.text(.04, .041, 'Different windows are not an effect comparison. No new facility calls or research trials; original red attempts and 180 baseline trials retained.', fontsize=10, color='#526c7d')
        figure.canvas.draw()
        renderer = figure.canvas.get_renderer()
        bounds = []
        for artist in figure.findobj(matplotlib.text.Text):
            if not artist.get_visible() or not artist.get_text():
                continue
            bound = artist.get_window_extent(renderer)
            canvas = figure.bbox
            if bound.x0 < canvas.x0 - 1 or bound.y0 < canvas.y0 - 1 or bound.x1 > canvas.x1 + 1 or bound.y1 > canvas.y1 + 1:
                bounds.append(artist.get_text())
        for extension in ('png', 'svg'):
            figure.savefig(args.output / ('reference-windows.' + extension), dpi=140, facecolor='white')
        plt.close(figure)
        require(not bounds, 'Text extends beyond canvas: ' + json.dumps(bounds))
        guard()
        terminal.update(status='SAVED_REFERENCE_FIGURE_RENDERED', source_guard='PASS_BEFORE_AND_AFTER',
            input_original_jobs=[spec[3] for spec in specs], original_business_identities='PASS', source_rows=4,
            figures=1, pngs=1, svgs=1, interpreter_optimize=0, text_bounds='PASS', visual_inspection='PENDING_SEPARATE_ACTUAL_VIEW')
    except BaseException as error:
        terminal.update(error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
        raise
    finally:
        terminal['output_files'] = {p.relative_to(args.output).as_posix(): dict(bytes=p.stat().st_size, sha256=sha(p)) for p in args.output.rglob('*') if p.is_file()}
        terminal['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        save(args.output / 'terminal.json', terminal)
    print(json.dumps(terminal))


if __name__ == '__main__':
    main()
