"""One public discriminating witness for the declared candidate mechanism."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from aegis_dc.decision_view import DecisionGateway
from aegis_dc.dispatch_policy import choose_work
from aegis_dc.evidence_ledger import RECORD_FIELDS
from test_dispatch_policy import lookahead_run_fixture


def fixture():
    _,run=lookahead_run_fixture();policy=run['policy_program'];options=policy['options']
    catalog=options['catalog'];catalog['horizon_s']=6;catalog['demand']=[dict(start_s=0,end_s=6,rate=1)]
    for outcome in catalog['outcomes']:outcome['capacity_profile'][0]['end_s']=6
    for question in catalog['questions']:
        question['window_s']=[0,6]
        for quantity in ('service_deficit_time_s','unserved_service_unit_s'):
            question['consequence_bounds'][quantity]['interval']=[0,6]
    for resource in options['value_model']['availability']:resource['window_s']=[0,6]
    belief=options['belief_model']
    for variant in belief['variants']:variant['positive_likelihood']['fixed-low-power']=[.5,.5,.5,.5]
    ledger=deepcopy(run['evidence_ledger'])
    ledger['records']=[dict(id='current-power',source_id='rectifier-meter-record',target_id='rectifier',
        observable_id='rectifier_input_power',unit='W',value=3000000,observed_at_s=0,arrived_at_s=0,valid_until_s=10,
        quality=dict(status='bounded',error_bound=0,note='Finite current public engineering record.'),
        provenance=dict(origin_id='current-power-root',copied_from_record_id=None))]
    plan=dict(schema='aegisdc-public-preparation-plan-v1',id='candidate26-first-witness',basis='synthetic_assumption',
        time_unit='s',decision_times_s=[0],requests=options['preparation_requests'])
    # Register the same public measurement sources which actual execution uses.
    registry=run['inspection_program']['profile']['nonfixed_profile']['registry']
    for field in ('sources','observables'):
        ids={row['id'] for row in ledger[field]}
        ledger[field].extend(deepcopy(row) for row in registry[field] if row['id'] not in ids)
    frame=DecisionGateway(run['nominal_knowledge'],ledger,plan).next_frame()
    policy.update(schema='aegisdc-dispatch-policy-program-v4',intervention_declaration=run['intervention_program'],
        resource_budget=dict(person_s=100,tool_s=100,cost=2,cost_unit='research_cost_unit'),
        evidence_projection=dict(schema='aegisdc-evidence-projection-v1',basis='synthetic_assumption',
            source_note='Finite no-extra-arrival projection; no private realization or future value.',
            inspection_profile=deepcopy(run['inspection_program']['profile']),background_sensor_profile=None,
            context_assumption='NO_UNSCHEDULED_RECORD_ARRIVALS_UNTIL_PROJECTED_REPORT'))
    for candidate in policy['candidates']:candidate['issue_cost']=1
    local=options['value_model']['question_models'][0];local['inspection']['cost']=local['intervention']['cost']=1
    return frame,policy,dict(issued=[],work_feedback=[])


def reframe(frame,time,records=None):
    ledger=dict(schema='aegisdc-evidence-ledger-v1',id=frame['evidence']['ledger_id'],facility_id=frame['facility_id'],
        basis='synthetic_assumption',time_unit='s',**deepcopy(frame['evidence']['static_knowledge']),
        records=[{k:deepcopy(r[k]) for k in RECORD_FIELDS} for r in (frame['evidence']['records'] if records is None else records)])
    plan=dict(schema='aegisdc-public-preparation-plan-v1',id='candidate26-current-history',basis='synthetic_assumption',
        time_unit='s',decision_times_s=[time],requests=frame['requests'])
    return DecisionGateway(frame['nominal_knowledge'],ledger,plan).next_frame()


def informative_fixture():
    frame,policy,history=fixture()
    policy['options']['belief_model']['independent_pairs']=[['fixed-low-power','lookahead-flow-channel']]
    projection=policy['evidence_projection'];projection['schema']='aegisdc-evidence-projection-v2'
    projection['report_class_support']=[dict(question_id='cooling',inspection_task_id='lookahead-inspect',record_id='post-clean-flow',
        assumption='EVERY_MODELED_OUTCOME_COMPLETES_SUITABLY_AT_DECLARED_TIME_WITH_DECISIVE_BINARY_REPORT',
        source_note='Uncalibrated finite-domain forecast assumption applied to every enumerated world; actual producer unchanged.')]
    return frame,policy,history


class EvidenceConsistentPolicyTests(unittest.TestCase):
    def test_explicit_certain_report_domain_allows_compatible_independent_information(self):
        frame,policy,history=informative_fixture();before=deepcopy(policy)
        baseline=choose_work(frame,policy,history)
        self.assertEqual(baseline['chosen_candidate_id'],'first-inspection')
        policy['policy']='evidence_consistent_contingent'
        choice=choose_work(frame,policy,history)
        self.assertEqual(choice['chosen_candidate_id'],'first-inspection')
        self.assertAlmostEqual(choice['forecast_plans'][0]['best_expected_service_deficit_s'],39/40)
        audit=choice['prospective_evidence_audit'][0]
        self.assertEqual(audit['classification'],'INFORMATIVE_COMPATIBLE_WITH_DECLARED_UPDATER')
        self.assertEqual(audit['forecast_assumption'],before['evidence_projection']['report_class_support'][0]['assumption'])
        self.assertEqual(audit['zero_forecast_mass_report_classes'],['threshold_straddled','missing'])
        self.assertEqual(len(audit['compatibility_by_assumption']),4)
        for row in audit['compatibility_by_assumption']:
            self.assertEqual(row['status'],'MATCHED')
            positive=row['branches']['positive'];negative=row['branches']['negative']
            self.assertEqual(positive['projected_outcome_mass']['cooling-limited'],[8,11])
            self.assertEqual(negative['projected_outcome_mass']['cooling-limited'],[2,29])
        self.assertEqual(policy['options']['value_model'],before['options']['value_model'])
        self.assertEqual(policy['options']['catalog'],before['options']['catalog'])

    def test_work_below_measurement_minimum_is_legal_work_with_unknown_information_value(self):
        frame,policy,history=fixture();policy['policy']='evidence_consistent_contingent'
        policy['evidence_projection']['inspection_profile']['bindings'][0]['minimum_work_s']=2
        choice=choose_work(frame,policy,history)
        inspection=next(r for r in choice['candidates'] if r['candidate_id']=='first-inspection')
        self.assertTrue(inspection['public_assessment']['legal_for_planning'])
        audit=choice['prospective_evidence_audit'][0]
        self.assertEqual(audit['classification'],'UNMODELED')
        self.assertIn('DECLARED_WORK_BELOW_MEASUREMENT_MINIMUM',audit['reasons'])
        plan=next(r for r in choice['forecast_plans'][0]['alternatives'] if r['kind']=='inspect_then_act')
        self.assertIsNone(plan['expected_service_deficit_s'])

    def test_public_inspection_binding_rejects_wrong_target_tool_and_qualification(self):
        for mismatch in ('target','tool','qualification'):
            frame,policy,history=fixture();policy['policy']='evidence_consistent_contingent'
            binding=policy['evidence_projection']['inspection_profile']['bindings'][0]
            if mismatch=='target':
                policy['candidates'][0]['task']['target_id']='filter'
                request=next(r for r in frame['requests'] if r['id']=='intent-filter-check');request['target_id']='filter'
                policy['options']['preparation_requests']=deepcopy(frame['requests'])
            elif mismatch=='tool':binding['tool_id']='tool_it_diagnostic'
            else:binding['qualification_id']='qualified_it_inspection'
            with self.subTest(mismatch=mismatch),self.assertRaises(ValueError):choose_work(frame,policy,history)

    def test_background_profile_must_share_facility_entities_and_registry_for_every_v4_policy(self):
        original=json.loads((Path(__file__).resolve().parents[1]/'configs/full-facility-sensor-channels-v1.json').read_bytes())
        for name in ('one_observation_lookahead','evidence_consistent_contingent'):
            frame,policy,history=fixture();policy['policy']=name
            policy['evidence_projection']['background_sensor_profile']=deepcopy(original)
            choose_work(frame,policy,history)
            for mismatch in ('facility','entities','source','observable'):
                wrong=deepcopy(policy);registry=wrong['evidence_projection']['background_sensor_profile']['ledger']
                if mismatch=='facility':registry['facility_id']='another-synthetic-facility'
                elif mismatch=='entities':registry['entity_ids'].remove('loc_entry')
                elif mismatch=='source':registry['sources'][0]['source_note']='Another public registry definition.'
                else:
                    extra=deepcopy(registry['observables'][0]);extra['id']='unshared-background-observable'
                    registry['observables'].append(extra)
                with self.subTest(policy=name,mismatch=mismatch),self.assertRaises(ValueError):choose_work(frame,wrong,history)

    def test_positive_work_must_advance_the_actual_projected_binary64_measurement_clock(self):
        for now,work in ((1,float.fromhex('0x0.0000000000001p-1022')),(1e16,1)):
            frame,policy,history=fixture();policy['policy']='evidence_consistent_contingent'
            records=deepcopy(frame['evidence']['records'])
            records[0].update(observed_at_s=now,arrived_at_s=now,valid_until_s=now+10)
            frame=reframe(frame,now,records)
            scope=policy['options']['belief_model']['scope'];scope.update(starts_at_s=now,epoch_s=100)
            local=policy['options']['value_model']['question_models'][0]
            local['inspection'].update(travel_s=0,wait_s=0,work_s=work)
            local['intervention']['work_s']=work
            interface=policy['candidates'][0]['task']['work_interface_id']
            policy['workforce_profile']['work_times_s'][interface]=work
            policy['evidence_projection']['inspection_profile']['bindings'][0]['minimum_work_s']=work
            choice=choose_work(frame,policy,history)
            audit=choice['prospective_evidence_audit'][0]
            self.assertEqual(audit['predicted_observed_at_s'],now)
            self.assertEqual(audit['classification'],'UNMODELED')
            self.assertIn('PROJECTED_MEASUREMENT_CLOCK_NOT_ADVANCING',audit['reasons'])

    def test_another_issued_inspection_with_no_arrived_result_is_not_an_empty_future_context(self):
        frame,policy,history=fixture();frame=reframe(frame,1);policy['policy']='evidence_consistent_contingent'
        other=deepcopy(policy['candidates'][0]);other.update(id='other-inspection');other['task']['id']='other-inspection-task'
        policy['candidates'].append(other)
        binding=deepcopy(policy['evidence_projection']['inspection_profile']['bindings'][0])
        binding.update(task_id=other['task']['id'],record_id='other-result',provenance=dict(origin_id='other-result',copied_from_record_id=None))
        policy['evidence_projection']['inspection_profile']['bindings'].append(binding)
        history['issued']=[dict(candidate_id=other['id'],issued_at_s=0)]
        pending=choose_work(frame,policy,history)
        self.assertEqual(pending['prospective_evidence_audit'][0]['classification'],'UNMODELED')
        self.assertIn('PENDING_INSPECTION_RECORD_JOINT_LAW_UNMODELED',pending['prospective_evidence_audit'][0]['reasons'])
        inspected=next(r for r in pending['forecast_plans'][0]['alternatives'] if r['kind']=='inspect_then_act')
        self.assertIsNone(inspected['expected_service_deficit_s'])
        for status in ('aborted','rejected'):
            history['work_feedback']=[dict(task_id=other['task']['id'],source_id='workforce-execution-report',
                observed_at_s=.25,arrived_at_s=.75,status=status,reason='DECLARED_TASK_ADMISSION_REFUSAL' if status=='rejected' else 'DECLARED_ABORT',
                location_id=None,origin_id='workforce:'+other['task']['id'],coverage='THIS_ISSUED_TASK_ONLY',basis='SYNTHETIC_FINITE_TIMED_EXECUTION_CHANNEL')]
            choice=choose_work(frame,policy,history)
            self.assertEqual(choice['prospective_evidence_audit'][0]['classification'],'NON_ADAPTIVE_UNDER_DECLARED_UPDATER')

    def test_malformed_v4_options_and_nested_models_are_rejected_before_binding_or_projection_access(self):
        for path in (('bindings',),('value_model',),('value_model','question_models'),
            ('value_model','question_models',0,'inspection','work_s'),('belief_model','channels'),
            ('catalog','outcomes',0,'conditional_probability'),('bindings',0,'inspection_candidate_id')):
            frame,policy,history=fixture();policy['policy']='evidence_consistent_contingent'
            parent=policy['options']
            for key in path[:-1]:parent=parent[key]
            del parent[path[-1]]
            with self.subTest(path=path),self.assertRaises(ValueError):choose_work(frame,policy,history)

    def test_result_independent_rejection_removes_false_contingent_credit_without_changing_report_law(self):
        frame,policy,history=fixture();before=deepcopy((frame,policy,history))
        baseline=choose_work(frame,policy,history)
        self.assertEqual(baseline['chosen_candidate_id'],'first-inspection')
        self.assertAlmostEqual(baseline['forecast_plans'][0]['best_expected_service_deficit_s'],39/40)
        policy['policy']='evidence_consistent_contingent'
        candidate=choose_work(frame,policy,history)
        self.assertEqual(candidate['chosen_candidate_id'],'first-action')
        alternatives={row['kind']:row for row in candidate['forecast_plans'][0]['alternatives']}
        self.assertAlmostEqual(alternatives['direct_intervention']['expected_service_deficit_s'],17/16)
        self.assertAlmostEqual(alternatives['inspect_then_act']['expected_service_deficit_s'],3/2)
        audit=candidate['prospective_evidence_audit'][0]
        self.assertEqual(audit['classification'],'NON_ADAPTIVE_UNDER_DECLARED_UPDATER')
        self.assertEqual(audit['covered_report_classes'],['positive','negative','threshold_straddled','missing'])
        self.assertEqual(audit['unchanged_factor_record_ids'],['current-power'])
        self.assertEqual(audit['marginalization'],'SUM_ORIGINAL_REPORT_MASS_PER_JOINT_OUTCOME_EQUALS_ONE')
        self.assertFalse(candidate['forecast_is_actual_observation'])
        self.assertEqual(policy['options']['value_model'],before[1]['options']['value_model'])
        self.assertEqual((frame,history),(before[0],before[2]))


if __name__=='__main__':unittest.main()
