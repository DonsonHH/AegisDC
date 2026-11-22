"""Before production, exercise immutable public workers, arrival guards and the transparent rule."""
from copy import deepcopy
from workpackage import *
from public_adapter import Worker,operative_view
import isolation as old_witness


def history_frames(history, duration):
    for item in history:
        frame=deepcopy(item)
        for r in frame['records']:
            if r['kind']=='order':r['value']=f'OPEN/MAINT-{duration}'
        yield frame


def run_twins(mode,role,manifest_,a,b,path):
    children=[Worker(mode,role,manifest_,path/(mode+'-'+role+suf+'.stderr')) for suf in ('-a','-b')]
    duration=0 if mode=='S0' else 600
    try:
        for proc,item in zip(children,(a,b)):proc.start(item[0])
        outcomes=[]
        for x,y in zip(history_frames(a[1],duration),history_frames(b[1],duration),strict=True):
            one,two=[proc.choose(a[0],v,role,{}) for proc,v in zip(children,(x,y),strict=True)]
            must(one==two,'same public history, different decision')
            outcomes.append(digest(one))
        must(len(outcomes)==61,'clock')
        return dict(public_frames=61,whole_replies_equal=True,output_hash=digest(outcomes),ipc=digest(children[0].ipc))
    finally:
        for proc in children:proc.close()


def transparent_fixture(a,inventory,path):
    # Public dispatch-only fixtures with literal expected choices, independent of any trial outcome.
    pub=deepcopy(a[0]);start=deepcopy(a[1][0]);sub={s['id']:s for s in pub['subjects']}
    for sid in sub:sub[sid]['write_window']=[0,156] if sid=='LC' else [1,2]
    proc=Worker('BASE','B_COST',inventory,path/'rule-positive.stderr');proc.start(pub)
    tests=[]
    try:
        def check_tick(t,duration,want,alarm=False):
            v=deepcopy(start);v.update(time=t,fixed=[],work=[],issued=[],writes=[],paid=[])
            v['records']=[dict(r,value='OPEN/MAINT-'+str(duration)) for r in v['records'] if r['kind']=='order']
            if alarm:v['records'].append(dict(kind='alarm',source='alarm-desk',origin='fixture',copied_from=None,
                subject='power-board',value='ALARM',sampled=t,arrived=t,until=t+600))
            choice=proc.choose(pub,v,'B_COST',{});task=(choice['request'] or {}).get('task')
            must(task==want,'rule witness '+str((t,duration,alarm,want,task)))
            tests.append([t,duration,alarm,task,choice['rationale']['reason']])
        check_tick(0,0,'LC::A')
        check_tick(0,600,None)
        check_tick(60,600,None)
        check_tick(120,600,'LC::A')
        check_tick(60,600,'LC::A',True)
    finally:proc.close()
    # Shared one-slot issue window: both candidates are admissible individually.
    conflict=deepcopy(pub);routes=conflict['routes'];routes[:]=['LG','LC','LB']
    for sub in conflict['subjects']:
        sub['write_window']=[0,36] if sub['id'] in ('LG','LC') else [1,2]
    proc=Worker('BASE','B_COST',inventory,path/'rule-conflict.stderr');proc.start(conflict)
    try:
        v=next(history_frames([start],0));choice=proc.choose(conflict,v,'B_COST',{})
        must(choice['request']['task']=='LG::A' and choice['rationale']['reason'].startswith('ROUTE_CONFLICT'),'default route')
        tests.append(['one_window','LG::A'])
    finally:proc.close()
    return tests


def main():
    verify_source();m=manifest();folder=ACT/'isolation';folder.mkdir()
    a,b=(old_witness.history(k) for k in ('5-04','5-10'))
    must(a[:2]==b[:2] and a[2]!=b[2],'previous actual paired private worlds')
    records={mode:{r:run_twins(mode,r,m,a,b,folder) for r in ('B_COST','V_COST','V_COST_NOPROBE')} for mode in spec()['settings']}
    guards=[]
    for role in ('B_COST','V_COST'):
        for issue in ('early','private'):
            w=Worker('BASE',role,m,folder/(role+'-'+issue+'.stderr'));w.start(a[0])
            frame=deepcopy(a[1][0]);frame=operative_view(frame) if role=='B_COST' else frame
            if issue=='early':frame['records'][0]['arrived']=60
            else:frame['private_cause']='guard'
            try:
                w.message({'view':frame})
            except RuntimeError:guards.append([role,issue])
            finally:w.close(failed=True)
    must(len(guards)==4,'public rejection')
    fixtures=transparent_fixture(a,m,folder)
    save(folder/'result.json',dict(job=job(),inputs=filehash(ACT/'inputs/manifest.json'),worlds=[a[2],b[2]],source_raw=[a[3],b[3]],
        same_public=digest(a[0]),noninterference=records,negative=guards,positive=fixtures,native_facility_runs=0))
    print('4 settings x 3 workers x 61 equal public clocks; 4 rejected inputs;',len(fixtures),'decision fixtures',flush=True)

if __name__=='__main__':main()
