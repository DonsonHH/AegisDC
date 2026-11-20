"""Bind public input documents and transcribe the independently specified literals."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
BASE = 'a1adc22cb5fe2a23d6b30185187054bd6dd98ea2'
OLD = 'docs/mainline/v6-intake-engineering-v1/'
FRAME = 'evidence/mainline/engineering/39c-development/slice-53/green/joint/public-decisions.json'

def blob(path):
    return subprocess.check_output(['git','cat-file','blob',BASE+':'+path],cwd=ROOT)

def identity(value):
    return sha256(value).hexdigest()

def canonical(doc):
    return identity(json.dumps(doc,sort_keys=True,separators=(',',':'),allow_nan=False).encode())

def replace(doc,path,value):
    for k in path[:-1]:
        doc=doc[k]
    doc[path[-1]]=deepcopy(value)

def write(name,doc):
    (HERE/name).write_bytes((json.dumps(doc,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode())

def main():
    saved=json.loads(blob(OLD+'result.json'))
    published={u['unit']:u for u in saved['units']}
    integrity=json.loads(blob(OLD+'integrity.json'))
    attempts=json.loads(blob(OLD+'attempts.json'))['attempts']
    prior=json.loads(blob(OLD+'inputs.json'))['common']['dispatch_program']
    row=json.loads(blob(FRAME))[0]
    public=dict(frame=row['frame'],history=row['history'],program=prior['policy_program'],closure_program=prior['closure_program'])
    # Each base argument is the exact immutable JSON element, not a private run or an output expectation.
    sources=dict(frame=[FRAME,[0,'frame']],history=[FRAME,[0,'history']],
                 program=[OLD+'inputs.json',['common','dispatch_program','policy_program']],
                 closure_program=[OLD+'inputs.json',['common','dispatch_program','closure_program']])
    ttl=['program','inspection_declaration','bindings',0,'validity_s']
    ack=['program','workforce_profile','feedback_latency_s']
    clock=['program','value_model','clock_s']
    t4=[0,0.5,1,2,3.25,4,4.5,5,5.5,5.75,6,6.5,6.75,7,7.25,7.5,8,9,10]
    fixtures=[
        ('T1',[[ttl,0.75]],'MEASURE',3.75,3.75,4,3.75),
        ('T2',[[ttl,0.5]],'DIRECT',3.75,3.75,3.75,3.75),
        ('T3',[[ttl,0.75],[ack,1]],'DIRECT',4.25,4.5,4,4.5),
        ('T4',[[ttl,0.75],[clock,t4]],'DIRECT',3.75,4,4,4),
    ]
    tests=[]
    for key,edits,decision,work_ack,next_tick,expires,direct_recheck in fixtures:
        arguments=deepcopy(public)
        for path,value in edits:
            replace(arguments,path,value)
        valid=key=='T1'
        reasons=[] if valid else ['REPORT_EXPIRED_AT_DECISION']
        tests.append(dict(id=key,replace=edits,public_arguments_sha256=canonical(arguments),
            literal=dict(instance='cooling-direct/question-0',as_of_s=0,root=decision,
                intention='cooling-direct/'+('inspect' if valid else 'action')+'-0',forecast_inspection_finish_s=3.25,
                forecast_report_s=3.75,declared_work_ack_s=work_ack,half_open_end_s=expires,
                first_legal_decision_s=next_tick,inspection_feasible=valid,inspection_blockers=reasons,
                contingent_chain_feasible=valid,contingent_chain_blockers=reasons,direct_feasible=True,
                direct_recheck_planned_issue_s=direct_recheck,common_continuation={'LOW':'ACT' if valid else 'DEFER','NORMAL':'DEFER'})))
    names=['expired-read','direct','budget-fee','budget-person','budget-tool','variant-disagreement','measure-low','delayed-order']
    objects={n:dict(attempt=published[n]['attempt'],row=n,run_sha256=published[n]['run_sha256'],
             canonical_input_sha256=published[n]['input_sha256'],execution_revision=published[n]['source'],
             runtime_tree_sha256=published[n]['source_tree']) for n in names}
    before=integrity['expiry_evidence']
    objects['historical-receipt']=dict(row='expired-read',attempt='green01',run_sha256=before['earlier_saved_run_sha256'],
        canonical_input_sha256=published['expired-read']['input_sha256'],execution_revision=before['earlier_recorded_revision'])
    base_files=[FRAME]+[OLD+f for f in ['inputs.json','expected.json','manifest.json','input-binding-addendum.json',
            'independent-values.json','result.json','attempts.json','integrity.json']]
    action='cooling-direct/action-0'; recheck='cooling-direct/recheck-0'; inspect='cooling-direct/inspect-0'
    common_end=dict(first_closed_s=7.5,first_current_state='VERIFIED_CLOSED',current_at_H=10,
        current_state='SYMPTOM_RETREATED_PENDING_VERIFICATION',risk_closed=False,question_closed=False,
        own_recheck_current_at_7_5=True,own_recheck_current_at_10=False,policy_reason_at_H='RECHECK_ISSUED',
        last_intention=None,issued_recheck_count=1,completed_recheck_count=1,issues_since_first_close=[])
    revised=dict(order_id='cooling-claim-0',first_choice='DIRECT',first_intention=action,
        inspection_blockers=['REPORT_EXPIRED_AT_DECISION'],direct_plan_available=True,
        issued=[[action,0],[recheck,3.75]],completed=[[action,3.25],[recheck,5]],completed_acks=[[action,3.25,3.75],[recheck,5,5.5]],
        action_report=[action,'residual-clean','APPLIED',3.25,3.75],
        own_record=['flow-after-clean','portable-intake-meter','intake_pump','flow','m3/s',5,5.5,10],
        frame_at_first_close=dict(condition_sample_s=[6,7],service_sample_s=[6,7],recheck_availability='current'),
        recheck_at_H='expired',remaining_recheck_eligible=False,envelope=[16.25,16.25,2],actual_person_tool=[4.5,4.5],
        paid_issue_cost=2,service_deficit_s=1,closure=common_end)
    freeze=dict(schema='aegisdc-intake-expiry-closeout-freeze-v1',baseline=BASE,
        status='POST_REVIEW_REVISION_BEFORE_NEW_QUALIFICATION',spec_sha256=identity((HERE/'spec.md').read_bytes()),
        authoring_tool_sha256=identity(Path(__file__).read_bytes()),public_source_sha256={f:identity(blob(f)) for f in base_files},
        initial_public_arguments=sources,canonicalization='JSON UTF-8, ensure_ascii=true, sorted object keys, compact separators, no NaN. Apply listed path/value replacements in order to a deep copy of the four base arguments.',
        public_entry='aegis_dc.dispatch_policy.choose_work(frame, program, history, intervention_declaration=program.intervention_declaration, closure_program=closure_program)',
        new_public_witnesses=tests,
        original_acceptance=dict(accepted_facility_units=[u for u in published if u!='expired-read'],accepted_unit_assertions=[309,309],
          original_full_units=19,original_full_assertions=[316,325],unmatched_unit='expired-read',unmatched_unit_assertions=[7,16],
          accepted_interfaces=['cross-threshold','outside-support','outside-model','unknown-version','wrong-channel'],
          accepted_pair_count=3),
        saved=dict(prior_activity='/share/home/renly/renly-patrol-rsi/mainline/V6-intake-20261120',native_objects=objects,
            private_manifests={a['attempt']:a['durable_sha256']['source/source-manifest.json'] for a in attempts if a['attempt'] in ('green01','green02','green03')},
            original_19_comparison=dict(path='saved01/output/report.json',sha256=saved['full_checks_sha256']),
            original_classifier_parts=before['actual_arrival_path_source_sha256'],direct_route_companions=names[1:6],
            revised_expired_read=revised,h10_direct_common=common_end,
            historical_arrived=dict(inspection_work=[[inspect,0,3.25]],own_completion_ack=[inspect,3.25,3.75],
               record=['flow-before-unused','portable-intake-meter','intake_pump','flow','m3/s',3.25,3.75,3.75],
               availability='expired',classification='EXPIRED',next_intention=None,manual_followups=0),
            delayed_opportunity=dict(carried=['TOO_LATE',0.5,4.25,4],actual_opened_s=0.5,actual_work_ids=[],
               actual_handheld_records=[],reference_inspection=inspect,actual_anchor=[0,2,2.25,3.25,3.75,3.75],
               inferred_from_anchor=dict(finish_s=3.75,report_s=4.25,work_ack_s=4.25,first_clock_s=4.5,deadline_s=4,
                   status='TOO_LATE'))),
        budget=dict(max_jobs=3,max_seconds_per_job=180,max_reserved_cpu_s=540,cpu_per_job=1,memory_MiB=1024,
            concurrent_jobs=1,gpus=0,facility_invocations=0,research_runs=0,public_units=4,
            initial_public_calls=4,max_public_calls_total=12,max_per_public_unit=3),
        stop='One initial job with four independent public calls plus saved reconciliation. Each retry requires terminal accounting and an identified checker/staging repair; only affected or unexecuted units/reads, each at most three times. Stop on any needed policy/science/expected-value change, exhaustions or success. Preserve unique sources, failures, unexecuted suffixes and versions. No facility entry, no new physical trajectory.',
        durable=['acceptance/specification and freeze','pinned author/check/staging tools','input identifiers, source archive and interpreter',
                 'per-unit public arguments, returned choices and comparisons, prior raw file read receipts; job stdout/stderr and terminal state',
                 'compact result and final Git integrity receipt'])
    write('freeze.json',freeze)

if __name__=='__main__':
    main()
