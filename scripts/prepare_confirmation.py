"""Prepare independent confirmation inputs after development, without running a policy."""

import argparse
from copy import deepcopy
from hashlib import sha256
import json
import math
from pathlib import Path
import sys

from comparison_release import (ROOT, LOCK, PROTOCOL, HELD, assignment_key, observation_seed,
    audit_release, audit_lock, _read_nonce, _execution_files)
from inspection_delivery import digest, durable, git, hashes, read, require, write
from prepare_comparison_worlds import _world, _apply_method, _admit, REFERENCE, RECIPES
from development_journal import append, write_record

AMENDMENT='docs/mainline/32-hydraulic-admission-amendment.json'
CORRECTED='configs/full-facility-comparison-held-blueprints-admission-v1.json'
PACKAGE='evidence/mainline/research/32-confirmation-freeze'


def head():
    return git('rev-parse','HEAD').decode().strip()


def admission_blueprints():
    audit_lock(ROOT/LOCK)
    amendment=read(ROOT/AMENDMENT)
    original=read(ROOT/amendment['original_blueprint'])
    amended=read(ROOT/CORRECTED)
    require(amendment['schema']=='aegisdc-frozen-admission-amendment-v1'
            and amendment['classification']=='PHYSICAL_ADMISSION_ONLY_BEFORE_CONFIRMATION'
            and amendment['corrected_blueprint']==CORRECTED
            and amendment['original_sha256']==digest((ROOT/amendment['original_blueprint']).read_bytes())
            and amendment['corrected_sha256']==digest((ROOT/CORRECTED).read_bytes()),
            'Explicit admission amendment identity differs')
    expected=deepcopy(original)
    changes=[]
    for phase,family,variant,old in (('confirmation','misleading-report','mr-a',.875),
                                      ('ablation','misleading-report','am-a',.9375)):
        row=expected[phase][family][0]
        require(row['variant']==variant and row['filter_multiplier']==old,'Original rejected coordinate differs')
        row['filter_multiplier']=1
        changes.append(dict(phase=phase,family=family,variant=variant,field='filter_multiplier',old=old,new=1))
    require(amended==expected and amendment['changes']==changes
            and amendment['physical_calls']==amendment['held_inputs_materialized']==amendment['nonce_reads']==0,
            'Admission amendment exceeds its two prospective physical corrections')
    params={row['id']:row['value'] for row in read(ROOT/'configs/full-facility-mainline-reserve-v6.json')['parameters']}
    screened=[]
    for phase in ('confirmation','ablation'):
        for family,rows in amended[phase].items():
            for row in rows:
                q=math.sqrt(params['pump_pressure_rise']/(params['lake_hydraulic_resistance']*row['filter_multiplier']
                    +params['lake_valve_open_resistance']/params['lake_valve_opening']**2))
                require(q<=params['lake_volume_flow']*(1+params['balance_relative_tolerance']),
                        'Requested inlet point exceeds the accepted V6 flow capacity')
                screened.append(dict(phase=phase,variant=row['variant'],requested_m3_s=q))
    return amended,screened


def prepare(source,nonce_path,folder):
    require(head()==source and not git('status','--porcelain'),'Use a clean immutable preparation source')
    require(folder.resolve()==ROOT/PACKAGE/'prepared-01' and not folder.exists(),'Use the single new preparation directory')
    require(sys.dont_write_bytecode and sys.pycache_prefix is not None and not Path(sys.pycache_prefix).exists(),
            'Use -B and a fresh unused cache prefix')
    blueprints,screened=admission_blueprints()
    gate=audit_release('confirmation','prepare',ROOT/LOCK,nonce_path,None,folder)
    lock=read(ROOT/LOCK)
    nonce=_read_nonce(nonce_path,lock['commitments_sha256']['confirmation'])
    plan=read(ROOT/PROTOCOL)
    phase=plan['phases']['confirmation']
    namespace=plan['seed_policy']['namespaces']['confirmation']
    shared=read(RECIPES)['shared']
    selected={}
    for family,variants in blueprints['confirmation'].items():
        selected[family]=sorted(variants,key=lambda row:assignment_key(nonce,plan['id'],namespace,family,row['variant']))
    folder.mkdir(parents=True)
    (folder/'inputs').mkdir()
    pins=hashes(source,_execution_files(source)|{PROTOCOL,LOCK,AMENDMENT,
        'docs/mainline/evidence/30-root.json','docs/mainline/evidence/31-root.json'})
    receipt=dict(status='FAIL',schema='aegisdc-confirmation-preparation-v1',source=source,pins=pins,gate=gate,
        assigned_worlds=[],prepared_inputs=0,input_hashes={},physical_calls=0,selector_calls=0,
        nonce_commitment=lock['commitments_sha256']['confirmation'],registered_research_trials=0)
    consumed={family:0 for family in selected}
    try:
        for world in phase['worlds']:
            family=world['family']
            recipe=deepcopy(selected[family][consumed[family]])
            consumed[family]+=1
            variant=recipe.pop('variant')
            arm_dir=folder/'inputs'/world['id']
            arm_dir.mkdir()
            append(folder/'attempts.jsonl',dict(status='STARTED_INPUT_WORLD',world_id=world['id'],variant=variant))
            document=_world(read(REFERENCE),world,plan,recipe,shared)
            program=document['dispatch_program']
            program['inspection_program']['realizations']['lookahead-inspect']['seed']=observation_seed(
                nonce,plan['id'],namespace,world['id'],'portable')
            program['sensor_program']['realization']['seed']=observation_seed(nonce,plan['id'],namespace,world['id'],'fixed')
            for arm in phase['arms']:
                item=deepcopy(document)
                _apply_method(item['dispatch_program'],arm)
                eligible=_admit(item,arm)
                raw=(json.dumps(item,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
                name=world['id']+'/'+arm+'.json'
                write(arm_dir/f'{arm}.json',raw)
                receipt['input_hashes'][name]=digest(raw)
                receipt['prepared_inputs']+=1
                require(len(eligible)>=2,'This fixed study world must admit both paid choices at its start')
            receipt['assigned_worlds'].append(dict(world_id=world['id'],family=family,variant=variant))
            append(folder/'attempts.jsonl',dict(status='COMPLETED_INPUT_WORLD',world_id=world['id'],variant=variant,
                                               arms=len(phase['arms'])))
        require(receipt['prepared_inputs']==phase['budget']['attempts']==96,'Confirmation input denominator differs')
        require(head()==source and all(digest((ROOT/p).read_bytes())==h for p,h in pins.items()),'Preparation source changed')
        receipt['status']='PASS_INPUT_ONLY'
    except BaseException as exc:
        receipt.update(error_type=type(exc).__name__,error=str(exc))
        raise
    finally:
        receipt['artifacts']={name:digest((folder/name).read_bytes()) for name in sorted(durable(folder))}
        write(folder/'receipt.json',receipt)
    print(json.dumps(dict(status=receipt['status'],source=source,worlds=len(receipt['assigned_worlds']),
        inputs=receipt['prepared_inputs'],physical_calls=0,selector_calls=0,registered_trials=0)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_subparsers(dest='mode',required=True)
    mode.add_parser('audit-admission')
    prep=mode.add_parser('prepare')
    prep.add_argument('--source',required=True);prep.add_argument('--nonce',type=Path,required=True)
    prep.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.mode=='audit-admission':
        _,rows=admission_blueprints()
        print(json.dumps(dict(status='PASS_EXPLICIT_ADMISSION_AMENDMENT',screened_public_recipes=len(rows),nonce_reads=0)))
    else:
        prepare(args.source,args.nonce,args.output.resolve())


if __name__=='__main__':
    main()
