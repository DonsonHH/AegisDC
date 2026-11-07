"""Prepare new ticket 28 cases using only immutable JSON inputs and rational arithmetic."""
from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = 'evidence/mainline/engineering/27-full-loop/reference/online-loop-v2.json'
DESTINATION = ROOT / 'evidence/mainline/engineering/28-negative-controls/reference-v2'
NOMINAL = 'V6-28-negative-controls-engineering'
TIMES = [1, 3, 4.5, 4.75, 5.5, 6.5, 7]
DURABLE = ('cases-v1.json', 'literals-v1.json', 'preparation.json')


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def change_parameters(model, values):
    parameters = {row['id']: row for row in model['parameters']}
    for name, value in values.items():
        row = parameters[name]
        low, high = row['valid_range']
        assert low <= value <= high, name
        row.update(value=value, source_note='Explicit ticket28 finite synthetic engineering assumption; no field calibration.')


def change_nominal(value):
    if type(value) is dict:
        for key, child in value.items():
            if key == 'nominal_knowledge_id':
                value[key] = NOMINAL
            else:
                change_nominal(child)
    elif type(value) is list:
        for child in value:
            change_nominal(child)


def add_registration(registry, field, row):
    existing = {item['id']: item for item in registry[field]}
    if row['id'] in existing:
        assert row == existing[row['id']]
    else:
        registry[field].append(deepcopy(row))


def common_online(reference):
    model = deepcopy(reference['model'])
    program = deepcopy(reference['replay_inputs']['dispatch_program'])
    change_parameters(model, dict(service_demand=.5, network_service_capacity=1, storage_service_capacity=1,
                                  filter_resistance_multiplier=1, pump_min_speed=1, ups_in_service=1))
    change_nominal(program)
    program['id'] = 'ticket28-common-online-evidence-program'
    program['nominal_knowledge']['id'] = NOMINAL
    program['decision_times_s'] = TIMES
    policy = program['policy_program']
    policy['id'] = 'ticket28-finite-evidence-consistent'
    # The public offered demand is shared with the actual cases. Normalized
    # deficit and the prior six-second contingent loss literals are unchanged.
    policy['options']['catalog']['demand'][0]['rate'] = .5
    program['closure_program']['risk_catalog'] = deepcopy(policy['options']['catalog'])
    sensors = program['sensor_program']['profile']
    for instrument in sensors['measurements']:
        if instrument['id'] in {'lake-flow', 'joint-service-meter'}:
            instrument['phase_s'] = 5
    policy['evidence_projection']['background_sensor_profile'] = deepcopy(sensors)
    for check in program['closure_program']['profile']['rules'][0]['checks']:
        if check['role'] == 'service':
            check['accepted_interval'] = [.5, .5]
    ledger = program['evidence_ledger']
    add_registration(ledger, 'observables', dict(id='cooling-review-28', quantity='category', value_type='text', unit='1'))
    add_registration(ledger, 'sources', dict(id='authorized-reviewer-28', kind='human_report', basis='synthetic_assumption',
        target_ids=['intake_pump'], observable_ids=['cooling-review-28'], dependency_group=None,
        source_note='Declared synthetic review input after two actual flow and two actual service samples; not generated human cognition.'))
    closure = program['closure_program']['profile']
    closure['review_channels'] = [dict(id='cooling-disposition-28', question_id='cooling',
        source_id='authorized-reviewer-28', target_id='intake_pump', observable_id='cooling-review-28', authorization_id='risk-owner-28')]
    closure['authorizations'] = [dict(id='risk-owner-28', source_id='authorized-reviewer-28', question_ids=['cooling'],
        dispositions=['FALSE_ALARM'], starts_at_s=0, expires_at_s=10, basis='synthetic_assumption',
        source_note='Synthetic authority to review an erroneous suspicion, not repair authority.')]
    closure['false_alarm_reviews'] = [dict(review_record_id='false-alarm-review-28', question_id='cooling',
        supporting_record_ids=['flow-transfer:0', 'flow-transfer:1', 'joint-service-transfer:0', 'joint-service-transfer:1'],
        rationale='Declared reviewer checks the false work-order suspicion against these four actually sampled, already available records.')]
    ledger['records'] = []
    return model, program


def false_report(program):
    ledger = program['evidence_ledger']
    ledger['records'] = [
        dict(id='delayed-lake-work-order', source_id='lake-work-order-source', target_id='filter',
            observable_id='lake_flow_suspected', unit='1', value=True, observed_at_s=1.5, arrived_at_s=3,
            valid_until_s=10, quality=dict(status='reported', error_bound=None, note='Fixed erroneous operator suspicion; physical state remains healthy.'),
            provenance=dict(origin_id='operator-lake-false-suspicion-28', copied_from_record_id=None)),
        dict(id='false-alarm-review-28', source_id='authorized-reviewer-28', target_id='intake_pump',
            observable_id='cooling-review-28', unit='1', value='FALSE_ALARM', observed_at_s=6.75, arrived_at_s=7,
            valid_until_s=10, quality=dict(status='reported', error_bound=None, note='Declared review decision; independently gated on real arrived evidence.'),
            provenance=dict(origin_id='authorized-cooling-review-28', copied_from_record_id=None)),
    ]


def late_case(reference):
    model = deepcopy(reference['model'])
    change_parameters(model, dict(service_demand=1, network_service_capacity=.25, storage_service_capacity=1,
                                  filter_resistance_multiplier=1, pump_min_speed=1, ups_in_service=1))
    for entity in model['entities']:
        if entity['id'] in {'worker_it', 'tool_it_diagnostic'}:
            entity['location_id'] = 'loc_control'
            entity['source_note'] = 'Both worker and required tool start at control in this finite synthetic case.'
    inherited = reference['replay_inputs']['dispatch_program']
    nominal = deepcopy(inherited['nominal_knowledge'])
    nominal['id'] = NOMINAL
    for entity in nominal['entities']:
        if entity['id'] in {'worker_it', 'tool_it_diagnostic'}:
            entity['nominal_location_id'] = 'loc_control'
    workforce = deepcopy(inherited['policy_program']['workforce_profile'])
    workforce['nominal_knowledge_id'] = NOMINAL
    task = dict(id='late-network-action-28', work_interface_id='inspect_it_service', target_id='network',
        crew=[dict(worker_id='worker_it', qualification_id='qualified_it_inspection')], tool_carrier_id='worker_it',
        deadline_s=4, source_note='One report-triggered research work intention; private future gate state is not a planning input.')
    action = deepcopy(inherited['intervention_program'])
    change_nominal(action)
    operation = action['profile']['operations'][0]
    operation.update(id='network-restore-28', kind='restore_network_capacity', target_id='network',
                     minimum_work_s=1, source_note='Bounded named network repair; unsuccessful work has no parameter effect.')
    action['profile']['authorizations'][0].update(operation_ids=[operation['id']], target_ids=['network'])
    action['bindings'][0].update(task_id=task['id'], operation_id=operation['id'], setting=1)
    ledger = deepcopy(inherited['evidence_ledger'])
    ledger['records'] = []
    add_registration(ledger, 'observables', dict(id='network-service-suspected-28', quantity='binary', value_type='boolean', unit='1'))
    add_registration(ledger, 'sources', dict(id='network-work-order-28', kind='work_order', basis='synthetic_assumption',
        target_ids=['network'], observable_ids=['network-service-suspected-28'], dependency_group=None,
        source_note='Delayed operator report, not a network-capacity or gate-truth channel.'))
    add_registration(ledger, 'observables', dict(id='network-capacity-observed-28', quantity='service_capacity', value_type='number', unit='1'))
    add_registration(ledger, 'sources', dict(id='network-check-28', kind='human_report', basis='synthetic_assumption',
        target_ids=['network'], observable_ids=['network-capacity-observed-28'], dependency_group=None,
        source_note='Declared potential later check channel; no measurement exists in this failed-work case.'))
    add_registration(ledger, 'observables', dict(id='service-rate-observed-28', quantity='service_capacity', value_type='number', unit='1'))
    add_registration(ledger, 'sources', dict(id='service-check-28', kind='human_report', basis='synthetic_assumption',
        target_ids=['critical_service'], observable_ids=['service-rate-observed-28'], dependency_group=None,
        source_note='Potential later service check; no record is invented from evaluator truth.'))
    ledger['records'] = [dict(id='delayed-network-work-order-28', source_id='network-work-order-28', target_id='network',
        observable_id='network-service-suspected-28', unit='1', value=True, observed_at_s=0, arrived_at_s=1, valid_until_s=5,
        quality=dict(status='reported', error_bound=None, note='Declared suspicion triggers the single authorized work intention.'),
        provenance=dict(origin_id='network-operator-suspicion-28', copied_from_record_id=None))]
    closure = deepcopy(inherited['closure_program'])
    change_nominal(closure)
    closure['intervention_declaration'] = deepcopy(action)
    closure['risk_catalog'] = deepcopy(inherited['policy_program']['options']['catalog'])
    profile = closure['profile']
    profile.update(id='late-network-closure-28', review_channels=[], authorizations=[], false_alarm_reviews=[])
    rule = profile['rules'][0]
    rule.update(id='network-verification-28', question_id='it-dependence', task_id=task['id'], operation_id=operation['id'])
    rule['checks'] = [
        dict(id='network-restored-28', role='condition', target_id='network', observable_id='network-capacity-observed-28',
            source_ids=['network-check-28'], accepted_interval=[1, 1]),
        dict(id='service-restored-28', role='service', target_id='critical_service', observable_id='service-rate-observed-28',
            source_ids=['service-check-28'], accepted_interval=[1, 1]),
    ]
    return dict(kind='report_triggered_crew', duration_s=4, maximum_step_s=.01, model=model,
        boundary_events=[dict(time_s=3, parameter_id='it_access_permit', value=0,
                             source_note='Private exogenous safety gate closes while the already issued crew is working.')],
        public_preparation=dict(nominal_knowledge=nominal, evidence_ledger=ledger,
            decision_times_s=[0, 1, 3.25, 4], trigger_record_id='delayed-network-work-order-28', issued_at_s=1,
            task=task, workforce_profile=workforce),
        intervention_program=action, closure_program=closure, closure_assessment_times_s=[3.25, 4])


def ratio(value):
    value = Fraction(value)
    return {'numerator': value.numerator, 'denominator': value.denominator}


def literals():
    prior = Fraction(1, 100)
    reported = prior * Fraction(3, 4) / (prior * Fraction(3, 4) + (1-prior) * Fraction(3, 100))
    cleared = reported * Fraction(1, 5) / (reported * Fraction(1, 5) + (1-reported) * Fraction(9, 10))
    assert reported == Fraction(25, 124) and cleared == Fraction(50, 941)
    common = dict(demand_service_unit_s=ratio(Fraction(1, 2)*Fraction(29, 4)),
                  delivered_service_unit_s=ratio(Fraction(29, 8)), normalized_deficit_s=ratio(0))
    return dict(schema='aegisdc-negative-control-independent-literals-v1', source='Fraction-only inventory/service/timing arithmetic before execution',
        normal={**common, 'work_person_s': ratio(0), 'access_check_person_s': ratio(0), 'travel_person_s': ratio(0)},
        false_report={**common, 'work_person_s': ratio(1), 'access_check_person_s': ratio(Fraction(1, 4)),
            'travel_person_s': ratio(0), 'cooling_probability_after_report': ratio(reported),
            'cooling_probability_after_negative_handheld': ratio(cleared),
            'inspection_completed_s': ratio(Fraction(17, 4)), 'inspection_arrived_s': ratio(Fraction(19, 4))},
        local_protection=dict(demand_service_unit_s=ratio(Fraction(3, 4)*3),
            delivered_service_unit_s=ratio(Fraction(3, 4)*2), normalized_deficit_s=ratio(1),
            work_person_s=ratio(0), access_check_person_s=ratio(0), travel_person_s=ratio(0),
            protection_sample_s=ratio(1), conditional_reset_s=ratio(2)),
        too_late=dict(demand_service_unit_s=ratio(4), delivered_service_unit_s=ratio(Fraction(1, 4)*4),
            normalized_deficit_s=ratio((1-Fraction(1, 4))*4), travel_person_s=ratio(1),
            access_check_person_s=ratio(Fraction(1, 4)), work_person_s=ratio(Fraction(3, 4)),
            theoretical_earliest_completion_s=ratio(1+1+Fraction(1, 4)+1), safety_abort_s=ratio(3),
            terminal_feedback_arrives_s=ratio(Fraction(7, 2))),
        fixed_head_flows=dict(clean_volume_flow_squared_m6_s2=ratio(Fraction(1, 100)), clean_mass_flow_kg_s=ratio(Fraction(499, 5))),
        total_integrations=4, total_simulated_duration_s=ratio(Fraction(29, 4)*2+3+4),
        public_online_decisions=14, late_preparation_frames=4, late_closure_assessments=2,
        caveat='Demand and timing arithmetic is analytic. Thermodynamic admissibility and the conditional local reset must be checked against actual independent saved trajectories; no global bound is claimed.')


def main():
    assert not DESTINATION.exists(), 'Prepare once into a new durable input directory'
    reference = read(ROOT / REFERENCE)
    model, normal = common_online(reference)
    false = deepcopy(normal)
    false_report(false)
    # Physical inputs are exactly shared; report records are the only changed
    # online input. The selectors never see the private case label.
    cases = dict(
        normal=dict(kind='online_dispatch', duration_s=7.25, maximum_step_s=.01, model=deepcopy(model),
            replay_inputs=dict(schema='aegisdc-facility-replay-inputs-v2', seed=28, exogenous_events=[],
                               action_commands=[], work_requests=[], dispatch_program=normal)),
        false_report=dict(kind='online_dispatch', duration_s=7.25, maximum_step_s=.01, model=deepcopy(model),
            replay_inputs=dict(schema='aegisdc-facility-replay-inputs-v2', seed=28, exogenous_events=[],
                               action_commands=[], work_requests=[], dispatch_program=false)),
        local_protection=dict(kind='plant_without_manual_dispatch', duration_s=3, maximum_step_s=.01, model=deepcopy(model),
            boundary_events=[dict(time_s=t, parameter_id='internal_valve_opening', value=x,
                source_note='Declared exogenous shutoff/reopening; no manual command or protection bypass.')
                for t,x in ((.75,0),(1.25,1))]),
        too_late=late_case(reference),
    )
    change_parameters(cases['local_protection']['model'], dict(service_demand=.75))
    assert cases['normal']['model'] == cases['false_report']['model']
    original_graphs = reference['model']['graphs']
    assert all(case['model']['graphs'] == original_graphs for case in cases.values())
    assert len(reference['model']['domains']) == 8 and len(original_graphs) == 4
    oracle = literals()
    DESTINATION.mkdir(parents=True)
    write(DESTINATION / 'cases-v1.json', dict(schema='aegisdc-negative-control-cases-v1',
        classification='FINITE_FULL_FACILITY_NEGATIVE_ENGINEERING_NOT_EFFECT_COMPARISON',
        facility_id=model['id'], cases=cases))
    write(DESTINATION / 'literals-v1.json', oracle)
    write(DESTINATION / 'preparation.json', dict(status='PREPARED_NOT_EXECUTED', authoring_tool_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        source_inputs={name: sha256((ROOT / name).read_bytes()).hexdigest() for name in
            (REFERENCE, 'scripts/prepare_negative_control_inputs.py',
             'evidence/mainline/engineering/28-negative-controls/reference/static-check-observation.json')},
        outputs={name: sha256((DESTINATION / name).read_bytes()).hexdigest() for name in DURABLE[:-1]},
        source_inputs_role='Only prepared static inputs reused, no prior run trajectory or measured outcome used.',
        durable_files=list(DURABLE), new_project_calls=0, new_physical_calls=0, new_selector_calls=0, research_trials=0))
    print(json.dumps(dict(prepared=DESTINATION.relative_to(ROOT).as_posix(), cases=list(cases), new_physics=0, new_selectors=0)))


if __name__ == '__main__':
    main()
