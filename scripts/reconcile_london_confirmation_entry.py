"""Read-only reconciliation of saved public engineering evidence, zero core calls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--activity',type=Path,required=True);p.add_argument('--verify',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or socket.gethostname().split('.')[0]=='mu01':raise SystemExit('Remote allocation required')
    evidence={};ok=True
    for name in ('author-01','red-01','green-01'):
        attempt=a.activity/name;identity=read(attempt/'source/execution-source.json')
        source_checks={f:sha(attempt/'source'/f)==meta['sha256'] for f,meta in identity['files'].items()}
        ok=ok and all(source_checks.values())
        files={}
        # Durable set: all output JSONs plus exact launch archive/source manifest,
        # submission script and process logs. No runtime caches are evidence.
        paths=list((attempt/'output').rglob('*.json'))+[attempt/n for n in ('source.tar','source/execution-source.json','job.slurm','stdout.log','stderr.log','exit-status.txt')]
        for path in paths:
            files[str(path.relative_to(attempt))]=dict(sha256=sha(path),bytes=path.stat().st_size)
        evidence[name]=dict(source_revision=identity['source_commit'],source_checks=source_checks,files=files)
    green=read(a.activity/'green-01/output/qualification.json');terminal=read(a.activity/'green-01/output/batch/terminal.json');verification=read(a.verify/'qualification.json')
    compact_units=[dict(id=u['id'],passed=u['passed'],assertions=len(u['assertions']),failed=[c for c in u['assertions'] if not c['matches']]) for u in verification['verification']['units']]
    pairs=verification['verification']['pairs']
    counts=verification['verification']['counts']
    interfaces=[dict(id=u['id'],matches=u['matches'],callback_calls=u.get('callback_calls',u.get('actual',{}).get('callback_calls',0) if isinstance(u.get('actual'),dict) else 0)) for u in green['interfaces']]
    rows=[dict(condition_id=r['condition_id'],status=r['status'],comparison_status=r['comparison_status'],valid_comparison=r['valid_comparison'],arms={k:{f:v[f] for f in ('stage','L','U','costs','requested_actions','request_times','hard_constraints_ok','verification_result')} for k,v in r['arms'].items()}) for r in terminal['rows']]
    result=dict(status='PASS_SAVED_RECONCILIATION' if ok and verification['status']=='PASS_FINITE_PUBLIC_ENGINEERING' else 'FAIL',job_id=os.environ['SLURM_JOB_ID'],host=socket.gethostname(),model_calls=0,
        execution_source=green['source_identity']['source_commit'],verification_source=verification['source_identity']['source_commit'],
        original_qualification_sha256=sha(a.activity/'green-01/output/qualification.json'),verification_sha256=sha(a.verify/'qualification.json'),
        counts=counts,units=compact_units,pairs=pairs,interfaces=interfaces,rows=rows,
        assertion_counts=dict(arm_and_unit=sum(u['assertions'] for u in compact_units),pair=sum(len(p['assertions']) for p in pairs),aggregate=len(verification['verification']['totals']),interfaces=len(interfaces)),
        malformed_count_regression=verification['malformed_count_regression'],archive_count_regression=verification['archive_count_regression'],
        all_original_source_hashes_match=ok,evidence=evidence,confirmation_runs=0,research_runs=0)
    with a.output.open('x',encoding='utf-8') as handle:json.dump(result,handle,ensure_ascii=False,indent=2);handle.write('\n')
    print(json.dumps(dict(status=result['status'],counts=counts,assertion_counts=result['assertion_counts'],model_calls=0)))
    return 0 if result['status']=='PASS_SAVED_RECONCILIATION' else 1


if __name__=='__main__':raise SystemExit(main())
