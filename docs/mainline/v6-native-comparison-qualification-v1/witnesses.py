"""Pre-execution witness wiring. Literal verdicts are in fixtures.json and oracle.py."""
from copy import deepcopy
from pathlib import Path
from fractions import Fraction
import json
import sys


def public_arguments(unit, call, saved):
    decision=next(d for d in saved['policy_public_decisions'] if d['frame']['as_of_s']==unit['at_s'])
    frame,history=deepcopy(decision['frame']),deepcopy(decision['history'])
    dispatch=call['dispatch_program']
    program=deepcopy(dispatch['policy_program'])
    edit=unit['edit']
    if edit=='second-order-valid-until-0.75':
        record=next(r for r in frame['evidence']['records'] if r['id']=='cooling-second-origin-20')
        record['valid_until_s']=0.75
    elif edit=='work-latency-1-and-no-arrived-ack':
        program['workforce_profile']['feedback_latency_s']=1
        history['work_feedback']=[]
    elif edit=='initial-validity-0.5':
        next(r for r in program['inspection_declaration']['bindings'] if r['task_id']=='cooling-direct/inspect-0')['validity_s']=0.5
    elif edit!='none':
        raise ValueError('Unknown prefix edit')
    closure=deepcopy(dispatch['closure_program'])
    closure['intervention_feedback']=deepcopy(history['intervention_feedback'])
    return dict(frame=frame,program=program,history=history,closure_program=closure,
                intervention_declaration=deepcopy(program['intervention_declaration']))


def substitutes(unit, directory, prior_dir):
    from aegis_dc import native_compare_score as score
    data=unit['inputs']
    if unit['id']=='Z1':
        full,limited,split=(score.service(data[k]) for k in ('full','limited','split'))
        def read_pair(a,b):
            r=score.compare_service(a,b)
            return [r['direction'],*r['balance_delta']]
        case=data['ambiguous']
        return dict(limited_L_U=limited['balance'],positive=read_pair(full,limited),negative=read_pair(limited,full),
                    subdivision=score.compare_service(limited,split)['direction'],
                    numeric=score.numeric_direction(Fraction(case['balance']),Fraction(case['rate']),case['identical_history']))
    if unit['id']=='Z2':
        measure=score.service([[0,10,1,1,0,10,10]])
        def arm(resources,closed):
            values=list(map(str,resources))
            return dict(status='COMPLETED',violations=[],service=measure,
                resources=dict(balance=values,rate=values,profiles=[[v] for v in values]),
                questions={data['question']:dict(first=data['first'],at=[
                    dict(time=t,closed=c) for t,c in zip(data['checkpoints'],closed)])})
        candidate=arm(data['V_resources'],data['closed'])
        direct=arm(data['D_resources'],data['closed'])
        a=score.compare_arms(candidate,direct)
        b=score.compare_arms(arm(data['V_resources'],data['V_changed_checkpoints']),direct)
        return dict(service=a['physical']['direction'],delta=a['resources']['balance_delta'],
            resources=a['resources']['direction'],closed_joint=a['same_service_resource_improvement'],
            lost_close_joint=b['same_service_resource_improvement'],physical_stays=b['physical']['direction'],
            resource_difference_stays=b['resources']['direction'],service_gain=a['service_gain'])
    if unit['id']=='Z3':
        run,trace,balances=score.read_native(prior_dir)
        before=score.score_arm(run,trace,balances)
        modified=deepcopy(run)
        for collection in (modified['workforce_public_feedback'],modified['policy_public_decisions'][-1]['history']['work_feedback']):
            original=next(r for r in collection if r['task_id']=='cooling-direct/recheck-0' and r['status']=='completed')
            collection.append(deepcopy(original))
        after=score.score_arm(modified,trace,balances)
        own=after['questions']['cooling-direct/question-0']
        return dict(first=own['first'],at_H=own['at'][-1]['state'],rechecks=own['rechecks_completed'],
            fee=after['resources']['balance'][2],resources=after['resources']['balance'],
            equal_before_after=before['resources']==after['resources'] and before['questions']==after['questions']
                and before['violations']==after['violations']==[])
    if unit['id']!='Z4':
        raise ValueError('Unknown substitute')
    from aegis_dc.native_compare_run import run_order
    target=directory/'injected-batch'
    order=[(data['condition'],arm) for arm in data['order']]
    def prepare(condition,arm,path):
        fixture=data['processes'][arm]
        script=("import pathlib,sys; pathlib.Path(sys.argv[1]).write_text(sys.argv[2])"
                if fixture['payload'] is not None else "import sys;sys.exit(7)")
        return [sys.executable,'-B','-c',script,str(path/'response.json'),json.dumps(fixture['payload'])], 'fixture-'+arm
    def read_return(condition,arm,path):
        return json.loads((path/'response.json').read_bytes())
    ledger=run_order(target,order,prepare,read_return)
    snapshot=(target/'ledger.json').read_bytes()
    try:
        run_order(target,order,prepare,read_return)
    except FileExistsError:
        rejected=(target/'ledger.json').read_bytes()==snapshot
    else:
        rejected=False
    return dict(states=[r['state'] for r in ledger['rows']],started=ledger['started'],complete_returns=ledger['complete_returns'],
        missing_returns=ledger['unreturned'],known_policy_subtotal=ledger['known_policy_subtotal'],
        unknown_internal=[r['arm'] for r in ledger['rows'] if r['started'] and r['internal_policy_calls'] is None],
        suffix=[r['arm'] for r in ledger['rows'] if r['state']=='NOT_EXECUTED'],
        processes=len([r for r in ledger['rows'] if r['pid'] is not None]),overwrite_rejected=rejected)
