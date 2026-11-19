"""Write the pre-execution amendment to the literal native input documents."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

root = Path(__file__).resolve().parent
data = json.loads((root/'inputs.json').read_bytes())

def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def replace(obj, path, value):
    for key in path[:-1]:
        obj=obj[key]
    obj[path[-1]]=deepcopy(value)

units = {}
changes = {}
for key, unit in data['units'].items():
    doc = deepcopy(data['common']) if unit['base']=='common' else json.loads(Path(data['legacy_path']).read_bytes())
    for path, value in unit['edits']:
        replace(doc,path,value)
    assert canonical(doc)==unit['sha256']
    edits = []
    events = doc['boundary_events']
    if events:
        normalized = [dict(e,time_s=float(e['time_s']),value=float(e['value'])) for e in events]
        diagnostic = ['business_program','components','diagnostic']
        edits += [[['boundary_events'],normalized],
                  [['business_program','run_binding','boundary_events_sha256'],canonical(normalized)],
                  [diagnostic+['reference','boundary_events_sha256'],canonical(normalized)]]
    if key=='delayed-order':
        path=['business_program','components','diagnostic','events',0,'opportunity']
        opportunity=doc['business_program']['components']['diagnostic']['events'][0]['opportunity']
        edits.append([path,dict(opportunity,status='TOO_LATE',starts_at_s=0.5,earliest_report_at_s=4.25,
                                source_note='First opportunity after lawful opening at 0.5; earliest physical arrival 4.25, next public tick 4.5, after deadline 4.')])
    for path, value in edits:
        replace(doc,path,value)
    units[key]={'edits':edits,'sha256':canonical(doc)}
changes={'schema':'aegisdc-v6-intake-binding-amendment-v1','supersedes_input_identity_at':'6a3e30e6',
         'reason':'Preserve exact native normalized event serialization and actual opportunity for a delayed work order. No new model output exists. No change to treatment, physical inputs, expected choices or budgets.',
         'units':units,'delayed_order_opportunity_expected':{'status':'TOO_LATE','starts_at_s':0.5,'earliest_report_at_s':4.25,'deadline_s':4},
         'author_files':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ['author_inputs.py','author_binding_addendum.py']},
         'original_manifest_sha256':hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest()}
(root/'input-binding-addendum.json').write_bytes((json.dumps(changes,indent=2)+'\n').encode())

