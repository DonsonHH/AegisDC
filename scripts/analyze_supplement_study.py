"""Recompute and summarize the completed independent supplemental study.

Confidence intervals resample twelve physical-seed blocks after averaging
model seeds within condition and assigning equal weight to four fault families.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from patrol_rsi.supplement_metrics import episode_summary

RUN = ROOT / 'runs/supplement-benchmark-20261103'
EVIDENCE = ROOT / 'evidence/supplement-study'
PAPER = ROOT / 'paper/source-data/supplement-study.json'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


def average(values):
    values = [float(x) for x in values if x is not None]
    return float(np.mean(values)) if values else None


def scalar_metrics(summary):
    result = {k: summary[k] for k in ['anomaly_segments', 'confirmed_segments', 'confirmation_ratio',
              'consequence_weighted_censored_delay_s', 'weighted_normalized_age', 'travel_m', 'service_s',
              'completed_inspections', 'extra_event_visits', 'false_measured_confirmations', 'choice_opportunities',
              'invalid_assignments_audited', 'duplicate_reservations_audited', 'revisit_violations_audited',
              'budget_violations_audited', 'extra_dispatches_audited']}
    for subset in ('all', 'not_fresh'):
        for metric in ('rmse_c', 'weighted_rmse_c', 'r2'):
            result[f'{subset}_{metric}'] = summary['temperature'][subset][metric]
    for stage in ('estimator_total_ms', 'neural_predict_ms', 'policy_total_ms', 'online_control_cycle_ms'):
        for kind in ('mean', 'p50', 'p95'):
            result[f'{stage}_{kind}'] = summary['latency'][stage][kind]
    return result


def check_equal(first, second, where):
    if isinstance(first, dict):
        if first.keys() != second.keys():
            raise AssertionError('Summary keys differ: '+where)
        for key in first:
            check_equal(first[key], second[key], where+'.'+key)
    elif isinstance(first, (float, int)) and not isinstance(first, bool):
        if not np.isclose(first, second, rtol=1e-10, atol=1e-10):
            raise AssertionError(f'Summary recomputation differs: {where}: {first} vs {second}')
    elif first != second:
        raise AssertionError('Summary recomputation differs: '+where)


def audit_actual_record(record):
    """Independent raw-ledger checks, separate from simulator safety counters."""
    events, dispatches, assignments = record['inspection_events'], record['dispatches'], record['assignments']
    completions = Counter((e['agent'], e['task'], e['time_s']) for e in events)
    expected = Counter((d['agent'], d['task'], d['certificate']['candidate_finish_s']) for d in dispatches)
    assert completions == expected
    assert Counter((a['time_s'], a['agent'], a['task']) for a in assignments) == Counter((d['time_s'], d['agent'], d['task']) for d in dispatches)
    active = []
    for dispatch in dispatches:
        cert = dispatch['certificate']
        assert cert['ok'] and cert['candidate_finish_s'] <= min(1800, cert['candidate_due_s'])+1e-9
        assert all(a <= b+1e-9 for a, b in zip(cert['fallback_completion_s'], cert['fallback_due_s']))
        active = [d for d in active if d['certificate']['candidate_finish_s'] > dispatch['time_s']+1e-9]
        assert all(d['task'] != dispatch['task'] and d['agent'] != dispatch['agent'] for d in active)
        active.append(dispatch)
    assert sum(d['extra_event_visit'] for d in dispatches) <= 12
    for event in events:
        assert event['calibrated'] and event['role'] == record['role_order'][event['task']]
    actual = defaultdict(list)
    for event in events:
        actual[event['task']].append(event['time_s'])
    for gap in record['exact_task_gaps']:
        times = sorted(actual[gap['task']])
        assert times == gap['completion_times_s']
        maximum = max(np.diff([0, *times, 1800]))
        assert abs(maximum-gap['maximum_gap_including_initial_and_terminal_s']) < 1e-9
        assert maximum <= record['deadlines_s'][gap['task']]+1e-9
    return {'events': len(events), 'dispatches': len(dispatches), 'tasks': len(record['role_order']), 'all_passed': True}


def bootstrap(values, protocol):
    defined = [float(v) for v in values if v is not None]
    if not defined:
        return {'mean': None, 'percentile95': None, 'blocks': 0}
    rng = np.random.default_rng(protocol['statistics']['bootstrap_seed'])
    a = np.asarray(defined)
    indices = rng.integers(0, len(a), (protocol['statistics']['bootstrap_replicates'], len(a)))
    return {'mean': float(a.mean()), 'percentile95': np.percentile(a[indices].mean(1), [2.5, 97.5]).tolist(), 'blocks': len(a)}


def build():
    protocol = read(RUN / 'protocol.json')
    ledger = [json.loads(line) for line in (RUN / 'attempts.jsonl').read_text(encoding='utf-8').splitlines() if line]
    completed = {(r['phase'], r['id']) for r in ledger if r['status'] == 'completed'}
    expected = {'compatibility': 2, 'pilot': 6, 'collect_train': 288, 'collect_development': 72,
                'estimator_train': 3, 'ppo_train': 720, 'ppo_development': 36, 'test': 1080, 'scale': 18}
    counts = Counter(r['phase'] for r in ledger if r['status'] == 'completed')
    assert counts == Counter(expected), (counts, expected)
    assert all((r['phase'], r['id']) in completed for r in ledger if r['status'] == 'started'), 'Unresolved attempts remain'
    assert len(protocol['case_sets']['test']) == 72
    rows, audits = [], []
    process_by_case = defaultdict(set)
    for case in protocol['case_sets']['test']:
        for folder in sorted((RUN / 'test').glob(case['id']+'-*')):
            if not folder.is_dir():
                continue
            with gzip.open(folder / 'record.json.gz', 'rt', encoding='utf-8') as stream:
                record = json.load(stream)
            with np.load(folder / 'arrays.npz') as arrays:
                recomputed = episode_summary(record, arrays)
            stored = read(folder / 'summary.json')
            check_equal(recomputed, stored, folder.name)
            audit = audit_actual_record(record)
            metadata = record['supplement_metadata']
            process_by_case[case['id']].add(record['process_sha256'])
            rows.append({'id': folder.name, 'case_id': case['id'], 'block': case['block'], 'family': case['family'],
                         'physical_seed': case['spec']['seed'], 'method': metadata['method_label'],
                         'model_seed': metadata['model_seed'], 'process_sha256': record['process_sha256'],
                         'record_sha256': sha(folder / 'record.json.gz'), 'arrays_sha256': sha(folder / 'arrays.npz'),
                         'summary_sha256': sha(folder / 'summary.json'), 'metrics': scalar_metrics(stored),
                         'by_role': record['by_role'], 'event_status_counts': stored['event_status_counts']})
            audits.append(audit)
    assert len(rows) == 1080
    assert all(len(processes) == 1 for processes in process_by_case.values())
    assert len({next(iter(s)) for s in process_by_case.values()}) == 60
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['case_id'], row['method']].append(row)
    condition_rows = []
    metric_names = list(rows[0]['metrics'])
    for case in protocol['case_sets']['test']:
        denominators = set()
        for method in protocol['methods']:
            samples = grouped[case['id'], method]
            assert len(samples) == (1 if method in ('nominal_tour', 'nominal_fifo', 'nominal_greedy') else 3)
            denominators.update(r['metrics']['anomaly_segments'] for r in samples)
            values = {name: average([r['metrics'][name] for r in samples]) for name in metric_names}
            baseline = grouped[case['id'], 'nominal_tour'][0]['metrics']
            values['travel_change_vs_tour_pct'] = average([(r['metrics']['travel_m']/baseline['travel_m']-1)*100 for r in samples])
            values['completion_change_vs_tour_pct'] = average([(r['metrics']['completed_inspections']/baseline['completed_inspections']-1)*100 for r in samples])
            roles = {role: {'segments': average([r['by_role'][role]['segments'] for r in samples]),
                            'confirmed': average([r['by_role'][role]['confirmed'] for r in samples])}
                     for role in ('thermal', 'electrical', 'cooling', 'control')}
            condition_rows.append({'case_id': case['id'], 'block': case['block'], 'family': case['family'], 'method': method,
                                   'model_runs': len(samples), 'metrics': values, 'by_role': roles})
        assert len(denominators) == 1, (case['id'], denominators)
    primary = protocol['analysis']['primary_families']
    all_metrics = list(condition_rows[0]['metrics'])
    blocks = {}
    for method in protocol['methods']:
        blocks[method] = []
        for block in range(12):
            selected = [r for r in condition_rows if r['block'] == block and r['method'] == method and r['family'] in primary]
            assert len(selected) == 4
            blocks[method].append({name: average([r['metrics'][name] for r in selected]) for name in all_metrics})
    aggregates = {}
    for method in protocol['methods']:
        selected = [r for r in condition_rows if r['method'] == method and r['family'] in primary]
        aggregates[method] = {name: bootstrap([row[name] for row in blocks[method]], protocol) for name in all_metrics}
        confirmed = sum(r['metrics']['confirmed_segments'] for r in selected)
        segments = sum(r['metrics']['anomaly_segments'] for r in selected)
        aggregates[method]['total_confirmed_model_mean'] = confirmed
        aggregates[method]['total_unique_anomaly_segments'] = segments
        aggregates[method]['pooled_confirmation_ratio'] = confirmed/segments if segments else None
        aggregates[method]['defined_wait_conditions'] = sum(r['metrics']['consequence_weighted_censored_delay_s'] is not None for r in selected)
        aggregates[method]['by_role'] = {role: {'segments': sum(r['by_role'][role]['segments'] for r in selected),
                                               'confirmed': sum(r['by_role'][role]['confirmed'] for r in selected)}
                                             for role in ('thermal', 'electrical', 'cooling', 'control')}
    families = {}
    for family in [r['id'] for r in protocol['families']]:
        families[family] = {}
        for method in protocol['methods']:
            selected = [r for r in condition_rows if r['family'] == family and r['method'] == method]
            families[family][method] = {name: average([r['metrics'][name] for r in selected]) for name in all_metrics}
            families[family][method]['defined_wait_conditions'] = sum(r['metrics']['consequence_weighted_censored_delay_s'] is not None for r in selected)
            families[family][method]['by_role'] = {role: {'segments': sum(r['by_role'][role]['segments'] for r in selected),
                                                   'confirmed': sum(r['by_role'][role]['confirmed'] for r in selected)}
                                                 for role in ('thermal', 'electrical', 'cooling', 'control')}
    contrasts = []
    for first, second in [*protocol['analysis']['task_primary_contrasts'], protocol['analysis']['joint_contrast']]:
        differences = {}
        for name in ['confirmed_segments', 'consequence_weighted_censored_delay_s', 'weighted_normalized_age',
                     'travel_change_vs_tour_pct', 'completion_change_vs_tour_pct', 'all_weighted_rmse_c']:
            values = [(a[name]-b[name]) if a[name] is not None and b[name] is not None else None
                      for a, b in zip(blocks[first], blocks[second])]
            differences[name] = bootstrap(values, protocol)
        contrasts.append({'first': first, 'second': second, 'metrics': differences})
    seed_variation = {}
    for method in protocol['methods']:
        if method in ('nominal_tour', 'nominal_fifo', 'nominal_greedy'):
            continue
        values = {}
        for seed in protocol['model_seeds']:
            selected = [r for r in rows if r['method'] == method and r['family'] in primary and r['model_seed'] == seed]
            assert len(selected) == 48
            values[str(seed)] = {name: average([r['metrics'][name] for r in selected]) for name in metric_names}
        seed_variation[method] = {'per_seed': values,
            'sample_sd': {name: float(np.std([v[name] for v in values.values()], ddof=1)) if all(v[name] is not None for v in values.values()) else None for name in metric_names}}
    fixed = read(RUN / 'fixed-stream-estimation.json')
    assert len(fixed['rows']) == 216 and fixed['prediction_calls'] == 77760
    fixed_blocks = []
    for block in range(12):
        selected = [r for r in fixed['rows'] if r['case']['block'] == block and r['case']['family'] in primary]
        assert len(selected) == 12
        values = {}
        for subset in ('all', 'not_fresh'):
            for metric in ('rmse_c', 'weighted_rmse_c', 'r2'):
                for estimator in ('nominal', 'cvae'):
                    values[f'{estimator}_{subset}_{metric}'] = average([r[estimator][subset][metric] for r in selected])
                values[f'delta_{subset}_{metric}'] = values[f'cvae_{subset}_{metric}']-values[f'nominal_{subset}_{metric}']
        fixed_blocks.append(values)
    fixed_aggregate = {name: bootstrap([r[name] for r in fixed_blocks], protocol) for name in fixed_blocks[0]}
    scale = [read(p) for p in sorted((RUN / 'scale').glob('*.json')) if not p.name.startswith('feasibility')]
    assert len(scale) == 18
    scales = {}
    for racks in protocol['scale']['racks']:
        selected = [r for r in scale if r['racks'] == racks]
        scales[str(racks)] = {'runs': len(selected), 'median_wall_s_with_tracemalloc': float(np.median([r['wall_s_with_tracemalloc'] for r in selected])),
                             'wall_range_s': [min(r['wall_s_with_tracemalloc'] for r in selected), max(r['wall_s_with_tracemalloc'] for r in selected)],
                             'max_python_traced_peak_bytes': max(r['python_traced_peak_bytes'] for r in selected),
                             'max_energy_residual_kj': max(r['max_energy_residual_kj'] for r in selected),
                             'max_electric_residual_kw': max(r['max_electric_residual_kw'] for r in selected),
                             'feasibility': read(RUN / 'scale' / f'feasibility-{racks}.json')}
    training = {p.stem: read(p) for p in sorted((RUN / 'training').glob('*.json')) if 'case-order' not in p.name}
    source = {'study_id': protocol['study_id'], 'protocol': protocol, 'seal': read(RUN / 'seal.json'),
              'amendments': read(RUN / 'amendments.json'), 'checkpoint_lock': read(RUN / 'test-checkpoint-lock.json'),
              'counts': dict(counts), 'environment_attempts': sum(r['status'] == 'started' and r['environment'] and r['phase'] != 'scale' for r in ledger),
              'physical_scale_attempts': sum(r['status'] == 'started' and r['phase'] == 'scale' for r in ledger),
              'failed_attempts': [r for r in ledger if r['status'] == 'failed'], 'test_conditions': 72, 'independent_seed_blocks': 12,
              'unique_test_physical_processes': 60, 'primary_conditions': 48, 'test_episode_count': len(rows),
              'audit': {'recomputed_summary_episodes': len(rows), 'independently_audited_raw_ledgers': len(audits),
                        'total_completed_inspections_audited': sum(r['events'] for r in audits), 'all_passed': all(r['all_passed'] for r in audits)},
              'definitions': {'aggregation': 'Average three model seeds within condition; equal-weight four primary families per physical seed; average12 blocks.',
                              'error_table': 'Mean per-episode RMSE and R2, not pooled spatial-temporal R2. Fixed-stream errors isolate the estimator.',
                              'confirmation_total': 'Sum over48 primary conditions after model-seed averaging; fractions are expected counts across three trained models, never extra independent anomalies.',
                              'interval': '95% percentile bootstrap of12 master physical-seed blocks; 10000 replicates seed20261103. Not a complete training-uncertainty interval.',
                              'latency': 'Means of final-test episode p50/p95; runtime scope excludes physical precomputation, I/O, evaluator and logger-only grids. One-step timings do not include whole-study overhead.'},
              'method_order': protocol['methods'], 'primary_aggregates': aggregates, 'family_aggregates': families,
              'contrasts': contrasts, 'seed_variation': seed_variation, 'condition_rows': condition_rows, 'block_values': blocks,
              'fixed_stream': {'aggregates': fixed_aggregate, 'blocks': fixed_blocks, 'prediction_calls': fixed['prediction_calls'], 'environment_runs': 0},
              'scale': scales, 'training': training}
    write(PAPER, source)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    write(EVIDENCE / 'test-rows.json', rows)
    for name in ['protocol.json', 'seal.json', 'amendments.json', 'test-checkpoint-lock.json', 'fixed-stream-estimation.json', 'pilot-summary.json', 'preflight-passed.json']:
        shutil.copyfile(RUN / name, EVIDENCE / name)
    shutil.copyfile(RUN / 'attempts.jsonl', EVIDENCE / 'attempts.jsonl')
    for subdirectory in ('training', 'compatibility', 'scale'):
        for path in sorted((RUN / subdirectory).glob('*.json')):
            target = EVIDENCE / subdirectory / path.name
            target.parent.mkdir(exist_ok=True)
            shutil.copyfile(path, target)
    # Small real checkpoint archive travels with the repository; raw frame/log
    # identity list preserves the separately retained local originals.
    with zipfile.ZipFile(EVIDENCE / 'checkpoints.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted((RUN / 'checkpoints').glob('*.pt')):
            archive.write(path, path.name)
    artifacts = {p.relative_to(RUN).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size}
                 for p in sorted(RUN.rglob('*')) if p.is_file()}
    write(EVIDENCE / 'local-artifacts.json', {'root': 'runs/supplement-benchmark-20261103', 'files': artifacts,
                                           'retention': 'Original frame/log files retained locally; metrics, identities, training histories and actual9checkpoints included in Git evidence.'})
    receipt = {'paper_source_sha256': sha(PAPER), 'test_rows_sha256': sha(EVIDENCE / 'test-rows.json'),
               'checkpoint_archive_sha256': sha(EVIDENCE / 'checkpoints.zip'), 'source_artifacts': len(artifacts),
               'counts': dict(counts), 'audit': source['audit'], 'analyzer_sha256': sha(Path(__file__))}
    write(EVIDENCE / 'analysis-receipt.json', receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    build()
