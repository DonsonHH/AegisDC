"""Current public decision inputs; backend handles never enter the frame."""
from copy import deepcopy

from .evidence_ledger import EvidenceLedger, RECORD_FIELDS, _plain_json, validate_ledger
from .scenario import DOMAINS, ENTITY_KINDS, RELATIONS

NOMINAL_FIELDS = {'schema', 'id', 'facility_id', 'basis', 'source_note',
                  'domain_ids', 'entities', 'qualification_ids', 'work_interfaces',
                  'graphs', 'reported_constraints'}
PLAN_FIELDS = {'schema', 'id', 'basis', 'time_unit', 'decision_times_s', 'requests'}
FRAME_FIELDS = {'schema', 'plan_id', 'facility_id', 'time_unit', 'as_of_s',
                'nominal_knowledge', 'evidence', 'requests'}
REQUEST_FIELDS = {'id', 'worker_id', 'work_interface_id', 'target_id'}
ENTITY_FIELDS = {'id', 'kind', 'domain', 'nominal_location_id', 'qualification_ids', 'tool_ids'}
INTERFACE_FIELDS = {'id', 'domain_id', 'target_ids', 'qualification_id', 'tool_ids'}
EDGE_FIELDS = {'id', 'from', 'to', 'kind', 'bidirectional', 'requires_qualification_ids'}
CONSTRAINT_FIELDS = {'id', 'source_id', 'target_id', 'observable_id', 'location_id'}
SNAPSHOT_FIELDS = {'schema', 'ledger_id', 'facility_id', 'time_unit', 'as_of_s',
                   'static_knowledge', 'records', 'correlation_groups', 'provenance_issues',
                   'independence', 'conflicts', 'current_record_ids'}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _fields(document, fields, label):
    _require(type(document) is dict and set(document) == fields,
             label + ' fields do not match the closed contract')


def _text(value, label):
    _require(type(value) is str and bool(value.strip()), label + ' must be nonempty public text')


def _texts(value, label, *, nonempty=False):
    _require(type(value) is list and (bool(value) or not nonempty), label + ' must be a declared list')
    for item in value:
        _text(item, label)
    _require(len(value) == len(set(value)), 'Duplicate ' + label)


def _registry(rows, fields, label):
    _require(type(rows) is list, label + ' must be a list')
    result = {}
    for row in rows:
        _fields(row, fields, label)
        _text(row['id'], label + ' id')
        _require(row['id'] not in result, 'Duplicate ' + label + ' id')
        result[row['id']] = row
    return result


def validate_nominal(document):
    """Detach declared design identities/relations, never current parameters."""
    _plain_json(document)
    _fields(document, NOMINAL_FIELDS, 'Public nominal knowledge')
    _require(document['schema'] == 'aegisdc-public-nominal-v1'
             and document['basis'] == 'synthetic_assumption',
             'Declare the public synthetic nominal knowledge schema')
    for field in ('id', 'facility_id', 'source_note'):
        _text(document[field], 'Public nominal ' + field)
    _texts(document['domain_ids'], 'nominal domains', nonempty=True)
    _require(set(document['domain_ids']) == DOMAINS, 'Declare all eight nominal domains')
    _texts(document['qualification_ids'], 'nominal qualifications')
    qualifications = set(document['qualification_ids'])
    entities = _registry(document['entities'], ENTITY_FIELDS, 'Nominal entity')
    _require(bool(entities), 'Declare nominal entity identities')
    for row in entities.values():
        _text(row['kind'], 'Entity kind')
        _text(row['domain'], 'Entity domain')
        _require(row['kind'] in ENTITY_KINDS and row['domain'] in DOMAINS, 'Unknown nominal entity kind/domain')
        location = row['nominal_location_id']
        if location is not None:
            _text(location, 'Nominal location')
            _require(location in entities and entities[location]['kind'] == 'location', 'Unknown nominal location')
        _texts(row['qualification_ids'], 'entity qualifications')
        _texts(row['tool_ids'], 'entity tool capabilities')
        _require(set(row['qualification_ids']) <= qualifications, 'Unknown nominal qualification')
        _require(all(identifier in entities and entities[identifier]['kind'] == 'tool'
                     for identifier in row['tool_ids']), 'Unknown nominal tool capability')
        _require(row['kind'] == 'worker' or not row['qualification_ids'] and not row['tool_ids'],
                 'Only nominal workers declare personnel qualifications/tool capabilities')
    interfaces = _registry(document['work_interfaces'], INTERFACE_FIELDS, 'Nominal work interface')
    for row in interfaces.values():
        _text(row['domain_id'], 'Work domain')
        _text(row['qualification_id'], 'Work qualification')
        _require(row['domain_id'] in DOMAINS and row['qualification_id'] in qualifications,
                 'Unknown nominal work domain/qualification')
        _texts(row['target_ids'], 'nominal work targets', nonempty=True)
        _texts(row['tool_ids'], 'nominal work tools')
        _require(set(row['target_ids']) <= set(entities), 'Unknown nominal work target')
        _require(all(identifier in entities and entities[identifier]['kind'] == 'tool'
                     for identifier in row['tool_ids']), 'Unknown nominal work tool')
    _fields(document['graphs'], set(RELATIONS), 'Nominal relation graphs')
    edge_ids = set()
    for kind, rows in document['graphs'].items():
        edges = _registry(rows, EDGE_FIELDS, 'Nominal relation')
        for edge in edges.values():
            for name in ('from', 'to', 'kind'):
                _text(edge[name], 'Relation ' + name)
            _require(edge['id'] not in edge_ids, 'Duplicate nominal relation identity across graphs')
            edge_ids.add(edge['id'])
            _require(edge['from'] in entities and edge['to'] in entities and edge['kind'] in RELATIONS[kind],
                     'Unknown nominal relation endpoint/kind')
            _require(type(edge['bidirectional']) is bool, 'Declare nominal relation direction as a boolean')
            _texts(edge['requires_qualification_ids'], 'nominal route qualifications')
            _require(set(edge['requires_qualification_ids']) <= qualifications, 'Unknown nominal route qualification')
            if kind == 'access':
                _require(all(entities[edge[name]]['kind'] == 'location' for name in ('from', 'to')),
                         'Nominal access relations connect locations')
            else:
                _require(not edge['bidirectional'] and not edge['requires_qualification_ids'],
                         'Only access relations declare walking direction/qualification metadata')
    constraints = _registry(document['reported_constraints'], CONSTRAINT_FIELDS, 'Reported constraint')
    for row in constraints.values():
        for name in CONSTRAINT_FIELDS:
            _text(row[name], 'Constraint ' + name)
        _require(row['target_id'] in entities and row['location_id'] in entities
                 and entities[row['location_id']]['kind'] == 'location', 'Unknown declared constraint target/location')
    return deepcopy(document)


def _public_plan(document, knowledge):
    _plain_json(document)
    _fields(document, PLAN_FIELDS, 'Public preparation plan')
    _require(document['schema'] == 'aegisdc-public-preparation-plan-v1'
             and document['basis'] == 'synthetic_assumption' and document['time_unit'] == 's',
             'Declare the public schedule in SI seconds')
    _text(document['id'], 'Public plan id')
    times = document['decision_times_s']
    _require(type(times) is list and bool(times), 'Declare at least one public decision time')
    _require(all(type(time) in (int, float) for time in times), 'Decision times must be finite numbers, not booleans')
    _require(all(first < second for first, second in zip(times, times[1:])),
             'Public decision times must be strictly increasing')
    requests = _registry(document['requests'], REQUEST_FIELDS, 'Public preparation request')
    entities = {row['id'] for row in knowledge['entities']}
    interfaces = {row['id'] for row in knowledge['work_interfaces']}
    for row in requests.values():
        for field in REQUEST_FIELDS:
            _text(row[field], 'Request ' + field)
        _require(row['worker_id'] in entities and row['target_id'] in entities
                 and row['work_interface_id'] in interfaces, 'Unknown nominal request identity')
    return deepcopy(document)


def _binding_registry(knowledge, ledger):
    _require(ledger['facility_id'] == knowledge['facility_id'], 'Evidence and public knowledge facility identities differ')
    _require(set(ledger['entity_ids']) == {row['id'] for row in knowledge['entities']},
             'Evidence must use the same declared nominal entity registry')
    sources = {row['id']: row for row in ledger['sources']}
    observables = {row['id']: row for row in ledger['observables']}
    for constraint in knowledge['reported_constraints']:
        source, observable = sources.get(constraint['source_id']), observables.get(constraint['observable_id'])
        _require(source is not None and observable is not None, 'Unregistered public restriction channel')
        _require(constraint['target_id'] in source['target_ids']
                 and constraint['observable_id'] in source['observable_ids'], 'Restriction channel is outside declared coverage')
        _require(observable['value_type'] == 'boolean' and observable['unit'] == '1',
                 'Restriction channels require a declared binary report')


def _canonical_registry(knowledge, ledger):
    """Normalize public registry presentation, never observations or queue data."""
    result = deepcopy(ledger)
    result['entity_ids'] = [row['id'] for row in knowledge['entities']]
    result['observables'] = sorted(result['observables'], key=lambda row: row['id'])
    result['sources'] = sorted(result['sources'], key=lambda row: row['id'])
    for source in result['sources']:
        source['target_ids'] = sorted(source['target_ids'])
        source['observable_ids'] = sorted(source['observable_ids'])
    return result


def _same_json(expected, actual):
    """JSON-number equivalence without conflating boolean false/true and 0/1."""
    if type(expected) in (int, float):
        return type(actual) in (int, float) and expected == actual
    if type(expected) is dict:
        return type(actual) is dict and set(expected) == set(actual) \
            and all(_same_json(value, actual[key]) for key, value in expected.items())
    if type(expected) is list:
        return type(actual) is list and len(expected) == len(actual) \
            and all(_same_json(first, second) for first, second in zip(expected, actual))
    return type(expected) is type(actual) and expected == actual


def _current_frame(frame):
    _plain_json(frame)
    _fields(frame, FRAME_FIELDS, 'Current decision frame')
    _require(frame['schema'] == 'aegisdc-dispatch-frame-v1' and frame['time_unit'] == 's',
             'Unknown current decision frame schema or unit')
    knowledge = validate_nominal(frame['nominal_knowledge'])
    _require(frame['facility_id'] == knowledge['facility_id'], 'Frame facility differs from public knowledge')
    _public_plan(dict(schema='aegisdc-public-preparation-plan-v1', id=frame['plan_id'],
        basis='synthetic_assumption', time_unit='s', decision_times_s=[frame['as_of_s']],
        requests=frame['requests']), knowledge)
    evidence = frame['evidence']
    _fields(evidence, SNAPSHOT_FIELDS, 'Current evidence snapshot')
    _require(evidence['schema'] == 'aegisdc-evidence-snapshot-v1' and evidence['time_unit'] == 's',
             'Unknown current evidence snapshot schema/unit')
    _require(frame['as_of_s'] == evidence['as_of_s'], 'Evidence clock differs from decision time')
    static = evidence['static_knowledge']
    _fields(static, {'entity_ids', 'observables', 'sources'}, 'Public evidence registry')
    _require(type(evidence['records']) is list, 'Current evidence records must be a list')
    records = []
    for row in evidence['records']:
        _fields(row, RECORD_FIELDS | {'age_s', 'availability'}, 'Current evidence record')
        records.append({name: row[name] for name in RECORD_FIELDS})
    received = validate_ledger(dict(schema='aegisdc-evidence-ledger-v1', id=evidence['ledger_id'],
        facility_id=evidence['facility_id'], basis='synthetic_assumption', time_unit='s',
        entity_ids=static['entity_ids'], observables=static['observables'], sources=static['sources'],
        records=records))
    _binding_registry(knowledge, received)
    received = _canonical_registry(knowledge, received)
    expected = EvidenceLedger(received).snapshot(frame['as_of_s'])
    presented = deepcopy(evidence)
    presented['static_knowledge'] = {name: received[name] for name in ('entity_ids', 'observables', 'sources')}
    _require(_same_json(expected, presented),
             'Evidence is not a consistent current snapshot; future/private or forged derived fields are forbidden')
    result = deepcopy(frame)
    result['nominal_knowledge'] = knowledge
    result['evidence'] = expected
    return result


def _assessment(frame, request):
    _fields(request, REQUEST_FIELDS, 'Public preparation request')
    knowledge = frame['nominal_knowledge']
    entities = {row['id']: row for row in knowledge['entities']}
    interfaces = {row['id']: row for row in knowledge['work_interfaces']}
    _require(request['worker_id'] in entities and request['target_id'] in entities
             and request['work_interface_id'] in interfaces, 'Unknown nominal request identity')
    worker, target = entities[request['worker_id']], entities[request['target_id']]
    interface = interfaces[request['work_interface_id']]
    reasons = []
    if worker['kind'] != 'worker':
        reasons.append('not_a_nominal_worker')
    if interface['qualification_id'] not in worker['qualification_ids']:
        reasons.append('nominal_qualification_mismatch')
    if not set(interface['tool_ids']) <= set(worker['tool_ids']):
        reasons.append('nominal_tool_capability_mismatch')
    if target['id'] not in interface['target_ids']:
        reasons.append('target_outside_nominal_work_interface')
    location = target['id'] if target['kind'] == 'location' else target['nominal_location_id']
    current_ids = set(frame['evidence']['current_record_ids'])
    considered, blocking = set(), set()
    for constraint in knowledge['reported_constraints']:
        if constraint['location_id'] != location:
            continue
        for record in frame['evidence']['records']:
            if record['id'] in current_ids and all(record[key] == constraint[key]
                    for key in ('source_id', 'target_id', 'observable_id')):
                considered.add(record['id'])
                if record['value'] is False:
                    blocking.add(record['id'])
    if blocking:
        reasons.append('current_report_restricts_entry')
    return dict(request_id=request['id'], legal_for_planning=not reasons,
                public_reasons=reasons, considered_record_ids=sorted(considered),
                blocking_record_ids=sorted(blocking), physical_feasibility='UNVERIFIED',
                execution_permission=False,
                unresolved_dynamic_requirements=['actual_access', 'current_worker_position',
                    'tool_availability', 'resource_occupation', 'route_and_timing', 'execution_authorization'],
                basis='NOMINAL_CAPABILITIES_AND_CURRENT_DECLARED_REPORTS_ONLY')


def public_feasibility(frame, request_id):
    """Read-only preparation assessment, never a query to a physical executor."""
    frame = _current_frame(frame)
    request = next((row for row in frame['requests'] if row['id'] == request_id), None)
    _require(request is not None, 'Unknown public preparation request')
    return _assessment(frame, request)


def decision_options(frame):
    """Non-optimizing tracer: first eligible intention in its declared order."""
    frame = _current_frame(frame)
    assessments = [_assessment(frame, request) for request in frame['requests']]
    return dict(schema='aegisdc-public-preparation-options-v1', as_of_s=frame['as_of_s'],
                candidate_assessments=assessments,
                legal_mask={row['request_id']: row['legal_for_planning'] for row in assessments},
                demo_choice_id=next((row['request_id'] for row in assessments if row['legal_for_planning']), None),
                execution_permission=False,
                demo_rule='FIRST_ELIGIBLE_DECLARED_PUBLIC_INTENTION_NOT_AN_EFFECT_METHOD')


class DecisionGateway:
    """Evaluator-owned public clock and ledger; consumers receive only JSON.

    The evaluator freezes a public schedule before a hidden-world comparison.
    A dispatcher must never receive this backend object or its next-frame method.
    """

    def __init__(self, nominal_knowledge, ledger_document, public_plan):
        for document in (nominal_knowledge, ledger_document, public_plan):
            _plain_json(document)
        knowledge = validate_nominal(nominal_knowledge)
        ledger = validate_ledger(ledger_document)
        plan = _public_plan(public_plan, knowledge)
        _binding_registry(knowledge, ledger)
        self._knowledge, self._plan = knowledge, plan
        self._ledger = EvidenceLedger(_canonical_registry(knowledge, ledger))
        self._index = 0

    def next_frame(self):
        """Release exactly the next declared public tick, including empty ticks."""
        if self._index == len(self._plan['decision_times_s']):
            raise StopIteration
        now = self._plan['decision_times_s'][self._index]
        frame = dict(schema='aegisdc-dispatch-frame-v1', plan_id=self._plan['id'],
                     facility_id=self._knowledge['facility_id'], time_unit='s', as_of_s=now,
                     nominal_knowledge=deepcopy(self._knowledge),
                     evidence=self._ledger.snapshot(now), requests=deepcopy(self._plan['requests']))
        self._index += 1
        return frame
