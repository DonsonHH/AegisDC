"""Finite, instance-bound intake decisions from a public V6 frame."""
from bisect import bisect_left
from copy import deepcopy
from fractions import Fraction

from .evidence_ledger import _fields, _finite, _require
from .intervention_execution import _authorization
from .policy_budget import DIMENSIONS
from .workforce_dispatch import prepare_work


SCHEMA = 'aegisdc-problem-driven-policy-v3'
ACTION_SCHEMAS = {'aegisdc-problem-driven-policy-v2', SCHEMA}
STAGES = {'inspect': 'task', 'action': 'action_task', 'recheck': 'recheck_task'}


def number(value):
    _finite(value, 'Public intake model number')
    return Fraction(str(value))


def validate_model(program):
    model = program['value_model']
    _fields(model, {'schema', 'template_id', 'clock_s', 'service_window_s', 'forecast_demand',
                    'first_travel_s', 'local_travel_s', 'flow_limits', 'order_likelihood', 'variants'},
            'Public intake value declaration')
    _require(model['schema'] == 'aegisdc-intake-value-v1' and len(program['templates']) == 1,
             'Declare one versioned intake problem')
    template = program['templates'][0]
    _require(template['id'] == model['template_id'] and template['action_condition'] is None
             and template['trigger']['target_id'] == 'intake_pump'
             and template['trigger']['observable_id'] == 'problem_reported'
             and template['action_task']['target_id'] == 'filter', 'Intake producer or direct action differs')
    profile = program['inspection_declaration']
    models = {m['model']['id']: m for m in profile['nonfixed_profile']['models']}
    for binding in profile['bindings']:
        m = models[binding['model_id']]
        _require((m['target_id'], m['source_id'], m['observable_id'], m['model']['kind'],
                  m['model']['signal_id'], m['model']['unit']) ==
                 ('intake_pump','portable-intake-meter','flow','numeric','intake_pump.volume_flow','m3/s')
                 and binding['tool_id'] == 'tool_flow_meter', 'Portable intake observation binding differs')
    ops = {op['id']: op for op in program['intervention_declaration']['profile']['operations']}
    for binding in program['intervention_declaration']['bindings']:
        op = ops[binding['operation_id']]
        _require(op['kind'] == 'clean_filter' and op['target_id'] == 'filter' and op['unit'] == '1'
                 and number(binding['setting']) == 1, 'Forecast only supports the named residual filter operation')
    clock = list(map(number, model['clock_s']))
    limits = list(map(number, model['flow_limits']))
    start, end = map(number, model['service_window_s'])
    _require(0 < len(clock) <= 128 and clock == sorted(set(clock)) and clock[0] == 0
             and 0 <= start < end <= clock[-1] and number(model['forecast_demand']) > 0, 'Invalid public intake horizon')
    _require(len(limits) == 4 and limits == sorted(set(limits)) and limits[0] == 0
             and number(model['first_travel_s']) >= 0 and number(model['local_travel_s']) == 0,
             'Invalid intake flow regimes or travel')
    likelihood = list(map(number, model['order_likelihood']))
    _require(len(likelihood) == 3 and all(0 <= x <= 1 for x in likelihood), 'Invalid work-order likelihood')
    _require(type(model['variants']) is list and 0 < len(model['variants']) <= 8, 'Declare finite intake sensitivity variants')
    for variant in model['variants']:
        _fields(variant, {'prior_weights', 'low_given_cause'}, 'Intake sensitivity variant')
        prior = list(map(number, variant['prior_weights']))
        low = list(map(number, variant['low_given_cause']))
        _require(len(prior) == len(low) == 3 and all(x >= 0 for x in prior)
                 and sum(prior) > 0 and all(0 <= x <= 1 for x in low), 'Invalid cause or report weights')


def report_class(record, now, disputed, model):
    if record is None:
        return 'PENDING'
    if record['id'] in disputed or record['provenance']['copied_from_record_id'] is not None:
        return 'CONFLICT'
    if record['arrived_at_s'] > now:
        return 'PENDING'
    if record['valid_until_s'] is not None and now >= record['valid_until_s']:
        return 'EXPIRED'
    if record['availability'] == 'missing' or record['value'] is None:
        return 'UNAVAILABLE'
    if record['quality']['status'] != 'bounded':
        return 'INCONCLUSIVE'
    left, cut, normal, outer = map(number, model['flow_limits'])
    value = number(record['value'])
    error = number(record['quality']['error_bound'])
    lo, hi = value-error, value+error
    if hi < left or lo > outer:
        return 'UNMODELED'
    if left <= lo and hi < cut:
        return 'LOW'
    if cut <= lo and hi <= normal:
        return 'NORMAL'
    if normal < lo and hi <= outer:
        return 'ZERO_SUPPORT'
    return 'INCONCLUSIVE'


def masses(model):
    laws = []
    for variant in model['variants']:
        prior = [number(p)*number(l) for p,l in zip(variant['prior_weights'],model['order_likelihood'])]
        if not sum(prior):
            return []
        posterior = [p/sum(prior) for p in prior]
        low = [p*number(l) for p,l in zip(posterior,variant['low_given_cause'])]
        laws.append((posterior, {'LOW':low, 'NORMAL':[p-l for p,l in zip(posterior,low)]}))
    return laws


def service_loss(model, weights, completion=None):
    start, end = map(number, model['service_window_s'])
    untreated = end-start if completion is None else min(end-start,max(Fraction(0), completion-start))
    return number(model['forecast_demand'])*(weights[0]*untreated + weights[1]*(end-start))


def continuation(model, laws, completion):
    table = {}
    for outcome in ('LOW','NORMAL'):
        keep = []
        for _, groups in laws:
            group = groups[outcome]
            keep.append(bool(sum(group) and completion is not None and
                             service_loss(model,group,completion) < service_loss(model,group)))
        table[outcome] = 'ACT' if keep and all(keep) else 'DEFER'
    return table


def planned_chain(frame, program, instance, stages, now, local, audits, ledger):
    """Price as-yet unissued stages. A future receipt's release is not an issue."""
    model = program['value_model']
    template = program['templates'][0]
    wf = program['workforce_profile']
    clock = list(map(number, model['clock_s']))
    inspections = {x['task_id']:x for x in program['inspection_declaration']['bindings']}
    intervention = program['intervention_declaration']
    action_bindings = {x['task_id']:x for x in intervention['bindings']}
    ops = {x['id']:x for x in intervention['profile']['operations']}
    grants = {x['id']:x for x in intervention['profile']['authorizations']}
    interfaces = {x['id']:x for x in frame['nominal_knowledge']['work_interfaces']}
    remaining = {k:number(ledger['remaining'][k]) for k in DIMENSIONS}
    envelope = dict.fromkeys(DIMENSIONS,Fraction(0))
    actual = dict.fromkeys(DIMENSIONS,Fraction(0))
    first_release = number(instance['opened_at_s'])
    at = number(now)
    rows, reasons = [], []
    completion = None
    for i,stage in enumerate(stages):
        task = deepcopy(template[STAGES[stage]])
        task['id'] = ident = f"{template['id']}/{stage}-{instance['slot']}"
        audit = audits.get(ident)
        if i == 0 and (not audit or not audit['eligible']):
            reasons.extend(audit['reasons'] if audit else ['STAGE_UNAVAILABLE'])
        deadline = number(task['deadline_s'])
        # Native prepare_work accepts a present/future deadline only.
        planning_task = dict(task,deadline_s=max(task['deadline_s'],frame['as_of_s']))
        reasons.extend(prepare_work(frame,wf,planning_task)['public_reasons'])
        interface_id = task['work_interface_id']
        if i == 0 and stage == 'recheck' and audit:
            release = number(audit['available_at_s'])
        else:
            release = first_release if stage != 'recheck' else report_at
        travel = number(model['local_travel_s'] if local or i else model['first_travel_s'])
        duration = travel + number(wf['access_check_s']) + number(wf['work_times_s'][interface_id])
        finish = at+duration
        workers, tools = len(task['crew']), len(interfaces[interface_id]['tool_ids'])
        for key, count in [('person_s',workers),('tool_s',tools)]:
            envelope[key] += max(Fraction(0),deadline-release)*count
            actual[key] += duration*count
        fee = number(template['issue_costs'][stage])
        envelope['cost'] += fee
        actual['cost'] += fee
        if finish > deadline or at > deadline:
            reasons.append('STAGE_DEADLINE')
        if stage == 'action':
            completion = finish
            binding = action_bindings[ident]
            op, grant = ops[binding['operation_id']], grants[binding['authorization_id']]
            if not all(_authorization(op,grant,t) for t in (at,finish)):
                reasons.append('ACTION_AUTHORITY')
            latency = intervention['profile']['feedback_latency_s']
        else:
            latency = inspections[ident]['arrival_latency_s']
        report_at = finish+number(latency)
        ready = max(report_at,finish+number(wf['feedback_latency_s']))
        pos = bisect_left(clock,ready)
        rows.append(dict(stage=stage,start=float(at),finish=float(finish),report=float(report_at),release=float(release)))
        if pos == len(clock):
            reasons.append('REPORT_OUTSIDE_CLOCK')
            break
        at = clock[pos]
    reasons += [key for key in DIMENSIONS if envelope[key] > remaining[key]]
    return dict(feasible=not reasons,reasons=sorted(set(reasons)),stages=rows,envelope=envelope,
                actual=tuple(actual[k] for k in DIMENSIONS),completion=completion)


def evaluate_root(model, single, direct, chain):
    laws = masses(model)
    table = continuation(model,laws,chain['completion'])
    requires_action = 'ACT' in table.values()
    can_measure = single['feasible'] and (not requires_action or chain['feasible'])
    scores = []
    for prior, groups in laws:
        chosen_mass = sum(sum(groups[o]) for o in table if table[o]=='ACT')
        measured_loss = sum(service_loss(model,g,chain['completion'] if table[o]=='ACT' else None)
                            for o,g in groups.items())
        work = tuple(a+chosen_mass*(b-a) for a,b in zip(single['actual'],chain['actual']))
        scores.append(dict(DEFER=(service_loss(model,prior),Fraction(0),Fraction(0),Fraction(0)),
            DIRECT=(service_loss(model,prior,direct['completion']),*direct['actual']),
            MEASURE=(measured_loss,*work)))
    def preferable(a,b):
        return bool(scores) and all(x[a]<=x[b] for x in scores) and any(x[a]<x[b] for x in scores)
    root = 'DIRECT' if direct['feasible'] and preferable('DIRECT','DEFER') else 'DEFER'
    if can_measure and preferable('MEASURE','DEFER') and (not direct['feasible'] or preferable('MEASURE','DIRECT')):
        root='MEASURE'
    return root,table,scores



def public_numbers(value):
    if isinstance(value, Fraction):
        return str(value)
    if isinstance(value, dict):
        return {key:public_numbers(item) for key,item in value.items()}
    if isinstance(value, (list,tuple)):
        return [public_numbers(item) for item in value]
    return value


def choose_intake(frame, program, history, compiled, choice):
    """Limit choice to native eligible instances and task-local feedback."""
    model = program['value_model']
    now = frame['as_of_s']
    audits = {row['candidate_id']:row for row in choice['candidates']}
    candidates = {row['id']:row['task'] for row in compiled['candidates']}
    declared = {b['task_id']:b for b in program['inspection_declaration']['bindings']}
    records = {r['id']:r for r in frame['evidence']['records']}
    disputed = {i for issue in frame['evidence']['conflicts']+frame['evidence']['provenance_issues'] for i in issue['record_ids']}
    issued = {r['candidate_id'] for r in history['issued']}
    terminal = {r['task_id']:r for r in history['work_feedback'] if r['status'] in {'completed','aborted','rejected'}}
    reports = {r['task_id']:r for r in history['intervention_feedback']}
    laws = masses(model)
    ledger = choice['resource_ledger']
    decisions = []
    selected = None
    for instance,question in zip(choice['question_instances'],choice['questions']):
        prefix = instance['template_id'] + '/'
        suffix = '-' + str(instance['slot'])
        ids = {stage:prefix+stage+suffix for stage in STAGES}
        def plan(stages,local):
            return planned_chain(frame,program,instance,stages,now,local,audits,ledger)
        def eligible(stage):
            return audits.get(ids[stage],{}).get('eligible',False)
        info = dict(question_id=instance['id'],order_origin=instance['origin_id'],
                    posterior=[prior for prior,_ in laws],tables_evaluated=0,branch_scores_evaluated=0)
        stage=None
        if question.get('question_closed'):
            state='CLOSED'
        elif ids['recheck'] in issued:
            state='RECHECK_ISSUED'
        elif ids['action'] in issued:
            reply=reports.get(ids['action'])
            if reply and reply['outcome']=='NO_EFFECT':
                state='ACTION_NO_EFFECT'
            elif eligible('recheck'):
                follow=plan(['recheck'],True)
                state='RECHECK' if follow['feasible'] else 'RECHECK_BLOCKED'
                if follow['feasible']:stage='recheck'
                info['plan']=follow
            else:
                state='AWAIT_ACTION'
        elif ids['inspect'] in issued:
            own=declared[ids['inspect']]
            record=records.get(own['record_id'])
            outcome=report_class(record,now,disputed,model)
            feedback=terminal.get(ids['inspect'])
            if feedback is not None and feedback['status']!='completed':
                outcome='UNAVAILABLE'
            elif record is not None and (feedback is None or feedback['observed_at_s']!=record['observed_at_s']):
                outcome='PENDING'
            state=outcome
            if outcome in ('LOW','NORMAL'):
                path=plan(['action','recheck'],True)
                table=continuation(model,laws,path['completion'])
                info.update(continuation=table,plan=path,tables_evaluated=len(laws),
                            branch_scores_evaluated=2*len(laws))
                if not laws or any(not sum(groups[outcome]) for _,groups in laws):
                    state='ZERO_SUPPORT'
                elif table[outcome]=='ACT' and path['feasible'] and eligible('action'):
                    state='ACT_'+outcome
                    stage='action'
                else:
                    state='DEFER_'+outcome
            info.update(observation=outcome,record_id=record['id'] if record else None)
        elif records[instance['trigger_record_id']]['availability']!='current':
            state='EXPIRED'
        elif not laws:
            state='ZERO_SUPPORT'
        else:
            single=plan(['inspect'],False)
            direct=plan(['action','recheck'],False)
            chain=plan(['inspect','action','recheck'],False)
            state,table,scores=evaluate_root(model,single,direct,chain)
            stage={'MEASURE':'inspect','DIRECT':'action','DEFER':None}[state]
            info.update(continuation=table,scores=scores,plans=dict(single=single,direct=direct,chain=chain),
                        tables_evaluated=len(laws),branch_scores_evaluated=2*len(laws))
        info['state']=state
        info['requested_candidate']=ids[stage] if stage is not None else None
        if selected is None and stage is not None and eligible(stage):
            selected=ids[stage]
        decisions.append(public_numbers(info))
    choice.update(policy=program['policy'],chosen_candidate_id=selected,
        work_intention=deepcopy(candidates[selected]) if selected else None,
        reason=next((r['state'] for r in decisions if selected and r['requested_candidate']==selected),
                    decisions[0]['state'] if decisions else 'NO_INSTANCE'),
        intake_decisions=decisions,model_evaluations=dict(risk=len(laws)*len(decisions),
            action_value=sum(r['tables_evaluated'] for r in decisions)),
        forecast_branch_count=sum(r['branch_scores_evaluated'] for r in decisions))
    return choice

