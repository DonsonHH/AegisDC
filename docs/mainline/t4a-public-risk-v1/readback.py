"""Identity and information-flow readback from saved original data; does not run a policy."""
from collections import Counter
import gzip
import json
import os
from bridge import *


def main():
    spec,pin=frozen();bundle=check_bundle(spec);w=read(ACTIVITY/'isolation/result.json')
    require(bundle==w['bundle'] and w['facility_starts']==0,'pre-native noninterference witness')
    manifest=inputs();seen=set();workers=set();units=[];jobs={};totals=Counter();checkpoints=Counter()
    paid_examples={}
    for group,pairs in [('pilot',spec['pilot']),*spec['batches'].items()]:
        base=ACTIVITY/'batches'/group;start=read(base/'start.json');terminal=read(base/'terminal.json')
        require(start['freeze']==sha(PK/'freeze.json') and start['positions']==pairs and start['job']==terminal['job']
                and terminal['entries']==[[k,role,0] for k,role in pairs],'group membership '+group)
        jobs[group]=dict(job=start['job'],positions=len(pairs),terminal_sha256=sha(base/'terminal.json'))
        for k,role in pairs:
            d=ACTIVITY/'positions'/(k+'-'+role);e=read(d/'entry.json');en=read(d/'native-entry.json');s=read(d/'result.json')
            require(s['entry']==e and s['public_calls']==61 and sha(d/'original.jsonl.gz')==s['raw_sha256'] and
                e['input_sha256']==manifest['files'][k] and e['method_release']==start['freeze'] and e['public_bundle']==bundle and
                e['job']==start['job'] and s['worker_pid']==en['worker_pid'] and s['worker_pid']!=e['pid'],'native identity')
            tag=(start['job'],e['pid']);worker=(start['job'],s['worker_pid'])
            require(tag not in seen and worker not in workers,'process reuse');seen.add(tag);workers.add(worker)
            with gzip.open(d/'original.jsonl.gz','rt') as f:
                first=json.loads(next(f));meta=first['metadata']
            original=read(PREVIOUS/'development-inputs'/(k+'.json'))
            require(meta['source_config']==original['native']['scenario'] and meta['inputs']['dispatch_program']==original['native']['dispatch_program']
                    and meta['t3_received_attachment_sha256']==digest(original['attachment']) and not meta['t3_unpurchased_evaluator_only'],
                    'same T3 plant and zero oracle feedback')
            hist=meta['policy_public_decisions']
            require([q['view']['time'] for q in hist]==list(range(0,3601,60)),'hour clock')
            transcript=[[q['view']['time'],digest(q['view']),digest(q['decision'])] for q in hist]
            require(s['IPC_sha256']==digest(transcript) and en['static_public']==digest(meta['inputs']['dispatch_program']['public']),
                    'actual worker replies/prefix')
            for step in hist:
                v=step['view'];out=step['decision'];t=v['time'];audit=out['rationale']
                require(set(v)=={'time','records','work','paid','writes','fixed','issued'} and audit['version']==role,'online schema')
                require(all(r['arrived']<=t for c in ('records','paid','fixed','writes') for r in v[c]),'arrival')
                if role.startswith('V'):
                    post=audit['posterior'];mass=sum(post['causes'].values())
                    require(abs(mass-(0 if post['model_conflict'] else 1))<1e-8,'posterior normalization')
                    for branch in audit['continuation_table']:
                        table=branch['table']
                        require(abs(sum(a['probability'] for a in table.values())-1)<1e-8,'report probabilities')
                        for j,z in enumerate(branch['vector']):
                            require(abs(z-sum(leaf['probability']*leaf['cost'][j] for leaf in table.values()))<1e-7,'one table per observation')
                q=out.get('request')
                if role in ('V1','V2','V3') and q and q['phase']=='I' and role not in paid_examples:
                    choices=audit['continuation_table']
                    winner=next(b for b in choices if b['first']==[q['subject'],'I'])
                    receipt=next((z for z in s['paid'] if z['task']==q['task']),None)
                    next_step=next((z for z in hist if receipt and z['view']['time']>=receipt['arrived']),None)
                    paid_examples[role]=dict(key=k,time=t,subject=q['subject'],task=q['task'],first=winner,
                        alternatives=[[b['first'],b['vector']] for b in choices],
                        actual_receipt=receipt,first_view_after_arrival=None if not next_step else
                        dict(at=next_step['view']['time'],chosen=next_step['decision']['rationale']['chosen']),
                        raw=s['raw_sha256'])
                if q and q['phase']=='R':
                    require(any(r['execution']==q['execution'] and r['epoch']==q['parent_epoch'] and r['outcome']=='APPLIED' for r in v['writes']),
                            'own review parent')
            require(set(s['checkpoints'])=={'900','1800','2700','3600'} and s['person']>=0 and s['tool']>=0 and s['fee']==len(s['requests'])
                    and all(abs(left-right)<1e-7 for left,right in zip((s['L'],s['U']),s['balance'],strict=True)),
                    'outcomes and fees')
            units.append(dict(key=k,role=role,job=e['job'],plant=e['pid'],worker=s['worker_pid'],input=e['input_sha256'],
                raw=s['raw_sha256'],score=sha(d/'result.json'),transcript=s['IPC_sha256'],release=e['method_release']))
            totals[role]+=1;checkpoints[role]+=len(hist)
    require(set(totals)==set(ARMS) and all(v==72 for v in totals.values()),'complete denominators')
    result=dict(roles=dict(totals),public_clock_calls=dict(checkpoints),jobs=jobs,units=units,first_actual_initial_read=paid_examples,
                isolated_workers=len(workers),native_processes=len(seen),holdout_calls=0,job=os.environ['SLURM_JOB_ID'])
    write(ACTIVITY/'attempt-inventory.json',result)
    print('reconciled native originals',dict(totals),len(workers),'isolated children',flush=True)


if __name__=='__main__':main()
