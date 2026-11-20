"""Publish small verified observations from the sole already completed readiness job."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
def read(path):return json.loads(path.read_bytes())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def require(test,message):
    if not test:raise ValueError(message)


def main(folder):
    local=folder/'returned';out=local/'output'
    retrieval=read(local/'retrieval.json');report=read(out/'report.json');freeze=read(HERE/'freeze.json')
    launch=read(folder/'launch.json');submission=read(folder/'submission.json');manifest=read(HERE/'research-manifest.json')
    inventory=read(out/'durable-files.json')
    for name,h in retrieval['downloaded'].items():require(sha(local/name)==h,'Downloaded file differs: '+name)
    require(report['job']==retrieval['job']==submission['job'] and report['launch_sha256']==sha(folder/'launch.json')==retrieval['server_sha256']['launch.json'],'Job identity drift')
    require(sha(folder/'source.tar.gz')==retrieval['server_sha256']['source.tar.gz']==submission['source_sha256'],'Source archive differs')
    require(report['manifest_sha256']==launch['manifest_sha256']==sha(HERE/'research-manifest.json')==submission['manifest_sha256'],'Final manifest differs')
    require(report['durable_manifest_sha256']==sha(out/'durable-files.json') and not report['unexecuted'],'Incomplete readback')
    results=[]
    for case in freeze['tests']:
        key=case['id'];row=report['results'][key]
        require(row['passed'] and not row['differences'] and row['expected']==case['expected'],'Missing witness: '+key)
        results.append(dict(id=key,observed_file_sha256=inventory['units/'+key+'/observed.json']['sha256'],**row))
    cases={}
    for key in ('J1','J2','J3','J4','H1'):
        where=out/'sites'/key
        study=where/'V6-native-method-study-v1'
        current=read(study/'progress.json')
        require(current['denominator']==len(current['rows'])==85 and current['purpose']=='PUBLIC_LAUNCH_SURROGATE'
                and current['research_arms_executed']==0,'Case domain changed')
        no_evidence=[r['unit'] for r in current['rows'] if r['state']=='NOT_EXECUTED']
        require(no_evidence==current['not_executed'],'Lost suffix')
        cases[key]=dict(scope='surrogate control and replay processes only',counts=current['counts'],
            reserved_job_slots=current['job_reservations'],reserved_cpu_s_in_test=current['reserved_cpu_s'],
            unresolved_jobs=current['unresolved_jobs'],exact_starts_in_test=current['total_starts_exact'],exact_decisions_in_test=current['total_decisions_exact'],
            complete_denominator=85,not_executed=no_evidence,observed_or_unresolved=[row for row in current['rows'] if row['state']!='NOT_EXECUTED'],
            halt=read(study/'halt.json'),original_transport_receipt_sha256=sha(where/'surrogate-transport.json'),
            full_global_ledger_sha256=sha(study/'progress.json'))
    h=read(out/'sites/H1/truncation-proof.json')
    require(h['score_error'].endswith('Incomplete physical trajectory') and h['service_error']=='Incomplete H10 service window'
            and h['physical_records']==h['balance_records']+1 and h['actual_elapsed']==[0,5],'Prefix proof differs')
    sub=report['surrogate_arm_requests']
    require(len(sub)==12 and len(report['originals'])==5 and report['passed'],'Actual verification limits differ')
    require(report['actual_facility_calls']==report['actual_public_policy_calls']==report['research_jobs_submitted']==report['real_research_authorizations_consumed']==0,
            'Unexpected real activity')
    top=retrieval['sacct'][0].split('|')
    require(top[0]==report['job'] and top[3:5]==['COMPLETED','0:0'],'Wrong terminal state')
    result=dict(schema='aegisdc-v6-research-launch-readiness-delivery-v1',status='DELIVERED_AWAITING_STUDY_LAUNCH_REVIEW',
        acceptance_sha256=manifest['acceptance_sha256'],accepted_finite_publication=manifest['finite_publication'],
        protocol_revision=manifest['protocol_revision'],freeze_revision=launch['freeze_revision'],launch_source_revision=manifest['launch_source_revision'],
        verification_revision=launch['source_revision'],final_manifest_sha256=report['manifest_sha256'],launcher_sha256=manifest['launcher_tree'],
        native_tree_sha256=manifest['native_source_tree'],python=manifest['python'],private_outputs=retrieval['private_root'],
        attempts=[dict(job=report['job'],slurm_state=top[3],exit_code=top[4],node=top[5],cpus=int(top[6]),memory=top[7],
            wall_seconds=int(top[8]),cpu_time=top[9],reserved_cpu_seconds=120,sacct_fields=retrieval['sacct_fields'],sacct=retrieval['sacct'],
            command=submission['command'],source_archive_sha256=submission['source_sha256'],launch_sha256=report['launch_sha256'],
            report_sha256=sha(out/'report.json'),private_inventory_sha256=sha(out/'durable-files.json'),
            declared_files_in_private_inventory=len(inventory),unexecuted=[],unexpected_failures=[],retries=0)],
        frozen_budget=freeze['budget'],checks=results,scope_counts=dict(real_slurm_verification_jobs=1,
            real_research_grants_created_or_consumed=0,real_research_scheduler_submissions=0,real_native_facility_calls=0,real_public_policy_calls=0,
            direct_production_cli_refusal_processes=1,surrogate_scheduler_submissions=sum(x['reserved_job_slots'] for x in cases.values()),
            surrogate_arm_processes=12,surrogate_arm_requests=sub,original_native_directories_read=5,
            prior_decisions_read_as_known_subtotals=sum(x['counts']['known_decisions'] for x in cases.values()),
            artificial_B1_counts_are_separate=True),
        fixture_journals=cases,additional_evidence=dict(
            lost_arm_files=read(out/'sites/J1-receipt-only/evidence-loss-readback.json'),
            unresolved_and_torn=read(out/'sites/J4/review-addendum-results.json'),historical_originals=report['originals'],H10=h),
        test_domain='Only synthetic published-review responses, substitute Slurm commands and replay child processes. No real positive grant, no real research scheduler activity; the 17-case/final-budget edge used artificial committed summaries. Real C01 source outputs stayed private and unchanged.',
        no_research_authorization=True,stop='Review actual study admission path and this exact manifest before deciding whether to authorize one consumption.')
    with (HERE/'result.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,indent=2,ensure_ascii=False);f.write('\n')
    print('witnesses',len(results),'declared output fields',sum(len(x['actual']) for x in results),'surrogate children',len(sub),'inventory',len(inventory))

if __name__=='__main__':main(Path(sys.argv[1]))
