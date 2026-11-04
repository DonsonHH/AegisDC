"""Execute the frozen control runbook once and fresh-read the saved public artifacts."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

from aegis_dc.plant import save_run, simulate_scenario
from aegis_dc.scenario import load_scenario, validate_scenario

ROOT = Path(__file__).resolve().parents[4]
BASE = Path(__file__).resolve().parent
CONFIG = ROOT / 'configs/full-facility-mainline-control-v5.json'


def file_sha(path):
    return sha256(path.read_bytes()).hexdigest()


def read_json(path):
    def invalid_constant(value):
        raise ValueError('Nonfinite JSON constant: ' + value)
    return json.loads(path.read_text(encoding='utf-8'), parse_constant=invalid_constant)


def write_new(path, value):
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def event(time_s, parameter_id, value):
    return {'time_s':time_s,'parameter_id':parameter_id,'value':value,
            'source_note':'Ticket 09 frozen synthetic engineering disturbance; not a field event or registered effect trial.'}


def fresh_read(directory, commit, expected):
    run=read_json(directory/'run.json')
    assert run['code_identity']['git_commit']==commit
    assert run['code_identity']['implementation_has_changes'] is False
    for name, expected_sha in run['code_identity']['files'].items():
        assert file_sha(ROOT/name)==expected_sha,(directory.name,name)
    for name,identity in run['artifacts'].items():
        path=directory/name
        assert file_sha(path)==identity['sha256'],(directory.name,name)
        if name.endswith('.jsonl'):
            assert len(path.read_text(encoding='utf-8').splitlines())==identity['records']
    trace=[json.loads(line) for line in (directory/'private-state.jsonl').read_text(encoding='utf-8').splitlines()]
    balances=[json.loads(line) for line in (directory/'balances.jsonl').read_text(encoding='utf-8').splitlines()]
    assert all(len(row['domains'])==8 for row in trace)
    assert all(row['domains']['control_monitoring']['local_measurement']['visibility']=='LOCAL_PLANT_ONLY' for row in trace)
    assert run['state_visibility']=='PRIVATE_PLANT_EVALUATOR_ONLY'
    assert run['model_calls']==run['training_calls']==run['research_trials']==0
    for key,value in expected.items():
        assert abs(run['summary'][key]-value)<1e-8,(directory.name,key,run['summary'][key],value)
    assert max(abs(row['energy_residuals_J']['facility']) for row in balances)<0.01
    assert max(abs(v) for row in balances for v in row['mass_residuals_kg'].values())<1e-8
    assert abs(run['summary']['whole_run_energy_residual_J'])<0.01
    return {'commit':commit,'source_tree_sha256':run['code_identity']['source_tree_sha256'],
        'expected_summary':expected,'observed_summary':{k:run['summary'][k] for k in expected},
        'trace_records':len(trace),'balance_records':len(balances),
        'max_step_energy_residual_J':max(abs(row['energy_residuals_J']['facility']) for row in balances),
        'max_mass_residual_kg':max(abs(v) for row in balances for v in row['mass_residuals_kg'].values()),
        'whole_run_energy_residual_J':run['summary']['whole_run_energy_residual_J'],
        'final_mode':trace[-1]['domains']['control_monitoring']['mode'],
        'final_floor_mass_kg':trace[-1]['domains']['space_access']['floor_water_mass_kg'],
        'true_initial_temperature_K':trace[0]['domains']['equipment_environment']['refrigerant']['temperature_K'],
        'reported_initial_temperature_K':trace[0]['domains']['control_monitoring']['local_measurement']['temperature_K'],
        'model_calls':run['model_calls'],'training_calls':run['training_calls'],'research_trials':run['research_trials']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    output=parser.parse_args().output.resolve();output.mkdir(parents=True,exist_ok=False)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    book=read_json(BASE/'runbook-v1.json')
    write_new(output/'declared-runbook.json',book)
    ledger=(output/'attempts.jsonl').open('x',encoding='utf-8',newline='\n')
    results={}
    for case in book['cases']:
        label=case['id'];scenario=load_scenario(CONFIG)
        for parameter in scenario['parameters']:
            if parameter['id'] in case['parameters']:
                parameter.update(value=case['parameters'][parameter['id']],basis='synthetic_assumption',
                    source_refs=['R09'],source_note='Frozen ticket 09 engineering override; not an observed field setting.')
        inputs={'schema':'aegisdc-engineering-inputs-v1','work_requests':[],
                'boundary_events':[event(*row) for row in case['events']]}
        request={'case':label,'scenario':scenario,'inputs':inputs,'duration_s':case['duration_s']}
        input_path=output/(label+'.request.json');write_new(input_path,request)
        attempt={'case':label,'started_UTC':datetime.now(timezone.utc).isoformat(),'source_commit':commit}
        try:
            if case.get('via_cli'):
                config_path=output/(label+'.config.json');write_new(config_path,scenario)
                inputs_path=output/(label+'.inputs.json');write_new(inputs_path,inputs)
                command=[sys.executable,'-B','-m','aegis_dc','simulate','--model',str(config_path),
                    '--duration',str(case['duration_s']),'--inputs',str(inputs_path),'--output',str(output/label)]
                process=subprocess.run(command,cwd=ROOT,env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),
                    capture_output=True)
                (output/(label+'.stdout.json')).write_bytes(process.stdout)
                (output/(label+'.stderr.txt')).write_bytes(process.stderr)
                write_new(output/(label+'.command.json'),{'command':command,'cwd':str(ROOT),'exit_code':process.returncode})
                assert process.returncode==0,'CLI original stdout/stderr retained'
            else:
                run=simulate_scenario(scenario,duration_s=case['duration_s'],boundary_events=inputs['boundary_events'])
                save_run(run,output/label)
            results[label]=fresh_read(output/label,commit,case['expected_summary'])
            if case.get('via_cli'):
                assert json.loads(process.stdout)==read_json(output/label/'run.json')
            attempt['outcome']='PASS'
        except BaseException:
            attempt['outcome']='FAIL'
            (output/(label+'.failure.txt')).write_text(traceback.format_exc(),encoding='utf-8',newline='\n')
            raise
        finally:
            attempt['ended_UTC']=datetime.now(timezone.utc).isoformat()
            ledger.write(json.dumps(attempt,allow_nan=False)+'\n');ledger.flush()
    ledger.close()
    rejections=[]
    for label in ('unknown-profile','fractional-validity','fractional-link-event','offset-range','wrong-offset-unit','legacy-profile-event'):
        scenario=load_scenario(CONFIG);events=[]
        if label=='unknown-profile':scenario['runtime']['local_control_profile']='unimplemented'
        elif label=='fractional-validity':next(r for r in scenario['parameters'] if r['id']=='local_temperature_sensor_valid')['value']=0.5
        elif label=='fractional-link-event':events=[event(0.25,'supervisory_link_available',0.5)]
        elif label=='offset-range':events=[event(0.25,'local_temperature_bias',51)]
        elif label=='wrong-offset-unit':next(r for r in scenario['parameters'] if r['id']=='local_temperature_bias')['unit']='W'
        elif label=='legacy-profile-event':
            scenario['runtime'].pop('local_control_profile');events=[event(0.25,'local_temperature_bias',-2)]
        write_new(output/(label+'.invalid-request.json'),{'scenario':scenario,'boundary_events':events,'duration_s':2})
        try:simulate_scenario(scenario,duration_s=2,boundary_events=events)
        except ValueError as error:rejections.append({'id':label,'outcome':'EXPECTED_REFUSAL','error':str(error),'successful_trajectory_returned':False})
        else:raise AssertionError('Invalid request unexpectedly succeeded: '+label)
    write_new(output/'expected-refusals.json',rejections)
    assert abs(results['leak-with-local-sensor-interruption']['final_floor_mass_kg']-0.3)<1e-8
    assert results['normal']['reported_initial_temperature_K']==results['normal']['true_initial_temperature_K']
    files={str(p.relative_to(output)).replace('\\','/'):file_sha(p) for p in sorted(output.rglob('*')) if p.is_file()}
    receipt={'schema':'aegisdc-control-engineering-receipt-v1','status':'PASS',
        'classification':'FINITE_ENGINEERING_FIXTURES_NOT_RESEARCH_OR_FIELD_VALIDATION',
        'source_commit':commit,'author_script_sha256':file_sha(Path(__file__)),
        'runbook_sha256':file_sha(BASE/'runbook-v1.json'),'base_configuration_sha256':file_sha(CONFIG),
        'runs':results,'successful_runs':len(results),'expected_refusals':len(rejections),'artifacts':files,
        'research_trials':0,'model_calls':0,'training_calls':0,'field_calibration':'PENDING',
        'scientific_gain':'NOT_ESTABLISHED','M1_gate':'IN_PROGRESS','overall_goal':'ACTIVE'}
    write_new(output/'receipt.json',receipt)
    print(json.dumps({'status':'PASS','source_commit':commit,'runs':len(results),'refusals':len(rejections),'hashed_files':len(files)}))


if __name__=='__main__':main()
