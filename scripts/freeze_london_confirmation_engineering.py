"""Transcribe PUBLIC engineering inputs and independent literal expectations.

No model imports, candidate enumeration, selection seed or sealed material.
Only run authoring in a remote Slurm allocation before qualification outputs.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import socket

from freeze_london_e14_cases import C0
from freeze_london_treatment_cases import expected, full_i, full_d, background, READ3, I_FULL, D_FULL


def material():
    units = []
    def add(identifier, changes, i, d, p):
        common = deepcopy(C0)
        common.update(deepcopy(changes))
        units.append(dict(condition_id=identifier, common=common, expected=dict(I=i, D=d, P=p)))
    short = expected(['READ_POS'], [0], 'NO_ACTION_CURRENT_SCOPE', 2, 1, 0, 'INSPECTION_STOP')
    add('X01', dict(tF=None,tR=None,cB=1), short, full_d(), background())
    add('X02', dict(tF=None,tR=None,cB=1,work_mode='LOAD_ISOLATED'), short, full_d(7), background())
    add('X03', dict(tF=None,tR=None,guard='BLOCK'),
        expected(READ3+['FIX_CTRL'],[0,2,4,6],'STOP_UNRESOLVED',11,8,0,'NOT_IMPLEMENTED',approval=1,approved=True,prepared=True),
        expected(['FIX_CTRL'],[0],'STOP_UNRESOLVED',5,5,0,'NOT_IMPLEMENTED',approval=1,approved=True,prepared=True), background())
    add('X04',dict(tF=None,tR=None,verification='INCONCLUSIVE'),
        full_i(verify='INCONCLUSIVE',stop='STOP_UNRESOLVED',stage='VERIFY_INCONCLUSIVE'),
        full_d(verify='INCONCLUSIVE',stop='STOP_UNRESOLVED',stage='VERIFY_INCONCLUSIVE'),background())
    add('X05',dict(tF=16,tR=None),full_i(),full_d(),background(1))
    add('X06',dict(tF=16,tR=None,permit=False),full_i(1),full_d(1),background(1))
    add('X07',dict(tF=None,tR=None,read_work=2,verify_work=2),
        expected(I_FULL,[0,3,6,9,15],'NO_ACTION_CURRENT_SCOPE',18,13,0,'VERIFIED','SUCCESS','PASS',1,approval=1,approved=True,prepared=True),
        expected(D_FULL,[0,6],'NO_ACTION_CURRENT_SCOPE',9,7,0,'VERIFIED','SUCCESS','PASS',1,approval=1,approved=True,prepared=True),background())
    add('X08',dict(tF=None,tR=None,work_mode='LOAD_ISOLATED',exit_result='FAIL'),
        expected(READ3+['FIX_CTRL'],[0,2,4,6],'ENV_PRE_CUTOFF',20,16,13,'EXIT_INCOMPLETE','SUCCESS',epoch=1,approval=1,hard=False,approved=True,prepared=True),
        expected(['FIX_CTRL'],[0],'ENV_PRE_CUTOFF',20,19,19,'EXIT_INCOMPLETE','SUCCESS',epoch=1,approval=1,hard=False,approved=True,prepared=True),background())
    pairs=[dict(id='mode-hidden',units=['X01','X02'],paths=['arms.I.public_trace']),
           dict(id='permit-hidden',units=['X05','X06'],paths=[f'arms.{a}.public_trace' for a in ('I','D','P')])]
    inputs=dict(schema='aegisdc-confirmation-entry-engineering-v1',purpose='PUBLIC_ENGINEERING',conditions=[dict(condition_id=u['condition_id'],common=u['common']) for u in units])
    expectations=dict(classification='INDEPENDENT_LITERAL_EXPECTATIONS',model_calls_at_authoring=0,units=[dict(id=u['condition_id'],expected=u['expected']) for u in units],pairs=pairs)
    coverage={u['condition_id']:{a:{k:e[k] for k in ['reached.stage','reached.commit_attempted','reached.verification_requested','reached.verification_result','score.L','score.person_seconds','score.hard_constraints_ok']} for a,e in u['expected'].items()} for u in units}
    fixtures=dict(classification='PUBLIC_INTERFACE_FIXTURES_NO_MODEL',
        json_reject=['{"a":1,"a":2}','{"a":NaN}','{"a":Infinity}','{"a":1.0}'],
        purpose_reject=['CONFIRMATION','DISCLOSED_DEVELOPMENT','UNKNOWN'],
        equivalent=[{'field':'E0','left':3,'right':'6/2'}],
        invalid_changes=[{'H':True},{'H':'20'},{'ready':1},{'cB':False},{'unexpected':0}],
        different_changes=[{'E0':2},{'work_mode':'LOAD_ISOLATED'},{'permit':False}],
        source_faults=['manifest_sha','input_sha','core_sha','python_sha','output_path'],
        callback_cases=[{'id':'raises','expected_status':'STOPPED_ON_ERROR','callbacks':1,'suffix':'NOT_EXECUTED'},
                        {'id':'malformed','expected_status':'STOPPED_ON_ERROR','callbacks':1,'suffix':'NOT_EXECUTED'}],
        expected_engineering_conditions=8,expected_core_arm_runs=24,
        expected_noncompliant=['X08'],unknown_purpose_model_calls=0)
    return {'inputs.json':inputs,'expected.json':expectations,'coverage.json':coverage,'interface-fixtures.json':fixtures}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or socket.gethostname().split('.')[0]=='mu01':
        raise SystemExit('Remote allocation required')
    args.output.mkdir(parents=True,exist_ok=False)
    files={}
    for name,value in material().items():
        data=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
        (args.output/name).write_bytes(data)
        files[name]=dict(sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))
    receipt=dict(files=files,job_id=os.environ['SLURM_JOB_ID'],host=socket.gethostname(),model_calls=0,confirmation_material_generated=False)
    (args.output/'authoring.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt))


if __name__=='__main__':
    main()
