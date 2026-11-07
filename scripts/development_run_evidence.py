"""Verify returned facility originals and describe development opportunities without policy calls."""

from math import fsum, isclose, isfinite

from registered_comparison import DOMAINS, require

TOL=1e-8
METRICS=('demand_service_unit_s','delivered_service_unit_s','service_deficit_time_s',
    'worker_travel_person_s','worker_work_person_s','worker_wait_person_s','access_check_person_s',
    'rendezvous_wait_person_s','queue_wait_person_s','tool_occupation_tool_s')
RECORD_FIELDS=('id','source_id','target_id','observable_id','unit','value','observed_at_s',
               'arrived_at_s','valid_until_s','quality','provenance')
TERMINAL={'completed','aborted','rejected'}
OP_PARAMETERS={'restore_network_capacity':'network_service_capacity','clean_filter':'filter_resistance_multiplier'}


def _raw_record(row):
    return {key:row[key] for key in RECORD_FIELDS}


def _same(a,b,message):
    require(type(a) in (int,float) and type(b) in (int,float) and isfinite(a) and isfinite(b)
            and isclose(a,b,rel_tol=0,abs_tol=TOL),message)


def _registry(rows,key):
    result={row[key]:row for row in rows}
    require(len(result)==len(rows),'Repeated returned identity: '+key)
    return result


def _records(program,run,frame,at):
    from aegis_dc.decision_view import validate_current_frame
    validate_current_frame(frame)
    require(frame['as_of_s']==at and frame['nominal_knowledge']==program['nominal_knowledge']
            and frame['requests']==program['preparation_requests'],'Decision frame exceeds its public input role')
    evidence=frame['evidence']
    require(evidence['as_of_s']==at,'Public evidence has a different clock')
    source_records=_registry(program['evidence_ledger']['records']+run['inspection_public_snapshot']['records'],'id')
    channels=_registry(program['sensor_program']['profile']['channels'],'id')
    sensor={f"{row['measurement_id']}:{row['poll_index']}":row for row in run['policy_sensor_private_audit']}
    for name,record in _registry(evidence['records'],'id').items():
        require(record['observed_at_s']<=record['arrived_at_s']<=at,'Future evidence leaked into a decision')
        if name in source_records:
            require(_raw_record(record)==_raw_record(source_records[name]),'Arrived input or inspection record changed')
            continue
        channel_id,_,index=name.rpartition(':')
        channel=channels[channel_id]
        origin=sensor[f"{channel['measurement_id']}:{index}"]
        require(channel['transform']=='identity' and not origin['private_reading_dropout']
                and record['source_id']==channel['source_id'] and record['observable_id']==channel['observable_id']
                and record['observed_at_s']==origin['source_observed_at_s'],
                'Public fixed observation does not match declared acquisition')
        require(origin['private_bias']==origin['private_noise_bound']==0,
                'Saved development sensor audit supports only the frozen zero-error fixed channel')
        _same(record['arrived_at_s'],record['observed_at_s']+channel['delay_s'],'Fixed observation delivery differs')
        _same(record['value'],origin['private_signal'],'Fixed observation differs from its acquisition')


def _opportunity(candidates,interfaces,budget,decision):
    choice,history=decision['choice'],decision['history']
    at=decision['frame']['as_of_s']
    issued=_registry(history['issued'],'candidate_id')
    terminal={row['task_id'] for row in history['work_feedback'] if row['status'] in TERMINAL}

    def resources(candidate):
        task=candidate['task']
        return {f"worker:{role['worker_id']}" for role in task['crew']} | {
            'tool:'+tool for tool in interfaces[task['work_interface_id']]['tool_ids']}

    occupied=set().union(*(resources(candidates[key]) for key in issued if candidates[key]['task']['id'] not in terminal))
    expected={}
    for name,row in candidates.items():
        task=row['task']
        span=task['deadline_s']-row['available_at_s']
        expected[name]=dict(person_s=span*len(task['crew']),
            tool_s=span*len(interfaces[task['work_interface_id']]['tool_ids']),cost=row['issue_cost'])
    spent={key:fsum(expected[name][key] for name in issued) for key in ('person_s','tool_s','cost')}
    require(all(spent[k]<=budget[k]+TOL for k in spent),'Common issue budget exceeded')
    ledger=choice['resource_ledger']
    require(ledger['spent_or_reserved']==spent and ledger['remaining']=={k:budget[k]-v for k,v in spent.items()}
            and ledger['cost_unit']==budget['cost_unit'] and not ledger['terminal_report_refund'],
            'Common admission ledger differs')
    audits=_registry(choice['candidates'],'candidate_id')
    require(set(audits)==set(candidates),'Policy audit changed the shared candidate set')
    eligible,contention=[],[]
    for name,audit in audits.items():
        declared=candidates[name]
        task=declared['task']
        require(audit['task_id']==task['id'] and audit['kind']==declared['kind']
                and audit['declared_resource_reservation']==expected[name],'Declared candidate or reservation differs')
        blocked=bool(resources(declared)&occupied) and name not in issued
        if blocked:
            contention.append(name)
        if (audit['public_assessment']['legal_for_planning']
                and audit.get('intervention_assessment',{}).get('legal_for_planning',True)
                and declared['available_at_s']<=at<=task['deadline_s'] and name not in issued and not blocked
                and all(spent[k]+expected[name][k]<=budget[k]+TOL for k in spent)):
            eligible.append(name)
    return sorted(eligible),sorted(contention),audits


def _decisions(model,program,run,arm):
    interfaces={row['id']:row for domain in model['domains'] for row in domain['work_interfaces']}
    policy=program['policy_program']
    budget=policy['resource_budget']
    candidates=_registry(policy['candidates'],'id')
    decisions=run['policy_public_decisions']
    require([row['frame']['as_of_s'] for row in decisions]==program['decision_times_s'],
            'Decision clock or count differs')
    issued=[]
    opportunities=[]
    for decision,at in zip(decisions,program['decision_times_s'],strict=True):
        require(set(decision)=={'frame','history','choice'},'Unexpected private decision record fields')
        frame,history,choice=(decision[key] for key in ('frame','history','choice'))
        require(set(history)=={'issued','work_feedback'},'Unexpected private policy history fields')
        _records(program,run,frame,at)
        require(history['issued']==issued
                and history['work_feedback']==[row for row in run['workforce_public_feedback'] if row['arrived_at_s']<=at],
                'Decision saw different issue history or workforce feedback')
        require(choice['policy']==arm and choice['as_of_s']==at and choice['execution_permission'] is False,
                'Policy identity or execution authority changed')
        eligible,contention,audits=_opportunity(candidates,interfaces,budget,decision)
        selected=choice['chosen_candidate_id']
        if selected is None:
            require(choice['work_intention'] is None,'Deferral invented work')
        else:
            require(selected in eligible and audits[selected]['eligible']
                    and choice['work_intention']==candidates[selected]['task'],'Issued task is outside common eligibility')
            require(arm!='no_human' and (arm!='periodic' or (candidates[selected]['kind']=='inspect' and at>=1)),
                    'Reference arm violated its declared behavior')
            issued.append(dict(candidate_id=selected,issued_at_s=at))
        opportunities.append(dict(time_s=at,common_preference_eligible=eligible,resource_contention=contention,
            chosen=selected,reason=choice['reason']))
    tasks=_registry(run['work_records'],'id')
    require(set(tasks)=={candidates[row['candidate_id']]['task']['id'] for row in issued},
            'Returned work did not match the public issues')
    entities=_registry(model['entities'],'id')
    for row in issued:
        declared=candidates[row['candidate_id']]['task']
        task=tasks[declared['id']]
        require({k:task[k] for k in declared}==declared and task['issued_at_s']==row['issued_at_s'],
                'Actual work changed the issued task')
        interface=interfaces[task['work_interface_id']]
        crew=task['crew']
        require(all(role['qualification_id'] in entities[role['worker_id']]['qualification_ids'] for role in crew)
                and any(role['worker_id']==task['tool_carrier_id'] and role['qualification_id']==interface['qualification_id']
                        for role in crew)
                and set(interface['tool_ids'])<=set(entities[task['tool_carrier_id']]['tool_ids'])
                and task['target_id'] in interface['target_ids'],'Unqualified crew or tools')
    account=run['policy_public_resource_ledger']
    expected={key:0 for key in ('person_s','tool_s','cost')}
    for row in issued:
        c=candidates[row['candidate_id']]
        t=c['task']
        span=t['deadline_s']-c['available_at_s']
        expected['person_s']+=span*len(t['crew'])
        expected['tool_s']+=span*len(interfaces[t['work_interface_id']]['tool_ids'])
        expected['cost']+=c['issue_cost']
    require(account['spent_or_reserved']==expected and all(expected[key]<=budget[key]+TOL for key in expected),
            'Final actual issue ledger exceeded its common envelope')
    return opportunities,tasks,interfaces,entities,expected


def _effects(program,run,tasks,trace):
    by_time={row['time_s']:row['domains'] for row in trace}
    intervention=program['intervention_program']
    bindings=_registry(intervention['bindings'],'task_id')
    operations=_registry(intervention['profile']['operations'],'id')
    grants=_registry(intervention['profile']['authorizations'],'id')
    effects=_registry(run['intervention_private_audit']['events'],'task_id')
    for name,audit in effects.items():
        task,binding=tasks[name],bindings[name]
        operation=operations[binding['operation_id']]
        require(audit['operation_id']==operation['id'] and audit['task_status']==task['status'],
                'Effect does not match actual work')
        if audit['outcome']=='APPLIED':
            at=audit['applied_at_s']
            grant=grants[binding['authorization_id']]
            target=next(row for row in program['nominal_knowledge']['entities'] if row['id']==task['target_id'])
            require(task['status']=='completed' and task['completed_at_s']==at==audit['observed_at_s']
                    and task['work_started_at_s']+operation['minimum_work_s']<=at
                    and grant['starts_at_s']<=task['issued_at_s']<=at<grant['expires_at_s']
                    and operation['id'] in grant['operation_ids'] and task['target_id'] in grant['target_ids']
                    and audit['parameter_id']==OP_PARAMETERS[operation['kind']]
                    and audit['new_value']==binding['setting']
                    and target['nominal_location_id'] not in by_time[at]['space_access']['blocked_location_ids'],
                    'Unauthorized actual effect or effect under blocked access')
        else:
            require(audit['outcome']=='NO_EFFECT' and 'applied_at_s' not in audit,'Unclassified actual effect')
    applied=[row for row in effects.values() if row['outcome']=='APPLIED']
    event_effects=[{k:v for k,v in row.items() if k!='kind'} for row in run['events']
                  if row['kind']=='completed_research_intervention']
    require(event_effects==applied and not any(row['kind']=='engineering_control_command' for row in run['events']),
            'Actual physical changes differ from the authorized effect audit')
    require(all(row['risk_closed'] is False for row in run['intervention_public_feedback']),
            'Completion feedback claimed verified risk closure')
    return [row for row in effects.values() if row['outcome']=='APPLIED']


def check_run(document,run,trace,balances):
    model,program=(document[k] for k in ('model','dispatch_program'))
    arm=program['policy_program']['policy']
    horizon=document['duration_s']
    inputs=run['inputs']
    require(inputs['dispatch_program']==program and inputs['duration_s']==horizon
            and inputs['maximum_step_s']==document['maximum_step_s']
            and inputs['boundary_events']==document.get('boundary_events',[])
            and not inputs['work_requests'] and 'action_commands' not in inputs,
            'Execution differs from registered physical or decision inputs')
    require(run['state_visibility']=='PRIVATE_PLANT_EVALUATOR_ONLY'
            and run['dispatch_interface']=='PUBLIC_SELECTION_WITH_PRIVATE_EXECUTION'
            and run['model_calls']==run['training_calls']==0 and run['field_calibration']=='PENDING',
            'Private/public runtime or scope changed')
    opportunities,tasks,interfaces,entities,spent=_decisions(model,program,run,arm)
    require(len(trace)==len(balances)+1 and trace[0]['time_s']==0 and trace[-1]['time_s']==horizon,
            'Returned trace and balance endpoints differ')
    initial_demand=next(row['value'] for row in model['parameters'] if row['id']=='service_demand')
    demand_events=[row for row in document.get('boundary_events',[]) if row['parameter_id']=='service_demand']
    require(not demand_events,'This registered development scope uses no timed demand changes')
    contributions={key:[] for key in METRICS}
    for left,right,row in zip(trace[:-1],trace[1:],balances,strict=True):
        start,end=left['time_s'],right['time_s']
        require(row['start_s']==start and row['end_s']==end and 0<end-start<=document['maximum_step_s']+TOL
                and set(left['domains'])==DOMAINS,'Noncontiguous or incomplete facility trace')
        domains=left['domains']
        dt=end-start
        service=domains['it_service']
        demand,delivered=service['demand'],service['delivered']
        require(demand==initial_demand,'Offered demand was changed by the policy or plant')
        require(min(row['capacity_slack_W'].values())>=-1e-6,'Electrical capacity was exceeded')
        require(0<=delivered<=demand and delivered<=min(service['capacities'].values())+TOL,
                'Service exceeds demand or actual capacity')
        for k,value in (('demand_service_unit_s',demand*dt),('delivered_service_unit_s',delivered*dt),
                        ('service_deficit_time_s',(demand-delivered)/demand*dt if demand else 0)):
            _same(row[k],value,'Balance service disagrees with physical trace')
        require(domains['control_monitoring']['compute_permitted']
                or domains['power']['actual_powers_W']['compute']==0,'Execution overrode local protection')
        crew=domains['people_tools_work']
        active=set(crew['active_requests'])
        require(not active&set(crew['queued_requests']),'Work is both active and queued')
        blocked=set(domains['space_access']['blocked_location_ids'])
        for name,worker in crew['workers'].items():
            if worker['request_id'] is not None:
                task=tasks[worker['request_id']]
                require(task['id'] in active and name in {role['worker_id'] for role in task['crew']},
                        'Worker has conflicting work reservation')
            if worker['status']=='working':
                require(worker['location_id'] is not None and worker['location_id'] not in blocked,
                        'Worker performed professional work under blocked access')
        for tool,record in crew['tools'].items():
            if record['reserved_by'] is not None:
                task=tasks[record['reserved_by']]
                require(task['id'] in active and tool in interfaces[task['work_interface_id']]['tool_ids'],
                        'Tool has conflicting work reservation')
        for task_id in active:
            task=tasks[task_id]
            require(all(crew['workers'][role['worker_id']]['request_id']==task_id for role in task['crew'])
                    and all(crew['tools'][tool]['reserved_by']==task_id
                            for tool in interfaces[task['work_interface_id']]['tool_ids']),
                    'Worker or tool has overlapping or missing reservations')
        _same(row['worker_wait_person_s'],fsum(row[k] for k in (
            'access_check_person_s','rendezvous_wait_person_s','queue_wait_person_s')),'Waiting subledger disagrees')
        for metric in METRICS:
            require(type(row[metric]) in (int,float) and isfinite(row[metric]) and row[metric]>=0,
                    'Negative or nonfinite returned metric')
            contributions[metric].append(row[metric])
    totals={key:fsum(values) for key,values in contributions.items()}
    for key,val in totals.items():
        _same(val,run['summary'][key],'Returned summary does not reproduce from balances: '+key)
    totals['unserved_service_unit_s']=totals['demand_service_unit_s']-totals['delivered_service_unit_s']
    totals['paid_person_s']=fsum(totals[key] for key in ('worker_travel_person_s','worker_work_person_s','worker_wait_person_s'))
    require(totals['paid_person_s']<=spent['person_s']+TOL
            and totals['tool_occupation_tool_s']<=spent['tool_s']+TOL,'Actual work exceeded reserved resource envelope')
    effects=_effects(program,run,tasks,trace)
    bound_inspections={row['task_id'] for row in program['inspection_program']['profile']['bindings']}
    return dict(status='PASS_RETURNED_DEVELOPMENT_EVIDENCE',arm=arm,trace_points=len(trace),balance_intervals=len(balances),
        totals=totals,opportunities=opportunities,common_two_or_more=sum(len(x['common_preference_eligible'])>=2 for x in opportunities),
        resource_contention_frames=sum(bool(x['resource_contention']) for x in opportunities),
        completed_inspections=sum(name in bound_inspections and row['status']=='completed' for name,row in tasks.items()),
        completed_interventions=sum(name not in bound_inspections and row['status']=='completed' for name,row in tasks.items()),
        task_dispositions={name:row['status'] for name,row in tasks.items()},applied_effects=effects,
        verified_closure='NOT_EVALUATED_WITHOUT_POST_ACTION_PROTOCOL',hard_violations=[])
