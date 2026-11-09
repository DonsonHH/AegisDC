"""Transparent public work choices; execution and plant state remain separate."""
from copy import deepcopy
from .decision_view import validate_current_frame
from .evidence_ledger import _fields,_plain_json,_registry,_require,_text,_finite
from .workforce_dispatch import prepare_work,TASK_FIELDS

PROGRAM_FIELDS={'schema','id','basis','policy','workforce_profile','candidates'}
CANDIDATE_FIELDS={'id','task','available_at_s','question_id','source_note'}
FEEDBACK_FIELDS={'task_id','source_id','observed_at_s','arrived_at_s','status','reason','location_id','origin_id','coverage','basis'}

def _resources(frame,task):
    interface=next(i for i in frame['nominal_knowledge']['work_interfaces'] if i['id']==task['work_interface_id'])
    return {r['worker_id'] for r in task['crew']}|set(interface['tool_ids'])

def _history(frame,history,candidates):
    _require(type(history['issued']) is list and type(history['work_feedback']) is list,'Declare public policy history lists')
    issued={};tasks={}
    for row in history['issued']:
        _fields(row,{'candidate_id','issued_at_s'},'Issued intention history');_text(row['candidate_id'],'Issued candidate id')
        _finite(row['issued_at_s'],'Issued intention time')
        _require(row['candidate_id'] in candidates and row['candidate_id'] not in issued,'Unknown/repeated issued candidate')
        candidate=candidates[row['candidate_id']]
        _require(candidate['available_at_s']<=row['issued_at_s']<=frame['as_of_s'],'Issued intention is not currently available history')
        issued[row['candidate_id']]=row;tasks[candidate['task']['id']]=(candidate,row)
    terminal={}
    locations={e['id'] for e in frame['nominal_knowledge']['entities'] if e['kind']=='location'}
    for row in history['work_feedback']:
        _fields(row,FEEDBACK_FIELDS,'Arrived workforce feedback')
        _text(row['task_id'],'Work feedback task identity');_text(row['status'],'Work feedback status')
        _require(row['task_id'] in tasks,'Feedback must bind an actually issued public task')
        _require(row['source_id']=='workforce-execution-report' and row['origin_id']=='workforce:'+row['task_id']
            and row['coverage']=='THIS_ISSUED_TASK_ONLY' and row['basis']=='SYNTHETIC_FINITE_TIMED_EXECUTION_CHANNEL','Unknown workforce feedback channel')
        _require(row['status'] in {'completed','aborted','rejected','safety_stop_observed'},'Unknown public work status')
        for key in ('observed_at_s','arrived_at_s'):_finite(row[key],'Work feedback '+key)
        _require(tasks[row['task_id']][1]['issued_at_s']<=row['observed_at_s']<=row['arrived_at_s']<=frame['as_of_s'],
            'Work feedback cannot contain pre-issue or future information')
        _require(row['location_id'] is None or row['location_id'] in locations,'Unknown reported work location')
        _require(row['reason'] is None or type(row['reason']) is str and bool(row['reason']),'Invalid reported work reason')
        if row['status']=='rejected':
            _require(row['location_id'] is None and row['reason']=='DECLARED_TASK_ADMISSION_REFUSAL',
                'Rejected task acknowledgment cannot disclose private location or refusal cause')
        if row['status'] in {'completed','aborted','rejected'}:
            _require(row['task_id'] not in terminal or terminal[row['task_id']]==row,'Contradictory terminal work reports')
            terminal[row['task_id']]=row
    occupied=set()
    for candidate,row in tasks.values():
        if candidate['task']['id'] not in terminal:occupied|=_resources(frame,candidate['task'])
    return issued,occupied

def choose_work(frame,program,history,*,intervention_declaration=None,closure_program=None):
    """Choose a declared intention from current public information only."""
    frame=validate_current_frame(frame);_plain_json(program);_plain_json(history);_plain_json(intervention_declaration)
    if type(program) is dict and program.get('schema')=='aegisdc-problem-driven-policy-v1':
        _require(intervention_declaration is None and closure_program is None,
            'Problem-driven actions and closure require a later instance-scoped execution contract')
        from .problem_tasks import choose_problem_work
        return choose_problem_work(frame,program,history)
    if type(program) is dict and program.get('schema')=='aegisdc-problem-driven-policy-v2':
        _require(intervention_declaration is None or intervention_declaration==program['intervention_declaration'],
            'Problem selector and executor intervention declarations differ')
        from .problem_actions import choose_problem_action
        return choose_problem_action(frame,program,history,closure_program=closure_program)
    _require(type(program) is dict,'Declare policy program object')
    _text(program.get('schema'),'Policy program schema')
    version4=type(program) is dict and program.get('schema')=='aegisdc-dispatch-policy-program-v4'
    version3=type(program) is dict and program.get('schema') in {'aegisdc-dispatch-policy-program-v3','aegisdc-dispatch-policy-program-v4'}
    version2=type(program) is dict and program.get('schema') in {'aegisdc-dispatch-policy-program-v2','aegisdc-dispatch-policy-program-v3','aegisdc-dispatch-policy-program-v4'}
    _fields(program,PROGRAM_FIELDS|({'options'} if version2 else set())|({'resource_budget','intervention_declaration'} if version3 else set())|({'evidence_projection'} if version4 else set()),'Dispatch policy program')
    _fields(history,{'issued','work_feedback'},'Public policy history')
    _text(program['schema'],'Policy program schema')
    _require(program['schema'] in {'aegisdc-dispatch-policy-program-v1','aegisdc-dispatch-policy-program-v2','aegisdc-dispatch-policy-program-v3','aegisdc-dispatch-policy-program-v4'}
        and program['basis']=='synthetic_assumption','Declare synthetic policy program')
    _text(program['id'],'Policy program id')
    _text(program['policy'],'Policy name')
    _require(program['policy'] in (({'no_human','fifo','periodic','risk_condition_priority_adapted','one_observation_lookahead'}|({'evidence_consistent_contingent'} if version4 else set())) if version2 else {'no_human','fifo'}),'Policy not implemented in this development slice')
    if version4:
        from .evidence_projection import validate_projection
        validate_projection(frame,program['evidence_projection'])
    if version2 and program['policy'] in {'no_human','fifo'}:_fields(program['options'],set(),'Policy options')
    candidates=_registry(program['candidates'],'Policy candidate');audits=[];task_ids=set()
    for candidate in candidates.values():
        _fields(candidate,CANDIDATE_FIELDS|({'kind'} if version2 else set())|({'issue_cost'} if version3 else set()),'Policy candidate')
        if version2:
            _text(candidate['kind'],'Declared policy intention kind')
            _require(candidate['kind'] in {'inspect','intervene'},'Declare inspection or intervention intention kind')
        for key in ('question_id','source_note'):_text(candidate[key],'Candidate '+key)
        _finite(candidate['available_at_s'],'Candidate availability')
        _require(candidate['available_at_s']>=0,'Negative candidate availability')
        task=candidate['task'];_fields(task,TASK_FIELDS,'Declared policy task');_finite(task['deadline_s'],'Declared task deadline')
        expired=task['deadline_s']<frame['as_of_s']
        # Validate the remaining public capability contract at the current
        # frame. This temporary validation deadline never becomes an intention.
        validation_task=deepcopy(task)
        if expired:validation_task['deadline_s']=frame['as_of_s']
        assessment=prepare_work(frame,program['workforce_profile'],validation_task)
        if expired:
            assessment['public_reasons']=sorted(set(assessment['public_reasons'])|{'DECLARED_DEADLINE_PASSED'})
            assessment['legal_for_planning']=False
        _require(candidate['task']['id'] not in task_ids,'Duplicate declared policy task')
        task_ids.add(candidate['task']['id']);reasons=list(assessment['public_reasons'])
        if candidate['available_at_s']>frame['as_of_s']:reasons.append('NOT_YET_AVAILABLE')
        audits.append(dict(candidate_id=candidate['id'],task_id=candidate['task']['id'],question_id=candidate['question_id'],
            eligible=not reasons,reasons=sorted(set(reasons)),available_at_s=candidate['available_at_s'],
            kind=candidate['kind'] if version2 else 'LEGACY_WORK_INTENTION',public_assessment=assessment))
    audits.sort(key=lambda c:c['candidate_id'])
    if version3:
        _require(intervention_declaration is None or intervention_declaration==program['intervention_declaration'],
            'Selector and executor public intervention declarations differ')
        intervention_declaration=program['intervention_declaration']
    if intervention_declaration is not None:
        from .intervention_execution import prepare_intervention,BIND_FIELDS
        _fields(intervention_declaration,{'schema','profile','bindings'},'Public policy intervention declaration')
        _require(intervention_declaration['schema']=='aegisdc-intervention-program-v1','Unknown public intervention declaration')
        _require(type(intervention_declaration['bindings']) is list,'Declare public intervention bindings')
        bindings={}
        tasks={c['task']['id'] for c in candidates.values()}
        for binding in intervention_declaration['bindings']:
            _fields(binding,BIND_FIELDS,'Public intervention binding')
            _text(binding['task_id'],'Public intervention task identity')
            _require(binding['task_id'] in tasks and binding['task_id'] not in bindings,'Unknown/repeated public intervention task')
            bindings[binding['task_id']]=binding
        for audit in audits:
            candidate=candidates[audit['candidate_id']];binding=bindings.get(candidate['task']['id'])
            if version3:_require((candidate['kind']=='intervene')==(binding is not None),'Task kind and public intervention binding differ')
            if binding is None:continue
            task=deepcopy(candidate['task'])
            if task['deadline_s']<frame['as_of_s']:task['deadline_s']=frame['as_of_s']
            assessment=prepare_intervention(frame,program['workforce_profile'],task,intervention_declaration['profile'],binding)
            audit['intervention_assessment']=assessment
            audit['reasons']=sorted(set(audit['reasons'])|set(assessment['public_reasons']))
            audit['eligible']=not audit['reasons']
    elif version3:_require(all(c['kind']=='inspect' for c in candidates.values()),'Intervention intentions require a public authority declaration')
    lifecycle=None
    if closure_program is not None:
        from .verified_closure import assess_closure
        lifecycle=assess_closure(frame,closure_program)
        closed={q['question_id'] for q in lifecycle['questions'] if q['question_closed']}
        for audit in audits:
            if audit['question_id'] in closed and program['policy']!='periodic':
                audit['reasons'].append('DECLARED_QUESTION_CLOSED');audit['eligible']=False
    due={}
    if program['policy']=='periodic':
        _fields(program['options'],{'schedule'},'Periodic reference options')
        schedule=program['options']['schedule'];_require(type(schedule) is list,'Declare explicit periodic reference list')
        for row in schedule:
            _fields(row,{'candidate_id','due_at_s'},'Periodic inspection reference')
            _text(row['candidate_id'],'Scheduled candidate');_finite(row['due_at_s'],'Periodic due time')
            _require(row['candidate_id'] in candidates and row['candidate_id'] not in due and row['due_at_s']>=0,
                'Unknown/repeated periodic inspection or negative due time')
            _require(candidates[row['candidate_id']]['kind']=='inspect','Periodic reference can schedule inspections only')
            due[row['candidate_id']]=row['due_at_s']
    issued,occupied=_history(frame,history,candidates)
    for audit in audits:
        candidate=candidates[audit['candidate_id']]
        if candidate['id'] in issued:audit['reasons'].append('ALREADY_ISSUED')
        elif _resources(frame,candidate['task'])&occupied:audit['reasons'].append('PUBLIC_UNACKNOWLEDGED_RESOURCE_OCCUPATION')
        if program['policy']=='periodic':
            if candidate['id'] not in due:audit['reasons'].append('NOT_IN_DECLARED_PERIODIC_REFERENCE')
            elif due[candidate['id']]>frame['as_of_s']:audit['reasons'].append('PERIODIC_REFERENCE_NOT_DUE')
        audit['reasons']=sorted(set(audit['reasons']));audit['eligible']=not audit['reasons']
    ledger=None;admission_budget=None
    if version3:
        from .policy_budget import AdmissionBudget
        admission_budget=AdmissionBudget(frame,program,history,candidates)
        ledger=admission_budget.audit(audits)
    eligible=sorted((c for c in audits if c['eligible']),key=lambda c:(c['available_at_s'],c['candidate_id']))
    if program['policy']=='periodic':eligible.sort(key=lambda c:(due[c['candidate_id']],c['candidate_id']))
    selected=eligible[0]['candidate_id'] if program['policy'] in {'fifo','periodic'} and eligible else None
    detail=dict(model_evaluations=dict(risk=0,action_value=0),unmodeled_question_ids=[])
    if program['policy']=='risk_condition_priority_adapted':
        from .risk_condition_policy import evaluate
        selected,detail=evaluate(frame,program['options'],candidates,audits)
    elif program['policy'] in {'one_observation_lookahead','evidence_consistent_contingent'}:
        from .lookahead_policy import evaluate
        options=deepcopy(program['options'])
        projection=program['evidence_projection'] if program['policy']=='evidence_consistent_contingent' else None
        selected,detail=evaluate(frame,options,candidates,audits,admission_budget=admission_budget,intervention_declaration=intervention_declaration,evidence_projection=projection,
            policy_declaration=program if version4 else None,history=history)
    reason=detail.pop('reason',None)
    if reason is None:
        reason=('POLICY_NO_HUMAN' if program['policy']=='no_human' else
            ('EXPLICIT_PERIODIC_INSPECTION_REFERENCE' if program['policy']=='periodic' else 'FIFO_EARLIEST_AVAILABLE') if selected else 'NO_PUBLICLY_ELIGIBLE_CANDIDATE')
    return dict(schema='aegisdc-policy-choice-v1',facility_id=frame['facility_id'],as_of_s=frame['as_of_s'],policy=program['policy'],
        chosen_candidate_id=selected,work_intention=deepcopy(candidates[selected]['task']) if selected else None,
        reason=reason,candidates=audits,
        generated_tour=False,execution_permission=False,scope='PUBLIC_SELECTION_ONLY_ACTUAL_EXECUTOR_GATE_REQUIRED',
        **({'resource_ledger':ledger} if version3 else {}),
        **({'question_lifecycle':lifecycle,'closure_model_evaluations':1} if lifecycle is not None else {}),**detail)
