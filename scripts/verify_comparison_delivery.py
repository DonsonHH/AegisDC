"""Verify the protocol, input-only preparation, and review corrections from saved bytes."""

import argparse
from hashlib import sha256
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
from zipfile import ZipFile

from comparison_release import LOCK, PROTOCOL, audit_lock
from inspection_delivery import ROOT, git, hashes, require
from registered_comparison import METHODS, REFERENCE_ARMS, audit_blueprints, canonical, read

PACKAGE='evidence/mainline/engineering/30-comparison-preparation'
REVIEW=f'{PACKAGE}/review-and-corrections'


def digest(raw):
    return sha256(raw).hexdigest()


def _archive(folder, name, expected):
    manifest=read(ROOT/folder/'manifest.json')
    raw=(ROOT/folder/name).read_bytes()
    require(digest(raw)==manifest['archive_sha256'],'Original preparation archive SHA differs')
    with ZipFile(io.BytesIO(raw)) as archive:
        paths=archive.namelist()
        require(len(paths)==len(set(paths))==expected and set(paths)==set(manifest['members']),
                'Original archive roles differ')
        members={p:archive.read(p) for p in paths}
    for path,value in members.items():
        p=PurePosixPath(path)
        require(not p.is_absolute() and '..' not in p.parts and '__pycache__' not in p.parts
                and p.suffix not in ('.pyc','.pyo') and digest(value)==manifest['members'][path],
                'Invalid archive member')
    return manifest,members


def _verified_input_originals(members,plan):
    base='input-preparation/30-development-inputs-02'
    receipt=json.loads(members[base+'/receipt.json'])
    require(receipt['status']=='PASS' and receipt['attempted']==receipt['passed']==36
            and receipt['facility_calls']==receipt['selector_calls']==receipt['registered_research_trials']==0,
            'Input-only preparation receipt differs')
    trials=plan['phases']['development']
    arms=REFERENCE_ARMS+METHODS
    checked=0
    for world in trials['worlds']:
        ident=world['id']
        pair,common=[],[]
        for arm in arms:
            path=f'{ident}/{arm}.json'
            raw=members[base+'/'+path]
            require(digest(raw)==receipt['artifacts'][path],'Prepared input differs')
            item=json.loads(raw)
            program=item['dispatch_program']
            policy=program['policy_program']
            require(policy.pop('policy')==arm and item['duration_s']==world['duration_s']
                    and program['decision_times_s']==plan['decision_times_s']
                    and policy['resource_budget']==plan['comparison']['common_admission_budget'],
                    'Compiled arm, common clock or resource budget differs')
            if arm in METHODS:
                pair.append(digest(canonical(item)))
            policy.pop('options')
            common.append(digest(canonical(item)))
            checked+=1
        stored=receipt['checks'][ident]
        require(len(set(pair))==1 and pair[0]==stored['pair_sha256']
                and len(set(common))==1 and common[0]==stored['common_six_arm_sha256'],
                'Original primary or six-arm parity differs')
    return checked


def _refusals(members,plan,blueprints,cli):
    variants=('negative-threshold-and-invalid-cost','premature-release','empty-stop-and-retry-forever',
        'missing-metric-rules-and-limits','illegal-exogenous-input','negative-robust-demand','empty-ablation-rules')
    count=0
    from copy import deepcopy
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as folder:
        path=Path(folder)
        for i,name in enumerate(variants):
            source=json.loads(members[f'independent/Standards/probes/{name}.json'])
            d=deepcopy(plan if i<4 else blueprints)
            if i==0:
                for k in ('minimum_worthwhile_gain_s','cost_bounds'):
                    d['comparison'][k]=source['comparison'][k]
            elif i==1:
                d['phases']['confirmation'].update(ticket='31',release='IMMEDIATE')
            elif i==2:
                d['attempt_policy'].update(stop_conditions=[],repeated_attempts='Retry forever')
            elif i==3:
                d['comparison'].pop('metric_definition')
            elif i==4:
                d['confirmation']['network-restorable'][0]['events'].append(
                    dict(time_s=1,parameter_id='coolant_inventory',value=-1,source_note='Invalid fixture'))
            elif i==5:
                d['robustness']['load-level']['reference']['offered_demand']=-1
            else:
                d['masks']={k:{} for k in d['masks']}
            check=path/f'{name}.json'
            check.write_bytes(canonical(d))
            args=['audit-plan',str(check)] if i<4 else ['audit-blueprints',str(ROOT/PROTOCOL),str(check)]
            result=subprocess.run([sys.executable,'-B','-X','utf8',str(cli),*args],cwd=ROOT,
                capture_output=True,check=False)
            require(result.returncode==2 and bool(result.stderr) and not result.stdout,
                    'A known invalid declaration was not cleanly refused: '+name)
            count+=1
    return count


def verify(delivery):
    require(git('rev-parse','HEAD').decode().strip()==delivery and not git('status','--porcelain'),
            'Use a clean checkout of the precise protocol delivery')
    require(git('rev-parse','pre-meeting-20261103^{}').decode().strip()=='076d9aa15c5bc99a5b7985f296e15543b7b0f3d7',
            'Historical preservation tag differs')
    lock=audit_lock(ROOT/LOCK)
    plan=read(ROOT/PROTOCOL)
    blueprint=read(ROOT/plan['held_blueprints'])
    draft=audit_blueprints(ROOT/PROTOCOL,ROOT/plan['held_blueprints'])
    prep,originals=_archive(PACKAGE,'preparation-originals.zip',81)
    corrections,reviews=_archive(REVIEW,'originals.zip',77)
    require(corrections['original_standards_probes']==7
            and corrections['original_static_findings']=={'Spec':1,'Standards':2},'Original review findings differ')
    paths=[LOCK,f'{PACKAGE}/manifest.json',f'{PACKAGE}/preparation-originals.zip',
           f'{REVIEW}/manifest.json',f'{REVIEW}/originals.zip','scripts/verify_comparison_delivery.py']
    require(hashes(delivery,paths)=={p:digest((ROOT/p).read_bytes()) for p in paths},
            'Saved delivery differs from committed original bytes')
    compiled=_verified_input_originals(originals,plan)
    corrected=_refusals(reviews,plan,blueprint,ROOT/'scripts/registered_comparison.py')
    for original in prep['input_preparation'].values():
        require(original['committed_source_identity']==hashes(original['source'],original['committed_source_identity']),
                'Original input-only preparation source differs')
    return dict(status='PASS_SAVED_PROTOCOL_DELIVERY',delivery=delivery,design_commit=lock['design_commit'],
        protocol_lock_sha256=digest((ROOT/LOCK).read_bytes()),design_source_pins=len(lock['pins']),
        archived_members=len(originals)+len(reviews),prepared_development_inputs=compiled,
        refused_original_probe_types=corrected,blueprints=draft,facility_calls=0,selector_calls=0,
        seed_reads=0,held_inputs_materialized=0,registered_research_trials=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delivery',required=True)
    args=parser.parse_args()
    print(json.dumps(verify(args.delivery),ensure_ascii=False,allow_nan=False))


if __name__=='__main__':
    main()
