"""Instance-scoped public stage gates; actual effects remain in the plant."""
from copy import deepcopy
from fractions import Fraction

from .evidence_ledger import _fields, _finite, _require, _text
from .inspection_execution import PROFILE_FIELDS, BINDING_FIELDS
from .intervention_execution import BIND_FIELDS, prepare_intervention, _authorization
from .nonfixed_evidence import validate_nonfixed_profile, _arrival
from .problem_tasks import declared_problem_tasks, open_questions
from .verified_closure import FEEDBACK_FIELDS


def _declarations(frame, program):
    catalog = {row['task']['id']: row for row in declared_problem_tasks(frame, program)}
    profile = program['inspection_declaration']
    _fields(profile, PROFILE_FIELDS, 'Public problem inspection declaration')
    _require(profile['schema'] == 'aegisdc-inspection-profile-v1' and profile['basis'] == 'synthetic_assumption'
             and profile['facility_id'] == frame['facility_id'], 'Problem inspection facility/basis differs')
    for key in ('id', 'source_note'):
        _text(profile[key], 'Problem inspection ' + key)
    nonfixed = validate_nonfixed_profile(profile['nonfixed_profile'])
    _require(nonfixed['registry']['facility_id'] == frame['facility_id']
             and set(nonfixed['registry']['entity_ids']) == {r['id'] for r in frame['nominal_knowledge']['entities']},
             'Problem inspection public entity identities differ')
    models = {row['model']['id']: row for row in nonfixed['models']}
    _require(type(profile['bindings']) is list, 'Declare public problem inspection bindings')
    inspections = {}
    record_ids = set()
    for binding in profile['bindings']:
        _fields(binding, BINDING_FIELDS, 'Public problem inspection binding')
        for key in ('task_id', 'record_id', 'model_id', 'tool_id', 'qualification_id'):
            _text(binding[key], 'Inspection ' + key)
        task_id = binding['task_id']
        _require(task_id in catalog and catalog[task_id]['kind'] == 'inspect' and task_id not in inspections
                 and binding['model_id'] in models and binding['record_id'] not in record_ids,
                 'Unknown/repeated problem inspection slot/model/record')
        model = models[binding['model_id']]
        _require(model['target_id'] == catalog[task_id]['task']['target_id'], 'Problem measurement target differs')
        inspections[task_id] = (binding, model)
        record_ids.add(binding['record_id'])
    _require(set(inspections) == {key for key, row in catalog.items() if row['kind'] == 'inspect'},
             'Declare every finite initial and recheck inspection slot exactly once')
    declaration = program['intervention_declaration']
    _fields(declaration, {'schema', 'profile', 'bindings'}, 'Public problem intervention declaration')
    _require(declaration['schema'] == 'aegisdc-intervention-program-v1'
             and type(declaration['bindings']) is list, 'Declare named problem interventions')
    actions = {}
    for binding in declaration['bindings']:
        _fields(binding, BIND_FIELDS, 'Public problem intervention binding')
        _text(binding['task_id'], 'Problem intervention task')
        task_id = binding['task_id']
        _require(task_id in catalog and catalog[task_id]['kind'] == 'intervene' and task_id not in actions,
                 'Unknown/repeated problem intervention slot')
        task = deepcopy(catalog[task_id]['task'])
        task['deadline_s'] = max(task['deadline_s'], frame['as_of_s'])
        prepare_intervention(frame, program['workforce_profile'], task, declaration['profile'], binding)
        actions[task_id] = binding
    _require(set(actions) == {key for key, row in catalog.items() if row['kind'] == 'intervene'},
             'Declare every finite action slot exactly once')
    return inspections, actions


def _feedback(frame, program, history, actions):
    _require(type(history['intervention_feedback']) is list, 'Declare arrived problem intervention feedback')
    issued = {row['candidate_id']: row['issued_at_s'] for row in history['issued']}
    _require(type(history['work_feedback']) is list, 'Declare arrived problem workforce feedback')
    profile = program['intervention_declaration']['profile']
    operations = {row['id']: row for row in profile['operations']}
    grants = {row['id']: row for row in profile['authorizations']}
    reports = {}
    for row in history['intervention_feedback']:
        _fields(row, FEEDBACK_FIELDS, 'Arrived problem intervention feedback')
        _text(row['task_id'], 'Intervention feedback task')
        task_id = row['task_id']
        _require(task_id in actions and task_id in issued and task_id not in reports,
                 'Intervention feedback must bind one actually issued action')
        _require(row['operation_id'] == actions[task_id]['operation_id']
                 and row['source_id'] == 'intervention-execution-report'
                 and row['origin_id'] == 'intervention:' + task_id
                 and row['coverage'] == 'THIS_AUTHORIZED_TASK_ONLY' and row['risk_closed'] is False,
                 'Invalid task-local problem intervention feedback channel')
        _require(row['outcome'] in {'APPLIED', 'NO_EFFECT'}, 'Unknown problem intervention outcome')
        _require(row['reason'] is None if row['outcome'] == 'APPLIED' else
                 type(row['reason']) is str and bool(row['reason']), 'Intervention reason differs from outcome')
        for key in ('observed_at_s', 'arrived_at_s'):
            _finite(row[key], 'Intervention feedback ' + key)
        _require(issued[task_id] <= row['observed_at_s'] <= row['arrived_at_s'] <= frame['as_of_s']
                 and row['arrived_at_s'] == _arrival(row['observed_at_s'], program['intervention_declaration']['profile']['feedback_latency_s']),
                 'Intervention feedback contains pre-issue, future or undeclared arrival time')
        if row['outcome'] == 'APPLIED':
            binding = actions[task_id]
            _require(_authorization(operations[binding['operation_id']], grants[binding['authorization_id']], row['observed_at_s']),
                     'APPLIED report contradicts the declared authorization at completion')
            terminal = [work for work in history['work_feedback'] if work['task_id'] == task_id
                        and work['status'] in {'completed', 'aborted', 'rejected'}]
            _require(all(work['status'] == 'completed' and work['observed_at_s'] == row['observed_at_s'] for work in terminal),
                     'APPLIED report contradicts the arrived workforce completion')
        reports[task_id] = row
    return reports


def _completion_arrived(history, report):
    return report is not None and any(work['task_id'] == report['task_id'] and work['status'] == 'completed'
        and work['observed_at_s'] == report['observed_at_s'] for work in history['work_feedback'])


def _measurement(frame, history, task_id, declaration):
    issued = {row['candidate_id']: row['issued_at_s'] for row in history['issued']}
    if task_id not in issued:
        return None
    binding, model = declaration
    record = next((r for r in frame['evidence']['records'] if r['id'] == binding['record_id']), None)
    if record is None:
        return None
    _require(all(record[key] == model[key] for key in ('source_id', 'target_id', 'observable_id'))
             and record['unit'] == model['model']['unit'] and record['provenance'] == binding['provenance']
             and issued[task_id] <= record['observed_at_s']
             and record['arrived_at_s'] == _arrival(record['observed_at_s'], binding['arrival_latency_s']),
             'Problem measurement differs from its issued producer binding')
    return record


def compile_problem_actions(frame, program, history, *, closure_program=None):
    """Compile active and all issued stages into the existing common budget gate."""
    templates, instances, questions, deferred = open_questions(frame, program, history)
    inspections, actions = _declarations(frame, program)
    _require(type(history['issued']) is list, 'Declare issued problem stages')
    reports = _feedback(frame, program, history, actions)
    lifecycle = None
    verification = {}
    if closure_program is not None:
        from .problem_closure import assess_instance_closure
        lifecycle = assess_instance_closure(frame, program, history, closure_program)
        verification = {row['question_id']: row for row in lifecycle['questions']}
    issued = {row['candidate_id'] for row in history['issued']}
    disputed = {identifier for issue in frame['evidence']['conflicts'] + frame['evidence']['provenance_issues']
                for identifier in issue['record_ids']}
    candidates = []
    gates = []
    for instance, question in zip(instances, questions):
        template = templates[instance['template_id']]
        suffix = '-' + str(instance['slot'])
        ids = {stage: template['id'] + '/' + stage + suffix for stage in ('inspect', 'action', 'recheck')}
        observed = _measurement(frame, history, ids['inspect'], inspections[ids['inspect']])
        rechecked = _measurement(frame, history, ids['recheck'], inspections[ids['recheck']])
        report = reports.get(ids['action'])
        completion_arrived = _completion_arrived(history, report)
        condition = template['action_condition']
        ready = observed is not None
        if condition is not None:
            model = inspections[ids['inspect']][1]
            _require(condition['observable_id'] == model['observable_id'] and condition['unit'] == model['model']['unit'],
                     'Action condition differs from its own initial measurement')
            ready = (ready and observed['availability'] == 'current' and observed['id'] not in disputed
                     and observed['quality']['status'] == 'bounded' and observed['provenance']['copied_from_record_id'] is None)
            if ready:
                low, high = map(Fraction, condition['accepted_interval'])
                value, error = Fraction(observed['value']), Fraction(observed['quality']['error_bound'])
                ready = low <= value - error and value + error <= high
        action_at = instance['opened_at_s'] if condition is None else observed['arrived_at_s'] if observed is not None else None
        if rechecked is not None:
            status = 'RECHECK_REPORTED_UNCLOSED'
        elif report is not None:
            status = ('ACTION_APPLIED_AWAITING_RECHECK' if completion_arrived else 'ACTION_APPLIED_AWAITING_WORK_ACK') if report['outcome'] == 'APPLIED' else 'ACTION_NO_EFFECT_UNCLOSED'
        elif ids['action'] in issued:
            status = 'ACTION_ISSUED_UNCONFIRMED'
        elif observed is not None:
            status = 'OBSERVATION_REPORTED_UNCLOSED'
        else:
            status = 'OPEN_UNCONFIRMED'
        question.update(workflow_status=status, risk_closed=False,
                        scope='PUBLIC_INSTANCE_WORKFLOW_NOT_ROOT_CAUSE_OR_VERIFIED_RISK_CLOSURE')
        verified = verification.get(instance['id'])
        if verified is not None:
            question.update(closure_status=verified['status'], risk_closed=verified['risk_closed'],
                            question_closed=verified['question_closed'], scope=verified['scope'])
        availability = dict(inspect=instance['opened_at_s'], action=action_at,
                            recheck=report['arrived_at_s'] if report is not None else None)
        allowed = dict(inspect=ids['action'] not in issued,
                       action=condition is None or ready,
                       recheck=report is not None and report['outcome'] == 'APPLIED' and completion_arrived)
        if verified is not None and verified['question_closed']:
            allowed = dict.fromkeys(allowed, False)
        for stage, key in [('inspect', 'task'), ('action', 'action_task'), ('recheck', 'recheck_task')]:
            task = dict(deepcopy(template[key]), id=ids[stage])
            at = availability[stage]
            current = allowed[stage] and at is not None and at <= task['deadline_s']
            gates.append(dict(task_id=task['id'], stage=stage, prerequisites_met=bool(current), already_issued=task['id'] in issued))
            if not current and task['id'] not in issued:
                continue
            _require(at is not None, 'Issued problem stage lost its original availability evidence')
            candidates.append(dict(id=task['id'], kind='intervene' if stage == 'action' else 'inspect', task=task,
                                   available_at_s=at, question_id=instance['id'], source_note=template['source_note'],
                                   issue_cost=template['issue_costs'][stage]))
    selector_policy=program['policy']
    if selector_policy=='defer_once':
        selector_policy='no_human' if not history['question_instances'] else 'fifo'
    compiled = dict(schema='aegisdc-dispatch-policy-program-v3', id=program['id'] + '-compiled',
                    basis=program['basis'], policy=selector_policy, workforce_profile=program['workforce_profile'],
                    candidates=candidates, options={}, resource_budget=program['resource_budget'],
                    intervention_declaration=dict(deepcopy(program['intervention_declaration']),
                        bindings=[row for key, row in actions.items() if key in {c['id'] for c in candidates}]))
    return dict(program=compiled, history=dict(issued=history['issued'], work_feedback=history['work_feedback']),
                question_instances=instances, questions=questions, deferred_triggers=deferred, stage_gates=gates,
                **({'question_lifecycle': lifecycle, 'instance_closure_evaluations': 1} if lifecycle is not None else {}))


def choose_problem_action(frame, program, history, *, closure_program=None):
    from .dispatch_policy import choose_work
    prepared = compile_problem_actions(frame, program, history, closure_program=closure_program)
    selector_policy=prepared['program']['policy']
    choice = choose_work(frame, prepared.pop('program'), prepared.pop('history'))
    choice.update(**prepared, task_generation_scope='PUBLIC_INSTANCE_STAGES_WITH_OWN_ACTION_RECHECK_VERIFICATION'
                  if closure_program is not None else 'PUBLIC_INSTANCE_STAGES_ACTUAL_EXECUTOR_AND_LATER_CLOSURE_GATES_REMAIN')
    if program['policy']=='defer_once':
        choice.update(policy=program['policy'],stage_selector_policy=selector_policy)
    return choice
