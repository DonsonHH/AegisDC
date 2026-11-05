"""Exercise ticket 18 at the public seam with frozen engineering inputs."""
from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
from itertools import product
import json
from pathlib import Path

from aegis_dc.belief import infer_belief
from aegis_dc.decision_view import DecisionGateway
from aegis_dc.evidence_ledger import RECORD_FIELDS
from belief_engineering_oracle import build_oracle


PROTOCOL = 'docs/mainline/18-belief-engineering-protocol.json'
PROTOCOL_PATH_ROLES = ('reference_model', 'finite_generator', 'calibration_oracle',
                       'archived_public_snapshots', 'public_nominal', 'public_plan',
                       'common_registry', 'fixed_profile', 'nonfixed_profile')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')


def read(path):
    return json.loads(Path(path).read_bytes())


def write(path, value):
    with path.open('xb') as stream:
        stream.write(encoded(value))


def _registry_union(ledger, registries):
    for registry in registries:
        require(set(ledger['entity_ids']) == set(registry['entity_ids']), 'Registry entity identity differs')
        for field in ('sources', 'observables'):
            indexed = {row['id']: row for row in ledger[field]}
            for row in registry[field]:
                if row['id'] in indexed:
                    require(indexed[row['id']] == row, 'Static channel declarations disagree: ' + row['id'])
                else:
                    ledger[field].append(row)
    return ledger


def _record(identifier, source, target, observable, unit, value, observed, arrived,
            *, origin=None, copy=None, bound=None):
    return dict(id=identifier, source_id=source, target_id=target, observable_id=observable,
                unit=unit, value=value, observed_at_s=observed, arrived_at_s=arrived,
                valid_until_s=20,
                quality=dict(status='bounded' if bound is not None else 'reported', error_bound=bound,
                             note='Frozen exact finite generator report with declared engineering quality.'),
                provenance=dict(origin_id=origin or identifier, copied_from_record_id=copy))


def _finite_inputs(hot, low_power):
    return [
        _record('hot-root', 'coolant-alarm-packet', 'immersion', 'coolant_hot_reported',
                '1', hot, 1, 11),
        _record('hot-carried-copy', 'coolant-alarm-packet', 'immersion', 'coolant_hot_reported',
                '1', hot, 1, 10, origin='hot-root', copy='hot-root'),
        _record('rectifier-root', 'rectifier-meter-record', 'rectifier', 'rectifier_input_power',
                'W', 0 if low_power else 2268000, 10, 12, bound=0),
    ]


def _calibrate(model, nominal, ledger, plan, oracle, protocol):
    plan = dict(plan, id='V6-belief-finite-generator-plan', decision_times_s=protocol['calibration_as_of_s'])
    label_order = ('no-reports', 'arrived-hot-only', 'both-arrived')
    found = {label: {} for label in label_order}
    frame_for_cli = None
    for hot, power in product((False, True), repeat=2):
        gateway = DecisionGateway(nominal, dict(ledger, records=_finite_inputs(hot, power)), plan)
        for count, label in enumerate(label_order):
            frame = gateway.next_frame()
            inference = infer_belief(frame, model)
            require(not inference['physical_actions'], 'Inference recorded a physical action')
            pattern = (hot, power)[:count]
            used = ['hot-root', 'rectifier-root'][:count]
            require(inference['information_updates'] == used, 'Incorrect factor availability: ' + label)
            copy = next(row for row in inference['record_audit'] if row['record_id'] == 'hot-carried-copy')
            require(copy['disposition'] == ('copy_not_a_factor' if count else 'copy_root_unavailable'),
                    'The carried copy must never add an independent factor')
            previous = found[label].setdefault(pattern, inference['posterior'])
            require(previous == inference['posterior'], 'A report affected inference before its arrival')
            if count == 2 and hot and power:
                frame_for_cli = frame
    tolerance = protocol['absolute_numeric_tolerance']
    checked, score = [], {}
    for label, partition in oracle['outcome_partitions'].items():
        weighted_brier = 0
        for row in partition['rows']:
            reports = tuple(row['reports'])
            expected = {state: float(Fraction(p)) for state, p in row['exact_frequencies'].items()}
            actual = found[label][reports]
            require(expected.keys() == actual.keys(), 'Inference state identity differs from the generator')
            max_error = max(abs(expected[state] - actual[state]) for state in expected)
            require(max_error <= tolerance, 'Finite conditional frequencies differ')
            for truth, conditional in expected.items():
                weighted_brier += (float(Fraction(row['probability'])) * conditional
                                   * sum((p - (state == truth)) ** 2 for state, p in actual.items()))
            checked.append(dict(stage=label, reports=list(reports), exact_probability=row['probability'],
                                exact_frequencies=row['exact_frequencies'], inference=actual,
                                max_absolute_error=max_error))
        expected_brier = partition['weighted_multiclass_brier_decimal']
        require(abs(weighted_brier - expected_brier) <= tolerance, 'True-law Brier score differs')
        score[label] = dict(inference=weighted_brier, exact=partition['weighted_multiclass_brier'])
    require(len(checked) == protocol['expected_calibration_rows'], 'Calibration partition incomplete')
    return dict(classification='EXACT_SYNTHETIC_GENERATOR_ONLY', atom_count=oracle['atoms'],
                normalization=oracle['exact_total_probability'], pattern_rows=checked,
                true_law_weighted_multiclass_brier=score, deliberately_wrong_comparators=oracle['negative_comparators'],
                tolerance=tolerance, max_absolute_error=max(row['max_absolute_error'] for row in checked)), frame_for_cli


def _archive(model, nominal, archived_ledger, plan, protocol):
    plan = dict(plan, id='V6-belief-archived-observation-plan', decision_times_s=protocol['archived_as_of_s'])
    expectation = {row['as_of_s']: row['rectifier_record'] for row in protocol['archived_arrival_expectations']}
    gateway = DecisionGateway(nominal, archived_ledger, plan)
    trajectory, seen = [], set()
    for time in plan['decision_times_s']:
        frame = gateway.next_frame()
        visible = {row['id']: row for row in frame['evidence']['records']}
        expected = {row['id'] for row in archived_ledger['records']
                    if row['arrived_at_s'] <= time and row['observed_at_s'] <= time}
        require(visible.keys() == expected, 'Archived observation gate differs')
        result = infer_belief(frame, model)
        require(not result['physical_actions'], 'Inference recorded a physical action')
        used = [dict(row, observed_value=visible[row['record_id']]['value']) for row in result['record_audit']
                if row['disposition'] == 'used']
        if time in expectation:
            power = next(row for row in used if row['channel_id'] == 'fixed-low-power')
            require(power['record_id'] == expectation[time], 'Incorrect archived rectifier representative at arrival gate')
            seen.add(time)
        trajectory.append(dict(as_of_s=time, arrived_count=len(visible), status=result['status'],
                               frame_sha256=sha256(encoded(frame)).hexdigest(), used=used,
                               posterior=result['posterior'], posterior_by_variant=result['posterior_by_variant'],
                               assumption_envelope=result['assumption_envelope']))
    require(seen == expectation.keys(), 'An archived arrival gate was not checked')
    return dict(classification='ARCHIVED_PUBLIC_V6_ENGINEERING', scope_id=model['scope']['id'],
                facility_id=model['facility_id'], domains=nominal['domain_ids'],
                input_record_count=len(archived_ledger['records']), frames=trajectory,
                arrival_expectations=protocol['archived_arrival_expectations'])


def exercise(root, protocol):
    load = lambda role: read(root / protocol[role])
    model, nominal, plan = (load(role) for role in ('reference_model', 'public_nominal', 'public_plan'))
    registries = [load('common_registry'), load('nonfixed_profile')['registry']]
    oracle = build_oracle((root / protocol['finite_generator']).read_bytes())
    require(oracle == load('calibration_oracle'), 'Independent oracle changed after generation')
    finite_ledger = _registry_union(load('fixed_profile')['ledger'], registries)
    finite_ledger['id'] = model['scope']['ledger_id']
    calibration, frame = _calibrate(model, nominal, finite_ledger, plan, oracle, protocol)

    # This archived object contains public records only. It is upstream of
    # DecisionGateway and is never an input to infer_belief.
    archived = load('archived_public_snapshots')[protocol['archived_snapshot_key']]
    archival_model = deepcopy(model)
    archival_model['scope'].update(protocol['archive_scope'])
    archival_ledger = _registry_union(dict(archived['static_knowledge'],
        schema='aegisdc-evidence-ledger-v1', id=archival_model['scope']['ledger_id'],
        facility_id=archived['facility_id'], basis='synthetic_assumption', time_unit='s',
        records=[{key: row[key] for key in RECORD_FIELDS} for row in archived['records']]), registries)
    require(len(archival_ledger['records']) == protocol['original_archive_record_count'],
            'Archived public input record count changed')
    trajectory = _archive(archival_model, nominal, archival_ledger, plan, protocol)
    return calibration, trajectory, archival_model, frame
