"""Freeze six development conditions using registration metadata, never scores."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / 'research/2026-11-01-multistep-workflow'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    import sys
    sys.path.insert(0, str(ROOT / 'src'))
    from patrol_rsi.multistep_workflow import Workflow
    registry = ROOT / '.work/multistep/historical-identities.json'
    historical = json.loads(registry.read_bytes())
    occupied = set(historical['seed_groups'])
    sources = []

    def extract(value, seed_field=False):
        if type(value) is int and seed_field:
            occupied.add(value)
        elif isinstance(value, list):
            for child in value:
                extract(child, seed_field)
        elif isinstance(value, dict):
            for key, child in value.items():
                extract(child, seed_field or 'seed' in key.lower())

    # Top-level protocols/manifests only: no old raw final sets or labels.
    for path in sorted((ROOT / 'research').glob('*/*.json')):
        if STAGE in path.parents:
            continue
        extract(json.loads(path.read_bytes()))
        sources.append({'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path)})
    seeds = (41000, 41001)
    if set(seeds) & occupied:
        raise ValueError('Requested new seeds overlap global registration metadata')
    cases = []
    fixtures = [('healthy', 900), ('coldplate_fouling', 180), ('aux_feeder_loss+cdu_fouling', 180)]
    for seed in seeds:
        for scenario, duration in fixtures:
            cases.append({'case_id': f'dev-{len(cases):02d}', 'specification': {
                'phase': 'development', 'seed': seed, 'scenario': scenario, 'duration_s': duration,
                'fault_start_s': 335, 'noise_c': .2, 'estimator': 'history',
                'control': 'feedback', 'resources': 'provisioned', 'variant': 'open'}})
    protocol = {'study': 'minimal-multistep-workflow-v1',
        'baseline_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
        'cases': cases, 'seed_selection': 'Two fixed unused seeds; no score inspection; original phase335 and original durations',
        'registry': {'historical_sha256': sha(registry), 'checked_metadata': sources,
            'excluded_seed_groups': sorted(occupied), 'new_seeds': list(seeds),
            'old_final_raw_opened': False, 'numeric_fingerprint_check': 'At first generation against historical registry and this cohort'},
        'limits': {'development_conditions': 6, 'environment_attempts': 60, 'real_model_calls': 4,
            'CPU_core_minutes': 120, 'GPU_allocation_seconds': 900, 'new_storage_bytes': 500000000,
            'parallel_allocations': 1, 'training_runs': 0},
        'first_cost_probe': {'case_id': 'dev-00', 'arm': 'D', 'counts_as_environment_attempt': True, 'reuse_result': True},
        'arms': {'A': 'Original Tour, no optional checks', 'B': 'Original E1 gate and ordering, K=1',
            'C': 'K=2, public first check; task preferences frozen before first result, live safety checks',
            'D': 'K=2, identical first check; replan after real reference using shared public state'},
        'parent_workflow': Workflow().to_dict(),
        'comparison': 'D vs C for same-budget feedback; do not attribute D vs B budget/first-logic changes to AI',
        'model_loop': {'parent': 'D', 'stop_after': 'first legal nonduplicate model child, evaluated on all six cases',
            'failed_calls_count': True, 'positive_human_result_required': False,
            'prompt': 'Only anonymous public completed trajectories and labeled development simulation scores',
            'forbidden': ['seed', 'scenario identity', 'hidden fault schedule', 'oracle actions', 'validation/test labels'],
            'editable': 'One or two Workflow enum fields; no safety/budget/data/physics edits'},
        'deliverables': ['目标对照.md', 'Runnable prototype and reproduction command',
            'All-condition table and real timeline', 'One-page four-question decision and one next hypothesis']}
    STAGE.mkdir(parents=True, exist_ok=True)
    for path, value in [(STAGE / 'protocol-v1.json', protocol),
                        (STAGE / 'historical-identities.json', historical)]:
        with path.open('x', encoding='utf8', newline='\n') as f:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write('\n')
    print(json.dumps({'cases': len(cases), 'seeds': list(seeds), 'metadata_files': len(sources),
                      'protocol_sha256': sha(STAGE / 'protocol-v1.json')}))


if __name__ == '__main__':
    main()
