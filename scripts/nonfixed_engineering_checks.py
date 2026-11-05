"""Independently stated ticket17 fixture outcomes; no posterior or policy gain."""
import json
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_package(directory):
    directory = Path(directory)
    read = lambda name: json.loads((directory/name).read_text(encoding='utf-8'))
    book, saved = read('runbook-copy.json'), read('snapshots.json')
    require(set(saved)=={case['id'] for case in book['snapshots']}, 'Snapshot set differs')
    for case in book['snapshots']:
        snap = saved[case['id']]
        require(snap['as_of_s']==case['as_of_s'], 'Decision time differs')
        require(snap['current_record_ids']==case['current_record_ids'], 'Literal current records differ: '+case['id'])
        require(snap['independence']=='NOT_ESTABLISHED', 'A source kind established independence')
    late = {r['id']:r for r in saved['late-history']['records']}['late-history']
    require(late['age_s']==30 and late['availability']=='expired' and late['value'] is False, 'History was refreshed or negative lost')
    first = saved['copy-first']
    records = {r['id']:r for r in first['records']}
    require('alarm-later' not in records, 'Future alarm leaked')
    require(records['copy-first']['provenance']==dict(origin_id='carried-shared-alarm-root', copied_from_record_id='alarm-later'), 'Missing parent changed carried provenance')
    require(first['provenance_issues']==[], 'A future parent generated a private issue')
    require(records['manual-negative']['value'] is False and records['manual-unknown']['value'] is None, 'False/null distinction lost')
    require(records['asset-zero']['value']==0 and records['asset-zero']['quality']['error_bound']==0, 'Explicit zero lost')
    require('completed-numeric' not in {r['id'] for r in saved['before-arrival']['records']}, 'Positive latency bypassed')
    after = saved['arrived']; rows = {r['id']:r for r in after['records']}
    numeric = rows['completed-numeric']; literal = book['literal_checks']
    require(numeric['value']==literal['completion_temperature_K'], 'Completion sample differs from frozen literal')
    require(numeric['observed_at_s']==97.5 and numeric['arrived_at_s']==98 and numeric['age_s']==.5, 'Completion/arrival coordinates differ')
    require(numeric['value'] not in [literal['start_temperature_K'],literal['arrival_temperature_K']], 'Start/delivery state was substituted')
    require(rows['detector-miss']['value'] is False and rows['detector-false-alarm']['value'] is True, 'Declared endpoint detector result differs')
    require(rows['detector-miss']['quality']==rows['detector-false-alarm']['quality'], 'Private detector correctness changed public quality')
    require(rows['detector-miss']['provenance']==rows['detector-false-alarm']['provenance'], 'Correlated session origin changed')
    require(rows['completed-indeterminate']['value'] is None and rows['completed-indeterminate']['availability']=='missing', 'Indeterminate inspection was imputed')
    require(not any(key.startswith('no-result-') for key in rows), 'Unqualified/uncovered/incomplete status produced evidence')
    require(any(g['kind']=='reported_origin' and g['record_ids']==['alarm-later','copy-first'] for g in after['correlation_groups']), 'Copy/root correlation was lost')
    audit = read('private-audit.json')['events']
    measurements = [a for a in audit if a['event_id']=='completed-numeric']
    require(len(measurements)==2, 'Recorded session query trace differs')
    for sample in measurements:
        require(sample['raw_planned_completed_at_s']==literal['raw_planned_completion_s'] and
            sample['effective_completed_at_s']==97.5 and sample['source_sample_at_s']==97.5, 'Planned/effective/source coordinates collapsed')
        require(sample['private_source']['code_identity']['git_commit']==book['saved_run_interpretation']['physical_source_commit'], 'Historical physical execution source differs')
    witness = read('private-source-witness.json')
    require(witness['actual_samples']==[dict(time_s=t,temperature_K=literal[k]) for t,k in [(65.5,'start_temperature_K'),(97.5,'completion_temperature_K'),(98,'arrival_temperature_K')]], 'Saved-point witness differs')
    require(witness['new_physics_execution'] is False and witness['historical_maximum_step_s']==1.0, 'Historical1s source misclassified as new physical qualification')
    models = read('public-models.json')
    require(models['independence']=='NOT_ESTABLISHED', 'Models established independence')
    for forbidden in ['private_source','private_draw','authorized_raw_signal','private_realization','run_sha256','source_tree_sha256']:
        require(forbidden not in json.dumps(saved)+json.dumps(models), 'Private material entered public output: '+forbidden)
    commands=read('commands.json')
    require({r['id']:r['returncode'] for r in commands}=={r['id']:r['expected_exit'] for r in book['CLI']}, 'CLI exits differ')
    require(read('cli/arrived/public-snapshot.json')==after and read('cli/arrived.stdout.json')==after, 'CLI/public interface differs')
    require(read('cli/before-arrival/public-snapshot.json')==saved['before-arrival'], 'CLI arrival gate differs')
    no_fixed=read('cli/no-fixed/public-snapshot.json')
    require(not any(s['kind'] in {'fixed_sensor','control_record'} for s in no_fixed['static_knowledge']['sources']), 'No-fixed fixture retained upstream sources')
    require('completed-numeric' in no_fixed['current_record_ids'] and 'copy-first' in no_fixed['current_record_ids'], 'Nonfixed path depends on a fixed source')
    require(read('cli/overwrite-preservation.json')['unchanged'] is True, 'CLI overwrote previous output')
    require(read('private-noninterference.json')['same_public_before_and_after_authorized_observation'] is True, 'Hidden-state pair interfered')
    return dict(status='PASS', literal_snapshots=len(saved), actual_CLI_commands=len(commands),
        source_time_quality_provenance_preserved=True, missing_zero_false_distinct=True,
        completion_and_arrival_gates=True, declared_detection_endpoints=True,
        correlated_root_preserved_before_original=True, sparse_fixed_sources_present=True,
        nonfixed_without_fixed_path=True, hidden_state_noninterference=True,
        exact_saved_point_no_interpolation=True, professional_execution_connected=False,
        new_physics_execution=False, registered_research_trials=0, model_calls=0, training_calls=0)
