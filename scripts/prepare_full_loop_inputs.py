"""Assemble the declared ticket 27 engineering world from immutable inputs only."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'evidence/mainline/engineering/26-candidate/reference/online-candidate-inspect.json'
FIXED_TEMPLATE = ROOT / 'configs/full-facility-sensor-channels-v1.json'
OUTPUT = ROOT / 'evidence/mainline/engineering/27-full-loop/reference/online-loop-v1.json'
NOMINAL = 'V6-27-lake-side-crew-engineering'


def load(path):
    return json.loads(path.read_bytes())


def fixed_measurements(program):
    sensor = program['sensor_program']
    profile, private = sensor['profile'], sensor['realization']
    original = load(FIXED_TEMPLATE)
    flow = next(row for row in original['measurements'] if row['id'] == 'lake-flow')
    flow.update(period_s=1, phase_s=7, declared_bias_bound=0, declared_noise_bound=0,
                quantization_bound=0, declared_dropout_probability=0)
    profile['measurements'] += [flow, dict(id='joint-service-meter', signal='joint_service_delivered', target_id='critical_service',
        period_s=1, phase_s=7, enabled=True, input_range=[0, 2], declared_bias_bound=0, declared_noise_bound=0,
        quantization_bound=0, declared_dropout_probability=0, calibration_group=None)]
    flow_channel = next(row for row in original['channels'] if row['id'] == 'flow-transfer')
    flow_channel.update(delay_s=.5, validity_s=3)
    profile['channels'] += [flow_channel, dict(id='joint-service-transfer', measurement_id='joint-service-meter',
        source_id='joint-service-record', observable_id='service_delivered_rate', transform='identity', threshold=None,
        delay_s=.5, validity_s=3, quality_mode='bounded')]
    profile['ledger']['sources'].append(dict(id='joint-service-record', kind='fixed_sensor', basis='synthetic_assumption',
        target_ids=['critical_service'], observable_ids=['service_delivered_rate'], dependency_group=None,
        source_note='Scheduled normalized delivery-rate instrument for this synthetic verification window.'))
    profile['ledger']['observables'].append(dict(id='service_delivered_rate', quantity='service_capacity', value_type='number', unit='1'))
    for name in ('biases', 'noise_bounds', 'dropout_probabilities'):
        private[name].update({'lake-flow': 0, 'joint-service-meter': 0})
    private['seed'] = 27
    return profile


def cooling_model(program):
    policy = program['policy_program']
    options = policy['options']
    model = options['belief_model']
    model['scope']['nominal_knowledge_id'] = NOMINAL
    work_order_channel = dict(id='lake-work-order', source_id='lake-work-order-source', target_id='filter',
        observable_id='lake_flow_suspected', unit='1', positive_when='true', threshold=None)
    # The finite updater supports one declared pair. Other records remain
    # in the public ledger without becoming factors in this cooling model.
    handheld = next(row for row in model['channels'] if row['id'] == 'lookahead-flow-channel')
    model['channels'] = [work_order_channel, handheld]
    model['independent_pairs'] = [['lake-work-order', handheld['id']]]
    for variant in model['variants']:
        variant['prior'] = [.74, .01, .125, .125]
        variant['positive_likelihood'] = {'lake-work-order': [.03, .75, .03, .03],
            handheld['id']: variant['positive_likelihood'][handheld['id']]}
        variant['basis'] = 'Finite engineering prior and same report law; the fixed power record is not a cooling-model factor.'
    options['catalog']['nominal_knowledge_id'] = NOMINAL
    options['value_model']['nominal_knowledge_id'] = NOMINAL
    return model


def main():
    reference = load(REFERENCE)
    model = reference['model']
    program = reference['dispatch_program']
    nominal = program['nominal_knowledge']
    nominal['id'] = NOMINAL
    program['id'] = 'ticket27-full-facility-recorded-loop-v1'
    program['decision_times_s'] = [1, 3, 4.5, 4.75, 6, 6.5, 7.5, 8.5]
    policy = program['policy_program']
    policy['id'] = 'ticket27-evidence-consistent-contingent'
    policy['workforce_profile']['nominal_knowledge_id'] = NOMINAL
    prior = cooling_model(program)
    parameters = {row['id']: row for row in model['parameters']}
    for key, value, note in (
        ('service_demand', .5, 'Starts at one-half; the external load rise to one is scheduled at 0.5 s.'),
        ('compute_demand_power', 2_000_000, 'Per-unit compute coefficient; the requested power is coefficient times demand, before supply and protection.'),
        ('network_service_capacity', 1, 'No permanent network restriction in this new restoration witness.'),
        ('storage_service_capacity', 1, 'Declared full nominal storage service capacity.'),
        ('filter_resistance_multiplier', 1, 'Starts clean; the external filter degradation at 1.5 s is separate from authorized cleaning.'),
        ('pump_min_speed', 1, 'Finite full-speed engineering assumption; all supply and local protection rules remain active.')):
        parameters[key].update(value=value, source_note=note + ' Synthetic engineering assumption, no site calibration.')
    sensors = fixed_measurements(program)
    registry = program['evidence_ledger']
    registry['sources'] = [row for row in registry['sources'] if row['id'] not in {'service-review', 'verify-flow'}]
    registry['observables'] = [row for row in registry['observables'] if row['id'] != 'service_delivery_ratio']
    registry['sources'].append(dict(id='lake-work-order-source', kind='work_order', basis='synthetic_assumption',
        target_ids=['filter'], observable_ids=['lake_flow_suspected'], dependency_group='lake-work-order-process',
        source_note='Delayed operator suspicion; reported, not a physical fault label or a calibrated measurement.'))
    registry['observables'].append(dict(id='lake_flow_suspected', quantity='binary', value_type='boolean', unit='1'))
    registry['records'] = [dict(id='delayed-lake-work-order', source_id='lake-work-order-source', target_id='filter',
        observable_id='lake_flow_suspected', unit='1', value=True, observed_at_s=1.5, arrived_at_s=3, valid_until_s=10,
        quality=dict(status='reported', error_bound=None, note='Synthetic finite work-order report with explicitly modeled errors.'),
        provenance=dict(origin_id='operator-lake-suspicion-27', copied_from_record_id=None))]
    inspection = program['inspection_program']
    binding = inspection['profile']['bindings'][0]
    binding.update(record_id='actual-lake-flow-before-action',
        provenance=dict(origin_id='actual-lake-flow-before-action', copied_from_record_id=None))
    projection = policy['evidence_projection']
    projection['inspection_profile'] = deepcopy(inspection['profile'])
    projection['background_sensor_profile'] = deepcopy(sensors)
    projection['report_class_support'][0]['record_id'] = binding['record_id']
    actions = program['intervention_program']
    action_profile = actions['profile']
    action_profile['nominal_knowledge_id'] = NOMINAL
    action_profile['operations'][0].update(id='ticket27-clean-filter', source_note='Named finite engineering cleaning; no service restoration claim.')
    action_profile['authorizations'][0]['operation_ids'] = ['ticket27-clean-filter']
    actions['bindings'][0].update(operation_id='ticket27-clean-filter', setting=1)
    policy['intervention_declaration'] = deepcopy(actions)
    closure = program['closure_program']
    closure['profile']['nominal_knowledge_id'] = NOMINAL
    closure['risk_catalog']['nominal_knowledge_id'] = NOMINAL
    closure['belief_model'] = deepcopy(prior)
    closure['intervention_declaration'] = deepcopy(actions)
    closure['intervention_feedback'] = []
    rule = closure['profile']['rules'][0]
    rule['operation_id'] = 'ticket27-clean-filter'
    rule['checks'][0].update(observable_id='lake_mass_flow', source_ids=['intake-flow-record'], accepted_interval=[99.7, 99.9])
    rule['checks'][1].update(observable_id='service_delivered_rate', source_ids=['joint-service-record'], accepted_interval=[1, 1])
    events = [dict(time_s=time, parameter_id=parameter, value=value, source_note=note) for time, parameter, value, note in (
        (.5, 'service_demand', 1, 'Offered service request rises, independently of what the plant can serve.'),
        (1, 'ups_in_service', 0, 'Declared UPS maintenance disables its bridge for this engineering window.'),
        (1.5, 'filter_resistance_multiplier', 4, 'Exogenous lake filter degradation, private to the facility.'),
        (2, 'grid_capacity', 0, 'Exogenous mains interruption; existing local protection remains in force.'),
        (3.4, 'grid_capacity', 10_000_000, 'Exogenous mains restoration; computation still awaits the local sampling rule.'))]
    prepared = dict(classification='NEW_TICKET27_ENGINEERING_INPUT_NOT_EFFECT_TRIAL', duration_s=10, maximum_step_s=.01,
        model=model, replay_inputs=dict(schema='aegisdc-facility-replay-inputs-v2', seed=27,
            exogenous_events=events, action_commands=[], work_requests=[], dispatch_program=program),
        source_inputs={path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
            for path in (REFERENCE, FIXED_TEMPLATE)},
        accounting_note='Forecast duration is six relative seconds. Actual duration is ten seconds. No physics/selector ran during assembly.')
    with OUTPUT.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(prepared, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(prepared=OUTPUT.relative_to(ROOT).as_posix(), new_physics=0, new_selector_calls=0)))


if __name__ == '__main__':
    main()
