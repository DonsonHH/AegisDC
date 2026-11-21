"""Validate archived public channels, actual arrivals, writes and parent verification; never call a policy."""
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path

ROOT=Path('/share/home/renly/renly-patrol-rsi/mainline/T2-minute-facility-20261121-v1')
PUBLIC_CLOCK=list(range(0,3601,60))


def load(path):return json.loads(path.read_bytes())


def require(ok,key):
    if not ok:raise ValueError(key)


def short_hash(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def main():
    require(os.environ.get('SLURM_JOB_ID'),'Slurm required')
    with gzip.open(ROOT/'study-results.json.gz','rt') as fp:res=json.load(fp)
    affected=set(map(tuple,load(ROOT/'observation-scope-audit.json')['affected']))
    check_count=Counter();route_counts=Counter();limits={};ambiguity=[];species=Counter()
    for row in res['rows']:
        key=row['key'];item=load(ROOT/'study-inputs'/(key+'.json'))
        native=item['native'];public=item['public'];cfg=native['dispatch_program']['policy_program']
        for role in ('P','PERIODIC','ALARM','ORACLE'):
            pos=ROOT/'positions'/(key+'-'+role)
            if (key,role)==('4-01','ORACLE'):pos/='attempt-02'
            elif (key,role) in affected:pos/='entitlement-attempt-02'
            x=row[role];log=load(pos/'result.json')
            with gzip.open(pos/'original.jsonl.gz','rt') as fp:ret=json.loads(next(fp))['metadata']
            require(ret['source_config']==native['scenario'] and
                    ret['inputs']['dispatch_program']==native['dispatch_program'] and
                    ret['inputs']['boundary_events']==sorted(native['boundary_events'],key=lambda z:z['time_s']) and
                    ret['inputs']['maximum_step_s']==.25 and ret['inputs']['duration_s']==3600,'input '+key+role)
            actual={v['task']:v['fields'] for v in ret['inspection_public_models']['bindings']}
            require(actual==public['read_rights'],'native observation rights '+key+role)
            ds=ret['policy_public_decisions']
            require([v['view']['time'] for v in ds]==PUBLIC_CLOCK,'public clocks')
            for obj in ds:
                t=obj['view']['time']
                for ch in ('orders','work','writes','paid','fixed'):
                    require(all(z['at']<=z['arrived']<=t for z in obj['view'][ch]),'public time')
            measured={a['task'] for a in ret['inspection_public_feedback'] if a['interval'] is not None}
            tokens={(r['target'],r['phase']) for r in ret['inspection_public_feedback'] if r['interval'] is not None}
            require(len(tokens)==len(measured),'single observation per physical target and phase')
            require(measured==set(log['paid_observed']) and len(measured)<=2,'effective observations')
            works={w['id']:w for w in ret['work_records']}
            writes=ret['intervention_private_audit']['events']
            public_writes=ret['intervention_public_feedback'];work_receipts=ret['workforce_public_feedback']
            for q in writes:
                if q['outcome']!='APPLIED':continue
                task=q['task_id'];work=works[task];typ=cfg['types'][task[0]]
                require(work['status']=='completed' and typ['write'][0]<=work['issued_at_s']<=q['applied_at_s']<typ['write'][1],
                        'physical write grant '+key+role)
            for r in works.values():
                if not r['id'].endswith('/R'):continue
                action=r['id'][:-1]+'A'
                require(any(v['task_id']==action and v['status']=='completed' and v['arrived_at_s']<=r['issued_at_s'] for v in work_receipts)
                    and any(v['task_id']==action and v['outcome']=='APPLIED' and v['arrived_at_s']<=r['issued_at_s'] for v in public_writes),
                    'proper receipt before own review '+key+role)
            if role=='ORACLE':
                for t,task in log['oracle']['plan'].items():
                    require(task in works and works[task]['status']=='completed' and works[task]['issued_at_s']==int(t)
                        and any(v['task_id']==task and v['outcome']=='APPLIED' for v in writes)
                        and works[task[:-1]+'R']['status']=='completed','native oracle action and verification '+key)
            if role=='PERIODIC':
                slots=[(t,s) for t,k,s in log['issues'] if s is not None]
                for (release,expected),(at,actual_id) in zip(public['duty_route'],slots):
                    require(actual_id==expected and release<=at<release+900,'paid route cycle '+key)
                route_counts[len(slots)]+=1
            if role=='P':
                require(not works and not measured and not writes,'background path')
                if item['evaluation']['ambiguous_pair']:
                    ambiguity.append({'key':key,'dispatch':short_hash(native['dispatch_program']),
                        'rights':short_hash(public),'physics':short_hash(native['scenario']),'fixed':short_hash(log['original_fixed']),
                        'view':short_hash([q['view'] for q in log['public_history']])})
                for fam, name in [('COOLING_ACCESS','cooling'),('RESERVE_TRANSFER','generator'),('RESERVE_TRANSFER','ups')]:
                    if row['family']==fam:
                        species.update({name+'/'+q[1][name] for q in x['reserve_transitions']})
            require(x['person_s']<=cfg['caps'][0]+1e-7 and x['tool_s']<=cfg['caps'][1]+1e-7 and x['fee']<=cfg['caps'][2],'cap')
            check_count[role]+=1
            limits[role]=max(limits.get(role,0),len(measured))
    require(len(ambiguity)==2 and ambiguity[0]['physics']!=ambiguity[1]['physics'] and
        all(ambiguity[0][k]==ambiguity[1][k] for k in ('dispatch','rights','fixed','view')),'paired ambiguous root')
    out=dict(positions=dict(check_count),scope='Original native metadata plus sealed scores, no model or policy calls',
        route_visits_per_position=dict(sorted(route_counts.items())),max_distinct_paid_observation_products=limits,
        ambiguous_pair=ambiguity,protected_state_exposures_in_P=dict(species),job=os.environ['SLURM_JOB_ID'])
    with (ROOT/'panel-identity.json').open('x') as fp:json.dump(out,fp,indent=2)
    print('original identities checked',dict(check_count), 'route visits',dict(route_counts),flush=True)


if __name__=='__main__':main()
