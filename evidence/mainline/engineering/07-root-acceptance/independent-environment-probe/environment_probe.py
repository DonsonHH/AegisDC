"""Independent read-only ticket-07 Spec review probes; engineering only."""
import argparse
from copy import deepcopy
from decimal import Decimal, localcontext
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
base=load_scenario(repo/'configs/full-facility-mainline-environment-v4.json')
request={'id':'at-floor-crossing','time_s':0,'worker_id':'worker_cooling',
         'work_interface_id':'inspect_equipment_environment','target_id':'room',
         'source_note':'Independent Spec review threshold probe, not research.'}
cases=[]
for inlet in [.1,.17,.23,.31,.7,1.3]:
    for drain in [0,.031,.07]:
        for threshold in [.1,.37,.7]:
            if inlet<=drain:
                continue
            for step in [1,.37]:
                crossing=threshold/(inlet-drain)
                scenario=deepcopy(base)
                changes={'floor_water_inflow':inlet,'drainage_mass_flow':drain,
                         'access_block_mass':threshold}
                for parameter in scenario['parameters']:
                    if parameter['id'] in changes:
                        parameter['value']=changes[parameter['id']]
                for entity in scenario['entities']:
                    if entity['id'] in {'worker_cooling','tool_flow_meter'}:
                        entity['location_id']='loc_it'
                result=simulate_scenario(scenario,duration_s=crossing+.25,step_s=step,
                                         work_requests=[request])
                record=result['work_records'][0]
                actual=record.get('finished_at_s')
                assert record['status']=='aborted' and actual is not None
                assert abs(actual-crossing)<1e-9
                cases.append({'overrides':changes,'maximum_step_s':step,
                              'expected_crossing_s':crossing,'observed_abort_s':actual,
                              'status':record['status']})

changes={'internal_hot_mass':1000,'minimum_internal_hot_mass':900,
    'internal_hot_leak_mass_flow':2,'drainage_mass_flow':1,'floor_water_inflow':2,
    'initial_floor_water_mass':10,'water_specific_heat':4000,
    'room_ambient_temperature':300,'initial_hot_temperature':320,
    'initial_cold_temperature':310,'pump_pressure_rise':0,'internal_pump_pressure_rise':0,
    'compute_demand_power':0,'network_demand_power':0,'storage_demand_power':0,
    'controller_power':0,'room_aux_power':0,'solid_coolant_conductance':0,
    'solid_air_conductance':0,'room_conductance':0,'room_temperature':300}
scenario=deepcopy(base)
for parameter in scenario['parameters']:
    if parameter['id'] in changes:
        parameter['value']=changes[parameter['id']]
result=simulate_scenario(scenario,duration_s=2)
with localcontext() as context:
    context.prec=70
    temperature=Decimal(310)-Decimal(10)*(Decimal(10)/Decimal(16))**(Decimal(4)/Decimal(3))
    energy=Decimal(16)*Decimal(4000)*temperature
    drain=Decimal(12000000)+Decimal(9920000)-energy
    exact={'floor_temperature_K':str(temperature),'floor_energy_J':str(energy),
           'drained_energy_J':str(drain)}
    expected={'floor_mass_kg':16,'floor_temperature_K':float(temperature),
              'floor_energy_J':float(energy),'drained_energy_J':float(drain),
              'hot_mass_kg':996,'hot_temperature_K':320,'external_nuisance_mass_kg':4,
              'hot_leaked_mass_kg':4,'hot_leak_energy_J':5120000,
              'external_nuisance_energy_J':4800000}
final=result['trace'][-1]['domains']
summary=result['summary']
actual={'floor_mass_kg':final['space_access']['floor_water_mass_kg'],
    'floor_temperature_K':final['space_access']['floor_water_temperature_K'],
    'floor_energy_J':final['space_access']['floor_water_sensible_energy_J'],
    'drained_energy_J':summary['floor_drain_energy_J'],
    'hot_mass_kg':final['facility_cooling']['hot_mass_kg'],
    'hot_temperature_K':final['facility_cooling']['hot_temperature_K'],
    'external_nuisance_mass_kg':summary['floor_water_inlet_mass_kg'],
    'hot_leaked_mass_kg':summary['internal_hot_leaked_mass_kg'],
    'hot_leak_energy_J':summary['internal_hot_leak_energy_J'],
    'external_nuisance_energy_J':summary['floor_inlet_energy_J']}
assert all(abs(actual[key]-value)<=1e-5 for key,value in expected.items())

records=repo/'evidence/mainline/engineering/07-environment'
run_count=artifact_count=0
for path in list((records/'fixtures-5ca3c3a0').rglob('run.json'))+list((records/'cli-5ca3c3a0').rglob('run.json')):
    manifest=json.loads(path.read_text(encoding='utf-8'))
    assert manifest['code_identity']['git_commit']=='5ca3c3a03d05802458cef1bdd10e66928d75bc1b'
    assert manifest['code_identity']['implementation_has_changes'] is False
    run_count+=1
    for name,entry in manifest['artifacts'].items():
        content=(path.parent/name).read_bytes()
        assert sha256(content).hexdigest()==entry['sha256']
        assert (len(content.splitlines()) if name.endswith('.jsonl') else 1)==entry['records']
        artifact_count+=1
receipt=json.loads((records/'receipt-5ca3c3a0.json').read_text(encoding='utf-8'))
for name,entry in receipt['frozen_inputs'].items():
    assert sha256((repo/name).read_bytes()).hexdigest()==entry['sha256']
report={'schema':'aegisdc-ticket07-independent-spec-review-probe-v1',
    'classification':'FINITE_ENGINEERING_SPEC_REVIEW_NOT_RESEARCH',
    'candidate_source_commit':'5ca3c3a03d05802458cef1bdd10e66928d75bc1b',
    'observed_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    'script_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
    'source_sha256':{str(name):sha256((repo/name).read_bytes()).hexdigest()
        for name in ('src/aegis_dc/plant.py','src/aegis_dc/environment.py',
                     'configs/full-facility-mainline-environment-v4.json')},
    'access_threshold_cases':cases,'access_threshold_case_count':len(cases),
    'mixed_water_case':{'overrides':changes,'duration_s':2,
        'independent_basis':'Constant-temperature hot withdrawal plus the analytic well-mixed tank solution: M1=16, Tin=310, T1=310-10*(10/16)^(4/3). Decimal 70 digits, no AegisDC outputs used for expected values.',
        'decimal_reference':exact,'expected':expected,'observed':actual,
        'max_energy_residual_J':summary['max_energy_residual_J'],
        'max_mass_residual_kg':summary['max_mass_residual_kg']},
    'fresh_reads':{'saved_runs':run_count,'artifact_hashes_and_counts':artifact_count,
                   'frozen_input_hashes':len(receipt['frozen_inputs']),'status':'PASS'}}
with args.output.open('x',encoding='utf-8') as stream:
    stream.write(json.dumps(report,indent=2,allow_nan=False)+'\n')
print(json.dumps({'output':str(args.output.resolve()),'sha256':sha256(args.output.read_bytes()).hexdigest(),
                 'access_cases':len(cases),'saved_runs':run_count,'artifact_hashes_and_counts':artifact_count}))
