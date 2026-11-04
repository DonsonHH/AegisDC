"""Author the explicit control-v5 research variant without changing its base."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
source = ROOT / 'configs/full-facility-mainline-environment-v4.json'
content = source.read_bytes()
scenario = json.loads(content)
scenario['id'] = 'aegisdc-zhengzhou-inspired-full-facility-control-v5'
scenario['runtime']['local_control_profile'] = 'aegisdc-local-control-faults-v1'
scenario['sources']['R09'] = {'classification':'synthetic_assumption',
    'uri':'docs/mainline/local-control-verification.md',
    'scope':'Bounded deterministic local measurement offsets, validity and supervisory autonomy; not site calibration.'}
records = [
    ('local_temperature_bias','temperature_offset','K',0,[-50,50]),
    ('local_internal_flow_bias','volume_flow_offset','m3/s',0,[-0.2,0.2]),
    ('local_temperature_sensor_valid','fraction','1',1,[0,1]),
    ('local_internal_flow_sensor_valid','fraction','1',1,[0,1]),
    ('supervisory_link_available','fraction','1',1,[0,1]),
]
for name, quantity, unit, value, limits in records:
    scenario['parameters'].append({'id':name,'quantity':quantity,'unit':unit,'value':value,
        'valid_range':limits,'basis':'synthetic_assumption','source_refs':['R09'],
        'source_note':'Explicit ticket 09 research measurement/control input; reported values do not replace physical state.'})
controller = next(e for e in scenario['entities'] if e['id']=='local_controller')
controller['parameter_refs'] += [r[0] for r in records]
controller['source_refs'].append('R09')
controller['source_note'] += ' Control-v5 selects finite biased/invalid local channels and autonomous operation under supervisory loss.'
output = ROOT / 'configs/full-facility-mainline-control-v5.json'
with output.open('x',encoding='utf-8',newline='\n') as stream:
    stream.write(json.dumps(scenario,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
receipt = {'classification':'SYNTHETIC_CONFIGURATION_AUTHORING',
    'base_file':str(source.relative_to(ROOT)).replace('\\','/'),'base_sha256':sha256(content).hexdigest(),
    'output_file':str(output.relative_to(ROOT)).replace('\\','/'),'output_sha256':sha256(output.read_bytes()).hexdigest(),
    'graphs_unchanged':True,'dynamic_verification':'NOT_RUN_BY_AUTHOR_PROGRAM'}
with (Path(__file__).parent/'config-source-receipt.json').open('x',encoding='utf-8',newline='\n') as stream:
    stream.write(json.dumps(receipt,indent=2)+'\n')
