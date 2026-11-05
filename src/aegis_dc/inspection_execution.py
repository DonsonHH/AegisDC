"""Actual crew-completion inspection producer; plant state stays private."""
from copy import deepcopy
from fractions import Fraction
from .evidence_ledger import EvidenceLedger
from .nonfixed_evidence import (validate_nonfixed_profile, _measurement_result, _realization,
    _arrival, _finite, _plain, _text, SIGNALS)

PROFILE_FIELDS={'schema','id','facility_id','basis','source_note','nonfixed_profile','bindings'}
BINDING_FIELDS={'task_id','model_id','tool_id','qualification_id','minimum_work_s',
                'condition_range','confirmation_threshold','record_id','arrival_latency_s','validity_s','provenance'}

def require(ok,message):
    if not ok:raise ValueError(message)
def fields(v,n,label):require(type(v) is dict and set(v)==n,label+' fields differ from closed inspection contract')

class InspectionSession:
    """Private event consumer. Only detached arrived ledger/model data are public."""
    def __init__(self,scenario,work_program,program):
        _plain(program);fields(program,{'schema','profile','realizations'},'Inspection program')
        require(program['schema']=='aegisdc-inspection-program-v1','Unknown real inspection program')
        profile=program['profile'];fields(profile,PROFILE_FIELDS,'Inspection profile')
        require(profile['schema']=='aegisdc-inspection-profile-v1' and profile['basis']=='synthetic_assumption'
                and profile['facility_id']==scenario['id'],'Inspection facility/basis differs')
        for k in ('id','source_note'):_text(profile[k],k)
        self.profile=validate_nonfixed_profile(profile['nonfixed_profile'])
        require(self.profile['registry']['facility_id']==scenario['id'],'Inspection registry facility differs')
        entities={r['id']:r for r in scenario['entities']}
        require(set(self.profile['registry']['entity_ids'])==set(entities),'Inspection registry entity identities differ')
        models={r['model']['id']:r for r in self.profile['models']}
        tasks={r['task']['id']:r['task'] for r in work_program['submissions']}
        interfaces={r['id']:r for d in scenario['domains'] for r in d['work_interfaces']}
        require(type(profile['bindings']) is list,'Inspection bindings must be a list')
        self.bindings={};record_ids=set()
        for row in profile['bindings']:
            fields(row,BINDING_FIELDS,'Inspection binding')
            for k in ('task_id','model_id','tool_id','qualification_id','record_id'):_text(row[k],k)
            require(row['task_id'] in tasks and row['task_id'] not in self.bindings and row['model_id'] in models,'Unknown or repeated inspection task/model')
            require(row['record_id'] not in record_ids,'Duplicate inspection record identity');record_ids.add(row['record_id'])
            task=tasks[row['task_id']];model=models[row['model_id']];interface=interfaces[task['work_interface_id']]
            require(model['target_id']==task['target_id'],'Inspection measurement target must equal actual work target')
            require(row['tool_id'] in interface['tool_ids'] and row['tool_id'] in entities and entities[row['tool_id']]['kind']=='tool','Measurement tool must be occupied by the actual interface')
            require(row['qualification_id']==interface['qualification_id'],'Inspection qualification must match actual interface')
            require(_finite(row['minimum_work_s'],'Minimum inspection work')>0,'Inspection work must take positive time')
            require(_finite(row['arrival_latency_s'],'Measurement latency')>=0,'Inspection latency cannot be negative')
            require(_finite(row['validity_s'],'Measurement validity')>0,'Inspection validity must be positive')
            _finite(row['confirmation_threshold'],'Named-signal confirmation threshold')
            bounds=row['condition_range'];require(type(bounds) is list and len(bounds)==2,'Declare physical signal suitability range')
            low,high=(_finite(x,'Signal condition bound') for x in bounds);require(low<=high,'Suitability bounds reversed')
            fields(row['provenance'],{'origin_id','copied_from_record_id'},'Inspection provenance')
            _text(row['provenance']['origin_id'],'origin_id')
            if row['provenance']['copied_from_record_id'] is not None:_text(row['provenance']['copied_from_record_id'],'copied_from_record_id')
            self.bindings[row['task_id']]=dict(deepcopy(row),binding=deepcopy(model))
        require(type(program['realizations']) is dict and set(program['realizations'])==set(self.bindings),'Declare one private observation realization per inspection task')
        self.realizations={k:deepcopy(_realization(v)) for k,v in program['realizations'].items()}
        for task_id,realization in self.realizations.items():
            model=self.bindings[task_id]['binding']['model']
            if model['kind']=='binary_detection':
                require(realization['bias']==0 and realization['noise_half_width']==0,
                    'Binary threshold performance is separate from numeric bias/noise')

        self.ledger=EvidenceLedger(self.profile['registry']);self.events=[];self.feedback=[];self.attempts=[];self.produced=set();self.processed=set();self.last_time=-1

    def process(self,time_s,workforce,point):
        from .workforce_dispatch import CrewWorkforce
        require(type(workforce) is CrewWorkforce, 'Inspection completion must come from the actual private crew executor')
        work_records=workforce.records
        _finite(time_s,'Current inspection time')
        require(type(time_s) is not bool and time_s>=self.last_time and point['time_s']==time_s,'Inspection consumes only the current physical event point')
        self.last_time=time_s
        self.attempts=[dict(task_id=t['id'],task_status=t['status'],issued_at_s=t['issued_at_s'],
            arrived_at_s=t.get('arrived_at_s'),work_started_at_s=t.get('work_started_at_s'),
            completed_at_s=t.get('completed_at_s'),measurement_record_id=self.bindings[t['id']]['record_id']
                if t['id'] in self.produced else None)
            for t in work_records if t['id'] in self.bindings]
        for task in work_records:
            if task['id'] not in self.bindings or task['id'] in self.processed:continue
            if task['status'] not in {'completed','aborted','rejected'}:continue
            self.processed.add(task['id']);binding=self.bindings[task['id']]
            audit=dict(task_id=task['id'],task_status=task['status'],arrived_at_s=task.get('arrived_at_s'),
                work_started_at_s=task.get('work_started_at_s'),completed_at_s=task.get('completed_at_s'),
                disposition='NOT_CONFIRMED_NO_MEASUREMENT')
            if task['status']!='completed':self.events.append(audit);continue
            require(task['completed_at_s']==time_s,'Measurement cannot be created from a historical or future completion')
            duration=Fraction(time_s)-Fraction(task['work_started_at_s'])
            if duration<Fraction(binding['minimum_work_s']):
                self.events.append(dict(audit,disposition='WORK_INTERVAL_TOO_SHORT'));continue
            model=binding['binding']['model'];value=point['domains']
            for key in SIGNALS[model['signal_id']][2]:value=value[key]
            _finite(value,'Current authorized physical sample')
            condition_ok=binding['condition_range'][0]<=value<=binding['condition_range'][1]
            token=dict(source_id=binding['binding']['source_id'],target_id=binding['binding']['target_id'],
                observable_id=binding['binding']['observable_id'],completed_at_s=time_s,provenance=binding['provenance'])
            signal=dict(value=value,source_sample_at_s=time_s)
            if condition_ok:
                measured,quality,outcome,realization,draw=_measurement_result(model,token,signal,self.realizations[task['id']])
            else:
                measured,quality=None,dict(status='unknown',error_bound=None,note=model['quality_note'])
                outcome,realization,draw=dict(condition_suitable=False),None,None
            record=dict(id=binding['record_id'],source_id=token['source_id'],target_id=token['target_id'],observable_id=token['observable_id'],
                unit=model['unit'],value=measured,observed_at_s=time_s,arrived_at_s=_arrival(time_s,binding['arrival_latency_s']),
                valid_until_s=_arrival(time_s,binding['validity_s']),quality=quality,provenance=deepcopy(binding['provenance']))
            self.ledger.ingest(record)
            self.produced.add(task['id'])
            next(r for r in self.attempts if r['task_id']==task['id'])['measurement_record_id']=record['id']
            confirmation='UNCONFIRMED'
            threshold=Fraction(binding['confirmation_threshold'])
            if model['kind']=='numeric' and quality['status']=='bounded':
                low=Fraction(measured)-Fraction(quality['error_bound']);high=Fraction(measured)+Fraction(quality['error_bound'])
                if low>=threshold:confirmation='CONFIRMED_AT_OR_ABOVE_THRESHOLD'
                elif high<threshold:confirmation='CONFIRMED_BELOW_THRESHOLD'
            self.feedback.append(dict(task_id=task['id'],record_id=record['id'],
                observed_at_s=time_s,arrived_at_s=record['arrived_at_s'],confirmation=confirmation,
                scope='NAMED_SIGNAL_THRESHOLD_ONLY_NOT_FAULT_DIAGNOSIS',source_id=record['source_id'],
                target_id=record['target_id'],observable_id=record['observable_id']))

            self.events.append(dict(audit,disposition='CONDITION_OUTSIDE_DECLARED_RANGE' if not condition_ok else 'INDETERMINATE_READING' if model['kind']=='unknown' else 'OBSERVATION_REPORTED',
                record_id=record['id'],source_sample_at_s=time_s,authorized_raw_signal=value,
                private_realization=realization,private_draw=dict(numerator=draw.numerator,denominator=draw.denominator) if draw is not None else None,**outcome))

    def snapshot(self,as_of_s):
        _finite(as_of_s,'Inspection snapshot time')
        require(0<=as_of_s<=self.last_time,'Public inspection snapshot cannot query the future')
        return self.ledger.snapshot(as_of_s)
    def public_feedback(self,as_of_s):
        _finite(as_of_s,'Inspection feedback time')
        require(0<=as_of_s<=self.last_time,'Inspection feedback cannot query the future')
        return deepcopy([r for r in self.feedback if r['arrived_at_s']<=as_of_s])
    def public_models(self):
        return dict(schema='aegisdc-inspection-public-models-v1',
            nonfixed_profile=deepcopy(self.profile),
            bindings=[{k:deepcopy(v) for k,v in row.items() if k!='binding'} for row in self.bindings.values()],
            confirmation_scope='Named physical signal threshold with declared numeric bound; no fault or restoration claim',
            independence='NOT_ESTABLISHED',execution_permission=False)
    def private_audit(self):
        return dict(schema='aegisdc-inspection-private-audit-v1',classification='PRIVATE_PLANT_EVALUATOR_ONLY',events=deepcopy(self.events),attempts=deepcopy(self.attempts))
