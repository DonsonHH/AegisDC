"""Independent compound sampling/latching probe for ticket-09 Spec review.

This is a finite engineering diagnostic, not a registered effect experiment.
The expected mode sequence and accounts are literal prior reasoning, independent
of the implementation's state-update formula.
"""
import argparse
from hashlib import sha256
import json
import os
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
config=repo/'configs/full-facility-mainline-control-v5.json'
scenario=load_scenario(config)
changes={'protection_temperature':315,'protection_reset_temperature':300,
         'control_sample_time':.7,'local_temperature_bias':20,'ups_energy':0,
         'diesel_initial_fuel_energy':0}
for parameter in scenario['parameters']:
    if parameter['id'] in changes:
        parameter['value']=changes[parameter['id']]
        parameter.update(basis='synthetic_assumption',
            source_note='Independent Spec review compound clock/latch engineering override; not a field setting or registered effect trial.')
rows=[(.3,'local_temperature_bias',5),(.4,'supervisory_link_available',0),
      (.8,'grid_capacity',0),(1.6,'grid_capacity',10000000),
      (1.9,'local_internal_flow_sensor_valid',0),(2.2,'local_internal_flow_sensor_valid',1),
      (2.4,'supervisory_link_available',1),(3.1,'local_temperature_bias',-10)]
events=[{'time_s':time,'parameter_id':name,'value':value,
         'source_note':'Independent Spec review compound control clock/latch engineering event; not research.'}
        for time,name,value in rows]
result=simulate_scenario(scenario,duration_s=4.1,step_s=.37,boundary_events=events)
samples=[]
for row in result['trace']:
    control=row['domains']['control_monitoring']
    if abs(control['local_measurement']['sampled_at_s']-row['time_s'])<1e-12:
        samples.append({'time_s':row['time_s'],'mode':control['mode'],
            'protection_latched':control['protection_latched'],
            'supervisory_mode':control['supervisory_mode'],
            'true_refrigerant_temperature_K':row['domains']['equipment_environment']['refrigerant']['temperature_K'],
            'reported_temperature_K':control['local_measurement']['temperature_K'],
            'reported_flow_m3_s':control['local_measurement']['internal_volume_flow_m3_s'],
            'local_measurement':control['local_measurement']})
expected_modes=['protected','protected','unpowered_fail_safe',
                'sensor_invalid_fail_safe','protected','normal']
assert [row['mode'] for row in samples]==expected_modes
assert all(row['protection_latched'] for row in samples[:-1])
assert samples[-1]['protection_latched'] is False
assert abs(result['summary']['service_deficit_time_s']-3.5)<1e-10
assert abs(result['summary']['delivered_service_unit_s']-.6)<1e-10
assert result['research_trials']==result['model_calls']==result['training_calls']==0
verify=subprocess.run([sys.executable,'-X','utf8',
    'evidence/mainline/engineering/09-control/verify_saved.py'],cwd=repo,
    env=dict(os.environ,PYTHONPATH=str(repo/'src')),check=True,
    capture_output=True,text=True,encoding='utf-8')
readback=json.loads(verify.stdout)
assert readback['status']=='PASS'
report={'schema':'aegisdc-ticket09-independent-spec-review-v1',
    'classification':'FINITE_ENGINEERING_REVIEW_DIAGNOSTIC_NOT_RESEARCH',
    'candidate_commit':'1ed6669221fd32a7ecfcc09d20292170505e89a8',
    'observed_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    'script_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
    'source_sha256':{name:sha256((repo/name).read_bytes()).hexdigest() for name in
       ('src/aegis_dc/local_control.py','src/aegis_dc/plant.py','src/aegis_dc/scenario.py',
        'src/aegis_dc/runtime_contract.py','configs/materials/reference-r134a-saturation.json')},
    'base_config':str(config),'base_config_sha256':sha256(config.read_bytes()).hexdigest(),
    'parameter_overrides':changes,'boundary_events':events,'duration_s':4.1,'maximum_step_s':.37,
    'independent_expected':{'mode_sequence':expected_modes,
        'nominal_sample_times_s':[0,.7,1.4,2.1,2.8,3.5],
        'service_deficit_time_s':3.5,'delivered_service_unit_s':.6,
        'basis':'Initial high report trips. Held latch survives in-band report, supervisory loss, power cycle, invalid sensor and supervisory return. Only the new safe report at 3.5 s meets reset gates; delivery lasts the remaining .6 s.'},
    'observed_samples':samples,
    'observed_summary':{key:result['summary'][key] for key in
        ('service_deficit_time_s','demand_service_unit_s','delivered_service_unit_s',
         'max_energy_residual_J','max_mass_residual_kg')},
    'sealed_originals_fresh_read':readback}
with args.output.open('x',encoding='utf-8') as stream:
    stream.write(json.dumps(report,indent=2,allow_nan=False)+'\n')
print(json.dumps({'output':str(args.output.resolve()),'sha256':sha256(args.output.read_bytes()).hexdigest()}))
