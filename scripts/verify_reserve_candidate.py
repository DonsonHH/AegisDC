"""Post-execution readback of both the reserve package and completed full checks."""
import argparse
import json
from pathlib import Path

from verify_reserve_delivery import verify, file_sha, git_blob_sha, is_runtime_cache, safe_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--full-index', type=Path, required=True)
    parser.add_argument('--delivery-commit', required=True)
    parser.add_argument('--output', type=Path)
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    index_path = arguments.full_index if arguments.full_index.is_absolute() else root / arguments.full_index
    index = json.loads(index_path.read_text(encoding='utf-8'))
    delivered = arguments.delivery_commit
    if git_blob_sha(root, delivered, index_path.relative_to(root).as_posix()) != file_sha(index_path):
        raise ValueError('Full-check index differs from committed delivery')
    package = verify(root, arguments.directory, delivery_commit=delivered)
    if package['execution_commit'] != index['execution_commit'] or index['full_regression_runs'] != 1:
        raise ValueError('Full-check/capture execution identities differ')
    for name, expected in index['artifacts'].items():
        if is_runtime_cache(name) or file_sha(safe_path(root, name)) != expected \
                or git_blob_sha(root, delivered, name) != expected:
            raise ValueError('Completed full-check artifact differs: ' + name)
    for name, expected in index['execution_tools_and_tests'].items():
        if git_blob_sha(root, index['execution_commit'], name) != expected \
                or git_blob_sha(root, delivered, name) != expected:
            raise ValueError('Full-check execution source differs: ' + name)
    for name, expected in index['post_execution_tools'].items():
        if file_sha(safe_path(root, name)) != expected or git_blob_sha(root, delivered, name) != expected:
            raise ValueError('Post-execution verifier differs from delivery')
    summary = json.loads(safe_path(root, index['summary_path']).read_text(encoding='utf-8'))
    if summary['overall'] != 'PASS' or summary['tests'] != index['tests']:
        raise ValueError('Full-check result or source-linked counts differ')
    result = dict(package, full_tests=summary['tests'], verified_original_files=summary['verified_original_files'],
                  completed_full_check_artifacts=len(index['artifacts']), full_regression_repeated=False)
    if arguments.output:
        with arguments.output.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
