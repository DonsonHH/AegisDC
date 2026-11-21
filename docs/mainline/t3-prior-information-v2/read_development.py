"""Verify saved native originals (including actual attachment and read projection) and resolve the two pilot entries."""
from collections import Counter
import gzip
import json
import os
import sys
from common import *
import summarize

FAILED=(('4-01','ORACLE'),('6-01','ORACLE'))
original_position=summarize.position


def location(k,role):
    root=REMOTE/'pre-native-import-recovery' if (k,role) in FAILED else REMOTE
    return root/'positions'/(k+'-'+role)


def final_position(k,role,mh,files):
    if (k,role) not in FAILED:return original_position(k,role,mh,files)
    old=REMOTE/'positions'/(k+'-'+role);insist([f.name for f in old.iterdir()]==['entry.json'] and
        load(old/'entry.json')['job']=='134777','pre-native pilot retained')
    d=location(k,role);e=load(d/'entry.json');r=load(d/'result.json')
    insist(r['passed'] and e['input']==r['input_sha256']==files[k] and e['manifest']==r['manifest']==mh
           and (k,role,e['pid'],e['job'])==(r['key'],r['role'],r['pid'],r['job']) and r['clocks']==61,'recovery identity')
    insist(sha(d/'original.jsonl.gz')==r['raw_sha256'],'recovery original')
    r['score_sha256']=sha(d/'result.json');r['pre_native_failure_job']='134777'
    return r


def digest_and_records(mh):
    """Strict clock and original trace checks. No new plant, selector, generator or scoring calls."""
    root=REMOTE/'development-inputs';m=load(root/'manifest.json');manifest=m['files']
    counted=Counter();attempts=[];meters=Counter();prior_aliased=0;covered_actions=Counter()
    planned=set()
    for d in sorted((REMOTE/'batches').iterdir()):
        if d.name in ('A','C'):continue
        begin=load(d/'started.json');end=load(d/'terminal.json')
        insist(begin['manifest']==end['manifest']==mh and begin['job']==end['job'] and [q[:2] for q in end['entries']]==begin['slots'],'group terminal')
        planned.update((begin['job'],k,role,code) for k,role,code in end['entries'])
    recovered=load(REMOTE/'pre-native-import-recovery/terminal.json')
    planned.update((recovered['job'],k,role,code) for (k,role),code in zip(recovered['keys'],recovered['exit']))
    with gzip.open(REMOTE/'development-result.json.gz','rt') as fp:out=json.load(fp)
    for row in out['rows']:
        k=row['key'];x=load(root/(k+'.json'));n=x['native'];pub=n['dispatch_program']['public']
        for role,s in row['arms'].items():
            d=location(k,role);e=load(d/'entry.json');score=load(d/'result.json')
            insist((e['job'],k,role,0) in planned and e['manifest']==mh and
                  e['input']==manifest[k] and s['raw_sha256']==score['raw_sha256'],'scheduled native role')
            raw=d/'original.jsonl.gz'
            with gzip.open(raw,'rt') as f:
                z=json.loads(next(f));meta=z['metadata']
                insist(meta['t3_received_attachment_sha256']==digest(x['attachment']) and
                    z['terminal']==s['attachment'] and meta['source_config']==n['scenario'] and
                    meta['inputs']['dispatch_program']==n['dispatch_program'] and meta['inputs']['boundary_events']==sorted(n['boundary_events'],key=lambda e:e['time_s']),
                    'native custody/attachment')
                hist=meta['policy_public_decisions'];insist([r['view']['time'] for r in hist]==list(CLOCK),'public clock')
                for dec in hist:
                    view=dec['view'];t=view['time']
                    insist(set(view)=={'time','records','work','paid','writes','fixed','issued'} and
                          all(r['arrived']<=t for c in ('records','paid','writes','fixed') for r in view[c]),'no evaluator fields')
                    for rec in view['records']:
                        if rec['copied_from']:
                            matching=[r for r in view['records'] if r['copied_from'] is None and
                                all(r[q]==rec[q] for q in ('origin','subject','kind','sampled','until','value'))]
                            insist(len(matching)==1 and matching[0]['arrived']<=rec['arrived'],'unique common evidence source')
                            exact=rec['copied_from']==matching[0]['origin']
                            legacy=(rec['kind']=='alarm' and rec['subject'] in ('C/c0','N/n0') and
                                rec['copied_from']=='alarm/'+rec['subject'].split('/')[-1] and
                                matching[0]['origin']=='alarm/'+rec['subject'])
                            insist(exact or legacy,'qualified T2 alias or exact ancestor')
                if role=='P':
                    values=meta['t3_unpurchased_evaluator_only'];insist(not meta['inspection_public_feedback'] and not meta['work_records'],'P free observations')
                    remaining={r['sampled'] for r in values}
                    for line in f:
                        if not remaining:break
                        v=json.loads(line)['sample'];t=v['time_s']
                        if t not in remaining:continue
                        remaining.remove(t)
                        for r in [q for q in values if q['sampled']==t]:
                            insist(r['would_arrive']==t+15 and r['start'] in CLOCK and r['usable'] in CLOCK,'paid counterfactual timing')
                            key=r['subject'].split('/')[0];fields=r['fields']
                            if key=='C':insist(fields['q']==v['domains']['facility_cooling']['lake_pump']['volume_flow_m3_s'],'P measured q')
                            if key=='N':insist(fields['e']==v['domains']['it_service']['capacities']['network'],'P measured e')
                            if key=='LC':insist(len(fields['versions'])==2 and len(set(fields['versions']))==1,'shared versions')
                            if key not in ('C','N'):
                                truth=[ev for ev in z['terminal']['events'] if ev['t']<=t][-1]
                                if key=='LB':insist(fields['contact']==truth['contact_B'],'physical isolated point')
                                if key=='LC':insist(fields['versions']==truth['versions'],'actual version read')
                                if key=='LG':insist(fields['ready']==truth['ready'],'actual readiness')
                                if key=='NR':insist(fields['group_kW']==truth['group_demand_kW'],'actual loaded group')
                                if key=='NP':insist(fields['latched']==truth['pump_latched'],'actual latch')
                                if key=='NC':insist(fields['commissioned']==truth['backup_commissioned'],'actual reacceptance')
                    insist(not remaining,'unwitnessed counterfactual sample time')
                else:insist(not meta['t3_unpurchased_evaluator_only'],'no oracle sample in policy')
                for r in meta['inspection_public_feedback']:
                    if r['phase']=='X':meters[role]+=1
                for r in meta['intervention_public_feedback']:
                    if r['outcome']=='APPLIED':covered_actions[r['operation']]+=1
            counted[role]+=1
            attempts.append(dict(key=k,role=role,job=e['job'],pid=e['pid'],entry_sha256=sha(d/'entry.json'),
                raw_sha256=s['raw_sha256'],score_sha256=sha(d/'result.json'),relative=d.relative_to(REMOTE).as_posix()))
    failures=[]
    for k,role in FAILED:
        d=REMOTE/'positions'/(k+'-'+role);e=load(d/'entry.json')
        insist(e['manifest']==mh and e['input']==manifest[k] and (e['job'],k,role,1) in planned,'earlier pre-call failure')
        failures.append(dict(key=k,role=role,job=e['job'],entry_sha256=sha(d/'entry.json'),state='IMPORT_FAILED_BEFORE_NATIVE_CALL'))
    insist(all(counted[r]==72 for r in ROLES) and len({(r['job'],r['pid']) for r in attempts})==288,'independent positions')
    return dict(job=slurm(),purpose='SAVED_ORIGINALS_ONLY',attempts=attempts,pre_native_failures=failures,roles=dict(counted),
                paid_renewals=dict(meters),applied_operations=dict(covered_actions),raw_originals=288,registered_pilot=6)


if __name__=='__main__':
    mh=sys.argv[1];summarize.position=final_position;summarize.main(mh)
    z=digest_and_records(mh);write(REMOTE/'development-readback.json',z)
    print('originals',z['roles'],'pre-native failures',len(z['pre_native_failures']),flush=True)
