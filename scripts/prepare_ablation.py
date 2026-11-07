"""Prepare only the original registered masks after accepted primary analysis."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from comparison_release import ROOT,PROTOCOL,LOCK,audit_lock,audit_release,_read_nonce,assignment_key,observation_seed,_execution_files
from inspection_delivery import read,require,git,hashes,digest,durable,write
from development_journal import append
from prepare_confirmation import admission_blueprints
from prepare_comparison_worlds import _world,_apply_method,_admit,REFERENCE,RECIPES
from ablation_planner import ARMS,planner_view,session_type,planning_scope,fingerprint

PACKAGE='evidence/mainline/research/35-ablation'
PREP=PACKAGE+'/prepared-01'
EXTENSION='docs/mainline/35-planner-executor-extension.json'
EXECUTION_LOCK='docs/mainline/evidence/30-ablation-execution-lock.json'

def public_document(world,recipe):
    document=_world(read(REFERENCE),world,read(ROOT/PROTOCOL),deepcopy(recipe),read(RECIPES)['shared'])
    _apply_method(document['dispatch_program'],'evidence_consistent_contingent')
    return document

def validate_view(document,mask,*,choose=False):
    from aegis_dc.dispatch_policy import choose_work
    from aegis_dc.evidence_projection import validate_projection,validate_value_projection_bindings
    from aegis_dc.lookahead_policy import validate_execution_bindings
    from aegis_dc.action_value import assess_action_value
    original=deepcopy(document);_admit(document,'evidence_consistent_contingent')
    instances=[];session=session_type(mask,instances)(document['dispatch_program'],document['duration_s'])
    with planning_scope(session):
        frame=session._frame(0,None);policy=session.planner_program['policy_program']
        validate_projection(frame,policy['evidence_projection'])
        validate_execution_bindings(policy,document['dispatch_program']['inspection_program'],frame=frame)
        candidates={c['id']:c for c in policy['candidates']}
        validate_value_projection_bindings(policy['options'],candidates,policy['evidence_projection'])
        assess_action_value(frame,policy['options']['belief_model'],policy['options']['catalog'],policy['options']['value_model'])
        choice=choose_work(frame,policy,dict(issued=[],work_feedback=[]),
            intervention_declaration=policy['intervention_declaration'],closure_program=None) if choose else None
    require(document==original and session.program==original['dispatch_program'],'Mask changed actual execution input')
    actual=session.execution_program;view=session.planner_program
    return dict(actual_catalog_tasks=len(session.catalog_program['submissions']),planner_candidates=len(view['policy_program']['candidates']),
        actual_intervention_bindings=len(actual['intervention_program']['bindings']),
        planner_intervention_bindings=len(view['intervention_program']['bindings']),
        unmodeled_question_retained=any(q['quantification']=='UNMODELED' for q in view['policy_program']['options']['catalog']['questions']),
        chosen_kind=choice['work_intention']['kind'] if choice and choice['work_intention'] and 'kind' in choice['work_intention'] else
            next((c['kind'] for c in view['policy_program']['candidates'] if choice and c['id']==choice['chosen_candidate_id']),None))

def audit_masks():
    blueprints,_=admission_blueprints();plan=read(ROOT/PROTOCOL);worlds=plan['phases']['ablation']['worlds']
    count=0;fixture=None
    for family,recipes in blueprints['ablation'].items():
        members=[w for w in worlds if w['family']==family]
        require(len(members)==len(recipes)==2,'Original ablation family denominator changed')
        for world,recipe in zip(members,recipes,strict=True):
            recipe=deepcopy(recipe);recipe.pop('variant')
            document=public_document(world,recipe)
            for arm in ARMS:
                result=validate_view(document,arm,choose=fixture is None and arm=='without_joint_crew_planning')
                count+=1
                if fixture is None and arm=='without_joint_crew_planning' and result['planner_candidates']==1:fixture=result
    require(fixture is not None,'Public joint-crew fixture is missing')
    return dict(status='PASS_PUBLIC_MASKS',public_worlds=8,checked_arm_views=count,nonce_reads=0,
        physical_calls=0,selector_calls=1,actual_plant_preserved=True,actual_executor_preserved=True,joint_fixture=fixture,
        classification='ENGINEERING_PUBLIC_DECLARATION_AND_SINGLE_SELECTOR_CHECK_NOT_REGISTERED_TRIAL')

def prepare(source,nonce_path,folder):
    require(git('rev-parse','HEAD').decode().strip()==source and not git('status','--porcelain'),'Use clean exact ablation preparation source')
    require(folder==ROOT/PREP and not folder.exists(),'Use unique original ablation input directory')
    require(sys.dont_write_bytecode and sys.pycache_prefix is not None and not Path(sys.pycache_prefix).exists(),'Use -B and unused cache prefix')
    blueprints,_=admission_blueprints();plan=read(ROOT/PROTOCOL);phase=plan['phases']['ablation']
    gate=audit_release('ablation','prepare',ROOT/LOCK,nonce_path,None,folder)
    lock=read(ROOT/LOCK);nonce=_read_nonce(nonce_path,lock['commitments_sha256']['ablation'])
    namespace=plan['seed_policy']['namespaces']['ablation']
    selected={f:sorted(rows,key=lambda r:assignment_key(nonce,plan['id'],namespace,f,r['variant'])) for f,rows in blueprints['ablation'].items()}
    consumed={f:0 for f in selected};folder.mkdir(parents=True);(folder/'inputs').mkdir()
    pins=hashes(source,_execution_files(source)|{PROTOCOL,LOCK,EXTENSION,'docs/mainline/evidence/34-root.json',
        'docs/mainline/32-hydraulic-admission-amendment.json','docs/mainline/32-seed-interface-amendment.json'})
    receipt=dict(schema='aegisdc-ablation-preparation-v1',status='FAIL',source=source,pins=pins,gate=gate,
        assigned_worlds=[],prepared_inputs=0,input_hashes={},physical_calls=0,selector_calls=0,
        nonce_reads=2,nonce_commitment=lock['commitments_sha256']['ablation'],registered_research_trials=0)
    try:
        for world in phase['worlds']:
            family=world['family'];recipe=deepcopy(selected[family][consumed[family]]);consumed[family]+=1
            variant=recipe.pop('variant');directory=folder/'inputs'/world['id'];directory.mkdir()
            append(folder/'attempts.jsonl',dict(status='STARTED_INPUT_WORLD',world_id=world['id'],variant=variant))
            document=public_document(world,recipe);program=document['dispatch_program']
            program['inspection_program']['realizations']['lookahead-inspect']['seed']=observation_seed(nonce,plan['id'],namespace,world['id'],'portable')
            program['sensor_program']['realization']['seed']=observation_seed(nonce,plan['id'],namespace,world['id'],'fixed')>>64
            for arm in phase['arms']:
                validate_view(document,arm)
                item=deepcopy(document);item['ablation_mask']=arm
                raw=(json.dumps(item,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
                name=world['id']+'/'+arm+'.json';write(directory/(arm+'.json'),raw)
                receipt['input_hashes'][name]=digest(raw);receipt['prepared_inputs']+=1
            receipt['assigned_worlds'].append(dict(world_id=world['id'],family=family,variant=variant))
            append(folder/'attempts.jsonl',dict(status='COMPLETED_INPUT_WORLD',world_id=world['id'],variant=variant,arms=4))
        require(receipt['prepared_inputs']==phase['budget']['attempts']==32,'Ablation input denominator differs')
        require(git('rev-parse','HEAD').decode().strip()==source and all(digest((ROOT/n).read_bytes())==h for n,h in pins.items()),'Ablation preparation source changed')
        receipt['status']='PASS_INPUT_ONLY'
    except BaseException as exc:
        receipt.update(error_type=type(exc).__name__,error=str(exc));raise
    finally:
        receipt['artifacts']={n:digest((folder/n).read_bytes()) for n in sorted(durable(folder))};write(folder/'receipt.json',receipt)
    print(json.dumps(dict(status=receipt['status'],worlds=8,inputs=32,physical_calls=0,selector_calls=0)))

def verify():
    audit_lock(ROOT/LOCK);lock=read(ROOT/EXECUTION_LOCK);receipt=read(ROOT/PREP/'receipt.json');plan=read(ROOT/PROTOCOL)
    source=lock['execution_source'];current=git('rev-parse','HEAD').decode().strip();pins=lock['execution_pins']
    require(set(pins)==_execution_files(source)==_execution_files(current)
            and pins==hashes(source,pins)==hashes(current,pins)
            and all(digest((ROOT/n).read_bytes())==h for n,h in pins.items()),'Ablation executable source or working bytes differ')
    require(receipt['status']=='PASS_INPUT_ONLY' and receipt['prepared_inputs']==32
            and receipt['physical_calls']==receipt['selector_calls']==0,'Ablation input preparation incomplete')
    require(receipt['pins']==hashes(receipt['source'],receipt['pins']),'Original ablation preparation source differs')
    require(durable(ROOT/PREP)==set(receipt['artifacts'])|{'receipt.json'}
            and all(digest((ROOT/PREP/n).read_bytes())==h for n,h in receipt['artifacts'].items()),'Ablation durable inputs differ')
    require(lock['schema']=='aegisdc-comparison-execution-lock-v1'
            and lock['status'] in ('PENDING_REVIEW','REVIEWED_FOR_EXECUTION')
            and lock['phase']=='ablation' and lock['design_lock_sha256']==digest((ROOT/LOCK).read_bytes())
            and lock['budget']==plan['phases']['ablation']['budget'] and lock['input_hashes']==receipt['input_hashes'],
            'Ablation lock/input/budget scope differs')
    expected={w['id']+'/'+arm+'.json' for w in plan['phases']['ablation']['worlds'] for arm in ARMS}
    require(set(lock['input_hashes'])==expected,'Ablation denominator or arm roster differs')
    seeds=[];blueprints,_=admission_blueprints();assigned={r['world_id']:r for r in receipt['assigned_worlds']}
    require(len(assigned)==8,'Ablation world assignments differ')
    for world in plan['phases']['ablation']['worlds']:
        assignment=assigned[world['id']]
        recipe=next(r for r in blueprints['ablation'][world['family']] if r['variant']==assignment['variant'])
        require(assignment['family']==world['family'],'Ablation assigned family differs')
        actual=[];pair=set()
        for arm in ARMS:
            name=world['id']+'/'+arm+'.json';raw=(ROOT/PREP/'inputs'/name).read_bytes()
            require(digest(raw)==lock['input_hashes'][name],'Ablation input SHA differs')
            document=json.loads(raw);require(document.pop('ablation_mask')==arm,'Ablation mask identity differs')
            parameters={r['id']:r['value'] for r in document['model']['parameters']}
            require(document['duration_s']==10 and document['maximum_step_s']==.01
                and document['boundary_events']==recipe['events']
                and parameters['network_service_capacity']==recipe['network_cap']
                and parameters['filter_resistance_multiplier']==recipe['filter_multiplier'],
                'Ablation physical recipe changed')
            actual.append(fingerprint(document));program=document['dispatch_program']
            fixed=program['sensor_program']['realization']['seed'];portable=program['inspection_program']['realizations']['lookahead-inspect']['seed']
            require(type(fixed) is int and 0<=fixed<1<<64 and type(portable) is int and 0<=portable<1<<128,'Ablation seed interface differs')
            pair.add((fixed,portable))
        require(len(set(actual))==len(pair)==1,'Ablation arms changed actual execution, evidence or randomness')
        seeds.extend(pair)
    require(len(set(seeds))==8,'Ablation world seed pair reused')
    for family,recipes in blueprints['ablation'].items():
        require({r['variant'] for r in assigned.values() if r['family']==family}=={r['variant'] for r in recipes},
                'Ablation family recipe assignment differs')
    return dict(status='PASS_EXACT_ABLATION_FREEZE',worlds=8,inputs=32,source=source,source_pins=len(pins),nonce_reads=0,physical_calls=0,selector_calls=0)

def fixture(source,folder):
    from ablation_planner import simulate_masked
    from ablation_run_evidence import save_native
    from development_journal import write_record
    from registered_development import _guard
    book=read(ROOT/'docs/mainline/35-adapter-engineering.json')
    require(git('rev-parse','HEAD').decode().strip()==source and not git('status','--porcelain'),'Use clean exact engineering witness source')
    require(folder==ROOT/book['output'] and not folder.exists(),'Use unique engineering witness output')
    stage=ROOT/'.work/35-engineering-native-01';require(not stage.exists(),'Engineering native staging already exists')
    require(sys.dont_write_bytecode and sys.pycache_prefix is not None and not Path(sys.pycache_prefix).exists(),'Use -B and unused engineering cache prefix')
    pins=hashes(source,_execution_files(source)|{'docs/mainline/35-adapter-engineering.json',EXTENSION,PROTOCOL,LOCK})
    document=public_document(book['world'],book['recipe']);document['dispatch_program']['decision_times_s']=book['decision_times_s']
    document['ablation_mask']=book['mask'];folder.mkdir(parents=True)
    write_record(folder/'attempt.json',dict(source=source,classification=book['classification'],charged_simulated_s=3,charged_decisions=3,pins=pins))
    write(folder/'input.json',document)
    receipt=dict(status='FAIL',source=source,physical_calls=0,charged_s=3,scheduled_decisions=3,registered_research_trials=0,automatic_retries=0)
    try:
        _guard(source,pins);receipt['physical_calls']=1;result=simulate_masked(document)
        count=save_native(stage,folder,document,result,source);require(count==3,'Engineering decision count differs')
        marker=result['ablation_execution_audit']
        require(len(marker['actual_catalog_task_ids'])==2 and len(marker['planner_candidate_ids'])==1
            and len(marker['actual_binding_task_ids'])==1 and marker['planner_binding_task_ids']==[],
            'Engineering actual/planner capability witness differs')
        require(all(d['choice']['work_intention'] is None or len(d['choice']['work_intention']['crew'])==1 for d in result['policy_public_decisions']),
            'Joint task selected under singleton planning mask')
        audit=read(folder/'audit.json');require(not audit['applied_effects'],'Engineering mask executed a removed intervention')
        require(any(w['status']=='completed' for w in result['work_records']),'Singleton inspection did not actually complete')
        _guard(source,pins);receipt['status']='PASS_ENGINEERING_VIEW_WITNESS'
    except BaseException as exc:receipt.update(error_type=type(exc).__name__,error=str(exc));raise
    finally:
        receipt['artifacts']={n:digest((folder/n).read_bytes()) for n in sorted(durable(folder))};write(folder/'receipt.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k!='artifacts'}))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('audit-masks','prepare','verify','fixture'))
    p.add_argument('--source');p.add_argument('--nonce',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.mode=='prepare':prepare(a.source,a.nonce,a.output.resolve())
    elif a.mode=='fixture':fixture(a.source,a.output.resolve())
    else:
        value=audit_masks() if a.mode=='audit-masks' else verify()
        if a.output:write(a.output,value)
        print(json.dumps(value,ensure_ascii=False))
if __name__=='__main__':main()
