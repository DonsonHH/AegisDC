"""Freeze/capture ticket-12 engineering qualification; no registered trials."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import traceback
import zipfile

from aegis_dc.plant import save_run, simulate_scenario
from aegis_dc.scenario import load_scenario
from numerical_engineering_checks import assess, inspect_run, member_identities, read_archive
from probe_numerical_phase import probe, PRIOR, EOS, TABLE
from verify_reserve_delivery import file_sha, git_blob_sha, is_runtime_cache

ROOT = Path(__file__).resolve().parents[1]
BOOK = 'docs/mainline/12-numerical-runbook.json'


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def configured(base, item):
    scenario = deepcopy(base)
    for row in scenario['parameters']:
        if row['id'] in item['overrides']:
            row.update(value=item['overrides'][row['id']], basis='synthetic_assumption',
                       source_note='Frozen ticket 12 numerical engineering case: ' + item['id'])
    return scenario


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--plot-dependencies', type=Path)
    parser.add_argument('--development', action='store_true', help='Reduced, explicitly unqualified preparation; no full suite')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT):
        raise ValueError('Capture must use a fresh worktree-local output directory')
    execution = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if not args.development and subprocess.check_output(['git', 'diff', '--name-only', 'HEAD'], cwd=ROOT, text=True).strip():
        raise ValueError('Freeze source, tools and inputs before formal engineering capture')
    book = json.loads((ROOT / BOOK).read_text(encoding='utf-8'))
    if args.development:
        book['cases'] = [item for item in book['cases'] if item['id'] != 'combined-240s']
    steps = [1, .025, .02, .01] if args.development else book['maximum_steps_s']
    source_tools = subprocess.check_output(['git', 'ls-files', '-z', '--', 'src', 'tests'], cwd=ROOT).decode('utf-8').split('\0')
    tools = [name for name in source_tools if name.endswith('.py')]
    tools += ['scripts/' + name for name in ('capture_mainline_numerics.py', 'numerical_engineering_checks.py',
        'probe_numerical_phase.py', 'plot_mainline_numerics.py', 'verify_mainline_numerics.py',
        'build_numerical_runbook.py', 'coupled_engineering_checks.py', 'verify_reserve_delivery.py', 'acceptance.py', 'verify_evidence.py')]
    inputs = [BOOK, book['profile'], TABLE, PRIOR, EOS]
    prior = ['docs/mainline/evidence/11.json', 'docs/mainline/evidence/M1.json',
             'evidence/mainline/engineering/property-reference/receipt.json',
             'evidence/mainline/engineering/12-numerical/development/red-clock-ulp.log']
    pinned = {}
    for group, names in [('pinned_tools', tools), ('execution_inputs', inputs), ('prior_durable_files', prior)]:
        pinned[group] = {name: file_sha(ROOT / name) for name in names}
        if not args.development:
            for name, identity in pinned[group].items():
                if is_runtime_cache(name) or git_blob_sha(ROOT, execution, name) != identity:
                    raise ValueError('Declared execution source/input differs from Git: ' + name)
    archives = {item['id']: {str(h): f"runs/{item['id']}/h-{h}.zip" for h in steps} for item in book['cases']}
    planned = ['declaration.json', 'runbook-copy.json', 'engineering-attempts.jsonl', 'runs-index.json',
               'assessment.json', 'phase-domain.json', 'expected-rejections.json', 'capture-status.json']
    planned += [name for by_step in archives.values() for name in by_step.values()]
    planned += ['figures/numerical-qualification' + suffix for suffix in ('.png', '.svg', '.json')]
    if not args.development:
        planned += ['full-check/' + name for name in ('summary.json', 'tests.log', 'evidence.json')]
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / 'declaration.json', dict(schema='aegisdc-declared-durable-set-v1', execution_commit=execution,
        declared_artifacts=planned, declared_tools=tools, declared_execution_inputs=inputs, declared_prior_files=prior,
        runtime_cache_policy='Exclude __pycache__, .pyc and .pyo by type BEFORE hashing; not delivery evidence.',
        original_policy='ZIP losslessly preserves all four original save_run files; member hashes/counts checked against public run.json. No trajectory writer remains after archive close.',
        full_regression_runs=0 if args.development else 1, classification='DEVELOPMENT_NOT_QUALIFIED' if args.development else 'ENGINEERING_NUMERICAL_QUALIFICATION_NOT_RESEARCH'))
    write_new(output / 'runbook-copy.json', book)
    index, analyses, sources = {}, {}, None
    stage = None
    with (output / 'engineering-attempts.jsonl').open('x', encoding='utf-8', newline='\n') as ledger:
        def record(value):
            ledger.write(json.dumps(dict(value, execution_commit=execution), allow_nan=False) + '\n')
            ledger.flush()
        try:
            base = load_scenario(ROOT / book['profile'])
            staging = ROOT / '.work/numerical-staging'
            staging.mkdir(parents=True, exist_ok=True)
            for item in book['cases']:
                name = item['id']
                index[name], analyses[name] = {}, {}
                for h in steps:
                    stage = name + '/' + str(h)
                    result = simulate_scenario(configured(base, item), duration_s=item['duration_s'], step_s=h,
                        boundary_events=item['events'], work_requests=item['work_requests'])
                    if sources is None:
                        sources = result['code_identity']['files']
                    if result['code_identity']['files'] != sources or (not args.development and result['code_identity']['implementation_has_changes']):
                        raise ValueError('Runtime source changed during capture')
                    archive_path = output / archives[name][str(h)]
                    archive_path.parent.mkdir(parents=True, exist_ok=True)
                    with tempfile.TemporaryDirectory(dir=staging, prefix='numeric-') as temporary:
                        temp_path = Path(temporary).resolve()
                        if not temp_path.is_relative_to(staging.resolve()):
                            raise ValueError('Temporary cleanup path escaped declared staging directory')
                        saved = temp_path / 'public-run'
                        save_run(result, saved)
                        with zipfile.ZipFile(archive_path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                            for path in sorted(saved.iterdir()):
                                archive.writestr(path.name, path.read_bytes())
                    manifest, scenario, trace, balances = read_archive(archive_path)
                    if scenario['entities'] != base['entities'] or scenario['graphs'] != base['graphs']:
                        raise ValueError('Complete V6 facility identities/relations changed')
                    analysis = inspect_run(item, manifest, scenario, trace, balances)
                    index[name][str(h)] = dict(archive=archives[name][str(h)], archive_sha256=file_sha(archive_path),
                        original_members=member_identities(archive_path),
                        source_commit=execution, scenario_sha256=manifest['scenario_sha256'], analysis=analysis)
                    analyses[name][str(h)] = analysis
                    record(dict(case=name, maximum_step_s=h, outcome='ENGINEERING_COMPLETED',
                        archive=archives[name][str(h)], archive_sha256=file_sha(archive_path)))
                print('captured numerical ' + name, flush=True)
            write_new(output / 'runs-index.json', index)
            rejections = []
            for item in book['rejections']:
                stage = item['id']
                scenario = configured(base, item)
                try:
                    simulate_scenario(scenario, duration_s=item['duration_s'], step_s=item['step_s'],
                                      boundary_events=item['events'])
                except ValueError as error:
                    if item['error_contains'] not in str(error):
                        raise ValueError('Unexpected rejection category: ' + str(error)) from error
                    rejections.append(dict(request=item, scenario=scenario, error=str(error), successful_trajectory_returned=False))
                    record(dict(case=stage, outcome='EXPECTED_REJECTION', error=str(error)))
                else:
                    raise ValueError('Unsupported numerical/physical domain returned a successful trajectory')
            write_new(output / 'expected-rejections.json', rejections)
            stage = 'phase-domain'
            write_new(output / 'phase-domain.json', probe(ROOT))
            assessment = assess(book, analyses)
            write_new(output / 'assessment.json', assessment)
            stage = 'saved-data-figure'
            import numpy
            if numpy.__version__ != '2.3.5':
                raise ValueError('Use pinned project NumPy 2.3.5')
            if args.plot_dependencies:
                sys.path.insert(0, str(args.plot_dependencies.resolve()))
            from plot_mainline_numerics import render
            figure = render(output)
            record(dict(stage=stage, outcome='RENDERED_FROM_SAVED_ORIGINALS'))
            full = None
            if not args.development:
                stage = 'one-full-acceptance'
                from acceptance import verify
                full = verify(ROOT, output / 'full-check')
                record(dict(stage=stage, outcome=full['overall'], tests=full.get('tests')))
                if full['overall'] != 'PASS':
                    raise ValueError('Full regression failed; original output retained')
            write_new(output / 'capture-status.json', dict(status='PASS', development=args.development,
                numerical_gate=assessment['all_declared_fixtures_qualified'], research_trials=0, model_calls=0, training_calls=0))
        except Exception as error:
            record(dict(stage=stage, outcome='UNEXPECTED_FAILURE', error=repr(error)))
            write_new(output / 'capture-status.json', dict(status='FAIL', stage=stage, error=repr(error), traceback=traceback.format_exc()))
            raise
    actual = {path.relative_to(output).as_posix() for path in output.rglob('*') if path.is_file() and not is_runtime_cache(path)}
    if actual != set(planned):
        raise ValueError('Declared durable set differs from completed outputs: ' + str(actual ^ set(planned)))
    write_new(output / 'receipt.json', dict(schema='aegisdc-numerical-capture-v1', engineering_capture='PASS',
        delivery_gate='PENDING_COMMIT_AND_FRESH_CHECKOUT', execution_commit=execution, runtime_sources=sources,
        **pinned, artifacts={name: file_sha(output / name) for name in planned},
        full_regression_runs=0 if args.development else 1, full_tests=full['tests'] if full else None,
        toolchain=dict(python=platform.python_version(), python_executable=sys.executable,
                       executable_sha256=file_sha(Path(sys.executable)), matplotlib=figure['matplotlib'], numpy=figure['numpy']),
        runtime_caches_required=0, research_trials=0, model_calls=0, training_calls=0,
        numerical_gate=assessment['all_declared_fixtures_qualified'], field_calibration='PENDING', research_gain='NOT_ESTABLISHED'))
    print(json.dumps(dict(capture='PASS', numerical_gate=assessment['all_declared_fixtures_qualified'], archives=sum(map(len, archives.values())), development=args.development)))


if __name__ == '__main__':
    main()
