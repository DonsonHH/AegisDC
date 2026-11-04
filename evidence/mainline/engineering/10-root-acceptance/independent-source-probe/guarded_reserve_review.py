"""Source-guarded focused review and independent finite-UPS hand probe.

No full regression or registered research is run. Existing output directories
are refused. The earlier unsealed observation is deliberately not consumed.
"""
import argparse
from fractions import Fraction
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys

parser=argparse.ArgumentParser()
parser.add_argument('--repo',type=Path,required=True)
parser.add_argument('--freeze',required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
repo=args.repo.resolve()
args.output.mkdir(parents=True,exist_ok=False)

def git(*arguments):
    return subprocess.check_output(['git',*arguments],cwd=repo)

def snapshot():
    tracked=git('ls-tree','-r','--name-only',args.freeze).decode().splitlines()
    names=[p for p in tracked if p.startswith('src/aegis_dc/') or p in
       ('src/patrol_rsi/contracts.py','tests/test_mainline_reserve.py',
        'configs/full-facility-mainline-reserve-v6.json',
        'configs/materials/reference-r134a-saturation.json')]
    actual={p:sha256((repo/p).read_bytes()).hexdigest() for p in names}
    expected={p:sha256(git('cat-file','blob',args.freeze+':'+p)).hexdigest() for p in names}
    assert actual==expected,'Protected review bytes do not match the frozen commit'
    dirty=git('status','--porcelain','--','src/aegis_dc','src/patrol_rsi/contracts.py',
       'tests/test_mainline_reserve.py','configs/full-facility-mainline-reserve-v6.json',
       'configs/materials/reference-r134a-saturation.json').decode().strip()
    assert not dirty,'Protected paths are changing: '+dirty
    return {'head':git('rev-parse','HEAD').decode().strip(),'protected_sha256':actual}

before=snapshot()
command=[sys.executable,'-B','-X','utf8','-m','unittest','discover','-s','tests',
         '-p','test_mainline_reserve.py','-v']
process=subprocess.run(command,cwd=repo,env=dict(os.environ,PYTHONPATH=str(repo/'src')),
                       capture_output=True)
(args.output/'focused-stdout.txt').write_bytes(process.stdout)
(args.output/'focused-stderr.txt').write_bytes(process.stderr)
assert process.returncode==0,'Focused test failure retained in original stdout/stderr'
after_targets=snapshot()
assert before['protected_sha256']==after_targets['protected_sha256']
text=process.stderr.decode('utf-8')
count=int(re.search(r'Ran (\d+) tests',text).group(1))
sys.path.insert(0,str(repo/'src'))
from aegis_dc.scenario import load_scenario
from aegis_dc.plant import simulate_scenario
scenario=load_scenario(repo/'configs/full-facility-mainline-reserve-v6.json')
changes={'grid_capacity':0,'diesel_in_service':0,'generator_initial_start_energy':0,
 'ups_energy':12500,'ups_internal_control_power':50,'ups_transfer_delay':.125,
 'ups_discharge_efficiency':.8,'ups_output_capacity':2000,'controller_power':1000,
 'pump_pressure_rise':0,'internal_pump_pressure_rise':0,'room_aux_power':0,
 'compute_demand_power':0,'network_demand_power':0,'storage_demand_power':0,
 'solid_coolant_conductance':0,'solid_air_conductance':0}
for parameter in scenario['parameters']:
    if parameter['id'] in changes:
        parameter.update(value=changes[parameter['id']],basis='synthetic_assumption',
                         source_note='Independent source-guarded Spec review finite-UPS hand probe; not site data or effect research.')
result=simulate_scenario(scenario,duration_s=10,step_s=.37)
summary=result['summary']
expected={'depletion_s':float(Fraction(2025,208)),
          'protected_energy_J':float(Fraction(249875,26)),
          'control_heat_J':float(Fraction(50625,104)),
          'ups_conversion_loss_J':float(Fraction(249875,104))}
depletion=next(event for event in result['events'] if event['kind']=='ups_depleted')
observed={'depletion_s':depletion['time_s'],
          'protected_energy_J':summary['ups_output_energy_J']-summary['reserve_room_control_heat_J'],
          'control_heat_J':summary['reserve_room_control_heat_J'],
          'ups_conversion_loss_J':summary['ups_loss_energy_J']}
assert all(abs(observed[name]-value)<1e-7 for name,value in expected.items())
assert abs(sum(observed[key] for key in ('protected_energy_J','control_heat_J','ups_conversion_loss_J'))-12500)<1e-7
assert result['trace'][-1]['domains']['backup']['ups_energy_J']==0
assert summary['demand_service_unit_s']==10 and summary['delivered_service_unit_s']==0
assert summary['service_deficit_time_s']==10
assert result['code_identity']['implementation_has_changes'] is False
assert all(before['protected_sha256'].get(name)==value
           for name,value in result['code_identity']['files'].items())
after_probe=snapshot()
assert before['protected_sha256']==after_probe['protected_sha256']
record={'classification':'FROZEN_SOURCE_ENGINEERING_SPEC_REVIEW_NOT_RESEARCH',
        'frozen_commit':args.freeze,'source_guard_before':before,
        'source_guard_after_targets':after_targets,'source_guard_after_probe':after_probe,
        'focused_command':command,'focused_test_count':count,'focused_exit_code':process.returncode,
        'focused_stdout_sha256':sha256(process.stdout).hexdigest(),
        'focused_stderr_sha256':sha256(process.stderr).hexdigest(),
        'probe':{'parameter_overrides':changes,'duration_s':10,'maximum_step_s':.37,
          'independent_expected':expected,'observed':observed,
          'expected_basis':'Wait uses 50/8=6.25J. Remaining 12493.75J discharges at 1000/.8+50=1300W; t_end=2025/208s. Three energy terms are exact rational hand values.',
          'code_identity':result['code_identity'],
          'max_energy_residual_J':summary['max_energy_residual_J'],
          'max_mass_residual_kg':summary['max_mass_residual_kg']},
        'script_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
        'registered_research_trials':0,'full_regression_repeated':False}
path=args.output/'review-receipt.json'
with path.open('x',encoding='utf-8') as stream:stream.write(json.dumps(record,indent=2,allow_nan=False)+'\n')
print(json.dumps({'status':'PASS','frozen_commit':args.freeze,'focused_tests':count,
                  'probe_depletion_s':observed['depletion_s'],'receipt':str(path),
                  'receipt_sha256':sha256(path.read_bytes()).hexdigest()}))
