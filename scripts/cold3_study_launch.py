"""Cold study production start/status/worker/arm. No surrogate or alternate-root switch."""
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from cold3_launch.binding import REAL, SHARED, Site, Review, GateError, check, host, load_release
from cold3_launch.control import start,worker,admitted
from cold3_launch.ledger import summary
from cold3_launch.native import real_child
from cold3_launch.transport import ColdSlurm,allocation


def main():
    import json,os
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['start','status','worker','arm'])
    p.add_argument('--manifest-sha',required=True);p.add_argument('--approval-revision');p.add_argument('--case');p.add_argument('--slot')
    a=p.parse_args();site=Site(SHARED,REAL);os.umask(0o077)
    try:
        if a.operation=='start':check(a.approval_revision is not None,'AUTHORIZATION_REQUIRED')
        host(ROOT,a.operation in ('start','status'));rel=load_release(ROOT,a.manifest_sha)
        if a.operation=='start':
            check(a.case is None and a.slot is None,'ARGUMENTS')
            return 0 if start(site,rel,Review(),a.approval_revision,ColdSlurm()) else 1
        check(a.approval_revision is None,'ARGUMENTS')
        if a.operation=='status':
            check(not a.case and not a.slot,'ARGUMENTS')
            if site.claim.exists():admitted(site,rel)
            state=summary(site,rel)
            print(json.dumps(dict(claim_present=site.claim.exists(),activity_present=site.activity.exists(),state=state),ensure_ascii=False))
            return 0
        check(a.case in rel.cases,'WORKER_ORDER')
        alloc=allocation()
        if a.operation=='worker':
            check(a.slot is None,'ARGUMENTS');return 0 if worker(site,rel,a.case,alloc)['passed'] else 1
        check(a.slot in rel.keys(a.case),'SLOT_ORDER');real_child(rel,site,a.case,a.slot,alloc)
        return 0
    except (GateError,ValueError,KeyError,OSError) as exc:
        print(json.dumps(dict(code=getattr(exc,'code','OPERATION_UNRESOLVED'),detail=str(exc))),file=sys.stderr);return 2


if __name__=='__main__':sys.exit(main())
