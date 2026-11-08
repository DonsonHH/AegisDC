"""Verify a small fresh Git delivery using identities only, without evaluation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    git = lambda *words: subprocess.check_output(['git', '-C', str(root), *words])
    commit = git('rev-parse', args.commit).decode().strip()
    if git('rev-parse', 'HEAD').decode().strip() != commit:
        raise ValueError('Fresh checkout is not at the declared delivery commit')
    manifest_bytes = (root / args.manifest).read_bytes()
    if manifest_bytes != git('show', commit + ':' + args.manifest):
        raise ValueError('Delivery manifest differs from its committed Git blob')
    manifest = json.loads(manifest_bytes.decode('utf-8'))
    if type(manifest.get('artifacts')) is not dict or not manifest['artifacts']:
        raise ValueError('Declare a nonempty durable delivery set')
    checked = []
    digest = lambda data: hashlib.sha256(data).hexdigest()
    for name, record in manifest['artifacts'].items():
        path = root / name
        if not path.resolve().is_relative_to(root) or path.is_symlink():
            raise ValueError('Delivery member escapes the declared checkout')
        data = path.read_bytes()
        blob = git('show', commit + ':' + name)
        if len(data) != record['bytes'] or digest(data) != record['sha256'] or data != blob:
            raise ValueError('Checkout, committed blob and declared digest differ: ' + name)
        checked.append(name)
    scientific_source = manifest['scientific_source']
    trees = {}
    for directory in ('src/aegis_dc', 'src/patrol_rsi', 'configs'):
        previous = git('rev-parse', scientific_source + ':' + directory).decode().strip()
        current = git('rev-parse', commit + ':' + directory).decode().strip()
        if previous != current:
            raise ValueError('Scientific runtime/config changed during the audit: ' + directory)
        trees[directory] = current

    packet = root / 'evidence/mainline/audits/39a-saved-20261109'
    staged = json.loads((packet / 'staging-manifest.json').read_text(encoding='utf-8'))
    for name, record in staged['files'].items():
        if record['source_path'] is not None:
            data = git('show', staged['source_commit'] + ':' + record['source_path'])
            blob_id = git('rev-parse', staged['source_commit'] + ':' + record['source_path']).decode().strip()
            if blob_id != record['git_blob']:
                raise ValueError('Original input Git identity differs: ' + name)
        else:
            data = (packet / name).read_bytes()
        if len(data) != record['bytes'] or digest(data) != record['sha256']:
            raise ValueError('Frozen execution source/input differs: ' + name)
    terminal = json.loads((packet / 'terminal.json').read_text(encoding='utf-8'))
    if terminal['status'] != 'COMPLETED' or terminal['source_commit'] != staged['source_commit']:
        raise ValueError('Audit terminal/source mismatch')
    for name, record in terminal['durable_outputs'].items():
        data = (packet / name).read_bytes()
        if len(data) != record['bytes'] or digest(data) != record['sha256']:
            raise ValueError('Original execution output differs: ' + name)

    for directory, filename in (
        ('spec-initial', 'original-manifest.json'),
        ('standards-initial', 'preparation-manifest.json'),
        ('spec-final', 'manifest.json'),
        ('standards-final', 'manifest.json'),
    ):
        location = root / 'evidence/mainline/audits/39a-review-20261109' / directory
        original = json.loads((location / filename).read_text(encoding='utf-8'))['artifacts']
        entries = {entry['path']: entry for entry in original} if isinstance(original, list) else original
        for name, record in entries.items():
            data = (location / name).read_bytes()
            if len(data) != record['bytes'] or digest(data) != record['sha256']:
                raise ValueError('Original independent-review member changed: ' + directory + '/' + name)
    result = {
        'classification': 'FRESH_GIT_IDENTITY_VERIFICATION_ONLY',
        'status': 'PASS',
        'delivery_commit': commit,
        'manifest': args.manifest,
        'manifest_sha256': digest((root / args.manifest).read_bytes()),
        'declared_files': len(checked),
        'scientific_source_unchanged_from': scientific_source,
        'scientific_trees': trees,
        'saved_audit_source': staged['source_commit'],
        'saved_audit_slurm_job': '133102',
        'project_calls': 0,
        'metric_recomputations': 0,
        'new_research_trials': 0,
        'original_failures_and_review_bytes_preserved': True,
    }
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
