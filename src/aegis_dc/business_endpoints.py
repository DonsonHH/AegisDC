"""Private business endpoints from actual work and public sampled assessments."""
from copy import deepcopy

from .evidence_ledger import _fields, _finite, _plain_json, _registry, _require, _text

PROGRAM_FIELDS = {'schema', 'id', 'facility_id', 'basis', 'time_unit', 'source_note', 'episodes'}
EPISODE_FIELDS = {'id', 'question_id', 'task_id', 'opened_at_s', 'source_note'}


def validate_business_program(program, facility_id, duration_s, dispatch_program, *, scenario=None, boundary_events=()):
    """Validate evaluation-only bindings before any physical execution begins."""
    _plain_json(program)
    if type(program) is dict and program.get('schema') in ('aegisdc-business-cost-evaluation-v1',
                                                         'aegisdc-business-cost-evaluation-v2'):
        from .cost_endpoints import validate_cost_program
        return validate_cost_program(program, facility_id)
    if type(program) is dict and program.get('schema') in ('aegisdc-business-diagnostic-evaluation-v1',
                                                        'aegisdc-business-diagnostic-evaluation-v2',
                                                        'aegisdc-business-diagnostic-evaluation-v3'):
        from .diagnostic_endpoints import validate_diagnostic_evaluation
        return validate_diagnostic_evaluation(program,facility_id,duration_s,dispatch_program,scenario,boundary_events)
    _fields(program, PROGRAM_FIELDS, 'Business closure evaluation program')
    instance_program = program['schema'] == 'aegisdc-business-instance-closure-evaluation-v1'
    _require(program['schema'] in ('aegisdc-business-closure-evaluation-v1', 'aegisdc-business-instance-closure-evaluation-v1')
             and program['basis'] == 'synthetic_assumption' and program['time_unit'] == 's',
             'Declare synthetic closure endpoint evaluation in SI seconds')
    for name in ('id', 'source_note'):
        _text(program[name], 'Business evaluation ' + name)
    _require(program['facility_id'] == facility_id, 'Business evaluation facility differs')
    closure = dispatch_program.get('closure_program') if type(dispatch_program) is dict else None
    _require(type(closure) is dict and type(closure.get('profile')) is dict
             and type(closure['profile'].get('rules')) is list,
             'Business closure endpoints require an executed public closure program')
    if instance_program:
        _require(closure.get('schema') == 'aegisdc-instance-closure-program-v1'
                 and dispatch_program.get('policy_program', {}).get('schema') == 'aegisdc-problem-driven-policy-v2',
                 'Instance endpoints require the matching public instance closure workflow')
    episodes = _registry(program['episodes'], 'Business event')
    _require(0 < len(episodes) <= 1024, 'Declare one to1024 finite business events')
    seen = set()
    for event in episodes.values():
        _fields(event, EPISODE_FIELDS, 'Business event')
        for name in ('question_id', 'task_id', 'source_note'):
            _text(event[name], 'Business event ' + name)
        _finite(event['opened_at_s'], 'Business event opening')
        _require(0 <= event['opened_at_s'] <= duration_s, 'Business event opening outside the run')
        binding = (event['question_id'], event['task_id'], event['opened_at_s'])
        _require(binding not in seen, 'Do not duplicate the same question/action/opening event')
        seen.add(binding)
        if instance_program:
            rules = []
            templates = dispatch_program['policy_program'].get('templates', [])
            _require(type(templates) is list, 'Declare public instance templates')
            for rule in closure['profile']['rules']:
                if type(rule) is not dict:
                    continue
                for template in templates:
                    if type(template) is not dict or template.get('id') != rule.get('template_id'):
                        continue
                    count = template.get('max_instances')
                    _require(type(count) is int and 0 < count <= 16, 'Declare finite instance endpoint slots')
                    for slot in range(count):
                        if (event['question_id'], event['task_id']) == (
                            template['id'] + '/question-' + str(slot), template['id'] + '/action-' + str(slot)):
                            rules.append(rule)
        else:
            rules = [rule for rule in closure['profile']['rules'] if type(rule) is dict
                     and (rule.get('question_id'), rule.get('task_id'), rule.get('opened_at_s')) == binding]
        _require(len(rules) == 1, 'Business event must bind one declared public question/action rule')
    return deepcopy(program)


def evaluate_business_closure(result, program):
    """Read completed-run outputs; never supply truth or endpoints to dispatch."""
    end = result['summary']['duration_s']
    episodes = []
    for event in program['episodes']:
        assessments = []
        for decision in result.get('policy_public_decisions', []):
            time = decision['frame']['as_of_s']
            if time < event['opened_at_s']:
                continue
            lifecycle = decision['choice'].get('question_lifecycle')
            if lifecycle is None:
                continue
            _require(lifecycle['as_of_s'] == time <= end,
                     'Actual closure assessment clock differs from its decision')
            for question in lifecycle['questions']:
                if question['question_id'] != event['question_id']:
                    continue
                if program['schema'] == 'aegisdc-business-instance-closure-evaluation-v1':
                    _require(question['opened_at_s'] == event['opened_at_s'] and question['task_id'] == event['task_id'],
                             'Actual instance opening/action differs from its private endpoint binding')
                assessments.append({name: deepcopy(question[name]) for name in
                    ('as_of_s', 'status', 'risk_closed', 'question_closed', 'supporting_record_ids',
                     'blocking_record_ids', 'disposition_record_ids', 'scope')})
        _require(all(a['as_of_s'] < b['as_of_s'] for a, b in zip(assessments, assessments[1:])),
                 'Business events require distinct increasing actual assessment clocks')
        completed = [row['completed_at_s'] for row in result['work_records']
                     if row['id'] == event['task_id'] and row['status'] == 'completed']
        reports = [row for row in result.get('intervention_public_feedback', [])
                   if row['task_id'] == event['task_id']]
        closed = [row['as_of_s'] for row in assessments if row['status'] == 'VERIFIED_CLOSED']
        first = closed[0] if closed else None
        last = assessments[-1] if assessments else None
        horizon = next((row for row in assessments if row['as_of_s'] == end), None)
        episodes.append(dict(id=event['id'], question_id=event['question_id'], task_id=event['task_id'],
            opened_at_s=event['opened_at_s'],
            actual_action_completed_at_s=min(completed) if completed else None,
            action_report_arrived_at_s=min(row['arrived_at_s'] for row in reports) if reports else None,
            action_report_outcome=reports[0]['outcome'] if len(reports) == 1 else None,
            first_verified_closed_at_s=first,
            time_to_first_verified_closed_s=first - event['opened_at_s'] if first is not None else None,
            closure_right_censored=first is None,
            closure_censor_at_s=last['as_of_s'] if first is None and last else None,
            last_assessed_at_s=last['as_of_s'] if last else None,
            latest_assessed_status=last['status'] if last else None,
            status_at_horizon=horizon['status'] if horizon else 'NOT_ASSESSED_AT_HORIZON',
            assessments=assessments,
            scope='ACTUAL_WORK_AND_DECLARED_FINITE_SAMPLED_CLOSURE_NOT_CONTINUOUS_RESTORATION'))
    return dict(schema='aegisdc-business-instance-closure-result-v1' if program['schema'] == 'aegisdc-business-instance-closure-evaluation-v1'
                else 'aegisdc-business-evaluation-v1', program_id=program['id'],
        facility_id=result['facility_id'], visibility='PRIVATE_EVALUATOR_ONLY',
        basis=program['basis'], time_unit='s', window_end_s=end,
        execution_code_identity=deepcopy(result['code_identity']), episodes=episodes,
        diagnosis_and_prevention=dict(status='NOT_DEFINED_FOR_THIS_PROGRAM_VERSION',
            false_positive_rate=None, missed_detection_rate=None, prevention_effect=None),
        new_research_trials=0,
        field_calibration='PENDING', research_gain_claim='NOT_ESTABLISHED')


def evaluate_business_endpoints(result, program):
    if program['schema'] in ('aegisdc-business-cost-evaluation-v1', 'aegisdc-business-cost-evaluation-v2'):
        from .cost_endpoints import evaluate_actual_costs
        return evaluate_actual_costs(result, program)
    if program['schema'] in ('aegisdc-business-diagnostic-evaluation-v1','aegisdc-business-diagnostic-evaluation-v2',
                             'aegisdc-business-diagnostic-evaluation-v3'):
        from .diagnostic_endpoints import evaluate_diagnostic_events
        return evaluate_diagnostic_events(result,program)
    return evaluate_business_closure(result,program)
