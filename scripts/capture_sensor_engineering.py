"""One frozen sparse-observation capture from an original full-V6 saved run."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from aegis_dc.evidence_ledger import EvidenceLedger
from aegis_dc.sensor_channels import load_saved_trace, sample_trace
from capture_evidence_engineering import file_sha, git_blob_sha, is_runtime_cache, pin_paths, write
from plot_sensor_channels import render
from sensor_engineering_checks import check, require

BOOK = 'docs/mainline/16-sensor-runbook.json'


def pins(root, book):
    declared = pin_paths(root)
    declared['frozen_inputs'] += [BOOK, 'docs/mainline/16-observation-contract.md',
        'configs/full-facility-sensor-channels-v1.json', 'configs/full-facility-sensor-realization-private-v1.json',
        'evidence/mainline/engineering/16-sensors/.gitattributes', book['original_archive']]
    declared['frozen_inputs'] += [p.relative_to(root).as_posix() for p in sorted(
        (root / 'evidence/mainline/engineering/16-sensors/development').glob('*')) if p.is_file()]
    return {group: {name: file_sha(root / name) for name in sorted(set(names))} for group, names in declared.items()}


def original_identity(root, book):
    path = root / book['original_archive']
    require(file_sha(path) == book['original_archive_sha256'], 'Original full-V6 archive changed')
    with zipfile.ZipFile(path) as archive:
        run = json.loads(archive.read('run.json'))
        scenario = json.loads(archive.read('scenario.json'))
        identity = dict(archive=book['original_archive'], archive_sha256=file_sha(path),
            original_manifest_sha256=__import__('hashlib').sha256(archive.read('run.json')).hexdigest(),
            original_code_identity=run['code_identity'], original_scenario_sha256=run['scenario_sha256'],
            original_inputs=run['inputs'], facility_id=scenario['id'], entity_ids=[r['id'] for r in scenario['entities']])
        require(run['code_identity']['git_commit'] == book['original_execution_commit'], 'Original physical execution identity differs')
        require(run['inputs']['duration_s'] == book['original_duration_s']
                and run['inputs']['maximum_step_s'] == book['original_maximum_step_s'], 'Original time resolution differs')
        for name, expected in run['code_identity']['files'].items():
            require(git_blob_sha(root, book['original_execution_commit'], name) == expected, 'Historical physical source differs')
        first = json.loads(archive.read('private-state.jsonl').splitlines()[0])
        require(sorted(first['domains']) == book['expected_domain_ids'], 'The original is not the declared eight-domain scene')
    return identity


def capture(folder):
    folder = folder.resolve()
    folder.relative_to(ROOT)
    require(not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, text=True).strip(), 'Freeze source, tools and runbook before capture')
    execution = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    book = json.loads((ROOT / BOOK).read_text(encoding='utf-8'))
    require(folder.relative_to(ROOT).as_posix() == book['output_directory'], 'Use the frozen unique capture directory')
    require(importlib.metadata.version('numpy') == book['numpy_version'], 'Use the declared unchanged NumPy runtime')
    frozen = pins(ROOT, book)
    for entries in frozen.values():
        for name, expected in entries.items():
            require(git_blob_sha(ROOT, execution, name) == expected, 'Frozen source/input bytes differ: ' + name)
    artifacts = ['declaration.json', 'runbook-copy.json', 'profile-copy.json', 'realization-primary-private.json',
        'realization-mismatch-private.json', 'original-input-identity.json', 'mismatch-production-private.json',
        'public-model.json', 'snapshots.json', 'independent-checks.json', 'commands.json', 'negative-profile.json',
        'overwrite-preservation.json', 'capture-failure.txt', 'figure-receipt.json', 'source-guard.json', 'attempt-ledger.json',
        'cli-primary/production-private.json', 'cli-primary/public-model.json',
        'figures/signal-and-error.svg', 'figures/delivery-and-missing.svg', 'figures/static-coverage.svg',
        'full-check/summary.json', 'full-check/evidence.json', 'full-check/tests.log']
    artifacts += ['cli/' + name + '.' + stream + '.txt' for name in ('primary', 'model', 'overwrite', 'queued-profile')
                  for stream in ('stdout', 'stderr')]
    folder.mkdir(parents=True, exist_ok=False)
    write(folder / 'declaration.json', dict(schema='aegisdc-sensor-engineering-declaration-v1',
        declared_artifacts=artifacts, terminal_receipt='receipt.json', runtime_caches='NOT_DELIVERABLE',
        pinned_paths={group: sorted(entries) for group, entries in frozen.items()},
        classification='PRIVATE_OBSERVATION_ENGINEERING_NOT_RESEARCH'))
    receipt = dict(schema='aegisdc-sensor-engineering-receipt-v1', execution_commit=execution,
        engineering_capture='FAIL', delivery_gate='PENDING_COMMIT_AND_FRESH_CHECKOUT', **frozen,
        started_at_utc=datetime.now(timezone.utc).isoformat(), full_regression_executions=0,
        registered_research_trials=0, model_calls=0, training_calls=0, field_calibration='PENDING',
        research_gain_claim='NOT_ESTABLISHED', python=dict(version=sys.version,
            implementation=sys.implementation.name, executable_sha256=file_sha(sys.executable)),
        numpy_version=importlib.metadata.version('numpy'))
    failure, stage = '', 'freeze-inputs'
    try:
        (folder / 'runbook-copy.json').write_bytes((ROOT / BOOK).read_bytes())
        (folder / 'profile-copy.json').write_bytes((ROOT / book['profile']).read_bytes())
        (folder / 'realization-primary-private.json').write_bytes((ROOT / book['realization']).read_bytes())
        identity = original_identity(ROOT, book)
        write(folder / 'original-input-identity.json', identity)
        (folder / 'cli').mkdir()
        commands = []

        def cli(identifier, arguments, expected):
            command = [sys.executable, '-X', 'utf8', '-m', 'aegis_dc.sensor_channels'] + arguments
            done = subprocess.run(command, cwd=ROOT, env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')), capture_output=True)
            for stream, data in [('stdout', done.stdout), ('stderr', done.stderr)]:
                (folder / 'cli' / (identifier + '.' + stream + '.txt')).write_bytes(data)
            commands.append(dict(id=identifier, argv=command, exit_code=done.returncode))
            require(done.returncode == expected, 'Unexpected actual sensor CLI result: ' + identifier)
            return done

        stage = 'actual-private-saved-run-sampling'
        args = ['sample', '--profile', str(ROOT / book['profile']), '--archive', str(ROOT / book['original_archive']),
                '--realization', str(ROOT / book['realization']), '--output', str(folder / 'cli-primary')]
        cli('primary', args, 0)
        primary = json.loads((folder / 'cli-primary/production-private.json').read_text(encoding='utf-8'))
        profile = json.loads((folder / 'profile-copy.json').read_text(encoding='utf-8'))
        public = cli('model', ['model', '--profile', str(ROOT / book['profile'])], 0)
        require(json.loads(public.stdout) == primary['public_model'], 'Public model CLI contains different data')
        before = {name: file_sha(folder / 'cli-primary' / name) for name in ('production-private.json', 'public-model.json')}
        cli('overwrite', args, 2)
        require(before == {name: file_sha(folder / 'cli-primary' / name) for name in before}, 'Existing output changed')
        write(folder / 'overwrite-preservation.json', dict(status='PRESERVED', hashes=before))
        bad = deepcopy(profile)
        bad['ledger']['records'] = [deepcopy(primary['ledger']['records'][0])]
        write(folder / 'negative-profile.json', bad)
        cli('queued-profile', ['model', '--profile', str(folder / 'negative-profile.json')], 2)
        write(folder / 'commands.json', commands)
        stage = 'same-trace-private-calibration-mismatch'
        realization = json.loads((folder / 'realization-primary-private.json').read_text(encoding='utf-8'))
        realization['biases'][book['mismatch_bias_key']] = book['mismatch_bias_value']
        write(folder / 'realization-mismatch-private.json', realization)
        trace = load_saved_trace(ROOT / book['original_archive'])
        mismatch = sample_trace(profile, trace, realization)
        mismatch['private_input_identity'] = trace['private_metadata']
        del trace
        write(folder / 'mismatch-production-private.json', mismatch)
        write(folder / 'public-model.json', primary['public_model'])
        snapshots = {name: EvidenceLedger(primary['ledger']).snapshot(time) for name, time in book['snapshots'].items()}
        write(folder / 'snapshots.json', snapshots)
        write(folder / 'independent-checks.json', check(primary, mismatch, profile, snapshots, book))
        stage = 'saved-data-figures'
        render(folder)
        stage = 'one-frozen-full-regression'
        from acceptance import verify
        receipt['full_regression_executions'] = 1
        full = verify(ROOT, folder / 'full-check')
        receipt['full_tests'] = full['tests']
        receipt['verified_historical_originals'] = full['verified_original_files']
        require(full['overall'] == 'PASS', 'Frozen full regression failed; original output retained')
        for entries in frozen.values():
            for name, expected in entries.items():
                require(file_sha(ROOT / name) == expected, 'Source/input changed during capture: ' + name)
        final_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        final_dirty = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, text=True)
        require(final_commit == execution and not final_dirty.strip(), 'Execution revision changed during capture')
        write(folder / 'source-guard.json', dict(status='PASS', before_commit=execution, after_commit=final_commit,
            tracked_dirty_before=False, tracked_dirty_after=False,
            verified_paths=sum(map(len, frozen.values())), source_tool_input_bytes_unchanged=True))
        receipt.update(engineering_capture='PASS', produced_primary_records=len(primary['ledger']['records']),
            produced_mismatch_records=len(mismatch['ledger']['records']), measurement_polls=len(primary['private_audit']),
            old_physical_execution=identity['original_code_identity']['git_commit'], new_physical_runs=0)
        stage = 'complete'
    except Exception as error:
        failure = traceback.format_exc()
        receipt['failure'] = dict(stage=stage, type=type(error).__name__, message=str(error))
    finally:
        (folder / 'capture-failure.txt').write_text(failure, encoding='utf-8', newline='\n')
        before_ledger = {p.relative_to(folder).as_posix() for p in folder.rglob('*')
                         if p.is_file() and not is_runtime_cache(p)}
        if before_ledger != set(artifacts) - {'attempt-ledger.json'}:
            receipt['engineering_capture'] = 'FAIL'
        write(folder / 'attempt-ledger.json', dict(schema='aegisdc-sensor-engineering-attempt-ledger-v1',
            capture_id=book['capture_id'], attempt=1, output_directory=book['output_directory'],
            execution_commit=execution, classification='ENGINEERING_OBSERVATION_ADAPTER_NOT_RESEARCH',
            status=receipt['engineering_capture'], terminal_stage=stage, full_regression_executions=receipt['full_regression_executions'],
            new_physical_runs=0, registered_research_trials=0, model_calls=0, training_calls=0,
            failure=receipt.get('failure')))
        actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file() and not is_runtime_cache(p)}
        receipt['missing_declared_artifacts'] = sorted(set(artifacts) - actual)
        receipt['unexpected_durable_artifacts'] = sorted(actual - set(artifacts))
        if receipt['missing_declared_artifacts'] or receipt['unexpected_durable_artifacts']:
            receipt['engineering_capture'] = 'FAIL'
        receipt['artifacts'] = {name: file_sha(folder / name) for name in sorted(actual)}
        write(folder / 'receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = capture(args.output)
    print(json.dumps({name: result.get(name) for name in ('engineering_capture', 'execution_commit', 'produced_primary_records', 'full_tests', 'failure')}))
    raise SystemExit(0 if result['engineering_capture'] == 'PASS' else 1)
