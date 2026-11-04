"""Read-only independent service-accounting review probe, ticket 08."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

parser=argparse.ArgumentParser()
parser.add_argument('--repo',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
repo=args.repo.resolve()
sys.path.insert(0,str(repo/'src'))
from aegis_dc.plant import simulate_scenario
from aegis_dc.scenario import load_scenario
base=repo/'evidence/mainline/engineering/08-service/runs-60f21f25-01'
receipt=json.loads((base/'receipt.json').read_text(encoding='utf-8'))
for name,digest in receipt['artifacts'].items():
    assert sha256((base/name).read_bytes()).hexdigest()==digest,name
runs=artifacts=0
for path in base.rglob('run.json'):
    manifest=json.loads(path.read_text(encoding='utf-8'))
    runs+=1
    for name,entry in manifest['artifacts'].items():
        content=(path.parent/name).read_bytes()
        assert sha256(content).hexdigest()==entry['sha256'],str(path.parent/name)
        assert (len(content.splitlines()) if name.endswith('.jsonl') else 1)==entry['records']
        artifacts+=1
events=[]
def event(t,parameter,value):
    events.append({'time_s':t,'parameter_id':parameter,'value':value,
                   'source_note':'Independent Spec review engineering accounting probe; not research.'})
event(0,'service_demand',.4);event(0,'network_service_capacity',.1)
event(.3,'service_demand',1.5)
event(.7,'network_service_capacity',.8);event(.7,'storage_service_capacity',.25)
event(1.2,'service_demand',0)
event(1.8,'service_demand',1);event(1.8,'network_service_capacity',1)
event(1.8,'storage_service_capacity',1);event(1.8,'compute_demand_power',0)
event(2.1,'compute_demand_power',2000000)
# Literal six-interval arithmetic, calculated independently of the plant:
# demand = .4*.3 + 1.5*.4 + 1.5*.5 + 0*.6 + 1*.3 + 1*.3 = 2.07
# delivery = .1*.3 + .1*.4 + .25*.5 + 0*.6 + 0*.3 + 1*.3 = .495
# deficit seconds = .75*.3 + (1.4/1.5)*.4 + (1.25/1.5)*.5 + 0 + 1*.3 + 0 = 1.315
expected={'demand_service_unit_s':2.07,'delivered_service_unit_s':.495,'service_deficit_time_s':1.315}
results=[]
for name in ('full-facility-mainline-v2.json','full-facility-mainline-water-v3.json'):
    result=simulate_scenario(load_scenario(repo/'configs'/name),duration_s=2.4,step_s=.37,boundary_events=events)
    observed={key:result['summary'][key] for key in expected}
    assert all(abs(observed[key]-value)<1e-12 for key,value in expected.items())
    results.append({'model':name,'observed':observed})
report={'classification':'READ_ONLY_ENGINEERING_SPEC_REVIEW_NOT_RESEARCH',
        'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        'script_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
        'duration_s':2.4,'maximum_step_s':.37,'boundary_events':events,
        'independent_expected':expected,'outcomes':results,
        'fresh_read':{'runs':runs,'artifacts_checked_for_sha_and_records':artifacts,
                      'receipt_hashes_checked':len(receipt['artifacts']),'status':'PASS'}}
with args.output.open('x',encoding='utf-8') as stream:
    stream.write(json.dumps(report,indent=2,allow_nan=False)+'\n')
print(json.dumps({'output':str(args.output.resolve()),'sha256':sha256(args.output.read_bytes()).hexdigest()}))
