"""Two fixed Slurm schedules. Compare terminal public-interface returns to preimplementation literals."""
import argparse
from copy import deepcopy
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

ROOT=Path(__file__).resolve().parents[1]
PACKAGE='docs/mainline/v6-joint-terminal-v1'
OLD='docs/mainline/v6-joint-engineering-v1'
FIXTURE_SHA='29c4b8b95313664f6246abbda0b06eb6ed5d91c603ca8af9f5a1661386a9a970'


def hash_file(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def read(p):
    if p.suffix=='.gz':
        with gzip.open(p,'rt',encoding='utf8') as f:return json.load(f)
    return json.loads(p.read_bytes())


def canonical(v):
    return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def save(p,v):
    with p.open('x',encoding='utf8',newline='\n') as f:
        json.dump(v,f,ensure_ascii=False,allow_nan=False,separators=(',',':'));f.write('\n')


def policy_projection(actual,sequence):
    first=actual['request'];root=actual['prefix']
    result=dict(first=actual['choice'],task=first['task'] if first else None,obligations=root['obligations'],reserve=root['reserved_review'],
                debit=root['debit'],confirmed=root['confirmed'],pending=root['pending'])
    if first:result.update(release=first['release'],planned_end=first['planned_end'])
    path=next((p for p in actual['alternatives'] if sequence and p['sequence']==sequence),None)
    if path:result.update(C_admitted=path['admitted'],C_required=path['required'])
    return result


def prefix_projection(prefix,cfg,task):
    typ=cfg['types'][task[0]]
    return dict(locked=sorted(prefix['locked']),debit=prefix['debit'],pending=sorted(prefix['pending']),
        confirmed=sorted(prefix['confirmed']),obligations=sorted(prefix['reviews']),
        reserve=sum(cfg['deadline']-r[1] for r in prefix['reviews'].values()),
        pose=[prefix['pose'][typ[k]] for k in ('worker','tool')])


def run_one(fixture,case,old,old_oracles):
    from aegis_dc.joint_evidence import own_ack,action_feedback,at_time,instances,certificate,observation
    from aegis_dc.joint_forecast import support
    from aegis_dc.joint_resources import public_prefix,schedule
    from aegis_dc.joint_policy import choose
    entry=case['entry'];args=case.get('args',{})
    if 'source_key' in case:
        key=case['source_key'];old_input=old[key]
        if canonical(old_input)!=fixture['legacy']['sources'][key] or key not in old_oracles:raise ValueError('Historical source mismatch')
        cfg=old_input['program'];v=old_input['view']
        if 'time' in args:v=at_time(v,args['time'])
    else:
        cfg=fixture['programs'][case['program']];v=case['view']
    cfg=deepcopy(cfg);v=deepcopy(v);task=args.get('task','N/n0/A')
    if entry in ('choose','legacy_choose'):
        actual=choose(cfg,v)
        return policy_projection(actual,args.get('inspect_sequence')),actual
    if entry=='own_ack':
        a=own_ack(cfg,v,task);return {'value':[a[k] for k in ('status','at','arrived','location')] if a else None},a
    if entry=='action_feedback':
        a=action_feedback(cfg,v,task);return {'value':[a[k] for k in ('outcome','at','arrived')] if a else None},a
    if entry in ('public_prefix','legacy_prefix'):
        p=public_prefix(cfg,v);answer=prefix_projection(p,cfg,task);return answer,p
    if entry=='legacy_observation':
        a=observation(cfg,v,task);return {'value':a[0]},a
    if entry=='legacy_route':
        a=schedule(cfg,v,[task]);row=a['steps'][0]
        return dict(emit_now=row['at']==v['time'],finish=row['planned_end'],ack=row['planned_ack']),a
    if entry=='legacy_cert':
        key=args['instance'];a=certificate(cfg,v,key,instances(cfg,v)[key]);return {'value':a},a
    if entry=='legacy_support':
        a=support(cfg,v,public_prefix(cfg,v));return {'value':sorted(w['origin'] for w in a)},a
    if entry=='adapter':
        from aegis_dc.joint_messages import native_message
        a=native_message(cfg,v['issued'],args['raw'],args['channel'],v['time'])
        return {'value':a},a
    if entry in ('statistics','sealed_statistics'):
        from audit_v6_joint import work_receipt_statistics
        if entry=='statistics':
            a=work_receipt_statistics(args['jobs'],args['work'],cfg,args['time']);return a,a
        archive=fixture['original_archive'];folder=Path(archive['path'])
        for f,field in [('run.json.gz','run_sha256'),('checks.json','checks_sha256'),('terminal.json','terminal_sha256')]:
            if hash_file(folder/f)!=archive[field]:raise ValueError('Original S09 bytes differ: '+f)
        raw=read(folder/'run.json.gz');original=read(folder/'checks.json');terminal=read(folder/'terminal.json')
        source=old['S09']
        if canonical(source)!=fixture['legacy']['sources']['S09'] or canonical(raw['source_config'])!=canonical(source['scenario']) or canonical(raw['inputs']['dispatch_program'])!=canonical(source['dispatch_program']):
            raise ValueError('Original S09 source binding differs')
        a=work_receipt_statistics(raw['work_records'],raw['workforce_public_feedback'],source['dispatch_program']['policy_program'],raw['summary']['duration_s'])
        from math import fsum
        balances=raw['balances'];work=raw['work_records'];cost=[fsum(r[k] for r in balances for k in
            ('worker_travel_person_s','worker_work_person_s','worker_wait_person_s')),fsum(r['tool_occupation_tool_s'] for r in balances),len(work)]
        facts=dict(real_work=cost,actual_requests=len(work),execution_outcomes=[r['outcome'] for r in raw['intervention_public_feedback']],
            physical_writes=sum(r['outcome']=='APPLIED' for r in raw['intervention_private_audit']['events']),
            original_failed_assertion=terminal['status']=='FAILED_ASSERTION' and not original['passed'] and
            any(r['actual']==1.0 and r['expected']==.5 and not r['ok'] for r in original['failures']))
        return {**a,**facts},dict(statistics=a,actual=facts,retained_failure=original['failures'],
            original_bytes={f:hash_file(folder/f) for f in ('run.json.gz','checks.json','terminal.json')},
            raw_work_messages=raw['workforce_public_feedback'],separate_execution_messages=raw['intervention_public_feedback'])
    raise ValueError('Unknown frozen unit')


def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=('T0','T1'));p.add_argument('release_sha');args=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or os.environ.get('SLURM_CPUS_PER_TASK')!='1':raise PermissionError('One CPU on Slurm required')
    pinfile=ROOT/'release.json'
    if hash_file(pinfile)!=args.release_sha:raise ValueError('Export identity')
    pin=read(pinfile)
    if pin['phase']!=args.phase or pin['purpose']!='PUBLIC_TERMINAL_ENGINEERING_ONLY':raise PermissionError('Purpose/phase mismatch')
    for path,h in pin['files'].items():
        if hash_file(ROOT/path)!=h:raise ValueError('Pinned bytes differ: '+path)
    path=ROOT/PACKAGE/'fixtures.json'
    if hash_file(path)!=FIXTURE_SHA:raise ValueError('Frozen fixture identity')
    f=read(path);budget=f['budget'];oldpack=ROOT/OLD
    for name,h in f['legacy']['files'].items():
        if hash_file(oldpack/name)!=h:raise ValueError('Old input/independent oracle identity')
    old=read(oldpack/'inputs.json.gz');old_oracles=read(oldpack/'oracle.json')['units']
    out=Path(pin['activity'])/args.phase
    red=args.phase=='T0';order=f['red' if red else 'green']
    if not red:
        previous=read(out.parent/'T0/result.json')
        if previous['status']!='RED_REPRODUCED' or previous['counts']['combined']!=len(f['red']):raise ValueError('Missing red phase')
    if len(set(order))!=len(order) or len(order)!=budget['red' if red else 'green']['combined'] or len(f['red'])+len(f['green'])!=budget['frozen_total'] or budget['frozen_total']>128:
        raise ValueError('Schedule or combined cap mismatch')
    def forbid(name,arguments):
        if name=='import' and arguments and arguments[0] in ('aegis_dc.plant','aegis_dc.native_compare_run'):
            raise PermissionError('No facility construction/execution in this package')
    sys.addaudithook(forbid)
    with (out/'started.lock').open('x') as fp:fp.write(os.environ['SLURM_JOB_ID'])
    counts=dict(policy=0,component=0,combined=0,facility=0,thermal=0,research=0);rows=[];failed=[]
    for key in order:
        case=f['units'][key];folder=out/key;folder.mkdir()
        kind='policy' if case['entry'] in ('choose','legacy_choose') else 'component'
        save(folder/'input.json',case);want=f['red_literal'][key] if red else case['expected']
        counts[kind]+=1;counts['combined']+=1
        with (out/'calls.jsonl').open('a',encoding='utf8') as fp:fp.write(json.dumps([key,kind,counts['combined']])+'\n')
        try:
            actual,raw=run_one(f,case,old,old_oracles)
            save(folder/'raw.json',raw)
            diffs=[dict(field=k,actual=actual.get(k),expected=value) for k,value in want.items() if k not in actual or actual[k]!=value]
            if red and all(k in actual and actual[k]==v for k,v in case['expected'].items()):
                diffs.append(dict(field='old behavior unexpectedly met revised requirement'))
            row=dict(unit=key,kind=kind,status='FAIL' if diffs else 'PASS',assertions=len(want)+int(red),actual=actual,expected=want,differences=diffs,
                     raw_sha256=hash_file(folder/'raw.json'),input_sha256=canonical(case))
        except Exception as exc:
            (folder/'error.txt').write_text(traceback.format_exc(),encoding='utf8');row=dict(unit=key,kind=kind,status='EXCEPTION',error=repr(exc),input_sha256=canonical(case))
        save(folder/'comparison.json',row);rows.append(row)
        if row['status']!='PASS':
            failed.append(key)
            # Cases are independent snapshots. A missing/corrupt frozen input blocks the remaining schedule.
            if row['status']=='EXCEPTION' and any(x in row['error'] for x in ('bytes differ','binding differs','source mismatch')):break
    status='FAILED' if failed or len(rows)!=len(order) else 'RED_REPRODUCED' if red else 'FINITE_SCOPE_PASS'
    save(out/'result.json',dict(phase=args.phase,job=os.environ['SLURM_JOB_ID'],status=status,
        source_revision=pin['revision'],release_sha256=args.release_sha,fixtures_sha256=FIXTURE_SHA,counts=counts,
        rows=rows,failed=failed,unexecuted=order[len(rows):],actual_assertions=sum(r.get('assertions',0) for r in rows)))
    print(status,counts,failed,flush=True);return int(status=='FAILED')


if __name__=='__main__':raise SystemExit(main())
