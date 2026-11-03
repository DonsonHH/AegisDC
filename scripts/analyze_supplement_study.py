"""Recompute and summarize the completed independent supplemental study.

Confidence intervals resample twelve physical-seed blocks after averaging
model seeds within condition and assigning equal weight to four fault families.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from patrol_rsi.supplement_metrics import episode_summary
from patrol_rsi.active_inspection import graph_for
from patrol_rsi.aisles import build_agents
from patrol_rsi.facility import FacilityConfig
from patrol_rsi.process import CompositeFacility

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
    elif isinstance(first, (list, tuple)):
        if len(first) != len(second):
            raise AssertionError('Summary length differs: '+where)
        for index, (a, b) in enumerate(zip(first, second)):
            check_equal(a, b, where+f'[{index}]')
    elif isinstance(first, (float, int)) and not isinstance(first, bool):
        if not np.isclose(first, second, rtol=1e-10, atol=1e-10):
            raise AssertionError(f'Summary recomputation differs: {where}: {first} vs {second}')
    elif first != second:
        raise AssertionError('Summary recomputation differs: '+where)


def audit_actual_record(record):
    """Independent raw-ledger checks, separate from simulator safety counters."""
    events, dispatches, assignments = record['inspection_events'], record['dispatches'], record['assignments']
    graph = graph_for(128, 'open'); agents = build_agents(graph, 'provisioned')
    assignment_map = {(a['time_s'], a['agent'], a['task']): a for a in assignments}
    completions = Counter((e['agent'], e['task'], e['time_s']) for e in events)
    expected = Counter((d['agent'], d['task'], d['certificate']['candidate_finish_s']) for d in dispatches)
    assert completions == expected
    assert Counter((a['time_s'], a['agent'], a['task']) for a in assignments) == Counter((d['time_s'], d['agent'], d['task']) for d in dispatches)
    active = []
    for dispatch in dispatches:
        cert = dispatch['certificate']
        agent = agents[dispatch['agent']]; task = graph.tasks[dispatch['task']]
        assert dispatch['task'] in agent['tour'] and task.required_role == agent['role']
        assignment = assignment_map[dispatch['time_s'], dispatch['agent'], dispatch['task']]
        distance = graph.path(tuple(assignment['source']), task.position_m)[0]
        assert abs(distance-assignment['distance_m']) < 1e-9 and tuple(assignment['target']) == task.position_m
        assert assignment['service_s'] == task.service_s
        assert cert['candidate_finish_s'] == dispatch['time_s']+5*math.ceil((distance+task.service_s)/5-1e-10)
        assert cert['ok'] and cert['candidate_finish_s'] <= min(1800, cert['candidate_due_s'])+1e-9
        assert all(a <= b+1e-9 for a, b in zip(cert['fallback_completion_s'], cert['fallback_due_s']))
        active = [d for d in active if d['certificate']['candidate_finish_s'] > dispatch['time_s']+1e-9]
        assert all(d['task'] != dispatch['task'] and d['agent'] != dispatch['agent'] for d in active)
        active.append(dispatch)
    assert sum(d['extra_event_visit'] for d in dispatches) <= 12
    for event in events:
        task = graph.tasks[event['task']]
        assert event['calibrated'] and event['role'] == task.required_role and event['access'] == task.access
        assert event['task_id'] == task.task_id and event['kind'] == task.kind
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


def independent_labels(reference, case):
    """Rebuild four professional labels/excesses without stepping a simulator."""
    graph = graph_for(128, 'open')
    temperatures = reference['true_temperature_c']
    contact = reference['offline_contact_temperature_c']
    flow = reference['offline_rack_flow_kg_s'].reshape(360, 16, 8).sum(2)
    spec = case['spec']
    # Pure declared fault schedule: no physical integration or environment run.
    config = FacilityConfig(fault_start_s=spec['fault_start_s'], fault_end_s=spec['fault_start_s']+spec['duration_s'], fault_rack=spec['fault_rack'])
    plant = CompositeFacility(config, spec['seed'], spec['scenario'], 'feedback')
    np.testing.assert_array_equal(reference['rack_weights'],plant.criticality)
    bias = np.stack([plant._faults(float(t))['sensor_bias'] for t in range(0, 1800, 5)])
    bias = abs(bias.reshape(360, 16, 8).mean(2))
    labels, excess, weights = [], [], []
    for task in graph.tasks:
        if task.kind == 'thermal':
            v = temperatures[:, task.index]; mask = v > 65; score = np.maximum(v-65, 0)/20
        elif task.kind == 'electrical':
            v = contact[:, task.index]; mask = v > 60; score = np.maximum(v-60, 0)/30
        elif task.kind == 'cooling':
            v = flow[:, task.index]; mask = v < 33.6; score = np.maximum(1-v/33.6, 0)
        else:
            v = bias[:, task.index]; mask = v > 1; score = v/18
        labels.append(mask); excess.append(score)
        weights.append(reference['rack_weights'][task.index] if task.kind == 'thermal' else reference['rack_weights'].reshape(16, 8)[task.index].mean())
    labels, excess = np.stack(labels, 1), np.stack(excess, 1)
    np.testing.assert_array_equal(labels, reference['offline_task_positive_labels'])
    return labels, excess, np.asarray(weights)


def independent_fresh_mask(record):
    expected=np.zeros((360,128),dtype=bool)
    expected[:,np.arange(128)%4==0]=True
    for event in record['inspection_events']:
        if event['kind']=='thermal':
            assert event['time_s']%5==0
            expected[int(event['time_s']/5)-1,event['task']]=True
    return expected


def independent_task_metrics(record, labels, excess, weights):
    graph = graph_for(128, 'open'); events = record['inspection_events']
    intervals = []
    for task_index, task in enumerate(graph.tasks):
        edges = np.diff(np.r_[False, labels[:, task_index], False].astype(int))
        for start, end in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
            if end-start < 3:
                continue
            found = [e['time_s'] for e in events if e['task'] == task_index and e['alarm'] and start <= int(e['time_s']/5)-1 < end]
            first = min(found) if found else None
            intervals.append({'task': task_index, 'task_id': task.task_id, 'kind': task.kind,
                              'onset_s': start*5., 'end_s': end*5., 'samples': int(end-start),
                              'weight': float(weights[task_index]*(1+excess[start:end, task_index].mean())),
                              'first_confirmation_s': first, 'detected': bool(found),
                              'delay_or_censor_s': (first if found else end*5.)-start*5.})
    check_equal(intervals, record['anomaly_intervals'], 'raw-label anomaly intervals')
    metric = record['metrics']
    confirmed = sum(r['detected'] for r in intervals)
    check_equal(confirmed, metric['confirmed_segments'], 'confirmed segments')
    check_equal(len(intervals), metric['anomaly_segments'], 'anomaly denominator')
    check_equal(len(intervals)-confirmed, metric['missed_segments'], 'missed segments')
    check_equal(1-confirmed/len(intervals) if intervals else None, metric['miss_rate'], 'miss rate')
    wait = sum(r['weight']*r['delay_or_censor_s'] for r in intervals)/sum(r['weight'] for r in intervals) if intervals else None
    check_equal(wait, metric['consequence_weighted_censored_delay_s'], 'weighted censored delay')
    check_equal(average([r['delay_or_censor_s'] for r in intervals if r['detected']]), metric['detected_only_mean_delay_s'], 'detected-only delay')
    false_alarms = sum(e['alarm'] and not labels[int(e['time_s']/5)-1, e['task']] for e in events)
    check_equal(false_alarms, metric['false_measured_confirmations'], 'false measured confirmations')
    check_equal(len(events), metric['completed_inspections'], 'completed inspections')
    check_equal(sum(a['distance_m'] for a in record['assignments']), metric['travel_m'], 'actual travel')
    check_equal(sum(a['service_s'] for a in record['assignments']), metric['service_s'], 'actual service')
    check_equal(18*1795-metric['travel_m']-metric['service_s'], metric['idle_s'], 'actual idle')
    check_equal(sum(e['extra_event_visit'] for e in events), metric['extra_event_visits'], 'extra completions')
    check_equal(sum(sum(r['certificate']['ok'] and r['budget_allowed'] for r in d['candidates']) > 1 for d in record['decisions']), metric['choice_opportunities'], 'legal choice opportunities')
    completion = defaultdict(list)
    for e in events:
        completion[e['task']].append(e['time_s'])
    clocks = np.arange(5, 1801, 5)
    age = []
    for task in range(len(graph.tasks)):
        stamps = np.r_[0., completion[task]]
        last = stamps[np.searchsorted(stamps, clocks, side='right')-1]
        age.append(clocks-last)
    age = np.stack(age, 1)
    check_equal(float((age > record['deadlines_s']).mean()), metric['mean_overdue_fraction'], 'overdue fraction')
    check_equal(float(age.max()), metric['maximum_inspection_age_s'], 'maximum age')
    check_equal(sum(bool(completion[t]) for t in range(len(graph.tasks)))/len(graph.tasks), metric['final_professional_coverage'], 'final professional coverage')
    for role in ('thermal', 'electrical', 'cooling', 'control'):
        selected = [r for r in intervals if r['kind'] == role]
        tasks = [i for i, t in enumerate(graph.tasks) if t.kind == role]
        row = record['by_role'][role]
        check_equal(len(selected), row['segments'], role+' denominator')
        check_equal(sum(r['detected'] for r in selected), row['confirmed'], role+' confirmations')
        check_equal(sum(bool(completion[t]) for t in tasks)/len(tasks), row['final_coverage'], role+' coverage')
        check_equal(float((age[:, tasks] > np.asarray(record['deadlines_s'])[tasks]).mean()), row['mean_overdue_fraction'], role+' overdue')
        check_equal(float(age[:, tasks].max()), row['maximum_inspection_age_s'], role+' maximum age')
    np.testing.assert_allclose(weights, record['asset_weights'], rtol=0, atol=0)


def verify_models(protocol, training):
    import torch
    from patrol_rsi.supplement_models import BenchmarkPolicy
    lock = read(RUN / 'test-checkpoint-lock.json')['checkpoints']
    assert len(lock) == 9 and set(lock) == {p.name for p in (RUN / 'checkpoints').glob('*.pt')}
    for name, identity in lock.items():
        assert sha(RUN / 'checkpoints' / name) == identity
    for seed in protocol['model_seeds']:
        history = training[f'cvae-{seed}']['history']
        assert len(history) == 30 and [r['epoch'] for r in history] == list(range(1, 31))
        best = min(history, key=lambda r:r['development_weighted_mse_normalized'])
        pack = torch.load(RUN / 'checkpoints' / f'cvae-{seed}.pt', map_location='cpu', weights_only=True)
        assert pack['model_seed'] == seed and pack['epoch'] == best['epoch']
        assert pack['study_id'] == protocol['study_id'] and pack['source_seal_sha256'] == sha(RUN / 'seal.json')
        assert pack['architecture'] == {'channels': 57, 'width': 16, 'latent': 16}
        check_equal(pack['development_weighted_mse'], best['development_weighted_mse_normalized'], 'CVAE checkpoint selection')
        assert sum(v.numel() for v in pack['state_dict'].values()) == 295777
        assert all(bool(torch.isfinite(v).all()) for v in pack['state_dict'].values())
        assert float(pack['state_dict']['output.weight'].abs().sum()) > 0
        order = read(RUN / 'training' / f'ppo-case-order-{seed}.json')
        torch.manual_seed(seed); initial = BenchmarkPolicy()
        initial_hash = hashlib.sha256(b''.join(p.detach().numpy().tobytes() for p in initial.parameters())).hexdigest()
        for estimator in ('nominal', 'cvae'):
            history = training[f'ppo-{estimator}-{seed}']
            assert history['initial_weights_sha256'] == initial_hash
            assert [r['case_id'] for r in history['history']] == order and len(order) == 120
            pack = torch.load(RUN / 'checkpoints' / f'ppo-{estimator}-{seed}.pt', map_location='cpu', weights_only=True)
            assert pack['episodes'] == 120 and pack['model_seed'] == seed and pack['estimator'] == estimator
            assert pack['study_id'] == protocol['study_id'] and all(bool(torch.isfinite(v).all()) for v in pack['state_dict'].values())
            assert pack['state_dict']['actor.0.weight'].shape == (32, 21) and pack['state_dict']['critic.0.weight'].shape == (32, 10)
            assert any(not torch.equal(value, initial.state_dict()[name]) for name,value in pack['state_dict'].items() if name.startswith('actor.'))
    return {'checkpoints_sha_verified':9,'cvae_selection_histories_verified':3,'paired_policy_initializations_and_orders_verified':3,
            'final120_episode_policies_verified':6,'actor_parameter_updates_verified':6}


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
    seal = read(RUN / 'seal.json'); amendments = read(RUN / 'amendments.json')
    expected_sources = seal['source_hashes']
    for amendment in amendments:
        assert hashlib.sha256(json.dumps(expected_sources, sort_keys=True).encode()).hexdigest() == amendment['previous_source_hashes_sha256']
        expected_sources = amendment['source_hashes']
    for name, identity in expected_sources.items():
        assert sha(ROOT / name) == identity
    expected_ids = set()
    for case in protocol['case_sets']['test']:
        expected_ids.update(case['id']+'-nominal-'+method for method in ('tour','fifo','greedy'))
        expected_ids.update(f"{case['id']}-nominal-ppo-{seed}" for seed in protocol['model_seeds'])
        expected_ids.update(f"{case['id']}-cvae-{method}-{seed}" for seed in protocol['model_seeds'] for method in ('fifo','greedy','ppo'))
    assert {p.name for p in (RUN / 'test').iterdir() if p.is_dir()} == expected_ids
    assert {identifier for phase,identifier in completed if phase == 'test'} == expected_ids
    rows, audits = [], []
    process_by_case = defaultdict(set)
    for case in protocol['case_sets']['test']:
        reference_path = RUN / 'test' / (case['id']+'-nominal-tour') / 'arrays.npz'
        with np.load(reference_path) as a:
            reference = {key:a[key] for key in a.files}
        labels, excess, weights = independent_labels(reference, case)
        for folder in sorted((RUN / 'test').glob(case['id']+'-*')):
            if not folder.is_dir():
                continue
            identities = read(folder / 'files.json')
            assert set(identities) == {'record.json.gz','arrays.npz','summary.json'}
            for name, identity in identities.items():
                assert sha(folder / name) == identity
            with gzip.open(folder / 'record.json.gz', 'rt', encoding='utf-8') as stream:
                record = json.load(stream)
            with np.load(folder / 'arrays.npz') as arrays:
                np.testing.assert_array_equal(arrays['true_temperature_c'], reference['true_temperature_c'])
                np.testing.assert_array_equal(arrays['offline_task_positive_labels'], labels)
                np.testing.assert_array_equal(arrays['rack_weights'], reference['rack_weights'])
                np.testing.assert_array_equal(arrays['fresh_measurement_mask'],independent_fresh_mask(record))
                recomputed = episode_summary(record, arrays)
            stored = read(folder / 'summary.json')
            check_equal(recomputed, stored, folder.name)
            audit = audit_actual_record(record)
            independent_task_metrics(record, labels, excess, weights)
            check_equal(float(reference['offline_process_scalars'][:,1].sum()*5/3600),record['metrics']['unserved_IT_kwh'],'shared process unserved energy')
            metadata = record['supplement_metadata']
            assert metadata['case'] == case and record['spec'] == case['spec']
            assert metadata['phase'] == 'test' and metadata['id'] == folder.name
            expected_name = case['id']+'-'+metadata['method_label'].replace('_','-')
            if metadata['model_seed'] is not None:
                assert metadata['model_seed'] in protocol['model_seeds']
                expected_name += '-'+str(metadata['model_seed'])
            assert expected_name == folder.name
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
            assert {r['model_seed'] for r in samples} == ({None} if len(samples) == 1 else set(protocol['model_seeds']))
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
    from patrol_rsi.supplement_metrics import temperature_metrics
    cases = {c['id']:c for c in protocol['case_sets']['test']}
    assert {(r['case']['id'],r['model_seed']) for r in fixed['rows']} == {(case,seed) for case in cases for seed in protocol['model_seeds']}
    for row in fixed['rows']:
        case = row['case']; assert case == cases[case['id']]
        reference_path = RUN / 'test' / (case['id']+'-nominal-tour') / 'arrays.npz'
        assert sha(reference_path) == row['source_arrays_sha256']
        with np.load(reference_path) as a, np.load(RUN / 'fixed-stream-predictions' / f"{case['id']}-cvae-{row['model_seed']}.npz") as b:
            nominal = temperature_metrics(a['predicted_temperature_c'],a['true_temperature_c'],a['rack_weights'],a['fresh_measurement_mask'])
            neural = temperature_metrics(b['predicted_temperature_c'],a['true_temperature_c'],a['rack_weights'],a['fresh_measurement_mask'])
            np.testing.assert_array_equal(b['predicted_temperature_c'][a['fresh_measurement_mask']],a['predicted_temperature_c'][a['fresh_measurement_mask']])
        check_equal(nominal,row['nominal'],'fixed-stream nominal errors')
        check_equal(neural,row['cvae'],'fixed-stream CVAE errors')
    fixed_blocks = []
    for block in range(12):
        selected = [r for r in fixed['rows'] if r['case']['block'] == block and r['case']['family'] in primary]
        assert len(selected) == 12
        values = {}
        for subset in ('all', 'not_fresh'):
            for metric in ('rmse_c', 'weighted_rmse_c', 'r2'):
                for estimator in ('nominal', 'cvae'):
                    values[f'{estimator}_{subset}_{metric}'] = average([r[estimator][subset][metric] for r in selected])
                a,b=values[f'cvae_{subset}_{metric}'],values[f'nominal_{subset}_{metric}']
                values[f'delta_{subset}_{metric}'] = a-b if a is not None and b is not None else None
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
    model_audit = verify_models(protocol,training)
    execution_source=read(RUN/'source-executed.json')
    assert sha(RUN/'source-executed.zip')==execution_source['archive_sha256']
    with zipfile.ZipFile(RUN/'source-executed.zip') as archive:
        assert set(archive.namelist())==set(execution_source['files'])
        for name,identity in execution_source['files'].items():
            assert hashlib.sha256(archive.read(name)).hexdigest()==identity
    training_costs=[]
    for seed in protocol['model_seeds']:
        for estimator in ('nominal','cvae'):
            attempts=[r for r in ledger if r['phase']=='ppo_train' and r['status']=='completed' and r['model_seed']==seed and r['estimator']==estimator]
            history=training[f'ppo-{estimator}-{seed}']['history']
            training_costs.append({'model_seed':seed,'estimator':estimator,'episodes':len(attempts),'time_steps':len(attempts)*359,
                'task_choices':sum(r['task_choices'] for r in history),
                'choice_sets_with_alternatives':sum(r['choice_sets_with_alternatives'] for r in history),
                'optimizer_updates':len(attempts)*4,'episode_and_update_wall_s':sum(r['wall_s'] for r in attempts)})
    neural_episodes = sum(r['status'] == 'completed' and
        ((r['phase'] in ('ppo_train','ppo_development') and r.get('estimator') == 'cvae') or
         (r['phase'] == 'test' and r.get('method_label','').startswith('cvae_'))) for r in ledger)
    assert neural_episodes == 1026
    source = {'study_id': protocol['study_id'], 'protocol': protocol, 'seal': read(RUN / 'seal.json'),
              'amendments': read(RUN / 'amendments.json'), 'checkpoint_lock': read(RUN / 'test-checkpoint-lock.json'),
              'executed_source':execution_source,
              'counts': dict(counts), 'environment_attempts': sum(r['status'] == 'started' and r['environment'] and r['phase'] != 'scale' for r in ledger),
              'physical_scale_attempts': sum(r['status'] == 'started' and r['phase'] == 'scale' for r in ledger),
              'failed_attempts': [r for r in ledger if r['status'] == 'failed'], 'test_conditions': 72, 'independent_seed_blocks': 12,
              'unique_test_physical_processes': 60, 'primary_conditions': 48, 'test_episode_count': len(rows),
              'neural_prediction_accounting':{'closed_loop_episodes':neural_episodes,'endpoints_per_episode':360,
                  'online_predictions_source_derived':neural_episodes*360,'fixed_stream_predictions':fixed['prediction_calls'],
                  'total_predictions_excluding_training_and_warmup':neural_episodes*360+fixed['prediction_calls'],
                  'scope':'Prior-mean temperature predictions only; PPO actor/critic and training forwards are separate operations.'},
              'audit': {'summary_consistency_episodes': len(rows),'recomputed_report_metric_episodes':len(rows), 'independently_audited_raw_ledgers': len(audits),
                        'independent_fields':['temperature errors and fresh masks','physical/asset weights','raw-label intervals and professional confirmations',
                                              'weighted censored waits and false alarms','travel/service/idle/completions','coverage/overdue/maximum age',
                                              'weighted normalized age','actual assignment/reservation/revisit/budget audit','shared process unserved energy'],
                        'raw_label_professional_outcomes_recomputed':len(rows),'fixed_stream_error_cases_recomputed':216,
                        'model_audit':model_audit,
                        'total_completed_inspections_audited': sum(r['events'] for r in audits), 'all_passed': all(r['all_passed'] for r in audits)},
              'definitions': {'aggregation': 'Average three model seeds within condition; equal-weight four primary families per physical seed; average12 blocks.',
                              'error_table': 'Mean per-episode RMSE and R2, not pooled spatial-temporal R2. Fixed-stream errors isolate the estimator.',
                              'confirmation_total': 'Sum over48 primary conditions after model-seed averaging; fractions are expected counts across three trained models, never extra independent anomalies.',
                              'interval': '95% percentile bootstrap of12 master physical-seed blocks; 10000 replicates seed20261103. Not a complete training-uncertainty interval.',
                              'latency': 'Means of final-test episode p50/p95; runtime scope excludes physical precomputation, I/O, evaluator and logger-only grids. One-step timings do not include whole-study overhead.'},
              'method_order': protocol['methods'], 'primary_aggregates': aggregates, 'family_aggregates': families,
              'contrasts': contrasts, 'seed_variation': seed_variation, 'condition_rows': condition_rows, 'block_values': blocks,
              'fixed_stream': {'aggregates': fixed_aggregate, 'blocks': fixed_blocks, 'prediction_calls': fixed['prediction_calls'], 'environment_runs': 0},
              'scale': scales, 'training': training,'policy_training_costs':training_costs}
    representative=protocol['case_sets']['test'][0];example_seed=protocol['model_seeds'][0]
    frame_time=representative['spec']['fault_start_s']+90;frame=int(frame_time/5)-1
    pod=representative['spec']['fault_rack']//8;rack=pod*8+1
    reference_path=RUN/'test'/(representative['id']+'-nominal-tour')/'arrays.npz'
    prediction_path=RUN/'fixed-stream-predictions'/f"{representative['id']}-cvae-{example_seed}.npz"
    with np.load(reference_path) as a,np.load(prediction_path) as b:
        example={'case':representative,'model_seed':example_seed,'frame_time_s':frame_time,'trace_rack_index':rack,'pod_index':pod,
                 'clock_s':list(range(5,1801,5)),
                 'frame_temperature_c':{'nominal':a['predicted_temperature_c'][frame].tolist(),'cvae':b['predicted_temperature_c'][frame].tolist(),'truth':a['true_temperature_c'][frame].tolist()},
                 'trace':{'nominal_c':a['predicted_temperature_c'][:,rack].tolist(),'cvae_c':b['predicted_temperature_c'][:,rack].tolist(),
                          'truth_c':a['true_temperature_c'][:,rack].tolist(),'fresh_mask':a['fresh_measurement_mask'][:,rack].tolist(),
                          'pod_flow_kg_s':a['offline_rack_flow_kg_s'].reshape(360,16,8).sum(2)[:,pod].tolist()},
                 'source_arrays_sha256':sha(reference_path),'source_prediction_sha256':sha(prediction_path),
                 'selection':'Deterministic illustrative rule: first registered compound test case, modelseed271, injection+90s frame, localrack1 of injected pod.'}
    example_path=ROOT/'paper/source-data/supplement-example.json'
    write(example_path,example)
    source['example']={'path':example_path.relative_to(ROOT).as_posix(),'sha256':sha(example_path)}
    write(PAPER, source)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    write(EVIDENCE / 'test-rows.json', rows)
    for name in ['protocol.json', 'seal.json', 'amendments.json', 'test-checkpoint-lock.json', 'fixed-stream-estimation.json', 'pilot-summary.json', 'preflight-passed.json']:
        shutil.copyfile(RUN / name, EVIDENCE / name)
    shutil.copyfile(RUN / 'attempts.jsonl', EVIDENCE / 'attempts.jsonl')
    for name in ('source-executed.zip','source-executed.json'):
        shutil.copyfile(RUN/name,EVIDENCE/name)
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
    lines=['# 独立补充基准：机房状态估计与四专业巡检','',
           '本包来自2026-11-03新授权的数据与模型补充。原事件验证包、九规则搜索和原失败记录保持原件身份。','',
           f"实际环境尝试{source['environment_attempts']}次，另有{source['physical_scale_attempts']}次纯物理规模运行；新包失败尝试{len(source['failed_attempts'])}次。",'',
           '最终测试包含12个独立物理种子块、72个条件、60条唯一物理轨迹、1080个闭环回合；主要分析为四故障族共48条件。',
           '三个CVAE-U-Net各训练30轮，六个PPO各训练120回合。条件内先平均三个模型种子，四故障族等权，再对12个物理种子块计算区间。','',
           '|方法|平均模型确认总数／唯一异常段|每主要条件确认|闭环加权RMSE / °C|加权归一年龄|','|---|---:|---:|---:|---:|']
    for method in protocol['methods']:
        row=aggregates[method]
        lines.append(f"|{method}|{row['total_confirmed_model_mean']:.2f}/{row['total_unique_anomaly_segments']:.0f}|{row['confirmed_segments']['mean']:.3f}|{row['all_weighted_rmse_c']['mean']:.3f}|{row['weighted_normalized_age']['mean']:.6f}|")
    lines += ['', '确认总数的小数表示训练种子平均，不增加独立样本。误差在本合成物理基准内解释；共同Tour观测流的主要估计对照、配对区间、四专业结果与成本见完整报告。','',
              '## 检查与原件','',
              f"分析器独立重建1080个回合的专业异常与确认、等待和实际成本，核对{source['audit']['total_completed_inspections_audited']:,}条完成记录；216个共同观测流误差重新计算，九个模型SHA及训练身份核对通过。",'',
              '- `protocol.json`、`seal.json`、`amendments.json`和`attempts.jsonl`：原登记、源身份与追加式执行记录。',
              '- `test-rows.json`：1080条测试评价明细及原始文件SHA；训练曲线在`training/`，实际九个checkpoint在`checkpoints.zip`。',
              '- `source-executed.zip`及同名JSON：本轮实际执行的34个源文件和逐文件SHA，保留执行版本与随后工程维护的区别。',
              '- `local-artifacts.json`：本地完整逐帧数组、执行日志与物理记录索引，根目录`runs/supplement-benchmark-20261103`。这些大体积原件留在共享本地工作区。',
              '- `paper/source-data/supplement-study.json`与`supplement-example.json`：仓库内可检查的图表输入和编号示例，HTML重建无需训练或新环境执行。','',
              '## 阅读与复算','',
              '先打开`paper/supervisor-briefing.html`离线阅读；完整方法为`paper/supplement-study-methods.md`。',
              '在已有写作依赖环境运行`python scripts/build_supervisor_report.py`可由保存输入重建报告。',
              '完整原件复算需保留本地`runs/`原件及隔离的Torch环境：`python scripts/analyze_supplement_study.py`；静态来源核对使用`python scripts/verify_report_sources.py`。',
              '执行器为`python scripts/run_supplement_study.py status`；`all`显式运行登记研究，不属于报告重建。研究环境为Python3.12.14、NumPy2.3.5、Torch2.6.0+cu124和RTX4060 Laptop GPU，环境身份见seal。','']
    (EVIDENCE/'README.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    build()
