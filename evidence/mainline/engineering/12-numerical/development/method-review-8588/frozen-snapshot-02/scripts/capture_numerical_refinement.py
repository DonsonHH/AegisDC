"""Capture only added fine steps under the explicit additive v2 protocol."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback
import zipfile

from aegis_dc.plant import save_run, simulate_scenario
from aegis_dc.scenario import load_scenario
from capture_mainline_numerics import configured, write_new
from numerical_engineering_checks import member_identities, read_archive
from numerical_refinement_checks import (check_numeric_range_extension, compact,
    assess_refinement as assess, inspect_refinement_run as inspect_run)
from verify_reserve_delivery import file_sha, git_blob_sha, is_runtime_cache, safe_path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = 'docs/mainline/12-numerical-refinement-v2.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--plot-dependencies', type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT):
        raise ValueError('Use a new output directory within this worktree')
    execution = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if subprocess.check_output(['git', 'diff', '--name-only', 'HEAD'], cwd=ROOT, text=True).strip():
        raise ValueError('Freeze the additive protocol and tools before capture')
    book = json.loads((ROOT / PROTOCOL).read_text(encoding='utf-8'))
    prior = safe_path(ROOT, book['v1_directory'])
    prior_receipt = json.loads((prior / 'receipt.json').read_text(encoding='utf-8'))
    if file_sha(prior / 'receipt.json') != book['v1_receipt_sha256'] or prior_receipt['numerical_gate']:
        raise ValueError('Original NO-GO identity changed')
    for name, identity in prior_receipt['runtime_sources'].items():
        if file_sha(ROOT / name) != identity or git_blob_sha(ROOT, execution, name) != identity:
            raise ValueError('Runtime changed; cannot reuse full regression or v1 numeric originals')
    old_index = json.loads((prior / 'runs-index.json').read_text(encoding='utf-8'))
    tools = ['scripts/' + name for name in ('capture_numerical_refinement.py', 'prepare_numerical_refinement.py',
        'verify_numerical_refinement.py', 'plot_numerical_refinement.py', 'capture_mainline_numerics.py',
        'numerical_engineering_checks.py', 'numerical_refinement_checks.py', 'coupled_engineering_checks.py', 'verify_reserve_delivery.py')]
    inputs = [PROTOCOL, book['profile'], 'configs/materials/reference-r134a-saturation.json']
    inputs += ['docs/mainline/12-numerical-analysis-v2.md', 'tests/test_numerical_alignment.py']
    inherited = [book['v1_directory'] + '/' + name for name in ('receipt.json', 'runbook-copy.json', 'runs-index.json',
                  'assessment.json', 'full-check/summary.json')]
    inherited += [book['v1_directory'] + '/' + old_index[item['id']][str(h)]['archive']
                  for item in book['cases'] for h in book['reused_original_steps_s']]
    pinned = {}
    for group, names in [('pinned_tools', tools), ('execution_inputs', inputs), ('inherited_originals', inherited)]:
        pinned[group] = {name: file_sha(ROOT / name) for name in names}
        for name, identity in pinned[group].items():
            if is_runtime_cache(name) or git_blob_sha(ROOT, execution, name) != identity:
                raise ValueError('Uncommitted pinned refinement input/tool: ' + name)
    planned = ['declaration.json', 'protocol-copy.json', 'engineering-attempts.jsonl', 'runs-index.json',
               'assessment.json', 'capture-status.json', 'figures/refinement.png', 'figures/refinement.svg', 'figures/refinement.json']
    planned += [f"runs/{item['id']}/h-{h}.zip" for item in book['cases'] for h in book['newly_run_steps_s']]
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / 'declaration.json', dict(execution_commit=execution, declared_artifacts=planned,
        declared_tools=tools, declared_execution_inputs=inputs, declared_inherited_originals=inherited,
        runtime_cache_policy='__pycache__, .pyc and .pyo excluded BEFORE hashing; no runtime cache required',
        classification=book['classification'], full_regression_runs=0))
    write_new(output / 'protocol-copy.json', book)
    staging = ROOT / '.work/numerical-staging'
    staging.mkdir(parents=True, exist_ok=True)
    index, analyses, stage = {}, {}, None
    with (output / 'engineering-attempts.jsonl').open('x', encoding='utf-8', newline='\n') as ledger:
        def record(value):
            ledger.write(json.dumps(dict(value, execution_commit=execution), allow_nan=False) + '\n')
            ledger.flush()
        try:
            for item in book['cases']:
                name = item['id']
                index[name], analyses[name] = {}, {}
                for h in book['reused_original_steps_s']:
                    old = old_index[name][str(h)]
                    manifest, scenario, trace, balances = read_archive(safe_path(prior, old['archive']))
                    analysis = inspect_run(item, manifest, scenario, trace, balances)
                    analyses[name][str(h)] = analysis
                    index[name][str(h)] = dict(archive_root='inherited_v1', archive=old['archive'],
                        archive_sha256=old['archive_sha256'], original_members=old['original_members'],
                        source_commit=manifest['code_identity']['git_commit'], analysis=compact(analysis))
                base = load_scenario(ROOT / book['profile'])
                scenario = configured(base, item)
                numeric_record = next(row for row in scenario['parameters'] if row['id'] == 'step_time')
                numeric_record.update(valid_range=[.0025, numeric_record['valid_range'][1]], basis='synthetic_assumption',
                    source_note='Explicit ticket-12 engineering protocol v2: numerical range extension only; original V6 file unchanged.')
                for h in book['newly_run_steps_s']:
                    stage = name + '/' + str(h)
                    result = simulate_scenario(scenario, duration_s=item['duration_s'], step_s=h,
                        boundary_events=item['events'], work_requests=item['work_requests'])
                    if result['code_identity']['files'] != prior_receipt['runtime_sources'] or result['code_identity']['git_commit'] != execution or result['code_identity']['implementation_has_changes']:
                        raise ValueError('Runtime execution identity changed in refinement')
                    relative = f'runs/{name}/h-{h}.zip'
                    path = output / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with tempfile.TemporaryDirectory(dir=staging, prefix='refinement-') as temporary:
                        temp_path = Path(temporary).resolve()
                        if not temp_path.is_relative_to(staging.resolve()):
                            raise ValueError('Staging cleanup escaped the intended workspace')
                        save_run(result, temp_path / 'run')
                        with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                            for original in sorted((temp_path / 'run').iterdir()):
                                archive.writestr(original.name, original.read_bytes())
                    del result
                    manifest, saved, trace, balances = read_archive(path)
                    # The range/provenance record is the only scenario change
                    # from the original case, with all physical values equal.
                    with zipfile.ZipFile(safe_path(prior, old_index[name]['0.01']['archive'])) as original_archive:
                        old_scenario = json.loads(original_archive.read('scenario.json'))
                    check_numeric_range_extension(old_scenario, saved)
                    analysis = inspect_run(item, manifest, saved, trace, balances)
                    analyses[name][str(h)] = analysis
                    index[name][str(h)] = dict(archive_root='refinement', archive=relative, archive_sha256=file_sha(path),
                        original_members=member_identities(path), source_commit=execution, analysis=compact(analysis))
                    record(dict(case=name, maximum_step_s=h, outcome='ENGINEERING_COMPLETED', archive=relative, archive_sha256=file_sha(path)))
                    print('captured refinement ' + stage, flush=True)
            write_new(output / 'runs-index.json', index)
            assessment = assess(book, analyses)
            write_new(output / 'assessment.json', assessment)
            import numpy
            if numpy.__version__ != '2.3.5':
                raise ValueError('Use project-pinned NumPy 2.3.5')
            if args.plot_dependencies:
                sys.path.insert(0, str(args.plot_dependencies.resolve()))
            from plot_numerical_refinement import render
            figure = render(output)
            write_new(output / 'capture-status.json', dict(status='PASS', numerical_gate=assessment['all_declared_fixtures_qualified'],
                new_physical_runs=12, full_regression_runs=0, reused_full_source_identical=True))
        except Exception as error:
            record(dict(stage=stage, outcome='UNEXPECTED_FAILURE', error=repr(error)))
            write_new(output / 'capture-status.json', dict(status='FAIL', stage=stage, error=repr(error), traceback=traceback.format_exc()))
            raise
    actual = {p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file() and not is_runtime_cache(p)}
    if actual != set(planned):
        raise ValueError('Refinement durable set mismatch')
    write_new(output / 'receipt.json', dict(schema='aegisdc-numerical-refinement-receipt-v2', engineering_capture='PASS',
        delivery_gate='PENDING_COMMIT_AND_FRESH_CHECKOUT', execution_commit=execution,
        runtime_sources=prior_receipt['runtime_sources'], **pinned, artifacts={name: file_sha(output / name) for name in planned},
        numerical_gate=assessment['all_declared_fixtures_qualified'], full_regression_runs=0,
        inherited_full_tests=prior_receipt['full_tests'], inherited_runtime_source_identical=True,
        toolchain=dict(figure['toolchain'], python_executable=sys.executable, python_version=sys.version,
                       python_executable_sha256=file_sha(Path(sys.executable))),
        runtime_caches_required=0, research_trials=0, model_calls=0, training_calls=0))
    print(json.dumps(dict(capture='PASS', numerical_gate=assessment['all_declared_fixtures_qualified'], newly_run_archives=12)))


if __name__ == '__main__':
    main()
