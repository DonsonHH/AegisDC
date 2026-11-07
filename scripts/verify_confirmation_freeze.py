"""Verify immutable confirmation inputs and execution identities without nonce or physical calls."""

import argparse,json
from pathlib import Path
from math import fsum

from comparison_release import ROOT,LOCK,PROTOCOL,_execution_files,audit_lock
from inspection_delivery import digest,git,hashes,require,durable,read
from registered_comparison import METHODS,canonical,audit_pair
from prepare_confirmation import AMENDMENT,SEED_AMENDMENT,admission_blueprints

PACKAGE='evidence/mainline/research/32-confirmation-freeze'
PREP=PACKAGE+'/prepared-02'
EXECUTION_LOCK='docs/mainline/evidence/30-confirmation-execution-lock.json'


def verify():
    lock=audit_lock(ROOT/LOCK)
    blueprints,screen=admission_blueprints()
    plan=read(ROOT/PROTOCOL)
    receipt=read(ROOT/PREP/'receipt.json')
    require(receipt['status']=='PASS_INPUT_ONLY' and receipt['prepared_inputs']==96
            and receipt['physical_calls']==receipt['selector_calls']==receipt['registered_research_trials']==0,
            'Input-only preparation did not complete')
    require(durable(ROOT/PREP)==set(receipt['artifacts'])|{'receipt.json'}
            and all(digest((ROOT/PREP/name).read_bytes())==sha for name,sha in receipt['artifacts'].items()),
            'Prepared durable originals differ')
    require(receipt['pins']==hashes(receipt['source'],receipt['pins']),'Original preparation source differs')
    execution=read(ROOT/EXECUTION_LOCK)
    source=execution['execution_source']
    current=git('rev-parse','HEAD').decode().strip()
    require(execution['schema']=='aegisdc-comparison-execution-lock-v1'
            and execution['status'] in ('PENDING_REVIEW','REVIEWED_FOR_EXECUTION')
            and execution['phase']=='confirmation'
            and execution['design_lock_sha256']==digest((ROOT/LOCK).read_bytes())
            and set(execution['execution_pins'])==_execution_files(source)==_execution_files(current)
            and execution['execution_pins']==hashes(source,execution['execution_pins'])==hashes(current,execution['execution_pins']),
            'Frozen executable membership or bytes differ')
    slots=plan['phases']['confirmation']['worlds']
    arms=plan['phases']['confirmation']['arms']
    expected={f"{w['id']}/{arm}.json" for w in slots for arm in arms}
    require(set(receipt['input_hashes'])==set(execution['input_hashes'])==expected
            and execution['input_hashes']==receipt['input_hashes'],'Held input denominator or hashes differ')
    require(execution['budget']==plan['phases']['confirmation']['budget'],'Fixed phase budget differs')
    assignments={row['world_id']:row for row in receipt['assigned_worlds']}
    require(len(assignments)==len(slots)==16,'World assignment denominator differs')
    seed_pairs=[]
    common=[]
    for world in slots:
        assigned=assignments[world['id']]
        available={r['variant']:r for r in blueprints['confirmation'][world['family']]}
        require(assigned['family']==world['family'] and assigned['variant'] in available,'Wrong held family/recipe')
        recipe=available[assigned['variant']]
        fingerprints=[]
        seeds=set()
        for arm in arms:
            name=world['id']+'/'+arm+'.json'
            path=ROOT/PREP/'inputs'/name
            raw=path.read_bytes()
            require(digest(raw)==execution['input_hashes'][name],'Held input raw SHA differs')
            document=json.loads(raw)
            program=document['dispatch_program']
            p={r['id']:r['value'] for r in document['model']['parameters']}
            require(document['duration_s']==10 and document['maximum_step_s']==.01
                    and p['network_service_capacity']==recipe['network_cap']
                    and p['filter_resistance_multiplier']==recipe['filter_multiplier']
                    and document['boundary_events']==recipe['events'],
                    'Held physical recipe or clocks changed')
            require(program['policy_program']['policy']==arm
                    and program['decision_times_s']==plan['decision_times_s']
                    and program['policy_program']['resource_budget']==plan['comparison']['common_admission_budget'],
                    'Held arm/decision/resource identity differs')
            fixed=program['sensor_program']['realization']['seed']
            portable=program['inspection_program']['realizations']['lookahead-inspect']['seed']
            require(type(fixed) is int and 0<=fixed<1<<64 and type(portable) is int and 0<=portable<1<<128,
                    'Private seed is incompatible with its registered interface')
            seeds.add((portable,fixed))
            common_doc=json.loads(raw)
            common_doc['dispatch_program']['policy_program'].pop('policy')
            common_doc['dispatch_program']['policy_program'].pop('options')
            fingerprints.append(digest(canonical(common_doc)))
        require(len(seeds)==1 and len(set(fingerprints))==1,'Reference arms changed the common world, records or action envelope')
        pair=audit_pair((ROOT/PREP/'inputs'/world['id']/(METHODS[0]+'.json'),
                        ROOT/PREP/'inputs'/world['id']/(METHODS[1]+'.json')))
        seed_pairs.extend(seeds)
        common.append(dict(world_id=world['id'],pair_sha256=pair['shared_input_sha256']))
    require(len(set(seed_pairs))==16,'Independent worlds reuse an identical seed pair')
    for family in blueprints['confirmation']:
        variants=[row['variant'] for row in assignments.values() if row['family']==family]
        require(len(variants)==len(set(variants))==4,'Held family assignment reused a recipe')
    return dict(status='PASS_EXACT_CONFIRMATION_FREEZE',preparation_source=receipt['source'],execution_source=source,
        worlds=16,inputs=96,screened_public_recipes=len(screen),fixed_budget=execution['budget'],
        pairs=common,nonce_reads=0,physical_calls=0,selector_calls=0,source_pins=len(execution['execution_pins']))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    value=verify()
    if args.output:
        with args.output.open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in value.items() if k!='pairs'},ensure_ascii=False))

if __name__=='__main__':main()
