"""Author complete E1-E4 qualification units from literal independent answers.

No model import, execution, or formula solver. Run under Slurm before any model
execution. Numeric expectations are transcribed from the accepted written tables.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import socket

C0 = dict(H=20,tF=10,tR=16,P=1,E0=3,vA=1,vB=1,cA=1,cB=0,capA=1,capB=1,capG=1,
          family='LEGACY_LINE',epoch=0,ready=True,connected=True,permit=True,exec_fault=False,
          tauG=1,tauB=2,read_work=1,publish=1,ttl=12,approval_work=1,prep=2,commit_work=1,
          exit_work=2,verify_work=1,budget=20,calendar=[],window=[0,20],grant_expiry=20,
          revoke=None,work_mode='ONLINE',approval='APPROVE',commit='SUCCESS',verification='PASS',
          exit_result='SUCCESS',guard='ALLOW',compatible='ALLOW',
          permissions=dict(read='ALLOW',propose='ALLOW',verify='ALLOW',direct='ALLOW'),
          read_modes=dict(READ_POS='DEFINITE',READ_VOLT='DEFINITE',READ_CONFIG='DEFINITE'),
          signal_missing=[],demand=[[0,1]])
CASES=[]; PAIRS=[]

def req(action,n=1,**kw):
    p=dict(action=action,request_id='rq-'+str(n),problem_id='q-1',target='feeder-B' if action in ('READ_POS','READ_VOLT') else 'ctrl-1')
    if action=='FIX_CTRL':p['mode']='DIRECT'
    p.update(kw);return p

def step(op,expected=None,select=None,**args):
    out=dict(op=op,args=args)
    if expected is not None:out['expected']=expected
    if select is not None:out['select']=select
    return out

def check(**values):return step('audit',values,list(values))
def advance(t):return step('advance',time=t)
def request(action,n=1,status='ADMITTED',**kw):return step('request',dict(status=status),payload=req(action,n,**kw))
def add(id,refs,steps,overrides=None,kind='run',input=None):
    config=deepcopy(C0);config.update(deepcopy(overrides or {}))
    CASES.append(dict(id=id,refs=refs,kind=kind,input=deepcopy(input) if input is not None else config,steps=deepcopy(steps)))

def rec(action,value,n,obs,avail,expiry,**extra):
    r=dict(record_kind='ACTION_RESULT',record_id='obs-'+str(n),problem_id='q-1',request_id='rq-'+str(n),action=action,
           target='feeder-B' if action in ('READ_POS','READ_VOLT') else 'ctrl-1',value=value,status='KNOWN',
           source_group={'READ_POS':'pos-B','READ_VOLT':'volt-B','READ_CONFIG':'cfg-local'}[action],
           observed_at=obs,available_at=avail,expires_at=expiry,maintenance_epoch='m0',receiver_role='AUDITOR',
           config_epoch=0 if action=='READ_CONFIG' else None,parent_execution_id=None)
    r.update(extra);return r

def verification_record(n,record_n,observed,available,expires,value='PASS',status='VERIFIED_FOR_TARGET'):
    return dict(record_kind='ACTION_RESULT',record_id='obs-'+str(record_n),problem_id='q-1',request_id='rq-'+str(n),action='VERIFY_CTRL',target='ctrl-1',value=value,status=status,source_group='probe-local',observed_at=observed,available_at=available,expires_at=expires,maintenance_epoch='m0',receiver_role='AUDITOR',config_epoch=1,parent_execution_id='ex-1')

def approval_record(receiver='AUDITOR'):
    return dict(record_kind='APPROVAL_RECEIPT',request_id='rq-1',action='FIX_CTRL',problem_id='q-1',target='ctrl-1',decision='APPROVE',grant_id='grant-1',decided_at=1,available_at=1 if receiver=='EXECUTOR' else 2,receiver_role=receiver)

def execution_record(success=True):
    return dict(record_kind='EXECUTION_RECEIPT',request_id='rq-1',action='FIX_CTRL',problem_id='q-1',target='ctrl-1',status='EXECUTED_UNVERIFIED' if success else 'NOT_IMPLEMENTED',committed_at=4 if success else None,available_at=5,receiver_role='AUDITOR',execution_id='ex-1' if success else None,target_config_epoch=1 if success else None)

def public_base():
    return dict(time=6,pre_open=True,pending=False,terminal_failure=False,phase='NONE',
                records=[],receipts=[],attempted=[],context=dict(permissions=deepcopy(C0['permissions']),
                compatible='ALLOW',window=[0,20],available=17,read_reserve=3,chain_reserve=6,
                chain_finish=14,read_parameters_known=True,chain_parameters_known=True),certificate=None)

def dcase(id,values=None,change=None,expected='PROPOSE_FIX',reason=None):
    v=public_base()
    if values is not None:
        v['records']=[rec(a,x,i,o,b,e) for a,x,i,o,b,e in zip(['READ_POS','READ_VOLT','READ_CONFIG'],values,[1,2,3],[1,3,5],[2,4,6],[13,15,17]) if x is not None]
    if change:change(v)
    for method in ['M0','B1']:
        why=reason if reason and method=='M0' else ('C5' if expected=='PROPOSE_FIX' else expected)
        add(id+'-'+method,[id],[],kind='decision',input=dict(view=v,method=method,expected=dict(action=expected,mode='EVIDENCE' if expected=='PROPOSE_FIX' else None,reason=why)))
    PAIRS.append(dict(id=id+'-action-equivalence',units=[id+'-M0',id+'-B1'],paths=['decision.action','decision.mode']))

identity=dict(kind='PLAN_IDENTITY',problem_id='q-1',target='ctrl-1',expires_at=20,plan='FIX_CTRL-v1',version=1)
dcase('D01',[1,1,'LEGACY_LINE'],expected='NO_ACTION_CURRENT_SCOPE')
dcase('D02',expected='READ_POS')
dcase('D03',[0,1,'LEGACY_LINE'],lambda v:v.update(certificate=identity),reason='D3')
dcase('D04a',[0,1,'LEGACY_LINE'])
dcase('D04b',[0,1,'LEGACY_LINE'],lambda v:v.update(certificate=dict(identity,expires_at=5)))
for suffix,kind in [('a','NONIDENTITY_BOUNDS'),('b','UPPER_ONLY')]:
    dcase('D05'+suffix,[0,1,None],lambda v,k=kind:v.update(certificate=dict(kind=k,direct_upper=1,read_upper=2)),expected='READ_CONFIG')
dcase('D06a',[0,1,'LEGACY_LINE'],lambda v:v['context'].update(available=0),expected='INFEASIBLE')
dcase('D06b',[0,1,'LEGACY_LINE'],lambda v:v['context'].update(window=[0,6]),expected='STOP')
dcase('D06c',[0,1,'LEGACY_LINE'],lambda v:v['context'].update(window=[0,10]),expected='INFEASIBLE')
dcase('D07a',[0,1,None],lambda v:v['context'].update(read_parameters_known=False),expected='INSUFFICIENT_INFORMATION')
def conflict(v):
    v['attempted']=['READ_POS','READ_VOLT','READ_CONFIG']
    v['records'].append(dict(record_kind='DOCUMENT_CLAIM',record_id='doc-1',problem_id='q-1',document_id='maint-1',claim_field='breaker_position',target='feeder-B',value=1,status='KNOWN',source_group='maint-doc',observed_at=1,available_at=2,expires_at=13,maintenance_epoch='m0',receiver_role='AUDITOR',request_id=None,action=None,config_epoch=None,parent_execution_id=None))
dcase('D07b',[0,1,'LEGACY_LINE'],conflict,expected='INSUFFICIENT_INFORMATION')
for suffix,cause in [('a','DENIED'),('b','NOT_IMPLEMENTED'),('c','VERIFY_FAILED')]:
    dcase('D08'+suffix,change=lambda v,c=cause:v.update(terminal_failure=True,phase='TERMINAL',terminal_reason=c),expected='STOP_UNRESOLVED')
dcase('D09',[None,1,None],lambda v:v.update(attempted=['READ_POS']),expected='READ_CONFIG')

def seq(c=0,v=1,k='LEGACY_LINE'):
    rows=[]
    for n,(a,start,val) in enumerate([('READ_POS',0,c),('READ_VOLT',2,v),('READ_CONFIG',4,k)],1):
        rows.extend([advance(start),request(a,n),advance(start+1),step('save_view',label='before_'+a),check(**{'observation_count':n-1}),advance(start+2),step('record',rec(a,val,n,start+1,start+2,start+13),index=n-1)])
    return rows
add('I01',['I01'],seq())
add('I02-position',['I02'],seq(c=1),dict(cB=1))
add('I02-voltage',['I02'],seq(v=0),dict(vB=0))
PAIRS += [dict(id='I02-position-before',units=['I01','I02-position'],paths=['saved.before_READ_POS']),dict(id='I02-voltage-before',units=['I01','I02-voltage'],paths=['saved.before_READ_VOLT'])]
for ident,mode in [('I03a','INCONCLUSIVE'),('I03b','CHANNEL_FAILED')]:
    add(ident,['I03'],[request('READ_POS'),advance(1),check(observation_count=0,spent=1,reserved=0,available=19),advance(2),step('record',rec('READ_POS','UNKNOWN',1,1,2,13,status='NO_RESULT'),index=0)],dict(read_modes=dict(C0['read_modes'],READ_POS=mode)))
PAIRS.append(dict(id='I03-private-failure-isolation',units=['I03a','I03b'],paths=['public']))
for suffix,payload,status in [('role',req('READ_POS',role='AUDITOR'),'INVALID_REQUEST'),('target',req('READ_POS',target='q-2'),'INVALID_REQUEST'),('private',req('READ_POS',family='LEGACY_LINE'),'INVALID_REQUEST')]:
    add('I04-'+suffix,['I04'],[step('request',dict(status=status),payload=payload),check(spent=0,observation_count=0,epoch=0)])
add('I04-denied',['I04'],[request('READ_POS',status='ACCESS_DENIED'),check(spent=0,observation_count=0)],dict(permissions=dict(C0['permissions'],read='DENY')))
add('I05',['I05'],seq()+[advance(12),step('copy',dict(status='ACCEPTED'),record_id='obs-1',copy_id='copy-1'),advance(13),check(**{'current_actions':['READ_VOLT','READ_CONFIG'],'spent':3,'observation_count':3,'source_groups':['pos-B','volt-B','cfg-local']})])

def fix(a,verify=True):
    rows=[advance(a),request('FIX_CTRL')]
    if verify:rows += [advance(a+5),check(phase='EXITING'),advance(a+6),request('VERIFY_CTRL',2,execution_id='ex-1',target_config_epoch=1),advance(a+8)]
    return rows

add('I06',['I06'],seq()+[request('FIX_CTRL',4),advance(10),check(epoch=1),step('view_select',{'known_epoch':0},select=['known_epoch']),advance(11),step('view_select',{'known_epoch':1},select=['known_epoch']),advance(12),request('VERIFY_CTRL',5,execution_id='ex-1',target_config_epoch=1),advance(14),check(verification_result='PASS',epoch=1),step('record',verification_record(5,4,13,14,25),index=3)],dict(tF=None,tR=None))
for suffix,ex,ep in [('execution','wrong',1),('epoch','ex-1',0)]:
    add('I07-'+suffix,['I07'],seq()+[request('FIX_CTRL',4),advance(12),request('VERIFY_CTRL',5,status='INVALID_PARENT',execution_id=ex,target_config_epoch=ep),check(verification_result='NOT_REQUESTED')],dict(tF=None,tR=None))
for suffix,payload in [('action',req('READ_VOLT')),('target',req('READ_POS',target='q-2'))]:
    add('I08-'+suffix,['I08'],[request('READ_POS'),request('READ_POS'),step('request',dict(status='INVALID_REQUEST'),payload=payload),advance(2),check(spent=1,observation_count=1)])
add('I09',['I09'],[request('READ_POS'),advance(1),check(observation_count=0),advance(3),check(spent=3,reserved=0,observation_count=0,read_status='ABORTED_READ')],dict(tF=1))
add('I10',['I10'],[request('READ_POS'),advance(2),check(pre_open=False,observation_count=1,spent=1)],dict(tF='3/2'))
for suffix,k in [('legacy','LEGACY_LINE'),('revised','REVISED_LOCAL')]:
    add('I11-'+suffix,['I11'],[request('READ_CONFIG'),advance(1),step('save_view',label='before'),check(observation_count=0),advance(2),step('record',rec('READ_CONFIG',k,1,1,2,13),index=0),advance(13),check(current_actions=[])],dict(family=k))
PAIRS.append(dict(id='I11-before-arrival',units=['I11-legacy','I11-revised'],paths=['saved.before']))

add('A01',['A01'],fix(0)+[check(epoch=1,family='REVISED_LOCAL',commit_result='SUCCESS',verification_result='PASS',spent=6),step('receipt',approval_record(),kind='APPROVAL_RECEIPT'),step('internal_approval',approval_record('EXECUTOR')),step('receipt',execution_record(),kind='EXECUTION_RECEIPT'),step('record',verification_record(2,1,7,8,19),index=0)])
add('A02',['A02'],fix(0,False)+[advance(2),check(epoch=0,spent=0,phase='TERMINAL')],dict(approval='DENY'))
for suffix,over,commit in [('commit',dict(commit='FAIL'),'FAIL'),('guard',dict(guard='BLOCK'),'NOT_ATTEMPTED')]:
    add('A03-'+suffix,['A03'],fix(0,False)+[advance(6),check(epoch=0,spent=5,commit_result=commit,verification_result='NOT_REQUESTED'),step('receipt',execution_record(False),kind='EXECUTION_RECEIPT')],over)
add('A04',['A04'],fix(0,False)+[advance(6),check(epoch=0,spent=5,commit_result='NOT_ATTEMPTED')],dict(revoke=[4,'FIX_GRANT']))
add('A05',['A05'],fix(0,False)+[advance(6),check(epoch=0,spent=0,commit_result='NOT_ATTEMPTED')],dict(grant_expiry='7/2',tF=None,tR=None))
for suffix,mode,result in [('a','FAIL','FAIL'),('b','INCONCLUSIVE','INCONCLUSIVE'),('c','CHANNEL_FAILED','INCONCLUSIVE')]:
    add('A06'+suffix,['A06'],fix(0)+[check(epoch=1,family='REVISED_LOCAL',verification_result=result,spent=6),step('record',verification_record(2,1,7,8,19,value='FAIL' if result=='FAIL' else 'UNKNOWN',status='VERIFY_FAILED' if result=='FAIL' else 'INCONCLUSIVE'),index=0)],dict(verification=mode))
add('A07',['A07'],fix(0)+[check(epoch=1,family='REVISED_LOCAL',spent=6)],dict(family='REVISED_LOCAL'))
add('A08',['A08'],[request('FIX_CTRL',status='ACCESS_DENIED'),check(epoch=0,spent=0)],dict(permissions=dict(C0['permissions'],direct='DENY')))
add('A09',['A09'],fix(5,False)+[advance(20),check(epoch=1,commit_result='SUCCESS',verification_result='NOT_REQUESTED',spent=5)])

def signals(vals):return {k:dict(value=v,quality='OK',sample_time=10) for k,v in zip(['zVA','zVB','zCA','zCB','zSA','zSB'],vals)}
sig=signals([0,1,1,0,1,1])
def ctrl(id,family,packet,result,error=None,private=None):
    add(id,[id.split('-')[0]],[],kind='control',input=dict(family=family,signals=packet,time=10,expected=result,expected_error=error,private_fixture=private))
for family,result in [('LEGACY_LINE',0),('REVISED_LOCAL',1)]:ctrl('C01-'+family,family,sig,result)
for family in ['LEGACY_LINE','REVISED_LOCAL']:ctrl('C02-'+family,family,signals([0,1,1,1,1,1]),0)
for suffix,private in [('connection',dict(cB=1)),('capacity',dict(capB=0))]:
    for family,result in [('LEGACY_LINE',0),('REVISED_LOCAL',1)]:ctrl('C03-'+suffix+'-'+family,family,sig,result,private=private)
for suffix,field in [('connection','zCB'),('support','zSB')]:
    p=signals([1,1,1,1,1,1]);p['zVA']=dict(value='UNKNOWN',quality='MISSING',sample_time=10);p[field]=dict(value='UNKNOWN',quality='MISSING',sample_time=10)
    ctrl('C04-'+suffix,'REVISED_LOCAL',p,1)
for suffix,over,at10 in [('ready',dict(ready=False),'FAILED'),('permit',dict(permit=False),'FAILED'),('capacity',dict(capG=0),'FAILED'),('fault',dict(exec_fault=True),'STARTING')]:
    add('C05-'+suffix,['C05'],[advance(10),check(g_state=at10),advance(11),check(g_state='FAILED')],dict(over,family='REVISED_LOCAL'))
p=deepcopy(sig);p['zVA']['sample_time']=11;ctrl('C06-future','REVISED_LOCAL',p,None,'ValueError')
p=deepcopy(sig);p['zVA']['value']='UNKNOWN';ctrl('C06-invalid','REVISED_LOCAL',p,None,'ValueError')

for id,a,epoch,spent,result in [('T01',5,1,5,'SUCCESS'),('T02',6,0,5,'NOT_ATTEMPTED'),('T03',7,0,4,'NOT_ATTEMPTED')]:
    add(id,[id],fix(a,False)+[advance(20),check(epoch=epoch,spent=spent,commit_result=result,verification_result='NOT_REQUESTED')])
add('T04',['T04'],[request('READ_POS'),advance(3),check(spent=0,reserved=3),advance(5),check(spent=1,observation_count=1),step('record',rec('READ_POS',0,1,4,5,16),index=0)],dict(calendar=[[0,3]]))
add('T05',['T05'],fix(0,False)+[advance(1),check(isolated=True,device='OFF'),advance(4),check(isolated=True,epoch=1),advance(6),check(isolated=False,device='BOOTING')],dict(work_mode='LOAD_ISOLATED',tF=None,tR=None))
add('T06',['T06'],fix(6,False)+[advance(10),check(isolated=True,epoch=0),advance(12),check(isolated=False,spent=5)],dict(work_mode='LOAD_ISOLATED'))
add('T07',['T07'],fix(0,False)+[advance(20),check(isolated=True,phase='EXITING',spent=19,resource_overrun=True)],dict(work_mode='LOAD_ISOLATED',exit_result='FAIL',tF=None,tR=None))
add('T08a',['T08'],[request('READ_POS'),advance(3),check(spent=3,observation_count=0,read_status='ABORTED_READ')],dict(revoke=[1,'READ_ROLE']))
add('T08b',['T08'],fix(0,False)+[advance(3),check(epoch=0,spent=0)],dict(grant_expiry=2,tF=None,tR=None))
add('T09',['T09'],fix(6,False)+[advance(10),check(vA=1,pre_open=False,epoch=0,commit_result='NOT_ATTEMPTED'),advance(20),check(spent=5,L=0,E=3)],dict(tR=10))
budgetsteps=[]
def accounts(spent,reserved,available):
    return dict(person=dict(limit=4,spent=spent,reserved=reserved,available=available),tool=dict(limit=4,spent=spent,reserved=reserved,available=available))
for t,action,n,expect,status in [(0,'READ_POS',1,[0,3,1],'ADMITTED'),(2,'READ_VOLT',2,[1,3,0],'ADMITTED'),(4,'READ_CONFIG',3,[2,0,2],'BUDGET_UNAVAILABLE')]:
    budgetsteps += [advance(t),request(action,n,status=status),check(spent=expect[0],reserved=expect[1],available=expect[2],budgets=accounts(*expect))]
    if t<4:budgetsteps +=[advance(t+1),check(spent=n,reserved=0,available=4-n,budgets=accounts(n,0,4-n),read_status='PENDING_PUBLICATION')]
budgetsteps +=[advance(20),check(spent=2,reserved=0,available=2,observation_count=2,budgets=accounts(2,0,2),observation_actions=['READ_POS','READ_VOLT'],started_actions=['READ_POS','READ_VOLT'])]
add('T10',['T10'],budgetsteps,dict(budget=4))

# Literal analytic results. No model or arithmetic evaluator produces these.
service=[
 ('S01',{},None,dict(L=5,U=5,E=0,load_energy=17,ups_energy=3,recoveries=[dict(off=13,recovered=18,duration=5,right_censored=False)])),
 ('S02',dict(tR=None),None,dict(L=7,U=7,E=0,load_energy=13,ups_energy=3,recoveries=[dict(off=13,recovered=None,lower_bound=7,right_censored=True)])),
 ('S03',dict(family='REVISED_LOCAL'),None,dict(L=0,U=0,E=2,load_energy=20,ups_energy=1,recoveries=[])),
 ('S04',dict(family='REVISED_LOCAL',E0=1),None,dict(L=0,U=0,E=0,load_energy=20,ups_energy=1,recoveries=[])),
 ('S05',dict(family='REVISED_LOCAL',E0='1/2'),None,dict(L='5/2',U='5/2',E=0,load_energy='39/2',ups_energy='1/2',recoveries=[dict(off='21/2',recovered=13,duration='5/2',right_censored=False)])),
 ('S06',dict(demand=[[0,1],[13,0],[18,1]]),None,dict(L=0,U=0,E=0,load_energy=17,ups_energy=3,recoveries=[dict(off=13,recovered=18,duration=5,right_censored=False)])),
 ('S07',dict(work_mode='LOAD_ISOLATED',tF=None,tR=None),0,dict(L=7,U=7,E=3,load_energy=15,ups_energy=0,spent=6,verification_result='PASS',recoveries=[dict(off=1,recovered=8,duration=7,right_censored=False)])),
 ('S08',dict(work_mode='LOAD_ISOLATED',exit_result='FAIL',tF=None,tR=None),0,dict(L=19,U=19,E=3,load_energy=1,ups_energy=0,recoveries=[dict(off=1,recovered=None,lower_bound=19,right_censored=True)])),
 ('S09',{},0,dict(L=0,U=0,E=2,load_energy=20,ups_energy=1,epoch=1,verification_result='PASS',recoveries=[])),
 ('S10a',{},6,dict(L=5,U=5,spent=5,epoch=0,E=0,ups_energy=3,load_energy=17,recoveries=[dict(off=13,recovered=18,duration=5,right_censored=False)])),('S10b',{},7,dict(L=5,U=5,spent=4,epoch=0,E=0,ups_energy=3,load_energy=17,recoveries=[dict(off=13,recovered=18,duration=5,right_censored=False)])),
 ('S11',dict(work_mode='LOAD_ISOLATED'),6,dict(L=10,U=10,E=0,ups_energy=3,recoveries=[dict(off=7,recovered=14,duration=7,right_censored=False),dict(off=15,recovered=18,duration=3,right_censored=False)])),
 ('S12a',dict(tF=None,tR=None),None,dict(L=0,U=0,E=3,load_energy=20,ups_energy=0,recoveries=[])),
 ('S12b',dict(tF=None,tR=None,demand=[[0,0]]),None,dict(L=0,U=0,E=3,load_energy=20,ups_energy=0,recoveries=[])),
 ('S13',dict(tR=10),None,dict(L=0,U=0,E=3,load_energy=20,ups_energy=0,recoveries=[],pre_open=False,vA=1))]
for ident,over,a,expected in service:
    steps=[] if a is None else fix(a,verify=(ident in ('S07','S09')))
    add(ident,[ident[:3] if ident.startswith(('S10','S12')) else ident],steps+[advance(20),check(**expected),step('conservation')],over)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or socket.gethostname().split('.')[0]=='mu01':raise SystemExit('Slurm allocation required')
    args.output.mkdir(parents=True,exist_ok=False)
    payload=dict(schema='aegisdc-e14-frozen-units-v2',source='e1-e4-v2 literal specification and explicit user corrections',model_calls_at_authoring=0,units=CASES,pairs=PAIRS)
    data=(json.dumps(payload,ensure_ascii=False,indent=2)+'\n').encode()
    (args.output/'cases.json').write_bytes(data)
    index=dict(units=len(CASES),pairs=len(PAIRS),sha256=hashlib.sha256(data).hexdigest(),coverage={c['id']:c['refs'] for c in CASES},expected_answers_source='Literal authored tables, no model import or outputs')
    (args.output/'coverage.json').write_text(json.dumps(index,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in index.items() if k!='coverage'}))

if __name__=='__main__':main()
