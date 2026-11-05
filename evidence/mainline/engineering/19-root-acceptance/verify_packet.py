"""Verify accepted ticket19 root packet and both immutable source deliveries."""
import argparse
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[4]
PACKET = 'evidence/mainline/engineering/19-root-acceptance'
CHECKOUT_CRLF = {'configs/candidate-example.json', 'configs/event-priority.json', 'configs/feedback-study.json', 'configs/risk-response.json', 'configs/coupled-example.json', 'configs/demo.json', 'configs/event-validation.json', 'configs/event-validation-amendment-draft.json', 'configs/facility-structure-v0.1.json', 'configs/response-defer-study.json', 'configs/event-validation-amended.json', 'configs/parent-rule.json', 'configs/risk-method-demo.json'}


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
    paths = sorted(paths)
    raw = subprocess.check_output(['git', 'cat-file', '--batch'], cwd=root,
        input=''.join(revision + ':' + n + '\n' for n in paths).encode())
    result, offset = {}, 0
    for name in paths:
        end = raw.index(b'\n', offset); header = raw[offset:end].split()
        require(len(header) == 3 and header[1] == b'blob', 'Missing blob: ' + name)
        start, size = end + 1, int(header[2])
        result[name] = digest(raw[start:start + size]); offset = start + size + 1
    require(offset == len(raw), 'Unexpected Git blob data')
    return result

def verify(root, delivery):
    root = root.resolve(); packet = root / PACKET
    require(git(root, 'rev-parse', 'HEAD').decode().strip() == delivery, 'Wrong delivery checkout')
    require(not git(root, 'status', '--porcelain'), 'Delivery checkout is not clean')
    tool = Path(__file__).relative_to(root).as_posix()
    require(Path(__file__).read_bytes() == git(root, 'cat-file', 'blob', delivery + ':' + tool), 'Delivery tool differs from Git')
    receipt = read(packet / 'receipt.json'); declaration = read(packet / 'declaration.json')
    manifest = read(packet / 'source-manifest.json')
    actual = {p.relative_to(packet).as_posix() for p in packet.rglob('*') if p.is_file()
              and '__pycache__' not in p.parts and p.suffix not in {'.pyc', '.pyo'}}
    declared = set(declaration['artifacts'])
    require(actual == declared | {'receipt.json'} and declared == set(receipt['artifacts']), 'Durable set differs')
    for name, expected in receipt['artifacts'].items():
        require(digest((packet / name).read_bytes()) == expected, 'Packet artifact differs: ' + name)
    committed = blobs(root, delivery, [PACKET + '/' + n for n in actual])
    require(all(digest((root / n).read_bytes()) == h for n, h in committed.items()), 'Packet differs from Git')
    archive_members = read(packet / 'archive-members.json'); total_members = 0
    for name, members in archive_members.items():
        with zipfile.ZipFile(packet / name) as archive:
            require(len(archive.namelist()) == len(set(archive.namelist())) and set(archive.namelist()) == set(members), 'ZIP set differs')
            for member, expected in members.items():
                path = PurePosixPath(member)
                require(not path.is_absolute() and '..' not in path.parts and '__pycache__' not in path.parts
                        and path.suffix not in {'.pyc', '.pyo'}, 'Invalid ZIP member')
                raw = archive.read(member)
                require(digest(raw) == expected['sha256'] and len(raw) == expected['bytes'], 'ZIP bytes differ: ' + member)
                total_members += 1
    summary = read(packet / 'raw/summary.json'); guard = read(packet / 'raw/source-guard.json')
    tests = summary['tests']; source = manifest['tested_source']
    require(summary['overall'] == 'PASS' and tests['run'] == tests['executed'] and tests['executed'] > 434, 'Root tests incomplete')
    require(tests['errors'] == tests['failures'] == tests['skipped'] == 0 and summary['verified_original_files'] == 20, 'Root test/evidence failure')
    require(source == guard['source_commit_before'] == guard['source_commit_after'] and guard['head_unchanged']
            and guard['sources_unchanged'] and guard['sources_match_declared_git_checkout'], 'Root execution changed')
    committed_sources = guard['committed_sources']
    require(committed_sources == blobs(root, source, committed_sources) == blobs(root, delivery, committed_sources), 'Tested source differs')
    for name, expected in committed_sources.items():
        raw = (root / name).read_bytes()
        if digest(raw) != expected:
            require(name in CHECKOUT_CRLF, 'Unclassified checkout source differs: ' + name)
            original = git(root, 'cat-file', 'blob', delivery + ':' + name)
            attributes = git(root, 'check-attr', '-z', 'text', 'eol', '--', name).decode().split('\0')
            require(attributes == [name, 'text', 'auto', name, 'eol', 'unspecified', '']
                    and b'\r' not in original and raw == original.replace(b'\n', b'\r\n'),
                    'Checkout is not the exact declared LF-to-CRLF conversion: ' + name)
    author = manifest['author']
    author_total = 0
    for role in ('original', 'correction', 'correction_v2'):
        component = author[role]
        saved = read(root / component['capture'])
        require(digest((root / component['capture']).read_bytes()) == component['capture_sha256']
                and saved['execution_commit'] == component['execution'] and saved['status'] == 'PASS', 'Author '+role+' identity differs')
        names = set(saved['artifacts']) | {'receipt.json'}
        folder = str(PurePosixPath(component['capture']).parent)
        old_blobs = blobs(root, component['data_delivery'], [folder + '/' + n for n in names])
        require(all(digest((root / n).read_bytes()) == h for n, h in old_blobs.items()), 'Author '+role+' original changed')
        author_total += len(names)
        differences = []
        for group in component['pin_groups']:
            pins = saved[group]
            require(pins == blobs(root, component['execution'], pins), 'Recorded '+role+' execution pins differ')
            current = blobs(root, delivery, pins)
            for name, expected in pins.items():
                if current[name] != expected:
                    differences.append(name)
                else:
                    require(digest((root / name).read_bytes()) == expected, 'Author '+role+' unchanged source differs')
        require(sorted(differences) == component['allowed_source_changes'], 'Unclassified '+role+' source change')
    require(author['original']['allowed_source_changes'] == ['src/aegis_dc/risk_scenarios.py']
            and author['correction']['allowed_source_changes'] == ['src/aegis_dc/risk_scenarios.py']
            and author['correction_v2']['allowed_source_changes'] == [], 'Wrong correction classification')
    require(len(manifest['visuals']) == 2, 'Visual set incomplete')
    for name, item in manifest['visuals'].items():
        require(digest((packet / name).read_bytes()) == item['png_sha256']
                and digest((root / item['svg']).read_bytes()) == item['svg_sha256'], 'Visual source differs')
    gate = read(root / 'docs/mainline/evidence/19-root.json')
    require(gate['status'] == 'ACCEPTED' and gate['actual_root_source'] == source
            and gate['packet_receipt_sha256'] == digest((packet / 'receipt.json').read_bytes()), 'Root authority differs')
    progress = read(root / 'docs/mainline/progress.json')
    require(progress['status'] == 'active' and progress['current_ticket'] == '20' and progress['current_milestone'] == 'M3'
            and next(m['status'] for m in progress['milestones'] if m['id'] == 'M3') == 'in_progress'
            and progress['research_trials']['attempts'] == 0, 'Frontier or research scope differs')
    require(manifest['reviews']['standards_findings'] == manifest['reviews']['spec_findings'] == 0
            and manifest['reviews']['independent_assertions'] == 720, 'Review result differs')
    return dict(status='PASS',delivery_commit=delivery,actual_root_source=source,packet_artifacts=len(declared),
        archive_members=total_members,root_tests=tests,guarded_files=len(committed_sources),historical_originals=20,
        author_originals=author_total,visuals=2,independent_assertions=720,
        delivery_verifier=tool,delivery_verifier_sha256=digest(Path(__file__).read_bytes()),
        exact_crlf_checkout_paths=sorted(CHECKOUT_CRLF),source_classification='Original1939and9cnumericcorrectionandnew99fullhorizonkeptseparate',
        full_regression_rerun=False,inference_rerun=False,new_physical_runs=0,registered_research_trials=0,
        llm_calls=0,training_calls=0,runtime_caches_required=0,overall_goal='ACTIVE')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delivery-commit', required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); result = verify(ROOT, args.delivery_commit)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result, ensure_ascii=False))
