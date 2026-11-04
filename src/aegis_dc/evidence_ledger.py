"""Decision-time evidence records; no plant state or inference dependencies."""
from copy import deepcopy
from fractions import Fraction
from itertools import combinations
import math
from pathlib import Path

from patrol_rsi.contracts import strict_json
from .scenario import SI_UNITS, SOURCE_CLASSES

SOURCE_KINDS = {'asset_record', 'maintenance_history', 'fixed_sensor', 'control_record',
                'human_report', 'work_order', 'handheld'}
DOCUMENT_FIELDS = {'schema', 'id', 'facility_id', 'basis', 'time_unit', 'entity_ids',
                   'observables', 'sources', 'records'}
RECORD_FIELDS = {'id', 'source_id', 'target_id', 'observable_id', 'unit', 'value',
                 'observed_at_s', 'arrived_at_s', 'valid_until_s', 'quality', 'provenance'}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _finite(value, label):
    valid = type(value) in (int, float)
    if valid:
        try:
            valid = math.isfinite(value)
        except OverflowError:
            valid = False
    _require(valid, label + ' must be a finite numeric value, not boolean or missing')


def _derived_number(exact, label):
    try:
        result = exact.numerator if exact.denominator == 1 else float(exact)
    except OverflowError as error:
        raise ValueError(label + ' exceeds the finite numeric output domain') from error
    _finite(result, label)
    return result


def _plain_json(value, ancestors=None, depth=0):
    """Reject executable/custom objects before any copy or serialization hook."""
    _require(depth < 64, 'Evidence must be shallow plain JSON, without cycles')
    if value is None or type(value) in (str, bool):
        return
    if type(value) in (int, float):
        _finite(value, 'JSON number')
        return
    _require(type(value) in (dict, list), 'Evidence accepts plain JSON only, not Python objects or callbacks')
    ancestors = set() if ancestors is None else ancestors
    _require(id(value) not in ancestors, 'Evidence cannot contain a reference cycle')
    ancestors.add(id(value))
    if type(value) is dict:
        _require(all(type(key) is str for key in value), 'JSON keys must be text')
        children = value.values()
    else:
        children = value
    for child in children:
        _plain_json(child, ancestors, depth + 1)
    ancestors.remove(id(value))


def _fields(value, expected, label):
    _require(type(value) is dict and set(value) == expected, label + ' fields do not match the closed contract')


def _text(value, label):
    _require(type(value) is str and bool(value.strip()), label + ' must be nonempty text')


def _strings(value, label):
    _require(type(value) is list and bool(value), label + ' must be a nonempty list')
    for item in value:
        _text(item, label)
    _require(len(value) == len(set(value)), 'Duplicate ' + label)


def _registry(rows, label):
    _require(type(rows) is list, label + ' must be a list')
    result = {}
    for row in rows:
        _require(type(row) is dict, label + ' entries must be objects')
        identifier = row.get('id')
        _text(identifier, label + ' id')
        _require(identifier not in result, 'Duplicate ' + label + ' id')
        result[identifier] = row
    return result


def _record(record, sources, observables):
    _fields(record, RECORD_FIELDS, 'record')
    for name in ('id', 'source_id', 'target_id', 'observable_id', 'unit'):
        _text(record[name], name)
    _require(record['source_id'] in sources, 'Unknown evidence source')
    source = sources[record['source_id']]
    _require(record['target_id'] in source['target_ids'], 'Target is outside declared source coverage')
    _require(record['observable_id'] in source['observable_ids'], 'Observable is outside declared source coverage')
    observable = observables[record['observable_id']]
    _require(record['unit'] == observable['unit'], 'Record unit disagrees with declared SI observable')
    for name in ('observed_at_s', 'arrived_at_s'):
        _finite(record[name], name)
    _require(record['observed_at_s'] <= record['arrived_at_s'], 'Observation cannot follow its arrival')
    if record['valid_until_s'] is not None:
        _finite(record['valid_until_s'], 'valid_until_s')
        _require(record['valid_until_s'] > record['observed_at_s'], 'Validity interval must end after observation')
    value = record['value']
    value_type = observable['value_type']
    if value is not None:
        if value_type == 'number':
            _finite(value, 'Observed value')
        elif value_type == 'boolean':
            _require(type(value) is bool, 'Binary observations require JSON true/false, not numeric substitutes')
        else:
            _text(value, 'Observed category')
    quality = record['quality']
    _fields(quality, {'status', 'error_bound', 'note'}, 'quality')
    _text(quality['note'], 'Quality note')
    status = quality['status']
    _text(status, 'Quality status')
    _require(status in {'unknown', 'bounded', 'reported'}, 'Unknown quality status')
    if value is None:
        _require(status == 'unknown', 'Missing values cannot have established quality')
    if status == 'bounded':
        _require(value_type == 'number' and value is not None, 'Only present numbers have absolute error bounds')
        error = quality['error_bound']
        _finite(error, 'Absolute error bound')
        _require(error >= 0, 'Absolute error bound must be nonnegative')
        exact_value, exact_error = Fraction(value), Fraction(error)
        _derived_number(exact_value - exact_error, 'Lower declared bound')
        _derived_number(exact_value + exact_error, 'Upper declared bound')
    else:
        _require(quality['error_bound'] is None, 'Unbounded quality must not invent an error bound')
        _require(status != 'reported' or value_type != 'number', 'Numbers need bounded or explicitly unknown quality')
    provenance = record['provenance']
    _fields(provenance, {'origin_id', 'copied_from_record_id'}, 'provenance')
    _text(provenance['origin_id'], 'Reported origin token')
    if provenance['copied_from_record_id'] is not None:
        _text(provenance['copied_from_record_id'], 'Carried copy reference')
        _require(provenance['copied_from_record_id'] != record['id'], 'A record cannot copy itself')


def validate_ledger(document):
    """Validate and detach a closed ledger; identical IDs are idempotent."""
    _plain_json(document)
    _fields(document, DOCUMENT_FIELDS, 'ledger')
    _require(document['schema'] == 'aegisdc-evidence-ledger-v1', 'Unknown evidence ledger schema')
    _require(document['basis'] == 'synthetic_assumption', 'Declare the synthetic facility basis')
    _require(document['time_unit'] == 's', 'Evidence time uses SI seconds')
    _text(document['id'], 'Ledger id')
    _text(document['facility_id'], 'Facility id')
    _strings(document['entity_ids'], 'Declared entity ids')
    observables = _registry(document['observables'], 'observable')
    _require(bool(observables), 'Declare at least one observable')
    for row in observables.values():
        _fields(row, {'id', 'quantity', 'value_type', 'unit'}, 'observable')
        for name in ('quantity', 'value_type', 'unit'):
            _text(row[name], 'Observable ' + name)
        value_type = row['value_type']
        _require(value_type in {'number', 'boolean', 'text'}, 'Unsupported observable value type')
        units = SI_UNITS if value_type == 'number' else {'binary': '1'} if value_type == 'boolean' else {'category': '1'}
        _require(row['quantity'] in units and row['unit'] == units[row['quantity']], 'Observable quantity requires its declared SI unit')
    sources = _registry(document['sources'], 'source')
    for row in sources.values():
        _fields(row, {'id', 'kind', 'basis', 'target_ids', 'observable_ids', 'dependency_group', 'source_note'}, 'source')
        _text(row['kind'], 'Source kind')
        _text(row['basis'], 'Source basis')
        _require(row['kind'] in SOURCE_KINDS, 'Unknown evidence source kind')
        _require(row['basis'] in SOURCE_CLASSES, 'Declare source basis separately from source kind')
        _text(row['source_note'], 'Source note')
        _strings(row['target_ids'], 'Source target ids')
        _strings(row['observable_ids'], 'Source observable ids')
        _require(set(row['target_ids']) <= set(document['entity_ids']), 'Unknown source target')
        _require(set(row['observable_ids']) <= set(observables), 'Unknown source observable')
        if row['dependency_group'] is not None:
            _text(row['dependency_group'], 'Declared dependency group')
    _require(type(document['records']) is list, 'Records must be a list')
    records = {}
    for row in document['records']:
        _record(row, sources, observables)
        if row['id'] in records:
            _require(records[row['id']] == row, 'Conflicting duplicate record id: ' + row['id'])
        else:
            records[row['id']] = row
    result = deepcopy(document)
    result['records'] = deepcopy(list(records.values()))
    return result


def _conflicts(rows):
    result = []
    for left, right in combinations(sorted(rows, key=lambda row: row['id']), 2):
        keys = ('target_id', 'observable_id', 'observed_at_s')
        if any(left[key] != right[key] for key in keys) or left['value'] is None or right['value'] is None:
            continue
        if left['quality']['status'] == right['quality']['status'] == 'bounded':
            # Exact rational arithmetic on the validated decoded int/binary64
            # values prevents endpoint rounding from erasing a positive gap.
            a, b = Fraction(left['value']), Fraction(right['value'])
            ea, eb = Fraction(left['quality']['error_bound']), Fraction(right['quality']['error_bound'])
            if not (a + ea < b - eb or b + eb < a - ea):
                continue
            kind = 'disjoint_declared_bounds'
        elif left['value'] != right['value']:
            kind = 'different_reported_values'
        else:
            continue
        result.append(dict(record_ids=[left['id'], right['id']], kind=kind,
                           **{key: left[key] for key in keys}))
    return result


def _copy_relations(rows):
    """Audit only received copy claims, without resolving private references."""
    visible = {row['id']: row for row in rows}
    references, links, mismatches, cycles = {}, set(), set(), set()
    for row in rows:
        parent = row['provenance']['copied_from_record_id']
        if parent is None:
            continue
        references.setdefault(parent, []).append(row['id'])
        if parent in visible:
            pair = tuple(sorted((row['id'], parent)))
            links.add(pair)
            if row['provenance']['origin_id'] != visible[parent]['provenance']['origin_id']:
                mismatches.add(pair)
    for start in sorted(visible):
        path, positions, cursor = [], {}, start
        while cursor in visible:
            if cursor in positions:
                cycles.add(tuple(sorted(path[positions[cursor]:])))
                break
            positions[cursor] = len(path)
            path.append(cursor)
            cursor = visible[cursor]['provenance']['copied_from_record_id']
    groups = [dict(kind='reported_copy_reference', copied_from_record_id=reference,
                   record_ids=sorted(identifiers))
              for reference, identifiers in sorted(references.items()) if len(identifiers) > 1]
    groups += [dict(kind='visible_copy_link', record_ids=list(pair)) for pair in sorted(links)]
    issues = [dict(kind='copy_origin_mismatch', record_ids=list(pair)) for pair in sorted(mismatches)]
    issues += [dict(kind='visible_copy_cycle', record_ids=list(cycle)) for cycle in sorted(cycles)]
    return groups, issues


class EvidenceLedger:
    """Own evidence inputs and expose detached explicit-time snapshots."""

    def __init__(self, document):
        self._document = validate_ledger(document)

    def ingest(self, record):
        """Atomically add one record; duplicate content does not add a sample."""
        _plain_json(record)
        candidate = deepcopy(self._document)
        candidate['records'].append(record)
        validated = validate_ledger(candidate)
        added = len(validated['records']) > len(self._document['records'])
        if added:
            self._document = validated
        return 'ADDED' if added else 'ALREADY_PRESENT'

    def snapshot(self, as_of_s):
        _finite(as_of_s, 'as_of_s')
        rows = []
        for record in self._document['records']:
            if record['arrived_at_s'] > as_of_s or record['observed_at_s'] > as_of_s:
                continue
            row = deepcopy(record)
            row['age_s'] = _derived_number(Fraction(as_of_s) - Fraction(record['observed_at_s']), 'Evidence age')
            row['availability'] = ('missing' if record['value'] is None else
                                   'expired' if record['valid_until_s'] is not None
                                   and as_of_s >= record['valid_until_s'] else 'current')
            rows.append(row)
        rows.sort(key=lambda row: (row['arrived_at_s'], row['id']))
        origins = {}
        for row in rows:
            origins.setdefault(row['provenance']['origin_id'], []).append(row['id'])
        correlations = [dict(kind='reported_origin', origin_id=origin, record_ids=sorted(identifiers))
                        for origin, identifiers in sorted(origins.items()) if len(identifiers) > 1]
        sources = {source['id']: source for source in self._document['sources']}
        dependencies = {}
        for row in rows:
            dependency = sources[row['source_id']]['dependency_group']
            if dependency is not None:
                dependencies.setdefault(dependency, []).append(row['id'])
        correlations += [dict(kind='declared_source_dependency', dependency_group=group,
                              record_ids=sorted(identifiers))
                         for group, identifiers in sorted(dependencies.items()) if len(identifiers) > 1]
        copy_groups, provenance_issues = _copy_relations(rows)
        correlations += copy_groups
        static = {name: deepcopy(self._document[name]) for name in ('entity_ids', 'observables', 'sources')}
        return dict(schema='aegisdc-evidence-snapshot-v1', ledger_id=self._document['id'],
                    facility_id=self._document['facility_id'], time_unit='s', as_of_s=as_of_s,
                    static_knowledge=static, records=rows, correlation_groups=correlations,
                    provenance_issues=provenance_issues,
                    independence='NOT_ESTABLISHED', conflicts=_conflicts(rows),
                    current_record_ids=[row['id'] for row in rows if row['availability'] == 'current'])


def load_ledger(path):
    """Load strict JSON without accessing a plant, replay, or current scenario."""
    return EvidenceLedger(strict_json(Path(path).read_text(encoding='utf-8')))
