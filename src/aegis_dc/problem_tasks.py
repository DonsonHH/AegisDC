"""Public evidence triggers professional investigations; fault truth stays absent."""
from copy import deepcopy
from collections import deque

from .evidence_ledger import _fields, _finite, _registry, _require, _strings, _text
from .workforce_dispatch import TASK_FIELDS, prepare_work, validate_profile

PROGRAM_FIELDS = {'schema', 'id', 'basis', 'time_unit', 'policy', 'workforce_profile', 'templates'}
TEMPLATE_FIELDS = {'id', 'question_id', 'domain_ids', 'task', 'trigger', 'max_instances', 'source_note'}
INSTANCE_FIELDS = {'id', 'template_id', 'slot', 'origin_id', 'trigger_record_id', 'opened_at_s'}


def _templates(frame, program):
    version2 = program['schema'] == 'aegisdc-problem-driven-policy-v2'
    _fields(program, PROGRAM_FIELDS | ({'resource_budget', 'inspection_declaration', 'intervention_declaration'}
                                     if version2 else set()), 'Problem-driven policy program')
    _require(program['basis'] == 'synthetic_assumption' and program['time_unit'] == 's',
             'Declare synthetic problem tasks in SI seconds')
    _text(program['id'], 'Problem policy id')
    _text(program['policy'], 'Problem policy')
    _require(program['policy'] in {'fifo', 'no_human'}, 'Declare the transparent investigation reference')
    knowledge = frame['nominal_knowledge']
    validate_profile(program['workforce_profile'], knowledge)
    templates = _registry(program['templates'], 'Problem template')
    _require(0 < len(templates) <= 32, 'Declare one to32 finite problem templates')
    sources = {s['id']: s for s in frame['evidence']['static_knowledge']['sources']}
    observables = {o['id']: o for o in frame['evidence']['static_knowledge']['observables']}
    entities = {e['id'] for e in knowledge['entities']}
    for row in templates.values():
        _fields(row, TEMPLATE_FIELDS | ({'action_task', 'recheck_task', 'action_condition', 'issue_costs'}
                                      if version2 else set()), 'Problem template')
        for name in ('question_id', 'source_note'):
            _text(row[name], 'Problem ' + name)
        _strings(row['domain_ids'], 'Problem domains')
        _require(set(row['domain_ids']) <= set(knowledge['domain_ids']), 'Unknown problem domain')
        _require(type(row['max_instances']) is int and 0 < row['max_instances'] <= 16,
                 'Declare one to16 problem instances per template')
        for key in (('task', 'action_task', 'recheck_task') if version2 else ('task',)):
            _fields(row[key], TASK_FIELDS, 'Professional task template')
            task = deepcopy(row[key])
            _finite(task['deadline_s'], 'Task deadline')
            _require(task['deadline_s'] >= 0, 'Negative task deadline')
            task['deadline_s'] = max(task['deadline_s'], frame['as_of_s'])
            prepare_work(frame, program['workforce_profile'], task)
        if version2:
            _fields(row['issue_costs'], {'inspect', 'action', 'recheck'}, 'Problem stage costs')
            for cost in row['issue_costs'].values():
                _finite(cost, 'Problem stage cost')
                _require(cost >= 0, 'Negative problem stage cost')
            condition = row['action_condition']
            if condition is not None:
                _fields(condition, {'observable_id', 'unit', 'accepted_interval'}, 'Problem action condition')
                observable = observables.get(condition['observable_id'])
                _require(observable is not None and observable['value_type'] == 'number'
                         and observable['unit'] == condition['unit'], 'Action condition requires a declared numeric SI observable')
                bounds = condition['accepted_interval']
                _require(type(bounds) is list and len(bounds) == 2, 'Declare action condition interval')
                for bound in bounds:
                    _finite(bound, 'Action condition bound')
                _require(bounds[0] <= bounds[1], 'Reversed action condition interval')
        trigger = row['trigger']
        _fields(trigger, {'source_ids', 'target_id', 'observable_id', 'equals'}, 'Public problem trigger')
        _strings(trigger['source_ids'], 'Trigger sources')
        _text(trigger['target_id'], 'Trigger target')
        _text(trigger['observable_id'], 'Trigger observable')
        _require(trigger['target_id'] in entities, 'Unknown trigger target')
        observable = observables.get(trigger['observable_id'])
        _require(observable is not None and observable['value_type'] == 'boolean'
                 and type(trigger['equals']) is bool, 'First problem trigger requires a declared boolean claim')
        for identifier in trigger['source_ids']:
            source = sources.get(identifier)
            _require(source is not None and trigger['target_id'] in source['target_ids']
                     and trigger['observable_id'] in source['observable_ids'],
                     'Problem trigger exceeds declared evidence coverage')
    return templates


def _matches(record, trigger):
    return (record['source_id'] in trigger['source_ids']
            and record['target_id'] == trigger['target_id']
            and record['observable_id'] == trigger['observable_id']
            and record['quality']['status'] == 'reported'
            and type(record['value']) is bool and record['value'] == trigger['equals'])


def declared_investigations(frame, program):
    """Register finite measurement slots without opening or issuing any problem."""
    templates = _templates(frame, program)
    return [dict(kind='inspect', task=dict(deepcopy(template['task']),
                 id=template['id'] + '/task-' + str(slot)))
            for template in templates.values() for slot in range(template['max_instances'])]


def declared_problem_tasks(frame, program):
    """Predeclare finite producer bindings; this does not issue any stage."""
    if program['schema'] == 'aegisdc-problem-driven-policy-v1':
        return declared_investigations(frame, program)
    return [dict(kind='intervene' if stage == 'action' else 'inspect',
                 task=dict(deepcopy(template[key]), id=template['id'] + '/' + stage + '-' + str(slot)))
            for template in _templates(frame, program).values()
            for slot in range(template['max_instances'])
            for stage, key in [('inspect', 'task'), ('action', 'action_task'), ('recheck', 'recheck_task')]]


def _service_context(knowledge, target_id):
    """Show one declared functional path per service; infer no capacity or risk."""
    entities = {row['id']: row for row in knowledge['entities']}
    outgoing = {}
    for edge in sorted(knowledge['graphs']['functional'], key=lambda row: row['id']):
        outgoing.setdefault(edge['from'], []).append(edge)
    pending = deque([(target_id, [])])
    visited = {target_id}
    paths = []
    while pending:
        target, edge_ids = pending.popleft()
        if entities[target]['kind'] == 'service':
            paths.append(dict(service_id=target, edge_ids=edge_ids))
        for edge in outgoing.get(target, []):
            if edge['to'] not in visited:
                visited.add(edge['to'])
                pending.append((edge['to'], edge_ids + [edge['id']]))
    return dict(classification='STATIC_FUNCTIONAL_PATHS_NOT_AVAILABLE_CAPACITY',
                target_id=target_id, paths=sorted(paths, key=lambda row: row['service_id']),
                missing_path_is_not_zero_risk=True)


def open_questions(frame, program, history):
    """Retain public opening identities independently of task-stage selection."""
    templates = _templates(frame, program)
    _fields(history, {'issued', 'work_feedback', 'question_instances'} |
            ({'intervention_feedback'} if program['schema'] == 'aegisdc-problem-driven-policy-v2' else set()),
            'Problem policy history')
    _require(type(history['question_instances']) is list, 'Declare public question-instance history')
    records = {r['id']: r for r in frame['evidence']['records']}
    instances = deepcopy(history['question_instances'])
    by_origin = set()
    by_slot = set()
    for row in instances:
        _fields(row, INSTANCE_FIELDS, 'Public problem instance')
        _text(row['template_id'], 'Problem-instance template')
        _require(row['template_id'] in templates, 'Unknown problem-instance template')
        template = templates[row['template_id']]
        _require(type(row['slot']) is int and 0 <= row['slot'] < template['max_instances'],
                 'Problem-instance slot exceeds the declaration')
        _require(row['id'] == row['template_id'] + '/question-' + str(row['slot']),
                 'Problem-instance identity differs from its stable slot')
        for name in ('origin_id', 'trigger_record_id'):
            _text(row[name], 'Problem-instance ' + name)
        _finite(row['opened_at_s'], 'Problem opening')
        record = records.get(row['trigger_record_id'])
        _require(record is not None and _matches(record, template['trigger'])
                 and record['provenance']['origin_id'] == row['origin_id'],
                 'Problem history must bind the originally arrived public claim')
        _require(record['arrived_at_s'] <= row['opened_at_s'] <= frame['as_of_s']
                 and (record['valid_until_s'] is None or row['opened_at_s'] < record['valid_until_s']),
                 'Problem history contains a future or unavailable opening')
        origin = (row['template_id'], row['origin_id'])
        slot = (row['template_id'], row['slot'])
        _require(origin not in by_origin and slot not in by_slot, 'Duplicate problem origin or slot')
        by_origin.add(origin)
        by_slot.add(slot)
    for identifier in templates:
        slots = sorted(slot for template, slot in by_slot if template == identifier)
        _require(slots == list(range(len(slots))), 'Problem slots must preserve their opening order')

    disputed = {identifier for issue in frame['evidence']['conflicts'] + frame['evidence']['provenance_issues']
                for identifier in issue['record_ids']}
    deferred = []
    for template in templates.values():
        for record in sorted(records.values(), key=lambda r: (r['arrived_at_s'], r['id'])):
            if record['availability'] != 'current' or record['id'] in disputed or not _matches(record, template['trigger']):
                continue
            origin = (template['id'], record['provenance']['origin_id'])
            if origin in by_origin:
                continue
            slot = sum(identifier == template['id'] for identifier, _ in by_slot)
            if slot >= template['max_instances']:
                deferred.append(dict(template_id=template['id'], record_id=record['id'],
                                     reason='DECLARED_QUESTION_CAPACITY_EXHAUSTED'))
                continue
            instances.append(dict(id=template['id'] + '/question-' + str(slot), template_id=template['id'],
                                  slot=slot, origin_id=origin[1], trigger_record_id=record['id'],
                                  opened_at_s=frame['as_of_s']))
            by_origin.add(origin)
            by_slot.add((template['id'], slot))

    questions = []
    for row in instances:
        template = templates[row['template_id']]
        record = records[row['trigger_record_id']]
        questions.append(dict(deepcopy(row), catalog_question_id=template['question_id'],
                              domain_ids=deepcopy(template['domain_ids']),
                              status='OPEN_DISPUTED' if record['id'] in disputed else
                              'OPEN_UNCONFIRMED' if record['availability'] == 'current' else 'OPEN_STALE',
                              quantification='UNMODELED_IN_THIS_FACTORY', fault_probability=None,
                              expected_service_deficit_time_s=None, time_unit='s',
                              service_context=_service_context(frame['nominal_knowledge'], template['task']['target_id']),
                              scope='PUBLIC_CLAIM_REQUIRES_INVESTIGATION_NOT_FAULT_DIAGNOSIS'))
    return templates, instances, questions, deferred


def choose_problem_work(frame, program, history):
    """Compile arrived public problem instances into the existing selection gate."""
    templates, instances, questions, deferred = open_questions(frame, program, history)
    candidates = []
    for row in instances:
        template = templates[row['template_id']]
        task = dict(deepcopy(template['task']), id=template['id'] + '/task-' + str(row['slot']))
        candidates.append(dict(id=task['id'], kind='inspect', task=task, available_at_s=row['opened_at_s'],
                               question_id=row['id'], source_note=template['source_note']))
    from .dispatch_policy import choose_work
    compiled = dict(schema='aegisdc-dispatch-policy-program-v2', id=program['id'] + '-compiled',
                    basis=program['basis'], policy=program['policy'],
                    workforce_profile=program['workforce_profile'], candidates=candidates, options={})
    choice = choose_work(frame, compiled, dict(issued=history['issued'], work_feedback=history['work_feedback']))
    choice.update(question_instances=instances, questions=questions, deferred_triggers=deferred,
                  task_generation_scope='FINITE_PUBLIC_INVESTIGATION_RULES_ONLY_NO_PHYSICAL_EFFECT_OR_CLOSURE')
    return choice
