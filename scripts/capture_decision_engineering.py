"""Capture one frozen ticket15 engineering audit and one full regression."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from acceptance import verify as full_check
from build_decision_fixture import build
from decision_engineering_checks import check_package, require
from plot_decision_privacy import render

BOOK = 'docs/mainline/15-truth-runbook.json'
FIXTURE = 'configs/full-facility-decision-v1'
FIGURES = ('hidden-world-witness.svg', 'decision-boundary-architecture.svg')


def file_sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def git_blob_sha(root, revision, name):
    result = subprocess.run(['git', 'show', revision + ':' + name], cwd=root, capture_output=True)
    require(result.returncode == 0, 'Missing committed source/delivery blob: ' + name)
    return sha256(result.stdout).hexdigest()


def is_runtime_cache(path):
    return '__pycache__' in path.parts or path.suffix in {'.pyc', '.pyo'}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def pin_paths(root):
    sources = [p.relative_to(root).as_posix() for p in sorted((root / 'src').rglob('*.py'))]
    tools = [p.relative_to(root).as_posix() for folder in ('scripts', 'tests')
             for p in sorted((root / folder).glob('*.py'))]
    inputs = ['pyproject.toml', '.gitattributes', 'AGENTS.md', 'GLOSSARY.md',
        'docs/adr/0002-sparse-evidence-not-sensor-free.md', 'docs/adr/0003-complete-facility-mainline.md',
        '.scratch/full-facility-mainline/spec.md', 'docs/mainline/information-boundary.md',
        'docs/mainline/15-decision-contract.md', BOOK,
        'configs/full-facility-mainline-reserve-v6.json', 'configs/full-facility-evidence-v1.json',
        'configs/materials/reference-r134a-saturation.json',
        'evidence/mainline/engineering/15-truth/README.md',
        'evidence/mainline/engineering/15-truth/.gitattributes']
    inputs += [p.relative_to(root).as_posix() for folder in (FIXTURE, 'tests/fixtures',
        'evidence/mainline/engineering/15-truth/development') for p in sorted((root / folder).rglob('*'))
        if p.is_file() and not is_runtime_cache(p)]
    return dict(runtime_sources=sorted(sources), authoring_verification_tools=sorted(tools), frozen_inputs=sorted(inputs))


def declared_artifacts():
    names = ['declaration.json', 'runbook-copy.json', 'commands.json', 'audit.stdout.txt', 'audit.stderr.txt',
        'independent-checks.json', 'figure-checks.json', 'capture-failure.txt',
        'full-check/summary.json', 'full-check/tests.log', 'full-check/evidence.json',
        'audit/runbook-copy.json', 'audit/audit-summary.json', 'audit/audit-status.json']
    names += ['figures/' + name for name in FIGURES]
    for group in ('fixture-copy', 'fixture-rebuilt'):
        names += [group + '/' + name for name in build()]
    for world in ('A', 'B'):
        names += [f'audit/private-worlds/{world}/{name}'
                  for name in ('run.json', 'scenario.json', 'private-state.jsonl', 'balances.jsonl')]
        for stream in ('common', 'open', 'closed'):
            names += [f'audit/evaluator-traces/{world}/{stream}/private-decision-trace.json']
            names += [f'audit/cli-transcripts/{world}/{stream}.{suffix}'
                      for suffix in ('stdout.txt', 'stderr.txt', 'command.json')]
    return sorted(names)


def capture(directory):
    directory = directory.resolve()
    directory.relative_to(ROOT)
    execution = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, text=True)
    require(not dirty.strip(), 'Commit the frozen source/tools/inputs before capture')
    declared = declared_artifacts()
    pins = {group: {name: file_sha(ROOT / name) for name in names} for group, names in pin_paths(ROOT).items()}
    for entries in pins.values():
        for name, identity in entries.items():
            require(git_blob_sha(ROOT, execution, name) == identity, 'Uncommitted frozen bytes: ' + name)
    directory.mkdir(parents=True, exist_ok=False)
    write(directory / 'declaration.json', dict(schema='aegisdc-decision-delivery-declaration-v1',
        classification='FULL_V6_INFORMATION_FLOW_ENGINEERING_NOT_POLICY_RESEARCH',
        declared_artifacts=declared, terminal_receipt='receipt.json',
        runtime_caches='NOT_DELIVERABLE', pinned_paths=pin_paths(ROOT)))
    receipt = dict(schema='aegisdc-decision-engineering-receipt-v1', execution_commit=execution,
        execution_started_utc=datetime.now(timezone.utc).isoformat(), engineering_capture='FAIL',
        delivery_gate='PENDING_COMMIT_AND_FRESH_CHECKOUT', **pins,
        python=dict(version=sys.version, implementation=sys.implementation.name, executable_sha256=file_sha(sys.executable)),
        numpy_version=importlib.metadata.version('numpy'), registered_research_trials=0,
        model_calls=0, training_calls=0, research_gain_claim='NOT_ESTABLISHED', field_calibration='PENDING')
    failure = ''
    try:
        (directory / 'runbook-copy.json').write_bytes((ROOT / BOOK).read_bytes())
        for group in ('fixture-copy', 'fixture-rebuilt'):
            (directory / group).mkdir()
        for name, document in build().items():
            (directory / 'fixture-copy' / name).write_bytes((ROOT / FIXTURE / name).read_bytes())
            write(directory / 'fixture-rebuilt' / name, document)
            require((directory / 'fixture-copy' / name).read_bytes() == (directory / 'fixture-rebuilt' / name).read_bytes(),
                    'Canonical public input does not reproduce: ' + name)
        command = [sys.executable, '-B', '-X', 'utf8', str(ROOT / 'scripts/audit_decision_privacy.py'),
                   '--output', str(directory / 'audit')]
        done = subprocess.run(command, cwd=ROOT, env=dict(os.environ,
            PYTHONPATH=str(ROOT / 'src'), PYTHONDONTWRITEBYTECODE='1'), capture_output=True)
        (directory / 'audit.stdout.txt').write_bytes(done.stdout)
        (directory / 'audit.stderr.txt').write_bytes(done.stderr)
        write(directory / 'commands.json', [dict(argv=command, returncode=done.returncode)])
        require(done.returncode == 0, 'Actual paired audit failed; retain the original stdout/stderr and failure status')
        checks = check_package(directory)
        write(directory / 'independent-checks.json', checks)
        (directory / 'figures').mkdir()
        render(directory, directory / 'figures')
        figures = {}
        for name in FIGURES:
            path = directory / 'figures' / name
            svg = ET.fromstring(path.read_bytes())
            require(svg.tag == '{http://www.w3.org/2000/svg}svg', 'Invalid SVG root')
            figures[name] = dict(sha256=file_sha(path), width=svg.attrib['width'], height=svg.attrib['height'],
                                elements=len(list(svg.iter())))
        write(directory / 'figure-checks.json', dict(status='PASS', figures=figures,
            source_data='Saved actual paired plant audit and detached public current-frame traces',
            author='scripts/plot_decision_privacy.py',
            visual_inspection='PENDING_ROOT_RENDER', classification='PRIVATE_ENGINEERING_EVALUATOR_FIGURES_NOT_DISPATCH_INPUT'))
        regression = full_check(ROOT, directory / 'full-check')
        receipt.update(independent_checks=checks, full_regression_executions=1, full_tests=regression['tests'],
                       verified_historical_originals=regression['verified_original_files'])
        require(regression['overall'] == 'PASS', 'Full engineering regression failed; retain original logs')
        receipt['engineering_capture'] = 'PASS'
    except Exception as error:
        failure = traceback.format_exc()
        receipt['failure'] = dict(type=type(error).__name__, message=str(error))
    finally:
        (directory / 'capture-failure.txt').write_text(failure, encoding='utf-8', newline='\n')
        durable = sorted(path.relative_to(directory).as_posix() for path in directory.rglob('*')
                         if path.is_file() and not is_runtime_cache(path))
        receipt['missing_declared_artifacts'] = sorted(set(declared) - set(durable))
        receipt['unexpected_durable_artifacts'] = sorted(set(durable) - set(declared))
        if receipt['missing_declared_artifacts'] or receipt['unexpected_durable_artifacts']:
            receipt['engineering_capture'] = 'FAIL'
        receipt['artifacts'] = {name: file_sha(directory / name) for name in durable}
        receipt['runtime_caches_required'] = 0
        receipt['execution_ended_utc'] = datetime.now(timezone.utc).isoformat()
        write(directory / 'receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = capture(args.output)
    print(json.dumps({key: result[key] for key in ('engineering_capture', 'execution_commit', 'delivery_gate')}))
    raise SystemExit(0 if result['engineering_capture'] == 'PASS' else 1)
