"""Independent score/retention guards; no runner, model or scorer imports."""
import argparse
from copy import deepcopy
import hashlib,json,os,socket
from pathlib import Path
from freeze_london_treatment_cases import C0,score_fixture

UNITS=[]
x=score_fixture(20,0);a=x['audit'];a['original_input'].update(E0=0,vA=0,vB=0,ready=False);a.update(E=0,load_energy=0)
a['segments'][0].update(source=None,power=0,service=0,demand=0,device='OFF')
UNITS.append(dict(id='G01-frozen-demand-not-trace-demand',kind='score',input=x,expected={'trace_status':'COMPLETE','L':20,'U':20,'reported_demand_matches':False,'model_report_agrees':False,'hard_constraints_ok':False}))
x=score_fixture(20,20);a=x['audit'];a['original_input']['demand']=[[0,1],[10,0]];a['U']=20;a['segments'][0].update(service=0,device='BOOTING')
UNITS.append(dict(id='G02-demand-breakpoint-inside-segment',kind='score',input=x,expected={'trace_status':'COMPLETE','L':10,'U':10,'reported_demand_matches':False,'model_report_agrees':False,'hard_constraints_ok':False}))
for id,fault,status in [('G03-retain-failed-final-advance','advance_H','INCOMPLETE_TRACE'),('G04-retain-failed-final-audit','final_audit','UNSCORED_AFTER_AUDIT_ERROR')]:
    c=deepcopy(C0);c.update(tF=None,tR=None)
    expected={'arms.I.requested_actions':['READ_POS','READ_VOLT','READ_CONFIG','FIX_CTRL','VERIFY_CTRL'],'arms.I.request_times':[0,2,4,6,12],'arms.I.stop.reason':'NO_ACTION_CURRENT_SCOPE','arms.I.stop.time':14,'arms.I.score.trace_status':status,'arms.I.score.L':None,'arms.I.score.U':None,'arms.I.score.hard_constraints_ok':False,'arms.D.score.trace_status':'COMPLETE','arms.D.score.L':0,'arms.P.score.trace_status':'COMPLETE','arms.P.score.L':0}
    if fault=='advance_H':expected['arms.I.final_audit.time']=14
    else:expected['arms.I.final_audit']=None
    UNITS.append(dict(id=id,kind='runner_fault',input=dict(common=c,order=['I','D','P'],fault=fault),expected=expected,expected_error_arm='I'))

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or socket.gethostname().split('.')[0]=='mu01':raise SystemExit('Slurm required')
    a.output.mkdir(parents=True,exist_ok=False)
    data=dict(schema='aegisdc-idp-engineering-guards-v1',classification='ENGINEERING_ONLY',public_tick_seconds=1,units=UNITS,pairs=[],model_calls_at_authoring=0)
    b=(json.dumps(data,indent=2)+'\n').encode();(a.output/'guards.json').write_bytes(b)
    print(json.dumps(dict(units=4,score_fixtures=2,injected_runner_failures=2,sha256=hashlib.sha256(b).hexdigest(),model_calls_at_authoring=0)))

if __name__=='__main__':main()
