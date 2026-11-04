"""Independent, read-only ticket-11 saved-input, literal and account audit."""
from fractions import Fraction
from hashlib import sha256
import importlib.util
import json
import math
from pathlib import Path
import subprocess

repo=Path('C:/Users/Donson/Documents/ChatGPT/Renly/.work/worktrees/full-site-11')
package=repo/'evidence/mainline/engineering/11-coupled/fixtures-b135ecff-01'
freeze='b135ecffb5fe5c3fecaa44859afbf925b8549bb1'
builder=repo/'scripts/build_coupled_runbook.py'
assert builder.read_bytes()==subprocess.check_output(['git','cat-file','blob',freeze+':scripts/build_coupled_runbook.py'],cwd=repo)
spec=importlib.util.spec_from_file_location('frozen_runbook_author',builder)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
book=json.loads((repo/'docs/mainline/11-coupled-runbook.json').read_text(encoding='utf-8'))
assert module.build()==book
assert book==json.loads((package/'runbook-copy.json').read_text(encoding='utf-8'))
receipt=json.loads((package/'receipt.json').read_text(encoding='utf-8'))
assert receipt['execution_commit']==freeze
for name,expected in receipt['artifacts'].items():
    assert sha256((package/name).read_bytes()).hexdigest()==expected,name
base=json.loads((repo/book['profile']).read_text(encoding='utf-8'))
base_values={row['id']:row['value'] for row in base['parameters']}
def lookup(document,path):
    for part in path.split('.'):
        document=document[int(part)] if isinstance(document,list) else document[part]
    return document

def stored(domains,p):
    cooling=domains['facility_cooling'];environment=domains['equipment_environment'];backup=domains['backup'];floor=domains['space_access']
    floor_energy=0 if floor['floor_water_mass_kg']==0 else floor['floor_water_mass_kg']*p['water_specific_heat']*floor['floor_water_temperature_K']
    return math.fsum([p['it_thermal_capacity']*environment['solid_temperature_K'],
        p['room_thermal_capacity']*environment['room_temperature_K'],
        cooling['hot_mass_kg']*p['water_specific_heat']*cooling['hot_temperature_K'],
        cooling['cold_mass_kg']*p['water_specific_heat']*cooling['cold_temperature_K'],
        environment['refrigerant']['internal_energy_J'],backup['ups_energy_J'],backup['fuel_energy_J'],backup['starter_energy_J'],floor_energy])

counts={'cases':0,'literal_checks':0,'states':0,'intervals':0}
max_energy=max_electric=max_water=max_phase=0.
combined=None
for item in book['cases']:
    folder=package/item['id'];manifest=json.loads((folder/'run.json').read_text(encoding='utf-8'))
    scenario=json.loads((folder/'scenario.json').read_text(encoding='utf-8'))
    supplied=json.loads((package/'inputs'/(item['id']+'-model.json')).read_text(encoding='utf-8'))
    inputs=json.loads((package/'inputs'/(item['id']+'-inputs.json')).read_text(encoding='utf-8'))
    assert scenario==supplied
    assert scenario['id']==base['id'] and scenario['entities']==base['entities'] and scenario['graphs']==base['graphs']
    assert set(item['overrides'])<=set(base_values)
    p=dict(base_values,**item['overrides'])
    assert {row['id']:row['value'] for row in scenario['parameters']}==p
    assert inputs['boundary_events']==manifest['inputs']['boundary_events']==item['events']
    assert inputs['work_requests']==manifest['inputs']['work_requests']==item['work_requests']
    assert manifest['inputs']['duration_s']==item['duration_s'] and manifest['inputs']['maximum_step_s']==item['step_s']
    rows=[json.loads(line) for line in (folder/'private-state.jsonl').read_text(encoding='utf-8').splitlines()]
    balances=[json.loads(line) for line in (folder/'balances.jsonl').read_text(encoding='utf-8').splitlines()]
    assert rows[0]['time_s']==0 and rows[-1]['time_s']==item['duration_s'] and len(rows)==len(balances)+1
    for condition in item['checks']:
        time=condition['time_s']
        document=manifest if time is None else rows[-1]['domains'] if time=='final' else next(r['domains'] for r in rows if abs(r['time_s']-time)<1e-9)
        actual=lookup(document,condition['path']);expected=condition['expected']
        if condition['op']=='greater':assert actual>expected
        elif type(expected) in (int,float):assert abs(actual-expected)<=condition['absolute_tolerance']
        else:assert type(actual) is type(expected) and actual==expected
        counts['literal_checks']+=1
    for row in rows:
        d=row['domains'];power=d['power'];phase=d['equipment_environment']['refrigerant']
        assert len(d)==8 and phase['volume_m3']==p['coolant_control_volume']
        assert all(d['backup'][key]>=0 for key in ('ups_energy_J','fuel_energy_J','starter_energy_J'))
        error=abs(math.fsum([phase['liquid_mass_kg'],phase['vapor_mass_kg'],-p['coolant_inventory']]))
        max_phase=max(max_phase,error);assert error<1e-8
        error=abs(math.fsum([power[key] for key in ('grid_draw_W','generator_output_W','ups_output_W','starter_output_W')])
           -math.fsum([*power['actual_powers_W'].values(),power['rectifier_loss_W']]))
        max_electric=max(max_electric,error);assert error<1e-6
    for index,interval in enumerate(balances):
        before,after=rows[index]['domains'],rows[index+1]['domains'];t=interval['start_s'];dt=interval['end_s']-t
        assert dt>0 and dt<=item['step_s']+1e-12
        offered=p['service_demand']
        for event in item['events']:
            if event['time_s']<=t and event['parameter_id']=='service_demand':offered=event['value']
        served=before['it_service']['delivered']
        assert abs(before['it_service']['demand']-offered)<1e-12
        assert 0<=served<=offered
        assert abs(interval['demand_service_unit_s']-offered*dt)<1e-8
        assert abs(interval['delivered_service_unit_s']-served*dt)<1e-8
        assert abs(interval['service_deficit_time_s']-((offered-served)/offered*dt if offered else 0))<1e-8
        error=abs(math.fsum([stored(after,p),-stored(before,p),-interval['boundary_input_J'],interval['boundary_output_J']]))
        max_energy=max(max_energy,error);assert error<.01
        for account in interval['mass_accounts_kg'].values():
            error=abs(math.fsum([account['before_kg'],account['in_kg'],-account['out_kg'],-account['after_kg']]))
            max_water=max(max_water,error);assert error<1e-8
        assert abs(interval['floor_inlet_energy_J'])<.01
        floor_delta=after['space_access']['floor_water_sensible_energy_J']-before['space_access']['floor_water_sensible_energy_J']
        assert abs(floor_delta-interval['internal_hot_leak_energy_J']+interval['floor_drain_energy_J'])<.01
        crew=before['people_tools_work']
        for key,value in [('worker_travel_person_s',sum(w['status']=='travelling' for w in crew['workers'].values())*dt),
                          ('worker_work_person_s',sum(w['status']=='working' for w in crew['workers'].values())*dt),
                          ('tool_occupation_tool_s',sum(w['reserved_by'] is not None for w in crew['tools'].values())*dt)]:
            assert abs(interval[key]-value)<1e-8
    if item['id']=='combined-episode-CLI':
        demand=Fraction(240)+Fraction(1,5)*175
        deficit=32+4;unserved=Fraction(6,5)*deficit;delivered=demand-unserved
        summary=manifest['summary'];work=manifest['work_records'][0]
        assert abs(summary['demand_service_unit_s']-float(demand))<1e-8
        assert abs(summary['delivered_service_unit_s']-float(delivered))<1e-8
        assert abs(summary['service_deficit_time_s']-deficit)<1e-8
        assert abs(work['finished_at_s']-145.5)<1e-8 and work['status']=='aborted'
        assert abs(summary['worker_travel_person_s']-120)<1e-8 and abs(summary['worker_work_person_s']-25.25)<1e-8
        assert abs(summary['internal_hot_leaked_mass_kg']-20)<1e-8
        assert abs(summary['floor_water_drained_mass_kg']-11.95)<1e-8
        assert abs(rows[-1]['domains']['space_access']['floor_water_mass_kg']-8.05)<1e-8
        combined={'independent_expected':{'demand_service_unit_s':float(demand),'delivered_service_unit_s':float(delivered),
            'unserved_service_unit_s':float(unserved),'normalized_deficit_s':deficit,
            'abort_s':145.5,'travel_person_s':120,'work_person_s':25.25,'leaked_kg':20,'drained_kg':11.95,'retained_kg':8.05},
            'observed_summary':summary,'work_record':work}
    counts['cases']+=1;counts['states']+=len(rows);counts['intervals']+=len(balances)
refused=json.loads((package/'expected-rejections.json').read_text(encoding='utf-8'))
assert len(refused)==3
for expected,actual in zip(book['rejections'],refused):
    assert expected['id']==actual['id'] and actual['successful_trajectory_returned'] is False and expected['error_contains'] in actual['error']
assert counts['cases']==17 and counts['literal_checks']==129 and combined is not None
record={'classification':'INDEPENDENT_SAVED_COUPLED_ACCOUNT_REVIEW_NO_PHYSICS_RERUN','execution_commit':freeze,
    'builder_is_declarative_and_matches_frozen_runbook':True,'package_receipt_sha256':sha256((package/'receipt.json').read_bytes()).hexdigest(),
    'artifact_sha256_checks':len(receipt['artifacts']),'counts':counts,'expected_rejections':len(refused),
    'maximum_energy_residual_J':max_energy,'maximum_electric_residual_W':max_electric,
    'maximum_water_residual_kg':max_water,'maximum_phase_mass_residual_kg':max_phase,
    'combined_episode':combined,'new_simulations':0,'full_regression_repeated':False,
    'script_sha256':sha256(Path(__file__).read_bytes()).hexdigest()}
path=Path('C:/Users/Donson/AppData/Local/Temp/aegisdc-review-11-spec-attachments/saved-account-readback-01.json')
with path.open('x',encoding='utf-8') as stream:stream.write(json.dumps(record,indent=2,allow_nan=False)+'\n')
print(json.dumps({'status':'PASS','counts':counts,'artifact_checks':len(receipt['artifacts']),'rejections':len(refused),'max_energy_residual_J':max_energy,'receipt':str(path),'sha256':sha256(path.read_bytes()).hexdigest()}))
