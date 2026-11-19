"""Remote Slurm qualification of the frozen V6 intake interface and native CLI."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import traceback
from copy import deepcopy

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT/'docs/mainline/v6-intake-engineering-v1'


def read(path):
    return json.loads(path.read_bytes())


def write(path, obj):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(obj,stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.write('\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def replace(obj,path,value):
    for part in path[:-1]:
        obj=obj[part]
    obj[path[-1]]=deepcopy(value)


def inputs(name, doc, amendment):
    row=doc['units'][name]
    base=(ROOT/doc['legacy_path'])
    if sha(base)!=doc['legacy_raw_sha256']:
        raise ValueError('Legacy input hash differs')
    obj=deepcopy(doc['common']) if row['base']=='common' else read(base)
    for entry in (row,amendment['units'][name]):
        for path,value in entry['edits']:
            replace(obj,path,value)
        if digest(obj)!=entry['sha256']:
            raise ValueError('Complete input drift: '+name)
    return obj


def cli(name, doc, amendment, directory, red, attempts):
    unit=directory/name
    unit.mkdir()
    obj=inputs(name,doc,amendment)
    paths={'model':obj['scenario'],'dispatch-program':obj['dispatch_program'],'business-program':obj['business_program'],
           'inputs':{'schema':'aegisdc-engineering-inputs-v1','work_requests':[],'boundary_events':obj['boundary_events']}}
    command=[sys.executable,'-B','-m','aegis_dc','simulate']
    for arg,value in paths.items():
        path=unit/(arg+'.json')
        write(path,value)
        command+=['--'+arg,str(path)]
    command+=['--duration',str(obj['duration_s']),'--step',str(obj['step_s']),'--output',str(unit/'run')]
    attempt=dict(unit=name,cli_started=False,returned=False,facility_status='NOT_STARTED')
    attempts.append(attempt)
    write(unit/'call.json',dict(input_sha256=digest(obj),command=command,invocation=1,mode='red' if red else 'native'))
    with (unit/'stdout').open('xb') as stdout,(unit/'stderr').open('xb') as stderr:
        with subprocess.Popen(command,cwd=ROOT,stdout=stdout,stderr=stderr) as proc:
            attempt.update(cli_started=True,pid=proc.pid,facility_status='NOT_KNOWN')
            write(unit/'started.json',attempt)
            proc.wait()
    attempt.update(returned=True,returncode=proc.returncode,facility_status=(
        'COMPLETED' if (unit/'run/run.json').is_file() else 'REJECTED_BY_PARSER' if red and proc.returncode==2 else 'NOT_KNOWN'))
    write(unit/'exit.json',dict(returncode=proc.returncode,stdout_sha256=sha(unit/'stdout'),stderr_sha256=sha(unit/'stderr')))
    return proc.returncode


def interfaces(doc):
    # The entry under test is called only on the explicit frozen public document.
    from aegis_dc.intake_value import report_class
    from aegis_dc.dispatch_policy import choose_work
    model=doc['common']['dispatch_program']['policy_program']
    results=[]
    for name,spec in doc['public_interface'].items():
        if 'record' in spec:
            actual=report_class(spec['record'],spec['as_of_s'],spec['disputed_ids'],model['value_model'])
        else:
            frame=spec['frozen_frame_and_history']
            path=ROOT/frame['path']
            if sha(path)!=frame['sha256']:
                raise ValueError('Public decision fixture drift')
            row=read(path)[frame['row_index']]
            program=deepcopy(model)
            replace(program,spec['edit_path'],spec.get('policy_schema',spec.get('observable_id')))
            try:
                choose_work(row['frame'],program,row['history'])
                actual='ACCEPT'
            except ValueError:
                actual='REJECT'
        results.append(dict(unit=name,actual=actual,expected=spec['expected'],passed=actual==spec['expected']))
    return results


def physical(unit):
    with (unit/'run/private-state.jsonl').open(encoding='utf-8') as stream:
        points={}
        for line in stream:
            row=json.loads(line)
            dom=row['domains']
            points[row['time_s']]=[dom['facility_cooling']['lake_mass_flow_kg_s']/998,dom['it_service']['delivered']]
        return points


def compare(name,unit,want,values):
    run=read(unit/'run/run.json')
    for file,meta in run['artifacts'].items():
        if sha(unit/'run'/file)!=meta['sha256']:
            raise ValueError('Native artifact drift: '+file)
    biz=run['business_evaluation']
    costs=biz['components']['costs']
    episodes=biz['components']['instance_closure']['episodes']
    ds=run['policy_public_decisions']
    summary=run['summary']
    physical_points=physical(unit)
    checks=[]
    def eq(field,actual,expected):
        match=(math.isclose(actual,expected,rel_tol=0,abs_tol=1e-7)
               if type(actual) in (int,float) and type(expected) in (int,float) else actual==expected)
        checks.append(dict(field=field,actual=actual,expected=expected,passed=match))
    tasks=[[r['id'].split('/')[-1],r['issued_at_s'],r.get('completed_at_s')] for r in run['work_records']]
    eq('actual ordered issues and actual work completions',tasks,want['issues'])
    eq('public issue count',len([r for r in ds if r['choice']['chosen_candidate_id']]),len(tasks))
    for key,value in [('person_s',costs['personnel_total']['value']),('tool_s',summary['tool_occupation_tool_s']),
                      ('issue_cost',costs['issue_fees']['value']),('service_deficit_time_s',summary['service_deficit_time_s']),
                      ('envelope_person_s',costs['admission']['spent_or_reserved']['person_s']),
                      ('envelope_tool_s',costs['admission']['spent_or_reserved']['tool_s']),
                      ('instances',len(ds[-1]['choice']['question_instances'])),('first_verified_at_s',episodes[0]['first_verified_closed_at_s'])]:
        eq(key,value,want[key])
    eq('verification binds own question',episodes[0]['question_id'],'cooling-direct/question-0')
    eq('native admission no refund',costs['admission']['terminal_report_refund'],False)
    eq('private business identity',biz['facility_id'],run['source_config']['id'] if 'source_config' in run else read(unit/'model.json')['id'])
    eq('native evaluated same dispatch',biz['run_binding']['dispatch_program_sha256'],digest(read(unit/'dispatch-program.json')))
    by_time={d['frame']['as_of_s']:d for d in ds}
    for when,state in want['decision_states']:
        eq('public decision '+str(when),by_time[when]['choice']['reason'],state)
    extra=want['extra']
    root=ds[0]['choice']
    if name in values['units']:
        decision=root['intake_decisions'][0]
        for k in ('scores','posterior','continuation'):
            eq('independent root '+k,decision[k],values[k])
        for key,data in values['branch_envelopes'].items():
            vector=decision['plans'][key]['envelope']
            from fractions import Fraction
            eq('complete envelope '+key,[float(Fraction(vector[k])) for k in ('person_s','tool_s','cost')],data)
    if 'continuation' in extra:
        eq('common continuation',root['intake_decisions'][0]['continuation'],extra['continuation'])
    if 'inspect_branch_infeasible' in extra:
        eq('full chain blocked by '+extra['inspect_branch_infeasible'],
           extra['inspect_branch_infeasible'] in root['intake_decisions'][0]['plans']['chain']['reasons'],True)
    if 'second_open' in extra:
        blockers=by_time[extra['shared_occupied_at']]['choice']['candidates']
        eq('competing slot shares worker/tool',any(r['question_id'].endswith('-1') and
           'PUBLIC_UNACKNOWLEDGED_RESOURCE_OCCUPATION' in r['reasons'] for r in blockers),True)
        eq('second slot opening',episodes[1]['opened_at_s'],extra['second_open'])
        eq('no borrowed action / closure', [episodes[1]['actual_action_completed_at_s'],episodes[1]['first_verified_closed_at_s']],[None,None])
        same=by_time[extra['second_open']]['choice']['intake_decisions'][0]
        eq('copy leaves origin posterior unchanged',same['posterior'],values['posterior'])
    if 'first_full_service_s' in extra:
        eq('external restoration',next((t for t,(_,service) in physical_points.items() if service==1),None),extra['first_full_service_s'])
    if 'action_report' in extra:
        eq('own action arrived',episodes[0]['action_report_arrived_at_s'],extra['action_report'])
        report=next((r for d in ds for r in d['frame']['evidence']['records'] if r['id']=='flow-after-clean'),None)
        eq('own recheck arrived',report['arrived_at_s'] if report else None,extra['own_recheck_arrival'])
    if 'action_outcome' in extra:
        rows=[r for d in ds for r in d['history']['intervention_feedback'] if r['task_id'].endswith('action-0')]
        eq('completion-time authorization',[rows[0]['outcome'],rows[0]['reason']] if rows else None,[extra['action_outcome'],extra['reason']])
    if name=='delayed-order':
        opportunity=biz['components']['diagnostic']['events'][0]['reference_opportunity']
        eq('delayed opening lawful opportunity', [opportunity[k] for k in ('status','starts_at_s','earliest_report_at_s','deadline_s')],['TOO_LATE',0.5,4.25,4])
    return dict(unit=name,passed=all(c['passed'] for c in checks),checks=checks,
        stages=tasks,decisions=[[d['frame']['as_of_s'],d['choice']['reason'],d['choice']['chosen_candidate_id']] for d in ds],
        endpoint=[{k:r.get(k) for k in ('question_id','opened_at_s','actual_action_completed_at_s','action_report_arrived_at_s',
            'action_report_outcome','first_verified_closed_at_s','status_at_horizon')} for r in episodes],
        actual_cost=costs['actual'],person=costs['personnel_total'],fees=costs['issue_fees'],admission=costs['admission'],
        service={k:summary[k] for k in ('demand_service_unit_s','delivered_service_unit_s','service_deficit_time_s')},
        calls=dict(facility=1,decisions=len(ds),issues=len(tasks),computed=costs['computation']),
        input_sha256=read(unit/'call.json')['input_sha256'],run_sha256=sha(unit/'run/run.json'),
        artifact_hashes=run['artifacts'],source_tree=run['code_identity']['source_tree_sha256'])



def pair_checks(units):
    def run(name):
        return read(units[name]/'run/run.json')
    before=lambda name:[(x['frame'],x['history'],x['choice']) for x in run(name)['policy_public_decisions'] if x['frame']['as_of_s']<3.75]
    left=physical(units['measure-low'])
    right=physical(units['matched-protection'])
    common=sorted(left.keys() & right.keys())
    conditions=['measure-low','direct','matched-protection']
    def writes(name):
        return [(e['task_id'],e['parameter_id'],e['applied_at_s'],e['old_value'],e['new_value'])
                for e in run(name)['intervention_private_audit']['events'] if e['outcome']=='APPLIED']
    mutations={name:writes(name) for name in conditions}
    clock=read(units['measure-low']/'dispatch-program.json')['decision_times_s']
    exogenous=[digest(read(units[name]/'inputs.json')) for name in conditions]
    models=[digest(read(units[name]/'model.json')) for name in conditions]
    return [
        dict(pair='same public prefix before paid arrival',matched=before('measure-low')==before('measure-normal'),cut=3.75),
        dict(pair='inspection cannot clear filter; same exogenous service',matched=all(t in common for t in clock) and
             mutations['matched-protection']==[] and
             mutations['measure-low']==[('cooling-direct/action-0','filter_resistance_multiplier',5,4,1)] and
             all(abs(left[t][0]-right[t][0])<1e-7 for t in common if t<5) and
             all(abs(left[t][1]-right[t][1])<1e-7 for t in common) and
             0.054<=right[10][0]<=0.055 and 0.099<=left[10][0]<=0.101,
             common_instants=len(common),actual_writes=mutations,post_action_flow=[left[10][0],right[10][0]]),
        dict(pair='direct, conditional and existing protection use identical model and exogenous events',
             matched=len(set(models))==1 and len(set(exogenous))==1 and
             [len(run(n)['work_records']) for n in conditions]==[3,2,0])]



def saved_handoff(report, previous, directory):
    """Publish bounded row-level facts, keeping trajectories and all assertions private."""
    attempts=[]
    for path in previous:
        prior=read(path/'report.json')
        pin=read(path.parent/'source/source-manifest.json')
        if sha(path.parent/'source/source-manifest.json')!=prior['source_manifest']:
            raise ValueError('Prior attempt identity drift')
        attempts.append(dict(attempt=path.parent.name,job=prior['job'],mode=prior['mode'],
            execution_revision=pin['execution_revision'],checker_revision=pin['checker_revision'],
            source_manifest_sha256=prior['source_manifest'],report_sha256=sha(path/'report.json'),
            completed_facilities=sum((path/row['unit']/'run/run.json').is_file() for row in prior['rows']),
            interfaces=len(prior['interfaces']),assertions=sum(len(row['checks']) for row in prior['rows']),
            policy_calls=sum(row['calls']['decisions'] for row in prior['rows']),original_failures=prior['failed'],
            not_executed=prior['not_executed']))
    rows=[]
    for r in report['rows']:
        path=Path(r['archive_parent'])/r['unit']
        actual=read(path/'run/run.json')
        changes=[]
        for t,state,task in r['decisions']:
            if not changes or changes[-1][1:]!=[state,task]:
                changes.append([t,state,task])
        first=actual['policy_public_decisions'][0]['choice'].get('intake_decisions',[])
        amounts={k:v['value'] for k,v in r['actual_cost'].items()}
        rows.append(dict(unit=r['unit'],original_expectation_matched=r['passed'],source=r['actual_revision'],
            source_tree=r['source_tree'],attempt=path.parent.parent.name,input_sha256=r['input_sha256'],
            run_sha256=r['run_sha256'],raw_artifacts=r['artifact_hashes'],decision_calls=r['calls']['decisions'],
            public_state_changes=changes,ordered_work_issue_completion=r['stages'],endpoints=r['endpoint'],
            public_model_at_open=({k:first[0].get(k) for k in ['posterior','scores','continuation','state']} if first else None),
            reservation=r['admission'],actual_occupation=amounts,person_total=r['person']['value'],issue_fee=r['fees']['value'],
            service=r['service'],assertions=len(r['checks']),mismatches=[q for q in r['checks'] if not q['passed']]))
    public=dict(schema='aegisdc-v6-intake-saved-row-reconciliation-v1',verification_source=report['checker_revision'],
            job=report['job'],source_manifest_sha256=report['source_manifest'],full_checks_sha256=sha(directory/'report.json'),
            additional_facility_calls=report['facility_invocations'],attempts=attempts,units=rows,
            pairs=report['pairs'],interfaces=report['prior_interfaces'],expected_file_sha256=sha(PACK/'expected.json'),
            original_comparison_complete=report['full_frozen_comparison'],review_exception='expired-read: original forecast credits predictably expired information. See separate review record.',
            red_rejection_counted_as_facility=False,research_trials=0)
    write(directory/'public-summary.json',public)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',required=True,choices=['red','green','saved'])
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source-manifest',type=Path,required=True)
    parser.add_argument('--source-sha',required=True)
    parser.add_argument('--units',nargs='*')
    parser.add_argument('--previous',type=Path,nargs='*',default=[])
    args=parser.parse_args()
    if not os.getenv('SLURM_JOB_ID') or sha(args.source_manifest)!=args.source_sha:
        raise ValueError('Missing Slurm or pinned source identity')
    identity=read(args.source_manifest)
    for path,expected in identity['files'].items():
        if sha(ROOT/path)!=expected:
            raise ValueError('Pinned file mismatch: '+path)
    if sha(Path(sys.executable).resolve())!=identity['interpreter_sha256']:
        raise ValueError('Interpreter mismatch')
    args.output.mkdir()
    plan=read(PACK/'manifest.json')
    for f,h in plan['files'].items():
        if sha(PACK/f)!=h:
            raise ValueError('Study input drift: '+f)
    doc=read(PACK/'inputs.json')
    amendment=read(PACK/'input-binding-addendum.json')
    want=read(PACK/'expected.json')
    values=read(PACK/'independent-values.json')
    all_names=plan['order']
    chosen=all_names if args.units is None else args.units
    if not chosen or len(set(chosen))!=len(chosen) or set(chosen)-set(all_names):
        raise ValueError('Undeclared or repeated facility unit')
    report=dict(mode=args.mode,job=os.environ['SLURM_JOB_ID'],source_manifest=sha(args.source_manifest),
        execution_revision=identity['execution_revision'],checker_revision=identity['checker_revision'],
        facility_invocations=0,starts=[],rows=[],interfaces=[],pairs=[],failed=[],not_executed=[],study_trials=0)
    try:
        if args.mode=='red':
            rc=cli('measure-low',doc,amendment,args.output,True,report['starts'])
            error=(args.output/'measure-low/stderr').read_text()
            report.update(expected_red=rc==2 and 'unrecognized arguments: --business-program' in error,
                          rejected_cli_invocations=1,returncode=rc)
            return rc if report['expected_red'] else 1
        if args.mode=='green':
            report['interfaces']=interfaces(doc)
        saved={}
        previous_interfaces=[]
        for previous in args.previous:
            old_report=read(previous/'report.json')
            previous_interfaces=old_report.get('interfaces') or previous_interfaces
            for row in old_report['rows']:
                if (previous/row['unit']/'run/run.json').is_file():
                    saved[row['unit']]=previous/row['unit']
        for index,name in enumerate(chosen):
            try:
                if args.mode=='green':
                    rc=cli(name,doc,amendment,args.output,False,report['starts'])
                    if rc:
                        raise RuntimeError('native CLI rc '+str(rc)+': '+(args.output/name/'stderr').read_text()[-1200:])
                    unit=args.output/name
                else:
                    unit=saved[name]
                source_manifest=read(unit.parent.parent/'source/source-manifest.json')
                native=read(unit/'run/run.json')
                runtime_files=native['code_identity']['files']
                expected_files={k:v for k,v in source_manifest['files'].items()
                    if (k.startswith('src/aegis_dc/') and k.count('/')==2 and k.endswith('.py')) or k=='src/patrol_rsi/contracts.py'}
                if runtime_files!=expected_files:
                    raise ValueError('Native runtime differs from its source archive')
                actual_inputs=inputs(name,doc,amendment)
                if read(unit/'call.json')['input_sha256']!=digest(actual_inputs) or any(
                        read(unit/filename)!=actual_inputs[key] for key,filename in
                         [('scenario','model.json'),('dispatch_program','dispatch-program.json'),('business_program','business-program.json')]):
                    raise ValueError('Actual invocation differs from complete frozen inputs')
                if read(unit/'inputs.json')['boundary_events']!=actual_inputs['boundary_events'] or read(unit/'exit.json')['returncode']!=0:
                    raise ValueError('Actual exogenous inputs or native exit differ')
                row=compare(name,unit,want['units'][name],values)
                row.update(actual_revision=source_manifest['execution_revision'],archive_parent=str(unit.parent),
                           verification_revision=identity['checker_revision'])
                report['rows'].append(row)
                saved[name]=unit
                if not row['passed']:
                    report['failed'].append(dict(unit=name,failing_checks=[c for c in row['checks'] if not c['passed']]))
            except Exception:
                report['failed'].append(dict(unit=name,error=traceback.format_exc()))
                report['not_executed']=chosen[index+1:]
                break
        if set(all_names)<=set(saved):
            report['pairs']=pair_checks(saved)
        if args.mode=='saved':
            report['prior_interfaces']=previous_interfaces
        checked=report['interfaces'] or previous_interfaces
        report['attempt_passed']=(len(report['rows'])==len(chosen) and not report['failed']
                and all(q['passed'] for q in checked) and all(q['matched'] for q in report['pairs']))
        report['full_frozen_comparison']=(report['attempt_passed'] and {r['unit'] for r in report['rows']}==set(all_names)
                and {q['unit'] for q in checked}==set(plan['public_interfaces']) and len(report['pairs'])==len(want['pairs']))
        return 0 if report['attempt_passed'] else 1
    except Exception:
        report['failed'].append(dict(error=traceback.format_exc()))
        return 1
    finally:
        report['facility_invocations']=sum(r['facility_status']=='COMPLETED' for r in report['starts'])
        report['cli_started']=sum(r['cli_started'] for r in report['starts'])
        report['unknown_facility_invocations']=sum(r['facility_status']=='NOT_KNOWN' for r in report['starts'])
        write(args.output/'report.json',report)
        if args.mode=='saved' and 'full_frozen_comparison' in report:
            saved_handoff(report,args.previous,args.output)


if __name__=='__main__':
    sys.exit(main())

