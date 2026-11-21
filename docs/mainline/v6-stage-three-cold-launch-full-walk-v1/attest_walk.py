"""Same-allocation readback of the frozen full-walk seals and duplicate-start rule."""
import json
import os
from pathlib import Path
import sys

TOOLS=Path(__file__).resolve().parent
DEPLOY=Path('/share/home/renly/renly-patrol-rsi/mainline/V6-cold-launch-release-v1/source')
sys.path[:0]=[str(DEPLOY/'scripts'),str(DEPLOY/'src')]
for name in ('aegis_dc.plant','aegis_dc.joint_policy','aegis_dc.joint_session'):
    sys.modules[name]=None
from cold3_launch.binding import QUAL, SURROGATE, GateError, Site, load_release
from cold3_launch.control import start
from cold3_runner import sha
from v6_research.control import doc,once


class SealedReview:
    def __init__(self,proof):
        self.proof=proof

    def authorize(self,release,revision,site):
        require(self.proof['purpose']==site.purpose==SURROGATE and self.proof['activity']==str(site.activity)
                and self.proof['launch']==release.sha and self.proof['approval']['review_revision']==revision,'sealed substitute identity')
        return self.proof['approval']


def require(ok,name):
    if not ok:raise ValueError(name)


def main():
    launch,pin_hash=sys.argv[1:]
    root=QUAL/'full-walk-supplement-01'
    out=root/'V1';job=os.environ.get('SLURM_JOB_ID')
    require(job and TOOLS==root/'tools' and os.environ.get('SLURM_CPUS_PER_TASK')=='1','allocation / namespace')
    pin=doc(TOOLS/'verification-pin.json')
    require(sha(TOOLS/'verification-pin.json')==pin_hash and pin['launch_sha256']==launch
            and sha(Path(__file__))==pin['seal_reader']['sha256'],'seal reader pin')
    def no_transport(event,args):
        if event in ('socket.connect','subprocess.Popen'):
            raise PermissionError('The readback has no scheduler transport or child budget')
    sys.addaudithook(no_transport)
    rel=load_release(DEPLOY,launch)
    f=doc(TOOLS/'validation-freeze.json')
    result=doc(out/'result.json');readback=doc(out/'full/readback.json');suite=Site(out/'full/sandbox',SURROGATE)
    require(result['status']=='PASS' and result['job']==job and result['verifier_sha256']==pin_hash
            and result['cases'][0]['readback_sha256']==sha(out/'full/readback.json'),'successful original full traversal')
    proof=doc(suite.claim/'consumption.json')
    entry_log=out/'surrogate-entries.jsonl';before=sha(entry_log)
    entries=[json.loads(line) for line in entry_log.read_bytes().splitlines()]
    require([e['slot'] for e in entries]==f['position_order'] and len(entries)==66,'substitute order')
    # The original verifier already probes admit(). Also call the public controller
    # start() using the existing synthetic proof; no scheduler is supplied or reachable.
    try:start(suite,rel,SealedReview(proof),proof['approval']['review_revision'],None)
    except GateError as error:duplicate=error.code
    else:raise AssertionError('duplicate controller start admitted')
    require(duplicate==f['full']['repeat_start'] and before==sha(entry_log),'repeat before new entry')
    last=suite.activity/'jobs'/f['rows'][-1]['row']
    worker=doc(last/'worker-result.json');finished=doc(suite.activity/'finished.json')
    seals={'worker_panel':sha(last/'panel.json'),'worker_receipt_panel':worker['panel_sha256'],
           'controller_panel':sha(suite.activity/'panel.json'),'finished_panel':finished['panel_sha256']}
    require(len(set(seals.values()))==1 and finished['purpose']==SURROGATE and finished['launch']==launch and
            (last/'panel.json').read_bytes()==(suite.activity/'panel.json').read_bytes(),'worker/controller byte seals')
    require(doc(suite.activity/'progress.json')==readback and doc(suite.activity/'panel.json')==readback['panel'],'final complete ledger/panel')
    checks=doc(out/'checks.json')
    worker_replay=[c for c in checks if c['check']=='worker replay']
    require(len(worker_replay)==1 and worker_replay[0]['ok'] and worker_replay[0]['actual']==f['full']['duplicate_worker'],'duplicate worker')
    bound=[];seen=set()
    for e,slot in zip(entries,f['position_order'],strict=True):
        row=slot.split('-',1)[0];folder=suite.activity/'jobs'/row;unit=folder/'arms'/slot
        start_rec,spawn,ret=(doc(unit/n) for n in ('entry.json','spawn.json','return.json'))
        claim=doc(folder/'worker-claim.json')
        require(start_rec['pid']==spawn['pid']==e['pid']==ret['pid'] and start_rec['parent']==spawn['parent']==ret['parent']==claim['worker_pid']
                and start_rec['slot']==spawn['slot']==ret['slot']==slot and start_rec['launch']==launch and
                e['job']==job and e['pid'] not in seen,'recorded isolated child '+slot)
        seen.add(e['pid']);bound.append(dict(slot=slot,donor=e['donor'],child_pid=e['pid'],worker_pid=claim['worker_pid']))
    pairs={p['row']+'-'+p['control']:p['category'] for p in readback['panel']['comparisons']}
    require(pairs==f['full']['expected']['material_pairs'] and readback['internal_exact']==3234 and
            readback['manual_exact']==196 and not readback['accounting_errors'] and not readback['known_unstarted']
            and not readback['potential_slots'] and not readback['unknown_internal'],'frozen full account')
    require(len(readback['jobs'])==24 and all(r['worker_sealed'] and r['committed'] and r['terminal']['state']=='COMPLETED'
            and r['terminal']['exit']=='0:0' for r in readback['jobs']),'all 24 independent simulated commits')
    once(out/'supplement-seals.json',dict(schema='cold-full-walk-dual-seal-v1',job=job,launch=launch,pin_sha256=pin_hash,
        source='fixed V1/full saved evidence',linked_children=bound,ledger_sha256=sha(out/'full/readback.json'),
        checks_sha256=sha(out/'checks.json'),surrogate_entries_sha256=before,duplicate_worker=worker_replay[0]['actual'],
        duplicate_full_controller_start=duplicate,repeat_start_new_entries=0,panel_seals=seals,
        worker_result_sha256=sha(last/'worker-result.json'),last_commit_sha256=sha(last/'committed.json'),
        controller_finished_sha256=sha(suite.activity/'finished.json'),control_progress_sha256=sha(suite.activity/'progress.json'),
        paired=pairs,denominators=readback['panel']['denominators'],row_commits=24,known_starts=66,validated_returns=66,
        known_saved_clocks=readback['internal_exact'],donor_manual_issues=readback['manual_exact'],
        real_facility=0,real_policy=0,real_study=0,real_grant_creation=0,real_grant_consumption=0))
    print('Dual panel seals and 66 existing process identities checked; duplicate start rejected before entry.',flush=True)


if __name__=='__main__':
    main()
