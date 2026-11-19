"""Editorial assembly of complete JSON documents, content identities and literal expectations; no project import."""
from pathlib import Path
from copy import deepcopy as cp
import hashlib
import json
import subprocess

P=Path("docs/mainline/v6-intake-engineering-v1")
BASE=Path("evidence/mainline/engineering/39c-development/slice-53/green/joint/frozen-call-input.json")
CFG=Path("configs/full-facility-mainline-reserve-v6.json")
old=json.loads(BASE.read_bytes())
def dump(name,value):
    (P/name).write_bytes((json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+"\n").encode())
def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def getraw(path):
    return subprocess.check_output(['git','cat-file','blob','HEAD:'+path.as_posix()])
def fileid(path):
    return hashlib.sha256(getraw(path)).hexdigest()
def at(obj, path):
    for k in path: obj=obj[k]
    return obj
def patch(obj, edits):
    for path,value in edits:
        at(obj,path[:-1])[path[-1]]=cp(value)
def edits(a,b,path=()):
    if type(a)!=type(b) or isinstance(a,dict) and set(a)!=set(b) or isinstance(a,list) and len(a)!=len(b):
        return [[list(path),b]]
    if isinstance(a,(dict,list)):
        return [row for k in (a.keys() if isinstance(a,dict) else range(len(a))) for row in edits(a[k],b[k],(*path,k))]
    return [] if a==b else [[list(path),b]]
def bind(j):
    d=j['dispatch_program']; b=j['business_program']; pol=d['policy_program']
    pol['inspection_declaration']=cp(d['inspection_program']['profile']); pol['intervention_declaration']=cp(d['intervention_program'])
    d['closure_program']['intervention_declaration']=cp(d['intervention_program'])
    b['run_binding']=dict(scenario_sha256=digest(j['scenario']),dispatch_program_sha256=digest(d),
        boundary_events_sha256=digest(j['boundary_events']),action_commands_sha256=digest([]),
        duration_s=float(j['duration_s']),maximum_step_s=float(j['step_s']))
    ref=b['components']['diagnostic']['reference']
    for key,item in [('scenario',j['scenario']),('boundary_events',j['boundary_events']),('nominal_knowledge',d['nominal_knowledge']),
            ('ledger',d['evidence_ledger']),('workforce_profile',pol['workforce_profile']),('inspection_profile',d['inspection_program']['profile'])]:
        ref[key+'_sha256']=digest(item)
    return j

clock=[0,0.5,1,2,3.25,3.75,4,4.5,5,5.5,5.75,6,6.5,6.75,7,7.25,7.5,8,9,10]
low=[dict(prior_weights=[1,1,16],low_given_cause=[1,1,0]),dict(prior_weights=[1,2,14],low_given_cause=[1,1,0])]
high=[dict(prior_weights=[8,1,2],low_given_cause=[1,1,0])]
passive=[dict(prior_weights=[0,1,18],low_given_cause=[1,1,0])]
model=dict(schema='aegisdc-intake-value-v1',template_id='cooling-direct',clock_s=clock,service_window_s=[8,10],
           forecast_demand=1,first_travel_s=2,local_travel_s=0,flow_limits=[0,0.08,0.12,0.14],
           order_likelihood=[1,1,0.5],variants=low)
common=cp(old); d=common['dispatch_program']; b=common['business_program']; pol=d['policy_program']
common['duration_s']=10; d['decision_times_s']=clock;d['id']='v6-intake-engineering'
pol.update(schema='aegisdc-problem-driven-policy-v3',policy='intake_value',value_model=model)
pol['resource_budget']['cost']=3
pol['resource_budget']['person_s']=30; pol['resource_budget']['tool_s']=30
order=cp(d['evidence_ledger']['records'][0]); d['evidence_ledger']['records']=[order]
grant=d['intervention_program']['profile']['authorizations'][0]
grant['operation_ids']=['residual-clean']; operation=d['intervention_program']['profile']['operations'][0]
operation.update(id='residual-clean',source_note='Named filter resistance reset to its bounded residual multiplier only.')
for binding in d['intervention_program']['bindings']:binding['operation_id']='residual-clean'
for m in d['sensor_program']['profile']['measurements']:m['phase_s']=6
for field in ('authorizations','review_channels','false_alarm_reviews'): d['closure_program']['profile'][field]=[]
b['components']['instance_closure']['episodes']=cp(b['components']['instance_closure']['episodes'][:1])
b['components']['diagnostic']['events'][0]['timing']['sample_times_s']=clock
common['boundary_events']=[dict(time_s=0,parameter_id='network_service_capacity',value=0.5,source_note='Synthetic network derating.'),
    dict(time_s=2,parameter_id='network_service_capacity',value=1,source_note='External network capacity restored.')]
bind(common)
ix=next(i for i,x in enumerate(common['scenario']['parameters']) if x['id']=='filter_resistance_multiplier')
D=['dispatch_program']; PP=D+['policy_program']; V=PP+['value_model','variants']; BU=PP+['resource_budget']
LED=D+['evidence_ledger','records']; CL=['business_program','components','instance_closure','episodes']
A=D+['intervention_program','profile','authorizations',0,'expires_at_s']
INSP=D+['inspection_program','profile','bindings',0]; second=cp(old['dispatch_program']['evidence_ledger']['records'][2])
second.update(observed_at_s=0.5,arrived_at_s=0.5)
e2=cp(old['business_program']['components']['instance_closure']['episodes'][1]); e2['opened_at_s']=0.5
clone=cp(order);clone.update(id='cooling-case-copy',arrived_at_s=0.5);clone['provenance']['copied_from_record_id']=order['id']
other=dict(id='independent-flow-report',source_id='point_flow',target_id='intake_pump',observable_id='flow',unit='m3/s',value=0.1,
    observed_at_s=3.25,arrived_at_s=3.75,valid_until_s=10,quality=dict(status='bounded',error_bound=0,note='Independent synthetic meter.'),
    provenance=dict(origin_id='external-flow',copied_from_record_id=None))
late=cp(order);late.update(observed_at_s=0.5,arrived_at_s=0.5)
ep=cp(b['components']['instance_closure']['episodes'][0]);ep['opened_at_s']=0.5
cases={}; expected={}
# issue times, true professional completions, fees, real person/tool seconds, envelope, closure, service, count.
I=[['inspect-0',0,3.25],['action-0',3.75,5],['recheck-0',5.5,6.75]]
Ionly=I[:1]
Direct=[['action-0',0,3.25],['recheck-0',3.75,5]]
def add(name,changes,plan,actual,envelope,closure,states,*,source='common',loss=1,instances=1,other_checks=None):
    j=cp(common if source=='common' else old);patch(j,changes)
    if source=='common' or changes:bind(j)
    cases[name]=dict(base=source,edits=edits(common if source=='common' else old,j),sha256=digest(j))
    expected[name]=dict(issues=plan,person_s=actual,tool_s=actual,issue_cost=len(plan),envelope_person_s=envelope,envelope_tool_s=envelope,
        first_verified_at_s=closure,service_deficit_time_s=loss,instances=instances,decision_states=states,
        extra=other_checks or {})
add('measure-low',[],I,5.75,24.5,7.5,[[0,'MEASURE'],[0.5,'PENDING'],[3.75,'ACT_LOW'],[5.5,'RECHECK']],other_checks={'first_full_service_s':2,'root_model':['1/5','2/5'],'action_report':5.5,'own_recheck_arrival':7.25})
add('measure-normal',[[['scenario','parameters',ix,'value'],1]],Ionly,3.25,10,None,[[0,'MEASURE'],[3.75,'DEFER_NORMAL']])
add('direct',[[V,high]],Direct,4.5,16.25,7.5,[[0,'DIRECT'],[3.75,'RECHECK']])
add('defer',[[V,passive]],[],0,0,None,[[0,'DEFER']])
add('delayed-order',[[LED,[late]],[CL,[ep]],[V,passive]],[],0,0,None,[[0,'NO_INSTANCE'],[0.5,'DEFER']])
add('copy-and-competition',[[LED,[order,clone,second]],[CL,[b['components']['instance_closure']['episodes'][0],e2]]],I,5.75,24.5,7.5,[[0,'MEASURE'],[0.5,'PENDING']],instances=2,other_checks={'second_open':0.5,'second_closed':False,'shared_occupied_at':0.5})
for name,key,n in [('fee','cost',2),('person','person_s',18),('tool','tool_s',18)]:
    add('budget-'+name,[[BU+[key],n]],Direct,4.5,16.25,7.5,[[0,'DIRECT']],other_checks={'inspect_branch_infeasible':key})
add('recheck-window',[[PP+['templates',0,'recheck_task','deadline_s'],4.75]],[],0,0,None,[[0,'DEFER']])
add('expiry',[[A,3.25]],[],0,0,None,[[0,'DEFER']])
add('expired-read',[[INSP+['validity_s'],0.5]],Ionly,3.25,10,None,[[0,'MEASURE'],[3.75,'EXPIRED']])
add('unavailable-read',[[INSP+['condition_range'],[0.058,1]]],Ionly,3.25,10,None,[[0,'MEASURE'],[3.75,'UNAVAILABLE']])
add('conflict',[[LED,[order,other]]],Ionly,3.25,10,None,[[0,'MEASURE'],[3.75,'CONFLICT']])
reverse=cp(low[0]);reverse['low_given_cause']=[0,1,1]
add('variant-disagreement',[[V,[low[0],reverse]]],Direct,4.5,16.25,7.5,[[0,'DIRECT']],other_checks={'continuation':{'LOW':'DEFER','NORMAL':'DEFER'}})
add('persistent-bottleneck',[[['boundary_events'],common['boundary_events'][:1]]],I,5.75,24.5,None,[[0,'MEASURE'],[3.75,'ACT_LOW']],loss=5)
no_human=cp(pol);no_human.pop('value_model');no_human.update(schema='aegisdc-problem-driven-policy-v2',policy='no_human')
add('matched-protection',[[PP,no_human]],[],0,0,None,[],other_checks={'first_full_service_s':2})
add('old-v2',[],Direct,4.5,16.25,5.5,[],source='legacy',loss=0,instances=2)
add('old-expiring-authority',[[A,3.25]],Direct[:1],3.25,10,None,[],source='legacy',loss=0,instances=2,other_checks={'action_outcome':'NO_EFFECT','reason':'authorization_unavailable_at_completion'})
interfaces={
 'cross-threshold':dict(value=0.08,error=0.01,expected='INCONCLUSIVE'),
 'outside-support':dict(value=0.13,error=0,expected='ZERO_SUPPORT'),
 'outside-model':dict(value=0.2,error=0,expected='UNMODELED'),
 'unknown-version':dict(policy_schema='aegisdc-problem-driven-policy-v999',expected='REJECT'),
 'wrong-channel':dict(observable_id='temperature',expected='REJECT')}
for key in ('cross-threshold','outside-support','outside-model'):
    u=interfaces[key]
    u['record']=dict(id='flow-before-unused',source_id='portable-intake-meter',target_id='intake_pump',observable_id='flow',unit='m3/s',
        observed_at_s=3.25,arrived_at_s=3.75,valid_until_s=8.25,availability='current',value=u.pop('value'),
        quality=dict(status='bounded',error_bound=u.pop('error'),note='Paid portable meter engineering input.'),
        provenance=dict(origin_id='flow-before-unused',copied_from_record_id=None))
    u['as_of_s']=3.75; u['disputed_ids']=[]; u['public_model_source']='common/dispatch_program/policy_program/value_model'
for key in ('unknown-version','wrong-channel'):
    u=interfaces[key]; u['frozen_frame_and_history']=dict(path=(BASE.parent/'public-decisions.json').as_posix(),
        sha256=fileid(BASE.parent/'public-decisions.json'),row_index=0,keys=['frame','history'])
    u['program_source']='common/dispatch_program/policy_program'
    u['edit_path']=(['schema'] if key=='unknown-version' else ['inspection_declaration','nonfixed_profile','models',0,'observable_id'])
dump('inputs.json',dict(schema='aegisdc-v6-intake-engineering-inputs-v1',common=common,
    legacy_path=BASE.as_posix(),legacy_raw_sha256=fileid(BASE),units=cases,public_interface=interfaces,
    format='Apply ordered [path-components,replacement] pairs to a deep copy of common/legacy. Each resulting complete call is fixed. Hash uses sorted compact ASCII JSON, no NaN. No implicit defaults outside the existing native input contracts.'))
dump('expected.json',dict(schema='aegisdc-v6-intake-independent-expectations-v1',units=expected,interfaces={k:v['expected'] for k,v in interfaces.items()},
    pairs=[dict(left='measure-low',right='measure-normal',expect='identical_public_prefix_before_3.75',before=3.75),
           dict(left='measure-low',right='matched-protection',expect='same_physical_flow_before_action_and_identical_external_service',before=5),
           dict(left='direct',right='measure-low',expect='same_exogenous_inputs_distinct_issue_chains')],
    tolerance=1e-7,physical_flow_anchor=dict(before=[0.054,0.055],after=[0.099,0.101],unit='m3/s')))
dump('coverage.json',dict(trigger=['delayed-order','copy-and-competition'],public_prefix=['measure-low','measure-normal'],
    first_choices=['measure-low','direct','defer'],pending_and_own_chain=['measure-low','copy-and-competition','measure-normal'],
    budget_dimensions=['budget-fee','budget-person','budget-tool','recheck-window'],physical_authority=['expiry','old-expiring-authority'],
    observation_boundaries=['unavailable-read','expired-read','conflict','cross-threshold','outside-support','outside-model'],
    common_continuation=['variant-disagreement','measure-low','measure-normal'],identity_and_service=['persistent-bottleneck','matched-protection','measure-low'],
    version_regressions=['old-v2','unknown-version','wrong-channel']))
dump('manifest.json',dict(schema='aegisdc-v6-intake-engineering-freeze-v1',baseline='b5a2e9ad60a544f51c8e3541245154aaf8fe5b81',
    base_model={CFG.as_posix():fileid(CFG),BASE.as_posix():fileid(BASE)},order=list(cases),public_interfaces=list(interfaces),
    files={name:hashlib.sha256((P/name).read_bytes()).hexdigest() for name in ['contract.md','inputs.json','expected.json','coverage.json']},
    normal_call='python -m aegis_dc simulate --model MODEL --inputs EVENTS --dispatch-program DISPATCH --business-program BUSINESS --duration H --step DT --output NEW',
    budget=dict(red_cli_rejections=1,red_accepted_plant_calls=0,maximum_facility_attempts=4*len(cases),maximum_per_unit=4,
        initial_native_units=len(cases),interface_units=len(interfaces),paired_units=3,maximum_interface_rounds=4,
        maximum_jobs=7,maximum_green_jobs=4,cpus_per_job=1,mem_GiB=4,wall_seconds_per_job=1800,concurrency=1,gpus=0,reserved_cpu_seconds_cap=12600),
    stop='Retain every invocation before use; no automatic outcome-driven repeat. At most four versions/attempts per facility unit, only affected or unexecuted units after correction. Archive all exceptions and rows. No changing frozen expectations, parameter/physical relations, access boundaries or scoring to pass. If out of scope or capped stop affected work for review. Red checks rejection on baseline, green uses native CLI, stored reconciliation spends zero facility calls.',
    study_trials=0))

