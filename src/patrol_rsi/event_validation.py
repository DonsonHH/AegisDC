"""Frozen, finite paired evaluation of event permissions and risk location."""
import csv
import gzip
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .reorder_execution import run_reorder
from .risk_response import run_response


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def load_resume(protocol, prior, index_path):
    """Read-only validation of the approved amendment and immutable prior attempts."""
    amendment = protocol.get('amendment', {})
    if amendment.get('authorization') != 'user_approved':
        raise ValueError('Budget amendment is pending user decision')
    current_sources = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}
    if current_sources != amendment['resumption_source_sha256']:
        raise ValueError('Resumption code differs from the reviewed amendment')
    index_bytes = index_path.read_bytes()
    if hashlib.sha256(index_bytes).hexdigest() != amendment['prior_index_sha256']:
        raise ValueError('Prior index identity mismatch')
    index = json.loads(index_bytes)
    for name, expected in index.items():
        path = (prior/name).resolve()
        if not path.is_relative_to(prior.resolve()):
            raise ValueError('Prior artifact path escapes run directory')
        data = path.read_bytes()
        if len(data) != expected['bytes'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
            raise ValueError('Prior artifact changed: '+name)
    old_protocol = json.loads((prior/'protocol.json').read_text(encoding='utf-8'))
    original = {k:v for k,v in protocol.items() if k != 'amendment'}
    original['max_evaluations'] = old_protocol['max_evaluations']
    if original != old_protocol or protocol['max_evaluations'] != old_protocol['max_evaluations']+1:
        raise ValueError('Amendment may add only one failed-attempt allowance; scientific protocol must match')
    attempts = json.loads((prior/'attempts.json').read_text(encoding='utf-8'))
    expected_keys = [(c['id'],m) for c in old_protocol['cases'] for m in old_protocol['methods']]
    if (len(attempts) != 10 or [a['status'] for a in attempts] != ['completed']*9+['failed']
            or [(a['case'],a['method']) for a in attempts] != expected_keys[:10]
            or attempts[-1]['error'] != 'Risk provenance components do not match executed risk'):
        raise ValueError('Unexpected prior attempt history')
    rows = json.loads((prior/'rows.json').read_text(encoding='utf-8'))
    if len(rows) != 9 or [(r['case'],r['method']) for r in rows] != expected_keys[:9]:
        raise ValueError('Prior successful rows do not match attempts')
    case_by_id = {c['id']:c for c in protocol['cases']}
    for row in rows:
        case = case_by_id[row['case']]
        if case['spec'].get('public_risk_pulses'):
            raise ValueError('Cannot inherit a case affected by the provenance repair')
        if row['record'] not in index:
            raise ValueError('Prior record absent from immutable index')
        with gzip.open(prior/row['record'],'rt',encoding='utf-8') as stream:
            record = json.load(stream)
        if record['spec'] != case['spec']:
            raise ValueError('Prior record specification mismatch')
    return attempts, {(r['case'],r['method']):r for r in rows}, index


def confirmed(record):
    return {(i['task_id'], i['onset_s'], i['end_s']) for i in record['anomaly_intervals'] if i['detected']}


def interval_keys(record):
    return {(i['task_id'], i['onset_s'], i['end_s']) for i in record['anomaly_intervals']}


def paired(a, b):
    if a['process_sha256'] != b['process_sha256'] or interval_keys(a) != interval_keys(b):
        raise ValueError('Paired processes or evaluation intervals differ')
    ac, bc = confirmed(a), confirmed(b)
    am, bm = a['metrics'], b['metrics']
    return {'gained': len(ac-bc), 'lost': len(bc-ac), 'net': len(ac)-len(bc),
            'gained_intervals': sorted(ac-bc), 'lost_intervals': sorted(bc-ac),
            'travel_delta_m': am['travel_m']-bm['travel_m'],
            'travel_delta_pct': 100*(am['travel_m']/bm['travel_m']-1),
            'service_delta_s': am['service_s']-bm['service_s'],
            'completed_delta': am['completed_inspections']-bm['completed_inspections'],
            'completed_loss_pct': 100*(1-am['completed_inspections']/bm['completed_inspections'])}


def bootstrap_mean(values, seed):
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = values[rng.integers(0, len(values), (10000, len(values)))].mean(axis=1)
    return {'mean': float(values.mean()), 'percentile95': np.quantile(means, [.025,.975]).tolist(),
            'positive': int((values>0).sum()), 'zero': int((values==0).sum()), 'negative': int((values<0).sum())}


def summarize(protocol, rows, pairs):
    groups = {}
    for group in sorted({r['group'] for r in rows}):
        groups[group] = {}
        for method in protocol['methods']:
            subset = [r for r in rows if r['group']==group and r['method']==method]
            groups[group][method] = {'cases': len(subset),
                **{k: sum(r[k] for r in subset) for k in ['anomaly_segments','confirmed_segments','missed_segments','extra_event_visits']},
                **{'mean_'+k: float(np.mean([r[k] for r in subset])) for k in ['travel_m','service_s','completed_inspections']},
                'event_outcomes': dict(sum((Counter(r['event_outcomes']) for r in subset), Counter()))}
    primary = [p for p in pairs if p['group']=='coupled']
    comparisons = {}
    for contrast in ['fifo_minus_tour','fifo_minus_shuffled']:
        comparisons[contrast] = {
            'net_confirmations': bootstrap_mean([p[contrast]['net'] for p in primary], protocol['bootstrap_seed']),
            **{k: float(np.mean([p[contrast][k] for p in primary])) for k in
               ['gained','lost','travel_delta_m','travel_delta_pct','service_delta_s','completed_delta','completed_loss_pct']}}
    # All-condition uncertainty resamples process-seed clusters, never individual abnormal segments.
    seeds = sorted({p['seed'] for p in pairs})
    cluster_net = [sum(p['fifo_minus_tour']['net'] for p in pairs if p['seed']==s) for s in seeds]
    main = comparisons['fifo_minus_tour']
    info = comparisons['fifo_minus_shuffled']
    limits = protocol['decision_thresholds']
    enough = sum(p['anomaly_segments']>0 for p in primary) >= limits['minimum_anomalous_primary_processes']
    safe = all(r[k]==0 for r in rows for k in ['tasks_violating_exact_gap','invalid_assignments','duplicate_reservations'])
    cost = (main['travel_delta_pct'] <= limits['maximum_travel_increase_pct'] and
            main['completed_loss_pct'] <= limits['maximum_completion_loss_pct'])
    gain = (main['net_confirmations']['mean'] >= limits['minimum_mean_net_confirmations'] and
            main['net_confirmations']['percentile95'][0] > 0)
    information = (info['net_confirmations']['mean'] >= limits['minimum_mean_net_confirmations'] and
                   info['net_confirmations']['percentile95'][0] > 0)
    decision = ('freeze_event_baseline_information_supported' if information else 'conditional_event_value_information_unresolved') if enough and safe and cost and gain else 'stop_bounded_package_keep_conditional_results'
    return {'evaluations': len(rows), 'model_calls':0, 'training':0, 'groups': groups,
            'primary_paired_processes':len(primary),'primary_comparisons':comparisons,
            'all_conditions_seed_cluster_net':bootstrap_mean(cluster_net, protocol['bootstrap_seed']),
            'gates':{'enough_anomalous_primary_processes':enough,'all_safety_zero':safe,'primary_mean_cost':cost,
                     'primary_gain':gain,'risk_information_increment':information},'decision':decision,
            'uncertainty_scope':'Exploratory percentile bootstrap over 12 process seeds. Not power-calibrated or population-wide inference.'}


def run_validation(args):
    from .cli import ROOT
    path = Path(args.protocol) if args.protocol else ROOT/'configs/event-validation.json'
    protocol = json.loads(path.read_text(encoding='utf-8'))
    cases = protocol['cases']
    resume = getattr(args,'resume_from',None)
    expected_budget = len(cases)*len(protocol['methods']) + int(bool(resume))
    if expected_budget != protocol['max_evaluations'] or protocol['methods'] != ['tour','fifo','shuffled']:
        raise ValueError('Invalid frozen evaluation budget or methods')
    if len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Duplicate cases')
    if {c['spec']['seed'] for c in cases} & set(protocol['seen_seeds']):
        raise ValueError('Seen confirmation seed')
    attempts, inherited, prior_index = [], {}, {}
    if resume:
        prior = Path(resume)
        index_path = ROOT/protocol['amendment']['prior_index_path']
        attempts, inherited, prior_index = load_resume(protocol,prior,index_path)
    elif 'amendment' in protocol:
        raise ValueError('An amendment must explicitly inherit the stopped package')
    out = Path(args.output); out.mkdir(parents=True, exist_ok=False)
    if resume:
        for name in prior_index:
            target = out/'prior'/name
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(prior/name,target)
        write(out/'prior-index.json',prior_index)
        write(out/'inheritance.json',{'original_attempts':len(attempts),'reused_successful_records':len(inherited),
                                    'scope':'Original9 results retain old source seal; new evaluations use current seal.'})
        write(out/'attempts.json',attempts)
    sources = {p.name: p.read_bytes() for p in Path(__file__).parent.glob('*.py')}
    (out/'source').mkdir()
    for name, data in sources.items():
        (out/'source'/name).write_bytes(data)
    (out/'protocol.json').write_bytes(path.read_bytes())
    write(out/'seal.json', {'at':datetime.now(timezone.utc).isoformat(),
        'protocol_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'source_sha256':{name:hashlib.sha256(data).hexdigest() for name,data in sources.items()}})
    rows, pairs = [], []
    for case in cases:
        records = {}
        for method in protocol['methods']:
            key = (case['id'],method)
            if key in inherited:
                row = inherited[key]
                shutil.copyfile(out/'prior'/row['record'],out/row['record'])
                with gzip.open(out/row['record'],'rt',encoding='utf-8') as stream:
                    records[method] = json.load(stream)
                rows.append(row)
                continue
            if len(attempts) >= protocol['max_evaluations']:
                raise RuntimeError('Budget exhausted')
            attempt = {'case':case['id'],'method':method,'status':'started','at':datetime.now(timezone.utc).isoformat()}
            attempts.append(attempt); write(out/'attempts.json',attempts)
            try:
                if method=='tour':
                    record, env = run_reorder(case['spec'],None,{'method':'T'})
                    record['process_sha256'] = env.trace.fingerprint
                else:
                    record, env = run_response(case['spec'],extra_visit_budget=protocol['extra_visit_budget'],
                        risk_permutation_seed=case['permutation_seed'] if method=='shuffled' else None)
                record['spec'] = case['spec']
                record['process_metadata'] = env.trace.metadata
                record['location_metadata'] = {'rack':case['spec']['fault_rack'],'pod':case['spec']['fault_rack']//8,
                    'has_remote_temperature':case['spec']['fault_rack']%4==0}
                filename = case['id']+'-'+method+'.json.gz'
                with gzip.open(out/filename,'wt',encoding='utf-8') as stream:
                    json.dump(record,stream,allow_nan=False)
                records[method] = record
                events = record.get('public_events',[])
                outcomes = Counter(e['status'] for e in events)
                outcomes['normal_measured'] = sum(e['status']=='measured' and not e['measured_alarm'] for e in events)
                outcomes['same_time_measurement'] = sum(e['measurement_s']==e['visible_s'] for e in events)
                outcomes['prior_signal_measurement'] = sum(e['measurement_s'] is not None and e['measurement_s']>e['visible_s'] for e in events)
                multiple = sum(sum(c['certificate']['ok'] and c.get('budget_allowed',True) and c['event_id'] is not None
                                   for c in d['candidates'])>1 for d in record.get('decisions',[]))
                row = {'case':case['id'],'group':case['group'],'seed':case['spec']['seed'],'method':method,'record':filename,
                       **{k:record['metrics'].get(k,0) for k in ['anomaly_segments','confirmed_segments','missed_segments',
                        'consequence_weighted_censored_delay_s','travel_m','service_s','completed_inspections','extra_event_visits',
                        'tasks_violating_exact_gap','invalid_assignments','duplicate_reservations']},
                       'multiple_legal_event_decisions':multiple,'event_outcomes':dict(outcomes)}
                rows.append(row); attempt['status']='completed'
                print(f"{len(attempts)}/{protocol['max_evaluations']} {case['id']} {method}",flush=True)
            except Exception as exc:
                attempt.update(status='failed',error=str(exc)); raise
            finally:
                write(out/'attempts.json',attempts)
        pairs.append({'case':case['id'],'group':case['group'],'seed':case['spec']['seed'],
                      'anomaly_segments':records['tour']['metrics']['anomaly_segments'],
                      'fifo_minus_tour':paired(records['fifo'],records['tour']),
                      'fifo_minus_shuffled':paired(records['fifo'],records['shuffled'])})
        write(out/'pairs.json',pairs); write(out/'rows.json',rows)
    if any((Path(__file__).parent/name).read_bytes()!=data for name,data in sources.items()) or path.read_bytes()!=(out/'protocol.json').read_bytes():
        raise RuntimeError('Code or protocol changed during evaluation')
    with (out/'results.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(rows[0])); writer.writeheader()
        writer.writerows(dict(r,event_outcomes=json.dumps(r['event_outcomes'],sort_keys=True)) for r in rows)
    summary = summarize(protocol,rows,pairs)
    summary.update(total_attempts=len(attempts),failed_attempts=sum(a['status']=='failed' for a in attempts),
                   reused_successful_records=len(inherited),new_successful_evaluations=len(rows)-len(inherited))
    write(out/'summary.json',summary)
    return summary
