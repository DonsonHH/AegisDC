"""Fixed diagnostic opportunities, normal/unknown events and hidden-state privacy."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from patrol_rsi.contracts import digest
from aegis_dc.plant import save_run, simulate_scenario

ROOT=Path(__file__).resolve().parents[1]


class DiagnosticQualificationTests(unittest.TestCase):
    def run_case(self,identifier):
        variants=json.loads((ROOT/'tests/fixtures/39c-diagnostic-qualification-04.json').read_bytes())
        case=next(row for row in variants['cases'] if row['id']==identifier)
        descriptor=json.loads((ROOT/'tests/fixtures/39c-network-state-diagnostic.json').read_bytes())
        fixture=json.loads((ROOT/descriptor['base_fixture']).read_bytes())
        model=fixture['model'];parameters={row['id']:row for row in model['parameters']}
        if parameters['network_service_capacity']['value']!=case['capacity']:
            parameters['network_service_capacity']['value']=case['capacity']
        if parameters['service_demand']['value']!=case['demand']:
            parameters['service_demand']['value']=case['demand']
        dispatch=fixture['dispatch_program'];dispatch['schema']='aegisdc-policy-run-program-v4'
        dispatch['decision_times_s']=[0,1.75,2];dispatch['policy_program']['policy']=case['policy']
        dispatch['diagnostic_profile']=deepcopy(descriptor['public_profile'])
        inspection=dispatch['inspection_program']['profile']
        if case['error_bound']:
            for row in inspection['nonfixed_profile']['models']:
                row['model']['reported_error_bound']=case['error_bound']
                row['model']['quality_note']='Conservative reported bound1straddles the state threshold; actual signal and private realization unchanged.'
            dispatch['policy_program']['inspection_declaration']=deepcopy(inspection)
        business=deepcopy(descriptor['business_program']);business['id']+='-'+identifier
        event=business['events'][0]
        if case['truth_unmodeled']:
            profile=dispatch['diagnostic_profile'];profile['id']='network-unmodeled-cause-proxy'
            profile['rules'][0]['id']='network-cause-proxy'
            profile['rules'][0]['source_note']='A capacity finding only; no claim to identify a network root cause.'
            business['diagnostic_profile_id']=profile['id'];event['condition_id']='network-cause-proxy'
            event['id']='network-unmodeled-proxy-event'
            event['truth']={'kind':'UNMODELED','source_note':'No modeled mapping from the capacity finding to a network root cause; this event meaning is distinct from a scalar capacity fault.'}
        else:
            event['truth']['threshold']=case['truth_threshold']
            if identifier=='wrong-demand-model':
                dispatch['diagnostic_profile']['rules'][0]['source_note']='Deliberately wrong estimate of the actual offered-demand requirement: assumes1when the actual requirement is0.5. This is not a design-capacity maintenance alarm.'
                event['truth']['source_note']='Actual offered demand0.5is the normative requirement, while the public model remains1. Actual usable capacity0.5satisfies demand; nameplate0.75is not the measured signal.'
        values=dict(scenario_sha256=model,boundary_events_sha256=[],nominal_knowledge_sha256=dispatch['nominal_knowledge'],
            ledger_sha256=dispatch['evidence_ledger'],workforce_profile_sha256=dispatch['policy_program']['workforce_profile'],
            inspection_profile_sha256=inspection)
        for key,value in values.items():business['reference'][key]=digest(value)
        output=None
        if os.environ.get('AEGIS_ENGINEERING_RESULT_DIR'):
            output=Path(os.environ['AEGIS_ENGINEERING_RESULT_DIR'])/identifier;output.mkdir()
            with (output/'frozen-call-input.json').open('x',encoding='utf-8',newline='\n') as stream:
                json.dump(dict(model=model,dispatch_program=dispatch,business_program=business,duration_s=2,
                    step_s=.01,boundary_events=[]),stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
        self.facility_calls=getattr(self,'facility_calls',0)+1
        result=simulate_scenario(model,duration_s=2,step_s=.01,dispatch_program=dispatch,business_program=business)
        self.returned_decisions=getattr(self,'returned_decisions',0)+len(result['policy_public_decisions'])
        if output is not None:
            save_run(result,output/'actual-run')
            for name,value in [('business-result.json',result['business_evaluation']),('public-projection.json',[
                    dict(frame=row['frame'],condition_assessment=row['condition_assessment']) for row in result['policy_public_decisions']])]:
                with (output/name).open('x',encoding='utf-8',newline='\n') as stream:
                    json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
        return result

    def test_normal_reading_does_not_promote_an_external_claim_to_a_false_alarm(self):
        result=self.run_case('normal');evaluation=result['business_evaluation']
        self.assertEqual(result['policy_public_decisions'][0]['condition_assessment']['conditions'][0]['status'],'UNKNOWN')
        self.assertEqual(result['policy_public_decisions'][1]['condition_assessment']['conditions'][0]['status'],'NORMAL')
        self.assertEqual(evaluation['events'][0]['initial_truth'],'NORMAL')
        self.assertEqual(evaluation['counts']['normal_matured'],1)
        self.assertEqual(evaluation['counts']['false_positive_state_events'],0)
        self.assertEqual(evaluation['rates']['false_positive_state_events']['value'],0)
        self.assertIsNone(evaluation['rates']['missed_confirmation']['value'])

    def test_no_human_keeps_the_fault_opportunity_and_hides_truth_from_public_conditions(self):
        fault=self.run_case('no-human-fault');normal=self.run_case('no-human-normal')
        projections=lambda run:[dict(frame=row['frame'],condition_assessment=row['condition_assessment'])
                                for row in run['policy_public_decisions']]
        self.assertEqual(projections(fault),projections(normal))
        original=json.loads((ROOT/'tests/fixtures/39c-network-state-diagnostic.json').read_bytes())
        self.assertEqual(fault['business_evaluation']['reference'],original['business_program']['reference'])
        self.assertEqual(fault['business_evaluation']['counts']['eligible_fault_matured'],1)
        self.assertEqual(fault['business_evaluation']['counts']['missed_fault_confirmation'],1)
        self.assertEqual(fault['business_evaluation']['rates']['missed_confirmation']['value'],1)
        self.assertEqual(normal['business_evaluation']['events'][0]['initial_truth'],'NORMAL')
        self.assertEqual(normal['business_evaluation']['counts']['normal_matured'],1)
        self.assertEqual(fault['work_records'],[]);self.assertEqual(normal['work_records'],[])

    def test_wrong_demand_model_creates_one_false_state_event_without_falsifying_the_reading(self):
        result=self.run_case('wrong-demand-model');evaluation=result['business_evaluation']
        self.assertEqual(result['policy_public_decisions'][1]['condition_assessment']['conditions'][0]['status'],'ABNORMAL')
        self.assertEqual(evaluation['events'][0]['initial_truth'],'NORMAL')
        # Allocated power limits the usable scalar to min(nameplate.75,demand.5).
        # Original failed133274 assertion and saved-only correction133280 remain.
        self.assertEqual(evaluation['events'][0]['initial_private_value'],.5)
        self.assertEqual(evaluation['counts']['events_total'],1)
        self.assertEqual(evaluation['counts']['false_positive_state_events'],1)
        self.assertEqual(evaluation['rates']['false_positive_state_events']['denominator'],1)
        self.assertEqual(evaluation['rates']['false_positive_state_events']['value'],1)

    def test_bounded_interval_crossing_keeps_unknown_and_does_not_shrink_the_denominator(self):
        result=self.run_case('uncertain');evaluation=result['business_evaluation']
        assessment=result['policy_public_decisions'][1]['condition_assessment']['conditions'][0]
        self.assertEqual(assessment['status'],'UNKNOWN')
        self.assertEqual(assessment['supporting_record_ids'],['it-capacity-before'])
        self.assertEqual(evaluation['counts']['eligible_fault_matured'],1)
        self.assertEqual(evaluation['counts']['missed_fault_confirmation'],1)
        self.assertEqual(evaluation['rates']['missed_confirmation']['value'],1)

    def test_unmodeled_root_cause_mapping_is_not_inferred_from_a_capacity_finding(self):
        result=self.run_case('unmodeled-proxy');evaluation=result['business_evaluation']
        self.assertEqual(result['policy_public_decisions'][1]['condition_assessment']['conditions'][0]['status'],'ABNORMAL')
        self.assertEqual(evaluation['events'][0]['initial_truth'],'UNKNOWN')
        self.assertIsNone(evaluation['events'][0]['initial_private_value'])
        self.assertEqual(evaluation['counts']['events_total'],1)
        self.assertEqual(evaluation['counts']['truth_unknown'],1)
        self.assertIsNone(evaluation['rates']['false_positive_state_events']['value'])
        self.assertIsNone(evaluation['rates']['missed_confirmation']['value'])


if __name__=='__main__':unittest.main()
