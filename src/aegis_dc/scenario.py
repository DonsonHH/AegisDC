"""Load the full-facility structural contract; this module performs no simulation."""
from pathlib import Path
import math

from patrol_rsi.contracts import digest, strict_json

DOMAINS = {
    'power', 'backup', 'facility_cooling', 'equipment_environment',
    'it_service', 'control_monitoring', 'space_access', 'people_tools_work',
}
SI_UNITS = {
    'power': 'W', 'energy': 'J', 'voltage': 'V', 'temperature': 'K',
    'mass': 'kg', 'volume': 'm3', 'volume_flow': 'm3/s', 'mass_flow': 'kg/s',
    'pressure': 'Pa', 'time': 's', 'thermal_capacity': 'J/K',
    'thermal_conductance': 'W/K', 'specific_heat': 'J/(kg*K)',
    'density': 'kg/m3', 'efficiency': '1', 'relative_humidity': '1',
    'service_capacity': '1', 'probability': '1', 'length': 'm',
}
PARAMETER_BASES = {'synthetic_assumption', 'published_reference', 'derived_reference'}
STRICTLY_POSITIVE = {'temperature', 'mass', 'volume', 'time', 'thermal_capacity',
                     'specific_heat', 'density', 'efficiency'}
ENTITY_KINDS = {'asset', 'location', 'service', 'worker', 'tool', 'point'}
SPECIALTIES = {'electrical', 'cooling', 'control', 'it'}
RELATIONS = {
    'physical': {'electric', 'heat', 'fluid'},
    'functional': {'requires', 'capacity', 'backup', 'control_permit', 'access_condition'},
    'control_information': {'measurement', 'report', 'command'},
    'access': {'walk'},
}
SCENARIO_FIELDS = {'schema', 'id', 'basis', 'scope', 'sources', 'media', 'domains',
                   'entities', 'qualifications', 'parameters', 'graphs', 'site_gaps', 'assumptions'}
SOURCE_CLASSES = {'synthetic_assumption', 'design_document', 'vendor_claim',
                  'published_site', 'published_model', 'reference_calculation', 'operator_published'}
ENTITY_FIELDS = {'id', 'kind', 'domain', 'label', 'location_id', 'ports',
                 'parameter_refs', 'basis', 'source_refs', 'source_note'}
EDGE_FIELDS = {'id', 'from', 'to', 'kind', 'basis', 'source_refs', 'source_note'}
EDGE_DETAIL_FIELDS = {'physical': {'from_port', 'to_port'}, 'functional': {'parameter_refs'},
                      'control_information': set(),
                      'access': {'duration_parameter', 'bidirectional', 'requires_qualification_ids'}}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _text(value, label):
    _require(isinstance(value, str) and bool(value.strip()), label + ' must be nonempty text')


def _strings(value, label, *, allow_empty=False):
    _require(isinstance(value, list) and (allow_empty or bool(value)), label + ' must be a declared list')
    for item in value:
        _text(item, label)
    _require(len(value) == len(set(value)), 'Duplicate ' + label)


def _number(value, label):
    valid = type(value) in (int, float)
    if valid:
        try:
            valid = math.isfinite(float(value))
        except OverflowError:
            valid = False
    _require(valid, label + ' requires a finite representable number; missing is not zero')


def _fields(row, expected, label):
    _require(isinstance(row, dict) and set(row) == expected, label + ' fields do not match the v1 contract')


def _index(rows, label):
    _require(isinstance(rows, list) and bool(rows), 'Declare ' + label)
    result = {}
    for row in rows:
        _require(isinstance(row, dict), label + ' record must be an object')
        identifier = row.get('id')
        _text(identifier, label + ' id')
        _require(identifier not in result, 'Duplicate ' + label + ' id: ' + identifier)
        result[identifier] = row
    return result


def _provenance(row, sources):
    _strings(row.get('source_refs'), 'source_refs')
    _require(all(ref in sources for ref in row['source_refs']), 'Unknown source reference')
    _text(row.get('source_note'), 'source_note')


def _contract(scenario):
    _require(isinstance(scenario, dict) and set(scenario) == SCENARIO_FIELDS, 'Scenario fields do not match the v1 contract')
    _require(scenario['schema'] == 'aegisdc-full-facility-scenario-v1', 'Unknown scenario schema')
    _require(scenario['basis'] == 'zhengzhou_inspired_synthetic', 'Declare a Zhengzhou-inspired synthetic research basis')
    _text(scenario['id'], 'Scenario id')
    _text(scenario['scope'], 'Scenario scope')
    _strings(scenario['assumptions'], 'assumptions')
    sources = scenario['sources']
    _require(isinstance(sources, dict) and bool(sources), 'Declare sources')
    for identifier, source in sources.items():
        _text(identifier, 'source id')
        _fields(source, {'classification', 'uri', 'scope'}, 'source')
        _text(source.get('classification'), 'source classification')
        _require(isinstance(source, dict) and source.get('classification') in SOURCE_CLASSES, 'Unknown source classification')
        _text(source.get('uri'), 'source URI')
        _text(source.get('scope'), 'source scope')


def _gaps(scenario, parameters):
    rows = scenario['site_gaps']
    _require(isinstance(rows, list), 'Declare site_gaps separately from active parameters')
    if not rows:
        return
    for gap in _index(rows, 'site gap').values():
        _require(set(gap) == {'id', 'value', 'needed_for', 'source_refs'}, 'site gap fields are not active parameter fields')
        _require(gap['value'] is None, 'Unresolved site gap must remain null')
        _require(gap['id'] not in parameters, 'site gap shadows an active parameter')
        _text(gap['needed_for'], 'site gap needed_for')
        _strings(gap['source_refs'], 'site gap source_refs')
        _require(all(ref in scenario['sources'] for ref in gap['source_refs']), 'Unknown site gap source')


def _parameters(scenario):
    sources = scenario.get('sources')
    _require(isinstance(sources, dict) and bool(sources), 'Declare sources')
    parameters = _index(scenario.get('parameters'), 'parameter')
    for row in parameters.values():
        _fields(row, {'id', 'quantity', 'unit', 'value', 'valid_range', 'basis', 'source_refs', 'source_note'}, 'parameter')
        quantity = row.get('quantity')
        _text(quantity, 'SI quantity')
        _require(quantity in SI_UNITS, 'Unknown SI quantity')
        _require(row.get('unit') == SI_UNITS[quantity], 'Parameter unit does not match SI quantity')
        _text(row.get('basis'), 'parameter source basis')
        _require(row['basis'] in PARAMETER_BASES, 'Declare parameter source basis')
        _provenance(row, sources)
        if row['basis'] != 'synthetic_assumption':
            _require(any(sources[ref]['classification'] != 'synthetic_assumption' for ref in row['source_refs']),
                     'Reference parameter needs a reference source')
        value = row.get('value')
        limits = row.get('valid_range')
        _number(value, 'Parameter value')
        _require(isinstance(limits, list) and len(limits) == 2, 'Declare valid_range')
        for limit in limits:
            _number(limit, 'valid_range')
        low, high = limits
        _require(0 <= low <= value <= high, 'Parameter outside nonnegative valid_range')
        if quantity in STRICTLY_POSITIVE:
            _require(low > 0, 'Quantity requires a strictly positive valid_range')
        if quantity in {'efficiency', 'relative_humidity', 'probability'}:
            _require(high <= 1, 'Fraction valid_range must stay in [0,1]')
    return parameters


def _domains(scenario):
    domains = scenario.get('domains')
    _require(isinstance(domains, list) and len(domains) == 8, 'Declare the eight operational domains')
    indexed = _index(domains, 'domain')
    _require(set(indexed) == DOMAINS, 'Declare the eight operational domains')
    for domain in domains:
        _fields(domain, {'id', 'label', 'entity_ids', 'states', 'inputs', 'outputs',
                         'behaviors', 'effect', 'work_interfaces'}, 'domain')
        _text(domain.get('label'), 'Domain label')
        for field in ['states', 'inputs', 'outputs', 'behaviors', 'entity_ids']:
            _strings(domain.get(field), domain['id'] + '.' + field)
        _text(domain.get('effect'), domain['id'] + '.effect')
        _require(isinstance(domain.get('work_interfaces'), list) and bool(domain['work_interfaces']),
                 domain['id'] + '.work_interfaces must be declared')


def _entities(scenario, parameters):
    entities = _index(scenario.get('entities'), 'entity')
    for entity in entities.values():
        _text(entity.get('kind'), 'Entity kind')
        _text(entity.get('domain'), 'Entity domain')
        _require(entity.get('kind') in ENTITY_KINDS, 'Unknown entity kind')
        _require(entity.get('domain') in DOMAINS, 'Unknown entity domain')
        extra = {'specialties', 'qualification_ids', 'tool_ids'} if entity['kind'] == 'worker' else \
                {'specialties'} if entity['kind'] == 'tool' else \
                {'target_id', 'visibility'} if entity['kind'] == 'point' else set()
        _fields(entity, ENTITY_FIELDS | extra, 'entity')
        _text(entity.get('label'), 'Entity label')
        _require(entity.get('basis') == 'synthetic_assumption', 'Instantiated research entities need a synthetic basis')
        _provenance(entity, scenario['sources'])
        _strings(entity.get('parameter_refs'), 'entity parameter_refs', allow_empty=True)
        _require(all(ref in parameters for ref in entity['parameter_refs']), 'Unknown entity parameter reference')
        location = entity.get('location_id')
        if location is not None:
            _require(isinstance(location, str) and location in entities and entities[location]['kind'] == 'location',
                     'Entity location must reference a location')
        elif entity['kind'] not in {'location', 'service'}:
            raise ValueError('Located entity must declare location_id')
        _require(isinstance(entity.get('ports'), dict), 'Declare entity ports')
        if entity['kind'] != 'asset':
            _require(not entity['ports'], 'Physical ports belong to assets')
    declared = []
    for domain in scenario['domains']:
        for identifier in domain['entity_ids']:
            _require(identifier in entities and entities[identifier]['domain'] == domain['id'],
                     'Domain entity_ids must reference owned entities')
            declared.append(identifier)
    _require(len(declared) == len(set(declared)) and set(declared) == set(entities),
             'Every entity must be declared once by its operational domain')
    return entities


def _ports(scenario, entities, parameters):
    media = scenario.get('media')
    _require(isinstance(media, dict) and bool(media), 'Declare carrier media')
    for name, medium in media.items():
        _text(name, 'medium id')
        _fields(medium, {'carrier', 'description'}, 'medium')
        _text(medium['carrier'], 'medium carrier')
        _require(medium['carrier'] in RELATIONS['physical'], 'Unknown medium carrier')
        _text(medium.get('description'), 'medium description')
    for entity in entities.values():
        for name, port in entity['ports'].items():
            _text(name, 'port id')
            _fields(port, {'direction', 'carrier', 'medium', 'parameter_ref'}, 'port')
            _text(port.get('direction'), 'port direction')
            _require(port.get('direction') in {'in', 'out'}, 'Declare port direction')
            carrier, medium = port.get('carrier'), port.get('medium')
            _text(carrier, 'port carrier')
            _text(medium, 'port medium')
            _require(carrier in RELATIONS['physical'], 'Unknown port carrier')
            _require(medium in media and media[medium]['carrier'] == carrier, 'port medium does not match carrier')
            parameter = port.get('parameter_ref')
            if parameter is not None:
                _text(parameter, 'port parameter_ref')
            if carrier == 'electric':
                _require(parameter in parameters and parameters[parameter]['quantity'] == 'voltage'
                         and parameters[parameter]['value'] > 0, 'Electrical port requires nominal voltage parameter')
            elif parameter is not None:
                allowed = {'power'} if carrier == 'heat' else {'volume_flow', 'mass_flow'}
                _require(parameter in parameters and parameters[parameter]['quantity'] in allowed,
                         'port parameter quantity does not match carrier')


def _physical_link(edge, start, end, parameters):
    outgoing, incoming = edge.get('from_port'), edge.get('to_port')
    _text(outgoing, 'from_port')
    _text(incoming, 'to_port')
    _require(outgoing in start['ports'] and incoming in end['ports'], 'Unknown physical port')
    a, b = start['ports'][outgoing], end['ports'][incoming]
    _require(a['direction'] == 'out' and b['direction'] == 'in', 'Physical port directions must be out to in')
    _require(a['carrier'] == b['carrier'] == edge['kind'], 'Physical port carrier mismatch')
    _require(a['medium'] == b['medium'], 'Physical port medium mismatch; exchange heat instead of connecting separated fluids')
    if edge['kind'] == 'electric':
        _require(parameters[a['parameter_ref']]['value'] == parameters[b['parameter_ref']]['value'],
                 'Electrical port voltage levels differ without a conversion asset')


def _people_and_work(scenario, entities, parameters):
    qualifications = scenario.get('qualifications')
    _require(isinstance(qualifications, dict) and bool(qualifications), 'Declare qualifications')
    for identifier, qualification in qualifications.items():
        _text(identifier, 'qualification id')
        _fields(qualification, {'specialty', 'basis', 'source_refs', 'source_note'}, 'qualification')
        _text(qualification.get('specialty'), 'qualification specialty')
        _require(isinstance(qualification, dict) and qualification.get('specialty') in SPECIALTIES,
                 'Unknown qualification specialty')
        _require(qualification.get('basis') == 'synthetic_assumption', 'Qualification is a research declaration')
        _provenance(qualification, scenario['sources'])
    for entity in entities.values():
        if entity['kind'] in {'worker', 'tool'}:
            _strings(entity.get('specialties'), 'specialties')
            _require(set(entity['specialties']) <= SPECIALTIES, 'Unknown specialty')
    for entity in entities.values():
        if entity['kind'] == 'worker':
            _strings(entity.get('qualification_ids'), 'worker qualifications')
            for identifier in entity['qualification_ids']:
                _require(identifier in qualifications and qualifications[identifier]['specialty'] in entity['specialties'],
                         'Worker qualification does not match specialty')
            _strings(entity.get('tool_ids'), 'worker tool_ids')
            for identifier in entity['tool_ids']:
                _require(identifier in entities and entities[identifier]['kind'] == 'tool', 'Unknown worker tool')
                _require(bool(set(entities[identifier].get('specialties', [])) & set(entity['specialties'])),
                         'Worker tool does not match specialty')
        if entity['kind'] == 'point':
            target = entity.get('target_id')
            if target is not None:
                _text(target, 'point target_id')
            _require(target is None or (target in entities and entities[target]['kind'] == 'asset'),
                     'Measurement point target must be an asset')
            _text(entity.get('visibility'), 'point visibility')
            _require(entity['visibility'] in {'local_and_optional_dispatch', 'optional_dispatch', 'dispatch_records_only'},
                     'Declare point visibility')
            _require((target is None) == (entity['visibility'] == 'dispatch_records_only'),
                     'Only a record inbox may omit a measurement target')
    work_ids = set()
    for domain in scenario['domains']:
        for work in domain['work_interfaces']:
            _fields(work, {'id', 'target_ids', 'specialty', 'qualification_id', 'tool_ids', 'duration_parameter'}, 'work interface')
            identifier = work.get('id')
            _text(identifier, 'work id')
            _require(identifier not in work_ids, 'Duplicate work interface')
            work_ids.add(identifier)
            _strings(work.get('target_ids'), 'work target_ids')
            _require(all(ref in domain['entity_ids'] for ref in work['target_ids']), 'Work target is not an owned domain entity')
            specialty, qualification = work.get('specialty'), work.get('qualification_id')
            _text(specialty, 'work specialty')
            _text(qualification, 'work qualification_id')
            _require(specialty in SPECIALTIES and qualification in qualifications
                     and qualifications[qualification]['specialty'] == specialty, 'Work qualification does not match specialty')
            _strings(work.get('tool_ids'), 'work tool_ids', allow_empty=True)
            for tool in work['tool_ids']:
                _require(tool in entities and entities[tool]['kind'] == 'tool' and specialty in entities[tool]['specialties'],
                         'Work tool does not match specialty')
            duration = work.get('duration_parameter')
            _text(duration, 'work duration_parameter')
            _require(duration in parameters and parameters[duration]['quantity'] == 'time', 'Work duration needs a time parameter')


def _graphs(scenario, entities, parameters):
    graphs = scenario.get('graphs')
    _require(isinstance(graphs, dict) and set(graphs) == set(RELATIONS), 'Declare four relationship graphs')
    qualifications = scenario.get('qualifications')
    _require(isinstance(qualifications, dict), 'Declare qualifications')
    all_edge_ids = set()
    for graph, rows in graphs.items():
        for edge in _index(rows, graph + ' edge').values():
            _fields(edge, EDGE_FIELDS | EDGE_DETAIL_FIELDS[graph], graph + ' relationship')
            _require(edge['id'] not in all_edge_ids, 'Duplicate relationship id')
            all_edge_ids.add(edge['id'])
            for endpoint in ['from', 'to']:
                _text(edge.get(endpoint), 'Relationship ' + endpoint)
                _require(edge[endpoint] in entities, 'Unknown relationship endpoint')
            _text(edge.get('kind'), 'relationship type')
            _require(edge.get('kind') in RELATIONS[graph], 'Wrong relationship type for ' + graph)
            _require(edge.get('basis') == 'synthetic_assumption', 'Research relationship needs a synthetic basis')
            _provenance(edge, scenario['sources'])
            start, end = entities[edge['from']], entities[edge['to']]
            if graph == 'physical':
                _require(start['kind'] == end['kind'] == 'asset', 'Physical links connect assets')
                _physical_link(edge, start, end, parameters)
            elif graph == 'functional':
                allowed_end = {'location'} if edge['kind'] == 'access_condition' else {'asset', 'service'}
                _require(start['kind'] == 'asset' and end['kind'] in allowed_end, 'Invalid functional endpoint roles')
                _strings(edge.get('parameter_refs'), 'functional parameter_refs', allow_empty=True)
                _require(all(ref in parameters for ref in edge['parameter_refs']), 'Unknown functional parameter')
            elif graph == 'control_information':
                if edge['kind'] == 'measurement':
                    _require(start['kind'] == 'asset' and end['kind'] == 'point', 'Measurement must connect asset to point')
                    _require(end['target_id'] == start['id'], 'Measurement relation differs from point target')
                elif edge['kind'] == 'command':
                    _require(start['domain'] == 'control_monitoring' and start['kind'] == end['kind'] == 'asset',
                             'Command must originate from a declared local control asset')
                else:
                    _require(start['kind'] in {'asset', 'point'} and end['kind'] in {'asset', 'point'}, 'Invalid report endpoints')
            else:
                _require(start['kind'] == end['kind'] == 'location', 'Access links use location identities')
                _require(type(edge.get('bidirectional')) is bool, 'Declare access direction')
                duration = edge.get('duration_parameter')
                _text(duration, 'access duration_parameter')
                _require(duration in parameters and parameters[duration]['quantity'] == 'time', 'Access duration needs a time parameter')
                _strings(edge.get('requires_qualification_ids'), 'access qualifications', allow_empty=True)
                _require(all(ref in qualifications for ref in edge['requires_qualification_ids']), 'Unknown access qualification')


def load_scenario(path):
    """Read and validate a structural scenario; no dynamics or actions are run."""
    scenario = strict_json(Path(path).read_text(encoding='utf-8'))
    _contract(scenario)
    _domains(scenario)
    parameters = _parameters(scenario)
    _gaps(scenario, parameters)
    entities = _entities(scenario, parameters)
    _ports(scenario, entities, parameters)
    _people_and_work(scenario, entities, parameters)
    _graphs(scenario, entities, parameters)
    return scenario


def describe_scenario(scenario):
    """Return inspectable source/relationship records without claiming dynamics."""
    return {
        'status': 'STRUCTURE_DEFINED_NOT_SIMULATED',
        'scenario_id': scenario['id'],
        'basis': scenario['basis'],
        'scope': scenario['scope'],
        'canonical_sha256': digest(scenario),
        'dynamic_model_executed': False,
        'field_calibration': 'PENDING',
        'behavior_status': 'DECLARED_NOT_EXECUTED',
        'parameter_consistency': 'Individual SI ranges checked; coupled initialization and dynamics remain unverified',
        'research_gain_claim': 'NOT_ESTABLISHED',
        'domain_count': len(scenario['domains']),
        'entity_count': len(scenario['entities']),
        'domains': scenario['domains'],
        'entities': scenario['entities'],
        'qualifications': scenario['qualifications'],
        'media': scenario['media'],
        'parameters': scenario['parameters'],
        'graphs': scenario['graphs'],
        'graph_edge_counts': {name: len(edges) for name, edges in scenario['graphs'].items()},
        'sources': scenario['sources'],
        'site_gaps': scenario['site_gaps'],
        'assumptions': scenario['assumptions'],
    }
