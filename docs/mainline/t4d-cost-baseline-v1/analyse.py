"""Read saved v3 and T4d returns. Draw once per scope, retaining each condition across comparisons."""
from collections import Counter
from statistics import mean
from workpackage import *
from analysis_v3 import draws, paired
from prepare import make_case

MEASURES=('L','U','person','tool','fee')
BASE_CONTROLS=('V_COST','V_COST_NOPROBE','B','PA')
SENS_CONTROLS=('B','B_COST','V_COST_NOPROBE')
EPS=1.e-7


def local_case(mode,key,inventory):
    f=case_file(mode,key);old=PREV/'dev-inputs'/(key+'.json')
    item=inventory['items'][mode][key]
    must(filehash(old)==item['prior_sha256'] and filehash(f)==item['sha256'],'individual input identity')
    case=read(f);source=read(old)
    must(case==make_case(source,spec()['settings'][mode]),'frozen generation')
    must(case['evaluation']==source['evaluation'] and case['attachment']==source['attachment'] and case['native']['scenario']==source['native']['scenario']
        and case['native']['boundary_events']==source['native']['boundary_events'],'private background and exogenous events')
    channels=case['native']['dispatch_program']['channel'];previous=source['native']['dispatch_program']['channel']
    must(len(channels)==len(previous),'exogenous record count')
    for new,oldrow in zip(channels,previous,strict=True):
        expected=dict(oldrow,value='OPEN/MAINT-0') if mode=='S0' and oldrow['kind']=='order' else oldrow
        must(new==expected,'only signed public duration may differ')
    return case


def score_return(mode,key,role,case,m):
    from aegis_cost_baseline.rule import operative_view
    folder=ACT/'positions'/mode/(key+'-'+role);raw=folder/'original.jsonl.gz';sc=folder/'score.json';s=read(sc)
    e=read(folder/'entry.json');n=read(folder/'native-entry.json')
    must(e==s['entry'] and n==s['worker'] and [mode,key,role] in spec()['groups'][e['group']]['positions']
         and e['input']==m['items'][mode][key]['sha256'] and e['source']==os.environ['T4D_SOURCE']
         and e['input_manifest']==os.environ['T4D_INPUTS'] and e['input']==filehash(case_file(mode,key)),'complete unit identity')
    must(filehash(raw)==s['raw_sha256'],'original file byte identity')
    with gzip.open(raw,'rt') as fp:meta=json.loads(next(fp))['metadata']
    must(meta['source_config']==case['native']['scenario'] and meta['inputs']['dispatch_program']==case['native']['dispatch_program']
        and meta['v3_received_maintenance']==case['maintenance'] and meta['t3_received_attachment_sha256']==digest(case['attachment'])
        and not meta['t3_unpurchased_evaluator_only'],'actual received physical and information bundle')
    ds=meta['policy_public_decisions'];pr=meta['v3_proposals']
    must(len(pr)==61 and [d['view']['time'] for d in ds]==list(range(0,3601,60)) and all(digest(v['view'])==q['view'] for v,q in zip(ds,pr,strict=True)),'declared time clock')
    must(all(abs(left-right)<EPS for left,right in zip((s['L'],s['U']),s['integral_balances'],strict=True)),'independent integration')
    if role!='ORACLE':
        must(n['bundle']==m['role_bundles'][mode][role] and n['worker_pid']!=e['pid'] and
             digest([[q['at'],q['view'],q['proposal']] for q in pr])==s['proposal_transcript'],'actual policy replies')
    reasons=[]
    if role=='B_COST':
        ipc=[]
        for d,q in zip(ds,pr,strict=True):
            must(q['external_refusal'] is None,'post-selector denial')
            reply={k:v for k,v in d['decision'].items() if k!='certificates'}
            ipc.append([q['at'],digest(operative_view(d['view'])),digest(reply)])
            if reply['request'] and reply['request']['phase']=='A':
                selected=next(z for z in reply['rationale']['considered'] if z['subject']==reply['request']['subject'])
                reasons.append(dict(at=q['at'],subject=selected['subject'],reason=selected['basis'],
                    signals=selected['signals'],route_conflict=reply['rationale']['reason'].startswith('ROUTE_CONFLICT')))
        must(digest(ipc)==s['public_ipc'],'exact screened inputs and worker-only decisions')
    audit=dict(mode=mode,key=key,role=role,job=e['job'],host=e['host'],pid=e['pid'],worker=n['worker_pid'],bundle=n['bundle'],
        input=e['input'],score=filehash(sc),raw=s['raw_sha256'],proposal=s['proposal_transcript'],public_ipc=s['public_ipc'])
    fields={k:s[k] for k in (*MEASURES,'first','checkpoints','closure_changes','requests','refusals','paid','writes','maintenance','oracle')}
    fields['operational_triggers']=reasons
    return fields,audit


def previous_score(row,role,index):
    x=row['arms'][role];u=index[(row['key'],role)];folder=PREV/'positions'/('dev-'+row['key']+'-'+role)/u['attempt']
    source=folder/'score.json'
    must(filehash(source)==u['score'] and x['score_sha256']==u['score'] and read(source)['raw']==u['raw'],'original v3 role')
    if role=='P':must(not x['requests'] and not x['maintenance'] and not x['writes'],'P invariant across action-only settings')
    return {k:x[k] for k in (*MEASURES,'first','checkpoints','requests','paid','writes','maintenance')}


def role_stats(rows,role):
    arms=[r['arms'][role] for r in rows]
    return dict(**{k:mean(a[k] for a in arms) for k in MEASURES},
        instances=sum(len(a['checkpoints']['3600']) for a in arms),
        closures={kind:dict(ever=sum(kind in types for a in arms for types in a['first'].values()),
           current=[sum(z==kind for a in arms for z in a['checkpoints'][t].values()) for t in ('900','1800','2700','3600')]) for kind in ('NA','PV')},
        initial_reads=sum(s.endswith('::I') for a in arms for _,s in a['requests']),
        actual_write_triggers=dict(Counter(z['reason'] for a in arms for z in a.get('operational_triggers',[]))))


def scopes(rows,primary,controls,by_subgroup):
    groups={'overall':rows}
    if by_subgroup:
        for dim in ('family','layer','duration'):
            for v in sorted({r[dim] for r in rows}):
                groups[dim+'/'+str(v)]=[r for r in rows if r[dim]==v]
    stats={}
    for name,slice_ in groups.items():
        ix=draws(slice_,name)
        stats[name]=dict(n=len(slice_),by_role={k:role_stats(slice_,k) for k in (primary,*controls)},
             paired={k:paired(slice_,primary,k,ix) for k in controls})
    return stats


def gap(rows):
    unresolved=[r['key'] for r in rows if r['minimum'] is None]
    if unresolved:return dict(n=len(rows),unresolved=unresolved,numerator=None,denominator=None,ratio=None)
    num=sum(r['arms']['V_COST']['L']-r['minimum'] for r in rows);den=sum(r['arms']['P']['L']-r['minimum'] for r in rows)
    return dict(n=len(rows),unresolved=[],numerator=num,denominator=den,ratio=num/den if den>EPS else None)


def main():
    verify_source();m=manifest();cfg=spec();parent=unpack(C/'development.json.gz')
    old={r['key']:r for r in parent['rows']};idx={(q['key'],q['role']):q for q in parent['units']}
    units=[];panels={}
    for mode in cfg['settings']:
        rows=[]
        for k in (cfg['order'] if mode=='BASE' else cfg['sensitivity_keys']):
            originally=old[k];case=local_case(mode,k,m);arms={}
            for role in (('B_COST',) if mode=='BASE' else cfg['roles']):
                arms[role],unit=score_return(mode,k,role,case,m);units.append(unit)
            for role in ((*BASE_CONTROLS,'P','ORACLE') if mode=='BASE' else ('P',)):arms[role]=previous_score(originally,role,idx)
            minimum=originally['minimum'] if mode=='BASE' else arms['ORACLE']['oracle']['certified_min']
            if minimum is not None:must(all(a['L']>=minimum-EPS for a in arms.values()),'actual arm below certified minimum '+mode+k)
            rows.append(dict(key=k,family=originally['family'],layer=originally['layer'],duration=case['maintenance']['exposure_s'],
                original_duration=originally['duration'],minimum=minimum,arms=arms))
        panels[mode]=rows
    units_by_id={(u['mode'],u['key'],u['role']) for u in units}
    expected={tuple(z) for g in cfg['groups'].values() for z in g['positions']}
    must(len(units)==612 and len(units_by_id)==612 and units_by_id==expected,'registered scientific positions')
    ids={(u['job'],u['pid']) for u in units};must(len(ids)==612,'independent native processes')
    parent36=[r for r in panels['BASE'] if r['key'] in set(cfg['sensitivity_keys'])]
    values={};worse=[]
    for mode,rows in [('BASE36',parent36),*((k,panels[k]) for k in ('S1','S2','S0'))]:
        values[mode]=dict(scopes=scopes(rows,'V_COST',SENS_CONTROLS,False),gap=gap(rows))
        if mode=='S0':
            for r in rows:
                d=r['arms']['V_COST']['L']-r['arms']['B']['L']
                if d>EPS:worse.append(dict(key=r['key'],family=r['family'],V=r['arms']['V_COST']['L'],B=r['arms']['B']['L'],delta=d))
    base=panels['BASE'];num=sum(r['arms']['B']['L']-r['arms']['B_COST']['L'] for r in base)
    den=sum(r['arms']['B']['L']-r['arms']['V_COST']['L'] for r in base)
    evidence=unpack(ACT/'failure-evidence.json.gz')
    must(evidence['keys']==cfg['failures'] and evidence['source']==filehash(C/'development.json.gz'),'nine saved-only cases')
    result=dict(schema='T4d-public-cost-baseline',job=job(),units=units,panels=panels,base=scopes(base,'B_COST',BASE_CONTROLS,True),
        sensitivity=values,capture=dict(total_B_minus_Bcost=num,total_B_minus_V=den,fraction=num/den if den>EPS else None),
        S0_worse=worse,holdout=dict(H1_commitment=None,H2_commitment=None,generated=0,run=0,accessed=0),
        public_protocol=filehash(PK/'confirmation-protocol-v2.md'),failure_sha256=filehash(ACT/'failure-evidence.json.gz'))
    save_gz(ACT/'development-result.json.gz',result)
    from tables import render
    render(result)
    print('capture',result['capture'],'probe by setting',[(k,v['scopes']['overall']['paired']['V_COST_NOPROBE']['L']) for k,v in values.items()],
          'S0 worse',[(x['key'],x['delta']) for x in worse],flush=True)


if __name__=='__main__':main()
