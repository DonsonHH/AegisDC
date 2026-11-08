"""Verify the declared Git delivery, captured source identities and remote originals."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
BASE = '047fc6615313fe28137a17eaefcb35d714222753'
MANIFEST = 'evidence/mainline/engineering/39b-root-acceptance/delivery-manifest-v2.json'
PACKET = 'evidence/mainline/engineering/39b-root-acceptance/root/'
DEVELOPMENT = 'evidence/mainline/engineering/39b-development/'
REMOTE = Path('/share/home/renly/renly-patrol-rsi/mainline/39b-development')
ORIGINAL_RECEIPTS = 'ae101123b7d55c3eeff58c1bfe3df0e63291b53f'
FRESH_TOOL = 'scripts/verify_39b_delivery.py'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def git(*args, input=None):
    return subprocess.check_output(['git', *args], cwd=ROOT, input=input)


def sha(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def check_file(path, record):
    require(path.is_file() and path.stat().st_size == record['bytes'] and sha(path) == record['sha256'],
            'Declared artifact differs: ' + str(path))


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def tree_blobs(commit, *paths):
    result={}
    for row in git('ls-tree','-r','-z',commit,'--',*paths).split(b'\0'):
        if row:
            header,name=row.split(b'\t',1)
            _,kind,identity=header.split()
            if kind==b'blob':
                result[name.decode()]=identity.decode()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--delivery-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(bool(os.environ.get('SLURM_JOB_ID')) and socket.gethostname().split('.')[0] != 'mu01',
            'Saved delivery verification requires a Slurm allocation')
    require(not sys.flags.optimize, 'Use non-optimized verification Python')
    args.output.mkdir(exist_ok=False)
    terminal = dict(status='FAILED', delivery_commit=args.delivery_commit)
    save(args.output/'attempt.json', dict(classification='FRESH_GIT_SAVED_DELIVERY_NOT_RESEARCH_TRIAL',
        started_at_utc=datetime.now(timezone.utc).isoformat(), source=args.delivery_commit,
        slurm_job_id=os.environ['SLURM_JOB_ID'], node=socket.gethostname(),
        facility_calls=0, direct_public_choice_calls=0, model_calls=0, new_research_trials=0))
    try:
        require(git('rev-parse','HEAD').decode().strip() == args.delivery_commit, 'Wrong actual fresh delivery HEAD')
        require(not git('status','--porcelain').strip(), 'Fresh checkout is dirty')
        require((ROOT/MANIFEST).read_bytes() == git('show',args.delivery_commit+':'+MANIFEST),
                'Manifest bytes differ from the committed delivery')
        manifest = read_json(ROOT/MANIFEST)
        require(manifest['base_commit'] == BASE and bool(manifest['files']), 'Declare a nonempty fixed-base delivery')
        require(manifest['original_receipt_commit']==ORIGINAL_RECEIPTS, 'Bind the already reviewed original receipts')
        expected = set(git('diff','--name-only',BASE,args.delivery_commit).decode().splitlines()) - {MANIFEST}
        require(set(manifest['files']) == expected, 'Delivery set differs from the complete committed change set')
        for name, record in manifest['files'].items():
            path=ROOT/name
            require(path.resolve().is_relative_to(ROOT) and not path.is_symlink(), 'Artifact path escapes its fresh checkout')
            check_file(path,record)
            require(path.read_bytes()==git('show',args.delivery_commit+':'+name), 'Artifact bytes differ from Git: '+name)
        require(not git('diff','--name-only',BASE,args.delivery_commit,'--','configs','evidence/mainline/research','paper/mainline-report-20261108').strip(),
                'Original configuration,180 research or accepted report changed')
        source=manifest['execution_source']
        original=read_json(ROOT/(PACKET+'terminal.json'))
        require(original['status']=='PASS' and original['source_commit']==source, 'Root regression did not pass at the declared source')
        require(original['verified_original_files']==20, 'Require all20 original historical artifacts')
        root_failed=read_json(ROOT/'evidence/mainline/engineering/39b-root-acceptance/attempt-01/terminal.json')
        require(root_failed['status']=='FAILED' and root_failed['tests']['run']==609
                and root_failed['tests']['failures']==1 and root_failed['tests']['errors']==root_failed['tests']['skipped']==0,
                'Original root01 failure was relabeled or lost')
        tests=original['tests']
        require(tests['run']==609 and tests['executed']==tests['run']
                and tests['failures']==tests['errors']==tests['skipped']==0, 'Root test gate differs')
        guard=read_json(ROOT/(PACKET+'source-guard.json'))
        require(guard['source']==source and guard['source_guard']=='PASS_BEFORE_AND_AFTER', 'Root source guard differs')
        require(guard['numpy']=='2.3.5' and guard['torch']=='2.6.0+cpu', 'Wrong frozen regression packages')
        references=[]
        execution_files=read_json(ROOT/(PACKET+'source-manifest-before.json'))
        require(bool(execution_files), 'Root execution source set must be nonempty')
        current_files=tree_blobs(args.delivery_commit,'src','scripts','tests','configs')
        current_files={name:blob for name,blob in current_files.items() if name.endswith(('.py','.json'))}
        require(FRESH_TOOL not in execution_files and set(current_files)==set(execution_files)|{FRESH_TOOL},
                'Current execution set differs from the passing root source plus the one declared saved-only verifier')
        for name,record in execution_files.items():
            require(current_files[name]==record['git_blob'], 'Post-root execution bytes changed: '+name)
            references.append((args.delivery_commit,name,record))
        originals=tree_blobs(ORIGINAL_RECEIPTS,DEVELOPMENT,'evidence/mainline/engineering/39b-root-acceptance')
        current_receipts=tree_blobs(args.delivery_commit,DEVELOPMENT,'evidence/mainline/engineering/39b-root-acceptance')
        require(bool(originals) and all(current_receipts.get(name)==blob for name,blob in originals.items()),
                'An original captured receipt, index, review, tool snapshot or data file changed after its review')
        for name in manifest['files']:
            if name.startswith('evidence/mainline/engineering/39b-root-acceptance/') and name.endswith('/source-manifest-before.json'):
                parent=(ROOT/name).parent
                captured_terminal=read_json(parent/'terminal.json')
                captured_source=captured_terminal['source_commit']
                check_file(ROOT/name,captured_terminal['output_files']['source-manifest-before.json'])
                for path,record in read_json(ROOT/name).items():
                    references.append((captured_source,path,record))
            if name.startswith('evidence/mainline/engineering/39b-root-acceptance/') and name.endswith('/source-manifest.json'):
                captured=read_json(ROOT/name)
                for path,record in captured['files'].items():
                    references.append((captured['source_commit'],path,record))
                require(sha((ROOT/name).parent/'job.slurm')==captured['job_script_sha256'],
                        'Root submission script differs from its frozen capture manifest')
        private_inputs=0
        for name in manifest['files']:
            if not name.startswith(DEVELOPMENT) or not name.endswith('/source-manifest.json'):
                continue
            path=ROOT/name;captured=read_json(path)
            require(bool(captured['files']), 'Captured execution input set must be nonempty')
            attempt=read_json(path.parent/'attempt.json')
            if 'manifest_sha256' in attempt:
                require(sha(path)==attempt['manifest_sha256'], 'Captured manifest differs from its original pre-work attempt')
            else:
                require(name==DEVELOPMENT+'slice-08/saved-correction-01/source-manifest.json'
                        and attempt['classification']=='SAVED_ASSERTION_CORRECTION_NOT_PHYSICAL_RETRY'
                        and attempt['facility_calls']==attempt['direct_public_choice_calls']==attempt['model_calls']==0,
                        'Captured attempt omitted its manifest hash outside the one classified saved-only legacy receipt')
                require(path.read_bytes()==git('show',ORIGINAL_RECEIPTS+':'+name),
                        'Classified saved-only manifest differs from the exact reviewed original Git blob')
            for staged, record in captured['files'].items():
                if record.get('git_blob') is not None or record.get('source_path') is not None:
                    references.append((captured['source_commit'],record.get('source_path') or staged,record))
                elif staged=='job.slurm':
                    check_file(path.parent/'job.slurm',record)
                elif staged in {'source-objects.pack','execution-snapshot.json'}:
                    require('attempt' in captured and Path(captured['attempt']).name==captured['attempt'],
                            'Declare the original private staging identity')
                    private_input=REMOTE/captured['attempt']/staged
                    require(private_input.resolve().is_relative_to(REMOTE.resolve()), 'Private staging input escapes its namespace')
                    check_file(private_input,record)
                    private_inputs+=1
                else:
                    raise ValueError('Unclassified captured durable input: '+staged)
        queries=[commit+':'+name for commit,name,_ in references]
        raw=git('cat-file','--batch',input=('\n'.join(queries)+'\n').encode())
        offset=0
        for (commit,name,record),query in zip(references,queries):
            end=raw.index(b'\n',offset);header=raw[offset:end].split()
            require(len(header)==3 and header[1]==b'blob','Recorded runtime source missing: '+query)
            size=int(header[2]);start=end+1;blob=raw[start:start+size]
            require(size==record['bytes'] and hashlib.sha256(blob).hexdigest()==record['sha256'],
                    'Recorded execution source/tool/input differs: '+query)
            if record.get('git_blob') is not None:
                require(header[0].decode()==record['git_blob'],'Captured Git object differs: '+query)
            offset=start+size+1
        require(offset==len(raw),'Extra source-object bytes')
        remote_originals=0
        for name in manifest['files']:
            if name.endswith('/originals-manifest.json') or name.endswith('/review-originals-manifest.json'):
                path=ROOT/name;review=read_json(path)
                require(bool(review['files']), 'Review original identity set must be nonempty')
                for relative,record in review['files'].items():
                    original_path=path.parent/relative
                    require(original_path.resolve().is_relative_to(ROOT), 'Review original path escapes the checkout')
                    require(original_path.relative_to(ROOT).as_posix() in manifest['files'], 'Review original omitted from delivery')
                    check_file(original_path,record)
            if name.startswith(DEVELOPMENT) and name.endswith('/terminal.json'):
                terminal_path=ROOT/name;captured_terminal=read_json(terminal_path)
                outputs=captured_terminal.get('output_files',{})
                native={k:v for k,v in outputs.items() if k.startswith('actual-run/') or '/actual-run/' in k}
                if captured_terminal.get('new_facility_calls',0)>0 and captured_terminal.get('returned_decisions',0)>0:
                    require(bool(native), 'Returned native run lost its complete output inventory')
                if native:
                    index_path=terminal_path.parent/'private-raw-index.json'
                    require(index_path.relative_to(ROOT).as_posix() in manifest['files'], 'Complete native output index omitted')
                    index=read_json(index_path)
                    require(bool(index['files']) and index['files']==native, 'Native index differs from the exact original terminal output set')
                for relative,record in outputs.items():
                    candidates=[terminal_path.parent/relative,terminal_path.parent/relative.replace('/','__')]
                    for output_path in candidates:
                        if output_path.is_file():
                            check_file(output_path,record)
                            break
            if name.startswith(DEVELOPMENT) and name.endswith('/private-raw-index.json'):
                index=read_json(ROOT/name);private_root=Path(index['remote_root'])
                require(bool(index['files']), 'Native original index must be nonempty')
                require(private_root.resolve().is_relative_to(REMOTE.resolve()),'Native trace root escapes its declared private namespace')
                for relative,record in index['files'].items():
                    path=private_root/relative
                    require(path.resolve().is_relative_to(private_root.resolve()),'Private artifact path escapes its root')
                    check_file(path,record)
                    if path.suffix=='.json':
                        read_json(path)
                    elif path.suffix=='.jsonl':
                        lines=0
                        with path.open(encoding='utf-8') as stream:
                            for line in stream:
                                json.loads(line)
                                lines+=1
                        require(lines>0, 'Native JSONL must contain actual records')
                    else:
                        raise ValueError('Unclassified native readability check: '+str(path))
                    remote_originals+=1
        failed=read_json(ROOT/(DEVELOPMENT+'slice-08/14-late-ack-qualification/terminal.json'))
        corrected=read_json(ROOT/(DEVELOPMENT+'slice-08/saved-correction-01/verification.json'))
        require(failed['status']=='FAILED' and corrected['status']=='SAVED_ASSERTIONS_VERIFIED_NOT_NATIVE_RERUN',
                'Original failed qualification or separate saved correction was relabeled')
        require(not git('status','--porcelain').strip(),'Verification changed the fresh checkout')
        save(args.output/'verification.json',dict(status='PASS',delivery_commit=args.delivery_commit,
            execution_source=source,declared_files=len(manifest['files']),recorded_source_file_checks=len(references),
            current_execution_files=len(execution_files),original_receipt_files=len(originals),
            private_staging_inputs=private_inputs,private_native_files=remote_originals,
            root_tests=tests,verified_original_files=original['verified_original_files'],
            failures_preserved=True,original_registered_research_runs=180,facility_calls=0,
            direct_public_choice_calls=0,model_calls=0,new_research_trials=0))
        terminal.update(status='PASS',declared_files=len(manifest['files']),source_file_checks=len(references),
                        private_native_files=remote_originals)
        print(json.dumps(terminal))
    except BaseException as error:
        terminal.update(error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc())
        raise
    finally:
        terminal['finished_at_utc']=datetime.now(timezone.utc).isoformat()
        save(args.output/'terminal.json',terminal)


if __name__=='__main__':
    main()
