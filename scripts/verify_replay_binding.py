"""Verify a frozen reader-v3 engineering delivery without rerunning the plant."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from aegis_dc.replay import read_attempt


def file_sha(path):
    return sha256(path.read_bytes()).hexdigest()


def cache(path):
    return '__pycache__' in {part.lower() for part in Path(path).parts} or Path(path).suffix.lower() in {'.pyc', '.pyo'}


def safe(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Artifact escapes its declared root')
    return path


def git_hashes(root, requests):
    """Hash exact committed bytes in one bounded batch, including binary blobs."""
    requests = sorted(set(requests))
    raw = subprocess.check_output(['git', 'cat-file', '--batch'], cwd=root,
                                  input=''.join(revision + ':' + name + '\n' for revision, name in requests).encode('utf-8'))
    result, cursor = {}, 0
    for key in requests:
        end = raw.find(b'\n', cursor)
        header = raw[cursor:end].split()
        if len(header) != 3 or header[1] != b'blob':
            raise ValueError('Missing committed delivery/source blob: ' + repr(key))
        size = int(header[2])
        start = end + 1
        result[key] = sha256(raw[start:start + size]).hexdigest()
        cursor = start + size + 1
    if cursor != len(raw):
        raise ValueError('Unexpected Git batch output')
    return result


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_outcomes(directory, book):
    pairs, refusals = {}, {}
    for case in book['positive_cases']:
        name = case['id']
        original, repeated = read_attempt(directory / name), read_attempt(directory / (name + '-replay'))
        require(original['record']['status'] == repeated['record']['status'] == 'COMPLETED', 'Positive replay did not complete')
        expected = dict(duration_s=case['expected_duration_s'], maximum_step_s=case['expected_maximum_step_s'])
        require(original['execution_inputs'] == repeated['execution_inputs'] == expected, 'Effective inputs differ from frozen literals')
        require(original['request']['duration_s'] == case['duration_s'] and original['request']['maximum_step_s'] == case['maximum_step_s'], 'Original declared request was changed')
        require(repeated['request']['duration_s'] == expected['duration_s'] and repeated['request']['maximum_step_s'] == expected['maximum_step_s'], 'Replay did not use validated actual inputs')
        one = {key: value for key, value in original['run'].items() if key not in {'code_identity', 'artifacts'}}
        two = {key: value for key, value in repeated['run'].items() if key not in {'code_identity', 'artifacts'}}
        require(one == two, 'Exact replay changed stored run semantics')
        require(one['summary']['delivered_service_unit_s'] == expected['duration_s'], 'Independent short normal service account failed')
        require(all(len(row['domains']) == 8 for row in one['trace']), 'Full facility was reduced')
        require(repeated['record']['replay_of']['attempt_sha256'] == original['record_sha256'], 'Replay origin pin differs')
        pairs[name] = dict(status='EXACT', execution_inputs=expected, states_each=len(one['trace']), intervals_each=len(one['balances']))
    for case in book['refusal_cases']:
        name = case['id']
        refused = read_attempt(directory / name)
        require(refused['record']['status'] == 'FAILED' and refused['record']['execution_kind'] == 'NOT_STARTED'
                and refused['run'] is None and refused['record']['failure']['stage'] == case['stage'], 'Origin contradiction acquired execution authority')
        artifact = case['artifact']
        require((directory / 'origins' / name / artifact).read_bytes() == (directory / name / 'origin' / artifact).read_bytes(), 'Offending origin bytes were not retained')
        require(json.loads((directory / (name + '-stdout.json')).read_text(encoding='utf-8')) == refused['record'], 'Actual CLI stdout differs from terminal refusal')
        refusals[name] = dict(status='FAILED_REQUEST', stage=case['stage'], execution_kind='NOT_STARTED', raw_bytes_preserved=True)
    return dict(status='PASS', exact_pairs=pairs, staged_refusals=refusals, completed_attempts=4, failed_requests=3,
                full_suite='NOT_RUN_THIS_REVISION', research_trials=0, model_calls=0, training_calls=0)


def verify(root, directory, delivery_commit):
    root, directory = root.resolve(), directory.resolve()
    relative = directory.relative_to(root).as_posix()
    receipt = json.loads((directory / 'receipt.json').read_text(encoding='utf-8'))
    declaration = json.loads((directory / 'declaration.json').read_text(encoding='utf-8'))
    require(receipt['schema'] == 'aegisdc-replay-binding-receipt-v1' and receipt['status'] == 'PASS'
            and receipt['delivery_gate'] == 'PENDING_COMMIT_AND_FRESH_CHECKOUT', 'Initial receipt failed or was rewritten')
    require(set(receipt['artifacts']) == set(declaration['declared_artifacts']), 'Initial durable declaration differs')
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob('*') if path.is_file() and not cache(path)}
    require(actual == set(receipt['artifacts']) | {'receipt.json'}, 'Unexpected/missing durable file')
    maps = [('runtime_sources', None), ('tools', 'declared_tools'), ('inputs', 'declared_inputs'), ('prior_durable_files', 'declared_prior_files')]
    for group, declared in maps:
        if declared:
            require(set(receipt[group]) == set(declaration[declared]), 'Declared provenance group differs: ' + group)
    requests = [(delivery_commit, relative + '/receipt.json')]
    requests += [(delivery_commit, relative + '/' + name) for name in receipt['artifacts']]
    for group, _ in maps:
        requests += [(revision, name) for name in receipt[group] for revision in (receipt['execution_commit'], delivery_commit)]
    prior = json.loads(safe(root, receipt['prior_capture'] + '/receipt.json').read_text(encoding='utf-8'))
    for group in ('runtime_sources', 'pinned_tools', 'execution_inputs', 'prior_durable_files'):
        requests += [(prior['execution_commit'], name) for name in prior[group]]
    committed = git_hashes(root, requests)
    require(file_sha(directory / 'receipt.json') == committed[(delivery_commit, relative + '/receipt.json')], 'Committed terminal receipt differs')
    for name, identity in receipt['artifacts'].items():
        require(not cache(name) and file_sha(safe(directory, name)) == committed[(delivery_commit, relative + '/' + name)] == identity, 'Durable artifact hash differs: ' + name)
    for group, _ in maps:
        for name, identity in receipt[group].items():
            require(not cache(name) and file_sha(safe(root, name)) == committed[(receipt['execution_commit'], name)]
                    == committed[(delivery_commit, name)] == identity, 'Source/tool/prior identity differs: ' + name)
    for group in ('runtime_sources', 'pinned_tools', 'execution_inputs', 'prior_durable_files'):
        for name, identity in prior[group].items():
            require(committed[(prior['execution_commit'], name)] == identity, 'Historical execution identity differs')
    require(prior['execution_commit'] == 'cf9b33900d8f349b9a8145c042bbffe03503c858'
            and prior['full_tests']['run'] == 345 and prior['full_tests']['executed'] == 343, 'Old full scope was changed')
    book = json.loads((directory / 'runbook-copy.json').read_text(encoding='utf-8'))
    checks = check_outcomes(directory, book)
    require(checks == json.loads((directory / 'independent-checks.json').read_text(encoding='utf-8')), 'Saved checks do not reproduce')
    names = [row['id'] + suffix for row in book['positive_cases'] for suffix in ('', '-replay')] + [row['id'] for row in book['refusal_cases']]
    for name in names:
        source = read_attempt(directory / name)['record']['source_identity']
        require(source['git_commit'] == receipt['execution_commit'] and source['implementation_has_changes'] is False
                and source['files'] == receipt['runtime_sources'], 'Attempt execution source differs')
    targets = json.loads((directory / 'target-summary.json').read_text(encoding='utf-8'))
    require(targets['failures'] == targets['errors'] == targets['skipped'] == 0 and targets['run'] > 0, 'Focused regression failed')
    return dict(status='PASS', execution_commit=receipt['execution_commit'], delivery_commit=delivery_commit,
                durable_artifacts=len(receipt['artifacts']), prior_durable_files=len(receipt['prior_durable_files']),
                completed_attempts=4, failed_requests=3, focused_tests=targets,
                historical_full_preserved=dict(source=prior['execution_commit'], run=345, executed=343, optional_skips=2),
                author_full_suite='NOT_RUN_THIS_REVISION', physics_rerun=False, target_rerun=False,
                runtime_caches_required=0, initial_pending_receipt_preserved=True, research_trials=0, model_calls=0, training_calls=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--delivery-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify(ROOT, args.directory, args.delivery_commit)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result, ensure_ascii=False))
