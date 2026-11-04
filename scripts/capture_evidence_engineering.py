"""Capture one frozen evidence engineering delivery and one full regression."""
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
from aegis_dc.evidence_ledger import EvidenceLedger
from acceptance import verify as full_check
from build_evidence_fixture import build
from evidence_engineering_checks import check_package
from plot_evidence_ledger import render


def file_sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def git_blob_sha(root, revision, name):
    result = subprocess.run(['git', 'show', revision + ':' + name], cwd=root, capture_output=True)
    if result.returncode:
        raise ValueError('Missing committed delivery blob: ' + name)
    return sha256(result.stdout).hexdigest()


def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def is_runtime_cache(path):
    return '__pycache__' in path.parts or path.suffix in {'.pyc', '.pyo'}


def pin_paths(root):
    sources = [p.relative_to(root).as_posix() for p in sorted((root / 'src').rglob('*.py'))]
    tools = [p.relative_to(root).as_posix() for folder in ('scripts', 'tests')
             for p in sorted((root / folder).glob('*.py'))]
    inputs = ['pyproject.toml', '.gitattributes', 'AGENTS.md', 'GLOSSARY.md',
              'docs/adr/0002-sparse-evidence-not-sensor-free.md', 'docs/adr/0003-complete-facility-mainline.md',
              '.scratch/full-facility-mainline/spec.md', 'docs/mainline/information-boundary.md',
              'docs/mainline/14-evidence-contract.md', 'docs/mainline/14-evidence-runbook.json',
              'configs/full-facility-evidence-v1.json', 'configs/full-facility-mainline-reserve-v6.json',
              'configs/materials/reference-r134a-saturation.json',
              'evidence/mainline/engineering/14-evidence/.gitattributes',
              'evidence/mainline/engineering/14-evidence/README.md']
    inputs += [p.relative_to(root).as_posix() for p in sorted(
        (root / 'evidence/mainline/engineering/14-evidence/development').glob('*.txt'))]
    return dict(runtime_sources=sorted(sources), authoring_verification_tools=sorted(tools), frozen_inputs=sorted(inputs))


def capture(directory):
    directory = directory.resolve()
    directory.relative_to(ROOT)
    execution = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, text=True)
    if dirty.strip():
        raise ValueError('Freeze and commit runtime, tools, fixture, runbook and format classifications before capture')
    pins = {group: {name: file_sha(ROOT / name) for name in names} for group, names in pin_paths(ROOT).items()}
    for entries in pins.values():
        for name, expected in entries.items():
            if git_blob_sha(ROOT, execution, name) != expected:
                raise ValueError('Uncommitted source/tool/input bytes: ' + name)
    book_path = ROOT / 'docs/mainline/14-evidence-runbook.json'
    book = json.loads(book_path.read_text(encoding='utf-8'))
    declared = ['declaration.json', 'runbook-copy.json', 'fixture-copy.json', 'fixture-rebuilt.json',
                'snapshots.json', 'commands.json', 'independent-checks.json', 'figure-checks.json',
                'capture-failure.txt', 'negative-inputs/invalid-unit.json', 'negative-inputs/malformed.json',
                'cli/public/snapshot.json', 'cli/overwrite-preservation.json',
                'figures/arrival-timeline.svg', 'figures/source-architecture.svg',
                'full-check/summary.json', 'full-check/tests.log', 'full-check/evidence.json']
    declared += ['cli/' + row['id'] + '.' + channel + suffix for row in book['cli']
                 for channel, suffix in [('stdout', '.json' if row['id'] == 'valid' else '.txt'), ('stderr', '.txt')]]
    directory.mkdir(parents=True, exist_ok=False)
    write(directory / 'declaration.json', dict(schema='aegisdc-evidence-delivery-declaration-v1',
        classification='ENGINEERING_NOT_RESEARCH', declared_artifacts=sorted(declared),
        terminal_receipt='receipt.json', runtime_caches='NOT_DELIVERABLE', pinned_paths=pin_paths(ROOT)))
    receipt = dict(schema='aegisdc-evidence-engineering-receipt-v1', execution_commit=execution,
        execution_started_utc=datetime.now(timezone.utc).isoformat(), engineering_capture='FAIL',
        delivery_gate='PENDING_COMMIT_AND_FRESH_CHECKOUT', **pins,
        python=dict(version=sys.version, implementation=sys.implementation.name, executable_sha256=file_sha(sys.executable)),
        numpy_version=importlib.metadata.version('numpy'), registered_research_trials=0,
        model_calls=0, training_calls=0, research_protocol=None, research_budget=None,
        research_gain_claim='NOT_ESTABLISHED', field_calibration='PENDING')
    failure = ''
    try:
        (directory / 'runbook-copy.json').write_bytes(book_path.read_bytes())
        (directory / 'fixture-copy.json').write_bytes((ROOT / book['fixture']).read_bytes())
        fixture = json.loads((directory / 'fixture-copy.json').read_text(encoding='utf-8'))
        write(directory / 'fixture-rebuilt.json', build())
        if (directory / 'fixture-rebuilt.json').read_bytes() != (directory / 'fixture-copy.json').read_bytes():
            raise ValueError('Authoring tool does not rebuild exact frozen fixture')
        ledger = EvidenceLedger(fixture)
        write(directory / 'snapshots.json', {case['id']: ledger.snapshot(case['as_of_s']) for case in book['snapshots']})
        (directory / 'negative-inputs').mkdir()
        (directory / 'cli').mkdir()
        invalid = json.loads(json.dumps(fixture))
        invalid['records'][0]['unit'] = 'kW'
        write(directory / 'negative-inputs/invalid-unit.json', invalid)
        (directory / 'negative-inputs/malformed.json').write_bytes(b'{"schema":')
        commands = []

        def cli(identifier, input_file, output=None):
            command = [sys.executable, '-X', 'utf8', '-m', 'aegis_dc', 'evidence',
                       '--ledger', str(input_file), '--as-of', '11']
            if output is not None:
                command += ['--output', str(output)]
            result = subprocess.run(command, cwd=ROOT, env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')), capture_output=True)
            suffix = '.json' if identifier == 'valid' else '.txt'
            (directory / ('cli/' + identifier + '.stdout' + suffix)).write_bytes(result.stdout)
            (directory / ('cli/' + identifier + '.stderr.txt')).write_bytes(result.stderr)
            commands.append(dict(id=identifier, argv=command, returncode=result.returncode))

        public = directory / 'cli/public'
        cli('valid', ROOT / book['fixture'], public)
        before = file_sha(public / 'snapshot.json')
        cli('invalid-unit', directory / 'negative-inputs/invalid-unit.json')
        cli('malformed', directory / 'negative-inputs/malformed.json')
        cli('overwrite', ROOT / book['fixture'], public)
        write(directory / 'commands.json', commands)
        write(directory / 'cli/overwrite-preservation.json', dict(
            unchanged=before == file_sha(public / 'snapshot.json'), before_sha256=before,
            after_sha256=file_sha(public / 'snapshot.json')))
        figures = directory / 'figures'
        figures.mkdir()
        render(fixture, figures)
        figure_checks = {}
        for name in ('arrival-timeline.svg', 'source-architecture.svg'):
            svg = ET.fromstring((figures / name).read_bytes())
            if svg.tag != '{http://www.w3.org/2000/svg}svg':
                raise ValueError('Invalid SVG root')
            figure_checks[name] = dict(sha256=file_sha(figures / name), width=svg.attrib['width'],
                                       height=svg.attrib['height'], elements=len(list(svg.iter())))
        write(directory / 'figure-checks.json', dict(status='PASS', author='scripts/plot_evidence_ledger.py',
            source_fixture_sha256=file_sha(directory / 'fixture-copy.json'), figures=figure_checks,
            units='s; K; W; m3/s; dimensionless binary', classification='ENGINEERING_INPUT_DIAGRAMS_NOT_DISPATCH'))
        checks = check_package(directory)
        write(directory / 'independent-checks.json', checks)
        regression = full_check(ROOT, directory / 'full-check')
        receipt.update(independent_checks=checks, full_regression_executions=1, full_tests=regression['tests'],
                       verified_historical_originals=regression['verified_original_files'])
        if regression['overall'] != 'PASS':
            raise ValueError('Full engineering regression failed; retain original logs')
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
    print(json.dumps({key: result[key] for key in ('engineering_capture', 'execution_commit', 'delivery_gate')}, ensure_ascii=False))
    raise SystemExit(0 if result['engineering_capture'] == 'PASS' else 1)
