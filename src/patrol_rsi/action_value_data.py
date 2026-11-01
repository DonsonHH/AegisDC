"""Offline outcomes only. This module is never called by feature selection or live policy."""
METRICS=('missed_segments','consequence_weighted_censored_delay_s','travel_m','service_s',
    'completed_inspections','current_round_unfinished_obligations','unfinished_committed_tasks')


def outcomes(original,branch):
    delta={}
    for k in METRICS:
        a,b=original['metrics'][k],branch['metrics'][k]
        if a is None:
            if b is not None:raise ValueError('Same process label validity')
            delta[k]=None
        else:
            if b is None:raise ValueError('Same process wait mask')
            delta[k]=b-a
    return {'relative_outcomes':delta,'wait_valid':delta['consequence_weighted_censored_delay_s'] is not None,
        'y':[delta[k] for k in ('missed_segments','consequence_weighted_censored_delay_s','travel_m','completed_inspections')]}


def event_pairs(original,branch,root_time):
    key=lambda e:(e['task_id'],e['onset_s'],e['end_s'])
    aa={key(e):e for e in original['anomaly_intervals']};bb={key(e):e for e in branch['anomaly_intervals']}
    if set(aa)!=set(bb):raise ValueError('Identical physical event identities required')
    result=[]
    for k,a in aa.items():
        b=bb[k];ta,tb=a['first_confirmation_s'],b['first_confirmation_s']
        status='both_missed' if ta is None and tb is None else 'new_confirmation' if ta is None else 'lost_confirmation' if tb is None else 'earlier' if tb<ta-1e-9 else 'later' if tb>ta+1e-9 else 'same'
        if ta!=tb and any(t is not None and t<=root_time+1e-9 for t in (ta,tb)):raise ValueError('Identical prefix cannot change a confirmation completed at/before the root')
        result.append({'task_id':k[0],'onset_s':k[1],'end_s':k[2],'original_first_s':ta,'candidate_first_s':tb,
            'status':status,'difference_s':tb-ta if ta is not None and tb is not None else None})
    return result


def objective(y):return [y[0],*([y[1]] if y[1] is not None else []),y[2],-y[3]]


def dominates(a,b):return all(x<=y+1e-9 for x,y in zip(a,b)) and any(x<y-1e-9 for x,y in zip(a,b))


def task_improvement(y):
    m,w,c,n=y
    return (m<-1e-9 or w is not None and w<-1e-9) and m<=1e-9 and (w is None or w<=1e-9) and c<=1e-9 and n>=-1e-9


def classify_root(rows):
    original=next(r for r in rows if r['original']);alternatives=[r for r in rows if not r['original']]
    v0=objective(original['y']);improving=[r['action_id'] for r in alternatives if task_improvement(r['y'])]
    nondominated=[r['action_id'] for r in rows if not any(dominates(objective(other['y']),objective(r['y'])) for other in rows)]
    tradeoffs=[r['action_id'] for r in alternatives if not dominates(v0,objective(r['y'])) and not dominates(objective(r['y']),v0) and any(abs(a-b)>1e-9 for a,b in zip(objective(r['y']),v0))]
    all_worse=bool(alternatives) and all(dominates(v0,objective(r['y'])) for r in alternatives)
    equivalent=all(all(abs(a-b)<=1e-9 for a,b in zip(objective(r['y']),v0)) for r in alternatives)
    return {'task_improving_actions':improving,'nondominated_actions':nondominated,'tradeoff_actions':tradeoffs,
        'all_alternatives_dominated_by_original':all_worse,'all_equivalent':equivalent,
        'category':'task_improvement' if improving else 'all_worse' if all_worse else 'all_equivalent' if equivalent else 'tradeoffs' if tradeoffs else 'cost_or_work_only'}
