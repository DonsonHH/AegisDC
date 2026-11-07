"""Preregistered public masks with an unchanged, fully capable private executor."""
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

ARMS=('full','without_nonfixed_context','without_dependency_context','without_joint_crew_planning')

def fingerprint(value):
    return sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def planner_view(program,mask):
    if mask not in ARMS:raise ValueError('Unknown registered ablation mask')
    result=deepcopy(program);policy=result['policy_program'];options=policy['options']
    if mask=='without_nonfixed_context':
        records=result['evidence_ledger']['records']
        removed={r['id'] for r in records if r['source_id']=='operator-report'}
        while True:
            descendants={r['id'] for r in records if r['provenance']['copied_from_record_id'] in removed}
            if descendants<=removed:break
            removed|=descendants
        result['evidence_ledger']['records']=[r for r in records if r['id'] not in removed]
    elif mask=='without_dependency_context':
        removed={'f12','f13','f14'}
        result['nominal_knowledge']['graphs']['functional']=[e for e in result['nominal_knowledge']['graphs']['functional'] if e['id'] not in removed]
        for question in options['catalog']['questions']:
            question['dependency_edge_ids']=[e for e in question['dependency_edge_ids'] if e not in removed]
        def compute_only(capacity):
            value=capacity['compute'];capacity.update(compute=value,network=value,storage=value)
        for outcome in options['catalog']['outcomes']:
            for segment in outcome['capacity_profile']:compute_only(segment['capacities'])
        for model in options['value_model']['question_models']:
            for variant in model['variants']:
                for stage in ('during_capacity','after_capacity'):
                    for capacity in variant[stage].values():compute_only(capacity)
    elif mask=='without_joint_crew_planning':
        removed={c['id'] for c in policy['candidates'] if len(c['task']['crew'])>1}
        affected={b['question_id'] for b in options['bindings'] if b['intervention_candidate_id'] in removed}
        policy['candidates']=[c for c in policy['candidates'] if c['id'] not in removed]
        options['bindings']=[b for b in options['bindings'] if b['question_id'] not in affected]
        options['value_model']['question_models']=[q for q in options['value_model']['question_models'] if q['question_id'] not in affected]
        for question in options['catalog']['questions']:
            if question['id'] in affected:
                question.update(quantification='UNMODELED',outcome_ids=[])
                question['evidence_gaps'].append('Joint intervention is unavailable to this planner; its incremental value remains unknown.')
        tasks={c['task']['id'] for c in policy['candidates']}
        declaration=policy['intervention_declaration']
        declaration['bindings']=[b for b in declaration['bindings'] if b['task_id'] in tasks]
        result['intervention_program']=deepcopy(declaration)
        projection=policy['evidence_projection']
        projection['report_class_support']=[r for r in projection['report_class_support'] if r['question_id'] not in affected]
    return result

@contextmanager
def planning_scope(session):
    previous=(session.program,session.nominal,session.ledger,session.intervention_program)
    view=session.planner_program
    session.program=view;session.nominal=view['nominal_knowledge'];session.ledger=view['evidence_ledger']
    session.intervention_program=view['intervention_program']
    from aegis_dc import risk_scenarios
    original_validator=risk_scenarios._catalog_for_frame
    if session.mask=='without_dependency_context':
        # Existing shape validation derives vector identities from the three
        # edges this registered mask removes. Rebind identities for validation
        # only. Belief, consequences, projections, choices and recorded frames
        # still receive the masked frame and compute-only capacity vectors.
        identity_edges=[deepcopy(e) for e in session.execution_program['nominal_knowledge']['graphs']['functional']
                        if e['id'] in {'f12','f13','f14'}]
        if len(identity_edges)!=3:raise ValueError('Registered component identity bindings differ')
        def catalog_shape(catalog,frame,belief):
            graph=frame['nominal_knowledge']['graphs']['functional']
            if any(e['id'] in {'f12','f13','f14'} for e in graph):raise ValueError('Masked dependency edge reached planning')
            if set(catalog['service_component_ids'])!={'compute','network','storage'}:raise ValueError('Masked component identities differ')
            if any(set(q['dependency_edge_ids'])&{'f12','f13','f14'} for q in catalog['questions']):
                raise ValueError('Masked question regained its removed dependency bindings')
            for outcome in catalog['outcomes']:
                for row in outcome['capacity_profile']:
                    c=row['capacities']
                    if not c['compute']==c['network']==c['storage']:raise ValueError('Masked consequence is not compute-only')
            validation_frame=deepcopy(frame)
            validation_frame['nominal_knowledge']['graphs']['functional'].extend(identity_edges)
            session.catalog_shape_validations+=1
            return original_validator(catalog,validation_frame,belief)
        risk_scenarios._catalog_for_frame=catalog_shape
    try:yield
    finally:
        risk_scenarios._catalog_for_frame=original_validator
        session.program,session.nominal,session.ledger,session.intervention_program=previous

def session_type(mask,instances):
    from aegis_dc.policy_execution import PolicySession
    class MaskedSession(PolicySession):
        def __init__(self,program,duration_s):
            # The existing constructor validates the complete actual catalog,
            # projection, permissions, tools and observation producers first.
            super().__init__(program,duration_s)
            if self.closure_template is not None:raise ValueError('Registered masks use no closure policy')
            self.execution_program=deepcopy(program)
            self.planner_program=planner_view(program,mask)
            self.mask=mask;self.catalog_shape_validations=0
            self.private_submission_frames=[]
            instances.append(self)
        def process(self,time_s,workforce,inspections,interventions):
            session=self
            def actual_frame(frame,task,channel):
                from aegis_dc.decision_view import validate_current_frame
                value=deepcopy(frame)
                value['nominal_knowledge']=deepcopy(session.execution_program['nominal_knowledge'])
                validate_current_frame(value)
                session.private_submission_frames.append(dict(channel=channel,task_id=task['id'],as_of_s=frame['as_of_s'],
                    evidence_sha256=fingerprint(frame['evidence']),
                    planner_nominal_sha256=fingerprint(frame['nominal_knowledge']),
                    actual_nominal_sha256=fingerprint(value['nominal_knowledge'])))
                return value
            class WorkSubmissions:
                def public_feedback(self,at):return workforce.public_feedback(at)
                def submit(self,frame,task):return workforce.submit(actual_frame(frame,task,'WORK_SUBMIT'),task)
            class ActionIssues:
                def public_feedback(self,at):return interventions.public_feedback(at)
                def record_issue(self,frame,profile,task):return interventions.record_issue(actual_frame(frame,task,'ACTION_ISSUE'),profile,task)
            with planning_scope(self):
                return super().process(time_s,WorkSubmissions(),inspections,ActionIssues() if interventions is not None else None)
        def resource_ledger(self,*args,**kwargs):
            with planning_scope(self):return super().resource_ledger(*args,**kwargs)
    return MaskedSession

def audit_document(document):
    result=deepcopy(document)
    result['dispatch_program']=planner_view(document['dispatch_program'],document['ablation_mask'])
    return result

def execution_audit(session,mask):
    return dict(mask=mask,adapter_source='scripts/ablation_planner.py',
        adapter_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        actual_program_sha256=fingerprint(session.execution_program),
        planner_program_sha256=fingerprint(session.planner_program),
        schema_component_identity_validations=session.catalog_shape_validations,
        private_submission_frames=deepcopy(session.private_submission_frames),
        actual_catalog_task_ids=sorted(r['task']['id'] for r in session.catalog_program['submissions']),
        planner_candidate_ids=sorted(c['id'] for c in session.planner_program['policy_program']['candidates']),
        actual_binding_task_ids=sorted(b['task_id'] for b in session.execution_program['intervention_program']['bindings']),
        planner_binding_task_ids=sorted(b['task_id'] for b in session.planner_program['intervention_program']['bindings']))

def simulate_masked(document):
    from aegis_dc import policy_execution
    from aegis_dc.plant import simulate_scenario
    mask=document['ablation_mask'];instances=[]
    original=policy_execution.PolicySession
    policy_execution.PolicySession=session_type(mask,instances)
    try:
        result=simulate_scenario(document['model'],duration_s=document['duration_s'],
            step_s=document['maximum_step_s'],boundary_events=document['boundary_events'],
            dispatch_program=document['dispatch_program'])
    finally:policy_execution.PolicySession=original
    if len(instances)!=1:raise ValueError('Expected one explicit planner/executor adapter instance')
    session=instances[0]
    if session.program!=document['dispatch_program']:raise ValueError('Actual execution view was not restored')
    result['ablation_execution_audit']=execution_audit(session,mask)
    result['ablation_execution_audit']['actual_plant_sha256']=fingerprint(document['model'])
    return result
