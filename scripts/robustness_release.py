"""Release only the original four robustness contrasts after the pre36 audit."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

from comparison_release import ROOT,LOCK,PROTOCOL,_read_nonce,observation_seed,_execution_files,_paths
from inspection_delivery import read,require,git,hashes,digest,durable,write
from registered_comparison import audit_pair,canonical
from prepare_comparison_worlds import _world,_apply_method,_admit,REFERENCE,RECIPES
from development_journal import append

EXTENSION='docs/mainline/36-prospective-extension.json'
PACKAGE='evidence/mainline/research/36-robustness'
PREP=PACKAGE+'/prepared-01'
EXECUTION_LOCK='docs/mainline/evidence/30-robustness-execution-lock.json'
AUTHORIZATION='docs/mainline/evidence/36-execution-authorization.json'
PREPARATION_AUTHORIZATION='docs/mainline/evidence/36-preparation-authorization.json'
NONCE=Path('C:/Users/Donson/.codex/private-research/AegisDC/30-comparison-v1/robustness.bin')

def head():return git('rev-parse','HEAD').decode().strip()

def preparation_pins(source):
    return hashes(source,_execution_files(source)|{EXTENSION,LOCK,PROTOCOL,
        'docs/mainline/evidence/pre36-alignment.json','docs/mainline/evidence/34-root.json','docs/mainline/evidence/35-root.json',
        'evidence/mainline/engineering/26-candidate/reference/online-baseline-inspect.json',
        'evidence/mainline/engineering/23-interventions/reference/network-full.json'})

def audit_design():
    lock=read(ROOT/LOCK);extension=read(ROOT/EXTENSION)
    require(read(ROOT/'docs/mainline/evidence/pre36-alignment.json')['status']=='ACCEPTED_TO_CONTINUE_WITH_EXPLICIT_COVERAGE_LIMITS',
            'Requires accepted substantive01–35 audit')
    require(read(ROOT/'docs/mainline/evidence/34-root.json')['status']=='ACCEPTED'
            and read(ROOT/'docs/mainline/evidence/35-root.json')['status']=='ACCEPTED','Requires accepted analysis and ablations')
    original=lock['design_commit'];pins=lock['pins']
    require(set(pins)==_paths(original) and pins==hashes(original,pins),'Original design pins differ')
    require(extension['original_design_commit']==original and extension['automatic_retries']==0,'Prospective design identity differs')
    current=hashes(head(),pins);changed={n for n in pins if pins[n]!=current[n]}
    require(changed==set(extension['changed_original_pins'])=={'src/aegis_dc/verified_closure.py'},'Undeclared old-source change')
    for n,row in extension['changed_original_pins'].items():
        require(row['original_sha256']==pins[n] and row['corrected_sha256']==current[n]
            and hashes(row['accepted_correction_source'],[n])[n]==current[n],'Corrected closure identity differs')
    require(all(digest((ROOT/n).read_bytes())==h for n,h in current.items()),'Current working design bytes differ')
    blueprint='configs/full-facility-comparison-held-blueprints-admission-v1.json'
    require(git('cat-file','blob','2dfe5537e4f95fa605f325b060ef32223dafb4f6:'+blueprint)==(ROOT/blueprint).read_bytes(),
            'Accepted blueprint changed after seen outcomes')
    return read(ROOT/PROTOCOL),read(ROOT/blueprint),lock

def compile_world(world,plan,blueprints):
    block=blueprints['robustness'][world['family']]
    recipe=deepcopy(block['shared']);recipe.pop('variant')
    document=_world(read(REFERENCE),world,plan,recipe,read(RECIPES)['shared'])
    program=document['dispatch_program'];policy=program['policy_program'];level=block[world['level']]
    # Pure public compilation uses a paired placeholder, never a held nonce.
    # Preparation replaces both with the registered block-wise HMAC realization.
    placeholder=300000+int(world['comparison'][1:])
    program['inspection_program']['realizations']['lookahead-inspect']['seed']=placeholder
    program['sensor_program']['realization']['seed']=placeholder
    params={p['id']:p for p in document['model']['parameters']}
    if world['family']=='load-level':
        rate=level['offered_demand'];params['service_demand']['value']=rate
        for row in policy['options']['catalog']['demand']:row['rate']=rate
        for question in policy['options']['catalog']['questions']:
            question['consequence_bounds']['unserved_service_unit_s']['interval']=[0,world['duration_s']*rate]
    elif world['family']=='sensor-coverage':
        sensor=program['sensor_program']['profile']
        next(m for m in sensor['measurements'] if m['id']=='rectifier-meter')['enabled']=level['rectifier_meter_enabled']
        policy['evidence_projection']['background_sensor_profile']=deepcopy(sensor)
    elif world['family']=='reserve-path':params['ups_in_service']['value']=level['ups_in_service']
    else:
        require(world['family']=='model-error','Unknown robustness axis')
        for local in policy['options']['value_model']['question_models']:
            for variant in local['variants']:
                for capacity in variant['after_capacity'].values():capacity['network']=level['declared_fallback_capacity']
    return document

def differences(a,b,path=''):
    if isinstance(a,dict) and isinstance(b,dict):
        require(set(a)==set(b),'Contrast changes object fields')
        return set().union(*(differences(a[k],b[k],path+'.'+k if path else k) for k in a))
    if isinstance(a,list) and isinstance(b,list):
        require(len(a)==len(b),'Contrast changes list length')
        return set().union(*(differences(x,y,path+'['+str(x.get('id',i) if isinstance(x,dict) else i)+']') for i,(x,y) in enumerate(zip(a,b,strict=True))))
    return set() if a==b else {path}

def check_contrast(reference,perturbed,family):
    actual=differences(reference,perturbed)
    if family=='load-level':
        expected={'model.parameters[service_demand].value',
          'dispatch_program.policy_program.options.catalog.demand[0].rate',
          'dispatch_program.policy_program.options.catalog.questions[cooling].consequence_bounds.unserved_service_unit_s.interval[1]'}
        require(actual==expected,'Load contrast exceeds its three declared quantities')
    elif family=='sensor-coverage':
        require(actual=={'dispatch_program.sensor_program.profile.measurements[rectifier-meter].enabled',
            'dispatch_program.policy_program.evidence_projection.background_sensor_profile.measurements[rectifier-meter].enabled'},
            'Sensor contrast changes more than actual/public enabled flag')
    elif family=='reserve-path':require(actual=={'model.parameters[ups_in_service].value'},'Reserve contrast changes more than effective UPS availability')
    else:require(bool(actual) and all(p.startswith('dispatch_program.policy_program.options.value_model.question_models[')
            and '.after_capacity.' in p and p.endswith('.network') for p in actual),'Forecast contrast changes actual execution or another knowledge field')
    return sorted(actual)

def describe_public():
    plan,blueprints,_=audit_design();rows=[];documents={}
    for world in plan['phases']['robustness']['worlds']:
        doc=compile_world(world,plan,blueprints);documents[world['id']]=doc
        program=doc['dispatch_program'];policy=program['policy_program']
        params={r['id']:r['value'] for r in doc['model']['parameters']}
        meter=next(m for m in program['sensor_program']['profile']['measurements'] if m['id']=='rectifier-meter')
        local=policy['options']['value_model']['question_models'][0]
        rows.append(dict(id=world['id'],offered_demand=params['service_demand'],
            public_demand=policy['options']['catalog']['demand'][0]['rate'],
            rectifier_meter_enabled=meter['enabled'],ups_in_service=params['ups_in_service'],
            actual_fallback_capacity=program['intervention_program']['bindings'][0]['setting'],
            forecast_capacity=next(iter(local['variants'][0]['after_capacity'].values()))['network'],
            graphs_sha256=digest(canonical(doc['model']['graphs']))))
    worlds=plan['phases']['robustness']['worlds']
    contrasts={worlds[i]['comparison']:check_contrast(documents[worlds[i]['id']],documents[worlds[i+1]['id']],worlds[i]['family']) for i in range(0,8,2)}
    require(not any(n.startswith('aegis_dc') for n in sys.modules),'Pure description imported project models')
    return dict(status='PASS_PUBLIC_DESIGN_ONLY',worlds=rows,contrasts=contrasts,contrast_blocks=4,
        physical_calls=0,selector_calls=0,admission_calls=0,nonce_reads=0)

def public_audit(output):
    require(output==ROOT/'evidence/mainline/engineering/36-public-admission/preflight-01.json'
            and not output.exists(),'Use the single declared public preflight output')
    source=head();require(not git('status','--porcelain'),'Pin public admission source before calls')
    pins=preparation_pins(source)
    write(output.with_name(output.stem+'.start.json'),dict(status='STARTED_PUBLIC_PREFLIGHT',source=source,pins=pins))
    rows=[];documents={};calls=0
    result=dict(status='FAILED_PUBLIC_PREFLIGHT',source=source,physical_calls=0,selector_calls=0,nonce_reads=0,registered_research_trials=0)
    try:
        require(sys.dont_write_bytecode and all(digest((ROOT/n).read_bytes())==h for n,h in pins.items()),'Use -B and exact public preflight working inputs')
        plan,blueprints,_=audit_design();phase=plan['phases']['robustness']
        for world in phase['worlds']:
            doc=compile_world(world,plan,blueprints);documents[world['id']]=doc
            for arm in phase['arms']:
                item=deepcopy(doc);_apply_method(item['dispatch_program'],arm)
                calls+=1;admitted=_admit(item,arm)
                rows.append(dict(world_id=world['id'],family=world['family'],level=world['level'],arm=arm,
                    admitted=admitted,model_sha256=digest(canonical(item['model']))))
        contrasts={phase['worlds'][i]['comparison']:check_contrast(documents[phase['worlds'][i]['id']],documents[phase['worlds'][i+1]['id']],phase['worlds'][i]['family']) for i in range(0,8,2)}
        require(head()==source and all(digest((ROOT/n).read_bytes())==h for n,h in pins.items()),'Public preflight source/input changed')
        result.update(status='PASS_PUBLIC_ROBUSTNESS_ADMISSION',rows=rows,contrasts=contrasts,worlds=8,source_guard='PASS')
    except BaseException as exc:result.update(error_type=type(exc).__name__,error=str(exc));raise
    finally:result['finite_admission_calls']=calls;write(output,result)
    return result

def prepare(source,folder):
    require(head()==source and not git('status','--porcelain'),'Clean exact preparation source required')
    require(folder==ROOT/PREP and not folder.exists(),'Unique original robustness preparation required')
    plan,blueprints,lock=audit_design();phase=plan['phases']['robustness']
    progress=read(ROOT/'docs/mainline/progress.json')
    require(progress['current_ticket']=='36' and progress['research_trials']['robustness']['attempts']==0,'Wrong frontier or robustness already started')
    public=read(ROOT/'evidence/mainline/engineering/36-public-admission/preflight-01.json')
    require(public['status']=='PASS_PUBLIC_ROBUSTNESS_ADMISSION','Public input admission must pass before unsealing')
    public_start=read(ROOT/'evidence/mainline/engineering/36-public-admission/preflight-01.start.json')
    require(public_start['source']==public['source'] and public_start['pins']==preparation_pins(public['source'])==preparation_pins(source),
            'Public admission source/input freeze differs from preparation')
    approval=read(ROOT/PREPARATION_AUTHORIZATION)
    require(approval['status']=='REVIEWED_FOR_INPUT_PREPARATION' and approval['source_pins']==preparation_pins(source),
            'Requires exact independently reviewed preparation source')
    require(sys.dont_write_bytecode and sys.pycache_prefix is not None and not Path(sys.pycache_prefix).exists(),'Use -B and unused cache prefix')
    folder.mkdir(parents=True);(folder/'inputs').mkdir()
    receipt=dict(status='FAILED_INPUT_PREPARATION',source=source,input_hashes={},prepared_inputs=0,assigned_worlds=[],
        physical_calls=0,selector_calls=0,finite_admission_calls=0,nonce_reads=0,registered_research_trials=0,
        pins=preparation_pins(source))
    append(folder/'attempts.jsonl',dict(status='STARTED_INPUT_PREPARATION',source=source,expected_inputs=16))
    try:
        require(all(digest((ROOT/n).read_bytes())==h for n,h in receipt['pins'].items()),'Preparation working source/input differs before nonce')
        nonce=_read_nonce(NONCE,lock['commitments_sha256']['robustness']);receipt['nonce_reads']=1
        namespace=plan['seed_policy']['namespaces']['robustness']
        for world in phase['worlds']:
            doc=compile_world(world,plan,blueprints);program=doc['dispatch_program']
            program['inspection_program']['realizations']['lookahead-inspect']['seed']=observation_seed(nonce,plan['id'],namespace,world['comparison'],'portable')
            program['sensor_program']['realization']['seed']=observation_seed(nonce,plan['id'],namespace,world['comparison'],'fixed')>>64
            directory=folder/'inputs'/world['id'];directory.mkdir()
            for arm in phase['arms']:
                item=deepcopy(doc);_apply_method(item['dispatch_program'],arm);receipt['finite_admission_calls']+=1;_admit(item,arm)
                raw=(json.dumps(item,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
                name=world['id']+'/'+arm+'.json';write(directory/(arm+'.json'),raw)
                receipt['input_hashes'][name]=digest(raw);receipt['prepared_inputs']+=1
            audit_pair(tuple(directory/(a+'.json') for a in phase['arms']))
            receipt['assigned_worlds'].append(dict(world_id=world['id'],comparison=world['comparison'],family=world['family'],level=world['level']))
            append(folder/'attempts.jsonl',dict(status='COMPLETED_INPUT_WORLD',world_id=world['id'],arms=2))
        require(receipt['prepared_inputs']==16 and head()==source,'Preparation source or input count changed')
        require(all(digest((ROOT/n).read_bytes())==h for n,h in receipt['pins'].items()),'Preparation working source changed')
        receipt['status']='PASS_INPUT_ONLY'
    except BaseException as exc:receipt.update(error_type=type(exc).__name__,error=str(exc));raise
    finally:
        receipt['artifacts']={n:digest((folder/n).read_bytes()) for n in sorted(durable(folder))};write(folder/'receipt.json',receipt)
    return dict(status=receipt['status'],inputs=16,worlds=8,nonce_reads=1,physical_calls=0,selector_calls=0)

def verify_freeze():
    plan,blueprints,_=audit_design();lock=read(ROOT/EXECUTION_LOCK);prep=read(ROOT/PREP/'receipt.json')
    source=lock['execution_source'];pins=lock['execution_pins']
    require(set(pins)==_execution_files(source)==_execution_files(head())
        and pins==hashes(source,pins)==hashes(head(),pins)
        and all(digest((ROOT/n).read_bytes())==h for n,h in pins.items()),'Frozen executable source or working bytes differ')
    require(lock['interpreter_sha256']==digest(Path(sys.executable).read_bytes())
        and lock['design_lock_sha256']==digest((ROOT/LOCK).read_bytes())
        and lock['extension_sha256']==digest((ROOT/EXTENSION).read_bytes())
        and lock['budget']==plan['phases']['robustness']['budget'],'Execution interpreter/protocol/budget differs')
    require(prep['status']=='PASS_INPUT_ONLY' and prep['prepared_inputs']==16 and prep['physical_calls']==prep['selector_calls']==0,'Prepared inputs incomplete')
    require(durable(ROOT/PREP)==set(prep['artifacts'])|{'receipt.json'}
        and all(digest((ROOT/PREP/n).read_bytes())==h for n,h in prep['artifacts'].items()),'Prepared originals differ')
    require(prep['pins']==hashes(prep['source'],prep['pins']),'Preparation source pins differ')
    expected={w['id']+'/'+a+'.json' for w in plan['phases']['robustness']['worlds'] for a in plan['phases']['robustness']['arms']}
    require(set(lock['input_hashes'])==set(prep['input_hashes'])==expected and lock['input_hashes']==prep['input_hashes'],'Frozen roster differs')
    docs={};seeds={}
    for world in plan['phases']['robustness']['worlds']:
        paths=tuple(ROOT/PREP/'inputs'/world['id']/(a+'.json') for a in plan['phases']['robustness']['arms'])
        audit_pair(paths)
        for path in paths:require(digest(path.read_bytes())==lock['input_hashes'][path.relative_to(ROOT/PREP/'inputs').as_posix()],'Input SHA differs')
        doc=read(paths[0]);program=doc['dispatch_program'];docs[world['id']]=doc
        require(program['closure_program'] is None and doc['model']['graphs']==read(ROOT/'configs/full-facility-mainline-reserve-v6.json')['graphs'],'Full facility or null closure changed')
        pair=(program['inspection_program']['realizations']['lookahead-inspect']['seed'],program['sensor_program']['realization']['seed'])
        require(type(pair[0]) is int and 0<=pair[0]<1<<128 and type(pair[1]) is int and 0<=pair[1]<1<<64,'Seed interface differs')
        seeds.setdefault(world['comparison'],set()).add(pair)
    worlds=plan['phases']['robustness']['worlds']
    for i in range(0,8,2):check_contrast(docs[worlds[i]['id']],docs[worlds[i+1]['id']],worlds[i]['family'])
    require(len(seeds)==4 and all(len(v)==1 for v in seeds.values()) and len(set(next(iter(v)) for v in seeds.values()))==4,'Contrast seeds not paired/distinct')
    return dict(status='PASS_EXACT_ROBUSTNESS_FREEZE',execution_source=source,inputs=16,blocks=4,physical_calls=0,selector_calls=0,nonce_reads=0)

def freeze(source):
    require(head()==source and not git('status','--porcelain'),'Freeze a clean exact source')
    plan,_,_=audit_design();prep=read(ROOT/PREP/'receipt.json')
    require(prep['status']=='PASS_INPUT_ONLY','No passing prepared inputs')
    data=dict(schema='aegisdc-robustness-execution-lock-v1',status='PENDING_INDEPENDENT_REVIEW',phase='robustness',
        design_lock_sha256=digest((ROOT/LOCK).read_bytes()),extension_sha256=digest((ROOT/EXTENSION).read_bytes()),
        execution_source=source,execution_pins=hashes(source,_execution_files(source)),interpreter_sha256=digest(Path(sys.executable).read_bytes()),
        input_hashes=prep['input_hashes'],budget=plan['phases']['robustness']['budget'])
    write(ROOT/EXECUTION_LOCK,data);return dict(status='PENDING_INDEPENDENT_REVIEW',execution_source=source,inputs=16)

if __name__=='__main__':
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='mode',required=True)
    p=sub.add_parser('audit-public');p.add_argument('--output',type=Path,required=True)
    p=sub.add_parser('prepare');p.add_argument('--source',required=True)
    p=sub.add_parser('freeze');p.add_argument('--source',required=True)
    sub.add_parser('verify')
    sub.add_parser('describe-public')
    p=sub.add_parser('audit-contrast');p.add_argument('--left',type=Path,required=True);p.add_argument('--right',type=Path,required=True)
    p.add_argument('--family',choices=['load-level','sensor-coverage','reserve-path','model-error'],required=True)
    args=parser.parse_args()
    result=public_audit(args.output.resolve()) if args.mode=='audit-public' else prepare(args.source,ROOT/PREP) if args.mode=='prepare' else freeze(args.source) if args.mode=='freeze' else describe_public() if args.mode=='describe-public' else dict(status='PASS_DECLARED_CONTRAST',paths=check_contrast(read(args.left),read(args.right),args.family)) if args.mode=='audit-contrast' else verify_freeze()
    print(json.dumps(result,ensure_ascii=False))
