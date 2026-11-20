"""Transcribe a verified Slurm attempt and its saved checks into a small public receipt."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


def read(file):
    return json.loads(file.read_bytes())


def sha(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def main():
    directory=Path(sys.argv[1])
    report=read(directory/'report.json')
    terminal=read(directory/'terminal.json')
    launch=read(directory/'launch.json')
    submission=read(directory/'submission.json')
    freeze=read(HERE/'freeze.json')
    files=terminal['artifacts']
    for local,relative in [('report.json','output/report.json'),('source.tar.gz','source.tar.gz'),('launch.json','launch.json')]:
        if sha(directory/local)!=files[relative]:
            raise ValueError('Local and remote evidence differ: '+local)
    if not (files['launch.json']==submission['launch_sha256']==report['launch_sha256']
            and files['source.tar.gz']==submission['source_archive_sha256']==launch['archive_sha256']
            and sha(HERE/'freeze.json')==launch['freeze_sha256']):
        raise ValueError('Execution source or freeze binding differs')
    main_job=terminal['sacct'][0].split('|')
    if main_job[0]!=report['slurm_job'] or main_job[0]!=submission['job'] or main_job[3:5]!=['COMPLETED','0:0']:
        raise ValueError('Unexpected job identity or terminal state')
    new_ids=[w['id'] for w in freeze['new_public_witnesses']]
    if not (report['selected']==['original',*new_ids,'revision','direct_horizon','received','reference_opportunity']
            and report['public_calls_started']==report['public_calls_returned']==new_ids
            and report['full_package_checked_in_attempt'] and report['attempt_passed'] and not report['unexecuted_selected']
            and not report['omitted_in_attempt'] and report['facility_invocations']==report['research_runs']==0):
        raise ValueError('Incomplete execution cannot be delivered as the finite closeout')
    for key in new_ids:
        if report['checks'][key]['return_sha256']!=files['output/'+key+'/choice.json']:
            raise ValueError('Archived returned choice differs')
    old=freeze['saved']['prior_activity']+'/'
    reads={path.removeprefix(old):info for path,info in report['read_receipts'].items() if path.startswith(old)}
    result=dict(schema='aegisdc-v6-intake-expiry-closeout-delivery-v1',date='2026-11-20',
        state='FINITE_CLOSEOUT_DELIVERED_FOR_REVIEW',baseline=launch['baseline'],freeze_revision=report['freeze_revision'],
        checker_revision=report['checker_revision'],historical_scope='Limited user acceptance at a1adc22c; original 19-row comparison preserved.',
        original_frozen_comparison=report['checks']['original'],
        post_review_saved_checks={key:report['checks'][key] for key in ['revision','direct_horizon','received','reference_opportunity']},
        new_public_qualification=[report['checks'][key] for key in new_ids],saved_prior_activity=old,checked_old_files=reads,
        source=dict(runtime_tree_unchanged_since=launch['baseline'],python='/share/home/renly/miniconda3/bin/python',
                    python_version='3.13.9',python_sha256=launch['python_sha256'],prefix_freeze_sha256=launch['freeze_sha256']),
        new_budget=freeze['budget'],allocated=dict(jobs=1,public_entry_calls=4,facility_calls=0,research_runs=0,
            cpus=1,memory_MiB=1024,reserved_cpu_s=180,wall_seconds=int(main_job[8]),cpu_time=main_job[9],gpus=0),
        attempts=[dict(attempt=launch['attempt'],job=main_job[0],partition=main_job[2],node=main_job[5],terminal=main_job[3],
            exit_code=main_job[4],started=main_job[10],ended=main_job[11],time_limit=main_job[12],command=submission['command'],
            private_path=submission['remote'],sacct_fields=terminal['queried_fields'],sacct=terminal['sacct'],
            source_and_durable_files_sha256=files,public_calls_started=report['public_calls_started'],
            public_calls_returned=report['public_calls_returned'],failed=[],unexecuted=report['unexecuted_selected'],retries=0)],
        prior_failure_ledger='../v6-intake-engineering-v1/attempts.json',recording_tool_sha256=sha(Path(__file__)),
        stop='Await user review of the closeout. No facility runs, method-benefit trials, ordinary improvement or RSI authorized by this delivery.')
    (HERE/'result.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode())


if __name__=='__main__':
    main()
