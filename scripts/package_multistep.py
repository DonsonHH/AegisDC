"""Small source-only snapshot; historical records and model weights stay in place."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('version')
    args = p.parse_args()
    if not args.version.startswith('v') or not args.version[1:].isdigit():
        raise ValueError('Explicit immutable source version')
    root = Path(__file__).resolve().parents[1]
    stage = root / 'research/2026-11-01-multistep-workflow'
    dest = root / '.work/multistep' / f'code-{args.version}'
    dest.mkdir(exist_ok=False)
    files = [*sorted((root / 'src').rglob('*.py')),
        *sorted((root / 'tests').glob('test_multistep_*.py')),
        *[root / 'scripts' / name for name in ('run_multistep.py', 'prepare_multistep.py', 'package_multistep.py',
            'run_m12d_paired.py', 'audit_m11.py', 'audit_m111.py')],
        *sorted((root / 'cluster').glob('multistep_*.sbatch')),
        stage / 'protocol-v1.json', stage / 'historical-identities.json', stage / '目标对照.md',
        root / 'research/2026-10-28-m111-coverage/frozen_estimator.json']
    hashes = {}
    for path in files:
        name = path.relative_to(root).as_posix()
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        data = path.read_bytes()
        if path.suffix == '.sbatch':
            data = data.replace(b'\r\n', b'\n')
        target.write_bytes(data)
        hashes[name] = sha(target)
    manifest = {'version': args.version, 'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                'files': hashes, 'no_historical_result_repack': True, 'no_model_copy': True}
    (dest / 'snapshot-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf8')
    area = stage / 'source'
    area.mkdir(exist_ok=True)
    archive = area / f'code-{args.version}.tar.gz'
    with archive.open('xb') as stream:
        with tarfile.open(fileobj=stream, mode='w:gz') as t:
            for path in sorted(dest.rglob('*')):
                if path.is_file():
                    t.add(path, arcname=path.relative_to(dest).as_posix(), recursive=False)
    receipt = {'source_manifest_sha256': sha(dest / 'snapshot-manifest.json'),
               'archive_sha256': sha(archive), 'archive_bytes': archive.stat().st_size, 'file_count': len(hashes),
               'version': args.version}
    (area / f'code-{args.version}-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf8')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
