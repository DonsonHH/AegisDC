"""Package historical records without executing or rewriting experiments."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def package(name, revision, output):
    run = ROOT / 'runs' / (name + '-20261102')
    evidence = ROOT / 'evidence' / name
    index = json.loads((evidence / 'local-artifacts.json').read_text(encoding='utf-8'))
    seal = json.loads((run / 'seal.json').read_text(encoding='utf-8'))
    members = {}
    for filename, expected in index.items():
        data = (run / filename).read_bytes()
        if sha(data) != expected['sha256'] or len(data) != expected['bytes']:
            raise ValueError('Historical artifact mismatch: ' + filename)
        members['runs/' + filename] = data
    protocol = subprocess.check_output(['git', 'show', f'{revision}:configs/{name}.json'], cwd=ROOT)
    if sha(protocol) != seal['protocol_sha256']:
        raise ValueError('Protocol seal mismatch')
    if json.loads(protocol) != json.loads((run / 'protocol.json').read_bytes()):
        raise ValueError('Recorded protocol differs from sealed config')
    members['configs/' + name + '.json'] = protocol
    provenance = {}
    for filename, expected in seal['source_sha256'].items():
        blob = subprocess.check_output(['git', 'show', f'{revision}:src/patrol_rsi/{filename}'], cwd=ROOT)
        candidates = [('git_blob', blob), ('git_blob_crlf', blob.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))]
        for snapshot in run.glob('executed-*'):
            if snapshot.name.removeprefix('executed-').replace('-', '_') == filename:
                candidates.insert(0, (snapshot.name, snapshot.read_bytes()))
        matched = next(((label, data) for label, data in candidates if sha(data) == expected), None)
        if matched is None:
            raise ValueError('Cannot recover sealed source: ' + filename)
        label, data = matched
        members['source/patrol_rsi/' + filename] = data
        provenance[filename] = {'sha256': expected, 'recovered_from': label}
    for filename in ['README.md', 'results.csv', 'summary.json', 'local-artifacts.json']:
        members['evidence/' + filename] = (evidence / filename).read_bytes()
    members['SOURCE-PROVENANCE.json'] = (json.dumps({'reference_revision': revision, 'files': provenance}, indent=2)+'\n').encode()
    members['README.txt'] = (
        'Historical experiment evidence, before the event-expiry fix.\n'
        'runs/: all 51 originally indexed files, including 42 compressed trajectories.\n'
        'source/: exact source bytes matching every entry in runs/seal.json.\n'
        'The reference commit is a recovery source; the seal hashes identify executed bytes.\n'
        'No experiments were rerun. Published outcomes remain historical.\n'
        'Verify SHA256SUMS.json against all other ZIP members.\n'
    ).encode()
    manifest = {key: {'bytes': len(data), 'sha256': sha(data)} for key, data in members.items()}
    members['SHA256SUMS.json'] = (json.dumps(manifest, indent=2)+'\n').encode()
    target = output / (name + '-20261102.zip')
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for key, data in members.items():
            archive.writestr(key, data)
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        for key, expected in manifest.items():
            assert sha(archive.read(key)) == expected['sha256']
    return {'file': target.name, 'bytes': target.stat().st_size, 'sha256': sha(target.read_bytes()),
            'indexed_run_files': len(index), 'sealed_source_files': len(provenance)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    result = [package('risk-response', '5efd8f5b', output), package('event-priority', '5e0f5555', output)]
    (output / 'packages.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
