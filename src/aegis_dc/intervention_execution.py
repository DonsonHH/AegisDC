"""Named, authorized research interventions after actual timed crew completion."""
from copy import deepcopy

from .decision_view import validate_current_frame
from .evidence_ledger import _plain_json
from .nonfixed_evidence import _arrival
from .thermodynamics import finite_number
from .workforce_dispatch import prepare_work

PROFILE_FIELDS={'schema','id','facility_id','nominal_knowledge_id','basis','source_note',
                'time_unit','feedback_latency_s','operations','authorizations'}
OP_FIELDS={'id','kind','target_id','unit','minimum_work_s','source_note'}
GRANT_FIELDS={'id','operation_ids','target_ids','starts_at_s','expires_at_s','basis','source_note'}
BIND_FIELDS={'task_id','operation_id','setting','authorization_id'}
# The parameter names cannot be supplied by an action caller. No inventory or
# energy-store reset, offered-demand write, or protection bypass is an operation.
OPERATIONS={
    'restore_network_capacity':('network','inspect_it_service','network_service_capacity','1'),
    'clean_filter':('filter','inspect_facility_cooling','filter_resistance_multiplier','1'),
    'adjust_compute_request':('compute','inspect_it_service','compute_demand_power','W'),
    'request_backup_cooling':('backup_tower','inspect_backup','backup_cooling_requested','1'),
}
# Public, versioned research domains for this operation catalog. These bounds
# describe supported inputs, not current actual capability or site calibration.
SETTING_BOUNDS={'restore_network_capacity':(0,2),'clean_filter':(.25,100),
                'adjust_compute_request':(0,5_000_000),'request_backup_cooling':(0,1)}

def require(ok,message):
    if not ok:raise ValueError(message)
def fields(value,names,label):
    require(type(value) is dict and set(value)==names,label+' differs from its closed contract')
def text(value,label):require(type(value) is str and bool(value.strip()),'Declare '+label)
def ids(values,label):
    require(type(values) is list,'Declare '+label+' list')
    for value in values:text(value,label)
    require(len(values)==len(set(values)),'Declare distinct '+label)
def registry(rows,label):
    require(type(rows) is list,'Declare '+label+' list')
    result={}
    for row in rows:
        require(type(row) is dict and 'id' in row,'Declare '+label+' identity')
        text(row['id'],label+' id');require(row['id'] not in result,'Duplicate '+label+' id')
        result[row['id']]=row
    return result

def _profile(profile,knowledge):
    _plain_json(profile);fields(profile,PROFILE_FIELDS,'Intervention profile')
    require(profile['schema']=='aegisdc-intervention-profile-v1' and profile['basis']=='synthetic_assumption'
            and profile['time_unit']=='s','Declare synthetic intervention profile in SI seconds')
    require(profile['facility_id']==knowledge['facility_id'] and profile['nominal_knowledge_id']==knowledge['id'],
            'Intervention/public facility identity differs')
    for key in ('id','source_note'):text(profile[key],key)
    require(finite_number(profile['feedback_latency_s'],'Feedback latency')>=0,'Negative feedback latency')
    interfaces={w['id']:w for w in knowledge['work_interfaces']}
    operations=registry(profile['operations'],'operation')
    require(bool(operations),'Declare at least one named operation')
    for op in operations.values():
        fields(op,OP_FIELDS,'Named operation');text(op['source_note'],'operation provenance')
        for key in ('kind','target_id','unit'):text(op[key],'operation '+key)
        require(op['kind'] in OPERATIONS,'Unsupported named operation kind')
        target,interface,_,unit=OPERATIONS[op['kind']]
        require(op['target_id']==target and op['unit']==unit and interface in interfaces
                and target in interfaces[interface]['target_ids'],'Operation target/unit/capability differs')
        finite_number(op['minimum_work_s'],'Minimum intervention work',positive=True)
    grants=registry(profile['authorizations'],'authorization')
    for grant in grants.values():
        fields(grant,GRANT_FIELDS,'Research authorization')
        require(grant['basis']=='synthetic_assumption','Declare research authority basis')
        text(grant['source_note'],'authorization provenance')
        ids(grant['operation_ids'],'authorized operations');ids(grant['target_ids'],'authorized targets')
        require(set(grant['operation_ids'])<=set(operations),'Unknown authorized operation')
        entities={e['id'] for e in knowledge['entities']}
        require(set(grant['target_ids'])<=entities,'Unknown authorized target')
        start=finite_number(grant['starts_at_s'],'Authorization start')
        end=finite_number(grant['expires_at_s'],'Authorization expiry')
        require(0<=start<end,'Authorization interval must be positive')
    return operations,grants

def _authorization(op,grant,time):
    return (op['id'] in grant['operation_ids'] and op['target_id'] in grant['target_ids']
            and grant['starts_at_s']<=time<grant['expires_at_s'])

def prepare_intervention(frame,workforce_profile,task,profile,binding):
    """Public proposal check: current records and declared authority, no plant query."""
    frame=validate_current_frame(frame);operations,grants=_profile(profile,frame['nominal_knowledge'])
    _plain_json(binding);fields(binding,BIND_FIELDS,'Intervention binding')
    for key in ('task_id','operation_id','authorization_id'):text(binding[key],'binding '+key)
    require(binding['task_id']==task['id'] and binding['operation_id'] in operations
            and binding['authorization_id'] in grants,'Unknown intervention task/operation/authority')
    setting=finite_number(binding['setting'],'Declared intervention setting')
    op=operations[binding['operation_id']];target,interface,_,_=OPERATIONS[op['kind']]
    low,high=SETTING_BOUNDS[op['kind']]
    require(low<=setting<=high,'Intervention setting outside named public research domain')
    if op['kind']=='request_backup_cooling':
        require(binding['setting'] in (0,1),'Backup selector request must be binary')
    require(task['target_id']==target and task['work_interface_id']==interface,'Operation must use its named work capability')
    result=prepare_work(frame,workforce_profile,task);reasons=list(result['public_reasons'])
    if workforce_profile['work_times_s'][interface]<op['minimum_work_s']:
        reasons.append('declared_professional_work_too_short')
    if not _authorization(op,grants[binding['authorization_id']],frame['as_of_s']):
        reasons.append('declared_authorization_unavailable_at_issue')
    result.update(legal_for_planning=not reasons,public_reasons=sorted(set(reasons)),
        operation_id=op['id'],authorization_id=binding['authorization_id'],execution_permission=False,
        physical_effect='NOT_EXECUTED',effect_gate='ACTUAL_CREW_COMPLETION_CURRENT_AUTHORITY_AND_PHYSICAL_DOMAIN')
    return result

class InterventionSession:
    """Private completion consumer; detached task-local feedback is its public view."""
    def __init__(self,scenario,work_program,program):
        _plain_json(program);fields(program,{'schema','profile','bindings'},'Intervention program')
        require(program['schema']=='aegisdc-intervention-program-v1','Unknown intervention program schema')
        submissions=work_program['submissions'];require(bool(submissions),'Interventions require actual issued crew tasks')
        nominal=submissions[0]['frame']['nominal_knowledge'];self.profile=deepcopy(program['profile'])
        self.operations,self.grants=_profile(self.profile,nominal)
        require(scenario['id']==self.profile['facility_id'],'Actual intervention facility differs')
        parameters={r['id']:r for r in scenario['parameters']};tasks={r['task']['id']:r for r in submissions}
        require(type(program['bindings']) is list,'Declare intervention bindings')
        self.bindings={};self.assessments={}
        for row in program['bindings']:
            fields(row,BIND_FIELDS,'Intervention binding')
            require(row['task_id'] in tasks and row['task_id'] not in self.bindings,'Unknown or repeated intervention task')
            submission=tasks[row['task_id']]
            assessment=prepare_intervention(submission['frame'],work_program['profile'],submission['task'],self.profile,row)
            op=self.operations[row['operation_id']];parameter=OPERATIONS[op['kind']][2]
            require(parameter in parameters and parameters[parameter]['unit']==op['unit'],'Actual parameter/unit unavailable')
            low,high=parameters[parameter]['valid_range']
            require(low<=row['setting']<=high,'Intervention setting outside declared physical domain')
            self.bindings[row['task_id']]=deepcopy(row);self.assessments[row['task_id']]=assessment
        self.events=[];self.feedback=[];self.processed=set();self.last_time=-1

    def record_issue(self,frame,workforce_profile,task):
        """Refresh a predeclared binding from its actual public issue frame."""
        if task['id'] not in self.bindings:return
        require(frame['as_of_s']==self.last_time and task['id'] not in self.processed,
                'Intervention intention must use the current unprocessed issue instant')
        self.assessments[task['id']]=prepare_intervention(frame,workforce_profile,task,self.profile,self.bindings[task['id']])

    def process(self,time,workforce,parameters):
        from .workforce_dispatch import CrewWorkforce
        require(type(workforce) is CrewWorkforce and workforce.last_time==time,'Use the actual current typed crew executor')
        finite_number(time,'Intervention time');require(time>=self.last_time,'Intervention clock cannot reverse');self.last_time=time
        effects=[]
        for task in workforce.records:
            if task['id'] not in self.bindings or task['id'] in self.processed or task['status'] not in {'completed','aborted','rejected'}:continue
            self.processed.add(task['id']);binding=self.bindings[task['id']];op=self.operations[binding['operation_id']]
            reason=None
            if task['status']!='completed':reason='actual_work_not_completed'
            elif task['completed_at_s']!=time:raise ValueError('Effects require current actual completion, not a saved or future token')
            elif not self.assessments[task['id']]['legal_for_planning']:reason='public_proposal_not_eligible'
            # Compare the same additive clock used to schedule crew completion.
            # Subtracting binary timestamps can turn a full declared second into
            # a value just below one (for example, a .2 start and 1.2 finish).
            elif time<task['work_started_at_s']+op['minimum_work_s']:reason='professional_work_too_short'
            elif not _authorization(op,self.grants[binding['authorization_id']],time):reason='authorization_unavailable_at_completion'
            audit=dict(task_id=task['id'],operation_id=op['id'],observed_at_s=time,task_status=task['status'],
                outcome='NO_EFFECT' if reason else 'APPLIED',reason=reason)
            if reason is None:
                parameter=OPERATIONS[op['kind']][2];old=parameters[parameter];new=binding['setting']
                parameters[parameter]=new
                audit.update(applied_at_s=time,parameter_id=parameter,old_value=old,new_value=new,
                             effect_scope='DECLARED_LOW_ORDER_PARAMETER_RESPONSE_NOT_VERIFIED_REPAIR')
                effects.append(deepcopy(audit))
            self.events.append(audit)
            self.feedback.append(dict(task_id=task['id'],operation_id=op['id'],source_id='intervention-execution-report',
                observed_at_s=time,arrived_at_s=_arrival(time,self.profile['feedback_latency_s']),
                outcome=audit['outcome'],reason=reason,origin_id='intervention:'+task['id'],
                coverage='THIS_AUTHORIZED_TASK_ONLY',risk_closed=False))
        return effects

    def public_feedback(self,as_of_s):
        finite_number(as_of_s,'Intervention feedback time');require(0<=as_of_s<=self.last_time,'Cannot query future intervention feedback')
        return deepcopy([r for r in self.feedback if r['arrived_at_s']<=as_of_s])
    def private_audit(self):
        return dict(classification='PRIVATE_PLANT_EVALUATOR_ONLY',events=deepcopy(self.events))
