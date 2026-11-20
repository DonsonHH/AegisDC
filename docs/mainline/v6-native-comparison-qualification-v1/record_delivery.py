"""Prepare public receipts by transcribing already executed private checks and Git identities."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

PACK='docs/mainline/v6-native-comparison-qualification-v1'
PROTOCOL='docs/mainline/v6-native-method-comparison-v1'
BASE='53cc32b93dd62c8ce5ffd725eed9afba167557e5'
FREEZE='5836f0f17c7189a5782835647181713a19ee68f1'
SCIENCE_FIRST='0f5db8c8ad630f898807d6a93503199f5555e116'
SCIENCE_FINAL='721d966218cbed4d5603c7fda5dafb83d595dfbe'
ROOT=Path(__file__).resolve().parents[3]

def sha(raw):return hashlib.sha256(raw).hexdigest()
def load(path):return json.loads(path.read_bytes())
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def write(name,data):
    with (ROOT/PACK/name).open('x',encoding='utf-8',newline='\n') as f:
        json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def need(ok, why):
    if not ok:raise ValueError(why)

def main(work):
    freeze=load(ROOT/PACK/'fixtures.json')
    protocol=load(ROOT/PROTOCOL/'conditions.json')
    reports={}; provenance=[]
    for attempt in ('red01','initial01','repair01'):
        folder=work/attempt; received=folder/'collected'
        retrieval=load(received/'retrieval.json')
        for name,expected in retrieval['downloaded_sha256'].items():
            need(sha((received/name).read_bytes())==expected,'Downloaded evidence differs: '+name)
        server=retrieval['server_sha256']
        need(sha((folder/'source.tar.gz').read_bytes())==server['source.tar.gz'] and
            sha((folder/'launch.json').read_bytes())==server['launch.json'],'Archived attempt identity differs')
        report=load(received/'output/report.json');launch=load(folder/'launch.json')
        submission=load(folder/'submission.json');main_job=retrieval['sacct'][0].split('|')
        need(launch['protocol_revision']==BASE and launch['freeze_revision']==FREEZE and
             main_job[0]==report['job']==submission['job'] and submission['launch_sha256']==report['launch_sha256']==server['launch.json'],
             'Job or submitted identity differs')
        catalog=load(received/'output/durable-files.json')
        need(sha((received/'output/durable-files.json').read_bytes())==report['durable_manifest_sha256'],'Durable index differs')
        counts=None if attempt=='red01' else load(received/'terminal-account.json')
        if counts is not None:
            need(counts['checker_summary_consistent'] and counts['native']['status']=='COMPLETE_ACCOUNTING','Unresolved attempt counts')
        reports[attempt]=report
        per_category={}
        for k,v in report['checks'].items():
            category=k.split('/')[0];entry=per_category.setdefault(category,dict(units=0,matched_units=0,assertions=0,matching=0))
            entry['units']+=1;entry['matched_units']+=int(v['passed'])
            entry['assertions']+=len(v.get('assertions',[]));entry['matching']+=sum(a['passed'] for a in v.get('assertions',[]))
        provenance.append(dict(attempt=attempt,job=main_job[0],purpose=launch['mode'],implementation_revision=launch['implementation_revision'],
            checker_revision=launch['checker_revision'],slurm=dict(state=main_job[1],exit_code=main_job[2],node=main_job[3],
                cpus=main_job[4],memory=main_job[5],elapsed_s=main_job[6],cpu_time=main_job[7],start=main_job[9],end=main_job[10]),
            private_directory=retrieval['remote'],scheduler_command=submission['submit'],historical_inputs_actually_read=report.get('historical_reads',{}),
            source_archive_sha256=server['source.tar.gz'],launch_sha256=server['launch.json'],report_sha256=server['output/report.json'],
            durable_manifest_sha256=report['durable_manifest_sha256'],durable_artifacts=len(catalog),submission_and_terminal_sha256=server,
            public_started=report['public_started'],public_returned=report['public_returned'],substitute_started=report['substitutes_started'],
            substitute_returned=report['substitutes_returned'],facility_started=report['facility_started'],facility_returned=report['facility_returned'],
            facility_unreturned=report['facility_unreturned'],internal_known=report['internal_policy_known'],
            unknown_internal=report['unknown_facility_internal'],unexecuted=report['unexecuted'],category_checks=per_category,
            original_error=report.get('fatal'),expected_red=report.get('expected_red',False),outer_account=None if counts is None else counts['native']))
    red,initial,final=(reports[x] for x in ('red01','initial01','repair01'))
    need(red['expected_red'] and not initial['passed'] and final['passed'],'Unexpected execution path')
    ids={kind:[u.get('unit',u.get('id')) for u in freeze[kind]] for kind in ('public','facilities','fixtures')}
    need(initial['public_started']==initial['public_returned']==ids['public'] and initial['substitutes_started']==initial['substitutes_returned']==ids['fixtures']
        and initial['facility_started']==initial['facility_returned']==1 and initial['internal_policy_known']==20,'Initial denominator')
    need(final['facility_started']==final['facility_returned']==len(ids['facilities'])==11 and final['internal_policy_known']==220 and
        not final['public_started'] and not final['substitutes_started'] and not final['unexecuted'],'Repair denominator')
    final_dir=work/'repair01/collected/output'
    all_checks={}
    for key in ids['public']:
        all_checks['public/'+key]=dict(attempt='initial01',**initial['checks']['public/'+key])
    for key in ids['fixtures']:
        all_checks['fixtures/'+key]=dict(attempt='initial01',**initial['checks']['fixtures/'+key])
    actual=[]
    for row in final['native_ledger']['rows']:
        name=row['unit']
        score_path=final_dir/'native'/name/'score.json'
        need(sha(score_path.read_bytes())==row['score_sha256'],'Saved score drift: '+name)
        score=load(score_path)
        all_checks['facilities/'+name]=dict(attempt='repair01',**final['checks']['facilities/'+name])
        need(score['semantic_sha256']==row['semantic_sha256'] and
             score['input_sha256']==row['input_sha256'] and row['state']=='COMPLETED','Native identity drift')
        actual.append(dict(unit=name,condition=row['condition'],arm=row['arm'],private_directory=row['directory'],
            pid=row['pid'],before_launch_ns=row['prepared_ns'],start_ns=row['start_ns'],return_ns=row['returned_ns'],exit_code=row['exit_code'],
            input_sha256=row['input_sha256'],native_sha256=row['native_sha256'],native_source_tree=score['native_source'],
            score_sha256=row['score_sha256'],semantic_sha256=row['semantic_sha256'],internal_decisions=row['internal_policy_calls'],
            service=score['service'],native_integrated_summary=score['native_summary'],resources=score['resources'],
            questions=score['questions'],violations=score['violations']))
    all_checks['batch-identity']=dict(attempt='repair01',**final['checks']['native-order'])
    need(all(c['passed'] for c in all_checks.values()),'Incomplete finite qualification')
    panel=load(final_dir/'native/saved-evaluation.json')
    need(len(panel['rows'])==17 and all(r['service_and_closure'] is None for r in panel['claims'].values()),'Engineering cannot decide the research panel')
    subledger=load(work/'initial01/collected/output/substitute-Z4/injected-batch/ledger.json')
    failures=dict(expected_red=red['status'],initial_facility=initial['checks']['facilities/C01-V'],
        initial_failed_row=initial['native_ledger']['rows'][0],initial_frozen_batch_oracle_exception=initial['fatal'],
        suffix=initial['unexecuted'],injected_Z4=dict(ledger=subledger,study_or_facility_calls=0),
        retained_raw_timestamp_diagnostics={q['unit']:q['retained_original_coordinate_checks'] for q in final['checks'].values() if q.get('retained_original_coordinate_checks')})
    write('result.json',dict(schema='aegisdc-native-comparison-qualification-delivery-v1',state='FINITE_ENGINEERING_DELIVERED_FOR_USER_REVIEW',
        protocol=BASE,freeze=FREEZE,initial=SCIENCE_FIRST,repair=SCIENCE_FINAL,
        frozen_oracle_sha256=sha(git('cat-file','blob',FREEZE+':'+PACK+'/oracle.py')),
        actual_oracle_repair_sha256=sha(git('cat-file','blob',SCIENCE_FINAL+':'+PACK+'/repair_facilities.py')),
        attempts=provenance,actual_counts=dict(unique_public=27,unique_facility=11,unique_substitutes=4,
            public_direct=27,facility_process_starts=12,complete_facility_returns=12,unknown_facility_internal=0,
            facility_internal_public_decisions=240,total_top_level_policy_calls=267,substitutes=4,
            substitute_child_processes=2,slurm_jobs=3,reserved_cpu_seconds=900,study_runs=0),
        frozen_caps=freeze['scope'],checks=all_checks,actual_native=actual,failures=failures,engineering_evaluation=panel,
        verification_boundary='Qualification and scoring read archived native run, private-state and balance files on the allocated node. Desktop retrieved selected score/ledger/return receipts and hashes. Initial frozen oracle remains published; only separate physical epoch checks and failed-suffix accounting amended.',
        final_unexecuted_engineering=[],new_research_authority=False,release_preparation_sha256=sha(Path(__file__).read_bytes())))
    schedule=[]
    for row in protocol['conditions']:
        schedule.append(dict(condition=row['id'],fixed_order=list(protocol['treatments_in_fixed_execution_order']),
            arm_inputs=row['arms'],source_unit=row['source_unit'],public_stratum=row['public_stratum'],
            known_engineering_slots=[r['arm'] for r in actual if r['condition']==row['id']]))
    pinned_sources=load(work/'repair01/launch.json')['files']
    versions={k:v for k,v in pinned_sources.items() if k.startswith('src/aegis_dc/') or k=='src/patrol_rsi/contracts.py' or k.startswith('configs/materials/')}
    write('research-manifest.json',dict(schema='aegisdc-v6-native-comparison-research-manifest-for-review-v1',
        state='PREPARED_AWAITING_SEPARATE_USER_AUTHORIZATION',purpose='RESEARCH_ONLY_AFTER_SEPARATE_AUTHORIZATION',
        research_execution_authorized=False,already_launched=0,authorization_record=None,qualification_acceptance_by_user=None,
        protocol_revision=BASE,protocol_sha256={n:sha(git('cat-file','blob',BASE+':'+PROTOCOL+'/'+n)) for n in ('README.md','conditions.json','conditions.md','gaps.md','treatments.md')},
        qualified_engineering_revision=SCIENCE_FINAL,actual_runtime_source_tree=actual[0]['native_source_tree'],
        runtime_and_material_sha256=versions,python=dict(path='/share/home/renly/miniconda3/bin/python',version='3.13.9',
              sha256=load(work/'repair01/launch.json')['python_sha256']),groups=schedule,
        planned=dict(conditions=17,physical_backgrounds=5,arm_positions=85,distinct_complete_calls=65,
            V_H_consistency_pairs=17,public_decisions_max=1700,manual_issues_max=216,
            paired_positions_per_comparator=17,predeclared_question_opportunities_each_arm=18,all_predeclared_question_slots=90,
            jobs=17,cpu_per_job=1,memory_MiB=1024,wall_seconds_per_job=120,concurrency=1,reserved_cpu_seconds=2040,gpus=0,retries=0),
        normal_native_command=['/share/home/renly/miniconda3/bin/python','-B','-m','aegis_dc','simulate','--model','<arm>/model.json',
            '--dispatch-program','<arm>/dispatch-program.json','--business-program','<arm>/business-program.json','--inputs','<arm>/inputs.json',
            '--duration','10','--step','0.01','--output','<arm>/run'],
        execution_template='One unique private research activity after approval; job per C01..C17. Within each job create fresh V,D,K,H,P processes, state and exclusive directories. Never import prior engineering trajectories as research arms.',
        activation='Current run_native enforces engineering scope and callback. A later explicitly authorized launch must bind the research-purpose gate to this manifest, frozen source/interpreter and a fresh private root; full research launch path was not executed in this package.',
        stopping='Failure or loss of arm identity, hard constraints, V/H mismatch, exhausted budget or unknown completion stops suffix; no research retries. Keep all 85 slots and four contrast panels of 17. Study output must be locked before reporting.',
        scientific_claim='No method gain, ordinary improvement or RSI result from the engineering activity.'))

if __name__=='__main__':main(Path(sys.argv[1]))
