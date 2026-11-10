"""Package an exact Git snapshot for a declared public-only container qualification."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import zipfile


TOOL = 'evidence/mainline/engineering/39c-development/tools/'
DEFAULT_RUNNER = TOOL + 'run_remote_engineering_slice_22.py'
STAGER = TOOL + 'stage_public_container_qualification.py'


def git(*args):
    return subprocess.check_output(['git', *args])


def sha(data):
    return hashlib.sha256(data).hexdigest()


def blob(revision, name):
    return git('show', f'{revision}:{name}')


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('protocol', help='Repository-relative frozen protocol path')
    parser.add_argument('phase', choices=['red', 'green'])
    args = parser.parse_args()
    require(not sys.flags.optimize, 'Optimized authoring is forbidden')
    root = Path(git('rev-parse', '--show-toplevel').decode().strip()).resolve()
    require(Path.cwd().resolve() == root, 'Run from the repository root')
    require(not git('status', '--porcelain').strip(), 'Freeze from a clean Git tree')
    control = git('rev-parse', 'HEAD').decode().strip()
    protocol_path = PurePosixPath(args.protocol)
    require(not protocol_path.is_absolute() and '..' not in protocol_path.parts
            and protocol_path.parts[:2] == ('docs', 'mainline'), 'Expected a docs/mainline protocol')
    protocol_name = protocol_path.as_posix()
    protocol = json.loads(blob(control, protocol_name))
    spec = protocol['container_snapshot']
    runner = spec.get('runner_path', DEFAULT_RUNNER)
    require(runner in (DEFAULT_RUNNER, TOOL + 'run_remote_engineering_slice_29.py',
                      TOOL + 'run_remote_engineering_slice_33.py'),
            'Use a reviewed, versioned container runner')
    attempt = spec['attempts'][args.phase]
    execution = (control if attempt['runtime_source'] == 'control'
                 else attempt['runtime_source'])
    require(git('rev-parse', f'{execution}^{{commit}}').decode().strip() == execution,
            'Pin a full immutable runtime commit or the current frozen control commit')
    if attempt.get('control_runtime_must_match', False):
        require(not git('diff', '--name-only', execution, control, '--', 'src'),
                'Control commit changed runtime relative to the fixed source')

    test = protocol['test']
    seed = protocol['fixed_seed']
    for fixed in (test, seed):
        data = blob(control, fixed['path'])
        require(sha(data) == fixed['sha256']
                and git('rev-parse', f"{control}:{fixed['path']}").decode().strip() == fixed['git_blob'],
                f"Frozen test/seed identity differs: {fixed['path']}")
    for fixed in spec.get('fixed_support_files', []):
        require(fixed['path'] in spec['support_files']
                and sha(blob(control, fixed['path'])) == fixed['sha256']
                and git('rev-parse', f"{control}:{fixed['path']}").decode().strip() == fixed['git_blob'],
                f"Frozen supporting authoring input differs: {fixed['path']}")
    require(test['test_names'] and all(name.startswith(PurePosixPath(test['path']).stem + '.')
                                     for name in test['test_names']),
            'Selected test must come from the staged test module')
    require(sha(blob(control, runner)) == spec['runner_sha256'], 'Frozen runner differs')
    budget = protocol['budget']
    calls = budget['direct_public_choice_calls']
    require((budget['tests'], budget['facility_entries'], budget['new_research_trials'],
             budget['GPU_use']) == (1, 0, 0, False) and type(calls) is int and 1 <= calls <= 64,
            'Declare one qualification test and a bounded public-call budget; no facility/trial/GPU work')
    require(calls == 1 or runner == TOOL + 'run_remote_engineering_slice_33.py',
            'Use the explicit-budget runner for a multi-condition qualification')
    require(attempt['maximum_invocations'] == 1, 'Each phase permits a single invocation')
    host = protocol['execution_host']
    project = PurePosixPath(host['project_root'])
    output = PurePosixPath(attempt['output_root'])
    staging = PurePosixPath(attempt['staging_root'])
    require(output.parent == project and staging.parent == project / 'inputs'
            and output.name == staging.name and output.name not in ('', '..', '.'),
            'Use distinct project output and input directories for the same attempt')

    runtime = git('ls-tree', '-r', '--name-only', execution, '--',
                  'src/aegis_dc', 'src/patrol_rsi/__init__.py',
                  'src/patrol_rsi/contracts.py').decode().splitlines()
    control_files = [protocol_name, test['path'], seed['path'], runner, STAGER, *spec['support_files']]
    revisions = {name: execution for name in runtime}
    require(not revisions.keys() & set(control_files), 'Control files cannot override runtime files')
    revisions.update({name: control for name in control_files})
    files = {name: blob(revision, name) for name, revision in sorted(revisions.items())}
    manifest = dict(
        schema='aegisdc-remote-container-engineering-manifest-v1',
        classification='REMOTE_CONTAINER_ENGINEERING_NOT_RESEARCH',
        protocol=protocol_name, phase=args.phase, attempt=output.name,
        execution_source=execution, control_source=control,
        expected_host=dict(hostname=host['container_identity'].split('@', 1)[1],
                           python=host['python'], user='root', persistent_mount=host['persistent_mount'],
                           project_root=str(project)),
        attempt_root=str(output), staging_root=str(staging),
        test=test['path'], test_names=test['test_names'], tests=1, direct_public_choice_calls=calls,
        facility_entries=0, max_returned_decisions=0, watchdog_s=120,
        fixed_seed=seed,
        files={name: dict(bytes=len(data), sha256=sha(data),
                          git_blob=git('rev-parse', f'{revisions[name]}:{name}').decode().strip())
               for name, data in files.items()})
    if args.phase == 'red':
        manifest['expected_red_text'] = attempt['expected_red_text']
    destination = root / '.work' / 'public-container-qualification' / output.name / control[:12]
    destination.mkdir(parents=True, exist_ok=False)
    archive = destination / 'source-snapshot.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for name, data in files.items():
            bundle.writestr(name, data)
    manifest.update(snapshot_bytes=archive.stat().st_size, snapshot_sha256=sha(archive.read_bytes()))
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode()
    with (destination / 'manifest.json').open('xb') as stream:
        stream.write(manifest_bytes)
    with (destination / 'runner.py').open('xb') as stream:
        stream.write(files[runner])
    print(json.dumps(dict(local_stage=str(destination), attempt=output.name,
                          control_source=control, execution_source=execution, files=len(files),
                          manifest_sha256=sha(manifest_bytes), snapshot_sha256=manifest['snapshot_sha256'],
                          runner_sha256=sha(files[runner]))))


if __name__ == '__main__':
    main()
