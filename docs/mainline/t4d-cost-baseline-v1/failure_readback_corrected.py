"""Record nine specified T4c failures from their sealed native originals. No policy or facility call."""
from workpackage import *
from aegis_action_cost.permit import Gate


def original(row,role,unit,source):
    entry=row['arms'][role]['entry']
    dirname=PREV/'positions'/('dev-'+row['key']+'-'+role)/entry['attempt']
    snap=dirname/'original.jsonl.gz';scores=dirname/'score.json'
    must(filehash(snap)==unit['raw'] and filehash(scores)==unit['score'],'original trace and scoring identity')
    saved=read(scores)
    must(saved['entry']==entry and saved['L']==row['arms'][role]['L'],'previous scored position')
    with gzip.open(snap,'rt') as f:first=json.loads(next(f))
    meta=first['metadata'];prog=meta['inputs']['dispatch_program']
    must(prog==source['native']['dispatch_program'] and source['native']['scenario']==meta['source_config']
        and digest(source['attachment'])==meta['t3_received_attachment_sha256'] and meta['v3_received_maintenance']==source['maintenance'],'actual parent condition')
    must(len(meta['policy_public_decisions'])==61 and digest([[z['at'],z['view'],z['proposal']] for z in meta['v3_proposals']])==unit['IPC'],'historical public path')
    return meta,first['terminal'],saved


def tick(item):
    v=item['view'];out=item['decision'];why=out['rationale'];t=v['time']
    clauses=[{k:r.get(k) for k in ('kind','subject','source','origin','record_type','value','arrived','until')}
             for r in v['records'] if r['kind']!='order' and r['arrived']<=t<r['until'] and r['copied_from'] is None]
    meters={}
    for r in v['fixed']:
        if r['arrived']<=t<r['until']:meters[r['field']]={k:r[k] for k in ('ok','origin','sampled','arrived','until')}
    return dict(time=t,chosen=why['chosen'],reason=why['reason'],public_view_sha256=digest(v),groups=why['posterior']['groups'],
        causes=why['posterior']['causes'],support=why['posterior']['supported_worlds'],signals=clauses,meters=meters,
        arrived_own_paid=[q for q in v['paid'] if q['arrived']<=t<q['until']],writes=v['writes'],work=v['work'],
        branches=[{k:b[k] for k in ('first','vector')} for b in why['continuation_table']],denials=out['refusals'])


def intervals(curve):
    return [[a,b,d,s] for a,b,d,s in curve if d>s]


def main():
    verify_source();manifest();panel=unpack(C/'development.json.gz');registry={(e['key'],e['role']):e for e in panel['units']}
    bykey={r['key']:r for r in panel['rows']};d={}
    for k in spec()['failures']:
        row=bykey[k];path=PREV/'dev-inputs'/(k+'.json');case=read(path)
        must(filehash(path)==spec()['public_inputs'][k],'original input')
        pub=case['native']['dispatch_program']['public'];subjects={s['id']:s for s in pub['subjects']}
        role_returns={};vmeta=terminal=None
        for role in ('V_COST','B','P','V_COST_NOPROBE'):
            u=registry[(k,role)];meta,term,scored=original(row,role,u,case)
            role_returns[role]=dict(L=scored['L'],U=scored['U'],person=scored['person'],fee=scored['fee'],requests=scored['requests'],
                 writes=scored['writes'],paid=scored['paid'],loss_intervals=intervals(scored['curve']),maintenance=scored['maintenance'],source=u)
            if role=='V_COST':vmeta=meta;terminal=term
        history=vmeta['policy_public_decisions'];frames=[tick(i) for i in history]
        nr=k.startswith('6-');sid='NR' if nr else 'C/c0' if row['layer']=='0000' else 'N/n0'
        sched=Gate(case['maintenance']['recovery'])
        legal=[it['view']['time'] for it in history if sched.admit(pub,it['view'],subjects[sid],'A')[0]]
        at={0,60}
        if legal:at.update((legal[0],legal[-1]))
        for role in ('V_COST','B'):
            at.update(t for t,task in role_returns[role]['requests'] if task.endswith('::A') or task.endswith('::I'))
        proc_events=[] if terminal is None else [{z:e.get(z) for z in ('t','group_demand_kW','transfer_limit_kW','tripped','controller_on','pump_running','pump_latched','capacity','cooling_exhausted')}
            for e in terminal['events'] if 'group_demand_kW' in e]
        d[k]=dict(family=row['family'],layer=row['layer'],duration=row['duration'],target=sid,minimum=row['minimum'],all_roles=role_returns,
            write_window=subjects[sid]['write_window'],legal_A_on_saved_path=legal,salient_times=sorted(at),frames=frames,
            public_config_sha256=digest(pub),comparison_source=registry[(k,'ORACLE')],private_physical_events=proc_events)
    save_gz(ACT/'failure-evidence.json.gz',dict(job=job(),keys=spec()['failures'],rows=d,source=filehash(C/'development.json.gz'),native_calls=0))
    print('reconciled nine original conditions; actual public decisions, physical events, loss curves and comparison hashes',flush=True)


if __name__=='__main__':main()
