"""Explicit research CLI. Approval comes only from the canonical published review decision."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]

from v6_research.binding import GitHubReview, GateError, REAL, SHARED, load_release, production_host
from v6_research.control import Site, snapshot, start, worker, admitted
from v6_research.slurm import Slurm, current_allocation


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('operation',choices=['start','worker','status'])
    parser.add_argument('--manifest-sha',required=True)
    parser.add_argument('--approval-revision')
    parser.add_argument('--case')
    args=parser.parse_args()
    try:
        if args.operation=='start' and not args.approval_revision:
            raise GateError('AUTHORIZATION_REQUIRED')
        release=load_release(ROOT,args.manifest_sha)
        production_host(ROOT,args.operation!='worker')
        site=Site(SHARED,REAL)
        os.umask(0o077)
        os.chdir(ROOT)
        os.environ.update(PYTHONPATH=str(ROOT/'src'),PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1',PYTHONHASHSEED='0')
        if args.operation=='start':
            if args.case:raise GateError('JOB_ORDER')
            ok=start(site,release,GitHubReview(),args.approval_revision,Slurm())
            print(json.dumps(dict(completed=ok,ledger=str(site.activity/'progress.json'))))
            return 0 if ok else 1
        if args.operation=='worker':
            if args.approval_revision or not args.case:raise GateError('JOB_ORDER')
            receipt=worker(site,release,args.case,current_allocation())
            print(json.dumps(receipt));return 0 if receipt['passed'] else 1
        admitted(site,release)
        state=snapshot(site,release)
        state['read_only_scheduler_observations']={}
        for j in state['jobs']:
            if j['case'] in state['unresolved_scheduler_outcomes'] and 'submitted' in j:
                try:observation=Slurm().observe(j['submitted'])
                except Exception as exc:observation=dict(job=j['submitted'],state='UNRESOLVED',detail=str(exc))
                state['read_only_scheduler_observations'][j['case']]=observation
        print(json.dumps(state));return 0
    except GateError as error:
        print(json.dumps(dict(code=error.code,detail=str(error))),file=sys.stderr);return 2
    except (ValueError,KeyError,OSError) as error:
        print(json.dumps(dict(code='OPERATION_UNRESOLVED',detail=str(error))),file=sys.stderr);return 1


if __name__=='__main__':sys.exit(main())
