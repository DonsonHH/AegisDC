"""Read-only M2 packet verification: bytes, Git, inert ZIPs and finite bridges."""
import argparse
import ast
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[4]
SOURCE = 'bcacbf78e4f071acd0a130c8dec85f5c95e4cc73'
PACKET = Path('evidence/mainline/engineering/M2-root-acceptance')


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def git(root, *arguments):
    return subprocess.check_output(['git', *arguments], cwd=root)


def tree(root, revision, *paths):
    result = {}
    for row in git(root, 'ls-tree', '-r', '-z', revision, '--', *paths).split(b'\0'):
        if row:
            header, name = row.split(b'\t', 1)
            result[name.decode('utf-8')] = header.split()[2].decode()
    return result


def blob_hashes(root, revision, names):
    names = sorted(set(names))
    data = subprocess.check_output(['git', 'cat-file', '--batch'], cwd=root,
        input=''.join(revision + ':' + n + '\n' for n in names).encode())
    offset, hashes = 0, {}
    for name in names:
        end = data.index(b'\n', offset)
        header = data[offset:end].split()
        require(len(header) == 3 and header[1] == b'blob', 'Missing delivery blob: ' + name)
        size = int(header[2]); start = end + 1
        hashes[name] = sha256(data[start:start + size]).hexdigest()
        offset = start + size + 1
    require(offset == len(data), 'Unexpected Git batch bytes')
    return hashes


def file_members(archive):
    require(len(archive.namelist()) == len(set(archive.namelist())), 'Duplicate ZIP member')
    return {name for name in archive.namelist() if not name.endswith('/')}


def bridges(root, folder):
    pre = read(folder / 'bridges/physical-kernel.json')
    definitions = []
    for revision in (pre['numerical_kernel_source'], pre['replay_source']):
        code = git(root, 'show', revision + ':src/aegis_dc/plant.py').decode('utf-8')
        definitions.append({n.name: ast.dump(n, include_attributes=False) for n in ast.parse(code).body
                            if isinstance(n, (ast.FunctionDef, ast.ClassDef))})
    for name in pre['unchanged_old_definitions']:
        require(definitions[0][name] == definitions[1][name], 'Kernel bridge changed: ' + name)
    require(len(pre['unchanged_old_definitions']) == 6 and '_Plant' in pre['unchanged_old_definitions'], 'Wrong bridge scope')
    raw = read(folder / 'bridges/combined-raw.json')
    archive = root / 'evidence/mainline/engineering/12-numerical/capture-04' / raw['numeric_archive']
    require(digest(archive) == raw['numeric_archive_sha256'], 'Numeric bridge ZIP changed')
    replay = root / 'evidence/mainline/engineering/13-replay/capture-04/combined-episode-CLI/trajectory'
    with zipfile.ZipFile(archive) as z:
        require(file_members(z) == {'run.json', 'scenario.json', 'private-state.jsonl', 'balances.jsonl'}, 'Bridge ZIP roles')
        for name, expected in raw['raw_file_comparison'].items():
            data = z.read(name)
            require(data == (replay / name).read_bytes(), 'Raw bridge differs: ' + name)
            require(sha256(data).hexdigest() == expected['numerical_sha256'] == expected['replay_sha256'], 'Bridge SHA')
        old = json.loads(z.read('run.json'))
    current = read(replay / 'run.json')
    require(old['code_identity']['git_commit'] == raw['numeric_execution'], 'Old bridge execution')
    require(current['code_identity']['git_commit'] == raw['replay_execution'], 'Replay bridge execution')
    for name in ('summary', 'work_records'):
        require(old[name] == current[name], 'Bridge ' + name)
    def schedule(rows):
        return sorted((r['time_s'], r['parameter_id'], r['value']) for r in rows)
    require(schedule(old['inputs']['boundary_events']) == schedule(current['inputs']['boundary_events'] + current['inputs']['action_commands']), 'Scheduled union changed')
    for name in ('duration_s', 'maximum_step_s', 'work_requests'):
        require(old['inputs'][name] == current['inputs'][name], 'Bridge input: ' + name)
    return {'unchanged_old_definitions': 6, 'raw_equal_files': 3, 'summary_and_work_equal': True,
            'scope': 'ONE saved combined240/h1 case and six old definitions; not a whole-runtime or true-error bound'}


def verify(root, delivery=None):
    root = root.resolve(); folder = root / PACKET
    declaration = read(folder / 'declaration.json'); receipt = read(folder / 'receipt.json')
    require(receipt['tested_source'] == SOURCE and receipt['delivery_gate'] == 'PENDING_COMMIT_AND_FRESH_CHECKOUT', 'Initial receipt identity')
    declared = set(declaration['declared_artifacts'])
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
    require(actual == declared | {'receipt.json'} and declared == set(receipt['artifacts']), 'Durable set differs')
    require(not any('__pycache__' in PurePosixPath(n).parts or PurePosixPath(n).suffix in {'.pyc', '.pyo'} for n in actual), 'Runtime cache delivered')
    for name, expected in receipt['artifacts'].items():
        require(digest(folder / name) == expected, 'Packet SHA: ' + name)
    if delivery:
        names = [str(PACKET / n).replace('\\', '/') for n in actual]
        hashes = blob_hashes(root, delivery, names)
        require(all(digest(root / name) == h for name, h in hashes.items()), 'Packet differs from delivery Git')
    preserved = read(folder / 'reviews/preservation.json'); members = 0
    for name, review in preserved['archives'].items():
        with zipfile.ZipFile(folder / name) as z:
            require(file_members(z) == set(review['members']), 'ZIP declaration: ' + name)
            for member, expected in review['members'].items():
                parts = PurePosixPath(member)
                require(not parts.is_absolute() and '..' not in parts.parts and '.git' not in parts.parts, 'Unsafe archive name')
                require('__pycache__' not in parts.parts and parts.suffix not in {'.pyc', '.pyo'}, 'Cache member')
                h, size = sha256(), 0
                with z.open(member) as stream:
                    for block in iter(lambda: stream.read(65536), b''):
                        h.update(block); size += len(block)
                require(h.hexdigest() == expected['sha256'] and size == expected['bytes'], 'ZIP original bytes: ' + member)
                members += 1
    summary = read(folder / 'raw/summary.json'); guard = read(folder / 'raw/source-guard.json')
    require(summary['tests']['run'] == summary['tests']['executed'] == 359, 'Actual root count')
    require(summary['tests']['failures'] == summary['tests']['errors'] == summary['tests']['skipped'] == 0, 'Root full result')
    require(summary['verified_original_files'] == 20 and summary['overall'] == 'PASS', 'Root old originals')
    require(guard['source_commit_before'] == guard['source_commit_after'] == SOURCE and guard['sources_unchanged'] and guard['head_unchanged'], 'Executed source guard')
    require(len(guard['actual_python_sources']) == 156, 'Source file count')
    for name, expected in guard['actual_python_sources'].items():
        require(digest(root / name) == expected, 'Tested Python byte changed: ' + name)
    subprocess.run(['git', 'diff', '--quiet', SOURCE, '--', 'src', 'scripts', 'tests', 'configs'], cwd=root, check=True)
    log = (folder / 'raw/tests.log').read_text(encoding='utf-8')
    for test in ('test_policy_masks_a_candidate_even_when_it_has_larger_logit', 'test_untrained_residual_preserves_exact_nominal_and_uses_no_posterior'):
        require(any(test in line and line.rstrip().endswith('ok') for line in log.splitlines()), 'Torch optional test not actually executed')
    manifest = read(folder / 'source-manifest.json')
    for name, expected in manifest['preserved_indexes'].items():
        require(digest(root / name) == expected, 'Historical index changed: ' + name)
    for name, expected in manifest['linked_inputs'].items():
        require(digest(root / name) == expected, 'Referenced accepted input changed: ' + name)
    require(tree(root, SOURCE, 'src/aegis_dc') == tree(root, manifest['replay_runtime_source'], 'src/aegis_dc'), 'Integrated runtime differs from e4')
    for subtree in ('src/patrol_rsi', 'paper'):
        require(tree(root, SOURCE, subtree) == tree(root, manifest['preserved_legacy_source'], subtree), 'Legacy/canonical tree changed')
    old_configs = tree(root, manifest['preserved_legacy_source'], 'configs')
    accepted_configs = tree(root, SOURCE, 'configs')
    require(all(accepted_configs.get(n) == h for n, h in old_configs.items()), 'An original canonical configuration changed')
    require(set(accepted_configs) - set(old_configs) == {'configs/full-facility-replay-example-v1.json'}, 'Unexpected added configuration')
    bridge = bridges(root, folder)
    progress = read(root / 'docs/mainline/progress.json')
    require(progress['status'] == 'active' and progress['current_ticket'] == '14' and progress['current_milestone'] == 'M3', 'Current frontier')
    states = {m['id']: m['status'] for m in progress['milestones']}
    require(states['M2'] == 'accepted' and states['M3'] == 'in_progress' and not progress['active_implementations'], 'Milestone/owner state')
    require(progress['research_trials']['attempts'] == 0, 'Research budget changed')
    for name in ('12-root.json', '13-root.json', 'M2.json'):
        gate = read(root / 'docs/mainline/evidence' / name)
        require(gate['status'] == 'ACCEPTED' and gate['actual_root_source'] == SOURCE, 'Root authority: ' + name)
    current = read(root / 'docs/current-research.json')
    require(current['fixed_sensors'] == 'present_with_sparse_coverage_and_variable_availability' and current['hidden_simulator_state_available_to_dispatch'] is False, 'Evidence boundary')
    links = 0
    for document in (folder / 'README.md', root / 'README.md', root / 'docs/MAINLINE.md', root / 'docs/NEXT.md'):
        for target in re.findall(r'\]\(([^)]+)\)', document.read_text(encoding='utf-8')):
            if '://' in target or target.startswith('#'):
                continue
            require((document.parent / target.split('#', 1)[0]).exists(), 'Local link: ' + target)
            links += 1
    return {'status': 'PASS' if delivery else 'LOCAL_VERIFIED_DELIVERY_NOT_YET_CHECKED',
            'actual_root_source': SOURCE, 'delivery_commit': delivery, 'packet_artifacts': len(declared),
            'terminal_receipt_git_checked': bool(delivery), 'review_archives': 4, 'review_zip_members': members,
            'root_tests': {'run': 359, 'executed': 359, 'failures': 0, 'errors': 0, 'skips': 0},
            'old_originals': 20, 'tested_python_files_unchanged': 156, 'local_links': links,
            'finite_bridge': bridge, 'runtime_caches_required': 0, 'zip_extraction': False,
            'new_model_runs': 0, 'new_full_suite_runs': 0, 'research_trials': 0,
            'root_metadata_is_not_test_execution_revision': True, 'overall_goal': 'ACTIVE'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--delivery-commit')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.root, args.delivery_commit)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result, ensure_ascii=False))
