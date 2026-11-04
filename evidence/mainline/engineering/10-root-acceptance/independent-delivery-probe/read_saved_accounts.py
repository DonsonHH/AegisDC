"""Read-only independent audit of ticket-10 saved inputs and physical accounts."""
from hashlib import sha256
import json
import math
from pathlib import Path
import subprocess

repo=Path('C:/Users/Donson/Documents/ChatGPT/Renly/.work/worktrees/full-site-10')
base=repo/'evidence/mainline/engineering/10-reserve'
package=base/'fixtures-179094ed-01'
book=json.loads((base/'runbook-v1.json').read_text(encoding='utf-8'))
copy=json.loads((package/'runbook-copy.json').read_text(encoding='utf-8'))
assert book==copy
frozen=json.loads(subprocess.check_output(['git','show','076fd215:evidence/mainline/engineering/10-reserve/runbook-v1.json'],cwd=repo,text=True,encoding='utf-8'))
assert frozen==book,'Frozen runbook changed after declaration'
receipt=json.loads((package/'receipt.json').read_text(encoding='utf-8'))
assert receipt['execution_commit']=='179094ed28b482fd75c50396c6213472870eed3d'
for name,expected in receipt['pinned_tools'].items():
    assert sha256((repo/name).read_bytes()).hexdigest()==expected,'Actual verifier/capture bytes changed: '+name
full=json.loads((base/'full-acceptance-index-179094ed.json').read_text(encoding='utf-8'))
for name,expected in full['post_execution_tools'].items():
    assert sha256((repo/name).read_bytes()).hexdigest()==expected
profile=json.loads((repo/book['source_profile']).read_text(encoding='utf-8'))
base_values={row['id']:row['value'] for row in profile['parameters']}
cases=[];traces=balances_count=0
max_energy=max_mass=max_store=0.
for item in book['cases']:
    name=item['id'];folder=package/name
    saved=json.loads((folder/'scenario.json').read_text(encoding='utf-8'))
    supplied=json.loads((package/'inputs'/(name+'-model.json')).read_text(encoding='utf-8'))
    inputs=json.loads((package/'inputs'/(name+'-inputs.json')).read_text(encoding='utf-8'))
    manifest=json.loads((folder/'run.json').read_text(encoding='utf-8'))
    assert saved==supplied,name
    assert set(item['overrides'])<=set(base_values),name
    expected_values=dict(base_values,**item['overrides'])
    assert {row['id']:row['value'] for row in saved['parameters']}==expected_values,name
    assert inputs['boundary_events']==item['events'],name
    key=lambda row:(row['time_s'],row['parameter_id'])
    assert sorted(manifest['inputs']['boundary_events'],key=key)==sorted(item['events'],key=key),name
    assert manifest['inputs']['duration_s']==item['duration_s']
    assert manifest['inputs']['maximum_step_s']==item['step_s']
    assert all(manifest[key]==0 for key in ('research_trials','training_calls','model_calls'))
    trace=[json.loads(line) for line in (folder/'private-state.jsonl').read_text(encoding='utf-8').splitlines()]
    balances=[json.loads(line) for line in (folder/'balances.jsonl').read_text(encoding='utf-8').splitlines()]
    assert trace[0]['time_s']==0 and trace[-1]['time_s']==item['duration_s']
    assert len(trace)==len(balances)+1
    traces+=len(trace);balances_count+=len(balances)
    for row in trace:
        assert all(row['domains']['backup'][key]>=0 for key in ('ups_energy_J','fuel_energy_J','starter_energy_J'))
        assert len(row['domains'])==8
        assert row['domains']['facility_cooling']['hot_mass_kg']>=0
        assert row['domains']['space_access']['floor_water_mass_kg']>=0
    for row in balances:
        dt=row['end_s']-row['start_s'];assert dt>0 and dt<=item['step_s']+1e-12
        residual=math.fsum([*row['storage_after_J'].values(),*[-x for x in row['storage_before_J'].values()],
                            -row['boundary_input_J'],row['boundary_output_J']])
        max_energy=max(max_energy,abs(residual));assert abs(residual)<.01,(name,residual)
        for account in row['mass_accounts_kg'].values():
            residual=math.fsum([account['before_kg'],account['in_kg'],-account['out_kg'],-account['after_kg']])
            max_mass=max(max_mass,abs(residual));assert abs(residual)<1e-8,(name,residual)
        for key in ('ups','fuel','starter'):
            residual=math.fsum([row['storage_after_J'][key],-row['storage_before_J'][key],
                                -row['component_energy_rates_W'][key]*dt])
            max_store=max(max_store,abs(residual));assert abs(residual)<1e-6,(name,key,residual)
    for key,value in item['expected'].items():
        assert abs(manifest['summary'][key]-value)<=book['absolute_metric_tolerance'],(name,key)
    cases.append({'id':name,'saved_inputs_equal_supplied_inputs':True,
                  'duration_s':item['duration_s'],'maximum_step_s':item['step_s'],
                  'trace_records':len(trace),'balance_records':len(balances)})
ledger=[json.loads(line) for line in (package/'engineering-attempts.jsonl').read_text(encoding='utf-8').splitlines()]
completed=[row for row in ledger if row['outcome']=='ENGINEERING_COMPLETED']
rejected=[row for row in ledger if row['outcome']=='EXPECTED_REJECTION']
assert len(completed)==20 and len(rejected)==6 and len(ledger)==26
assert {row['case'] for row in completed}=={row['id'] for row in book['cases']}
refusals=json.loads((package/'expected-rejections.json').read_text(encoding='utf-8'))
assert len(refusals)==6 and {row['id'] for row in refusals}=={row['case'] for row in rejected}
assert all(row['successful_trajectory_returned'] is False and row['error'] for row in refusals)
for row in refusals:
    assert sha256((package/'rejections'/(row['id']+'.json')).read_bytes()).hexdigest()==row['input_sha256']
result={'classification':'SAVED_INPUT_AND_ACCOUNT_RECOMPUTATION_NO_SIMULATION',
        'reviewed_candidate':'5b1d30d6cdb5acbe6fd76ac9400e00939dd04afa',
        'execution_commit':receipt['execution_commit'],
        'delivery_commit':'2172dab0f2ba7e7913c926bc196f8a6c0a3f0ea9',
        'cases':cases,'case_count':len(cases),'expected_refusals':len(refusals),
        'trace_records':traces,'balance_records':balances_count,
        'frozen_runbook_semantically_identical':True,'actual_capture_and_verifier_bytes_match':True,
        'max_independently_recomputed_energy_residual_J':max_energy,
        'max_independently_recomputed_mass_residual_kg':max_mass,
        'max_reserve_store_rate_residual_J':max_store,
        'new_simulations':0,'full_regression_repeated':False,
        'script_sha256':sha256(Path(__file__).read_bytes()).hexdigest()}
path=Path('C:/Users/Donson/AppData/Local/Temp/aegisdc-review-10-delivery-spec-attachments/independent-account-readback-01.json')
with path.open('x',encoding='utf-8') as stream:stream.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps({'status':'PASS','cases':len(cases),'refusals':len(refusals),'traces':traces,'balances':balances_count,
 'max_energy_residual_J':max_energy,'max_mass_residual_kg':max_mass,'receipt':str(path),'sha256':sha256(path.read_bytes()).hexdigest()}))
