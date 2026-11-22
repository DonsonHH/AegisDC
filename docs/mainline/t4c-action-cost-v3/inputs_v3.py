"""Generate public development and engineering inputs. No interface to a holdout seed."""
from common_v3 import *
from generator_v2 import FAMILIES,complete,base_case,incident_case,source_rng,DEFS,msg
from common import templates

RULES=read(SRC/'rules.json')
SEED=2026112251
SID=('C/c0','N/n0','N/n0','C/c0','LC','NR')
SECOND=('N/n0','C/c0','C/c0','N/n0','LG','NC')


def attach(x,seconds):
    x['maintenance']=dict(exposure_s=seconds,capacity=RULES['bypass_capacity'],recovery=RULES['exclusive_recovery_s'])
    for r in x['native']['dispatch_program']['channel']:
        if r['kind']=='order':r['value']='OPEN/MAINT-'+str(seconds)
    return x


def condition(seed,i,n,templates_):
    fam=FAMILIES[i]
    if i>=4:
        desc=incident_case(seed,n,fam)
    else:
        desc=base_case(seed,n,fam,templates_)
        target=desc['first']
        other='C/c0' if target=='N/n0' else 'N/n0'
        desc['windows'][other]=[0,desc['windows'][target][1]]
    menu=[s for s,count in zip(RULES['exposure_menu_s'],RULES['counts_per_twelve'],strict=True) for _ in range(count)]
    block,slot=divmod(n,12)
    source_rng(seed,'maintenance-bypass-v3',fam,block).shuffle(menu)
    return attach(complete(desc,templates_,seed),menu[slot])


def fixture(i,source,case):
    fam=FAMILIES[i];first=SID[i];second=SECOND[i]
    if i>=4:
        desc=incident_case(SEED,0,fam,'NORMAL')
    else:
        desc=base_case(SEED,0,fam,source)
        desc['subjects']=['C/c0','N/n0']
        desc['donor'].update(initial='S12',events=[],shift_starts={'C':0,'N':0},
            physical=dict(filter_resistance_multiplier=1,network_service_capacity=1,service_demand=1,
                          storage_service_capacity=1,rectifier_capacity=5000000))
    desc['inspect']=list(desc['subjects'])
    desc['windows']={s:[0,1500] for s in desc['subjects']}
    desc['stream']=[msg('order',s,'fixture-desk',0,0,3601,'OPEN',origin='order/'+s) for s in desc['subjects']]
    if i==5:desc['stream'].append(msg('release','NC','works-office',0,0,3601,'HANDOVER_RELEASED',origin='fixture-handover'))
    onset=155 if first=='C/c0' else 35
    expected=dict(L=0,U=0,write_first=first,first_time=onset,lock_refusal=[],issued_A=[])
    if case in ('wrong','bypass'):
        seconds=600 if case=='wrong' else 0
        plan={0:first+'::A'}
        expected.update(L=seconds/2,U=seconds/2,issued_A=[[0,first+'::A']],indicated=False,
                        penalty_until=onset+seconds)
    elif case in ('lock','clear'):
        seconds=0
        plan={120:second+'::A'}
        if case=='lock':
            plan.update({0:first+'::A',600:second+'::A'})
            expected.update(issued_A=[[0,first+'::A'],[600,second+'::A']],lock_refusal=[[120,second]])
        else:
            expected.update(write_first=second,first_time=None,issued_A=[[120,second+'::A']])
    else:
        seconds=1200 if case=='direct' else 0
        desc['donor']['physical']['network_service_capacity']=.25
        desc['windows']['N/n0']=[0,220]
        if case=='lock-loss':
            plan={0:'C/c0::A',60:'N/n0::A',180:'N/n0::A'}
            expected.update(L=2700,U=2700,write_first='C/c0',first_time=155,
                issued_A=[[0,'C/c0::A']],lock_refusal=[[60,'N/n0'],[180,'N/n0']])
        else:
            t=0 if case=='direct' else 60
            plan={t:'N/n0::A'}
            expected.update(L=(t+35)*.75,U=(t+35)*.75,write_first='N/n0',first_time=t+35,indicated=True,
                            penalty_until=t+35,issued_A=[[t,'N/n0::A']])
    return dict(case=attach(complete(desc,source,SEED),seconds),plan=plan,expected=expected)


def prepare():
    pinned();src=templates()
    pairs={}
    for phase in ('eng','dev'):
        dest=ACT/(phase+'-inputs');dest.mkdir();files={};keys=[]
        with gzip.open(ACT/(phase+'-inputs.jsonl.gz'),'xt',encoding='utf-8',compresslevel=5) as out:
            if phase=='eng':
                items=[(f'{i+1}-{c}',fixture(i,src,c)) for i in range(6) for c in ('wrong','bypass','lock','clear')]
                items.extend((c,fixture(1,src,c)) for c in ('direct','lock-loss','lock-clear'))
            else:
                items=[(f'{i+1}-{n+1:02d}',condition(SEED,i,n,src)) for n in range(12) for i in range(6)]
            for k,x in items:
                path=dest/(k+'.json');write(path,x);files[k]=sha(path);keys.append(k)
                out.write(json.dumps([k,x],separators=(',',':'),allow_nan=False)+'\n')
        pairs[phase]=dict(purpose=phase,files=files,order=keys,input_archive=sha(ACT/(phase+'-inputs.jsonl.gz')),
                  rules=sha(SRC/'rules.json'),source_freeze=sha(PK/'freeze.json'),job=job(),holdout_generated=0)
        write(dest/'manifest.json',pairs[phase])
    print('materialized',[(k,len(v['order'])) for k,v in pairs.items()],flush=True)

if __name__=='__main__':prepare()
