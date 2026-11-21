"""Read saved engineering originals and frozen literals. Never calls a plant, dispatcher or scoring routine."""
import gzip
import json
import os
import sys
from pathlib import Path
from common import BIZ,CLOCK,REMOTE,load,sha,slurm,write,insist,digest


def read_gate(gate,manifest_hash):
    ip=REMOTE/'engineering-inputs';m=load(ip/'manifest.json')
    insist(sha(ip/'manifest.json')==manifest_hash,'A/C freeze')
    terminal=load(REMOTE/(gate+'-terminal.json'));out=[]
    for key in m['definitions'][gate]:
        parent=REMOTE/'positions'/key;expected=load(ip/(key+'.json'));case=expected['input']
        origin=load(parent/'entry.json') if (parent/'entry.json').is_file() else None
        result=load(parent/'result.json') if (parent/'result.json').is_file() else None
        row=dict(key=key,job=origin['job'] if origin else None,issued=bool(origin),returned=bool(result),
                 input=m['files'][key],expected=expected['expect'],plan=expected['plan'])
        if result:
            raw=parent/'original.jsonl.gz'
            insist(origin['manifest']==result['manifest']==manifest_hash and origin['input']==result['input_sha256']==m['files'][key]
                   and origin['pid']==result['pid'] and sha(raw)==result['raw_sha256'],'engineering binding '+key)
            with gzip.open(raw,'rt') as fp:
                first=json.loads(next(fp));meta=first['metadata']
                insist(meta['source_config']==case['native']['scenario'] and meta['inputs']['dispatch_program']==case['native']['dispatch_program']
                    and meta['t3_received_attachment_sha256']==digest(case['attachment']),'received scenario/attachment')
                insist([q['view']['time'] for q in meta['policy_public_decisions']]==list(CLOCK),'public sequence')
                # Ground the published fixed rows against actual native samples and incident physical transitions.
                fixed={r['sampled']:{} for r in result['fixed']}
                for r in result['fixed']:fixed[r['sampled']][r['field']]=r
                subs={q['id']:q for q in case['native']['dispatch_program']['public']['subjects']}
                sides=first['terminal']['events'] if first['terminal'] else []
                count=0
                for line in fp:
                    pair=json.loads(line);sample=pair['sample'];t=sample['time_s']
                    if t not in fixed:continue
                    dom=sample['domains'];it=dom['it_service'];physical={k:v for k,v in fixed[t].items()}
                    for field,z in physical.items():
                        if field=='service':v=it['delivered']>=1;source='service'
                        else:
                            source=subs[field]['key']
                            if source=='C':v=.099<=dom['facility_cooling']['lake_pump']['volume_flow_m3_s']<=.101
                            elif source=='N':v=it['capacities']['network']>=1
                            else:
                                state=[s for s in sides if s['t']<=t][-1]
                                if source=='LC':v=state['source']!='NONE'
                                elif source=='LB':v=state['B']
                                elif source=='LG':v=state['ready']
                                elif source=='NR':v=not state['tripped']
                                elif source=='NP':v=state['controller_on'] and state['pump_running'] and not state['pump_latched']
                                elif source=='NC':v=state['backup_commissioned']
                                else:raise ValueError(source)
                        insist(v==z['ok'] and z['origin']==f'meter/{source}@{t:g}' and z['arrived']==t+15 and z['until']==t+720,'fixed source '+key+field)
                        count+=1
            row.update(passed=result['passed'],checks=result['checks'],work=result['work'],paid=result['paid'],writes=result['writes'],
                 checkpoints=result['checkpoints'],first=result['first'],L=result['L'],U=result['U'],first_loss=result['first_loss'],
                 fixed_checked=count,physical_state=result['physical_checkpoints'],attachment=result['attachment'],raw_sha256=result['raw_sha256'],
                 score_sha256=sha(parent/'result.json'))
        out.append(row)
    return dict(declared=len(out),passed=terminal['passed'] and all(r.get('passed') for r in out),job=terminal['job'],rows=out)


if __name__=='__main__':
    slurm();gates=sys.argv[1].split(',');mh=sys.argv[2]
    r={k:read_gate(k,mh) for k in gates}
    name='engineering-'+'-'.join(gates)+'-readback.json'
    write(REMOTE/name,r)
    print(name,sha(REMOTE/name),{k:v['passed'] for k,v in r.items()},flush=True)
