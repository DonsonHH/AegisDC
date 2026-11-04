"""Read back the independent architecture correction and its frozen inputs."""
import argparse
import json
from pathlib import Path
import subprocess

from verify_reserve_delivery import file_sha, git_blob_sha, is_runtime_cache, safe_path


def verify(root, directory, delivery_commit, original_delivery_commit):
    root = root.resolve()
    directory = (directory if directory.is_absolute() else root / directory).resolve()
    relative = directory.relative_to(root).as_posix()
    delivery = subprocess.check_output(['git', 'rev-parse', delivery_commit + '^{commit}'], cwd=root, text=True).strip()
    old_delivery = subprocess.check_output(['git', 'rev-parse', original_delivery_commit + '^{commit}'], cwd=root, text=True).strip()
    receipt_name = 'facility-architecture-v2.json'
    receipt = json.loads((directory / receipt_name).read_text(encoding='utf-8'))
    if file_sha(directory / receipt_name) != git_blob_sha(root, delivery, relative + '/' + receipt_name):
        raise ValueError('Visual correction receipt differs from delivery Git')
    declaration = json.loads((directory / 'declaration.json').read_text(encoding='utf-8'))
    declared = set(declaration['declared_artifacts'])
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob('*')
              if path.is_file() and not is_runtime_cache(path)}
    if declared != set(receipt['artifacts']) or actual != declared | {receipt_name}:
        raise ValueError('Visual correction durable set differs from its initial declaration')
    for name, expected in receipt['artifacts'].items():
        if is_runtime_cache(name) or file_sha(safe_path(directory, name)) != expected \
                or git_blob_sha(root, delivery, relative + '/' + name) != expected:
            raise ValueError('Visual correction artifact mismatch: ' + name)
    plot = receipt['plot_source_commit']
    if plot != declaration['plot_source_commit'] or receipt['pinned_authoring_tools'] != declaration['pinned_authoring_tools']:
        raise ValueError('Declared and observed plot sources differ')
    for name, expected in receipt['pinned_authoring_tools'].items():
        if file_sha(safe_path(root, name)) != expected or git_blob_sha(root, plot, name) != expected \
                or git_blob_sha(root, delivery, name) != expected:
            raise ValueError('Frozen visual author/tool identity mismatch: ' + name)

    def original(name, expected):
        if file_sha(safe_path(root, name)) != expected or git_blob_sha(root, old_delivery, name) != expected \
                or git_blob_sha(root, delivery, name) != expected:
            raise ValueError('Original input was changed while correcting its visual: ' + name)

    original(receipt['source_run'], receipt['source_run_sha256'])
    run_path = safe_path(root, receipt['source_run'])
    manifest = json.loads(run_path.read_text(encoding='utf-8'))
    if manifest['code_identity'] != receipt['original_execution_identity']:
        raise ValueError('The original physical execution identity changed')
    if receipt['source_originals'] != {name: item['sha256'] for name, item in manifest['artifacts'].items()}:
        raise ValueError('Source original set differs from the run manifest')
    for name, expected in receipt['source_originals'].items():
        original((run_path.parent / name).relative_to(root).as_posix(), expected)
    scenario = json.loads((run_path.parent / 'scenario.json').read_text(encoding='utf-8'))
    original((run_path.parent / 'scenario.json').relative_to(root).as_posix(), receipt['source_scenario_sha256'])
    original(receipt['supersedes'], receipt['superseded_receipt_sha256'])
    old_receipt = json.loads(safe_path(root, receipt['supersedes']).read_text(encoding='utf-8'))
    if old_receipt['artifacts'] != receipt['superseded_artifacts']:
        raise ValueError('Superseded original identities were rewritten')
    for name, expected in receipt['superseded_artifacts'].items():
        original((Path(receipt['supersedes']).parent / name).as_posix(), expected)

    selected = receipt['details']['selected_declared_edges']
    for name, edge in selected.items():
        source = next(item for item in scenario['graphs'][edge['graph']] if item['id'] == name)
        if any(edge.get(key) != value for key, value in source.items()):
            raise ValueError('Rendered relation differs from V6: ' + name)
        expected = '<->' if source.get('bidirectional', False) else '-|>'
        if edge['rendered_arrowstyle'] != expected:
            raise ValueError('Rendered arrowheads contradict declared direction: ' + name)
    access = {name: edge for name, edge in selected.items() if edge['graph'] == 'access'}
    if set(access) != {edge['id'] for edge in scenario['graphs']['access']} \
            or not all(edge['bidirectional'] and edge['rendered_arrowstyle'] == '<->' for edge in access.values()):
        raise ValueError('The complete V6 bidirectional access set is not shown')
    if receipt['physics_rerun'] or receipt['full_suite_rerun'] \
            or any(receipt[key] != 0 for key in ('research_trials', 'model_calls', 'training_calls')):
        raise ValueError('Visual correction was mislabeled as a new physical/research run')
    tool = 'scripts/verify_coupled_architecture_v2.py'
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    if git_blob_sha(root, revision, tool) != file_sha(root / tool):
        raise ValueError('The readback verifier is not committed')
    return dict(status='PASS', original_execution_commit=manifest['code_identity']['git_commit'],
        original_delivery_commit=old_delivery, plot_source_commit=plot, visual_delivery_commit=delivery,
        declared_artifacts=len(declared), pinned_authoring_tools=len(receipt['pinned_authoring_tools']),
        rendered_relations=len(selected), bidirectional_access_edges=len(access),
        original_bytes_preserved=True, verification_tool_commit=revision, verification_tool_sha256=file_sha(root / tool),
        initial_pending_receipt_preserved=receipt['delivery_gate'] == 'PENDING_COMMIT_AND_FRESH_CHECKOUT',
        physics_rerun=False, full_suite_rerun=False, runtime_caches_required=0,
        research_trials=0, model_calls=0, training_calls=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--delivery-commit', required=True)
    parser.add_argument('--original-delivery-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    result = verify(arguments.root, arguments.directory, arguments.delivery_commit, arguments.original_delivery_commit)
    with arguments.output.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result))
