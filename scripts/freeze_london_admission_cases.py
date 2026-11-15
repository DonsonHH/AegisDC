"""Independent literal C4/C7 flow inputs, frozen before implementation repair."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import socket
from freeze_london_e14_cases import C0, req

UNITS=[];PAIRS=[]

def op(name,expected=None,**args):
    row=dict(op=name,args=args)
    if expected is not None:row['expected']=expected
    return row

def audit(**fields):return op('audit',fields)
def move(t):return op('advance',time=t)
def direct():return op('request',{'status':'ADMITTED'},payload=req('FIX_CTRL'))
def cycle(label,action,n=1,reply='ADMITTED',plan=None):
    expected={'view.view_schema':'aegisdc-e14-public-v2','decision.action':action,'reply':None if reply is None else {'status':reply}}
    if action=='VERIFY_CTRL':
        expected.update({'payload.execution_id':'ex-1','payload.target_config_epoch':1})
    if plan:
        name,fields=plan
        expected.update({'view.context.acquisition_plans.'+name+'.'+k:v for k,v in fields.items()})
    return op('cycle',expected,label=label,request_id='rq-'+str(n))

def add(id,changes,steps):
    c=deepcopy(C0);c.update(tF=None,tR=None);c.update(changes)
    for method in ['M0','B1']:
        UNITS.append(dict(id=id+'-'+method,kind='flow',refs=[id,'C4/C7 public acquisition plan v2'],input=dict(config=deepcopy(c),method=method),steps=deepcopy(steps)))
    labels=[s['args']['label'] for s in steps if s['op']=='cycle']
    paths=[f'cycles.{label}.{field}' for label in labels for field in ['decision.action','payload','reply']]
    PAIRS.append(dict(id=id+'-method-consistency',units=[id+'-M0',id+'-B1'],paths=paths))

add('F01-c7-own-recipe',dict(read_work=5,verify_work=1,budget=8),[
 direct(),move(6),audit(spent=5,available=3,phase='AWAITING_VERIFY'),
 cycle('verify','VERIFY_CTRL',2,plan=('VERIFY_CTRL',dict(work=1,exit_reserve=2,reserve=3,earliest_start=6,work_complete=7,available_at=8,reserved_until=9,admissible=True,reason='ADMITTED'))),
 move(8),audit(spent=6,reserved=0,available=2,epoch=1,verification_result='PASS',phase='TERMINAL')])
add('F02-c7-long-verify',dict(read_work=1,verify_work=5,budget=12),[
 direct(),move(6),cycle('verify','VERIFY_CTRL',2,plan=('VERIFY_CTRL',dict(work=5,reserve=7,earliest_start=6,work_complete=11,available_at=12,reserved_until=13,admissible=True))),
 move(12),audit(spent=10,reserved=0,available=2,verification_result='PASS')])
add('F03-c7-queue',dict(calendar=[[6,9]]),[
 direct(),move(6),cycle('verify','VERIFY_CTRL',2,plan=('VERIFY_CTRL',dict(earliest_start=9,reserved_until=12,available_at=11,admissible=True))),
 audit(spent=5,reserved=0),move(9),audit(spent=5,reserved=3),move(11),audit(spent=6,verification_result='PASS')])
add('F04-c7-window-equal',dict(window=[0,9]),[
 direct(),move(6),cycle('verify','VERIFY_CTRL',2,plan=('VERIFY_CTRL',dict(reserved_until=9,available_at=8,admissible=True))),
 move(8),audit(spent=6,verification_result='PASS')])
add('F05-c4-window-short',{},[
 move(18),cycle('read','INSUFFICIENT_INFORMATION',reply=None,plan=('READ_POS',dict(reserve=3,admissible=False,reason='NOT_STARTED_RESOURCE'))),
 move(20),audit(spent=0,observation_count=0,started_actions=[])])
add('F06-c4-window-equal',{},[
 move(17),cycle('read','READ_POS',plan=('READ_POS',dict(earliest_start=17,work_complete=18,available_at=19,reserved_until=20,admissible=True))),
 move(19),audit(spent=1,observation_count=1,observation_actions=['READ_POS'])])
add('F07-c4-queue',dict(calendar=[[0,3]]),[
 cycle('read','READ_POS',plan=('READ_POS',dict(earliest_start=3,reserved_until=6,available_at=5,admissible=True))),
 audit(spent=0,reserved=0),move(3),audit(spent=0,reserved=3),move(5),audit(spent=1,observation_count=1)])
add('F08-c4-calendar-short',dict(calendar=[[16,19]]),[
 move(16),cycle('read','INSUFFICIENT_INFORMATION',reply=None,plan=('READ_POS',dict(admissible=False,reason='NOT_STARTED_RESOURCE'))),
 move(20),audit(spent=0,observation_count=0,started_actions=[])])
add('F09-c4-budget-short',dict(budget=2),[
 cycle('read','INSUFFICIENT_INFORMATION',reply=None,plan=('READ_POS',dict(reserve=3,admissible=False,reason='BUDGET_UNAVAILABLE'))),
 move(2),audit(spent=0,available=2,observation_count=0)])
add('F10-c4-budget-equal',dict(budget=3),[
 cycle('read','READ_POS',plan=('READ_POS',dict(reserve=3,admissible=True))),audit(spent=0,reserved=3,available=0),
 move(2),audit(spent=1,reserved=0,available=2,observation_count=1)])
add('F11a-private-guard',dict(tF=10,tR=16),[cycle('read','READ_POS')])
add('F11b-private-guard',dict(tF=1,tR=16,family='REVISED_LOCAL',cB=1,ready=False,approval='DENY',commit='FAIL',verification='FAIL',guard='BLOCK'),[cycle('read','READ_POS')])
for method in ['M0','B1']:
    PAIRS.append(dict(id='F11-hidden-plan-isolation-'+method,units=['F11a-private-guard-'+method,'F11b-private-guard-'+method],paths=['cycles.read']))
add('F12-before-window-queue',dict(window=[5,20]),[
 cycle('read','READ_POS',plan=('READ_POS',dict(earliest_start=5,reserved_until=8,available_at=7,admissible=True))),
 audit(spent=0,reserved=0),move(7),audit(spent=1,observation_count=1)])
# Complete literal public point at t=0. Each negative changes only its target
# field; a generic missing-time/record failure must not satisfy this witness.
valid_view=dict(view_schema='aegisdc-e14-public-v2',time=0,pre_open=True,pending=False,terminal_failure=False,phase='NONE',records=[],receipts=[],history=[],attempted=[],known_epoch=None,certificate=None,
    context=dict(permissions=dict(read='ALLOW',propose='ALLOW',verify='ALLOW',direct='ALLOW'),compatible='ALLOW',window=[0,20],available=20,read_reserve=3,verify_reserve=3,chain_reserve=8,chain_finish=8,chain_resource_end=9,read_parameters_known=True,chain_parameters_known=True,
    acquisition_plans={action:dict(work=1,exit_reserve=2,reserve=3,earliest_start=0,work_complete=1,available_at=2,reserved_until=3,admissible=True,reason='ADMITTED') for action in ['READ_POS','READ_VOLT','READ_CONFIG','VERIFY_CTRL']}))
unknown=deepcopy(valid_view);unknown['view_schema']='aegisdc-e14-public-v99'
missing=deepcopy(valid_view);del missing['context']['acquisition_plans']
for id,view in [('V01-unknown-version',unknown),('V02-missing-v2-plans',missing)]:
    for method in ['M0','B1']:
        UNITS.append(dict(id=id+'-'+method,kind='invalid_view',refs=[id],input=dict(view=view,method=method),expected_error='ValueError',steps=[]))

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or socket.gethostname().split('.')[0]=='mu01':raise SystemExit('Slurm allocation required')
    a.output.mkdir(parents=True,exist_ok=False)
    package=dict(schema='aegisdc-read-verify-admission-frozen-v1',classification='FINITE_INTERFACE_REGRESSION_NOT_RESEARCH',model_calls_at_authoring=0,units=UNITS,pairs=PAIRS)
    data=(json.dumps(package,ensure_ascii=False,indent=2)+'\n').encode();(a.output/'cases.json').write_bytes(data)
    report=dict(units=len(UNITS),pairs=len(PAIRS),sha256=hashlib.sha256(data).hexdigest(),coverage={u['id']:u['refs'] for u in UNITS},model_calls_at_authoring=0)
    (a.output/'coverage.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='coverage'}))

if __name__=='__main__':main()
