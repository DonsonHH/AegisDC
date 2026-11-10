"""Bind private diagnostic, instance and cost endpoints to one actual facility run."""
from copy import deepcopy

from patrol_rsi.contracts import digest
from .evidence_ledger import _fields, _finite, _plain_json, _require, _text

PROGRAM_FIELDS = {'schema', 'id', 'facility_id', 'basis', 'time_unit', 'source_note', 'run_binding', 'components'}
BINDING_FIELDS = {'scenario_sha256', 'dispatch_program_sha256', 'boundary_events_sha256',
                  'action_commands_sha256', 'duration_s', 'maximum_step_s'}
COMPONENT_SCHEMAS = dict(diagnostic='aegisdc-business-diagnostic-evaluation-v3',
    instance_closure='aegisdc-business-instance-closure-evaluation-v2', costs='aegisdc-business-cost-evaluation-v2')


def execution_input_binding(scenario, inputs):
    """Hash normalized execution inputs; do not include private evaluation in dispatch."""
    return dict(scenario_sha256=digest(scenario), dispatch_program_sha256=digest(inputs['dispatch_program']),
        boundary_events_sha256=digest(inputs['boundary_events']),
        action_commands_sha256=digest(inputs.get('action_commands', [])),
        duration_s=inputs['duration_s'], maximum_step_s=inputs['maximum_step_s'])


def validate_composite_program(program, facility_id, duration_s, dispatch, scenario, boundary_events, execution_binding):
    """Check the whole input binding and each closed component before integration."""
    from .business_endpoints import validate_business_program
    from .cost_endpoints import validate_cost_program
    from .diagnostic_endpoints import validate_diagnostic_evaluation

    _plain_json(program)
    _fields(program, PROGRAM_FIELDS, 'Composite business evaluation')
    _require(program['schema'] == 'aegisdc-business-composite-evaluation-v1'
             and program['facility_id'] == facility_id and program['basis'] == 'synthetic_assumption'
             and program['time_unit'] == 's', 'Composite identity, basis or time unit differs')
    for name in ('id', 'source_note'):
        _text(program[name], 'Composite ' + name)
    _require(type(dispatch) is dict and dispatch.get('schema') == 'aegisdc-policy-run-program-v5',
             'Composite business evaluation requires native execution v5')
    binding = program['run_binding']
    _fields(binding, BINDING_FIELDS, 'Composite run binding')
    for name in ('duration_s', 'maximum_step_s'):
        _finite(binding[name], 'Composite ' + name)
        _require(binding[name] > 0, 'Composite time inputs must be positive')
    _require(type(execution_binding) is dict and binding == execution_binding,
             'Composite run binding differs from actual execution inputs')
    components = program['components']
    _require(type(components) is dict and set(components) == set(COMPONENT_SCHEMAS),
             'Declare exactly diagnostic, instance_closure and costs components')
    for name, schema in COMPONENT_SCHEMAS.items():
        _require(type(components[name]) is dict and components[name].get('schema') == schema,
                 'Composite component version differs: ' + name)
    validate_diagnostic_evaluation(components['diagnostic'], facility_id, duration_s,
                                   dispatch, scenario, boundary_events)
    validate_business_program(components['instance_closure'], facility_id, duration_s, dispatch,
                              scenario=scenario, boundary_events=boundary_events)
    validate_cost_program(components['costs'], facility_id)
    ids = [program['id'], *(component['id'] for component in components.values())]
    _require(len(ids) == len(set(ids)), 'Composite and component program identities must be distinct')
    return deepcopy(program)


def evaluate_composite_endpoints(result, program):
    """Extract all three complete private reports from the same completed RunResult."""
    from .business_endpoints import evaluate_business_closure
    from .cost_endpoints import evaluate_actual_costs
    from .diagnostic_endpoints import evaluate_diagnostic_events

    binding = execution_input_binding(result['source_config'], result['inputs'])
    _require(binding == program['run_binding'], 'Composite actual result input binding differs')
    declarations = program['components']
    components = dict(diagnostic=evaluate_diagnostic_events(result, declarations['diagnostic']),
        instance_closure=evaluate_business_closure(result, declarations['instance_closure']),
        costs=evaluate_actual_costs(result, declarations['costs']))
    for name, component in components.items():
        _require(component['program_id'] == declarations[name]['id']
                 and component['facility_id'] == result['facility_id']
                 and component['window_end_s'] == result['summary']['duration_s']
                 and component['visibility'] == 'PRIVATE_EVALUATOR_ONLY'
                 and component['execution_code_identity'] == result['code_identity'],
                 'Composite component actual run identity differs: ' + name)
    return dict(schema='aegisdc-business-composite-result-v1', program_id=program['id'],
        facility_id=result['facility_id'], visibility='PRIVATE_EVALUATOR_ONLY', basis=program['basis'], time_unit='s',
        window_end_s=result['summary']['duration_s'], execution_code_identity=deepcopy(result['code_identity']),
        run_binding=binding, business_program_sha256=digest(program),
        component_program_sha256={name: digest(component) for name, component in declarations.items()},
        components=components, new_research_trials=0, field_calibration='PENDING', research_gain_claim='NOT_ESTABLISHED')
