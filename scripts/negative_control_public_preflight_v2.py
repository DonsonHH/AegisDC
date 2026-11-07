"""Run a frozen public-input validation fixture; never simulate or choose work."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

from inspection_delivery import ROOT, digest, durable, git, hashes, read, require, unchanged, write

PROTOCOL='docs/mainline/28-public-input-preflight-v2.json'


def append(path, value):
    with path.open('ab') as f:
        f.write((json.dumps(value,ensure_ascii=False,allow_nan=False)+'\n').encode())
        f.flush()
        os.fsync(f.fileno())


def initial_frame(nominal, ledger, requests, public_profiles, counters):
    from aegis_dc.decision_view import DecisionGateway
    current=deepcopy(ledger)
    for extra in public_profiles:
        require(extra['facility_id']==current['facility_id'] and set(extra['entity_ids'])==set(current['entity_ids']),
                'Public registries differ')
        for field in ('sources','observables'):
            items={row['id']:row for row in current[field]}
            for row in extra[field]:
                require(row['id'] not in items or items[row['id']]==row,'Conflicting public registry declaration')
                if row['id'] not in items:
                    current[field].append(deepcopy(row));items[row['id']]=row
    plan=dict(schema='aegisdc-public-preparation-plan-v1',id='ticket28-public-input-validation',basis='synthetic_assumption',
              time_unit='s',decision_times_s=[0],requests=deepcopy(requests))
    counters['initial_public_frames']+=1
    return DecisionGateway(nominal,current,plan).next_frame()


def capture(source):
    require(git('rev-parse','HEAD').decode().strip()==source and not git('status','--porcelain'),
            'Use the exact clean committed preflight source')
    protocol=read(ROOT/PROTOCOL)
    folder=ROOT/protocol['output']
    require(not folder.exists(),'Preflight output exists; no overwrite or automatic retry')
    runtime=[p for p in git('ls-tree','-rz','--name-only',source,'src').decode().strip('\0').split('\0')
             if p.endswith('.py') and '__pycache__' not in p]
    pins={role:hashes(source,paths) for role,paths in dict(runtime=runtime,tools=protocol['tools'],
        inputs=[PROTOCOL,protocol['input'],protocol['context']]).items()}
    require(unchanged(source,pins),'Preflight bytes differ from committed source')
    folder.mkdir(parents=True)
    write(folder/'declaration.json',dict(artifacts=protocol['durable_outputs'],terminal='receipt.json',
        classification=protocol['classification'],forbidden_calls=protocol['forbidden_calls']))
    write(folder/'attempt.json',dict(status='STARTED',source=source,pins=pins,
        executable=sys.executable,python=sys.version,executable_sha256=digest(Path(sys.executable).read_bytes()),
        utc=datetime.now(timezone.utc).isoformat(),scope='Public declaration validation only, no actual facility state passed to policy.'))
    counters=dict(validate_scenario_calls=0,initial_public_frames=0,assess_risks_calls=0,
                  physical_calls=0,selector_calls=0,closure_calls=0)
    terminal=dict(status='FAIL',source=source,pins=pins,counters=counters,error=None,source_guard=False,registered_research_trials=0)
    try:
        for name in ('scenarios','frames','risks'):
            (folder/name).mkdir()
        sys.path.insert(0,str(ROOT/'src'))
        from aegis_dc.scenario import validate_scenario
        from aegis_dc.risk_scenarios import assess_risks
        cases=read(ROOT/protocol['input'])['cases']
        validated={}
        for name,case in cases.items():
            append(folder/'attempts.jsonl',dict(operation='validate_scenario',case=name,status='STARTED'))
            counters['validate_scenario_calls']+=1
            validated[name]=validate_scenario(case['model'])
            write(folder/'scenarios'/f'{name}.json',validated[name])
            append(folder/'attempts.jsonl',dict(operation='validate_scenario',case=name,status='COMPLETED'))
        write(folder/'validated-scenarios.json',validated)
        frames,risks={},{}
        for name in ('normal','false_report'):
            program=cases[name]['replay_inputs']['dispatch_program']
            profiles=[program['sensor_program']['profile']['ledger'],
                      program['inspection_program']['profile']['nonfixed_profile']['registry']]
            frames[name]=initial_frame(program['nominal_knowledge'],program['evidence_ledger'],
                                       program['preparation_requests'],profiles,counters)
            write(folder/'frames'/f'{name}.json',frames[name])
            risks[name]={}
            for role,model,catalog in (
                ('policy',program['policy_program']['options']['belief_model'],program['policy_program']['options']['catalog']),
                ('closure',program['closure_program']['belief_model'],program['closure_program']['risk_catalog'])):
                append(folder/'attempts.jsonl',dict(operation='assess_risks',case=name,role=role,status='STARTED'))
                counters['assess_risks_calls']+=1
                risks[name][role]=assess_risks(frames[name],model,catalog)
                write(folder/'risks'/f'{name}-{role}.json',risks[name][role])
                append(folder/'attempts.jsonl',dict(operation='assess_risks',case=name,role=role,status='COMPLETED'))
        name='too_late'
        declared=cases[name]['public_preparation'];closure=cases[name]['closure_program']
        frames[name]=initial_frame(declared['nominal_knowledge'],declared['evidence_ledger'],declared['requests'],[],counters)
        write(folder/'frames'/f'{name}.json',frames[name])
        append(folder/'attempts.jsonl',dict(operation='assess_risks',case=name,role='closure',status='STARTED'))
        counters['assess_risks_calls']+=1
        risks[name]=dict(closure=assess_risks(frames[name],closure['belief_model'],closure['risk_catalog']))
        write(folder/'risks'/f'{name}-closure.json',risks[name]['closure'])
        append(folder/'attempts.jsonl',dict(operation='assess_risks',case=name,role='closure',status='COMPLETED'))
        write(folder/'frames.json',frames);write(folder/'risks.json',risks)
        require(counters==protocol['expected_counters'],'Public preflight call budget differs')
        require(durable(folder)==set(protocol['durable_outputs']),'Preflight durable role set differs')
        terminal['status']='PASS_PUBLIC_INPUT_VALIDATION_ONLY'
    except Exception as error:
        terminal.update(error=dict(type=type(error).__name__,message=str(error)))
        append(folder/'attempts.jsonl',dict(status='FAILED',error_type=type(error).__name__,message=str(error)))
    finally:
        try:
            terminal['source_guard']=unchanged(source,pins)
        except (OSError,subprocess.SubprocessError) as error:
            terminal.update(source_guard=False,source_guard_error=str(error))
        if not terminal['source_guard']:
            terminal['status']='FAIL'
        terminal['artifacts']={name:digest((folder/name).read_bytes()) for name in sorted(durable(folder))}
        write(folder/'receipt.json',terminal)
    require(terminal['status']=='PASS_PUBLIC_INPUT_VALIDATION_ONLY','Public preflight failed; preserve output and stop')
    return dict(status=terminal['status'],source=source,counters=counters,registered_research_trials=0)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True)
    args=p.parse_args()
    print(json.dumps(capture(args.source),ensure_ascii=False))
