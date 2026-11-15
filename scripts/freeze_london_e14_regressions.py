"""Pre-execution literals for review-identified implementation guards.

Separate engineering regressions; never replace the 105 accepted qualification
units. Uses only the input author's C0/serialization helpers, no model code.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import socket
from freeze_london_e14_cases import C0, req, step, check, advance, request, rec, public_base


units=[];pairs=[]
def add(id,steps,changes=None):
    c=deepcopy(C0);c.update(changes or {})
    units.append(dict(id=id,refs=['existing E1-E4 rules; implementation review regression'],kind='run',input=c,steps=steps))
for label,plan in [('success','SUCCESS'),('failure','FAIL')]:
    add('G01-'+label,[request('FIX_CTRL'),advance(4),step('save_view',label='before_receipt'),step('view_select',dict(terminal_failure=False,phase='EXITING',pending=True),select=['terminal_failure','phase','pending'])],dict(commit=plan))
pairs.append(dict(id='G01-no-early-commit-outcome',units=['G01-success','G01-failure'],paths=['saved.before_receipt']))
for value in (0,7):
    add('G02-budget-'+str(value),[request('FIX_CTRL',status='BUDGET_UNAVAILABLE'),advance(2),check(spent=0,epoch=0,phase='NONE')],dict(budget=value))
add('G03-queued-revoked',[request('READ_POS'),advance(5),check(spent=0,observation_count=0,started_actions=[],read_status='ABORTED_READ')],dict(calendar=[[0,3]],revoke=[1,'READ_ROLE']))
add('G04-late-verify',[request('FIX_CTRL'),advance(7),request('VERIFY_CTRL',2,execution_id='ex-1',target_config_epoch=1),advance(11),check(epoch=1,verification_result='ABORTED',phase='TERMINAL',current_actions=[],spent=6,observation_count=1)],dict(publish=3))
add('G05-aborted-verify',[request('FIX_CTRL'),advance(6),request('VERIFY_CTRL',2,execution_id='ex-1',target_config_epoch=1),advance(9),check(epoch=1,verification_result='ABORTED',phase='TERMINAL',spent=8,observation_count=0)],dict(tF=7))
for label,plan in [('success','SUCCESS'),('failure','FAIL')]:
    add('G06-'+label,[request('FIX_CTRL'),advance(6),step('save_view',label='after_exit_before_receipt'),step('view_select',dict(terminal_failure=False,pending=True,phase='APPROVED'),select=['terminal_failure','pending','phase'])],dict(publish=5,commit=plan))
pairs.append(dict(id='G06-late-receipt-isolation',units=['G06-success','G06-failure'],paths=['saved.after_exit_before_receipt']))
for kind in ('target','receiver','epoch'):
    v=public_base();v['records']=[rec('READ_POS',0,1,1,2,13),rec('READ_VOLT',1,2,3,4,15),rec('READ_CONFIG','LEGACY_LINE',3,5,6,17)]
    if kind=='target':v['records'][-1]['target']='ctrl-other'
    if kind=='receiver':v['records'][-1]['receiver_role']='GUEST'
    if kind=='epoch':v['known_epoch']=1
    for method in ('M0','B1'):
        units.append(dict(id='G07-'+kind+'-'+method,refs=['existing E1 applicability rules'],kind='decision',input=dict(view=deepcopy(v),method=method,expected=dict(action='READ_CONFIG',mode=None,reason='READ_CONFIG')),steps=[]))

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or socket.gethostname().split('.')[0]=='mu01':raise SystemExit('Slurm allocation required')
    a.output.mkdir(parents=True,exist_ok=False)
    value=dict(schema='aegisdc-e14-review-regression-literals',classification='ENGINEERING_REGRESSION_NOT_RESEARCH_NOT_REPLACEMENT_FOR_105',model_calls_at_authoring=0,units=units,pairs=pairs)
    data=(json.dumps(value,indent=2)+'\n').encode();(a.output/'regressions.json').write_bytes(data)
    print(json.dumps(dict(units=len(units),pairs=len(pairs),sha256=hashlib.sha256(data).hexdigest(),model_calls_at_authoring=0)))

if __name__=='__main__':main()
