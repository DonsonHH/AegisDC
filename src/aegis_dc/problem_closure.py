"""Instance-bound verification from arrived public action, recheck and samples."""
from copy import deepcopy
from fractions import Fraction

from .decision_view import validate_current_frame
from .evidence_ledger import _fields, _finite, _plain_json, _registry, _require, _strings, _text
from .problem_tasks import _templates, open_questions
from .verified_closure import CHECK_FIELDS, _check

PROGRAM_FIELDS = {'schema', 'profile', 'intervention_declaration', 'intervention_feedback'}
PROFILE_FIELDS = {'schema', 'id', 'facility_id', 'nominal_knowledge_id', 'basis', 'time_unit', 'source_note', 'rules'}
RULE_FIELDS = {'id', 'template_id', 'service_id', 'minimum_span_s', 'required_samples', 'recheck_accepted_interval', 'checks'}


def _interval(value, label):
    _require(type(value) is list and len(value) == 2, 'Declare ' + label + ' interval')
    for bound in value:
        _finite(bound, label + ' bound')
    _require(value[0] <= value[1], 'Reversed ' + label + ' interval')


def validate_instance_closure(frame, policy, program):
    """Validate static public criteria without a risk-probability surrogate."""
    frame = validate_current_frame(frame)
    _plain_json(program)
    _fields(program, PROGRAM_FIELDS, 'Instance closure program')
    _require(program['schema'] == 'aegisdc-instance-closure-program-v1', 'Unknown instance closure program')
    _require(program['intervention_declaration'] == policy['intervention_declaration'],
             'Instance closure and policy action declarations differ')
    _require(type(program['intervention_feedback']) is list, 'Declare arrived instance action feedback')
    profile = program['profile']
    _fields(profile, PROFILE_FIELDS, 'Instance closure profile')
    _require(profile['schema'] == 'aegisdc-instance-closure-profile-v1'
             and profile['basis'] == 'synthetic_assumption' and profile['time_unit'] == 's',
             'Declare synthetic instance verification in SI seconds')
    for key in ('id', 'source_note'):
        _text(profile[key], 'Instance closure ' + key)
    _require(profile['facility_id'] == frame['facility_id']
             and profile['nominal_knowledge_id'] == frame['nominal_knowledge']['id'],
             'Instance closure public facility identity differs')
    templates = _templates(frame, policy)
    rules = _registry(profile['rules'], 'Instance closure rule')
    _require(bool(rules), 'Declare applicable instance verification rules')
    sources = {row['id']: row for row in frame['evidence']['static_knowledge']['sources']}
    observables = {row['id']: row for row in frame['evidence']['static_knowledge']['observables']}
    services = {row['id'] for row in frame['nominal_knowledge']['entities'] if row['kind'] == 'service'}
    seen = set()
    for rule in rules.values():
        _fields(rule, RULE_FIELDS, 'Instance closure rule')
        _text(rule['template_id'], 'Instance verification template')
        _text(rule['service_id'], 'Instance verification service')
        _require(rule['template_id'] in templates and rule['template_id'] not in seen,
                 'Unknown/repeated instance verification template')
        seen.add(rule['template_id'])
        template = templates[rule['template_id']]
        # This is an explicit joint verification criterion, not a causal path
        # inferred by joining distinct physical and functional relation graphs.
        _require(rule['service_id'] in services, 'Instance verification requires a declared service entity')
        _finite(rule['minimum_span_s'], 'Instance verification span')
        _require(rule['minimum_span_s'] > 0 and type(rule['required_samples']) is int
                 and rule['required_samples'] >= 2, 'Require two genuine samples and positive verification span')
        _interval(rule['recheck_accepted_interval'], 'Own recheck')
        checks = _registry(rule['checks'], 'Instance verification check')
        roles = set()
        condition_targets = {template[key]['target_id'] for key in ('task', 'action_task', 'recheck_task')}
        condition_targets.add(template['trigger']['target_id'])
        for check in checks.values():
            _fields(check, CHECK_FIELDS, 'Instance verification check')
            roles.add(check['role'])
            _require(check['role'] in {'condition', 'service'}, 'Unknown instance verification role')
            _require(check['target_id'] in condition_targets if check['role'] == 'condition' else
                     check['target_id'] == rule['service_id'], 'Instance verification target outside scope')
            observable = observables.get(check['observable_id'])
            _require(observable is not None and observable['value_type'] == 'number',
                     'Instance verification requires a declared numeric observable')
            _strings(check['source_ids'], 'Instance verification sources')
            for identifier in check['source_ids']:
                source = sources.get(identifier)
                _require(source is not None and check['target_id'] in source['target_ids']
                         and check['observable_id'] in source['observable_ids'],
                         'Instance verification source outside declared coverage')
            _interval(check['accepted_interval'], 'Instance accepted')
        _require(roles == {'condition', 'service'}, 'Require both instance condition and service verification')
    return rules


def assess_instance_closure(frame, policy, history, program):
    """Use each instance's own public completion chain before sampled closure."""
    from .problem_actions import _completion_arrived, _declarations, _feedback, _measurement

    frame = validate_current_frame(frame)
    rules = validate_instance_closure(frame, policy, program)
    _require(program['intervention_feedback'] == history['intervention_feedback'],
             'Instance closure must use the same actually arrived public feedback')
    _, instances, _, _ = open_questions(frame, policy, history)
    inspections, actions = _declarations(frame, policy)
    reports = _feedback(frame, policy, history, actions)
    issued = {row['candidate_id']: row['issued_at_s'] for row in history['issued']}
    current_ids = set(frame['evidence']['current_record_ids'])
    disputed = {identifier for issue in frame['evidence']['conflicts']
                if set(issue['record_ids']) <= current_ids for identifier in issue['record_ids']}
    disputed |= {identifier for issue in frame['evidence']['provenance_issues']
                 if set(issue['record_ids']) & current_ids for identifier in issue['record_ids']}
    by_template = {row['template_id']: row for row in rules.values()}
    questions = []
    for instance in instances:
        rule = by_template.get(instance['template_id'])
        if rule is None:
            continue
        prefix = instance['template_id']
        suffix = '-' + str(instance['slot'])
        action_id = prefix + '/action' + suffix
        recheck_id = prefix + '/recheck' + suffix
        action = reports.get(action_id)
        recheck = _measurement(frame, history, recheck_id, inspections[recheck_id])
        anchor = dict(task_id=recheck_id, record_id=recheck['id'] if recheck is not None else None,
                      passed=False, supporting_record_ids=[])
        checks = []
        trace = []
        status = 'OPEN_UNCONFIRMED'
        if action is not None:
            _require(action['observed_at_s'] >= instance['opened_at_s'], 'Instance action precedes its opening')
            trace.append(dict(event='ACTION_REPORT_AVAILABLE', task_id=action_id,
                observed_at_s=action['observed_at_s'], arrived_at_s=action['arrived_at_s'], outcome=action['outcome']))
            status = 'OPEN_ACTION_FAILED' if action['outcome'] == 'NO_EFFECT' else 'ACTION_REPORTED_AWAITING_WORK_ACK'
            if action['outcome'] == 'APPLIED' and _completion_arrived(history, action):
                status = 'ACTION_COMPLETED_PENDING_VERIFICATION'
                checks = [_check(frame, rule, check, action['observed_at_s']) for check in rule['checks']]
                if recheck is not None:
                    low, high = map(Fraction, rule['recheck_accepted_interval'])
                    ready = (recheck['availability'] == 'current' and recheck['id'] not in disputed
                             and recheck['quality']['status'] == 'bounded'
                             and recheck['provenance']['copied_from_record_id'] is None
                             and issued[recheck_id] >= action['arrived_at_s']
                             and recheck['observed_at_s'] >= action['observed_at_s']
                             and _completion_arrived(history, dict(task_id=recheck_id, observed_at_s=recheck['observed_at_s'])))
                    if ready:
                        value = Fraction(recheck['value'])
                        error = Fraction(recheck['quality']['error_bound'])
                        ready = low <= value - error and value + error <= high
                    anchor.update(passed=bool(ready), supporting_record_ids=[recheck['id']] if ready else [])
                    trace.append(dict(event='OWN_RECHECK_AVAILABLE', task_id=recheck_id, record_id=recheck['id'],
                        observed_at_s=recheck['observed_at_s'], arrived_at_s=recheck['arrived_at_s'],
                        valid_until_s=recheck['valid_until_s'], passed=bool(ready), provenance=deepcopy(recheck['provenance'])))
                if anchor['passed'] and all(check['passed'] for check in checks):
                    status = 'VERIFIED_CLOSED'
                elif all(check['passed'] for check in checks if check['role'] == 'condition'):
                    status = 'SYMPTOM_RETREATED_PENDING_VERIFICATION'
        supporting = {identifier for check in checks for identifier in check['supporting_record_ids']}
        supporting.update(anchor['supporting_record_ids'])
        blocking = {identifier for check in checks for identifier in check['insufficient_record_ids']}
        if recheck is not None and not anchor['passed']:
            blocking.add(recheck['id'])
        for record in frame['evidence']['records']:
            if record['id'] in supporting | blocking:
                trace.append(dict(event='VERIFICATION_RECORD_AVAILABLE' if record['id'] in supporting else 'VERIFICATION_RECORD_BLOCKED',
                    record_id=record['id'], observed_at_s=record['observed_at_s'], arrived_at_s=record['arrived_at_s'],
                    valid_until_s=record['valid_until_s'], provenance=deepcopy(record['provenance'])))
        trace.sort(key=lambda row: (row['arrived_at_s'], row.get('record_id', '')))
        closed = status == 'VERIFIED_CLOSED'
        questions.append(dict(question_id=instance['id'], template_id=prefix, opened_at_s=instance['opened_at_s'],
            rule_id=rule['id'], task_id=action_id, recheck_task_id=recheck_id, as_of_s=frame['as_of_s'], status=status,
            risk_closed=closed, question_closed=closed, physical_restoration_claim=False,
            supporting_record_ids=sorted(supporting), blocking_record_ids=sorted(blocking), disposition_record_ids=[],
            own_recheck=anchor, checks=checks, trace=trace,
            scope='OWN_INSTANCE_ACTION_RECHECK_AND_DECLARED_FINITE_SAMPLED_CRITERIA_ONLY'))
    evaluated = {row['question_id'] for row in questions}
    return dict(schema='aegisdc-instance-closure-assessment-v1', facility_id=frame['facility_id'],
        as_of_s=frame['as_of_s'], questions=questions,
        unevaluated_question_ids=sorted(row['id'] for row in instances if row['id'] not in evaluated),
        private_state_used=False, risk_probability_invented=False)
