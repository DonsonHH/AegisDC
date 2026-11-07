"""Check the committed ticket 27 packet and saved runs without executing the model."""
import argparse
import json
from hashlib import sha256
from pathlib import Path, PurePosixPath
import subprocess
import sys
import zipfile


PACKET = 'evidence/mainline/engineering/27-root-acceptance'
AUTHORITY = 'docs/mainline/evidence/27-root.json'
AUTHOR = 'evidence/mainline/engineering/27-full-loop'
ORIGINAL_SOURCE = '36ae97cc17e4b9297017289e285d00abaee29929'
ORIGINAL_DATA = '3ffa95d6e966443287f6b32f156413ce9587edae'
REPLAY_SOURCE = '83a66f1c3abe0b2613d0700448b22f82e576f3b7'
AUTHOR_DATA = 'be0612c29c41b6df67b1fddc91b96a7ec217ae94'
ROOT_SOURCE = 'a97d09eb19b7d64b38f2042075221627f9255fa7'
PREMEETING = '076d9aa15c5bc99a5b7985f296e15543b7b0f3d7'
REVIEW_COUNTS = {'Spec': 402, 'Standards': 373}
REVIEW_SEALS = {
    'Spec': '863b8e61b65a94d93c996ab3f611df585e9ffeab11f0584a21df70c32f0dc203',
    'Standards': '85b453e102db3242f6e06cbd7f43be7c7d7f0604bae79b764891932d7268ff82',
}
FIGURES = {f'27-{name}.{ext}' for name in ('actual-loop', 'evidence-architecture') for ext in ('png', 'svg')}
FIXTURE_GROUPS = ('26-online-development', '27-development', '27-replay-development')
CONFIG_CRLF = {
    'configs/candidate-example.json', 'configs/coupled-example.json', 'configs/demo.json',
    'configs/event-priority.json', 'configs/event-validation-amended.json',
    'configs/event-validation-amendment-draft.json', 'configs/event-validation.json',
    'configs/facility-structure-v0.1.json', 'configs/feedback-study.json', 'configs/parent-rule.json',
    'configs/response-defer-study.json', 'configs/risk-method-demo.json', 'configs/risk-response.json',
}


def require(condition, description):
    if not condition:
        raise ValueError(description)


def digest(raw):
    return sha256(raw).hexdigest()


def identity(raw):
    return {'sha256': digest(raw), 'bytes': len(raw)}


def read(path):
    return json.loads(path.read_bytes())


def write_new(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def durable(name):
    path = PurePosixPath(name)
    return '__pycache__' not in path.parts and path.suffix not in {'.pyc', '.pyo'}


def durable_files(folder):
    return {p.relative_to(folder).as_posix() for p in folder.rglob('*')
            if p.is_file() and durable(p.relative_to(folder).as_posix())}


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root)


def tracked(root, rev, *scope):
    return set(git(root, 'ls-tree', '-rz', '--name-only', rev, '--', *scope).decode().strip('\0').split('\0')) - {''}


def blobs(root, rev, paths):
    ordered = sorted(paths)
    if not ordered:
        return {}
    raw = subprocess.check_output(['git', 'cat-file', '--batch'], cwd=root,
                                  input=''.join(f'{rev}:{p}\n' for p in ordered).encode())
    offset, result = 0, {}
    for name in ordered:
        newline = raw.index(b'\n', offset)
        fields = raw[offset:newline].split()
        require(len(fields) == 3 and fields[1] == b'blob', f'Missing Git blob: {rev}:{name}')
        size = int(fields[2])
        start = newline + 1
        result[name] = raw[start:start+size]
        offset = start + size + 1
    require(offset == len(raw), 'Git batch returned unexpected trailing bytes')
    return result


def verify_archive(packet, name, manifest):
    with zipfile.ZipFile(packet / name) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)) and set(names) == set(manifest), f'Archive roles differ: {name}')
        for member in names:
            path = PurePosixPath(member)
            require(durable(member) and not path.is_absolute() and '..' not in path.parts
                    and path.as_posix() == member and '\\' not in member, f'Invalid archive member: {member}')
            require(identity(archive.read(member)) == manifest[member], f'Archive bytes differ: {name}:{member}')
    return len(names)


def verify_reviews(packet, records, members):
    review_sources = set()
    declared = set()
    final_counts = {}
    with zipfile.ZipFile(packet / 'reviews.zip') as archive:
        for row in records:
            prefix = row['folder'] + '/'
            seal = archive.read(prefix + row['seal'])
            review = json.loads(archive.read(prefix + 'review.json'))
            require(digest(seal) == row['seal_sha256'], f'Review seal changed: {prefix}')
            require(all(review[key] == row[key] for key in ('axis', 'checks', 'status', 'unresolved')), f'Review verdict changed: {prefix}')
            bound = json.loads(seal)['artifacts']
            declared |= {prefix + row['seal'], *(prefix + name for name in row['unsealed_git_exports'])}
            for name, expected in bound.items():
                member = prefix + name
                require(members[member] == expected, f'Original review manifest disagrees: {member}')
                declared.add(member)
            review_sources.add(review.get('source', review.get('data')))
            if row['folder'].startswith('27-saved-'):
                axis = row['axis']
                require(not row['unresolved'] and row['status'].startswith('PASS')
                        and review.get('source', review.get('data')) == AUTHOR_DATA
                        and row['checks'] == REVIEW_COUNTS[axis] and row['seal_sha256'] == REVIEW_SEALS[axis]
                        and review.get('project_calls', review.get('new_project_calls')) == 0,
                        f'Independent final {axis} gate did not pass')
                final_counts[axis] = row['checks']
    require(declared == set(members) and final_counts == REVIEW_COUNTS and len(review_sources) >= 6,
            'Independent review history or final gates incomplete')
    return final_counts


def verify_fixtures(packet, attempt, groups, members, guard):
    require(set(attempt['fixture_baseline']) == set(groups) == set(FIXTURE_GROUPS), 'Fixture group roles differ')
    observed_cases = {group: set() for group in groups}
    for name in members:
        group, case, _ = name.split('/', 2)
        observed_cases[group].add(case)
    runtime = {name: sha for name, sha in guard['actual_sources'].items() if name.startswith('src/') and name.endswith('.py')}
    with zipfile.ZipFile(packet / 'root-fixtures.zip') as archive:
        for group, cases in groups.items():
            require(set(cases) == observed_cases[group] and not set(cases) & set(attempt['fixture_baseline'][group]),
                    f'New and previous root fixtures overlap or are missing: {group}')
            for case in cases:
                prefix = f'{group}/{case}/'
                is_replay = group == '27-replay-development'
                attempt_path = 'development-attempt.json' if is_replay else 'attempt.json'
                source_dir = 'runtime-source/' if group == '26-online-development' else 'pre-call/'
                record = json.loads(archive.read(prefix + attempt_path))
                require(record['source_commit'] == ROOT_SOURCE, f'Root fixture execution source differs: {prefix}')
                observed_runtime = {name: sha for name, sha in record['source_files'].items() if name in runtime}
                require(observed_runtime == runtime, f'Incomplete root fixture source set: {prefix}')
                for name, sha in record['source_files'].items():
                    require(members[prefix + source_dir + name]['sha256'] == sha, f'Root fixture pre-call pin differs: {prefix}{name}')
                terminal_path = 'recorded/attempt.json' if is_replay else 'terminal.json'
                terminal = json.loads(archive.read(prefix + terminal_path))
                require(terminal['status'] == cases[case], f'Root fixture terminal state differs: {prefix}')
                for member in members:
                    if member.startswith(prefix) and member.endswith('/run.json'):
                        run = json.loads(archive.read(member))
                        code = run['code_identity']
                        require(code['git_commit'] == ROOT_SOURCE and not code['implementation_has_changes']
                                and all(runtime[name] == sha for name, sha in code['files'].items()),
                                f'Root fixture recorded run source differs: {member}')
                        for name, artifact in run['artifacts'].items():
                            candidate = member.removesuffix('run.json') + name
                            require(members[candidate]['sha256'] == artifact['sha256'], f'Root fixture recorded run payload differs: {candidate}')
    return {group: len(cases) for group, cases in groups.items()}


def verify(root, delivery):
    packet = root / PACKET
    require(git(root, 'rev-parse', 'HEAD').decode().strip() == delivery and not git(root, 'status', '--porcelain'),
            'Verify from a clean checkout at the requested packet delivery commit')
    require(git(root, 'rev-parse', 'pre-meeting-20261103^{}').decode().strip() == PREMEETING, 'Pre-meeting tag changed')
    receipt, declaration, inventory = (read(packet / name) for name in ('receipt.json', 'declaration.json', 'inventory.json'))
    names = set(declaration['artifacts'])
    packet_names = names | {'receipt.json'}
    require(len(names) == len(declaration['artifacts']) and names == set(receipt['artifacts'])
            and receipt['status'] == 'CANDIDATE_PENDING_FRESH_DELIVERY'
            and declaration['terminal'] == 'receipt.json' and receipt['tested_source'] == ROOT_SOURCE
            and durable_files(packet) == packet_names, 'Packet durable roles differ')
    git_names = {f'{PACKET}/{name}' for name in packet_names}
    require(tracked(root, delivery, PACKET) == git_names, 'Committed packet tree has different membership')
    for path, raw in blobs(root, delivery, git_names).items():
        require((root / path).read_bytes() == raw, f'Packet checkout differs from Git: {path}')
        if not path.endswith('/receipt.json'):
            require(identity(raw) == receipt['artifacts'][path.removeprefix(PACKET + '/')], f'Packet artifact hash differs: {path}')
    require(set(inventory['archives']) == set(declaration['archive_roles']) == {'reviews.zip', 'root-fixtures.zip'}
            and all(sorted(members) == declaration['archive_roles'][name] for name, members in inventory['archives'].items()),
            'Incorrect archive set or predeclared member roles')
    archive_members = {name: verify_archive(packet, name, members) for name, members in inventory['archives'].items()}
    reviews = verify_reviews(packet, inventory['reviews'], inventory['archives']['reviews.zip'])
    with zipfile.ZipFile(packet / 'reviews.zip') as archive:
        for row in inventory['reviews']:
            exports = row['unsealed_git_exports']
            for name, raw in blobs(root, AUTHOR_DATA, [n.removeprefix('export/') for n in exports]).items():
                require(archive.read(f"{row['folder']}/export/{name}") == raw, f'Unsealed export differs from fixed author Git blob: {name}')
    summary, guard, evidence = (read(packet / 'raw' / name) for name in ('summary.json', 'source-guard.json', 'evidence.json'))
    tests = summary['tests']
    require(summary['overall'] == summary['evidence'] == summary['engineering'] == tests['gate'] == 'PASS'
            and summary['research'] == 'NOT_RUN'
            and tests['executed'] == tests['run'] == 567
            and tests['failures'] == tests['errors'] == tests['skipped'] == 0
            and summary['verified_original_files'] == evidence['verified_original_files'] == 20, 'Full integrated engineering gate differs')
    log = (packet / 'raw/tests.log').read_text(encoding='utf-8')
    require('Ran 567 tests in ' in log and log.rstrip().endswith('OK')
            and all(name in log for name in ('test_recorded_online_dispatch_reexecutes', 'test_actual_delivered_rate_arrives_later',
                                              'test_service_instrument_refuses')), 'Actual full log lacks ticket 27 tests')
    require(guard['source_commit_before'] == guard['source_commit_after'] == ROOT_SOURCE
            and guard['sources_unchanged'] and guard['head_unchanged'] and guard['sources_match_declared_git_checkout'],
            'Root source guard differs')
    runtime = guard['committed_sources']
    guarded = {name for name in tracked(root, ROOT_SOURCE, 'src', 'scripts', 'tests', 'configs') if name.endswith(('.py', '.json'))}
    require(set(runtime) == set(guard['actual_sources']) == guarded, 'Runtime/tool/test/config guard set differs')
    source_blobs = blobs(root, ROOT_SOURCE, guarded)
    require(runtime == {name: digest(raw) for name, raw in source_blobs.items()}
            and source_blobs == blobs(root, delivery, guarded), 'Runtime files differ from execution revision')
    conversions, executed_conversions = [], {}
    for name, raw in source_blobs.items():
        if guard['actual_sources'][name] != runtime[name]:
            converted = raw.replace(b'\n', b'\r\n')
            require(name in CONFIG_CRLF and b'\r' not in raw and digest(converted) == guard['actual_sources'][name],
                    f'Undeclared execution source conversion: {name}')
            executed_conversions[name] = dict(rule='exact_lf_to_crlf_checkout', actual_sha256=digest(converted),
                                               committed_sha256=runtime[name], crlf_count=raw.count(b'\n'))
        working = (root / name).read_bytes()
        if working != raw:
            require(name in CONFIG_CRLF and b'\r' not in raw and working == raw.replace(b'\n', b'\r\n'),
                    f'Undeclared clean checkout source conversion: {name}')
            conversions.append(name)
    require(guard['checkout_classification'] == executed_conversions, 'Execution source conversion inventory differs')
    attempt, terminal, process = (read(packet / 'launch' / name) for name in ('attempt.json', 'terminal.json', 'process.json'))
    require(attempt['status'] == 'STARTED' and attempt['source'] == process['source'] == terminal['source'] == ROOT_SOURCE
            and terminal['status'] == 'COMPLETED' and terminal['returncode'] == 0 and terminal['summary_exists']
            and terminal['stdout_sha256'] == digest((packet / 'launch/stdout.txt').read_bytes())
            and terminal['stderr_sha256'] == digest((packet / 'launch/stderr.txt').read_bytes())
            and attempt['classification'] == 'SINGLE_INTEGRATED_ENGINEERING_REGRESSION_NOT_FORMAL_CAPTURE'
            and attempt['runner_sha256'] == guard['runner_sha256'] == digest((packet / 'tools/root_runner.py').read_bytes())
            and attempt['launcher_sha256'] == digest((packet / 'tools/root_launcher.py').read_bytes())
            and attempt['python_executable_sha256'] == guard['python_executable_sha256'], 'Root launch is not bound to its completed execution')
    require(read(packet / 'launch/stdout.txt')['root_gate'] == 'PASS', 'Root launch stdout does not confirm PASS')
    fixtures = verify_fixtures(packet, attempt, inventory['root_fixture_cases'], inventory['archives']['root-fixtures.zip'], guard)

    pinned = {}
    for version, names in (
        (ORIGINAL_DATA, ('capture-20261107-02', 'capture-02-launch')),
        (AUTHOR_DATA, ('capture-20261107-03', 'capture-03-launch')),
    ):
        paths = tracked(root, version, *(f'{AUTHOR}/{name}' for name in names))
        require(len(paths) == (21 if version == ORIGINAL_DATA else 25), 'Frozen capture role count differs')
        for name, raw in blobs(root, version, paths).items():
            require((root / name).read_bytes() == raw, f'Frozen capture checkout changed: {name}')
            pinned[name] = raw
        require({name: pinned[name] for name in paths} == blobs(root, delivery, paths), 'Frozen capture delivery Git changed')
    old = read(root / AUTHOR / 'capture-20261107-02/receipt.json')
    require(old['status'] == 'FAIL' and old['source'] == ORIGINAL_SOURCE, 'Original outer failure relabeled')
    sys.path.insert(0, str(root / 'scripts'))
    import full_loop_delivery
    import full_loop_development_v2
    protocol = read(root / full_loop_delivery.PROTOCOL)
    formal = full_loop_delivery.verify(root / protocol['output'], protocol, delivery)
    require(formal['status'] == 'PASS' and formal['source'] == REPLAY_SOURCE and formal['artifacts'] == 17
            and formal['retained_original_runs'] == formal['replay_runs'] == 1 and formal['combined_simulated_duration_s'] == 20,
            'Retained original and single replay gate differs')
    service = full_loop_development_v2.verify_service(root / AUTHOR / 'development-service-20261107-02', delivery)
    replay = full_loop_development_v2.replay_checks(root / AUTHOR / 'development-replay-20261107-01', delivery)

    rendered, visual_qa = (read(packet / 'figures' / n) for n in ('render.json', 'visual-review.json'))
    figure_origins = {
        **{f'original/{name}': f'{AUTHOR}/capture-20261107-02/original/trajectory/{name}'
           for name in ('run.json', 'private-state.jsonl', 'scenario.json')},
        'replay/checks.json': f'{AUTHOR}/capture-20261107-03/checks.json',
    }
    require(rendered['source'] == {name: digest(pinned[rel]) for name, rel in figure_origins.items()}
            and rendered['renderer_sha256'] == digest((packet / 'tools/render_27_loop.py').read_bytes())
            and set(rendered['artifacts']) == FIGURES
            and all(digest((packet / 'figures' / name).read_bytes()) == sha for name, sha in rendered['artifacts'].items())
            and visual_qa['status'] == 'PASS' and visual_qa['verified_images'] ==
                {name: rendered['artifacts'][name] for name in FIGURES if name.endswith('.png')},
            'Displayed figures are not bound to actual saved data and visual inspection')
    draft = read(packet / 'visual-draft/render.json')
    first = visual_qa['initial_render']
    require(first['status'] == 'SUPERSEDED_VISUAL_ONLY'
            and first['render_json_sha256'] == digest((packet / 'visual-draft/render.json').read_bytes())
            and set(draft['artifacts']) == FIGURES and draft['source'] == rendered['source']
            and all(digest((packet / 'visual-draft' / name).read_bytes()) == sha for name, sha in draft['artifacts'].items())
            and first['architecture_png_sha256'] == draft['artifacts']['27-evidence-architecture.png']
            and draft['artifacts']['27-actual-loop.png'] == rendered['artifacts']['27-actual-loop.png'],
            'Visual-only correction lost the initial render or changed the source data')
    gate = read(root / AUTHORITY)
    require(gate['status'] in {'CANDIDATE_PENDING_FRESH_DELIVERY', 'ACCEPTED'} and gate['actual_root_source'] == ROOT_SOURCE
            and gate['packet_receipt_sha256'] == digest((packet / 'receipt.json').read_bytes()), 'Root authority does not bind packet')
    return dict(status='PASS', delivery_commit=delivery, actual_root_source=ROOT_SOURCE,
                root_tests=tests, historical_originals=20, guarded_files=len(guarded),
                exact_crlf_checkout_paths=sorted(conversions), packet_artifacts=len(names),
                archive_members=archive_members, final_review_checks=reviews, root_fixture_counts=fixtures,
                formal=formal, development_service=service, development_replay=replay,
                original_attempt_status='OUTER_FAIL_INNER_COMPLETED_RETAINED', original_data=ORIGINAL_DATA,
                verified_capture_and_launch_artifacts=len(pinned), viewed_pngs=2,
                new_physics=0, new_selector_calls=0, new_full_regression=False, registered_research_trials=0,
                field_calibration='PENDING', overall_goal='ACTIVE', verifier_sha256=digest(Path(__file__).read_bytes()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delivery-commit', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = verify(Path(__file__).resolve().parents[4], args.delivery_commit)
    write_new(args.output, result)
    print(json.dumps(result, ensure_ascii=False))
