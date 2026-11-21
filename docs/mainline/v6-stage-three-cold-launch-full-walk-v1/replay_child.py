"""Verification namespace only. A subprocess copies an existing engineering artifact; no facility or policy."""
import fcntl
import gzip
import json
import os
from pathlib import Path
import shutil
import sys

HERE=Path(__file__).resolve().parent
DEPLOY=Path('/share/home/renly/renly-patrol-rsi/mainline/V6-cold-launch-release-v1/source')
sys.path[:0]=[str(DEPLOY/'scripts'),str(DEPLOY/'src')]
for forbidden in ('aegis_dc.plant','aegis_dc.joint_policy','aegis_dc.joint_session'):sys.modules[forbidden]=None
from cold3_launch.binding import QUAL, SURROGATE, Site, check, load_release
from cold3_launch.native import child_admission,entry_record,count_end,envelope
from cold3_runner import digest,read,sha,save
from v6_research.control import doc,once
from aegis_dc.native_compare_run import note


SUPPLEMENT = QUAL / 'full-walk-supplement-01'


def main():
    phase,scenario,h,pin_hash,key,job=sys.argv[1:]
    check(HERE==SUPPLEMENT/'tools' and phase=='V1' and scenario=='full' and os.environ.get('SLURM_JOB_ID'),'SURROGATE_LOCATION')
    pin=read(HERE/'verification-pin.json');check(sha(HERE/'verification-pin.json')==pin_hash and
        sha(Path(__file__))==pin['files']['replay_child.py'] and sha(HERE/'validation-freeze.json')==pin['files']['validation-freeze.json']
        and pin['launch_sha256']==h and pin['namespace']==str(SUPPLEMENT) and pin['output']==str(SUPPLEMENT/phase) and pin['phase']==phase,'VERIFIER_IDENTITY')
    f=read(HERE/'validation-freeze.json');rel=load_release(DEPLOY,h)
    case=key.split('-')[0];suite=SUPPLEMENT/phase
    site=Site(suite/scenario/'sandbox',SURROGATE);alloc=doc(site.activity/'jobs'/case/'worker-claim.json')['allocation']
    check(job==alloc['job'],'JOB_IDENTITY');unit,item=child_admission(rel,site,case,key,alloc)
    spec=next((x for x in f['faults'] if x['id']==scenario),None)
    check((phase=='V1' and scenario=='full') or (phase=='V0' and spec is not None),'SURROGATE_SCOPE')
    planned=f['position_order'] if scenario=='full' else spec['ordered_substitute_entries']
    column=next(c for row in f['rows'] for c in row['order'] if c['slot']==key);donor=f['donor_sources'][column['donor']]
    source=Path(f['source_activity'])/donor['retained_run']
    check(sha(source)==donor['raw_sha256'] and digest(item)==column['request_sha256'],'ORIGINAL_IDENTITY')
    mode=spec['mode'] if spec and spec['slot']==key else 'COPY'
    # This is the substitute arm-entry boundary; no facility/selector is called.
    with (suite/'entry-budget.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        log=suite/'surrogate-entries.jsonl'
        past=[json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
        done=[x['slot'] for x in past if x['case']==scenario]
        check(len(past)<f['resource'][phase]['surrogate_cap'] and done==planned[:len(done)] and
              len(done)<len(planned) and planned[len(done)]==key,'SUBSTITUTE_CAP')
        note(log,dict(case=scenario,slot=key,donor=column['donor'],pid=os.getpid(),job=os.environ['SLURM_JOB_ID']))
    once(unit/'entry.json',entry_record(rel,site,key,job,digest(item)))
    source_run=None
    literal=3 if mode=='NO_RETURN' else 4 if mode=='UNKNOWN_CLOCK' else 49
    # The fake journal is a reconstruction of saved decision epochs, not evaluation.
    with (unit/'decisions.jsonl').open('x',encoding='utf8') as stream:
        for n in range(1,literal+1):stream.write(json.dumps(dict(slot=key,n=n,at=(n-1)/4))+'\n')
        stream.flush();os.fsync(stream.fileno())
    if mode=='NO_RETURN':return 23
    if mode!='UNKNOWN_CLOCK':count_end(unit,key,rel,literal)
    if mode in ('UNKNOWN_CLOCK','WRONG_SOURCE','WRONG_INPUT','BAD_CERTIFICATE','MISSING_LEFT'):
        source_run=read(source)
        if mode=='UNKNOWN_CLOCK':source_run['policy_public_decisions']=None
        elif mode=='WRONG_SOURCE':source_run['code_identity']['files']['src/aegis_dc/joint_policy.py']='0'*64
        elif mode=='WRONG_INPUT':source_run['inputs']['dispatch_program']['id']='WRONG-SAVED-DISPATCH'
        elif mode=='BAD_CERTIFICATE':source_run['policy_public_decisions'][-1]['decision']['certificates']={}
        else:del next(e for e in source_run['private_physical_audit']['epochs'] if e['t']==2)['left']
        save(unit/'run.json.gz',source_run)
    else:
        with source.open('rb') as original,(unit/'run.json.gz').open('xb') as copied:shutil.copyfileobj(original,copied)
    if mode=='ARCHIVE_COLLISION':
        with (unit/'score.json.gz').open('xb') as stream:stream.write(f['fixture_bindings']['sentinel'].encode())
    once(unit/'donor.json',dict(slot=key,donor=column['donor'],mode=mode,original_sha256=donor['raw_sha256'],
        requested=column['request_sha256'],evidence_input=donor['source_input'],original_method=column['donor'].split('-',1)[1]))
    if mode=='MALFORMED_RETURN':
        with (unit/'return.json').open('xb') as stream:stream.write(b'{')
    else:once(unit/'return.json',envelope(rel,site,key,job,digest(item),donor['source_input'],sha(unit/'run.json.gz'),None if mode=='UNKNOWN_CLOCK' else literal))
    return 0


if __name__=='__main__':sys.exit(main())
