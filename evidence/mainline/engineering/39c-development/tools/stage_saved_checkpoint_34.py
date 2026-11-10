"""Package committed saved-data tools without executing project code locally."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile


def git(*args):
    return subprocess.check_output(['git', *args])


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', required=True)
    args = parser.parse_args()
    root = Path(git('rev-parse', '--show-toplevel').decode().strip()).resolve()
    if Path.cwd().resolve() != root or git('status', '--porcelain').strip():
        raise SystemExit('Stage only from the clean canonical Git root')
    source = git('rev-parse', 'HEAD').decode().strip()
    protocol = json.loads(git('show', source + ':' + args.protocol))
    attempt = protocol['attempt']
    if not attempt or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in attempt):
        raise ValueError('Unsafe attempt name')
    paths = sorted(set(protocol['source_paths'] + [args.protocol, protocol['runner_path']]))
    files, contents = {}, {}
    for name in paths:
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('Unsafe source path')
        data = git('show', source + ':' + name)
        contents[name] = data
        files[name] = dict(bytes=len(data), sha256=sha(data),
                           git_blob=git('rev-parse', source + ':' + name).decode().strip())
    for name, expected in protocol.get('source_sha256', {}).items():
        if files[name]['sha256'] != expected:
            raise ValueError('Frozen source differs: ' + name)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in contents.items():
            entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100600 << 16
            archive.writestr(entry, data)
    archive_bytes = buffer.getvalue()
    manifest = dict(protocol['manifest'], source_commit=source, files=files,
                    attempt=attempt, protocol=args.protocol,
                    snapshot_sha256=sha(archive_bytes), snapshot_bytes=len(archive_bytes))
    remote = Path('/root/private_data/aegisdc-mainline-39c')
    # These are POSIX paths even when staging on Windows.
    if (manifest['output_root'] != '/root/private_data/aegisdc-mainline-39c/' + attempt
            or protocol['staging_root'] != '/root/private_data/aegisdc-mainline-39c/inputs/' + attempt):
        raise ValueError('Remote roots differ from exact protocol attempt')
    local = root / '.work/saved-checkpoint-staging' / attempt / source[:12]
    local.mkdir(parents=True, exist_ok=False)
    (local / 'manifest.json').write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')
    (local / 'source-snapshot.zip').write_bytes(archive_bytes)
    (local / 'runner.py').write_bytes(contents[protocol['runner_path']])
    print(json.dumps(dict(local_stage=str(local), attempt=attempt, source_commit=source,
                          files=len(files), manifest_sha256=sha((local / 'manifest.json').read_bytes()),
                          snapshot_sha256=sha(archive_bytes), runner_sha256=sha((local / 'runner.py').read_bytes()))))


if __name__ == '__main__':
    main()
