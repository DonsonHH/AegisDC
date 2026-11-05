"""Saved-byte observation diagnostics; no sensor producer or plant imports."""
from copy import deepcopy
import json
import math

from aegis_dc.evidence_ledger import EvidenceLedger


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(primary, mismatch, profile, snapshots, book):
    left, right = primary['ledger'], mismatch['ledger']
    require(len(left['entity_ids']) == 45 and left['facility_id'] == profile['ledger']['facility_id'], 'Complete V6 identity differs')
    require(len(left['records']) == book['expected_record_count'] == len(right['records']), 'Declared polling coverage differs')
    require(primary['public_model'] == mismatch['public_model'], 'Private calibration changed the public model')
    require(primary['public_model']['ledger']['records'] == [], 'Public model contains queued observations')
    encoded = json.dumps(dict(public_model=primary['public_model'], snapshots=snapshots), sort_keys=True)
    for hidden in ('private_signal', 'private_bias', 'private_realization', 'private_noise_bucket',
                   'private_input_identity', 'original_code_identity', 'fault_case', 'seed'):
        require(hidden not in encoded, 'Private evaluator metadata entered the public projection: ' + hidden)
    require({row['target_id'] for row in left['records']} == set(book['expected_targets']), 'An uncovered target was read')
    require(len(primary['private_audit']) == book['expected_poll_count'], 'Declared actual polling count differs')
    a, b = primary['private_audit'], mismatch['private_audit']
    require([(r['measurement_id'], r['poll_index'], r['source_observed_at_s'], r['private_signal'],
              r['private_noise_bucket'], r['private_reading_dropout']) for r in a]
            == [(r['measurement_id'], r['poll_index'], r['source_observed_at_s'], r['private_signal'],
                 r['private_noise_bucket'], r['private_reading_dropout']) for r in b], 'Private bias changed external signal/noise/availability')
    require(not any(row['declared_bound_violated'] for row in a), 'Nominal case violated a declared model bound')
    require(any(row['declared_bound_violated'] for row in b), 'Registered mismatch did not expose a private bound violation')
    rows = {row['id']: row for row in left['records']}
    other = {row['id']: row for row in right['records']}
    for identifier, row in rows.items():
        mate = other[identifier]
        require(row['quality'] == mate['quality'] and row['provenance'] == mate['provenance'], 'Actual error relabeled public quality/provenance')
        require((row['value'] is None) == (mate['value'] is None), 'Bias mismatch changed the missing-data mechanism')
        if row['value'] is None:
            require(row['quality']['status'] == 'unknown' and row['quality']['error_bound'] is None, 'Missing value invented quality')
    for index in book['invalid_controller_sample_indices']:
        temperature = rows['controller-temperature-transfer:' + str(index)]
        validity = rows['controller-validity-transfer:' + str(index)]
        require(temperature['value'] is None and validity['value'] is False, 'Reported invalid control sample became actual temperature or numeric zero')
        require(temperature['observed_at_s'] == index and temperature['arrived_at_s'] == index + .5,
                'Reported control sampling/delivery epoch differs')
        require(temperature['provenance'] == validity['provenance'], 'Control fields lost their common report root')
    require(rows['controller-validity-transfer:175']['value'] is True
            and rows['controller-validity-transfer:180']['value'] is True, 'Control validity transition changed')
    audit = {(row['measurement_id'], row['poll_index']): row for row in a}
    require(audit['rectifier-meter', 14]['private_signal'] == 0, 'The saved outage has no literal zero rectifier input at 70 s')
    require(audit['lake-flow', 16]['private_signal'] < audit['lake-flow', 15]['private_signal'], 'The saved filter change did not alter the sampled flow')
    earliest = EvidenceLedger(left).snapshot(math.nextafter(.5, -math.inf))
    require(earliest['records'] == [], 'A one-ULP future first delivery became visible')
    require(EvidenceLedger(left).snapshot(.5)['current_record_ids'] == book['first_current_record_ids'], 'First actual delivery differs from literal expectation')
    for identifier, instant in book['snapshots'].items():
        require(snapshots[identifier] == EvidenceLedger(left).snapshot(instant), 'Saved as-of snapshot differs')
    changed = deepcopy(left)
    for row in changed['records']:
        if row['arrived_at_s'] > 2:
            row['value'] = None
            row['quality'] = dict(status='unknown', error_bound=None, note='Changed private future payload.')
    require(EvidenceLedger(changed).snapshot(2) == EvidenceLedger(left).snapshot(2), 'Private future payload changed the earlier whole snapshot')
    require(any(row['value'] is None for row in left['records']), 'No actual missing readings were produced')
    return dict(status='PASS', same_V6_entity_ids=45, produced_records=len(rows), measurement_polls=len(a),
                configured_targets=book['expected_targets'], original_private_signal_dynamic=True,
                actual_zero_preserved_in_private_reference=True, missing_not_zero=True,
                reported_controller_invalid_samples=len(book['invalid_controller_sample_indices']),
                public_model_and_quality_independent_of_realized_bias=True,
                shared_noise_and_availability_replayed=True, one_ULP_future_hidden=True,
                private_future_payload_noninterference=True, snapshots=len(snapshots),
                public_static_model_and_snapshots_exclude_private_metadata=True,
                registered_research_trials=0, model_calls=0, training_calls=0)
