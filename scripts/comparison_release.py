"""Bind a frozen comparison design to Git, and audit held-phase release without running it."""

import argparse
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import subprocess

from inspection_delivery import ROOT, git, hashes, write
from registered_comparison import audit_blueprints, canonical, read, require

PROTOCOL = 'docs/mainline/30-comparison-protocol-v1.json'
LOCK = 'docs/mainline/evidence/30-protocol-lock.json'
AUTHORITY = 'docs/mainline/evidence/30-root.json'
FROZEN_STATUS = 'FROZEN_NO_EXECUTION_UNTIL_TICKET_30_ACCEPTED'
HELD = ('confirmation','ablation','robustness')
PINS = (
    PROTOCOL,
    'docs/mainline/30-comparison-design.md',
    'docs/mainline/30-registered-comparison.md',
    'docs/mainline/evidence/29-root.json',
    'docs/mainline/research/closest-methods.md',
    'configs/full-facility-comparison-development-v1.json',
    'configs/full-facility-comparison-held-blueprints-v1.json',
    'configs/full-facility-mainline-reserve-v6.json',
    'configs/materials/reference-r134a-saturation.json',
    'evidence/mainline/engineering/23-interventions/reference/network-full.json',
    'evidence/mainline/engineering/26-candidate/reference/online-baseline-inspect.json',
    'evidence/mainline/engineering/30-comparison-preparation/manifest.json',
    'evidence/mainline/engineering/30-comparison-preparation/preparation-originals.zip',
    'scripts/comparison_release.py',
    'scripts/inspection_delivery.py',
    'scripts/prepare_comparison_worlds.py',
    'scripts/registered_comparison.py',
    'scripts/summarize_comparison_facts.py',
    'src/patrol_rsi/__init__.py',
    'src/patrol_rsi/contracts.py',
)


def digest(raw):
    return sha256(raw).hexdigest()


def _head():
    return git('rev-parse','HEAD').decode().strip()


def _hex(value, length=64):
    return type(value) is str and re.fullmatch(f'[0-9a-f]{{{length}}}',value) is not None


def _ancestor(source, descendant):
    require(_hex(source,40) and _hex(descendant,40),'Use full immutable Git commits')
    result=subprocess.run(['git','merge-base','--is-ancestor',source,descendant],cwd=ROOT,
                          stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
    require(result.returncode==0,'Frozen Git revision is not an ancestor')


def _paths(source):
    runtime={name for name in git('ls-tree','-rz','--name-only',source,'src/aegis_dc').decode().split('\0')
             if name.endswith('.py')}
    require(bool(runtime),'Missing accepted facility runtime')
    return set(PINS)|runtime


def _pin_check(source, pins):
    require(_hex(source,40),'Use the exact full frozen commit')
    _ancestor(source,_head())
    require(set(pins)==_paths(source) and pins==hashes(source,pins)==hashes(_head(),pins)
            and all(digest((ROOT/name).read_bytes())==value for name,value in pins.items()),
            'Frozen protocol, source or working bytes differ')


def _plan():
    plan=read(ROOT/PROTOCOL)
    require(plan['status']==FROZEN_STATUS,'Protocol has not been frozen')
    audit_blueprints(ROOT/PROTOCOL,ROOT/plan['held_blueprints'])
    return plan


def _read_nonce(path, expected):
    require(_hex(expected),'Invalid nonce commitment')
    raw=path.read_bytes()
    require(len(raw)==32 and hmac.compare_digest(digest(raw),expected),'Nonce does not match the commitment')
    return raw


def _audit_nonce(path, expected):
    _read_nonce(path,expected)
    return dict(status='PASS_COMMITMENT',held_inputs_materialized=0,facility_calls=0,selector_calls=0)


def _clean():
    require(not git('status','--porcelain'),'Use a clean repository checkout')


def create_lock(nonce_dir, output):
    _clean()
    _plan()
    source=_head()
    pins=hashes(source,_paths(source))
    _pin_check(source,pins)
    nonce_dir=nonce_dir.resolve()
    require(not nonce_dir.is_relative_to(ROOT.resolve()) and not nonce_dir.exists(),
            'Use a new private directory outside the checkout')
    require(output.resolve()==ROOT/LOCK and not output.exists(),'Use the single canonical new lock path')
    nonce_dir.mkdir(mode=0o700,parents=True)
    commitments={}
    for phase in HELD:
        raw=secrets.token_bytes(32)
        nonce=nonce_dir/f'{phase}.bin'
        with os.fdopen(os.open(nonce,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as file:
            file.write(raw)
            file.flush()
            os.fsync(file.fileno())
        commitments[phase]=digest(raw)
    require(len(set(commitments.values()))==len(HELD),'Phase nonce collision; preserve and review')
    require(_head()==source and not git('status','--porcelain'),'Source changed while committing nonces')
    write(output,dict(schema='aegisdc-comparison-source-lock-v1',status='FROZEN_INPUT_DESIGN',
        protocol_id=read(ROOT/PROTOCOL)['id'],design_commit=source,pins=pins,commitments_sha256=commitments,
        held_inputs_materialized=0,registered_research_trials=0))
    return dict(status='FROZEN_LOCK_WRITTEN',design_commit=source,source_pins=len(pins),phases=list(HELD),
                held_inputs_materialized=0,registered_research_trials=0)


def audit_lock(path):
    plan=_plan()
    lock=read(path)
    require(set(lock)=={'schema','status','protocol_id','design_commit','pins','commitments_sha256',
                       'held_inputs_materialized','registered_research_trials'}
            and lock['schema']=='aegisdc-comparison-source-lock-v1' and lock['status']=='FROZEN_INPUT_DESIGN'
            and lock['protocol_id']==plan['id']
            and lock['held_inputs_materialized']==lock['registered_research_trials']==0,
            'Unknown held phase source lock')
    commitments=lock['commitments_sha256']
    require(set(commitments)==set(HELD) and len(set(commitments.values()))==len(HELD)
            and all(_hex(value) for value in commitments.values()),'Invalid phase commitments')
    _pin_check(lock['design_commit'],lock['pins'])
    return lock


def _committed(path):
    raw=(ROOT/path).read_bytes()
    require(raw==git('cat-file','blob',f'{_head()}:{path}'),'Gate receipt differs from its committed blob')
    return read(ROOT/path)


def _accepted(ticket):
    path=f'docs/mainline/evidence/{ticket}-root.json'
    require((ROOT/path).is_file(),f'Requires accepted ticket {ticket}')
    record=_committed(path)
    require(record.get('status')=='ACCEPTED' and record.get('ticket')==ticket,f'Requires accepted ticket {ticket}')
    return record


def _execution_receipt(phase, lock, plan, directory):
    # Filled by ticket 32 (confirmation) or the separately audited preparation
    # within tickets 35 and 36. A missing or incomplete receipt refuses release.
    path=f'docs/mainline/evidence/30-{phase}-execution-lock.json'
    require((ROOT/path).is_file(),'Requires committed exact phase execution lock')
    receipt=_committed(path)
    require(set(receipt)=={'schema','status','phase','design_lock_sha256','execution_commit','inputs','budget'}
            and receipt['schema']=='aegisdc-comparison-execution-lock-v1'
            and receipt['status']=='REVIEWED_FOR_EXECUTION' and receipt['phase']==phase
            and receipt['design_lock_sha256']==digest((ROOT/LOCK).read_bytes())
            and receipt['execution_commit']==_head() and receipt['budget']==plan['phases'][phase]['budget'],
            'Exact phase execution identity or budget differs')
    phase_plan=plan['phases'][phase]
    expected={f"{world['id']}/{arm}.json" for world in phase_plan['worlds'] for arm in phase_plan['arms']}
    pins=receipt['inputs']
    require(set(pins)==expected and len(expected)==phase_plan['budget']['attempts'],'Phase input denominator differs')
    require(directory.is_dir(),'Requires frozen phase input directory')
    require(all(_hex(h) and digest((directory/name).read_bytes())==h for name,h in pins.items()),
            'Frozen phase input bytes differ')
    _ancestor(lock['design_commit'],receipt['execution_commit'])


def audit_release(phase, stage, lock_path, nonce_path, input_directory, output):
    _clean()
    accepted=_accepted('30')
    require(lock_path.resolve()==ROOT/LOCK,'Use the committed canonical design lock')
    _committed(LOCK)
    lock=audit_lock(lock_path)
    require(accepted.get('protocol_lock')==LOCK
            and accepted.get('protocol_lock_sha256')==digest((ROOT/LOCK).read_bytes())
            and accepted.get('design_commit')==lock['design_commit'],'Ticket 30 does not bind the design lock')
    plan=_plan()
    _accepted('31' if phase=='confirmation' and stage=='prepare' else '32' if phase=='confirmation' else '34')
    require(output is not None and not output.resolve().exists(),'Use a unique, unused phase output directory')
    if stage=='execute':
        require(input_directory is not None,'Execution requires frozen input originals')
        _execution_receipt(phase,lock,plan,input_directory.resolve())
    # Only after exact source and stage checks may this gate read the nonce.
    _read_nonce(nonce_path,lock['commitments_sha256'][phase])
    return dict(status='PASS_PHASE_GATE_AUDIT_ONLY',phase=phase,stage=stage,checked_commit=_head(),
        budget=plan['phases'][phase]['budget'],held_inputs_materialized=0,facility_calls=0,selector_calls=0)


def assignment_key(nonce, protocol_id, namespace, family, variant):
    value=hmac.digest(nonce,canonical(['assignment',protocol_id,namespace,family,variant]),'sha256')
    return (value.hex(),variant)


def observation_seed(nonce, protocol_id, namespace, seed_key, channel):
    require(channel in ('portable','fixed'),'Unknown registered seed channel')
    value=hmac.digest(nonce,canonical(['seed',protocol_id,namespace,seed_key,channel]),'sha256')
    return int.from_bytes(value[:16],'big')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    nonce=commands.add_parser('audit-nonce')
    nonce.add_argument('nonce',type=Path)
    nonce.add_argument('--sha256',required=True)
    create=commands.add_parser('create-lock')
    create.add_argument('--nonce-dir',type=Path,required=True)
    create.add_argument('--output',type=Path,default=ROOT/LOCK)
    lock=commands.add_parser('audit-lock')
    lock.add_argument('lock',type=Path)
    release=commands.add_parser('audit-release')
    release.add_argument('--phase',choices=HELD,required=True)
    release.add_argument('--stage',choices=('prepare','execute'),required=True)
    release.add_argument('--lock',type=Path,required=True)
    release.add_argument('--nonce',type=Path,required=True)
    release.add_argument('--input-directory',type=Path)
    release.add_argument('--output',type=Path)
    args=parser.parse_args()
    try:
        if args.command=='audit-nonce':
            result=_audit_nonce(args.nonce,args.sha256)
        elif args.command=='create-lock':
            result=create_lock(args.nonce_dir,args.output)
        elif args.command=='audit-lock':
            frozen=audit_lock(args.lock)
            result=dict(status='PASS_DESIGN_LOCK',design_commit=frozen['design_commit'],source_pins=len(frozen['pins']),
                        held_inputs_materialized=0,registered_research_trials=0)
        else:
            result=audit_release(args.phase,args.stage,args.lock,args.nonce,args.input_directory,args.output)
    except (OSError,ValueError,KeyError,TypeError,subprocess.CalledProcessError) as exc:
        parser.exit(2,f'{exc}\n')
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))


if __name__=='__main__':
    main()
