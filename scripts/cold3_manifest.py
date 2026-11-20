"""Bind the cold study *data* to the reviewed engineering record. Never imports a policy or plant."""
import gzip
import hashlib
import json
from pathlib import Path
from cold3_runner import PK,ROOT,read,save,sha,digest

TRANSFER={
    'A01':'O,C,M; fee-two direct restriction and closed branch inherited from original P01-P04',
    'A02':'O,C,M; C no-op and common-service mask separately retained',
    'A03':'C,M,X; simultaneous order, paid N then true C and its own R',
    'A04':'C,X,G,M; paid N then N correction and own R vs direct C',
    'A05':'L,D1,D2; capped N branch, C stays in evaluation; original S05 N equal write',
    'A06':'L,D1,D2; N-only complete chain at fee two and late opening still observed',
    'A07':'L,C; funded late C admission following early N, possible equal N write as S05',
    'A08':'L,M; funded late C admission, real N change and C equal-write representation',
    'B01':'O; original P03/S01/S16 and H12 HOLD: one repair cannot remove coincident forecast bottlenecks',
    'B02':'O,M; common no-benefit root and full-window no-effect coverage',
    'B03':'O,D5,D6; both real orders and binding double-repair budget',
    'B04':'O,M; both order paths with independent equal-write / full-window coverage',
    'B05':'O,X; single N direct paths and native S05 equal-write family',
    'B06':'O,X; single N direct and own R, same .5 N timing in O-J_ORDER',
    'B07':'X,C,O; branch to C after N and two direct actions, N equal-write in S05',
    'B08':'X,O; the B08 design-time direction is declared separately; X is an engineering budget-bound near match',
    'C01':'G,X; actual positive bundle, independent N fix and R, no-probe denial',
    'C02':'G,U,D9 and prior S04; N-only paid workflow and (1,.25) supply restriction',
    'C03':'U; mixed read, empty support, no elective correction in matched complete trajectories',
    'C04':'M; storage masks both, C equal write and full H check',
    'C05':'D7,C,U,M and prior S08/G16; completion equal to expiry refused, read-only and direct C paths',
    'C06':'D8,C,U,M; same roots, N direct alternative meets earlier window while read-then-N remains too late',
    'C07':'D3,D4,G and previous native HOLD; entire positive contingent plan unaffordable',
    'C08':'G; complete positive chain at exact person bound; identical tool work with relaxed tool cap',
}


def assemble_manifest(root,out,pin,plan,freeze,release_sha):
    study_path=root/'F0/frozen/study-inputs.json.gz'
    if sha(study_path)!=freeze['files']['study-inputs.json.gz']:raise ValueError('Frozen research bytes changed')
    study=read(study_path)
    disclosure=read(PK/'disclosure.json.gz')
    if set(study)!=set(freeze['study']) or any(digest(v)!=freeze['study'][k] for k,v in study.items()):raise ValueError('Study inputs differ')
    matrix=read(PK/'conditions.json')
    saved_roots=root/'A/public-roots.json.gz';audit_receipt=root/'A/result.json'
    audited=read(audit_receipt) if audit_receipt.is_file() else {}
    checked_exposures=bool(saved_roots.is_file() and audited.get('public_roots_sha256')==sha(saved_roots))
    snapshots=read(saved_roots) if checked_exposures else {}
    if checked_exposures and (set(snapshots)!=set(freeze['engineering']) or any(len(v)!=49 for v in snapshots.values())):
        checked_exposures=False
    if audited.get('status')=='PASS' and not checked_exposures:raise ValueError('Missing authenticated complete engineering exposure index')
    observed={};overlap={}
    for k,entries in snapshots.items():
        for e in entries:
            for kind,sign in zip(('view','configured'),e['signature']):
                observed.setdefault(kind+':'+sign,[]).append([k,e['time']])
    schedules=[];position=0
    for cond in matrix['core_rows']:
        group=[]
        for mode in cond['arms']:
            key=cond['id']+'-'+mode;x=study[key];cf=x['dispatch_program']['policy_program']
            if cf['method']!=mode or cf['caps']!=cond['budget'] or len(cf['clock'])!=49 or not x['private_physical_audit']:raise ValueError('Research identity '+key)
            entry=disclosure['study'][key]
            if entry['hashes']['full']!=freeze['study'][key]:raise ValueError('Pre-outcome disclosure binding '+key)
            overlap[key]={t:dict(same_environment=observed.get('view:'+r['view_sha'],[]),
                same_configuration_and_view=observed.get('configured:'+r['configured_view_sha'],[])) for t,r in entry['known_roots'].items()}
            group.append(dict(position=position,arm=mode,input_key=key,complete_call_sha256=freeze['study'][key],scenario_sha256=digest(x['scenario']),
                 dispatch_sha256=digest(x['dispatch_program']),common_physics=entry['hashes']['physics'],common_design=entry['hashes']['design'],
                 public_decisions=49,H=12,step=.01));position+=1
        if len({g['common_physics'] for g in group})!=1 or len({g['common_design'] for g in group})!=1:raise ValueError('Incomparable cold arms')
        schedules.append(dict(row=cond['id'],positions=group,primary=[group[0]['input_key'],group[1]['input_key']],
            mechanism_pairs=[[group[0]['input_key'],g['input_key']] for g in group[2:]],transfer=TRANSFER[cond['id']]))
    results={};problems=[]
    for j in plan['jobs']:
        phase=j[0]
        if phase=='M':continue
        rp=root/phase/'result.json'
        if not rp.is_file():
            results[phase]=dict(status='MISSING');problems.append(phase);continue
        data=read(rp);results[phase]=dict(status=data['status'],receipt_sha256=sha(rp),job=data.get('job'),counts=data['counts'],
            failed=data.get('failed',[]),error=data.get('error'),unexecuted=data.get('unexecuted',[]))
        if data['status'] not in ('PASS','EXPECTED_PRIOR_REJECTIONS'):problems.append(phase)
    if not checked_exposures:problems.append('A/exposure-index')
    study_manifest=dict(schema='aegisdc-cold-study-review-manifest-v2',purpose='COLD_RESEARCH_REVIEW_ONLY',state='STOP_AT_RESEARCH_LAUNCH_REVIEW',
        authority=None,grants_consumed=0,study_starts=0,engineering_status='FINITE_EVIDENCE_AVAILABLE' if not problems else 'PARTIAL_ENGINEERING_EVIDENCE',
        failed_or_missing_phases=problems,approval='Separate explicit, published one-time user authorization bound to these exact manifest bytes and the supported scope; engineering gate rejects study-purpose inputs.',
        release_revision=pin['revision'],release_sha256=release_sha,execution_file_sha256=pin['files'],python_sha256=pin['interpreter_sha256'],
        data_file='study-inputs.json.gz',data_sha256=sha(study_path),input_freeze_sha256=sha(PK/'input-freeze.json'),
        protocol_sha256=sha(PK/'protocol.md'),matrix_sha256=sha(PK/'conditions.json'),engineering_schedule_sha256=sha(PK/'engineering-plan.json'),
        earlier_disclosure_sha256=sha(PK/'disclosure.json.gz'),new_observed_prefix_comparison='engineering-prefix-overlap.json.gz',
        recorded_engineering_phases=results,limits=matrix['planned_study_limits'],groups=schedules,order='serial condition then listed arm, isolated processes',
        retries=0,scoring='cold3_evaluation.score_arm / compare_pair / panel, H12 only, private left and pre-manual channels required; finite full denominator and unresolved suffix retained',
        limitations=['No study outcome or one-time launch grant. Engineering is public and not independent confirmation.',
         'Qualification transfers only over matched authentic event families; still check actual common history through the first different physical effect or H.',
         'Any uncovered grid/effect, hard breach, missing true left or unqualified prefix stops affected attribution; no imputed evidence.',
         'Conditional warm panel absent. Original S09 and half-step failures retained. No ordinary improvement or RSI.'])
    if position!=66 or len(schedules)!=24:raise ValueError('Cold study denominator')
    save(out/'engineering-prefix-overlap.json.gz',dict(root_comparison=overlap,actual_engineering_index=observed,
        caveat='Study history after first possible elective choice is unobserved; match that history only in a future authorized run.'))
    study_manifest['new_observed_prefix_sha256']=sha(out/'engineering-prefix-overlap.json.gz')
    save(out/'study-manifest.json',study_manifest)
    return dict(study_manifest_sha256=sha(out/'study-manifest.json'),prefix_overlap_sha256=study_manifest['new_observed_prefix_sha256'],
                cold_positions=position,primary_pairs=len(schedules),mechanism_pairs=sum(len(g['mechanism_pairs']) for g in schedules),
                engineering_problems=problems,study_starts=0,launch_authorized=False)
