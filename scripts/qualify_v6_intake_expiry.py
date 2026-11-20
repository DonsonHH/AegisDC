"""Public decision fixtures and saved-data checks for the bounded V6 expiry closeout."""
import argparse
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT/'docs/mainline/v6-intake-expiry-closeout-v1'
OLD = 'docs/mainline/v6-intake-engineering-v1/'
QUESTION = 'cooling-direct/question-0'
ACTION = 'cooling-direct/action-0'
RECHECK = 'cooling-direct/recheck-0'
INSPECT = 'cooling-direct/inspect-0'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return sha(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def checked_bytes(path, expected, receipts):
    raw = path.read_bytes()
    found = sha(raw)
    require(found == expected, f'Artifact hash differs: {path}')
    receipts[str(path)] = {'sha256':found, 'bytes':len(raw)}
    return raw


def extract(obj, path):
    for key in path:
        obj = obj[key]
    return obj


def overlay(obj, replacements):
    result = deepcopy(obj)
    for path, value in replacements:
        extract(result, path[:-1])[path[-1]] = deepcopy(value)
    return result


def one(rows, **fields):
    matches = [r for r in rows if all(r.get(k) == v for k,v in fields.items())]
    require(len(matches) == 1, f'Expected one {fields}, found {len(matches)}')
    return matches[0]


def columns(row, *names):
    return [row[k] for k in names]


def check(actual, expected):
    """Compare returned observations to predeclared fields, with no calls to the policy."""
    require(actual.keys() == expected.keys(), f'Check fields differ: {actual.keys() ^ expected.keys()}')
    def same(a,b):
        if type(b) is bool: return type(a) is bool and a == b
        if type(b) in (int,float): return type(a) in (int,float) and a == b
        if isinstance(b,dict): return isinstance(a,dict) and a.keys()==b.keys() and all(same(a[k],v) for k,v in b.items())
        if isinstance(b,list): return isinstance(a,list) and len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
        return a == b
    diffs = {k:{'expected':expected[k], 'actual':v} for k,v in actual.items() if not same(v,expected[k])}
    return dict(actual=actual, literal_sha256=canonical(expected), fields=len(expected), mismatches=diffs, passed=not diffs)


def run_public(unit, initial, output, report):
    from aegis_dc.dispatch_policy import choose_work
    args = overlay(initial, unit['replace'])
    input_hash = canonical(args)
    require(input_hash == unit['public_arguments_sha256'], 'Public decision input drift')
    directory = output/unit['id']
    directory.mkdir()
    write(directory/'arguments.json', args)
    write(directory/'begin.json', {'public_entry':'choose_work', 'input_sha256':input_hash})
    report['public_calls_started'].append(unit['id'])
    program = args['program']
    choice = choose_work(args['frame'], program, args['history'],
                         closure_program=args['closure_program'], intervention_declaration=program['intervention_declaration'])
    report['public_calls_returned'].append(unit['id'])
    write(directory/'choice.json', choice)
    require(canonical(args) == input_hash, 'Public argument mutated during decision')
    info = one(choice['intake_decisions'], question_id=QUESTION)
    plans = info['plans']
    inspection = plans['single']['stages'][0]
    binding = one(program['inspection_declaration']['bindings'], task_id=INSPECT)
    # Receipt and expiry below are declaration-based dates. The selector exposes the next
    # usable tick in its conditional action stage and the feasibility flags for both plans.
    actual = dict(instance=info['question_id'], as_of_s=choice['as_of_s'], root=choice['reason'],
        intention=choice['work_intention']['id'], forecast_inspection_finish_s=inspection['finish'],
        forecast_report_s=inspection['report'], declared_work_ack_s=inspection['finish']+program['workforce_profile']['feedback_latency_s'],
        half_open_end_s=inspection['finish']+binding['validity_s'], first_legal_decision_s=plans['chain']['stages'][1]['start'],
        inspection_feasible=plans['single']['feasible'], inspection_blockers=plans['single']['reasons'],
        contingent_chain_feasible=plans['chain']['feasible'], contingent_chain_blockers=plans['chain']['reasons'],
        direct_feasible=plans['direct']['feasible'], direct_recheck_planned_issue_s=plans['direct']['stages'][1]['start'],
        common_continuation=info['continuation'])
    require(choice['chosen_candidate_id']==actual['intention'], 'Policy intention identity differs')
    return dict(unit=unit['id'], input_sha256=input_hash, return_sha256=sha((directory/'choice.json').read_bytes()),
                **check(actual,unit['literal']))


class PriorRuns:
    """Read only version- and content-bound originals from the previous activity."""
    def __init__(self, freeze, sources, receipts):
        self.saved=freeze['saved']
        self.root=Path(self.saved['prior_activity'])
        self.sources=sources
        self.receipts=receipts
        self.manifests={key:json.loads(checked_bytes(self.root/key/'source/source-manifest.json',digest,receipts))
                        for key,digest in self.saved['private_manifests'].items()}

    def run(self, name):
        pin=self.saved['native_objects'][name]
        unit=pin['row']
        attempt=pin['attempt']
        manifest=self.manifests[attempt]
        require(manifest['execution_revision']==pin['execution_revision'], 'Historical execution version changed')
        run=json.loads(checked_bytes(self.root/attempt/'output'/unit/'run/run.json',pin['run_sha256'],self.receipts))
        src={k:v for k,v in manifest['files'].items() if (k.startswith('src/aegis_dc/') and k.count('/')==2
             and k.endswith('.py')) or k=='src/patrol_rsi/contracts.py'}
        require(run['code_identity']['files']==src and run['code_identity']['source_tree_sha256']==canonical(src),
                'Historical native runtime identity differs')
        material=self.sources[OLD+'inputs.json']
        original=overlay(material['common'],material['units'][unit]['edits'])
        original=overlay(original,self.sources[OLD+'input-binding-addendum.json']['units'][unit]['edits'])
        require(canonical(original)==pin['canonical_input_sha256'], 'Historical full call inputs differ')
        native=run['inputs']
        require(run['scenario_sha256']==canonical(original['scenario'])
                and native['duration_s']==original['duration_s'] and native['maximum_step_s']==original['step_s']
                and all(canonical(native[k])==canonical(original[k]) for k in ('dispatch_program','business_program','boundary_events')),
                'Saved run differs from the bound original call')
        return run

    def source_transfer(self):
        path='src/aegis_dc/intake_value.py'
        versions={}
        for key in ('green01','green03','current'):
            location=ROOT/path if key=='current' else self.root/key/'source'/path
            source=location.read_bytes() if key=='current' else checked_bytes(location,self.manifests[key]['files'][path],self.receipts)
            text=source.decode()
            def section(left,right):
                start=text.index(left)
                return sha(text[start:text.index(right,start)].encode())
            versions[key]=dict(exact_numeric_conversion=section('def number(', 'def validate_model('),
                report_class=section('def report_class(', 'def masses('),
                own_record_and_work_ack_before_supported_continuation=section("        elif ids['inspect'] in issued:", "            if outcome in ('LOW','NORMAL'):"))
        require(all(v==self.saved['original_classifier_parts'] for v in versions.values()), 'Arrived-record source transfer differs')
        return versions

    def original_comparison(self, acceptance):
        receipt=self.saved['original_19_comparison']
        data=json.loads(checked_bytes(self.root/receipt['path'],receipt['sha256'],self.receipts))
        rows={}
        for row in data['rows']:
            require(row['unit'] not in rows,'Duplicate original unit')
            comparisons=[]
            for assertion in row['checks']:
                a,b=assertion['actual'],assertion['expected']
                matches=(math.isclose(a,b,rel_tol=0,abs_tol=1e-7) if type(a) in (int,float) and type(b) in (int,float) else a==b)
                require(matches==assertion['passed'], 'Original assertion accounting drift')
                comparisons.append(matches)
            rows[row['unit']]=[sum(comparisons),len(comparisons)]
        selected=acceptance['accepted_facility_units']
        accepted=[sum(rows[k][i] for k in selected) for i in (0,1)]
        full=[sum(row[i] for row in rows.values()) for i in (0,1)]
        accepted_set={k for k,(matched,total) in rows.items() if total==matched}
        require(accepted_set==set(selected) and set(rows)==accepted_set|{acceptance['unmatched_unit']}, 'Original denominator changed')
        return check(dict(accepted_facility_units=sorted(accepted_set),accepted_unit_assertions=accepted,
            original_full_units=len(rows),original_full_assertions=full,unmatched_unit=acceptance['unmatched_unit'],
            unmatched_unit_assertions=rows[acceptance['unmatched_unit']],
            accepted_interfaces=[i['unit'] for i in data['prior_interfaces'] if i['passed']],
            accepted_pair_count=sum(bool(i['matched']) for i in data['pairs'])),
            dict(acceptance,accepted_facility_units=sorted(selected)))


def tick(run, at):
    return one((d for d in run['policy_public_decisions'] if d['frame']['as_of_s']==at))


def verified(decision):
    return one(decision['choice']['question_lifecycle']['questions'], question_id=QUESTION)


def received(decision, record_id):
    return one(decision['frame']['evidence']['records'],id=record_id)


def completed_acks(decision):
    return [columns(r,'task_id','observed_at_s','arrived_at_s')
            for r in decision['history']['work_feedback'] if r['status']=='completed']


def issues(run):
    return [[d['choice']['chosen_candidate_id'],d['frame']['as_of_s']] for d in run['policy_public_decisions']
            if d['choice']['chosen_candidate_id'] is not None]


def direct_closure(run):
    decisions=run['policy_public_decisions']
    first=next(d for d in decisions if verified(d)['question_closed'])
    end=decisions[-1]
    first_state,end_state=verified(first),verified(end)
    episode=one(run['business_evaluation']['components']['instance_closure']['episodes'],question_id=QUESTION)
    require(episode['first_verified_closed_at_s']==first['frame']['as_of_s'] and
            episode['status_at_horizon']==end_state['status'], 'Business endpoint differs from public clock assessments')
    actual=issues(run)
    return dict(first_closed_s=episode['first_verified_closed_at_s'],first_current_state=first_state['status'],
        current_at_H=end['frame']['as_of_s'],current_state=end_state['status'],risk_closed=end_state['risk_closed'],
        question_closed=end_state['question_closed'],own_recheck_current_at_7_5=verified(tick(run,7.5))['own_recheck']['passed'],
        own_recheck_current_at_10=verified(tick(run,10))['own_recheck']['passed'],policy_reason_at_H=end['choice']['reason'],
        last_intention=end['choice']['chosen_candidate_id'],issued_recheck_count=sum(task==RECHECK for task,_ in actual),
        completed_recheck_count=sum(r['id']==RECHECK and r['status']=='completed' for r in run['work_records']),
        issues_since_first_close=[r for r in actual if r[1]>=first['frame']['as_of_s']])


def repaired_chain(run):
    start=tick(run,0)
    end=tick(run,10)
    first=tick(run,7.5)
    question=verified(first)
    rec_id=question['own_recheck']['record_id']
    record=received(first,rec_id)
    receipt=one(tick(run,3.75)['history']['intervention_feedback'],task_id=ACTION)
    root=one(start['choice']['intake_decisions'],question_id=QUESTION)
    source_records={r['id']:r for r in first['frame']['evidence']['records']}
    def times(role):
        ids=one(question['checks'],role=role)['supporting_record_ids']
        return sorted({source_records[key]['observed_at_s'] for key in ids})
    costs=run['business_evaluation']['components']['costs']
    spent=costs['admission']['spent_or_reserved']
    return dict(order_id=one(start['choice']['question_instances'],id=QUESTION)['trigger_record_id'],
        first_choice=start['choice']['reason'],first_intention=start['choice']['chosen_candidate_id'],
        inspection_blockers=root['plans']['single']['reasons'],direct_plan_available=root['plans']['direct']['feasible'],
        issued=issues(run),completed=[columns(r,'id','completed_at_s') for r in run['work_records'] if r['status']=='completed'],
        completed_acks=completed_acks(end),action_report=columns(receipt,'task_id','operation_id','outcome','observed_at_s','arrived_at_s'),
        own_record=columns(record,'id','source_id','target_id','observable_id','unit','observed_at_s','arrived_at_s','valid_until_s'),
        frame_at_first_close=dict(condition_sample_s=times('condition'),service_sample_s=times('service'),recheck_availability=record['availability']),
        recheck_at_H=received(end,rec_id)['availability'],
        remaining_recheck_eligible=one(end['choice']['candidates'],candidate_id=RECHECK)['eligible'],
        envelope=columns(spent,'person_s','tool_s','cost'),
        actual_person_tool=[costs['personnel_total']['value'],costs['actual']['tool_occupation_tool_s']['value']],
        paid_issue_cost=costs['issue_fees']['value'],service_deficit_s=run['summary']['service_deficit_time_s'],closure=direct_closure(run))


def past_receipt(run):
    decision=tick(run,3.75)
    reading=received(decision,'flow-before-unused')
    info=one(decision['choice']['intake_decisions'],question_id=QUESTION)
    require(info['record_id']==reading['id'] and info['state']==decision['choice']['reason'], 'Expired receipt or selection identity differs')
    return dict(inspection_work=[columns(r,'id','issued_at_s','completed_at_s') for r in run['work_records'] if r['id']==INSPECT and r['status']=='completed'],
        own_completion_ack=columns(one(decision['history']['work_feedback'],task_id=INSPECT,status='completed'),
                                   'task_id','observed_at_s','arrived_at_s'),
        record=columns(reading,'id','source_id','target_id','observable_id','unit','observed_at_s','arrived_at_s','valid_until_s'),
        availability=reading['availability'],classification=info['state'],next_intention=decision['choice']['chosen_candidate_id'],
        manual_followups=sum(t>=decision['frame']['as_of_s'] for _,t in issues(run)))



def delayed_opportunity(delayed, measured):
    dispatch=delayed['inputs']['dispatch_program']
    reference_dispatch=measured['inputs']['dispatch_program']
    require(delayed['scenario_sha256']==measured['scenario_sha256']
            and delayed['inputs']['boundary_events']==measured['inputs']['boundary_events']
            and all(dispatch[k]==reference_dispatch[k] for k in ('nominal_knowledge','decision_times_s','inspection_program','intervention_program'))
            and all(dispatch['policy_program'][k]==reference_dispatch['policy_program'][k] for k in ('workforce_profile','templates')),
            'Transfer of a realized first trip requires the same route, work recipe, clock and exogenous condition')
    compiled=one(delayed['policy_public_decisions'][-1]['choice']['question_instances'],id=QUESTION)
    opening=compiled['opened_at_s']
    require(received(tick(delayed,opening),compiled['trigger_record_id'])['arrived_at_s']==opening, 'Delayed order not at stated opening')
    opportunity=one(delayed['business_evaluation']['components']['diagnostic']['events'],condition_id='native50-flow')['reference_opportunity']
    work=one(measured['work_records'], id=INSPECT, status='completed')
    last=measured['policy_public_decisions'][-1]
    obs=received(last,'flow-before-unused')
    ack=one(last['history']['work_feedback'], task_id=INSPECT, status='completed')
    require(work['completed_at_s']==ack['observed_at_s']==obs['observed_at_s'] and obs['source_id']=='portable-intake-meter',
            'Reference trip, actual sampling and actual completion receipt must bind')
    trip=work['paths']['worker_cooling']
    require(len(trip)==1 and work['work_started_at_s']==work['arrived_at_s']==trip[0]['arrives_at_s'], 'Reference movement differs')
    origin=work['issued_at_s']
    finish=opening+work['completed_at_s']-origin
    report=finish+(obs['arrived_at_s']-obs['observed_at_s'])
    work_ack=finish+(ack['arrived_at_s']-ack['observed_at_s'])
    actual_clock=[d['frame']['as_of_s'] for d in delayed['policy_public_decisions']]
    require(actual_clock==dispatch['decision_times_s'], 'Saved decisions do not follow declared clock')
    first_tick=next(t for t in actual_clock if t>=max(report,work_ack))
    deadline=opportunity['deadline_s']
    return dict(carried=columns(opportunity,'status','starts_at_s','earliest_report_at_s','deadline_s'),
        actual_opened_s=opening,actual_work_ids=[r['id'] for r in delayed['work_records']],
        actual_handheld_records=sorted({r['id'] for d in delayed['policy_public_decisions'] for r in d['frame']['evidence']['records']
                if r['source_id']=='portable-intake-meter'}),reference_inspection=work['id'],
        actual_anchor=[origin,trip[0]['gate_at_s'],work['work_started_at_s'],work['completed_at_s'],obs['arrived_at_s'],ack['arrived_at_s']],
        inferred_from_anchor=dict(finish_s=finish,report_s=report,work_ack_s=work_ack,first_clock_s=first_tick,
            deadline_s=deadline,status='TOO_LATE' if first_tick>deadline else 'IN_TIME'))


def execute(output, launch, selection, report):
    receipts=report['read_receipts']
    for name, digest in launch['files'].items():
        checked_bytes(ROOT/name,digest,receipts)
    freeze=json.loads((PACK/'freeze.json').read_bytes())
    require(launch['baseline']==freeze['baseline'] and sha((PACK/'freeze.json').read_bytes())==launch['freeze_sha256'],
            'Freeze or baseline identity differs')
    require(sha(Path(sys.executable).resolve().read_bytes())==launch['python_sha256'],'Interpreter differs')
    require(os.environ['SLURM_CPUS_PER_TASK']=='1' and os.environ['SLURM_MEM_PER_NODE']=='1024','Allocation differs')
    public_sources={name:json.loads(checked_bytes(ROOT/name,h,receipts)) for name,h in freeze['public_source_sha256'].items()}
    initial={k:extract(public_sources[name],keys) for k,(name,keys) in freeze['initial_public_arguments'].items()}
    saved=freeze['saved']
    historical=PriorRuns(freeze,public_sources,receipts)
    def original():
        return historical.original_comparison(freeze['original_acceptance'])
    def revision():
        return check(repaired_chain(historical.run('expired-read')),saved['revised_expired_read'])
    def other_routes():
        subrows={key:check(direct_closure(historical.run(key)),saved['h10_direct_common']) for key in saved['direct_route_companions']}
        return dict(rows=subrows,passed=all(row['passed'] for row in subrows.values()))
    def actual_receipt():
        readback=check(past_receipt(historical.run('historical-receipt')),saved['historical_arrived'])
        readback['source_transfer']=historical.source_transfer()
        return readback
    def timing():
        return check(delayed_opportunity(historical.run('delayed-order'),historical.run('measure-low')),saved['delayed_opportunity'])
    # Missing any plant dependency fails closed. The authorized API call returns an intention only.
    require('aegis_dc.plant' not in sys.modules, 'Plant was imported before public qualification')
    sys.modules['aegis_dc.plant']=None
    steps={'original':original}
    for fixture in freeze['new_public_witnesses']:
        steps[fixture['id']]=lambda fixture=fixture:run_public(fixture,initial,output,report)
    steps.update(revision=revision,direct_horizon=other_routes,received=actual_receipt,reference_opportunity=timing)
    selected=list(steps) if selection is None else selection
    require(selected and len(set(selected))==len(selected) and set(selected)<=steps.keys(), 'Invalid subset')
    report.update(selected=selected,omitted_in_attempt=[key for key in steps if key not in selected])
    for key in selected:
        try:
            report['checks'][key]=steps[key]()
        except Exception:
            report['checks'][key]=dict(passed=False,error=traceback.format_exc())
    require(sys.modules['aegis_dc.plant'] is None, 'Plant access policy changed')
    report['attempt_passed']=all(row['passed'] for row in report['checks'].values())
    report['full_package_checked_in_attempt']=report['attempt_passed'] and set(selected)==steps.keys()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--launch',type=Path,required=True)
    parser.add_argument('--launch-sha',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--only',nargs='+')
    args=parser.parse_args()
    output=args.output.resolve()
    output.mkdir(exist_ok=False)
    report=dict(schema='aegisdc-v6-intake-expiry-checks-v1',slurm_job=os.environ.get('SLURM_JOB_ID'),
        public_calls_started=[],public_calls_returned=[],facility_invocations=0,research_runs=0,checks={},read_receipts={})
    try:
        launch=json.loads(checked_bytes(args.launch.resolve(),args.launch_sha,report['read_receipts']))
        require(report['slurm_job'] and launch['output']==str(output) and launch['selection']==args.only,
                'Bad launch directory, selection or allocation')
        report['selected']=args.only if args.only is not None else ['original','T1','T2','T3','T4','revision','direct_horizon','received','reference_opportunity']
        report.update(launch_sha256=args.launch_sha,checker_revision=launch['checker_revision'],freeze_revision=launch['freeze_revision'],
            runtime_baseline=launch['baseline'])
        execute(output,launch,args.only,report)
    except Exception:
        report.update(attempt_passed=False,fatal=traceback.format_exc())
    finally:
        report['unexecuted_selected']=[u for u in report.get('selected',[]) if u not in report['checks']]
        write(output/'report.json',report)
    return 0 if report['attempt_passed'] else 1


if __name__=='__main__':
    sys.exit(main())
