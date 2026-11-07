"""Run only the registered development phase, from the exact precompiled originals."""

import argparse
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile

from comparison_release import AUTHORITY, LOCK, PROTOCOL, audit_lock
from inspection_delivery import ROOT, digest, git, require
from registered_comparison import read
from verify_comparison_delivery import _verified_input_originals

PREP='evidence/mainline/engineering/30-comparison-preparation'
MEMBER_PREFIX='input-preparation/30-development-inputs-02'
PHASE='development'


def head():
    return git('rev-parse','HEAD').decode().strip()


def committed(path):
    raw=(ROOT/path).read_bytes()
    require(raw==git('cat-file','blob',f'{head()}:{path}'),'Committed input bytes differ: '+path)
    return json.loads(raw)


def load_roster():
    authority=committed(AUTHORITY)
    require(authority['status']=='ACCEPTED' and authority['ticket']=='30'
            and authority['protocol']==PROTOCOL and authority['protocol_lock']==LOCK,
            'Requires accepted ticket 30 and its frozen protocol')
    committed(LOCK)
    lock=audit_lock(ROOT/LOCK)
    require(authority['design_commit']==lock['design_commit']
            and authority['protocol_lock_sha256']==digest((ROOT/LOCK).read_bytes()),
            'Acceptance does not bind the frozen design')
    protocol=read(ROOT/PROTOCOL)
    phase=protocol['phases'][PHASE]
    roles=read(ROOT/PREP/'manifest.json')
    archive=ROOT/PREP/'preparation-originals.zip'
    require(digest(archive.read_bytes())==roles['archive_sha256'],'Prepared originals archive differs')
    slots=[]
    originals={}
    with ZipFile(archive) as source:
        require(len(source.namelist())==len(set(source.namelist())),'Repeated archived member')
        for row in phase['worlds']:
            arms=phase['arms']
            shift=(row['slot']-1)%len(arms)
            for arm in arms[shift:]+arms[:shift]:
                member=f"{MEMBER_PREFIX}/{row['id']}/{arm}.json"
                raw=source.read(member)
                sha=digest(raw)
                require(roles['members'][member]==sha,'Development original bytes differ')
                slot=dict(index=len(slots)+1,world_id=row['id'],family=row['family'],arm=arm,
                          duration_s=row['duration_s'],scheduled_decisions=len(protocol['decision_times_s']),
                          input_member=member,input_sha256=sha)
                slots.append(slot)
                originals[member]=raw
        receipt=f'{MEMBER_PREFIX}/receipt.json'
        raw=source.read(receipt)
        require(digest(raw)==roles['members'][receipt],'Preparation receipt differs')
        require(_verified_input_originals(dict(originals,**{receipt:raw}),protocol)==36,'Development input parity differs')
    budget=phase['budget']
    require(budget==dict(attempts=len(slots),simulated_charge_s=sum(s['duration_s'] for s in slots),
        scheduled_decisions=sum(s['scheduled_decisions'] for s in slots)),
        'Development schedule does not match the frozen budget')
    return protocol,slots,originals


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('plan',))
    parser.parse_args()
    try:
        protocol,slots,_=load_roster()
        print(json.dumps(dict(status='PASS_DEVELOPMENT_PLAN_ONLY',phase=PHASE,slots=slots,
            budget=protocol['phases'][PHASE]['budget'],facility_calls=0,selector_calls=0,
            held_inputs_read=0,seed_reads=0,registered_research_trials=0),allow_nan=False))
    except (OSError,ValueError,KeyError,TypeError,subprocess.CalledProcessError) as exc:
        parser.exit(2,f'{exc}\n')


if __name__=='__main__':
    main()
