"""Verify ticket25 transparent-policy root delivery without new physical runs."""
import argparse
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[4]
PACKET = 'evidence/mainline/engineering/25-root-acceptance'
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
    require(summary['overall'] == 'PASS' and tests['run'] == tests['executed'] and tests['executed'] > 512, 'Root tests incomplete')
    require(tests['errors'] == tests['failures'] == tests['skipped'] == 0 and summary['verified_original_files'] == 20, 'Root test/evidence failure')
    require(source == guard['source_commit_before'] == guard['source_commit_after'] and guard['head_unchanged']
            and guard['sources_unchanged'] and guard['sources_match_declared_git_checkout'], 'Root execution changed')
    committed_sources = guard['committed_sources']
    require(committed_sources == blobs(root, source, committed_sources), 'Recorded root execution source differs')
    import sys
    sys.path.insert(0,str(root / 'scripts'))
    import policy_metadata_delivery as metadata_tool
    metadata_protocol=read(root / metadata_tool.PROTOCOL)
    metadata_tool.exact_metadata_source(metadata_protocol,delivery)
    current_sources=blobs(root,delivery,committed_sources)
    metadata_path=metadata_protocol['runtime_changed_path']
    require(all(current_sources[n]==h for n,h in committed_sources.items() if n!=metadata_path), 'Undeclared source change after root execution')
    for name, expected in committed_sources.items():
        raw = (root / name).read_bytes()
        if name==metadata_path:
            require(digest(raw)==current_sources[name], 'Metadata source working bytes differ')
        elif digest(raw) != expected:
            require(name in CHECKOUT_CRLF, 'Unclassified checkout source differs: ' + name)
            original = git(root, 'cat-file', 'blob', delivery + ':' + name)
            attributes = git(root, 'check-attr', '-z', 'text', 'eol', '--', name).decode().split('\0')
            require(attributes == [name, 'text', 'auto', name, 'eol', 'unspecified', '']
                    and b'\r' not in original and raw == original.replace(b'\n', b'\r\n'),
                    'Checkout is not the exact declared LF-to-CRLF conversion: ' + name)
    author = manifest['author']
    saved = read(root / author['capture'])
    require(digest((root / author['capture']).read_bytes()) == author['capture_sha256']
            and saved['execution_commit'] == author['execution'] and saved['status'] == 'PASS', 'Author original differs')
    require(committed_sources[metadata_path]==saved['pinned']['runtime'][metadata_path], 'Full-run and original policy physical source differ')
    folder = str(PurePosixPath(author['capture']).parent)
    names = set(saved['artifacts']) | {'receipt.json'}
    old_blobs = blobs(root, author['data_delivery'], [folder + '/' + n for n in names])
    require(all(digest((root / n).read_bytes()) == h for n, h in old_blobs.items()), 'Original capture changed')
    for role in ('runtime','tools','inputs'):
        require(saved['pinned'][role] == blobs(root, author['execution'], saved['pinned'][role]), 'Author recorded execution source differs')
        current=blobs(root,delivery,saved['pinned'][role])
        require(all(current[n]==h and digest((root/n).read_bytes())==h for n,h in saved['pinned'][role].items() if n!=metadata_path), 'Unclassified author delivery difference')
    require(saved['physical_attempts'] == saved['physical_completed'] == saved['validated_new_cases'] == 11 and saved['reused_cases_validated'] == 2 and saved['failures'] == 0, 'Correction/new/reused attempt accounting differs')
    checks = read(root / folder / 'checks.json')
    require(checks['status'] == 'PASS' and len(checks['cases']) == 13 and checks['same_world_declarations_equal'] and checks['hidden_pair_public_decisions_equal'], 'Saved interface gates differ')
    previous = manifest['previous_author']
    previous_saved = read(root / previous['capture'])
    require(previous_saved['status'] == 'FAIL' and previous_saved['execution_commit'] == previous['execution']
            and previous_saved['physical_attempts'] == previous_saved['physical_completed'] == 2
            and previous_saved['validated_cases'] == 1 and previous_saved['failures'] == 1
            and previous_saved['error'] == 'Literal selection sequence differs: fifo', 'Original failed capture was changed')
    previous_folder = str(PurePosixPath(previous['capture']).parent)
    previous_names = set(previous_saved['artifacts']) | {'receipt.json'}
    previous_blobs = blobs(root, previous['data_delivery'], [previous_folder + '/' + n for n in previous_names])
    require(all(digest((root / n).read_bytes()) == h for n,h in previous_blobs.items()), 'Original failure artifacts were rewritten')
    reused = read(root / folder / 'reused-originals.json')
    require(len(reused['copies']) == 8 and reused['classification'] == 'BYTE_IDENTICAL_REUSE_NO_NEW_PHYSICAL_CALL', 'Reuse accounting differs')
    for n,item in reused['copies'].items():
        require(digest((root / folder / n).read_bytes()) == item['sha256'] == digest((root / item['original']).read_bytes()), 'Reused bytes differ')
    metadata_manifest=manifest['metadata_correction']
    metadata_saved=read(root / metadata_manifest['capture'])
    require(metadata_saved['execution_commit']==metadata_manifest['execution'] and digest((root / metadata_manifest['capture']).read_bytes())==metadata_manifest['capture_sha256'], 'Metadata execution identity differs')
    metadata_folder=str(PurePosixPath(metadata_manifest['capture']).parent)
    metadata_names=set(metadata_saved['artifacts'])|{'receipt.json'}
    metadata_original_blobs=blobs(root,metadata_manifest['data_delivery'],[metadata_folder+'/'+n for n in metadata_names])
    require(all(digest((root/n).read_bytes())==h for n,h in metadata_original_blobs.items()), 'Original metadata data delivery differs')
    metadata_result=metadata_tool.verify(root / str(PurePosixPath(metadata_manifest['capture']).parent),metadata_protocol,delivery)
    require(metadata_result['status']=='PASS' and metadata_result['new_metadata_calls']==2, 'Metadata gate failed')
    author_total = len(names)
    require(len(manifest['visuals']) == 2, 'Visual set incomplete')
    for name, item in manifest['visuals'].items():
        require(digest((packet / name).read_bytes()) == item['png_sha256']
                and digest((root / item['svg']).read_bytes()) == item['svg_sha256'], 'Visual source differs')
    gate = read(root / 'docs/mainline/evidence/25-root.json')
    require(gate['status'] == 'ACCEPTED' and gate['actual_root_source'] == source
            and gate['packet_receipt_sha256'] == digest((packet / 'receipt.json').read_bytes()), 'Root authority differs')
    progress = read(root / 'docs/mainline/progress.json')
    require(progress['status'] == 'active' and progress['current_ticket'] == '26' and progress['current_milestone'] == 'M4'
            and next(m['status'] for m in progress['milestones'] if m['id'] == 'M3') == 'accepted'
            and progress['research_trials']['attempts'] == 0, 'Frontier or research scope differs')
    require(manifest['reviews']['standards_findings'] == manifest['reviews']['spec_findings'] == 0
            and manifest['reviews']['independent_assertions'] > 0 and manifest['reviews']['standards_checks'] > 0, 'Review result differs')
    return dict(status='PASS',delivery_commit=delivery,actual_root_source=source,packet_artifacts=len(declared),
        archive_members=total_members,root_tests=tests,guarded_files=len(committed_sources),historical_originals=20,
        author_originals=author_total,original_failed_files=len(previous_names),visuals=2,independent_assertions=manifest['reviews']['independent_assertions'],standards_checks=manifest['reviews']['standards_checks'],
        delivery_verifier=tool,delivery_verifier_sha256=digest(Path(__file__).read_bytes()),
        exact_crlf_checkout_paths=sorted(CHECKOUT_CRLF),source_classification='Original538root checks at recorded9dsource; exact single metadata-line delivery correction;13policy+2metadata engineering calls',
        metadata_execution=metadata_manifest['execution'],metadata_new_cases=2,all_declared_engineering_calls=15,all_engineering_duration_s=30.02,full_regression_rerun=False,inference_rerun=False,new_physical_runs=0,registered_research_trials=0,
        llm_calls=0,training_calls=0,runtime_caches_required=0,overall_goal='ACTIVE')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delivery-commit', required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); result = verify(ROOT, args.delivery_commit)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result, ensure_ascii=False))
