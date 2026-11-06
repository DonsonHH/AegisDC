"""Verify ticket26 root delivery from original bytes, without project execution."""
import argparse
from hashlib import sha256
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[4]
PACKET = 'evidence/mainline/engineering/26-root-acceptance'
CHECKOUT_CRLF = {'configs/candidate-example.json', 'configs/event-priority.json', 'configs/feedback-study.json',
    'configs/risk-response.json', 'configs/coupled-example.json', 'configs/demo.json', 'configs/event-validation.json',
    'configs/event-validation-amendment-draft.json', 'configs/facility-structure-v0.1.json',
    'configs/response-defer-study.json', 'configs/event-validation-amended.json', 'configs/parent-rule.json',
    'configs/risk-method-demo.json'}


def read(path):
    return json.loads(path.read_bytes())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return sha256(raw).hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root)


def blobs(root, revision, paths):
    names = sorted(set(paths))
    raw = subprocess.check_output(['git', 'cat-file', '--batch'], cwd=root,
        input=''.join(revision + ':' + name + '\n' for name in names).encode())
    result, offset = {}, 0
    for name in names:
        end = raw.index(b'\n', offset)
        header = raw[offset:end].split()
        require(len(header) == 3 and header[1] == b'blob', 'Missing Git blob: ' + name)
        start, size = end + 1, int(header[2])
        result[name] = digest(raw[start:start + size])
        offset = start + size + 1
    require(offset == len(raw), 'Unexpected Git bytes')
    return result


def verify(root, delivery):
    root = root.resolve()
    packet = root / PACKET
    require(git(root, 'rev-parse', 'HEAD').decode().strip() == delivery and not git(root, 'status', '--porcelain'), 'Use clean requested delivery checkout')
    receipt, declaration, manifest = (read(packet / name) for name in ('receipt.json', 'declaration.json', 'source-manifest.json'))
    actual = {path.relative_to(packet).as_posix() for path in packet.rglob('*') if path.is_file()
        and '__pycache__' not in path.parts and path.suffix not in {'.pyc', '.pyo'}}
    require(actual == set(declaration['artifacts']) | {'receipt.json'} and
        set(receipt['artifacts']) == set(declaration['artifacts']), 'Root durable set differs')
    for name, expected in receipt['artifacts'].items():
        require(digest((packet / name).read_bytes()) == expected, 'Root artifact differs: ' + name)
    require(all(digest((root / name).read_bytes()) == expected for name, expected in
        blobs(root, delivery, [PACKET + '/' + name for name in actual]).items()), 'Root committed blobs differ')
    archive_members = read(packet / 'archive-members.json')
    total_members = 0
    for name, members in archive_members.items():
        with zipfile.ZipFile(packet / name) as archive:
            require(len(archive.namelist()) == len(set(archive.namelist())) and set(archive.namelist()) == set(members), 'Root ZIP member set differs')
            for member, expected in members.items():
                path = PurePosixPath(member)
                require(not path.is_absolute() and '..' not in path.parts and '__pycache__' not in path.parts
                    and path.suffix not in {'.pyc', '.pyo'}, 'Undeclared cache/unsafe ZIP member')
                raw = archive.read(member)
                require(digest(raw) == expected['sha256'] and len(raw) == expected['bytes'], 'Root ZIP member differs')
                total_members += 1
    lifecycle = read(packet / 'root-regression-lifecycle.json')
    require(lifecycle['full_attempts'] == 2 and lifecycle['fully_accepted_runs'] == 1 and lifecycle['interrupted_runs'] == 1
        and not lifecycle['first']['root_full_pass_proven'] and not lifecycle['first']['summary_exists']
        and not lifecycle['first']['original_terminal_exists'] and not lifecycle['finite_frozen_capture_repeated'], 'Interrupted root run was relabeled')
    require(lifecycle['source'] == lifecycle['second']['source'] == manifest['tested_source'], 'Root lifecycle source differs')
    old_cases = set(lifecycle['first']['observed_case_directories'])
    new_cases = set(lifecycle['second']['new_case_directories'])
    require(len(old_cases) == 18 and new_cases and not old_cases & new_cases, 'Root fixture attempt sets overlap')
    require({row['case'] for row in manifest['root_regression_attempts']} == old_cases | new_cases, 'Root fixture lifecycle incomplete')
    with zipfile.ZipFile(packet / 'support.zip') as support:
        observation = json.loads(support.read('26-root-full-interruption-01/observation.json'))
        require(digest(support.read('26-root-full-interruption-01/observation.json')) == lifecycle['first']['observation_sha256']
            and observation['status'] == 'TRANSPORT_INTERRUPTED_NO_COMPLETE_ROOT_ACCEPTANCE'
            and observation['source'] == manifest['tested_source'], 'Interrupted attempt observation differs')
        require(digest(support.read('26-root-full-launch-02/attempt.json')) == lifecycle['second']['attempt_sha256']
            and digest(support.read('26-root-full-launch-02/terminal.json')) == lifecycle['second']['terminal_sha256'], 'Completed attempt records differ')
        terminal = json.loads(support.read('26-root-full-launch-02/terminal.json'))
        require(terminal['status'] == 'COMPLETED' and terminal['returncode'] == 0
            and terminal['source'] == manifest['tested_source'], 'Root second attempt incomplete')
        interrupted_members = json.loads(support.read('26-root-full-interruption-01/members.json'))
        with zipfile.ZipFile(io.BytesIO(support.read('26-root-full-interruption-01/originals.zip'))) as interrupted_archive:
            require(len(interrupted_archive.namelist()) == len(set(interrupted_archive.namelist())) and
                set(interrupted_archive.namelist()) == set(interrupted_members), 'Interrupted originals snapshot set differs')
            for name, identity in interrupted_members.items():
                original = interrupted_archive.read(name)
                require(digest(original) == identity['sha256'] and len(original) == identity['bytes'], 'Interrupted snapshot original changed')
                if name.startswith('development/'):
                    current_name = 'original/' + name.removeprefix('development/')
                    require(archive_members['root-regression-originals.zip'][current_name] == identity, 'Interrupted fixture was rewritten after observation')
    with zipfile.ZipFile(packet / 'root-regression-originals.zip') as originals:
        root_members = archive_members['root-regression-originals.zip']
        execution_guard = read(packet / 'raw/source-guard.json')
        expected_runtime = {name: value for name, value in execution_guard['actual_sources'].items()
            if name.startswith('src/') and name.endswith('.py')}
        require(expected_runtime == {name: value for name, value in execution_guard['committed_sources'].items()
            if name.startswith('src/') and name.endswith('.py')}, 'Actual runtime guard differs from committed execution bytes')
        expected_run_identity = {name: value for name, value in expected_runtime.items()
            if name.startswith('src/aegis_dc/') or name == 'src/patrol_rsi/contracts.py'}
        require(len(root_members) == manifest['root_regression_original_members'], 'Root original member count differs')
        for record in manifest['root_regression_attempts']:
            prefix = 'original/' + record['case'] + '/'
            attempt = json.loads(originals.read(prefix + 'attempt.json'))
            terminal = json.loads(originals.read(prefix + 'terminal.json'))
            require(attempt['source_commit'] == manifest['tested_source'] and terminal['status'] == record['terminal_status'], 'Root original source/status changed')
            require(attempt['source_files'] == expected_runtime, 'Root attempt runtime set/hash differs from actual executed source guard')
            require(record['root_full_attempt'] == ('01_INTERRUPTED' if record['case'] in old_cases else '02_COMPLETED'), 'Root fixture attempt attribution differs')
            for name, expected in attempt['source_files'].items():
                require(digest(originals.read(prefix + 'runtime-source/' + name)) == expected, 'Root original runtime snapshot differs')
            if prefix + 'original/run.json' in root_members:
                run = json.loads(originals.read(prefix + 'original/run.json'))
                require(run['code_identity']['git_commit'] == manifest['tested_source'] and
                    not run['code_identity']['implementation_has_changes'], 'Root actual run source differs')
                require(run['code_identity']['files'] == expected_run_identity, 'Root run byte identity differs from executed runtime guard')
                for name, identity in run['artifacts'].items():
                    require(digest(originals.read(prefix + 'original/' + name)) == identity['sha256'], 'Root original artifact differs')
                require(json.loads(originals.read(prefix + 'model.json')) == json.loads(originals.read(prefix + 'original/scenario.json'))
                    and json.loads(originals.read(prefix + 'dispatch-program.json')) == run['inputs']['dispatch_program'], 'Root original actual input differs')
    summary, guard = read(packet / 'raw/summary.json'), read(packet / 'raw/source-guard.json')
    tests = summary['tests']
    source = manifest['tested_source']
    require(summary['overall'] == 'PASS' and tests['run'] == tests['executed'] > 538 and
        tests['errors'] == tests['failures'] == tests['skipped'] == 0 and summary['verified_original_files'] == 20, 'Integrated full gate failed')
    require(source == guard['source_commit_before'] == guard['source_commit_after'] and guard['head_unchanged']
        and guard['sources_unchanged'] and guard['sources_match_declared_git_checkout'], 'Integrated source guard failed')
    identities = guard['committed_sources']
    require(identities == blobs(root, source, identities) == blobs(root, delivery, identities), 'Executed source/delivery differs')
    require(set(guard['actual_sources']) == set(identities), 'Actual execution source set differs')
    original_conversions = {}
    for name, expected in identities.items():
        if guard['actual_sources'][name] != expected:
            original = git(root, 'cat-file', 'blob', source + ':' + name)
            require(name in CHECKOUT_CRLF and b'\r' not in original and
                digest(original.replace(b'\n', b'\r\n')) == guard['actual_sources'][name], 'Original execution has an unclassified source conversion')
            original_conversions[name] = dict(rule='exact_lf_to_crlf_checkout', actual_sha256=guard['actual_sources'][name],
                committed_sha256=expected, crlf_count=original.count(b'\n'))
    require(guard['checkout_classification'] == original_conversions, 'Original execution conversion classification differs')
    conversions = []
    for name, expected in identities.items():
        raw = (root / name).read_bytes()
        if digest(raw) != expected:
            original = git(root, 'cat-file', 'blob', delivery + ':' + name)
            require(name in CHECKOUT_CRLF and b'\r' not in original and raw == original.replace(b'\n', b'\r\n'), 'Unclassified checkout byte difference: ' + name)
            conversions.append(name)
    # These imported verification modules use only saved JSON, stdlib and Git.
    sys.path.insert(0, str(root / 'scripts'))
    import candidate_delivery
    import verify_candidate_development
    author = manifest['author']
    capture = root / author['folder']
    saved = read(capture / 'receipt.json')
    require(saved['execution_commit'] == author['execution'] and
        digest((capture / 'receipt.json').read_bytes()) == author['receipt_sha256'], 'Original author identity differs')
    names = [author['folder'] + '/' + name for name in set(saved['artifacts']) | {'receipt.json'}]
    require(all(digest((root / name).read_bytes()) == expected for name, expected in
        blobs(root, author['data_delivery'], names).items()), 'Original data delivery changed')
    author_check = candidate_delivery.verify(capture, read(root / candidate_delivery.PROTOCOL), delivery)
    require(author_check['status'] == 'PASS' and author_check['selector_calls'] == 10 and
        author_check['physical_runs'] == 6 and author_check['simulated_duration_s'] == 36, 'Formal engineering budget differs')
    development_check = verify_candidate_development.verify(root / manifest['development']['folder'], delivery)
    require(development_check['public_attempt_directories'] == 30 and development_check['unobserved_outcomes'] == 1
        and development_check['historical_input_or_tool_gap_cases'] == 26, 'Historic development failure/gap accounting changed')
    require(len(manifest['visuals']) == 3, 'Actual data/value/boundary visual set incomplete')
    for name, identity in manifest['visuals'].items():
        require(digest((packet / name).read_bytes()) == identity['png_sha256'] and
            digest((root / identity['svg']).read_bytes()) == identity['svg_sha256'], 'Rendered visual source differs')
    require(manifest['visual_review']['status'] == 'PASS' and manifest['visual_review']['actually_viewed_pngs'] == 3
        and manifest['visual_review']['open_findings'] == 0, 'Actual visual QA missing')
    require(all(review['unresolved'] == 0 and review['checks'] > 0 for review in manifest['reviews']), 'Unresolved independent review')
    with zipfile.ZipFile(packet / 'reviews.zip') as archive:
        for review in manifest['reviews']:
            require(digest(archive.read(review['member'])) == review['sha256'], 'Independent review changed')
    gate = read(root / 'docs/mainline/evidence/26-root.json')
    require(gate['status'] in {'CANDIDATE_PENDING_FRESH_DELIVERY', 'ACCEPTED'} and gate['actual_root_source'] == source
        and gate['author_source'] == author['execution'] and gate['author_data_delivery'] == author['data_delivery']
        and gate['packet_receipt_sha256'] == digest((packet / 'receipt.json').read_bytes()), 'Root authority differs')
    progress = read(root / 'docs/mainline/progress.json')
    require(progress['status'] == 'active' and progress['current_milestone'] == 'M4' and
        progress['current_ticket'] in {'26', '27'} and progress['research_trials']['attempts'] == 0, 'Frontier or research scope differs')
    require(git(root, 'rev-parse', 'pre-meeting-20261103^{}').decode().strip() == '076d9aa15c5bc99a5b7985f296e15543b7b0f3d7', 'Premeeting source changed')
    return dict(status='PASS', delivery_commit=delivery, actual_root_source=source,
        packet_artifacts=len(declaration['artifacts']), archive_members=total_members, root_tests=tests,
        guarded_files=len(identities), historical_originals=20, author_originals=len(names),
        selector_calls=10, physical_runs=6, simulated_duration_s=36, scheduled_online_decisions=21,
        development_attempt_dirs=30, development_unknowns=1, development_historical_gap_cases=26,
        visuals=3, independent_review_packets=len(manifest['reviews']), exact_crlf_checkout_paths=conversions,
        root_regression_original_members=manifest['root_regression_original_members'],
        root_full_attempts=2, root_full_completed=1, root_full_interrupted=1,
        delivery_verifier=Path(__file__).relative_to(root).as_posix(),
        delivery_verifier_sha256=digest(Path(__file__).read_bytes()), new_selector_calls=0, new_physical_runs=0,
        full_regression_rerun=False, registered_research_trials=0, field_calibration='PENDING', overall_goal='ACTIVE')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delivery-commit', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = verify(ROOT, args.delivery_commit)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result, ensure_ascii=False))
