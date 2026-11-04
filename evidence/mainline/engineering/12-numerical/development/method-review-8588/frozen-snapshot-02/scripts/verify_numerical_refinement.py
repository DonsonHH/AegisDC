"""Fresh-checkout v2 delivery verification, without a physics/full-suite rerun."""
import argparse
import json
from pathlib import Path
import subprocess
import zipfile

from numerical_refinement_checks import (check_numeric_range_extension, compact,
    assess_refinement as assess, inspect_refinement_run as inspect_run)
from numerical_engineering_checks import member_identities, read_archive
from verify_reserve_delivery import file_sha, git_blob_sha, is_runtime_cache, safe_path


def verify(root, directory, delivery_commit):
    root = root.resolve()
    directory = (directory if directory.is_absolute() else root / directory).resolve()
    relative = directory.relative_to(root).as_posix()
    delivery = subprocess.check_output(['git', 'rev-parse', delivery_commit + '^{commit}'], cwd=root, text=True).strip()
    receipt = json.loads((directory / 'receipt.json').read_text(encoding='utf-8'))
    if receipt['delivery_gate'] != 'PENDING_COMMIT_AND_FRESH_CHECKOUT' or receipt['full_regression_runs'] != 0:
        raise ValueError('Initial receipt/reused-full policy changed')
    if file_sha(directory / 'receipt.json') != git_blob_sha(root, delivery, relative + '/receipt.json'):
        raise ValueError('Receipt differs from delivery Git')
    declaration = json.loads((directory / 'declaration.json').read_text(encoding='utf-8'))
    declared = set(declaration['declared_artifacts'])
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file() and not is_runtime_cache(p)}
    if set(receipt['artifacts']) != declared or actual != declared | {'receipt.json'}:
        raise ValueError('V2 durable declaration differs')
    for name, identity in receipt['artifacts'].items():
        if file_sha(safe_path(directory, name)) != identity or git_blob_sha(root, delivery, relative + '/' + name) != identity:
            raise ValueError('V2 durable artifact mismatch: ' + name)
    execution = receipt['execution_commit']
    for group, declared_group in [('pinned_tools', 'declared_tools'), ('execution_inputs', 'declared_execution_inputs'), ('inherited_originals', 'declared_inherited_originals')]:
        if set(receipt[group]) != set(declaration[declared_group]):
            raise ValueError('V2 provenance declaration mismatch')
    for group in ('runtime_sources', 'pinned_tools', 'execution_inputs', 'inherited_originals'):
        for name, identity in receipt[group].items():
            if is_runtime_cache(name) or file_sha(safe_path(root, name)) != identity or git_blob_sha(root, execution, name) != identity or git_blob_sha(root, delivery, name) != identity:
                raise ValueError('V2 execution/delivery provenance mismatch: ' + name)
    book = json.loads((directory / 'protocol-copy.json').read_text(encoding='utf-8'))
    if book != json.loads((root / 'docs/mainline/12-numerical-refinement-v2.json').read_text(encoding='utf-8')):
        raise ValueError('V2 protocol copy differs')
    prior = safe_path(root, book['v1_directory'])
    old_receipt = json.loads((prior / 'receipt.json').read_text(encoding='utf-8'))
    if file_sha(prior / 'receipt.json') != book['v1_receipt_sha256'] or old_receipt['runtime_sources'] != receipt['runtime_sources'] or old_receipt['numerical_gate']:
        raise ValueError('Original negative runtime/receipt identity changed')
    if old_receipt['full_tests'] != receipt['inherited_full_tests'] or old_receipt['full_regression_runs'] != 1:
        raise ValueError('Inherited full-suite evidence differs')
    index = json.loads((directory / 'runs-index.json').read_text(encoding='utf-8'))
    old_index = json.loads((prior / 'runs-index.json').read_text(encoding='utf-8'))
    analyses, new_count, inherited_count, new_points = {}, 0, 0, 0
    for item in book['cases']:
        name = item['id']
        analyses[name] = {}
        if set(index[name]) != {str(h) for h in book['maximum_steps_s']}:
            raise ValueError('Declared v2 levels missing')
        for h, record in index[name].items():
            if record['archive_root'] not in ('inherited_v1', 'refinement'):
                raise ValueError('Unknown original-archive root')
            source_root = prior if record['archive_root'] == 'inherited_v1' else directory
            path = safe_path(source_root, record['archive'])
            if file_sha(path) != record['archive_sha256'] or member_identities(path) != record['original_members']:
                raise ValueError('Original archive/member identity mismatch')
            manifest, scenario, trace, balances = read_archive(path)
            expected_commit = old_index[name][h]['source_commit'] if record['archive_root'] == 'inherited_v1' else execution
            if record['source_commit'] != expected_commit:
                raise ValueError('Index source identity differs from actual execution')
            if manifest['code_identity']['git_commit'] != expected_commit or manifest['code_identity']['files'] != receipt['runtime_sources'] or manifest['code_identity']['implementation_has_changes']:
                raise ValueError('Actual runtime identity changed')
            if manifest['inputs']['maximum_step_s'] != float(h):
                raise ValueError('Step identity mismatch')
            analysis = inspect_run(item, manifest, scenario, trace, balances)
            if compact(analysis) != record['analysis']:
                raise ValueError('Saved v2 analysis does not reproduce')
            analyses[name][h] = analysis
            if record['archive_root'] == 'inherited_v1':
                inherited_count += 1
            else:
                new_count += 1
                new_points += len(trace)
                numeric = next(row for row in scenario['parameters'] if row['id'] == 'step_time')
                if numeric['valid_range'][0] != .0025:
                    raise ValueError('New numeric range was not declared')
                with zipfile.ZipFile(safe_path(prior, old_index[name]['0.01']['archive'])) as original_archive:
                    check_numeric_range_extension(json.loads(original_archive.read('scenario.json')), scenario)
    assessment = assess(book, analyses)
    if assessment != json.loads((directory / 'assessment.json').read_text(encoding='utf-8')):
        raise ValueError('V2 assessment does not reproduce')
    figure = json.loads((directory / 'figures/refinement.json').read_text(encoding='utf-8'))
    for name, identity in figure['inputs'].items():
        if file_sha(directory / name) != identity:
            raise ValueError('V2 figure input differs')
    for name, identity in figure['outputs'].items():
        if file_sha(directory / 'figures' / name) != identity:
            raise ValueError('V2 figure output differs')
    return dict(status='PASS', execution_commit=execution, delivery_commit=delivery, new_original_archives=new_count,
        reused_original_archives=inherited_count, new_state_points=new_points, numerical_gate=assessment['all_declared_fixtures_qualified'],
        cases=len(analyses), declared_artifacts=len(declared), initial_pending_receipt_preserved=True,
        runtime_caches_required=0, full_suite_rerun=False, physics_rerun=False, research_trials=0, model_calls=0, training_calls=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--delivery-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.root, args.directory, args.delivery_commit)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result))
