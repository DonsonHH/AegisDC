"""Verify the retained failed-assertion run without any project or plant calls."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import traceback


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or socket.gethostname().split('.')[0] == 'mu01':
        raise SystemExit('Saved-only verification requires a Slurm compute allocation')
    root = args.manifest.resolve().parent
    frozen_sha = sha(args.manifest)
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    args.output.mkdir(exist_ok=False)
    save(args.output / 'attempt.json', dict(classification='SAVED_ASSERTION_CORRECTION_NOT_PHYSICAL_RETRY',
         started_at_utc=datetime.now(timezone.utc).isoformat(), slurm_job_id=os.environ['SLURM_JOB_ID'],
         node=socket.gethostname(), source_commit=manifest['source_commit'], facility_calls=0,
         direct_public_choice_calls=0, model_calls=0, new_statistical_units=0))
    terminal = dict(status='FAILED', source_commit=manifest['source_commit'])
    try:
        protocol = json.loads((root/'protocol.json').read_text(encoding='utf-8'))
        def guard():
            if sha(args.manifest) != frozen_sha:
                raise ValueError('Saved verification manifest changed')
            for name, record in manifest['files'].items():
                if (root/name).stat().st_size != record['bytes'] or sha(root/name) != record['sha256']:
                    raise ValueError('Pinned verification tool/protocol changed: ' + name)
            for record in protocol['inputs'].values():
                path=Path(record['path'])
                if path.stat().st_size != record['bytes'] or sha(path) != record['sha256']:
                    raise ValueError('Original saved input changed: ' + path.name)
        guard()
        if sha(Path(__file__)) != manifest['files']['verify_saved_delayed_ack.py']['sha256']:
            raise ValueError('Execute the pinned saved verifier')
        data=json.loads(Path(protocol['inputs']['summary']['path']).read_text(encoding='utf-8'))
        original=json.loads(Path(protocol['inputs']['terminal']['path']).read_text(encoding='utf-8'))
        log=Path(protocol['inputs']['test_log']['path']).read_text(encoding='utf-8')
        assert original['status']=='FAILED' and original['failures']==1 and original['errors']==0
        assert "'expired' != 'stale'" in log
        assert data['code_identity']['git_commit']==protocol['runtime_source'] and not data['code_identity']['implementation_has_changes']
        decisions=data['decisions']
        assert [r['choice']['chosen_candidate_id'] for r in decisions]==['network-case/inspect-0',None,'network-case/action-0',None,'network-case/recheck-0',None]
        waiting=decisions[3]
        assert waiting['history']['intervention_feedback'][0]['outcome']=='APPLIED'
        assert waiting['choice']['questions'][0]['workflow_status']=='ACTION_APPLIED_AWAITING_WORK_ACK'
        assert next(r for r in waiting['choice']['stage_gates'] if r['stage']=='recheck')['prerequisites_met'] is False
        task={r['id']:r for r in data['work_records']}
        assert task['network-case/action-0']['completed_at_s']==3.25
        assert task['network-case/recheck-0']['completed_at_s']==5.25
        record={r['id']:r for r in data['inspection_records']}
        assert record['it-capacity-before']['availability']=='expired'
        after=record['it-capacity-after']
        assert (after['observed_at_s'],after['arrived_at_s'],after['value'])==(5.25,5.75,.75)
        assert data['resource_ledger']['spent_or_reserved']==dict(person_s=24.5,tool_s=24.5,cost=3)
        for key, expected in [('demand_service_unit_s',7),('delivered_service_unit_s',3.625),
                              ('service_deficit_time_s',3.375),('worker_work_person_s',3),('access_check_person_s',.75)]:
            assert abs(data['summary'][key]-expected)<=1e-12, key
        assert decisions[-1]['choice']['questions'][0]['risk_closed'] is False
        guard()
        save(args.output/'verification.json',dict(status='SAVED_ASSERTIONS_VERIFIED_NOT_NATIVE_RERUN',
            original_job='133138',original_native_status='FAILED_NOT_RELABELED',original_runtime_source=protocol['runtime_source'],
            correction='The canonical public availability enum is expired, not the frozen test literal stale. All other behavior expectations unchanged.',
            checked_behavior='Arrived action report with missing workforce ACK withholds recheck; later ACK releases it. Expired initial measurement does not erase spent action or budget.',
            source_guard='PASS_BEFORE_AND_AFTER',facility_calls=0,direct_public_choice_calls=0,model_calls=0,new_research_trials=0))
        terminal.update(status='COMPLETED',source_guard='PASS_BEFORE_AND_AFTER',
            outputs={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in args.output.iterdir() if p.is_file()})
        print(json.dumps(dict(status='SAVED_ASSERTIONS_VERIFIED_NOT_NATIVE_RERUN',facility_calls=0)))
    except BaseException as error:
        terminal.update(error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc())
        raise
    finally:
        terminal['finished_at_utc']=datetime.now(timezone.utc).isoformat()
        save(args.output/'terminal.json',terminal)


if __name__=='__main__':
    main()
