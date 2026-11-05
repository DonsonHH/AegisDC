"""Question lifecycle from public arrived records, never evaluator truth."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
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
    profile.update(review_channels=[],authorizations=[],false_alarm_reviews=[])
    catalog=load('configs/full-facility-risk-scenarios-v1.json');profile['risk_catalog_id']=catalog['id']
    program=dict(schema='aegisdc-closure-program-v1',profile=profile,risk_catalog=catalog,belief_model=load('configs/full-facility-belief-model-v1.json'),
        intervention_feedback=[dict(task_id='clean-filter',operation_id='clean-filter-operation',source_id='intervention-execution-report',
            observed_at_s=3,arrived_at_s=3.5,outcome='APPLIED',reason=None,origin_id='intervention:clean-filter',coverage='THIS_AUTHORIZED_TASK_ONLY',risk_closed=False)])
    declaration=load('evidence/mainline/engineering/23-interventions/reference/filter-later-inspection.json')['intervention_program']
    declaration['profile']['operations'][0]['id']='clean-filter-operation'
    declaration['profile']['authorizations'][0]['operation_ids']=['clean-filter-operation']
    declaration['bindings'][0].update(task_id='clean-filter',operation_id='clean-filter-operation')
    program['intervention_declaration']=declaration
    return frame,program,ledger,nominal

def reframe(ledger,nominal,time):
    accepted=json.loads((ROOT/'evidence/mainline/engineering/18-beliefs/capture-01/cli-frame.json').read_bytes())
    plan=dict(schema='aegisdc-public-preparation-plan-v1',id='closure24',basis='synthetic_assumption',time_unit='s',decision_times_s=[time],requests=accepted['requests'])
    return DecisionGateway(nominal,ledger,plan).next_frame()

class VerifiedClosureTests(unittest.TestCase):
    def test_current_same_signal_contradiction_blocks_even_outside_selected_sources(self):
        from aegis_dc.verified_closure import assess_closure
        frame,program,ledger,nominal=fixture()
        ledger['sources'].append(dict(id='sparse-fixed-flow',kind='fixed_sensor',basis='synthetic_assumption',target_ids=['intake_pump'],
            observable_ids=['flow'],dependency_group=None,source_note='Separate sparse fixed source in the same actual public signal scope.'))
        bad=deepcopy(next(r for r in ledger['records'] if r['id']=='verify-flow-5'))
        bad.update(id='fixed-flow-contradiction',source_id='sparse-fixed-flow',value=.01)
        bad['provenance']['origin_id']='fixed-flow-origin';ledger['records'].append(bad)
        result=assess_closure(reframe(ledger,nominal,6),program)['questions'][0]
        self.assertFalse(result['risk_closed'])
        self.assertIn('fixed-flow-contradiction',result['checks'][0]['insufficient_record_ids'])

    def test_rule_operation_must_bind_a_declared_intervention_task(self):
        from aegis_dc.verified_closure import assess_closure
        frame,program,_,_=fixture()
        program['profile']['rules'][0]['operation_id']='made-up-repair'
        program['intervention_feedback'][0]['operation_id']='made-up-repair'
        with self.assertRaises(ValueError):assess_closure(frame,program)

    def test_cli_assesses_only_the_declared_public_frame_and_closed_program(self):
        from aegis_dc.verified_closure import assess_closure
        frame,program,_,_=fixture()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'frame.json').write_text(json.dumps(frame),encoding='utf-8')
            (root/'program.json').write_text(json.dumps(program),encoding='utf-8')
            result=subprocess.run([sys.executable,'-B','-X','utf8','-m','aegis_dc.verified_closure',
                '--frame',str(root/'frame.json'),'--program',str(root/'program.json'),'--output',str(root/'out.json')],
                cwd=ROOT,capture_output=True,text=True,encoding='utf-8',env=dict(os.environ,PYTHONPATH=str(ROOT/'src')))
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue((root/'out.json').exists())
            self.assertEqual(json.loads((root/'out.json').read_bytes()),assess_closure(frame,program))
            private=deepcopy(program);private['actual_state']={'filter':1}
            with self.assertRaises(ValueError):assess_closure(frame,private)

    def test_missing_stale_copied_or_ambiguous_evidence_keeps_question_open(self):
        from aegis_dc.verified_closure import assess_closure
        for mode in ('missing-service','expired','future','copied','same-origin','ambiguous','pre-action','no-effect','no-feedback'):
            frame,program,ledger,nominal=fixture()
            if mode=='missing-service':ledger['records']=[r for r in ledger['records'] if r['source_id']!='service-review']
            elif mode=='expired':
                for row in ledger['records']:row['valid_until_s']=6
            elif mode=='future':
                for row in ledger['records']:row['arrived_at_s']=7
            elif mode in {'copied','same-origin'}:
                for row in ledger['records']:
                    if row['source_id']=='verify-flow' and row['observed_at_s']==5:
                        row['provenance']['origin_id']='verify-flow-4'
                        if mode=='copied':row['provenance']['copied_from_record_id']='verify-flow-4'
            elif mode=='ambiguous':
                for row in ledger['records']:
                    if row['source_id']=='verify-flow':row['quality']['error_bound']=.02
            elif mode=='pre-action':
                for index,row in enumerate(ledger['records']):row.update(observed_at_s=1+index/10,arrived_at_s=2)
            elif mode=='no-effect':program['intervention_feedback'][0].update(outcome='NO_EFFECT',reason='actual_work_not_completed')
            else:program['intervention_feedback']=[]
            with self.subTest(mode=mode):
                result=assess_closure(reframe(ledger,nominal,6),program)['questions'][0]
                self.assertFalse(result['risk_closed'])
                self.assertFalse(result['question_closed'])
                self.assertNotIn(result['status'],{'FALSE_ALARM_REVIEWED','RISK_ACCEPTED'})
        frame,program,_,_=fixture()
        program['intervention_feedback'][0]['arrived_at_s']=7
        with self.assertRaises(ValueError):assess_closure(frame,program)

    def test_false_alarm_needs_explicit_authorized_evidence_bound_review(self):
        from aegis_dc.verified_closure import assess_closure
        frame,program,ledger,nominal=fixture()
        program['intervention_feedback']=[]
        ledger['observables'].append(dict(id='cooling-review',quantity='category',value_type='text',unit='1'))
        ledger['sources'].append(dict(id='authorized-reviewer',kind='human_report',basis='synthetic_assumption',
            target_ids=['intake_pump'],observable_ids=['cooling-review'],dependency_group=None,source_note='Declared research review channel.'))
        ledger['records'].append(dict(id='false-alarm-review',source_id='authorized-reviewer',target_id='intake_pump',observable_id='cooling-review',unit='1',
            value='FALSE_ALARM',observed_at_s=5.5,arrived_at_s=5.75,valid_until_s=10,
            quality=dict(status='reported',error_bound=None,note='Reviewed original report; finite synthetic supporting record dossier.'),
            provenance=dict(origin_id='review-fa',copied_from_record_id=None)))
        program['profile']['review_channels']=[dict(id='cooling-disposition',question_id='cooling',source_id='authorized-reviewer',
            target_id='intake_pump',observable_id='cooling-review',authorization_id='risk-owner')]
        program['profile']['authorizations']=[dict(id='risk-owner',source_id='authorized-reviewer',question_ids=['cooling'],dispositions=['FALSE_ALARM'],
            starts_at_s=0,expires_at_s=10,basis='synthetic_assumption',source_note='Explicit synthetic review authority.')]
        program['profile']['false_alarm_reviews']=[dict(review_record_id='false-alarm-review',question_id='cooling',
            supporting_record_ids=['service-review-4','service-review-5','verify-flow-4','verify-flow-5'],
            rationale='Reviewer checked the originating suspicion against the listed finite records; no claim from normality alone.')]
        result=assess_closure(reframe(ledger,nominal,6),program)['questions'][0]
        self.assertEqual(result['status'],'FALSE_ALARM_REVIEWED')
        self.assertTrue(result['question_closed'])
        self.assertFalse(result['risk_closed'])
        self.assertFalse(result['physical_restoration_claim'])
        self.assertEqual(result['disposition_record_ids'],['false-alarm-review'])
        self.assertEqual(sorted(e['record_id'] for e in result['trace'] if e['event']=='VERIFICATION_RECORD_AVAILABLE'),
            ['service-review-4','service-review-5','verify-flow-4','verify-flow-5'])
        incomplete=deepcopy(program);incomplete['profile']['false_alarm_reviews'][0]['supporting_record_ids']=['verify-flow-4']
        pending=assess_closure(reframe(ledger,nominal,6),incomplete)['questions'][0]
        self.assertFalse(pending['question_closed'])
        self.assertNotEqual(pending['status'],'FALSE_ALARM_REVIEWED')
        adverse=deepcopy(next(r for r in ledger['records'] if r['id']=='verify-flow-5'))
        adverse.update(id='visible-adverse-flow',value=.01,observed_at_s=5.25,arrived_at_s=5.5)
        adverse['provenance']['origin_id']='adverse-flow-origin'
        ledger['records'].append(adverse)
        challenged=assess_closure(reframe(ledger,nominal,6),program)['questions'][0]
        self.assertFalse(challenged['question_closed'])
        self.assertNotEqual(challenged['status'],'FALSE_ALARM_REVIEWED')

    def test_authorized_risk_acceptance_is_not_verified_physical_restoration(self):
        from aegis_dc.verified_closure import assess_closure
        frame,program,ledger,nominal=fixture()
        ledger['records']=[]
        ledger['observables'].append(dict(id='cooling-review',quantity='category',value_type='text',unit='1'))
        ledger['sources'].append(dict(id='authorized-reviewer',kind='human_report',basis='synthetic_assumption',
            target_ids=['intake_pump'],observable_ids=['cooling-review'],dependency_group=None,source_note='Declared research authority channel.'))
        ledger['records'].append(dict(id='risk-acceptance',source_id='authorized-reviewer',target_id='intake_pump',observable_id='cooling-review',unit='1',
            value='ACCEPT_RISK',observed_at_s=4,arrived_at_s=4.5,valid_until_s=8,
            quality=dict(status='reported',error_bound=None,note='Authorized synthetic management disposition.'),
            provenance=dict(origin_id='accept-risk-1',copied_from_record_id=None)))
        program['profile']['review_channels']=[dict(id='cooling-disposition',question_id='cooling',source_id='authorized-reviewer',
            target_id='intake_pump',observable_id='cooling-review',authorization_id='risk-owner')]
        program['profile']['authorizations']=[dict(id='risk-owner',source_id='authorized-reviewer',question_ids=['cooling'],
            dispositions=['ACCEPT_RISK','ESCALATE'],starts_at_s=0,expires_at_s=8,basis='synthetic_assumption',source_note='Finite synthetic authority, not field authorization.')]
        result=assess_closure(reframe(ledger,nominal,6),program)['questions'][0]
        self.assertEqual(result['status'],'RISK_ACCEPTED')
        self.assertTrue(result['question_closed'])
        self.assertFalse(result['risk_closed'])
        self.assertFalse(result['physical_restoration_claim'])
        expired=assess_closure(reframe(ledger,nominal,8),program)['questions'][0]
        self.assertFalse(expired['question_closed'])
        self.assertNotEqual(expired['status'],'RISK_ACCEPTED')
        # An unresolved reported disposition cannot silently override escalation.
        escalation=deepcopy(ledger['records'][0]);escalation.update(id='escalate-risk',value='ESCALATE',observed_at_s=5,arrived_at_s=5.5)
        escalation['provenance']['origin_id']='escalate-risk-1';ledger['records'].append(escalation)
        raised=assess_closure(reframe(ledger,nominal,6),program)['questions'][0]
        self.assertEqual(raised['status'],'ESCALATED')
        self.assertFalse(raised['question_closed'])
        # A forged original which another visible copy identifies inconsistently
        # cannot become authority merely because it has no parent itself.
        ledger['records']=ledger['records'][:1]
        badcopy=deepcopy(ledger['records'][0]);badcopy['id']='mismatched-review-copy'
        badcopy['provenance']=dict(origin_id='different-review-origin',copied_from_record_id='risk-acceptance')
        ledger['records'].append(badcopy)
        tainted=assess_closure(reframe(ledger,nominal,6),program)['questions'][0]
        self.assertFalse(tainted['question_closed'])
        self.assertNotEqual(tainted['status'],'RISK_ACCEPTED')
        ledger['records']=ledger['records'][:1]
        keep=deepcopy(ledger['records'][0]);keep.update(id='keep-open-review',value='KEEP_OPEN')
        keep['provenance']['origin_id']='keep-open-origin';ledger['records'].append(keep)
        conflicted=assess_closure(reframe(ledger,nominal,6),program)['questions'][0]
        self.assertFalse(conflicted['question_closed'])
        self.assertNotEqual(conflicted['status'],'RISK_ACCEPTED')

    def test_genuine_verification_samples_need_distinct_observation_times(self):
        from aegis_dc.verified_closure import assess_closure
        frame,program,ledger,nominal=fixture()
        rule=program['profile']['rules'][0];rule['required_samples']=3
        extra=deepcopy(next(r for r in ledger['records'] if r['id']=='verify-flow-4'))
        extra.update(id='same-instant-other-report')
        extra['provenance']['origin_id']='other-reported-origin'
        ledger['records'].append(extra)
        result=assess_closure(reframe(ledger,nominal,6),program)['questions'][0]
        self.assertFalse(result['checks'][0]['passed'])
        self.assertEqual(result['checks'][0]['genuine_sample_count'],2)

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
