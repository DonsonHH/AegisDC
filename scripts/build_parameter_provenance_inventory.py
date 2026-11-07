"""Inventory the accepted V6 parameter provenance without running the facility."""
import argparse
from collections import Counter
from hashlib import sha256
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = 'configs/full-facility-mainline-reserve-v6.json'
PRIOR = ['docs/mainline/evidence/M2.json', 'docs/mainline/evidence/M4.json',
         'docs/mainline/evidence/12-root.json', 'docs/mainline/evidence/28-root.json']
OUTPUT = 'evidence/mainline/engineering/29-uncertainty-domain/reference/v6-parameter-inventory-v1.json'
EXPECTED_DOMAINS = {'power','backup','facility_cooling','equipment_environment','it_service',
                    'control_monitoring','space_access','people_tools_work'}
GRAPHS = {'physical','functional','control_information','access'}
BASIS_ROLE = {'synthetic_assumption':'SYNTHETIC_MODEL_ASSUMPTION',
              'derived_reference':'SYNTHETIC_VALUE_FROM_DECLARED_REFERENCE_CALCULATION'}


def require(value, message):
    if not value:
        raise ValueError(message)


def read(relative):
    return json.loads((ROOT/relative).read_bytes())


def digest(relative):
    return sha256((ROOT/relative).read_bytes()).hexdigest()


def build():
    model=read(SCENARIO)
    authority={p:read(p) for p in PRIOR}
    require(all(a['status']=='ACCEPTED' for a in authority.values()),'Required predecessor evidence not accepted')
    require({row['id'] for row in model['domains']}==EXPECTED_DOMAINS and set(model['graphs'])==GRAPHS,
            'Use the complete eight-domain V6 facility')
    rows=model['parameters']
    names={row['id'] for row in rows}
    require(len(names)==len(rows) and len(names)==113,'Unexpected accepted V6 parameter set size')
    entry_by_id={}
    refs=set(model['sources'])
    for row in rows:
        name=row['id']
        require(row['basis'] in BASIS_ROLE and bool(row['source_refs']) and set(row['source_refs'])<=refs,
                'Unresolved declared parameter source: '+name)
        lo,hi=row['valid_range']
        value=row['value']
        require(all(type(number) in (int,float) and math.isfinite(number) for number in (lo,hi,value))
                and lo<=value<=hi,'Recorded model input is outside its scalar bounds: '+name)
        entry_by_id[name]=dict(quantity=row['quantity'],unit=row['unit'],accepted_v6_value=value,
            declared_scalar_range=[lo,hi],basis=row['basis'],evidence_role=BASIS_ROLE[row['basis']],
            source_refs=row['source_refs'],source_note=row['source_note'],
            admissibility='SCALAR_ONLY_NOT_A_JOINT_DISTRIBUTION',site_calibrated=False)
    gaps={}
    for row in model['site_gaps']:
        name=row['id']
        require(row['value'] is None and name not in names and name not in gaps and set(row['source_refs'])<=refs,
                'Site gaps must be unresolved and separate from runtime inputs')
        gaps[name]=dict(value=None,needed_for=row['needed_for'],source_refs=row['source_refs'],
            evidence_role='UNRESOLVED_SITE_DATA')
    property_path=model['runtime']['property_table']
    require(digest(property_path)==model['runtime']['property_sha256'],'Frozen saturation surrogate bytes changed')
    counts=Counter(row['basis'] for row in rows)
    require(counts=={'synthetic_assumption':106,'derived_reference':7} and len(gaps)==4,
            'Accepted model provenance inventory changed; revise instead of silently replacing it')
    pins={path:digest(path) for path in (SCENARIO,property_path,*PRIOR,Path(__file__).relative_to(ROOT).as_posix())}
    return dict(schema='aegisdc-v6-parameter-provenance-inventory-v1',status='INVENTORY_NOT_JOINT_DOMAIN_ACCEPTANCE',
        facility_id=model['id'],facility_scope=model['scope'],runtime_model=model['runtime']['model'],
        domain_ids=sorted(EXPECTED_DOMAINS),relationship_counts={name:len(rows) for name,rows in model['graphs'].items()},
        source_pins=pins,
        sources=model['sources'],parameters=dict(sorted(entry_by_id.items())),site_gaps=dict(sorted(gaps.items())),
        basis_counts=dict(sorted(counts.items())),calibrated_site_parameter_count=0,
        numerical_evidence_scope='Finite numerical witnesses and declared tolerances only; no global parameter guarantee.',
        evidence_boundary='Source classification and module scope come from the accepted V6 input. This inventory does not turn public statements, reference calculations or scalar input limits into observations.',
        field_calibration='PENDING',new_project_calls=0,new_physical_calls=0,registered_research_trials=0)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('build','verify'))
    args=p.parse_args()
    value=build()
    destination=ROOT/OUTPUT
    if args.mode=='build':
        destination.parent.mkdir(parents=True,exist_ok=True)
        with destination.open('x',encoding='utf-8',newline='\n') as f:
            f.write(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    else:
        require(read(OUTPUT)==value,'Committed parameter inventory differs from the authoritative inputs')
    print(json.dumps(dict(status='PASS_INVENTORY_ONLY',parameters=len(value['parameters']),
        basis_counts=value['basis_counts'],site_gaps=len(value['site_gaps']),
        new_physical_calls=0,registered_research_trials=0),ensure_ascii=False))


if __name__=='__main__':
    main()
