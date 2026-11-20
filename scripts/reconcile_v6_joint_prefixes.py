"""F7. Read the unchanged F0 temporal oracle and saved F6 traces. No selectors or facility imports."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path


def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def read(p):
    if p.suffix=='.gz':
        with gzip.open(p,'rt',encoding='utf8') as f:return json.load(f)
    return json.loads(p.read_bytes())


def save(path,x):
    with path.open('x',encoding='utf8') as f:json.dump(x,f,ensure_ascii=False,separators=(',',':'))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('activity',type=Path);parser.add_argument('pins',type=Path)
    parser.add_argument('pin_sha');args=parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or int(os.environ.get('SLURM_CPUS_PER_TASK',0))!=1:raise PermissionError('Slurm F7 only')
    if sha(args.pins)!=args.pin_sha:raise ValueError('F7 pinned recipe identity')
    pins=read(args.pins);root=args.activity.resolve();out=root/'F7'
    if str(root)!=pins['activity'] or pins['source_sha256']!=sha(Path(__file__)) or pins['purpose']!='SAVED_PREFIX_RECONCILIATION_ONLY':
        raise ValueError('Read-only source or activity identity mismatch')
    with (out/'started.lock').open('x') as f:f.write(os.environ['SLURM_JOB_ID'])
    frozen=root/'F0/frozen/oracle.json'
    if sha(frozen)!=pins['F0_oracle_sha256'] or sha(root/'F6/result.json')!=pins['F6_result_sha256']:
        raise ValueError('Frozen oracle / saved attempt binding')
    oracle=read(frozen);ledger={r['key']:r for r in read(root/'F6/result.json')['rows']}
    checks=[];scopes={};decision_count=0;plan_count=0
    def check(unit,t,name,actual,expected):
        checks.append(dict(unit=unit,time=t,check=name,actual=actual,expected=expected,ok=actual==expected))
    for key,times in oracle['temporal'].items():
        path=root/'F6'/key/'run.json.gz'
        if sha(path)!=ledger[key]['actual_sha256']:raise ValueError('Saved native bytes '+key)
        run=read(path);cfg=run['inputs']['dispatch_program']['policy_program']
        decisions={d['view']['time']:d for d in run['policy_public_decisions']};entries=[]
        for (t,worlds,confirmed,pending,owed,_,_),(_,expected_debit,expected_reserve) in zip(times,oracle['temporal_remaining'][key]):
            decision_count+=1
            v=decisions[t]['view'];d=decisions[t]['decision'];prefix=d['prefix']
            real={r['task']:r for r in v['issued']}
            cost=[sum(cfg['deadline']-r['release'] for r in real.values())]*2+[len(real)*cfg['fee']]
            check(key,t,'same irreversible root debit',cost,[expected_debit,expected_debit,len(real)])
            check(key,t,'all real tasks occur once',prefix['issued'],list(real))
            check(key,t,'original worlds and received-only writes',[sorted(prefix['support']),prefix['confirmed'],prefix['pending']],
                  [sorted(worlds),sorted(confirmed),sorted(pending)])
            check(key,t,'W retains previously owed reviews and conditional resources',
                  [prefix['obligations'],prefix['reserved_review']],[sorted(owed),expected_reserve])
            # Reconstruct actual processed public receipts, separately from predicted steps.
            for task in confirmed:
                h=[r for r in v['work'] if r['task']==task and r['status']=='completed']
                w=[r for r in v['writes'] if r['task']==task and r['outcome']=='APPLIED']
                check(key,t,'two arrived success identities '+task,bool(h and w and h[0]['at']==w[0]['at']
                    and max(h[0]['arrived'],w[0]['arrived'])<=t),True)
            for task in pending:
                check(key,t,'pending has no arrived APPLIED '+task,any(r['task']==task and r['outcome']=='APPLIED' for r in v['writes']),False)
            for task,continuations in prefix['contingent'].items():
                check(key,t,'in-flight probe retains its previously issued contingent reservation '+task,continuations==real[task].get('contingent',[]),True)
            alts=d['alternatives'];check(key,t,'one WAIT plan',sum(not a['sequence'] for a in alts),1)
            n=0
            for alternative in alts:
                for pathno,proposal in enumerate([alternative]+alternative.get('branches',[])):
                    n+=1;steps=proposal['steps'];names=[s['task'] for s in steps]
                    extra=sum(cfg['deadline']-s['release'] for s in steps)
                    amount=[cost[0]+extra,cost[1]+extra,cost[2]+len(steps)*cfg['fee']]
                    label=f"{alternative['sequence']} branch {pathno}"
                    check(key,t,'same paid base and each proposed issue charged once '+label,proposal['required'],amount)
                    check(key,t,'no already issued or duplicated prospective task '+label,
                          bool(set(names)&set(real)) or len(names)!=len(set(names)),False)
                    if proposal.get('admitted',True):
                        check(key,t,'every owed review included on complete branch '+label,sorted(set(owed)-set(names)),[])
                        check(key,t,'conditional full-branch budget '+label,all(x<=y for x,y in zip(amount,cfg['caps'])),True)
                    for s in steps:
                        if not s['task'].endswith('/R'):continue
                        parent=s['task'][:-1]+'A'
                        check(key,t,'own review has issued or scheduled parent '+label+' '+parent,parent in real or parent in names,True)
            req=d['request']
            if req and req['task'].endswith('/R'):
                parent=req['task'][:-1]+'A'
                check(key,t,'real review uses actual arrived parent only',parent in confirmed,True)
            entries.append(dict(time=t,alternative_and_branch_count=n,paid=cost,review_reserved=expected_reserve))
            plan_count+=n
        scopes[key]=entries
    failures=[r for r in checks if not r['ok']]
    save(out/'checks.json',dict(checks=checks,failures=failures,decision_rows=decision_count,plan_and_branch_rows=plan_count,scope=scopes))
    save(out/'result.json',dict(group='F7',job=os.environ['SLURM_JOB_ID'],scope='saved-only original-world and common-prefix audit; previous native classifications retained',
        status='PASS' if not failures else 'FINDINGS_RETAINED',assertions=len(checks),failures=failures,decision_rows=decision_count,
        plan_and_branch_rows=plan_count,checks_sha256=sha(out/'checks.json'),scope_by_unit=scopes,
        counts=dict(facility=0,direct=0,internal=0,component=0)))
    return int(bool(failures))


if __name__=='__main__':raise SystemExit(main())
