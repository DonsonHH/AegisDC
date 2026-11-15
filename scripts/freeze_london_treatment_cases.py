"""Literal engineering expectations and complete *unexecuted* dev inputs.

No model, runner or scorer imports. Expected values are hand-derived from the
accepted timelines and the runner contract, not from implementation outputs.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import socket
from freeze_london_e14_cases import C0

READ3=['READ_POS','READ_VOLT','READ_CONFIG']
I_FULL=READ3+['FIX_CTRL','VERIFY_CTRL'];D_FULL=['FIX_CTRL','VERIFY_CTRL']

def expected(actions,times,stop,time,spent,loss,stage,commit='NOT_ATTEMPTED',verify='NOT_REQUESTED',epoch=0,queue=0,approval=0,unstarted=0,hard=True,published=None,visible_reads=None,approved=False,prepared=False):
    reads=sum(a.startswith('READ_') for a in actions)
    verification_published=published if published is not None else verify in ('PASS','FAIL','INCONCLUSIVE')
    return {'requested_actions':actions,'request_times':times,'stop.reason':stop,'stop.time':time,
            'policy_times':list(range(time if stop=='ENV_PRE_CUTOFF' else time+1)),
            'reached.stage':stage,'reached.fix_requested':'FIX_CTRL' in actions,
            'reached.approved':approved,'reached.preparation_started':prepared,
            'reached.commit_result':commit,'reached.commit_attempted':commit in ('SUCCESS','FAIL'),
            'reached.verification_requested':'VERIFY_CTRL' in actions,
            'reached.verification_result':verify,
            'reached.verification_published':verification_published,
            'reached.verification_parent_valid':True if verification_published else None,
            'reached.read_results_published':reads,
            'reached.read_records_visible_to_policy':reads if visible_reads is None else visible_reads,
            'score.trace_status':'COMPLETE','score.L':loss,'score.U':loss,
            'score.person_seconds':spent,'score.tool_seconds':spent,
            'score.resource_queue_seconds':queue,'score.approval_wait_seconds':approval,
            'score.unstarted_observed_wait_seconds':unstarted,'score.hard_constraints_ok':hard,
            'final_audit.epoch':epoch}

def full_i(loss=0,verify='PASS',stop='NO_ACTION_CURRENT_SCOPE',stage='VERIFIED'):
    return expected(I_FULL,[0,2,4,6,12],stop,14,9,loss,stage,'SUCCESS',verify,1,approval=1,approved=True,prepared=True)
def full_d(loss=0,verify='PASS',stop='NO_ACTION_CURRENT_SCOPE',stage='VERIFIED'):
    return expected(D_FULL,[0,6],stop,8,6,loss,stage,'SUCCESS',verify,1,approval=1,approved=True,prepared=True)
def background(loss=0):return expected([],[],'NO_NEW_ACTIONS',0,0,loss,'BACKGROUND_ONLY')

UNITS=[];PAIRS=[]
def add(id,changes,I,D,P,order=None):
    c=deepcopy(C0);c.update(changes)
    UNITS.append(dict(id=id,kind='triplet',input=dict(common=c,order=order or ['I','D','P']),expected=dict(I=I,D=D,P=P)))

add('E01-no-fault-full-chain',dict(tF=None,tR=None),full_i(),full_d(),background())
late_i=expected(READ3+['FIX_CTRL'],[0,2,4,6],'ENV_PRE_CUTOFF',10,8,5,'NOT_IMPLEMENTED',approval=1,approved=True,prepared=True)
add('E02-c0-cutoff',{},late_i,full_d(),background(5))
add('E03-short-circuit',dict(cB=1),expected(['READ_POS'],[0],'NO_ACTION_CURRENT_SCOPE',2,1,0,'INSPECTION_STOP'),full_d(),background())
add('E04-information-insufficient',dict(tF=None,tR=None,read_modes=dict(C0['read_modes'],READ_POS='INCONCLUSIVE')),expected(READ3,[0,2,4],'INSUFFICIENT_INFORMATION',6,3,0,'INSPECTION_STOP'),full_d(),background())
add('E05-approval-denied',dict(tF=None,tR=None,approval='DENY'),expected(READ3+['FIX_CTRL'],[0,2,4,6],'STOP_UNRESOLVED',8,3,0,'APPROVAL_DENIED',approval=1,unstarted=2),expected(['FIX_CTRL'],[0],'STOP_UNRESOLVED',2,0,0,'APPROVAL_DENIED',approval=1,unstarted=2),background())
add('E06-commit-failure-reached',dict(tF=None,tR=None,commit='FAIL'),expected(READ3+['FIX_CTRL'],[0,2,4,6],'STOP_UNRESOLVED',11,8,0,'COMMIT_FAILED',commit='FAIL',approval=1,approved=True,prepared=True),expected(['FIX_CTRL'],[0],'STOP_UNRESOLVED',5,5,0,'COMMIT_FAILED',commit='FAIL',approval=1,approved=True,prepared=True),background())
add('E07-verification-failure-reached',dict(tF=None,tR=None,verification='FAIL'),full_i(verify='FAIL',stop='STOP_UNRESOLVED',stage='VERIFICATION_FAILED'),full_d(verify='FAIL',stop='STOP_UNRESOLVED',stage='VERIFICATION_FAILED'),background())
add('E08-direct-permission',dict(tF=None,tR=None,permissions=dict(C0['permissions'],direct='DENY')),full_i(),expected([],[],'INFEASIBLE',0,0,0,'NO_ACTION'),background())
add('E09-queue-full-chain',dict(tF=None,tR=None,calendar=[[0,3]]),expected(I_FULL,[0,5,7,9,15],'NO_ACTION_CURRENT_SCOPE',17,9,0,'VERIFIED','SUCCESS','PASS',1,queue=3,approval=1,approved=True,prepared=True),expected(D_FULL,[0,8],'NO_ACTION_CURRENT_SCOPE',10,6,0,'VERIFIED','SUCCESS','PASS',1,queue=2,approval=1,approved=True,prepared=True),background())
add('E10-budget-insufficient',dict(tF=None,tR=None,budget=4),expected(READ3[:2],[0,2],'INSUFFICIENT_INFORMATION',4,2,0,'INSPECTION_STOP'),expected([],[],'INFEASIBLE',0,0,0,'NO_ACTION'),background())
add('E11-harmful-isolation',dict(tF=None,tR=None,work_mode='LOAD_ISOLATED'),full_i(7),full_d(7),background())
add('E12-incomplete-exit',dict(tF=None,tR=None,work_mode='LOAD_ISOLATED',exit_result='FAIL'),expected(READ3+['FIX_CTRL'],[0,2,4,6],'ENV_PRE_CUTOFF',20,16,13,'EXIT_INCOMPLETE','SUCCESS',epoch=1,approval=1,hard=False,approved=True,prepared=True),expected(['FIX_CTRL'],[0],'ENV_PRE_CUTOFF',20,19,19,'EXIT_INCOMPLETE','SUCCESS',epoch=1,approval=1,hard=False,approved=True,prepared=True),background())
add('E13-order-isolation',dict(tF=None,tR=None),full_i(),full_d(),background(),order=['P','D','I'])
add('E14-private-half-second-cutoff',dict(tF='3/2'),expected(['READ_POS'],[0],'ENV_PRE_CUTOFF',2,1,'27/2','INSPECTION_STOP',visible_reads=0),expected(['FIX_CTRL'],[0],'ENV_PRE_CUTOFF',2,'5/2','27/2','NOT_IMPLEMENTED',approval=1,approved=True,prepared=True),background('27/2'))
add('E15-queue-cutoff-before-approval',dict(calendar=[[0,3]]),expected(READ3+['FIX_CTRL'],[0,5,7,9],'ENV_PRE_CUTOFF',10,3,5,'NOT_IMPLEMENTED',queue=3,approval=None,unstarted=1),expected(D_FULL,[0,8],'ENV_PRE_CUTOFF',10,6,0,'VERIFY_ABORTED','SUCCESS','ABORTED',1,queue=2,approval=1,published=True,approved=True,prepared=True),background(5))
add('E16-backup-unavailable',dict(ready=False),deepcopy(late_i),full_d(5),background(5))
PAIRS += [dict(id='execution-order-independent',units=['E01-no-fault-full-chain','E13-order-isolation'],paths=[f'arms.{arm}.{part}' for arm in ['I','D','P'] for part in ['public_trace','score']]),
          dict(id='unobserved-backup-does-not-inform-policy',units=['E02-c0-cutoff','E16-backup-unavailable'],paths=[f'arms.{arm}.public_trace' for arm in ['I','D','P']]),
          dict(id='position-hidden-before-arrival',units=['E01-no-fault-full-chain','E03-short-circuit'],paths=['arms.I.public_trace'],prefix=2)]

def score_fixture(time,reported_loss):
    c=deepcopy(C0);c.update(tF=None,tR=None)
    audit=dict(time=time,original_input=c,segments=[dict(start=0,end=time,source='A',power=1,demand=1,service=1,device='RUNNING',isolated=False,occupied=False,work_action=None,work_stage=None)],E=3,L=reported_loss,U=0,load_energy=time,ups_energy=0,spent=0,budgets={name:dict(limit=20,spent=0,reserved=0,available=20) for name in ['person','tool']},resource_overrun=False,internal_approval=None,observations=[],receipts=[],commit_result='NOT_ATTEMPTED',verification_result='NOT_REQUESTED',epoch=0,phase='NONE',operations=[],started_actions=[],recoveries=[])
    run=dict(arm='P',requests=[],public_trace=[],stop=dict(reason='NO_NEW_ACTIONS',time=0),errors=[])
    return dict(audit=audit,run=run,isolation_ok=True)
UNITS.append(dict(id='S01-partial-window-not-full-score',kind='score',input=score_fixture(1,0),expected={'trace_status':'INCOMPLETE_TRACE','L':None,'U':None,'hard_constraints_ok':False}))
UNITS.append(dict(id='S02-independent-scoring-not-model-total',kind='score',input=score_fixture(20,5),expected={'trace_status':'COMPLETE','L':0,'U':0,'model_report_agrees':False,'hard_constraints_ok':False}))

# Complete proposed development inputs, no expected outcomes and no execution.
DEV=[]
def dev(id,changes):
    c=deepcopy(C0);c.update(deepcopy(changes));DEV.append(dict(condition_id=id,classification='DISCLOSED_DEVELOPMENT',common=c))
dev('C01',{});dev('C02',dict(cB=1));dev('C03',dict(family='REVISED_LOCAL'))
dev('C04a',dict(ready=False));dev('C04b',dict(permit=False))
dev('C05a',dict(approval='DENY'));dev('C05b',dict(commit='FAIL'));dev('C05c',dict(guard='BLOCK'))
dev('C06a',dict(read_modes=dict(C0['read_modes'],READ_POS='INCONCLUSIVE')));dev('C06b',dict(verification='FAIL'));dev('C06c',dict(verification='INCONCLUSIVE'))
dev('C07a',dict(budget=4));dev('C07b',dict(budget=8));dev('C08a',dict(calendar=[[0,3]]));dev('C08b',dict(window=[0,9]))
dev('C09a',dict(tF=None,tR=None,work_mode='LOAD_ISOLATED'));dev('C09b',dict(tF=None,tR=None,work_mode='LOAD_ISOLATED',exit_result='FAIL'))
dev('C10a',dict(tR=10));dev('C10b',dict(tR=None))

def save(path,data):
    b=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode();path.write_bytes(b);return hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or socket.gethostname().split('.')[0]=='mu01':raise SystemExit('Remote Slurm allocation required')
    a.output.mkdir(parents=True,exist_ok=False)
    eng=dict(schema='aegisdc-idp-engineering-v1',classification='ENGINEERING_ONLY',public_tick_seconds=1,model_calls_at_authoring=0,units=UNITS,pairs=PAIRS)
    h=save(a.output/'engineering-cases.json',eng)
    coverage={u['id']:(dict(kind='score',expected=u['expected']) if u['kind']=='score' else {arm:dict(stage=e['reached.stage'],approved=e['reached.approved'],preparation_started=e['reached.preparation_started'],commit_attempted=e['reached.commit_attempted'],verification_requested=e['reached.verification_requested'],verification_result=e['reached.verification_result']) for arm,e in u['expected'].items()}) for u in UNITS}
    save(a.output/'engineering-coverage.json',coverage)
    dh=save(a.output/'development-inputs.json',dict(schema='aegisdc-r3-development-inputs-v1',status='REVIEW_FREEZE_NOT_EXECUTION',execution_authorized=False,confirmation=False,conditions=DEV,treatments=['I','D','P'],public_tick_seconds=1))
    result=dict(units=len(UNITS),triplets=16,arm_runs=48,score_fixtures=2,pairs=len(PAIRS),engineering_sha256=h,development_conditions=len(DEV),development_input_sha256=dh,model_calls_at_authoring=0,research_experiments=0,confirmation_results_accessed=False)
    save(a.output/'authoring.json',result);print(json.dumps(result))

if __name__=='__main__':main()
