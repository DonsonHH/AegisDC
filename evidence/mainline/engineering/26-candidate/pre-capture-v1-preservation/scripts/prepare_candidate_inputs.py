"""Prepare ticket26 finite engineering inputs; never execute the plant/selector."""
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from test_evidence_consistent_policy import fixture, informative_fixture, reframe
from test_evidence_consistent_execution import online_fixture
from test_verified_closure import fixture as closure_fixture

PACKAGE = 'evidence/mainline/engineering/26-candidate'
PROTOCOL = 'docs/mainline/26-candidate-engineering-protocol.json'


def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def exact(policy):
    policy['evidence_projection'].update(schema='aegisdc-evidence-projection-v3',
        valuation_mass_basis='EXACT_FINITE_PUBLIC_BELIEF_CONTEXT_V1')


def nonneutral(policy):
    for variant in policy['options']['belief_model']['variants']:
        variant['positive_likelihood']['fixed-low-power'] = [.1, .2, .9, .4]


def attach_closure(program):
    _, closure, registry, _ = closure_fixture()
    closure['intervention_feedback'] = []
    closure['intervention_declaration'] = deepcopy(program['intervention_program'])
    nominal = program['nominal_knowledge']['id']
    closure['profile']['nominal_knowledge_id'] = nominal
    closure['risk_catalog']['nominal_knowledge_id'] = nominal
    closure['belief_model']['scope']['nominal_knowledge_id'] = nominal
    rule = closure['profile']['rules'][0]
    rule.update(task_id='lookahead-action', operation_id=program['intervention_program']['bindings'][0]['operation_id'])
    rule['checks'][0].update(source_ids=['portable-intake-meter'], accepted_interval=[.07, .08])
    for field in ('sources', 'observables'):
        known = {row['id'] for row in program['evidence_ledger'][field]}
        program['evidence_ledger'][field].extend(deepcopy(row) for row in registry[field] if row['id'] not in known)
    program['closure_program'] = closure


def main():
    folder = ROOT / PACKAGE / 'reference'
    folder.mkdir(exist_ok=False)
    pure, physical = [], []

    def decision(name, frame, policy, history, expected):
        path = folder / (name + '.json')
        write(path, dict(classification='ENGINEERING_PUBLIC_DECISION_NOT_EFFECT_TRIAL',
            frame=frame, policy_program=policy, history=history))
        pure.append(dict(id=name, input=path.relative_to(ROOT).as_posix(), expected=expected))

    def plant(name, model, program, expected):
        path = folder / (name + '.json')
        write(path, dict(classification='ENGINEERING_ACTUAL_EXECUTION_NOT_EFFECT_TRIAL',
            model=model, dispatch_program=program))
        expected.update(demand_service_unit_s=6, delivered_service_unit_s=1.5, service_deficit_time_s=4.5)
        physical.append(dict(id=name, input=path.relative_to(ROOT).as_posix(), duration_s=6, expected=expected))

    for name in ('one_observation_lookahead', 'evidence_consistent_contingent'):
        frame, policy, history = fixture()
        policy['policy'] = name
        baseline = name == 'one_observation_lookahead'
        decision('nonadaptive-' + ('baseline' if baseline else 'candidate'), frame, policy, history,
            dict(chosen='first-inspection' if baseline else 'first-action',
                values=dict(inspect_then_act=[39, 40] if baseline else [3, 2], direct_intervention=[17, 16], defer=[3, 2]),
                classification=None if baseline else 'NON_ADAPTIVE_UNDER_DECLARED_UPDATER'))

    frame, policy, history = informative_fixture()
    policy['policy'] = 'evidence_consistent_contingent'
    decision('informative-candidate', frame, policy, history, dict(chosen='first-inspection',
        values=dict(inspect_then_act=[39, 40], direct_intervention=[17, 16], defer=[3, 2]),
        classification='INFORMATIVE_COMPATIBLE_WITH_DECLARED_UPDATER', positive=[8, 11], negative=[2, 29]))

    frame, policy, history = informative_fixture()
    policy['policy'] = 'evidence_consistent_contingent'
    policy['options']['belief_model']['independent_pairs'] = []
    records = deepcopy(frame['evidence']['records'])
    records[0]['valid_until_s'] = 1.75
    decision('neutral-expiry-boundary', reframe(frame, 0, records), policy, history,
        dict(chosen='first-inspection', values=dict(inspect_then_act=[39, 40]),
            classification='INFORMATIVE_COMPATIBLE_WITH_DECLARED_UPDATER', positive=[8, 11], negative=[2, 29]))

    frame, policy, history = informative_fixture()
    policy['policy'] = 'evidence_consistent_contingent'
    for variant in policy['options']['belief_model']['variants']:
        variant['prior'] = [.5, 0, 0, .5]
        variant['positive_likelihood']['lookahead-flow-channel'] = [.66, .24, .24, .24]
    keys = ('nominal', 'cooling-limited', 'power-limited', 'other')
    for outcome in policy['options']['catalog']['outcomes']:
        outcome['conditional_probability'] = dict(zip(keys,
            [.8, .2, .2, .2] if outcome['id'] == 'cooling-limited' else
            [.2, .8, .8, .8] if outcome['id'] == 'nominal' else [0, 0, 0, 0]))
    decision('coarse-outcome-mismatch', frame, policy, history, dict(chosen='first-action',
        values=dict(inspect_then_act=None), classification='UNMODELED',
        reason='IMPLEMENTATION_CONTEXT_OUTCOME_MASS_UNSUPPORTED',
        projected_positive=[16, 25], original_positive=[8, 9]))

    frame, policy, history = informative_fixture()
    policy['policy'] = 'evidence_consistent_contingent'
    policy['options']['belief_model']['variants'][0]['positive_likelihood']['fixed-low-power'] = [.1, .2, .9, .4]
    decision('legacy-representation-boundary', frame, policy, history, dict(chosen='first-action',
        values=dict(inspect_then_act=None), classification='UNMODELED', reason='VALUATION_REPRESENTATION_UNSUPPORTED',
        exact_current=[16, 59]))

    for name in ('one_observation_lookahead', 'evidence_consistent_contingent'):
        frame, policy, history = informative_fixture()
        policy['policy'] = name
        exact(policy)
        nonneutral(policy)
        baseline = name == 'one_observation_lookahead'
        decision('exact-' + ('baseline' if baseline else 'candidate'), frame, policy, history,
            dict(chosen='first-inspection', values=dict(inspect_then_act=[619, 590], direct_intervention=[63, 59], defer=[96, 59]),
                classification=None if baseline else 'INFORMATIVE_COMPATIBLE_WITH_DECLARED_UPDATER',
                common_exact=[16, 59], positive=None if baseline else [128, 171], negative=None if baseline else [32, 419]))

    frame, policy, history = informative_fixture()
    policy['policy'] = 'evidence_consistent_contingent'
    exact(policy)
    nonneutral(policy)
    policy['options']['belief_model']['independent_pairs'] = []
    records = deepcopy(frame['evidence']['records'])
    records[0]['valid_until_s'] = 1.5
    decision('nonneutral-expiry-context', reframe(frame, 0, records), policy, history, dict(chosen='first-action',
        values=dict(inspect_then_act=None), classification='UNMODELED', reason='IMPLEMENTATION_CONTEXT_OUTCOME_MASS_UNSUPPORTED',
        projected_positive=[8, 11], original_positive=[128, 171]))

    frame, policy, history = fixture()
    policy['policy'] = 'evidence_consistent_contingent'
    frame = reframe(frame, 1)
    other = deepcopy(policy['candidates'][0])
    other['id'] = 'other-inspection'
    other['task']['id'] = 'other-inspection-task'
    policy['candidates'].append(other)
    binding = deepcopy(policy['evidence_projection']['inspection_profile']['bindings'][0])
    binding.update(task_id=other['task']['id'], record_id='other-result',
        provenance=dict(origin_id='other-result', copied_from_record_id=None))
    policy['evidence_projection']['inspection_profile']['bindings'].append(binding)
    history['issued'] = [dict(candidate_id=other['id'], issued_at_s=0)]
    decision('pending-issued-inspection', frame, policy, history, dict(chosen='first-action',
        values=dict(inspect_then_act=None), classification='UNMODELED', reason='PENDING_INSPECTION_RECORD_JOINT_LAW_UNMODELED'))

    for label, name in (('candidate', 'evidence_consistent_contingent'), ('baseline', 'one_observation_lookahead')):
        model, program = online_fixture(name)
        attach_closure(program)
        plant('online-' + label + '-inspect', model, program, dict(chosen=['first-inspection', None, 'first-action', None],
            completed_at_s=[2.25, 4], work_started_at_s=[1.25, 3], effect_at_s=[4], polls=[0],
            work_person_s=2, spent=dict(person_s=20, tool_s=20, cost=2), handheld='bounded', closure_pending=True))

    model, program = online_fixture()
    for variant in program['policy_program']['options']['belief_model']['variants']:
        variant['positive_likelihood']['lookahead-flow-channel'] = [.5, .5, .5, .5]
    for variant in program['policy_program']['options']['value_model']['question_models'][0]['variants']:
        variant['positive_likelihood'] = dict.fromkeys(variant['positive_likelihood'], .5)
    plant('online-candidate-direct', model, program, dict(chosen=['first-action', None, None, None],
        completed_at_s=[2.25], work_started_at_s=[1.25], effect_at_s=[2.25], polls=[0],
        work_person_s=1, spent=dict(person_s=10, tool_s=10, cost=1), handheld=None,
        inspection_prediction=[3, 2], direct_prediction=[17, 16]))

    model, program = online_fixture()
    for variant in program['policy_program']['options']['belief_model']['variants']:
        variant['prior'] = [.5, 0, .25, .25]
    plant('online-candidate-defer', model, program, dict(chosen=[None] * 4,
        completed_at_s=[], work_started_at_s=[], effect_at_s=[], polls=[0], work_person_s=0,
        spent=dict(person_s=0, tool_s=0, cost=0), handheld=None,
        interpretation='Zero modeled impairment; actual service remains impaired. This is not a healthy-world claim.'))

    model, program = online_fixture(period=1)
    program['decision_times_s'] = [1]
    plant('online-known-fixed-arrival', model, program, dict(chosen=['first-action'], completed_at_s=[2.25],
        work_started_at_s=[1.25], effect_at_s=[2.25], polls=[0, 1, 2, 3, 4, 5, 6], work_person_s=1,
        spent=dict(person_s=10, tool_s=10, cost=1), handheld=None,
        first_reason='BACKGROUND_ARRIVAL_JOINT_LAW_UNMODELED'))

    model, program = online_fixture()
    program['inspection_program']['profile']['bindings'][0]['condition_range'] = [0, .01]
    program['policy_program']['evidence_projection']['inspection_profile'] = deepcopy(program['inspection_program']['profile'])
    plant('online-actual-indeterminate', model, program, dict(chosen=['first-inspection', None, 'first-action', None],
        completed_at_s=[2.25, 4], work_started_at_s=[1.25, 3], effect_at_s=[4], polls=[0], work_person_s=2,
        spent=dict(person_s=20, tool_s=20, cost=2), handheld='missing'))

    protocol = dict(schema='aegisdc-candidate-engineering-protocol-v1', ticket='26', status='FROZEN_ON_COMMIT_BEFORE_CAPTURE',
        classification='FINITE_ENGINEERING_INTERFACES_NOT_EFFECT_COMPARISON',
        pure_cases=pure, physical_cases=physical, pure_selector_calls=len(pure), physical_runs=len(physical),
        total_simulated_duration_s=sum(case['duration_s'] for case in physical), maximum_step_s=.01,
        scheduled_online_decision_calls=sum(len(json.loads((ROOT / case['input']).read_bytes())['dispatch_program']['decision_times_s']) for case in physical),
        authoring_tool='scripts/candidate_delivery.py', helper_tool='scripts/inspection_delivery.py',
        input_preparation_tool='scripts/prepare_candidate_inputs.py',
        contracts=['docs/mainline/26-evidence-consistent-candidate.md', 'docs/mainline/26-projection-law-next-slice.md',
            'docs/mainline/26-exact-valuation-basis-proposal.md', 'docs/mainline/26-online-policy-bridge-plan.md',
            'docs/mainline/26-finite-engineering-delivery.md'],
        same_public_pair=['nonadaptive-baseline', 'nonadaptive-candidate'],
        same_exact_pair=['exact-baseline', 'exact-candidate'],
        same_online_pair=['online-baseline-inspect', 'online-candidate-inspect'],
        durable_root=['attempt.json', 'attempts.jsonl', 'checks.json', 'actual-online.svg', 'decision-values.svg', 'candidate-boundary.svg'],
        durable_pure=['decision.json', 'computation.json'], durable_physical=['run.json', 'scenario.json', 'private-state.jsonl', 'balances.jsonl'],
        terminal_receipt='receipt.json', absolute_tolerance=1e-9, energy_tolerance_J=1e-4, mass_tolerance_kg=1e-9,
        retry_rule='One call per declared case; fsynced STARTED before invocation. Save original and check before next case. Any failure stops. No automatic retry or overwriting; correction requires a new explicit frozen protocol/source/output and complete attempt accounting.',
        durable_classification='Declared durable inputs, tools and outputs only. __pycache__, .pyc and .pyo are runtime caches and are not delivery evidence.',
        expected_source_rule='Execution at a clean committed revision, exact runtime/tool/input blob guards before and after all calls; saved verification checks original execution identity and delivery Git blobs.',
        registered_research_trials=0, llm_calls=0, training_calls=0, field_calibration='PENDING',
        full_regression='ONE_ROOT_INTEGRATED_RUN_AFTER_REVIEW',
        scope='One synthetic eight-domain V6 world, sparse fixed sensor continuing to poll, real crew/tool/measurement/action. Public declaration and actual information timing, constant-report/direct/defer and forecast-support counterexamples. Identical paired inputs except policy name. No policy superiority, field calibration, AI/RSI or complete M4 claim.',
        forecast_scope='Each catalog horizon is relative to the decision. Actual physical horizon is six seconds; network capacity0.25 limits all six worlds, so demand6/delivery1.5/deficit4.5 independently of filter cleaning.',
        oracle_scope='Literal independent Fraction, timing, hydraulic and service witnesses were prepared before capture. Expectations are not filled from captured outputs.')
    write(ROOT / PROTOCOL, protocol)
    print(json.dumps(dict(prepared_pure_cases=len(pure), prepared_physical_cases=len(physical),
        new_selector_calls=0, new_physical_runs=0, proposed_physical_duration_s=protocol['total_simulated_duration_s'])))


if __name__ == '__main__':
    main()
