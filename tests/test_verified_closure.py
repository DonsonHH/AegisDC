"""Question lifecycle from public arrived records, never evaluator truth."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from aegis_dc.decision_view import DecisionGateway
ROOT=Path(__file__).resolve().parents[1]

def fixture(as_of_s=6):
    load=lambda name:json.loads((ROOT/name).read_bytes())
    accepted=load('evidence/mainline/engineering/18-beliefs/capture-01/cli-frame.json')
    nominal=accepted['nominal_knowledge']
    ledger=dict(schema='aegisdc-evidence-ledger-v1',id=accepted['evidence']['ledger_id'],facility_id=accepted['facility_id'],
        basis='synthetic_assumption',time_unit='s',**accepted['evidence']['static_knowledge'],records=[])
    ledger['observables'].append(dict(id='service_delivery_ratio',quantity='service_capacity',value_type='number',unit='1'))
    for source,target,observable,kind in [('verify-flow','intake_pump','flow','handheld'),('service-review','critical_service','service_delivery_ratio','control_record')]:
        ledger['sources'].append(dict(id=source,kind=kind,basis='synthetic_assumption',target_ids=[target],observable_ids=[observable],
            dependency_group=source+'-chain',source_note='Explicit synthetic verification channel; no field calibration.'))
    for observed,arrival in [(4,4.5),(5,5.5)]:
        for source,target,observable,value,unit in [('verify-flow','intake_pump','flow',.09,'m3/s'),('service-review','critical_service','service_delivery_ratio',1,'1')]:
            identifier=source+'-'+str(observed)
            ledger['records'].append(dict(id=identifier,source_id=source,target_id=target,observable_id=observable,unit=unit,value=value,
                observed_at_s=observed,arrived_at_s=arrival,valid_until_s=10,quality=dict(status='bounded',error_bound=0,note='Exact finite engineering witness.'),
                provenance=dict(origin_id=identifier,copied_from_record_id=None)))
    plan=dict(schema='aegisdc-public-preparation-plan-v1',id='closure24',basis='synthetic_assumption',time_unit='s',decision_times_s=[as_of_s],requests=accepted['requests'])
    frame=DecisionGateway(nominal,ledger,plan).next_frame()
    profile=dict(schema='aegisdc-closure-profile-v1',id='closure24-engineering',facility_id=frame['facility_id'],
        nominal_knowledge_id=nominal['id'],risk_catalog_id='full-facility-risk-v1',basis='synthetic_assumption',time_unit='s',
        source_note='Finite sampled condition-and-service criterion, not continuous restoration.',rules=[dict(
            id='cooling-verification',question_id='cooling',opened_at_s=0,task_id='clean-filter',operation_id='clean-filter-operation',
            minimum_span_s=1,required_samples=2,checks=[
                dict(id='flow-restored',role='condition',target_id='intake_pump',observable_id='flow',source_ids=['verify-flow'],accepted_interval=[.08,.12]),
                dict(id='service-restored',role='service',target_id='critical_service',observable_id='service_delivery_ratio',source_ids=['service-review'],accepted_interval=[1,1])])])
    catalog=load('configs/full-facility-risk-scenarios-v1.json');profile['risk_catalog_id']=catalog['id']
    program=dict(schema='aegisdc-closure-program-v1',profile=profile,risk_catalog=catalog,belief_model=load('configs/full-facility-belief-model-v1.json'),
        intervention_feedback=[dict(task_id='clean-filter',operation_id='clean-filter-operation',source_id='intervention-execution-report',
            observed_at_s=3,arrived_at_s=3.5,outcome='APPLIED',reason=None,origin_id='intervention:clean-filter',coverage='THIS_AUTHORIZED_TASK_ONLY',risk_closed=False)])
    return frame,program,ledger,nominal

def reframe(ledger,nominal,time):
    accepted=json.loads((ROOT/'evidence/mainline/engineering/18-beliefs/capture-01/cli-frame.json').read_bytes())
    plan=dict(schema='aegisdc-public-preparation-plan-v1',id='closure24',basis='synthetic_assumption',time_unit='s',decision_times_s=[time],requests=accepted['requests'])
    return DecisionGateway(nominal,ledger,plan).next_frame()

class VerifiedClosureTests(unittest.TestCase):
    def test_conflicting_copy_cannot_be_ignored_to_keep_question_closed(self):
        from aegis_dc.verified_closure import assess_closure
        frame,program,ledger,nominal=fixture()
        copy=deepcopy(next(r for r in ledger['records'] if r['id']=='verify-flow-5'))
        copy.update(id='contradictory-copy',value=.01)
        copy['provenance']['copied_from_record_id']='verify-flow-5'
        ledger['records'].append(copy)
        result=assess_closure(reframe(ledger,nominal,6),program)['questions'][0]
        self.assertFalse(result['risk_closed'])
        self.assertIn('contradictory-copy',result['checks'][0]['insufficient_record_ids'])

    def test_action_completion_needs_post_action_condition_and_service_evidence(self):
        from aegis_dc.verified_closure import assess_closure
        frame,program,ledger,nominal=fixture();original=deepcopy((frame,program))
        result=assess_closure(frame,program);question=result['questions'][0]
        self.assertEqual(question['status'],'VERIFIED_CLOSED')
        self.assertTrue(question['risk_closed'])
        self.assertEqual(question['supporting_record_ids'],['service-review-4','service-review-5','verify-flow-4','verify-flow-5'])
        self.assertEqual(question['scope'],'DECLARED_FINITE_SAMPLED_CRITERIA_ONLY')
        self.assertEqual((frame,program),original)
        early=reframe(ledger,nominal,3.5)
        pending=assess_closure(early,program)['questions'][0]
        self.assertEqual(pending['status'],'ACTION_COMPLETED_PENDING_VERIFICATION')
        self.assertFalse(pending['risk_closed'])
        self.assertEqual(pending['supporting_record_ids'],[])

if __name__=='__main__':unittest.main()
