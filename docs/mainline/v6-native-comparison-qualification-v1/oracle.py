"""Frozen comparison oracle. Only JSON, file bytes and independent literal expectations."""
from fractions import Fraction
import hashlib
import json


def json_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


class Assertions:
    def __init__(self, unit):
        self.unit = unit
        self.items = []

    def equal(self, key, actual, expected):
        # Exact semantic equality, including booleans; allow native int/float clocks.
        def same(a, b):
            if isinstance(b, bool):
                return type(a) is bool and a == b
            if type(b) in (int, float):
                return type(a) in (int, float) and a == b
            if isinstance(b, list):
                return isinstance(a, list) and len(a) == len(b) and all(same(x,y) for x,y in zip(a,b))
            if isinstance(b, dict):
                return isinstance(a, dict) and a.keys() == b.keys() and all(same(a[k],v) for k,v in b.items())
            return a == b
        self.items.append(dict(field=key, actual=actual, expected=expected, passed=same(actual,expected)))

    def result(self):
        return dict(unit=self.unit, assertions=self.items, passed=bool(self.items) and all(i['passed'] for i in self.items))


def public(unit, choice):
    a = Assertions(unit['unit'])
    ex = unit['expected']
    root = choice['intake_decisions'][0]
    a.equal('actual decision time', choice['as_of_s'], unit['at_s'])
    a.equal('public state', root['state'], ex['state'])
    a.equal('selected candidate', choice['chosen_candidate_id'], ex['selected'])
    a.equal('returned work intention', (choice['work_intention'] or {}).get('id'), ex['selected'])
    a.equal('real question count', len(choice['question_instances']), ex['instance_count'])
    a.equal('own question', root['question_id'], 'cooling-direct/question-0')
    a.equal('current audit eligible if issued', ex['selected'] is None or any(
        r['candidate_id']==ex['selected'] and r['eligible'] for r in choice['candidates']), True)
    if 'observation' in ex:
        a.equal('actual classification', root['observation'], ex['observation'])
        a.equal('bound own record', root['record_id'], ex['record'])
        if ex['observation']=='LOW':
            a.equal('fixed LOW branch', root['continuation']['LOW'], 'ACT')
    elif unit['condition']=='C17':
        a.equal('slot 1 cannot borrow the occupied tool', any(r['question_id']=='cooling-direct/question-1' and
            ex['targeted_blocker'] in r['reasons'] and not r['eligible'] for r in choice['candidates']), True)
    else:
        plans=root['plans']
        a.equal('complete direct feasibility',plans['direct']['feasible'],unit['condition']!='C15')
        a.equal('fixed low branch feasibility',plans['chain']['feasible'],ex['targeted_blocker'] is None)
        if ex['targeted_blocker']:
            a.equal('targeted full-branch blocker',ex['targeted_blocker'] in plans['chain']['reasons'],True)
    return a.result()


def facility(unit, run, trace, balances, scored):
    a = Assertions(unit['unit'])
    ex=unit['expected']
    decisions=run['policy_public_decisions']
    a.equal('facility id',run['facility_id'],'zhengzhou-inspired-synthetic-full-facility-reserve-v6')
    a.equal('physical window', [trace[0]['time_s'],trace[-1]['time_s']],[0,10])
    a.equal('complete source-bound native call',run['business_evaluation']['run_binding']['dispatch_program_sha256'],unit['identities']['dispatch'])
    a.equal('number of top level decisions',len(decisions),ex['decision_calls'])
    a.equal('work intention, issue and actual completion',[[r['id'].split('/')[-1],r['issued_at_s'],r.get('completed_at_s')] for r in run['work_records']],ex['work'])
    a.equal('charged native work and fees',[float(Fraction(k)) for k in scored['resources']['balance']],ex['actual_resources'])
    a.equal('occupation interval readback',[float(Fraction(k)) for k in scored['resources']['rate']],ex['actual_resources'])
    a.equal('hard constraint audit',scored['violations'],[])
    a.equal('predeclared opportunities',len(scored['questions']),ex['opportunities'])
    own=scored['questions']['cooling-direct/question-0']
    a.equal('first actual verified instant',own['first'],ex['first_close'])
    a.equal('5,7.5,H10 legal close',[r['closed'] for r in own['at']],ex['valid_at_5_7_5_10'])
    a.equal('checkpoint times',[r['time'] for r in own['at']],[5,7.5,10])
    a.equal('issued / completed rechecks',[own['rechecks_issued'],own['rechecks_completed']],[ex['recheck_count']]*2)
    if 'service_L_U' in ex:
        for kind in ('balance','rate'):
            for index,wanted in enumerate(ex['service_L_U']):
                a.equal(f'whole window {kind} {index}',abs(float(Fraction(scored['service'][kind][index]))-wanted)<1e-8,True)
        network=[e['applied_at_s'] for e in run['events'] if e.get('parameter_id')=='network_service_capacity' and e['value']==1]
        a.equal('network recovery',network,[ex['network_recovery_s']])
    if 'valve' in ex:
        cooling=[r['domains']['facility_cooling'] for r in trace]
        a.equal('all snapshots closed valve',[min(c['valve_groups']['lake_valve_group']['opening'] for c in cooling),
            max(c['valve_groups']['lake_valve_group']['opening'] for c in cooling)],[ex['valve']]*2)
        a.equal('all sampled flows zero',all(c['lake_pump']['volume_flow_m3_s']==ex['volume_flow'] for c in cooling),True)
        low=next(d for d in decisions if d['frame']['as_of_s']==3.75)
        a.equal('paid low observation',low['choice']['intake_decisions'][0]['observation'],ex['measurement'])
        events=run['intervention_private_audit']['events']
        a.equal('only named filter write',[[e['parameter_id'],e['old_value'],e['new_value'],e['applied_at_s']] for e in events if e['outcome']=='APPLIED'],ex['writes'])
    if 'split_s' in ex:
        a.equal('joint service cap at all snapshots',max(r['domains']['it_service']['delivered'] for r in trace)<=ex['max_service']+1e-8,True)
        a.equal('real exogenous writes',[[e['applied_at_s'],e['parameter_id'],e['value']] for e in run['events'] if e.get('kind')=='exogenous_boundary_input'],ex['event_bindings'])
        for number,part in enumerate(([b for b in balances if b['end_s']<=4],[b for b in balances if b['start_s']>=4])):
            totals=[sum(b['service_deficit_time_s'] for b in part),sum(b['demand_service_unit_s']-b['delivered_service_unit_s'] for b in part)]
            a.equal('positive complete subwindow '+str(number),bool(part) and all(x>=y-1e-8 for x,y in zip(totals,ex['min_segment_L_U'][number])),True)
    if 'max_IT_W' in ex:
        domains=[r['domains'] for r in trace]
        maxpower=max(sum(d['power']['actual_powers_W'][x] for x in ('compute','network','storage')) for d in domains)
        a.equal('shared electrical limit',maxpower<=ex['max_IT_W']+1e-8,True)
        a.equal('compute capacity bound',max(d['it_service']['capacities']['compute'] for d in domains)<=ex['max_compute_capacity']+1e-8,True)
        a.equal('joint delivery follows three actual capacities and demand',
            all(d['it_service']['delivered']==min(d['it_service']['demand'],*d['it_service']['capacities'].values())
                and d['it_service']['delivered']<=ex['max_delivery']+1e-8 for d in domains),True)
    if 'receipts' in ex:
        last=decisions[-1]
        audit=[]
        for event in last['history']['work_feedback']:
            if event['status']!='completed':continue
            if '/action-' in event['task_id']:
                report=next(r for r in last['history']['intervention_feedback'] if r['task_id']==event['task_id'])
            else:
                report=next(r for r in last['frame']['evidence']['records'] if r['id']=='flow-after-clean')
            audit.append([event['task_id'].split('/')[-1],event['observed_at_s'],report['arrived_at_s'],event['arrived_at_s']])
        a.equal('report and ACK timelines',audit,ex['receipts'])
    if 'second_open_s' in ex:
        half=next(r for r in decisions if r['frame']['as_of_s']==0.5)
        second=next(r for r in half['choice']['question_instances'] if r['slot']==1)
        rec=next(r for r in half['frame']['evidence']['records'] if r['id']==second['trigger_record_id'])
        a.equal('second independent opening and expiry',[second['opened_at_s'],rec['valid_until_s']],[ex['second_open_s'],ex['second_last_valid_s']])
        a.equal('blocked by actually occupied crew/tool',any(r['question_id']==second['id'] and not r['eligible']
                and 'PUBLIC_UNACKNOWLEDGED_RESOURCE_OCCUPATION' in r['reasons'] for r in half['choice']['candidates']),True)
        a.equal('no later second-slot issuance',[r['id'] for r in run['work_records'] if r['id'].endswith('-1')],ex['second_actual_work'])
        a.equal('second cannot borrow closure',any(r['closed'] for r in scored['questions'][second['id']]['at']),ex['second_closed'])
    return a.result()


def substitute(unit, actual):
    a=Assertions(unit['id'])
    for key,value in unit['expected'].items():
        a.equal(key,actual.get(key),value)
    return a.result()


def native_order(ledger, expected_units):
    a=Assertions('batch-identity')
    rows=ledger['rows']
    a.equal('ordered native attempts',[r['unit'] for r in rows],expected_units)
    a.equal('all independent native calls returned',[r['state'] for r in rows],['COMPLETED']*len(rows))
    a.equal('separate output directories',len({r['directory'] for r in rows}),len(rows))
    a.equal('separate recorded subprocess launches',len({(r['pid'],r['start_ns']) for r in rows if r['pid'] is not None}),len(rows))
    for r in rows:
        a.equal('before-launch and return '+r['unit'],r['prepared_ns']<=r['start_ns']<=r['returned_ns'],True)
    by_id={r['unit']:r for r in rows}
    if {'C01-V','C01-H'}<=by_id.keys():
        v,h=(by_id[x] for x in ('C01-V','C01-H'))
        a.equal('V/H complete call SHA',v['input_sha256'],h['input_sha256'])
        a.equal('V/H same public history, private trajectory and semantic endpoints',v['semantic_sha256'],h['semantic_sha256'])
    return a.result()
