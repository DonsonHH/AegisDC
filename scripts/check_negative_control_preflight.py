"""Check ticket 28 declarations without importing or executing the facility."""
import argparse
import ast
from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = 'docs/mainline/28-negative-engineering-protocol-v2.json'


def read(path):
    return json.loads(path.read_bytes())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def inspect():
    protocol = read(ROOT / PROTOCOL)
    document = read(ROOT / protocol['input'])
    cases = document['cases']
    literals = read(ROOT / protocol['literals'])
    require(list(cases) == protocol['cases'] == ['normal','false_report','local_protection','too_late'], 'Four named engineering cases required')
    require(sum(Fraction(case['duration_s']) for case in cases.values()) == Fraction(43,2)
            and protocol['total_simulated_duration_s'] == 21.5 and protocol['total_integrations'] == 4,
            'Physical budget differs')
    require(all(case['maximum_step_s'] == .01 for case in cases.values()), 'Step differs')
    for case in cases.values():
        require(len(case['model']['domains']) == 8 and len(case['model']['graphs']) == 4, 'Full facility missing')
        require(case['model']['graphs'] == cases['normal']['model']['graphs']
                and case['model']['id'] == document['facility_id'], 'Facility identities or relations differ')
        for parameter in case['model']['parameters']:
            low, high = parameter['valid_range']
            require(low <= parameter['value'] <= high, 'Out-of-range initial parameter: ' + parameter['id'])
    a,b = (deepcopy(cases[name]['replay_inputs']['dispatch_program']) for name in ('normal','false_report'))
    a_records, b_records = a['evidence_ledger'].pop('records'), b['evidence_ledger'].pop('records')
    require(cases['normal']['model'] == cases['false_report']['model'] and a == b
            and a_records == [] and len(b_records) == 2, 'Normal and false-report cases have different physical or decision rules')
    require(a['decision_times_s'] == b['decision_times_s'] == protocol['online_decisions_s']
            and len(a['decision_times_s']) * 2 == literals['public_online_decisions'] == 14, 'Scheduled public decision budget differs')
    for program in (a,b):
        policy = program['policy_program']
        require(policy['options']['catalog'] == program['closure_program']['risk_catalog']
                and policy['options']['catalog']['demand'] == [dict(start_s=0,end_s=6,rate=.5)], 'Public demand laws differ')
        require(policy['evidence_projection']['inspection_profile'] == program['inspection_program']['profile']
                and policy['evidence_projection']['background_sensor_profile'] == program['sensor_program']['profile'],
                'Public future-evidence declaration differs from actual instrument declaration')
        require(policy['intervention_declaration'] == program['intervention_program'] == program['closure_program']['intervention_declaration'],
                'Policy and real action declarations differ')
    require([(r['observed_at_s'],r['arrived_at_s']) for r in b_records] == [(1.5,3),(6.75,7)],
            'Report or declared review times differ')
    support = b['closure_program']['profile']['false_alarm_reviews'][0]['supporting_record_ids']
    require(set(support) == {'flow-transfer:0','flow-transfer:1','joint-service-transfer:0','joint-service-transfer:1'}
            and len(support) == 4, 'False-alarm review does not declare four actual instrument records')
    late = cases['too_late']
    planned = late['public_preparation']
    require(planned['decision_times_s'] == [0,1,3.25,4] and planned['issued_at_s'] == 1
            and late['closure_assessment_times_s'] == [3.25,4], 'Late public clocks differ')
    require(late['boundary_events'] == [dict(time_s=3,parameter_id='it_access_permit',value=0,
            source_note='Private exogenous safety gate closes while the already issued crew is working.')],
            'Late private safety event differs')
    expected_locations = {'worker_it':'loc_control', 'tool_it_diagnostic':'loc_control'}
    for entity in late['model']['entities']:
        if entity['id'] in expected_locations:
            require(entity['location_id'] == expected_locations[entity['id']], 'Actual start differs')
    for entity in planned['nominal_knowledge']['entities']:
        if entity['id'] in expected_locations:
            require(entity['nominal_location_id'] == expected_locations[entity['id']], 'Declared start differs')
    idle = read(ROOT / protocol['protection_workforce_input'])
    require(idle['submissions'] == [] and idle['plan']['decision_times_s'] == [0]
            and idle['plan']['requests'] == [] and idle['evidence_ledger']['records'] == [], 'Idle crew has tasks or observations')
    for preparation_name in (protocol['preparation'], protocol['protection_workforce_preparation']):
        path = ROOT / preparation_name
        receipt = read(path)
        for name, sha in receipt['source_inputs'].items():
            require(digest(ROOT / name) == sha, 'Static preparation source changed: ' + name)
        for name, sha in receipt.get('outputs',receipt.get('artifacts',{})).items():
            require(digest(path.parent / name) == sha, 'Static preparation output changed: ' + name)
    require(read(ROOT / protocol['preparation'])['authoring_tool_sha256'] ==
            digest(ROOT / 'scripts/prepare_negative_control_inputs_v2.py'), 'Case authoring tool changed')
    require(read(ROOT / protocol['protection_workforce_preparation'])['authoring_tool_sha256'] ==
            digest(ROOT / 'scripts/prepare_negative_control_workforce.py'), 'Idle-crew authoring tool changed')
    require(literals['total_integrations'] == 4 and literals['total_simulated_duration_s'] ==
            {'numerator':43,'denominator':2}, 'Independent total differs')
    for name in protocol['tools']:
        ast.parse((ROOT / name).read_bytes(), filename=name)
    runtime = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / 'src').rglob('*.py') if '__pycache__' not in p.parts)
    inputs = {PROTOCOL, protocol['contract'], protocol['input'], protocol['literals'], protocol['preparation'],
              protocol['protection_workforce_input'], protocol['protection_workforce_preparation'],
              *protocol['retained_unexecuted_draft'], *protocol['retained_context'], *protocol['retained_failed_reviews']}
    return dict(status='PASS_STATIC_DECLARATIONS_ONLY', source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        classification='INPUT_AND_TOOL_PREFLIGHT_NOT_RUNTIME_ACCEPTANCE',
        source_tree_has_uncommitted_changes=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT)),
        source_note='HEAD is context only; checked current byte identities are recorded separately. No execution source is certified by this static preflight.',
        cases=list(cases), scheduled_physical_calls=4, scheduled_simulated_seconds=21.5, scheduled_online_decisions=14,
        static_input_pins={name:digest(ROOT/name) for name in sorted(inputs)},
        tool_pins={name:digest(ROOT/name) for name in protocol['tools']},
        runtime_files=len(runtime), runtime_pins={name:digest(ROOT/name) for name in runtime},
        declared_protection_initial_frames=1, declared_late_preparation_frames=4,
        new_project_calls=0, new_physical_calls=0, new_selector_calls=0, new_closure_calls=0, new_research_trials=0,
        reviewer_gate='PENDING_INDEPENDENT_FIXED_SOURCE_REVIEW', formal_capture_started=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Preflight output exists')
    result = inspect()
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if not k.endswith('_pins')},ensure_ascii=False))
