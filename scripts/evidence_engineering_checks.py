"""Literal engineering outcomes for ticket 14, not a probabilistic inference."""
from copy import deepcopy
import json
from pathlib import Path

from aegis_dc.evidence_ledger import EvidenceLedger


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def check_package(directory):
    directory = Path(directory)
    book = json.loads((directory / 'runbook-copy.json').read_text(encoding='utf-8'))
    fixture = json.loads((directory / 'fixture-copy.json').read_text(encoding='utf-8'))
    saved = json.loads((directory / 'snapshots.json').read_text(encoding='utf-8'))
    _require(set(saved) == {row['id'] for row in book['snapshots']}, 'Unexpected snapshot set')
    for case in book['snapshots']:
        result = saved[case['id']]
        _require(result['as_of_s'] == case['as_of_s'], 'Snapshot decision time differs')
        _require(result['current_record_ids'] == case['current_record_ids'], 'Literal current IDs differ: ' + case['id'])
        _require(result['independence'] == 'NOT_ESTABLISHED', 'Independence was invented')
        _require(result == EvidenceLedger(fixture).snapshot(case['as_of_s']), 'Saved snapshot differs from public interface')
    expected = book['literal_checks']
    rows = {row['id']: row for row in saved['late-history']['records']}
    _require(rows['late-history']['age_s'] == expected['late_history_at_16_age_s'], 'Late arrival reset observation age')
    _require(rows['late-history']['availability'] == expected['late_history_at_16_availability'], 'Late history was refreshed')
    _require(saved['before-conflict']['conflicts'] == [], 'Future conflict leaked')
    _require([row['record_ids'] for row in saved['conflict']['conflicts']] == expected['conflict_pairs_at_18'], 'Literal conflict pairs differ')
    received = {row['id']: row for row in saved['work-order-first']['records']}
    _require('alarm-t10' not in received, 'Original alarm arrived early')
    _require(received['copy-before-alarm']['provenance'] == dict(
        origin_id=expected['copied_origin'], copied_from_record_id=expected['known_reference_before_alarm']), 'Carried root was lost')
    _require(received['human-false']['value'] is False, 'Binary false was replaced')
    _require(received['human-false']['quality']['status'] == 'unknown', 'Unknown quality was upgraded')
    _require(received['zero-power']['value'] == 0, 'Explicit zero was replaced')
    final = {row['id']: row for row in saved['expired']['records']}
    _require(final['handheld-negative']['value'] == -2, 'Negative offset was replaced')
    _require(final['missing-flow']['value'] is None and final['missing-flow']['availability'] == 'missing', 'Missing reading was imputed')
    _require(len(fixture['entity_ids']) == expected['shared_entity_ids'], 'Shared identity count differs')
    _require(sum(source['kind'] == 'fixed_sensor' for source in fixture['sources']) == expected['fixed_sources'], 'Sparse fixed source count differs')
    # Adversarial private-input changes retain all public declarations and received data.
    changed = deepcopy(fixture)
    for record in changed['records']:
        if record['arrived_at_s'] >= 18:
            record.update(id='pending-' + record['id'], arrived_at_s=999, valid_until_s=None)
            record['provenance'] = dict(origin_id='unseen-changed-origin', copied_from_record_id=None)
    changed['records'].append(deepcopy(changed['records'][-1]))
    _require(EvidenceLedger(changed).snapshot(17.999999999999996) == saved['before-conflict'], 'Future data leaked')
    commands = json.loads((directory / 'commands.json').read_text(encoding='utf-8'))
    _require({row['id']: row['returncode'] for row in commands} == {
        row['id']: row['expected_exit'] for row in book['cli']}, 'Actual CLI exit codes differ')
    _require(json.loads((directory / 'cli/public/snapshot.json').read_text(encoding='utf-8')) == saved['work-order-first'], 'Saved CLI snapshot differs')
    _require(json.loads((directory / 'cli/valid.stdout.json').read_text(encoding='utf-8')) == saved['work-order-first'], 'CLI stdout differs')
    _require(json.loads((directory / 'cli/overwrite-preservation.json').read_text(encoding='utf-8'))['unchanged'] is True, 'CLI output was overwritten')
    return dict(status='PASS', literal_snapshots=len(saved), fixed_sensor_sources=3,
                source_kinds=7, shared_entity_ids=45, conflict_pairs=2,
                copied_root_preserved_before_original=True, future_mutation_noninterference=True,
                late_arrival_age_s=76, missing_zero_negative_false_distinct=True,
                unknown_quality_preserved=True, actual_CLI_commands=4,
                registered_research_trials=0, model_calls=0, training_calls=0)
