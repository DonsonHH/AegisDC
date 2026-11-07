"""Package the original ticket 29 development attempts without replaying them."""

from argparse import ArgumentParser
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from inspection_delivery import digest, hashes, read, require, write

ATTEMPTS = {
    'phase-red-01': 'FAIL',
    'phase-green-01': 'PASS',
    'phase-boundary-01': 'PASS',
    'water-red-01': 'FAIL',
    'water-green-01': 'PASS',
    'water-boundary-red-01': 'FAIL',
    'water-boundary-green-01': 'PASS',
    'domain-red-01': 'FAIL',
    'domain-green-01': 'PASS',
}
ATTEMPT_FILES = ('attempt.json', 'terminal.json', 'stdout.raw', 'stderr.raw')
RECORDERS = ('phase', 'water', 'domain')


def verify_members(members):
    expected = {f'29-{stage}/{name}' for stage in ATTEMPTS for name in ATTEMPT_FILES}
    expected.update(f'29-{stage}-record.py' for stage in RECORDERS)
    require(set(members) == expected, 'Unexpected development archive member')
    attempts = {}
    for stage, status in ATTEMPTS.items():
        name = f'29-{stage}'
        start = json.loads(members[name + '/attempt.json'])
        terminal = json.loads(members[name + '/terminal.json'])
        source = start['source']
        require(start['status'] == 'STARTED' and terminal['status'] == status
                and terminal['source'] == source and terminal['source_guard']
                and (terminal['returncode'] == 0) == (status == 'PASS'),
                f'Attempt lifecycle differs: {name}')
        require(start['pins'] == hashes(source, start['pins']), f'Declared execution blobs differ: {name}')
        for record in (start, terminal):
            require(record['physical_runs'] == record['registered_research_trials'] == 0,
                    f'Development scope differs: {name}')
        for stream in ('stdout', 'stderr'):
            require(digest(members[f'{name}/{stream}.raw']) == terminal[stream + '_sha256'],
                    f'Native log bytes differ: {name}/{stream}')
        attempts[name] = {'source': source, 'status': status, 'declared_source_files': len(start['pins'])}
    return {
        'scope': 'Declared partial development source pins and original logs; no facility or research runs.',
        'attempts': attempts,
        'members': {name: digest(content) for name, content in sorted(members.items())},
    }


def package(work, folder):
    members = {f'29-{stage}/{name}': (work / f'29-{stage}' / name).read_bytes()
               for stage in ATTEMPTS for name in ATTEMPT_FILES}
    for stage in RECORDERS:
        path = work / f'29-{stage}-record.py'
        members[path.name] = path.read_bytes()
    manifest = verify_members(members)
    folder.mkdir()
    archive = folder / 'development-originals.zip'
    with ZipFile(archive, 'x', compression=ZIP_DEFLATED) as output:
        for name, content in sorted(members.items()):
            output.writestr(name, content)
    manifest['archive_sha256'] = digest(archive.read_bytes())
    write(folder / 'manifest.json', manifest)


def verify(folder):
    archive = folder / 'development-originals.zip'
    with ZipFile(archive) as source:
        names = source.namelist()
        require(len(names) == len(set(names)), 'Repeated archive member')
        manifest = verify_members({name: source.read(name) for name in names})
    manifest['archive_sha256'] = digest(archive.read_bytes())
    require(manifest == read(folder / 'manifest.json'), 'Development archive manifest differs')
    return len(manifest['members'])


if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('--package-from', type=Path)
    args = parser.parse_args()
    if args.package_from:
        package(args.package_from, args.folder)
    print(f'Development originals verified: {verify(args.folder)} members')
