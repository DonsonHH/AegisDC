"""Verify declared numerical delivery against original ZIP members and Git blobs.

Does not simulate, run a flash, render, or rerun the full acceptance suite.
"""
import argparse
import json
from pathlib import Path
import subprocess

from numerical_engineering_checks import assess, inspect_run, member_identities, read_archive
from verify_reserve_delivery import file_sha, git_blob_sha, is_runtime_cache, safe_path


def verify(root, directory, delivery_commit):
    root = root.resolve()
    directory = (directory if directory.is_absolute() else root / directory).resolve()
    relative = directory.relative_to(root).as_posix()
    delivery = subprocess.check_output(['git', 'rev-parse', delivery_commit + '^{commit}'], cwd=root, text=True).strip()
    receipt = json.loads((directory / 'receipt.json').read_text(encoding='utf-8'))
    if receipt['delivery_gate'] != 'PENDING_COMMIT_AND_FRESH_CHECKOUT' or receipt['engineering_capture'] != 'PASS':
        raise ValueError('Initial pending execution receipt was rewritten')
    if git_blob_sha(root, delivery, relative + '/receipt.json') != file_sha(directory / 'receipt.json'):
        raise ValueError('Delivery receipt differs from Git')
    declaration = json.loads((directory / 'declaration.json').read_text(encoding='utf-8'))
    declared = set(declaration['declared_artifacts'])
    if declared != set(receipt['artifacts']):
        raise ValueError('Declaration differs from durable hashes')
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file() and not is_runtime_cache(p)}
    if actual != declared | {'receipt.json'}:
        raise ValueError('Unexpected/missing durable files')
    for name, identity in receipt['artifacts'].items():
        if is_runtime_cache(name) or file_sha(safe_path(directory, name)) != identity or git_blob_sha(root, delivery, relative + '/' + name) != identity:
            raise ValueError('Durable artifact differs from manifest/delivery Git: ' + name)
    execution = receipt['execution_commit']
    for group, declared_group in [('pinned_tools', 'declared_tools'), ('execution_inputs', 'declared_execution_inputs'), ('prior_durable_files', 'declared_prior_files')]:
        if set(receipt[group]) != set(declaration[declared_group]):
            raise ValueError('Pinned provenance set differs from declaration')
    for group in ('runtime_sources', 'pinned_tools', 'execution_inputs', 'prior_durable_files'):
        for name, identity in receipt[group].items():
            if is_runtime_cache(name) or git_blob_sha(root, execution, name) != identity or git_blob_sha(root, delivery, name) != identity or file_sha(safe_path(root, name)) != identity:
                raise ValueError('Execution/delivery/current source identity mismatch: ' + name)
    book = json.loads((directory / 'runbook-copy.json').read_text(encoding='utf-8'))
    if book != json.loads((root / 'docs/mainline/12-numerical-runbook.json').read_text(encoding='utf-8')):
        raise ValueError('Frozen runbook copy differs')
    original_index = json.loads((directory / 'runs-index.json').read_text(encoding='utf-8'))
    base = json.loads((root / book['profile']).read_text(encoding='utf-8'))
    analyses, count, points, verified_runtime_commits = {}, 0, 0, set()
    for item in book['cases']:
        analyses[item['id']] = {}
        by_step = original_index[item['id']]
        if set(by_step) != {str(h) for h in book['maximum_steps_s']}:
            raise ValueError('Missing declared step levels')
        for h, record in by_step.items():
            path = safe_path(directory, record['archive'])
            if file_sha(path) != record['archive_sha256']:
                raise ValueError('Archive identity differs')
            if member_identities(path) != record['original_members']:
                raise ValueError('Original member SHA/byte/count identity differs')
            manifest, scenario, trace, balances = read_archive(path)
            if manifest['code_identity']['git_commit'] != record['source_commit'] or manifest['code_identity']['files'] != receipt['runtime_sources'] or manifest['code_identity']['implementation_has_changes']:
                raise ValueError('Runtime differs from its recorded clean execution source')
            if record['source_commit'] not in verified_runtime_commits:
                for name, identity in receipt['runtime_sources'].items():
                    if git_blob_sha(root, record['source_commit'], name) != identity:
                        raise ValueError('Historical actual runtime differs from its execution Git revision')
                verified_runtime_commits.add(record['source_commit'])
            if scenario['entities'] != base['entities'] or scenario['graphs'] != base['graphs']:
                raise ValueError('One complete V6 identity/topology changed')
            if manifest['inputs']['maximum_step_s'] != float(h) or manifest['scenario_sha256'] != record['scenario_sha256']:
                raise ValueError('Step/config identity changed')
            actual_analysis = inspect_run(item, manifest, scenario, trace, balances)
            if actual_analysis != record['analysis']:
                raise ValueError('Saved independent numerical analysis does not reproduce')
            analyses[item['id']][h] = actual_analysis
            count += 1
            points += len(trace)
    if verified_runtime_commits != set(receipt['runtime_execution_commits']):
        raise ValueError('Declared runtime execution revisions differ from actual original manifests')
    assessment = assess(book, analyses)
    if assessment != json.loads((directory / 'assessment.json').read_text(encoding='utf-8')):
        raise ValueError('Numerical assessment does not reproduce')
    rejections = json.loads((directory / 'expected-rejections.json').read_text(encoding='utf-8'))
    if len(rejections) != len(book['rejections']):
        raise ValueError('Declared refusal count mismatch')
    for expected, actual in zip(book['rejections'], rejections):
        if actual['request'] != expected or actual['successful_trajectory_returned'] or expected['error_contains'] not in actual['error']:
            raise ValueError('Refusal identity/category mismatch')
    phase = json.loads((directory / 'phase-domain.json').read_text(encoding='utf-8'))
    if phase['unchanged_frozen_cases'] != 432 or phase['frozen_refusals'] != 5 or len(phase['neighborhoods']) != 255:
        raise ValueError('Representation/domain probe count mismatch')
    figure = json.loads((directory / 'figures/numerical-qualification.json').read_text(encoding='utf-8'))
    for name, identity in figure['inputs'].items():
        if file_sha(safe_path(directory, name)) != identity:
            raise ValueError('Figure input identity mismatch')
    for name, identity in figure['outputs'].items():
        if file_sha(safe_path(directory / 'figures', name)) != identity:
            raise ValueError('Figure output identity mismatch')
    full = json.loads((directory / 'full-check/summary.json').read_text(encoding='utf-8'))
    if full['overall'] != 'PASS' or full['tests'] != receipt['full_tests'] or receipt['full_regression_runs'] != 1:
        raise ValueError('Exactly one full regression did not pass')
    return dict(status='PASS', execution_commit=execution, delivery_commit=delivery,
                declared_durable_artifacts=len(declared), original_archives=count, original_members=4 * count,
                state_points=points, cases=len(analyses), numerical_gate=assessment['all_declared_fixtures_qualified'],
                runtime_execution_commits=receipt['runtime_execution_commits'],
                reused_engineering_originals=receipt['reused_engineering_originals'],
                frozen_representation_cases=432, strict_refusals=5, representation_neighbors=255,
                full_facility_expected_refusals=len(rejections),
                full_tests=full['tests'], verified_original_files=full['verified_original_files'],
                runtime_caches_required=0, initial_pending_receipt_preserved=True,
                physics_rerun=False, full_suite_rerun=False, research_trials=0, model_calls=0, training_calls=0)


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
    print(json.dumps(result, ensure_ascii=False))
