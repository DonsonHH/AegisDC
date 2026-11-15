"""Additional literal guards for existing role and explicit-version semantics."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import socket
from freeze_london_admission_cases import C0, direct, move, cycle, audit, op, valid_view
from freeze_london_e14_cases import req

units=[];pairs=[]
for id,read,verify in [('H01-read-role-required','DENY','ALLOW'),('H02-verify-role-required','ALLOW','DENY')]:
    c=deepcopy(C0);c.update(tF=None,tR=None);c['permissions'].update(read=read,verify=verify)
    steps=[direct(),move(6),cycle('verify','INSUFFICIENT_INFORMATION',2,reply=None,plan=('VERIFY_CTRL',dict(admissible=False,reason='ACCESS_DENIED'))),
           op('request',{'status':'ACCESS_DENIED'},payload=req('VERIFY_CTRL',2,execution_id='ex-1',target_config_epoch=1)),
           audit(spent=5,verification_result='NOT_REQUESTED',started_actions=['FIX_CTRL'],observation_count=0)]
    for method in ['M0','B1']:units.append(dict(id=id+'-'+method,kind='flow',refs=[id,'existing read AND verify gate'],input=dict(config=deepcopy(c),method=method),steps=deepcopy(steps)))
    pairs.append(dict(id=id+'-method-consistency',units=[id+'-M0',id+'-B1'],paths=['cycles.verify.decision.action','cycles.verify.payload','cycles.verify.reply']))
view=deepcopy(valid_view);del view['view_schema'];del view['context']['acquisition_plans']
for method in ['M0','B1']:units.append(dict(id='H03-no-implicit-downgrade-'+method,kind='invalid_view',refs=['explicit legacy opt-in required'],input=dict(view=deepcopy(view),method=method),expected_error='ValueError',steps=[]))

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or socket.gethostname().split('.')[0]=='mu01':raise SystemExit('Slurm required')
    a.output.mkdir(parents=True,exist_ok=False)
    body=dict(schema='aegisdc-admission-role-version-guards-v1',classification='ENGINEERING_GUARD_NOT_RESEARCH',model_calls_at_authoring=0,units=units,pairs=pairs)
    b=(json.dumps(body,indent=2)+'\n').encode();(a.output/'guards.json').write_bytes(b)
    print(json.dumps(dict(units=len(units),pairs=len(pairs),sha256=hashlib.sha256(b).hexdigest(),model_calls_at_authoring=0)))

if __name__=='__main__':main()
