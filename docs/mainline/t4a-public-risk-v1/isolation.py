"""Noninterference witness on two actual different saved physical worlds. No facility imports or calls."""
from copy import deepcopy
import gzip
import os
from pathlib import Path
from bridge import *


def history(k):
    x=read(PREVIOUS/'development-inputs'/(k+'.json'))
    d=PREVIOUS/'positions'/(k+'-P')
    result=read(d/'result.json');raw=d/'original.jsonl.gz'
    require(sha(raw)==result['raw_sha256'] and sha(PREVIOUS/'development-inputs'/(k+'.json'))==inputs()['files'][k],'pinned history')
    with gzip.open(raw,'rt') as fp:meta=json.loads(next(fp))['metadata']
    require(meta['source_config']==x['native']['scenario'] and meta['t3_received_attachment_sha256']==digest(x['attachment']),'distinct true input')
    return x['native']['dispatch_program']['public'],[r['view'] for r in meta['policy_public_decisions']],digest(x['attachment']),sha(raw)


def reading(view,released):
    v=deepcopy(view);sid='LB';name='LB::I'
    v['issued']=[dict(task=name,subject=sid,phase='I',at=0,planned_end=35,worker='worker_electrical',tool='tool_electrical_meter',
                      instance=sid,parent=None,execution=None,parent_epoch=None,patrol_slot=None)]
    v['work']=[dict(task_id=name,source_id='workforce-execution-report',observed_at_s=35,arrived_at_s=50,
                    status='completed',reason=None,location_id='loc_electrical',origin_id='workforce:'+name,
                    coverage='THIS_ISSUED_TASK_ONLY',basis='synthetic public witness')]
    v['paid']=[dict(task=name,subject=sid,phase='I',source='onsite/LB',origin=name+'@35',worker='worker_electrical',tool='tool_electrical_meter',
                    issued=0,sampled=35,arrived=50,until=2135,parent=None,execution=None,parent_epoch=None,physical_epoch=0,
                    fields={'contact':0,'upstream':1,'released':released})]
    return v


def reject_test(out,pub,view,field):
    proc=PublicProcess('V3',out/(field+'.stderr'))
    try:
        proc.message({'public':pub})
        if field=='private':view=dict(view,private_truth={'source':'synthetic guard'})
        else:
            view=deepcopy(view);view['records'][0]['arrived']=view['time']+60
        try:proc.message({'view':view})
        except RuntimeError:return True
        return False
    finally:proc.close(failed=True)


def main():
    spec,_=frozen();out=ACTIVITY/'isolation';out.mkdir()
    bundle=check_bundle(spec,create=True)
    a,b=(history(k) for k in ('5-04','5-10'))
    require(a[:2]==b[:2] and a[2]!=b[2] and len(a[1])==61,'paired public history')
    duty_dir=PREVIOUS/'positions/C-L-read-fix'
    with gzip.open(duty_dir/'original.jsonl.gz','rt') as fp:duty_native=json.loads(next(fp))['metadata']
    duty_pub=duty_native['inputs']['dispatch_program']['public']
    duty=next(r['view'] for r in duty_native['policy_public_decisions'] if r['decision']['request'] and r['decision']['request']['phase']=='R')
    result={};all_events={}
    for version in ('V1','V2','V3'):
        left=PublicProcess(version,out/(version+'-a.stderr'));right=PublicProcess(version,out/(version+'-b.stderr'))
        options=0;sensitivities=0;nonwait=0
        try:
            for v1,v2 in zip(a[1],b[1],strict=True):
                one=left.choose(a[0],v1,version,{})
                two=right.choose(b[0],v2,version,{})
                require(one==two,'private-twin divergence at '+str(v1['time']))
                rr=one['rationale'];tab=rr['continuation_table'];options+=len(tab);nonwait+=int(one['request'] is not None)
                for candidate in tab:
                    loss,work,fees,value=candidate['vector']
                    require(abs(value-loss-rr['price']*(work+30*fees))<1e-6,'price identity')
                    if candidate['first'] and candidate['first'][1]=='I':
                        leaf=candidate['table']
                        require('UNKNOWN' in leaf and abs(sum(x['probability'] for x in leaf.values())-1)<1e-8,'proper probability table')
                        sensitivities+=int(len({tuple(v['continue_with']) for v in leaf.values()})>1)
            require(left.events==right.events and options>0,'nontrivial public comparison')
            all_events[version]=list(left.events)
            frame=deepcopy(a[1][3])
            prior=next(r for r in frame['records'] if r['kind']=='prior' and r['copied_from'] is None)
            before=left.choose(a[0],frame,version,{})
            frame['records'].append(dict(prior,source='registered-relay',copied_from=prior['origin']))
            require(before==left.choose(a[0],frame,version,{}),'source copied twice')
            r1=left.choose(a[0],reading(a[1][3],True),version,{})
            r2=left.choose(a[0],reading(a[1][3],False),version,{})
            require(r1['rationale']['posterior']['causes']!=r2['rationale']['posterior']['causes'],'paid signal has no consequence for belief')
            aborted=reading(a[1][3],False);aborted['paid']=[];aborted['work'][0].update(status='aborted',location_id=None)
            require(left.choose(a[0],aborted,version,{})['rationale']['reason']!='AWAIT_OWN_PAID_RESULT','failure is terminal')
            result[version]=dict(public_ticks=61,same_full_decisions=61,nonwait=nonwait,priced_roots=options,
                different_continuations=sensitivities,extra_checks=['same-source duplicate','lawful contrasting paid readings','terminal refusal'],
                detail_sha256=digest(all_events[version]),worker_pids=[left.child.pid,right.child.pid])
        finally:left.close();right.close()
        obliged=PublicProcess(version,out/(version+'-mandatory.stderr'))
        try:
            actual=obliged.choose(duty_pub,duty,version,{})
            require(actual['request'] and actual['request']['phase']=='R' and actual['request']['execution'],'real positive mandatory witness')
            result[version]['independent_positive_due']=actual['request']['task']
        finally:obliged.close()
    for role in ('PA','B'):
        proc=PublicProcess(role,out/(role+'.stderr'))
        try:
            frame=deepcopy(a[1][2]);frame['records'].append(dict(kind='alarm',subject='power-board',source='alarm-desk',
                sampled=70,arrived=100,until=730,origin='synthetic-alarm',copied_from=None,value='ALARM'))
            resp=proc.choose(a[0],frame,role,{})
            require(resp['request']['task']=='LC::A','public response priority')
        finally:proc.close()
    require(reject_test(out,a[0],a[1][0],'private') and reject_test(out,a[0],a[1][0],'future'),'invalid input accepted')
    write(out/'per-tick-digests.json',all_events)
    write(out/'result.json',dict(status='PUBLIC_BOUNDARY_WITNESSED',job=os.environ['SLURM_JOB_ID'],freeze=sha(PK/'freeze.json'),
        bundle=bundle,originals=[a[3],b[3]],private_attachments=[a[2],b[2]],same_public_program=digest(a[0]),
        versions=result,guards=['private field rejected','future arrival rejected','PA alarm wins over patrol','B direct'],
        facility_starts=0,scientific_baseline_runs=0,tests_use_development_only=True))
    print(result,flush=True)


if __name__=='__main__':main()
