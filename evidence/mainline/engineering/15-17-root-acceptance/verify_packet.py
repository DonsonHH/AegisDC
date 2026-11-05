"""Fixed M3 tickets 15–17 root-delivery check; stdlib only, no evidence/model execution."""
import argparse
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[4]
SOURCE = '777ee58541a4cb2be2ff200de2ac135c6f13affe'
PACKET = Path('evidence/mainline/engineering/15-17-root-acceptance')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def blobs(root, revision, names):
    names = sorted(set(names))
    data = subprocess.check_output(['git', 'cat-file', '--batch'], cwd=root,
        input=''.join(revision + ':' + n + '\n' for n in names).encode())
    result, offset = {}, 0
    for name in names:
        end = data.index(b'\n', offset); header = data[offset:end].split()
        require(len(header) == 3 and header[1] == b'blob', 'Missing Git blob: ' + name)
        size = int(header[2]); start = end + 1
        result[name] = sha256(data[start:start + size]).hexdigest(); offset = start + size + 1
    require(offset == len(data), 'Unexpected Git batch bytes')
    return result


def verify(root, delivery=None):
    root = root.resolve(); packet = root / PACKET
    declaration = read(packet / 'declaration.json'); receipt = read(packet / 'receipt.json')
    require(receipt['tested_source'] == SOURCE and receipt['delivery_gate'] == 'PENDING_COMMIT_AND_FRESH_CHECKOUT', 'Initial receipt changed')
    actual = {p.relative_to(packet).as_posix() for p in packet.rglob('*') if p.is_file()}
    require(actual == set(declaration['declared_artifacts']) | {'receipt.json'}, 'Packet durable set')
    require(set(receipt['artifacts']) == set(declaration['declared_artifacts']), 'Declared hash set')
    require(not any('__pycache__' in PurePosixPath(n).parts or PurePosixPath(n).suffix in {'.pyc', '.pyo'} for n in actual), 'Cache in delivery')
    for name, expected in receipt['artifacts'].items():
        require(digest(packet / name) == expected, 'Packet hash: ' + name)
    if delivery:
        names = [(PACKET / n).as_posix() for n in actual]
        require(all(digest(root / n) == h for n, h in blobs(root, delivery, names).items()), 'Packet Git bytes')
    preserved = read(packet / 'archive-members.json'); zip_members = 0
    for name, archive in preserved.items():
        with zipfile.ZipFile(packet / name) as z:
            require(len(z.namelist()) == len(set(z.namelist())) and set(z.namelist()) == set(archive), 'ZIP member roles')
            for member, expected in archive.items():
                p = PurePosixPath(member)
                require(not p.is_absolute() and '..' not in p.parts and '.git' not in p.parts and '__pycache__' not in p.parts and p.suffix not in {'.pyc', '.pyo'}, 'Unsafe/cache ZIP member')
                h, size = sha256(), 0
                with z.open(member) as stream:
                    for block in iter(lambda: stream.read(65536), b''):
                        h.update(block); size += len(block)
                require(h.hexdigest() == expected['sha256'] and size == expected['bytes'], 'ZIP raw original: ' + member)
                zip_members += 1
    summary = read(packet / 'raw/summary.json'); guard = read(packet / 'raw/source-guard.json')
    require(summary['overall'] == 'PASS' and summary['tests']['run'] == summary['tests']['executed'] == 420, 'Actual root result')
    require(summary['tests']['failures'] == summary['tests']['errors'] == summary['tests']['skipped'] == 0 and summary['verified_original_files'] == 20, 'Root failure/old evidence count')
    require(guard['source_commit_before'] == guard['source_commit_after'] == SOURCE and guard['sources_unchanged'] and guard['head_unchanged'], 'Root execution guard')
    require(len(guard['actual_python_sources']) == 190, 'Python source count')
    for name, expected in guard['actual_python_sources'].items():
        require(digest(root / name) == expected, 'Tested Python changed: ' + name)
    subprocess.run(['git', 'diff', '--quiet', SOURCE, '--', 'src', 'scripts', 'tests', 'configs', '.gitattributes'], cwd=root, check=True)
    manifest = read(packet / 'source-manifest.json')
    require(manifest['tested_source'] == SOURCE and set(manifest['components']) == {'15', '16', '17'}, 'Component manifest')
    receipt_sha = digest(packet / 'receipt.json')
    for ticket, component in manifest['components'].items():
        capture, module = component['capture'], component['module']
        require(digest(root / capture) == component['capture_sha256'], 'Original capture receipt changed')
        require(blobs(root, component['execution'], [module])[module] == digest(root / module), 'Component execution source')
        subtree = str(PurePosixPath(capture).parents[1])
        subprocess.run(['git', 'diff', '--quiet', component['final'], '--', subtree], cwd=root, check=True)
        gate = read(root / f'docs/mainline/evidence/{ticket}-root.json')
        require(gate['status'] == 'ACCEPTED' and gate['actual_root_source'] == SOURCE and gate['packet_receipt_sha256'] == receipt_sha, 'Root authority')
    sensor = read(root / manifest['components']['16']['capture'])
    require(sensor['engineering_capture'] == 'FAIL' and sensor['full_tests']['run'] == 390, 'Original sensor FAIL must remain recorded')
    require(len(manifest['visuals']) == 7, 'Visual count')
    for image, source in manifest['visuals'].items():
        require(digest(packet / image) == source['png_sha256'] and digest(root / source['svg']) == source['svg_sha256'], 'Visual derivation bytes')
    for report, expected in manifest['report_sha256'].items():
        require(preserved['reviews.zip'][report]['sha256'] == expected, 'Reviewed report identity')
    progress = read(root / 'docs/mainline/progress.json')
    require(progress['status'] == 'active' and progress['current_ticket'] == '18' and progress['current_milestone'] == 'M3', 'Current frontier')
    require(next(x['status'] for x in progress['milestones'] if x['id'] == 'M3') == 'in_progress' and not progress['active_implementations'], 'Stage/ownership')
    require(progress['research_trials']['attempts'] == 0, 'Research lifecycle changed')
    links = 0
    for document in (packet / 'README.md', root / 'README.md', root / 'docs/MAINLINE.md', root / 'docs/NEXT.md'):
        for target in re.findall(r'\]\(([^)]+)\)', document.read_text(encoding='utf-8')):
            if '://' not in target and not target.startswith('#'):
                require((document.parent / target.split('#', 1)[0]).exists(), 'Local link: ' + target)
                links += 1
    return {'status': 'PASS' if delivery else 'LOCAL_VERIFIED_DELIVERY_NOT_YET_CHECKED', 'actual_root_source': SOURCE,
        'delivery_commit': delivery, 'packet_artifacts': len(receipt['artifacts']), 'terminal_receipt_git_checked': bool(delivery),
        'inert_zip_archives': len(preserved), 'zip_members': zip_members, 'zip_extracted': False,
        'root_tests': summary['tests'], 'old_originals': 20, 'tested_python_unchanged': 190,
        'latest_readable_png': 7, 'visual_method': 'sharp0.35.5 local raster inspection; not browser', 'local_links': links,
        'runtime_caches_required': 0, 'new_model_runs': 0, 'new_full_suite_runs': 0,
        'next_ready_unassigned': ['18'], 'overall_goal': 'ACTIVE'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=ROOT); p.add_argument('--delivery-commit'); p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); result = verify(args.root, args.delivery_commit)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result, ensure_ascii=False))
