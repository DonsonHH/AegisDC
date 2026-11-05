"""Capture the frozen ticket 18 engineering checks or verify their committed outputs."""
import argparse
from fractions import Fraction
from hashlib import sha256
import json
from math import isclose, isfinite
import os
from pathlib import Path
import subprocess
import sys

from belief_engineering_oracle import build_oracle
from plot_belief_engineering import render


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = 'docs/mainline/18-belief-engineering-protocol.json'
PACKAGE = 'evidence/mainline/engineering/18-beliefs'
GATE = 'PENDING_ROOT_INTEGRATED_FULL_WITH_TORCH'
COUNTS = dict(new_physical_runs=0, registered_research_trials=0, llm_calls=0, training_calls=0)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return sha256(raw).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    with path.open('xb') as stream:
        stream.write(value if isinstance(value, bytes) else
                     (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8'))


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def blob_hash(revision, name):
    return digest(git('cat-file', 'blob', f'{revision}:{name}'))


def source_paths(protocol, revision):
    tracked = git('ls-tree', '-rz', '--name-only', revision, 'src', PACKAGE + '/development')
    names = tracked.decode('utf-8').strip('\0').split('\0')
    from belief_engineering_checks import PROTOCOL_PATH_ROLES
    return {
        'runtime_sources': sorted(name for name in names if name.startswith('src/') and name.endswith('.py')),
        'authoring_verification_tools': protocol['authoring_verification_tools'],
        'frozen_inputs': sorted([PROTOCOL, *[protocol[role] for role in PROTOCOL_PATH_ROLES],
                                 'docs/mainline/18-belief-updates.md', PACKAGE + '/.gitattributes',
                                 *[name for name in names if name.endswith('.log')]]),
    }


def durable(directory):
    return {path.relative_to(directory).as_posix() for path in directory.rglob('*')
            if path.is_file() and '__pycache__' not in path.parts and path.suffix not in {'.pyc', '.pyo'}}


def unchanged_sources(execution, pins):
    return (git('rev-parse', 'HEAD').decode().strip() == execution
            and all(digest((ROOT / name).read_bytes()) == expected
                    for group in pins.values() for name, expected in group.items()))


def capture(directory, protocol):
    require(not git('status', '--porcelain', '--untracked-files=all'), 'Execution checkout must be clean')
    require(Path(os.environ.get('PYTHONPATH', '')).resolve() == ROOT / 'src', 'Set PYTHONPATH to the execution checkout src')
    execution = git('rev-parse', 'HEAD').decode().strip()
    pins = {group: {name: blob_hash(execution, name) for name in names}
            for group, names in source_paths(protocol, execution).items()}
    for group in pins.values():
        for name, expected in group.items():
            require(digest((ROOT / name).read_bytes()) == expected, 'Execution file differs from Git: ' + name)
    directory.mkdir()
    attempt = dict(schema='aegisdc-belief-engineering-attempt-v1', classification='ENGINEERING_ONLY',
                   execution_commit=execution, output=directory.relative_to(ROOT).as_posix(),
                   executable=sys.executable, python=sys.version,
                   executable_sha256=digest(Path(sys.executable).read_bytes()),
                   pythonpath=os.environ['PYTHONPATH'], argv=sys.argv, **COUNTS)
    write(directory / 'attempt.json', attempt)
    receipt = dict(schema='aegisdc-belief-engineering-receipt-v1', execution_commit=execution,
                   global_regression_gate=GATE, field_calibration='PENDING', **COUNTS, **pins)
    declared = set(protocol['durable_outputs'])
    try:
        from belief_engineering_checks import exercise

        calibration, trajectory, archival_model, frame = exercise(ROOT, protocol)
        for name, value in [('calibration.json', calibration), ('archived-trajectory.json', trajectory),
                            ('archived-model.json', archival_model), ('cli-frame.json', frame)]:
            write(directory / name, value)
        cli_args = ['-B', '-X', 'utf8', '-m', 'aegis_dc.belief',
                    '--frame', str(directory / 'cli-frame.json'), '--model', protocol['reference_model']]
        cli = subprocess.run([sys.executable, *cli_args], cwd=ROOT, capture_output=True)
        receipt.update(cli_argv=cli_args, cli_exit_code=cli.returncode)
        write(directory / 'cli-stdout.raw', cli.stdout)
        write(directory / 'cli-stderr.raw', cli.stderr)
        require(cli.returncode == 0 and not cli.stderr, 'Belief CLI failed')
        for name, data in render(directory).items():
            write(directory / name, data)
        require(durable(directory) == declared, 'Capture differs from frozen durable declaration')
        receipt['status'] = 'PASS'
    except Exception as error:
        receipt.update(status='FAIL', error_type=type(error).__name__, error=str(error))
        raise
    finally:
        receipt['source_head_and_bytes_unchanged'] = unchanged_sources(execution, pins)
        if not receipt['source_head_and_bytes_unchanged']:
            receipt.update(status='FAIL', source_guard_error='Execution source or HEAD changed during capture')
        receipt['artifacts'] = {name: digest((directory / name).read_bytes()) for name in sorted(durable(directory))}
        write(directory / protocol['terminal_receipt'], receipt)
    require(receipt['source_head_and_bytes_unchanged'], 'Execution source or HEAD changed during capture')
    return receipt


def verify_calibration(directory, protocol, model):
    oracle = build_oracle((ROOT / protocol['finite_generator']).read_bytes())
    require(oracle == read(ROOT / protocol['calibration_oracle']), 'Independent finite oracle differs')
    data = read(directory / 'calibration.json')
    require(data['classification'] == 'EXACT_SYNTHETIC_GENERATOR_ONLY' and data['atom_count'] == oracle['atoms'] == 64
            and data['normalization'] == oracle['exact_total_probability'] == '1', 'Finite witness scope differs')
    rows = {(row['stage'], tuple(row['reports'])): row for row in data['pattern_rows']}
    expected_count = protocol['expected_calibration_rows']
    require(len(rows) == len(data['pattern_rows']) == expected_count, 'Conditional rows missing or duplicated')
    tolerance = protocol['absolute_numeric_tolerance']
    maximum = 0
    for stage, partition in oracle['outcome_partitions'].items():
        brier = Fraction(0)
        for row in partition['rows']:
            saved = rows[stage, tuple(row['reports'])]
            frequencies = row['exact_frequencies']
            require(saved['exact_probability'] == row['probability'] and saved['exact_frequencies'] == frequencies
                    and saved['inference'].keys() == frequencies.keys(), 'Saved witness identity differs')
            error = max(abs(saved['inference'][state] - float(Fraction(p))) for state, p in frequencies.items())
            require(error == saved['max_absolute_error'] and error <= tolerance, 'Saved posterior fails independent oracle')
            maximum = max(maximum, error)
            probabilities = {state: Fraction(str(p)) for state, p in saved['inference'].items()}
            for truth, frequency in frequencies.items():
                brier += Fraction(row['probability']) * Fraction(frequency) * sum(
                    (p - (state == truth)) ** 2 for state, p in probabilities.items())
        score = data['true_law_weighted_multiclass_brier'][stage]
        require(score['exact'] == partition['weighted_multiclass_brier'] and
                isclose(score['inference'], float(brier), abs_tol=tolerance, rel_tol=0) and
                isclose(score['inference'], float(Fraction(score['exact'])), abs_tol=tolerance, rel_tol=0),
                'Saved Brier score fails independent oracle')
    require(data['max_absolute_error'] == maximum and data['tolerance'] == tolerance
            and data['deliberately_wrong_comparators'] == oracle['negative_comparators'], 'Saved calibration summary differs')
    frame = read(directory / 'cli-frame.json')
    cli = read(directory / 'cli-stdout.raw')
    audits = {row['record_id']: row for row in cli['record_audit']}
    require(cli['schema'] == 'aegisdc-belief-result-v1' and cli['scope_id'] == model['scope']['id']
            and cli['facility_id'] == model['facility_id'] and cli['as_of_s'] == frame['as_of_s'] == 12
            and cli['posterior'] == rows['both-arrived', (True, True)]['inference']
            and cli['information_updates'] == ['hot-root', 'rectifier-root'] and cli['physical_actions'] == []
            and audits['hot-root']['observation_epoch'] == 0 and audits['rectifier-root']['observation_epoch'] == 1
            and audits['hot-carried-copy']['disposition'] == 'copy_not_a_factor'
            and (directory / 'cli-stderr.raw').read_bytes() == b'', 'Saved CLI does not match the witness')
    return dict(atom_count=oracle['atoms'], calibration_rows=expected_count, max_absolute_error=maximum)


def verify_archive(directory, protocol, model):
    archive = read(directory / 'archived-trajectory.json')
    original = read(ROOT / protocol['archived_public_snapshots'])[protocol['archived_snapshot_key']]
    archived_model = read(directory / 'archived-model.json')
    scope = dict(model['scope'], **protocol['archive_scope'])
    require(archived_model == dict(model, scope=scope) and archive['scope_id'] == scope['id']
            and scope['id'] != model['scope']['id'] and archive['facility_id'] == model['facility_id']
            and archive['domains'] == read(ROOT / protocol['public_nominal'])['domain_ids']
            and archive['classification'] == 'ARCHIVED_PUBLIC_V6_ENGINEERING', 'Archive and generator scope differ')
    records = {row['id']: row for row in original['records']}
    require(len(records) == len(original['records']) == archive['input_record_count'] ==
            protocol['original_archive_record_count'], 'Archived public count differs')
    frames = archive['frames']
    require([row['as_of_s'] for row in frames] == protocol['archived_as_of_s'], 'Saved decision instants differ')
    arrival = {row['as_of_s']: row['rectifier_record'] for row in protocol['archived_arrival_expectations']}
    for frame in frames:
        time = frame['as_of_s']
        visible = {key: row for key, row in records.items() if row['observed_at_s'] <= time and row['arrived_at_s'] <= time}
        require(frame['arrived_count'] == len(visible), 'Archived decision used an incorrect visibility gate')
        require(frame['status'] == ('UPDATED' if frame['used'] else 'PRIOR_PREDICTION'), 'Archive status differs')
        for item in frame['used']:
            source = visible[item['record_id']]
            require(item['observed_value'] == source['value'] and all(item[field] == source[field]
                    for field in ('source_id', 'observed_at_s', 'arrived_at_s', 'valid_until_s'))
                    and item['origin_id'] == source['provenance']['origin_id']
                    and item['copied_from_record_id'] is source['provenance']['copied_from_record_id'] is None,
                    'A used record differs from its visible archive origin')
        if time in arrival:
            require([row['record_id'] for row in frame['used'] if row['channel_id'] == 'fixed-low-power'] == [arrival[time]],
                    'Rectifier arrival boundary differs')
        variants = frame['posterior_by_variant']
        require(frame['posterior'] == variants[model['variants'][0]['id']], 'Archive reference variant differs')
        for posterior in variants.values():
            require(isclose(sum(posterior.values()), 1, abs_tol=1e-14, rel_tol=0) and
                    all(isfinite(p) and 0 <= p <= 1 for p in posterior.values()), 'Invalid saved posterior')
        for state, bounds in frame['assumption_envelope'].items():
            values = [posterior[state] for posterior in variants.values()]
            require(bounds == [min(values), max(values)], 'Saved envelope differs from variant range')
    return dict(archived_public_records=len(records), archived_frames=len(frames), arrival_boundaries=len(arrival))


def verify(directory, protocol, delivery):
    delivery = git('rev-parse', delivery).decode().strip()
    require(git('rev-parse', 'HEAD').decode().strip() == delivery, 'Check out the requested delivery revision')
    relative = directory.relative_to(ROOT).as_posix()
    terminal = protocol['terminal_receipt']
    receipt = read(directory / terminal)
    execution = receipt['execution_commit']
    git('merge-base', '--is-ancestor', execution, delivery)
    require(receipt['status'] == 'PASS' and receipt['cli_exit_code'] == 0 and receipt['global_regression_gate'] == GATE
            and receipt['field_calibration'] == 'PENDING' and receipt['source_head_and_bytes_unchanged'],
            'The original capture has a different gate, source guard or scope')
    require(all(receipt[key] == 0 for key in COUNTS), 'Capture scope counts differ')
    declared = set(protocol['durable_outputs'])
    require(declared == set(receipt['artifacts']) and durable(directory) == declared | {terminal},
            'Committed durable artifacts differ from declaration')
    for name, expected in receipt['artifacts'].items():
        require(digest((directory / name).read_bytes()) == expected == blob_hash(delivery, relative + '/' + name),
                'Original artifact differs: ' + name)
    require(digest((directory / terminal).read_bytes()) == blob_hash(delivery, relative + '/' + terminal),
            'Original receipt differs from delivery blob')
    for group, names in source_paths(protocol, execution).items():
        require(set(names) == set(receipt[group]), 'Pinned path set differs: ' + group)
        for name, expected in receipt[group].items():
            require(digest((ROOT / name).read_bytes()) == expected == blob_hash(execution, name) == blob_hash(delivery, name),
                    'Pinned execution or delivery source differs: ' + name)
    attempt = read(directory / 'attempt.json')
    require(attempt['execution_commit'] == execution and attempt['output'] == relative and
            attempt['classification'] == 'ENGINEERING_ONLY' and all(attempt[key] == 0 for key in COUNTS),
            'Original attempt ledger differs')
    model = read(ROOT / protocol['reference_model'])
    calibration = verify_calibration(directory, protocol, model)
    archive = verify_archive(directory, protocol, model)
    figures = render(directory)
    for name, expected in figures.items():
        require((directory / name).read_bytes() == expected, 'Data-derived figure differs: ' + name)
    return dict(schema='aegisdc-belief-fresh-delivery-proof-v1', status='PASS', execution_commit=execution,
                delivery_commit=delivery, durable_artifacts=len(declared), terminal_receipts=1,
                pinned_paths={group: len(receipt[group]) for group in source_paths(protocol, execution)},
                cli_saved_output_checked=True, svg_figures=len(figures), inference_rerun=False,
                source_head_and_bytes_unchanged=True,
                full_regression_rerun=False, runtime_caches_required=0, global_regression_gate=GATE,
                field_calibration='PENDING', **calibration, **archive, **COUNTS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['capture', 'verify'])
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--delivery')
    args = parser.parse_args()
    protocol = read(ROOT / PROTOCOL)
    directory = (ROOT / args.capture).resolve()
    require(directory.parent == ROOT / PACKAGE, 'Use a dedicated capture directory within ticket 18 evidence')
    if args.mode == 'capture':
        result = capture(directory, protocol)
    else:
        require(args.delivery, 'Verification requires a committed delivery revision')
        result = verify(directory, protocol, args.delivery)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, sort_keys=True))


if __name__ == '__main__':
    main()
