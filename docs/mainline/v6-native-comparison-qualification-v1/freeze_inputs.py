"""Transcribe independent engineering literals and bind immutable JSON input sources."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
BASE='53cc32b93dd62c8ce5ffd725eed9afba167557e5'
PROTOCOL='docs/mainline/v6-native-method-comparison-v1/'
OLD='docs/mainline/v6-intake-engineering-v1/'
def raw(path):
    return subprocess.check_output(['git','cat-file','blob',BASE+':'+path],cwd=HERE.parents[2])
def digest(data):
    return hashlib.sha256(data).hexdigest()
def save(name,data):
    (HERE/name).write_bytes((json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())
def main():
    cond=json.loads(raw(PROTOCOL+'conditions.json'))
    cases={r['id']:r for r in cond['conditions']}
    previous=json.loads(raw(OLD+'result.json'))
    prior={r['unit']:r for r in previous['units']}
    receipt=json.loads(raw(OLD+'integrity.json'))['expiry_evidence']
    prereq={}
    for k in ('measure-low','measure-normal','copy-and-competition','unavailable-read','conflict','direct'):
        u=prior[k];prereq[k]=dict(attempt=u['attempt'],unit=k,run_sha256=u['run_sha256'])
        if k=='direct':prereq[k]['artifacts']=u['raw_artifacts']
    prereq['expired-original']=dict(attempt='green01',unit='expired-read',run_sha256=receipt['earlier_saved_run_sha256'])
    public=[]
    for case,decisions,reason in [
        ('C01',['DIRECT','MEASURE'],None),('C09',['DIRECT','MEASURE'],None),('C10',['DEFER','MEASURE'],None),
        ('C11',['DIRECT','MEASURE'],None),('C12',['DIRECT','DIRECT'],'cost'),('C13',['DIRECT','DIRECT'],'person_s'),
        ('C14',['DIRECT','DIRECT'],'tool_s'),('C15',['DEFER','DEFER'],'STAGE_DEADLINE'),
        ('C16',['DIRECT','DIRECT'],'ACTION_AUTHORITY'),('C17',['PENDING','PENDING'],'PUBLIC_UNACKNOWLEDGED_RESOURCE_OCCUPATION')]:
        for arm,decision in zip(('D','K'),decisions):
            competing=case=='C17'
            public.append(dict(unit=case+'-'+arm,condition=case,arm=arm,call_sha256=cases[case]['arms'][arm]['complete_call'],
                prefix='copy-and-competition' if competing else 'measure-low',at_s=0.5 if competing else 0,
                edit='second-order-valid-until-0.75' if competing else 'none',
                expected=dict(state=decision,selected={'DIRECT':'cooling-direct/action-0','MEASURE':'cooling-direct/inspect-0'}.get(decision),
                    targeted_blocker=reason,instance_count=2 if competing else 1)))
    for uid,case,prefix,edit,state,read in [
        ('low','C01','measure-low','none','ACT_LOW','LOW'),('normal','C02','measure-normal','none','DEFER_NORMAL','NORMAL'),
        ('no-ack','C01','measure-low','work-latency-1-and-no-arrived-ack','PENDING','PENDING'),
        ('expired','C01','expired-original','initial-validity-0.5','EXPIRED','EXPIRED'),
        ('missing','C06','unavailable-read','none','UNAVAILABLE','UNAVAILABLE'),('conflict','C07','conflict','none','CONFLICT','CONFLICT'),
        ('c11-low','C11','measure-low','none','ACT_LOW','LOW')]:
        public.append(dict(unit='K-'+uid,condition=case,arm='K',call_sha256=cases[case]['arms']['K']['complete_call'],
             prefix=prefix,at_s=3.75,edit=edit,
             expected=dict(state=state,selected='cooling-direct/action-0' if state=='ACT_LOW' else None,
                           observation=read,record='flow-before-unused',instance_count=1)))
    lookup={'M':[['inspect-0',0,3.25],['action-0',3.75,5],['recheck-0',5.5,6.75]],
            'D':[['action-0',0,3.25],['recheck-0',3.75,5]],'late-ack':[['action-0',0,3.25],['recheck-0',4.5,5.75]],'P':[]}
    measures={'M':[5.75,5.75,3],'D':[4.5,4.5,2],'late-ack':[4.5,4.5,2],'P':[0,0,0]}
    fs=[]
    for case,arm,route,close in [('C01','V','M',[False,True,True]),('C01','D','D',[False,True,False]),
           ('C01','K','M',[False,True,True]),('C01','H','M',[False,True,True]),('C01','P','P',[False,False,False]),
           ('C03','K','M',[False,False,False]),('C04','P','P',[False,False,False]),('C05','P','P',[False,False,False]),
           ('C08','K','late-ack',[False,True,True]),('C17','D','D',[False,True,False]),('C17','K','M',[False,True,True])]:
        expected=dict(work=lookup[route],actual_resources=measures[route],valid_at_5_7_5_10=close,
             first_close=7.5 if any(close) else None,recheck_count=sum('recheck' in row[0] for row in lookup[route]),
             decision_calls=20,opportunities=2 if case=='C17' else 1)
        if case=='C01':expected.update(service_L_U=[2,2],network_recovery_s=4)
        if case=='C03':expected.update(valve=0,volume_flow=0,measurement='LOW',writes=[['filter_resistance_multiplier',1,1,5]])
        if case=='C04':expected.update(max_service=0.5,split_s=4,min_segment_L_U=[[2,2],[3,3]],
            event_bindings=[[0,'network_service_capacity',0.5],[4,'network_service_capacity',1],[4,'storage_service_capacity',0.5]])
        if case=='C05':expected.update(max_IT_W=97000,max_compute_capacity=0.0485,max_delivery=0.0485)
        if case=='C08':expected.update(receipts=[['action-0',3.25,3.75,4.25],['recheck-0',5.75,6.25,6.75]])
        if case=='C17':expected.update(second_open_s=0.5,second_last_valid_s=0.75,second_actual_work=[],second_closed=False)
        fs.append(dict(unit=case+'-'+arm,condition=case,arm=arm,identities=cases[case]['arms'][arm],expected=expected))
    full=[[0,10,1,1,0,10,10]]; limited=[[0,4,1,0.5,2,4,2],[4,10,1,1,0,6,6]]
    split=[[0,2,1,0.5,1,2,1],[2,4,1,0.5,1,2,1],[4,10,1,1,0,6,6]]
    z=[
      dict(id='Z1',inputs=dict(columns=['start','end','demand_rate','delivery_rate','balance_L','balance_demand','balance_delivered'],
        full=full,limited=limited,split=split,ambiguous=dict(balance='0',rate='1/4503599627370496',identical_history=False)),
        expected=dict(limited_L_U=['2','2'],positive=['BETTER','2','2'],negative=['WORSE','-2','-2'],subdivision='EQUAL',numeric='NUMERIC_UNRESOLVED')),
      dict(id='Z2',inputs=dict(service='Z1.full',V_resources=[1,1,1],D_resources=[2,2,2],question='cooling-direct/question-0',
          checkpoints=[5,7.5,10],closed=[False,True,True],first=7.5,V_changed_checkpoints=[False,True,False]),
          expected=dict(service='EQUAL',delta=['1','1','1'],resources='BETTER',closed_joint=True,lost_close_joint=False,physical_stays='EQUAL',
              resource_difference_stays='BETTER',service_gain=False)),
      dict(id='Z3',inputs=dict(saved='direct',append='deep copy of first existing completed workforce feedback for cooling-direct/recheck-0 at end in terminal workforce_public_feedback and final history work_feedback',
          preserve_saved_original=True),expected=dict(first=7.5,at_H='SYMPTOM_RETREATED_PENDING_VERIFICATION',rechecks=1,fee='2',resources=['9/2','9/2','2'],equal_before_after=True)),
      dict(id='Z4',inputs=dict(order=['V','D','K','H','P'],condition='FIXTURE',processes={'V':{'returncode':0,'payload':{'internal_policy_calls':1}},
         'D':{'returncode':7,'payload':None}},second_invocation='same existing output path must reject before launch'),
         expected=dict(states=['COMPLETED','FAILED','NOT_EXECUTED','NOT_EXECUTED','NOT_EXECUTED'],started=2,complete_returns=1,
           missing_returns=1,known_policy_subtotal=1,unknown_internal=['D'],suffix=['K','H','P'],processes=2,overwrite_rejected=True))]
    files=[PROTOCOL+x for x in ('README.md','conditions.md','conditions.json','gaps.md','treatments.md','integrity.json')]+[OLD+'inputs.json',OLD+'input-binding-addendum.json',OLD+'result.json',OLD+'integrity.json']
    out=dict(schema='aegisdc-native-comparison-engineering-freeze-v1',protocol_revision=BASE,source_sha256={q:digest(raw(q)) for q in files},
         prior_root='/share/home/renly/renly-patrol-rsi/mainline/V6-intake-20261120',prior_runs=prereq,
         argument_recipe='Select the only policy_public_decisions with frame.as_of_s==at_s from the named immutable historical run. Copy only frame/history. Use row/arm frozen complete program, its intervention declaration and closure program with arrived history feedback. Only named edits: C17 changes second origin valid_until_s to 0.75 at the still-current 0.5 prefix. no-ack uses public-only workforce feedback latency 1, history.work_feedback empty. expired uses both public initial-slot inspection binding validity 0.5 and authentic expired history. Other fields untouched. These are prior public interface histories, not shared observations between facility arms.',
         public=public,facilities=fs,fixtures=z,scope=dict(initial=[27,11,4],internal_decision_cap=220,initial_total_policy_cap=247,
              total=[54,22,8],total_internal_decision_cap=440,total_policy_cap=494,maximum_repairs=1,jobs=3,
              cpu=1,memory_MiB=1024,wall_s=300,concurrent=1,reserved_cpu_s=900,study_facility_authorized=0),
         comparison=dict(direction='D_or_other_minus_V',windows=[5,7.5,10],physical_service='original L and U plus exact rate-history re-integration',
           numeric_bound='No tolerance for decisions, integer counts or direction. Engineering floating point physical bound checks use 1e-8 absolute units; exact rational endpoint and direction checks remain exact.'),
         coverage=dict(public_root=[r['unit'] for r in public[:20]],paid_observation=[r['unit'] for r in public[20:]],native=[r['unit'] for r in fs],
             saved_scoring=['Z1','Z2','Z3'],failure_process=['Z4'],isolation=['C01-V','C01-H'],competition=['C17-D','C17-K']),
         stop='One zero-call baseline entry red job; one initial qualification; at most one targeted in-scope repair of failed/affected or unexecuted units. On native failure stop the scheduled suffix. Preserve all per-unit inputs/outputs, process identities, unknowns, failures and denominators. No scientific expectation changes, no research launch.')
    save('fixtures.json',out)

if __name__=='__main__':
    main()
