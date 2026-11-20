"""Check archived attempt and release bytes in a fresh detached checkout; no model imports."""
import hashlib
import json
from pathlib import Path
import posixpath
import re
import subprocess
import sys
import tarfile

PACK='docs/mainline/v6-intake-expiry-closeout-v1'
OLD='docs/mainline/v6-intake-engineering-v1'
BASE='a1adc22cb5fe2a23d6b30185187054bd6dd98ea2'
FREEZE='d456ee0b13ad5a3da6d1d8236bf9405fda8c45a5'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def checked(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    checkout, attempt, output=map(Path,sys.argv[1:4])
    def git(*args):
        return subprocess.check_output(['git','-C',str(checkout),*args])
    head=git('rev-parse','HEAD').decode().strip()
    checked(not git('status','--porcelain','--untracked-files=no'),'Fresh checkout is dirty')
    release=json.loads((checkout/PACK/'result.json').read_bytes())
    launch=json.loads((attempt/'launch.json').read_bytes())
    actual=release['attempts'][0]
    checked(sha((attempt/'source.tar.gz').read_bytes())==actual['source_and_durable_files_sha256']['source.tar.gz']
        and sha((attempt/'launch.json').read_bytes())==actual['source_and_durable_files_sha256']['launch.json']
        and sha((attempt/'report.json').read_bytes())==actual['source_and_durable_files_sha256']['output/report.json'],'Attempt transfer drift')
    source_commit=launch['checker_revision']
    checked(source_commit==release['checker_revision'] and launch['baseline']==BASE and launch['freeze_revision']==FREEZE,
        'Execution and freeze identities differ')
    with tarfile.open(attempt/'source.tar.gz','r:gz') as archive:
        archive_files={m.name:sha(archive.extractfile(m).read()) for m in archive if m.isfile()}
    checked(archive_files==launch['files'],'Archived files differ from launch manifest')
    changed=git('diff','--name-only',BASE,head).decode().splitlines()
    nav={'docs/MAINLINE.md','docs/mainline/progress.json','docs/current-research.json'}
    checked(all(name in nav or name.startswith(PACK+'/') or name=='scripts/qualify_v6_intake_expiry.py' for name in changed),
            'A pre-existing protected file or out-of-scope runtime changed')
    old_spec=json.loads((checkout/OLD/'integrity.json').read_bytes())
    protected=old_spec['frozen_slice57_sha256']
    deliverables={}
    targets=set()
    for name in sorted(set(changed)|set(archive_files)|set(protected)):
        file=checkout/name
        data=file.read_bytes()
        checked(data==git('cat-file','blob',head+':'+name),'Fresh bytes differ from committed blob: '+name)
        digest=sha(data)
        if name in archive_files:
            checked(digest==archive_files[name] and sha(git('cat-file','blob',source_commit+':'+name))==digest,
                    'Executed/archived/released file differs: '+name)
        if name in changed:
            deliverables[name]={'sha256':digest,'bytes':len(data)}
        if name in protected:
            checked(digest==protected[name], 'Historical slice 57 differs: '+name)
        if name.startswith(PACK+'/') and name.endswith('.md'):
            for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)',data.decode()):
                path=link.split('#')[0]
                if path and not re.match(r'[a-z]+:',path):
                    target=posixpath.normpath(posixpath.join(posixpath.dirname(name),path))
                    git('cat-file','-e',head+':'+target)
                    targets.add(target)
    freeze=json.loads((checkout/PACK/'freeze.json').read_bytes())
    for name in ['freeze.json','spec.md','author_freeze.py']:
        path=PACK+'/'+name
        checked(git('cat-file','blob',FREEZE+':'+path)==(checkout/path).read_bytes(),'Freeze revision changed: '+path)
    for case,record in zip(freeze['new_public_witnesses'],release['new_public_qualification'],strict=True):
        checked(record['unit']==case['id'] and record['input_sha256']==case['public_arguments_sha256']
                and record['passed'] and not record['mismatches'], 'Public witness receipt drift')
    old=release['original_frozen_comparison']['actual']
    prior=release['post_review_saved_checks']
    checked(old['accepted_unit_assertions']==[309,309] and old['original_full_assertions']==[316,325]
        and old['unmatched_unit_assertions']==[7,16] and all(q['passed'] for q in prior.values()), 'Result scopes differ')
    state=json.loads((checkout/'docs/mainline/progress.json').read_bytes())
    checked(not state['active_implementations'] and state['v6_intake_expiry_closeout']['status']=='DELIVERED_AWAITING_REVIEW'
        and state['v6_intake_expiry_closeout']['actual_new_facility_calls']==0,'Review gate differs')
    receipt=dict(schema='aegisdc-intake-expiry-git-integrity-v1',checked_content_revision=head,baseline=BASE,freeze_revision=FREEZE,
        checker_revision=source_commit,checked_new_or_current_files=deliverables,archived_files_checked=len(archive_files),
        frozen_slice57=protected,all_baseline_diffs_within_additive_package_and_three_status_files=True,
        verified_markdown_targets=sorted(targets),new_job=actual['job'],new_facility_calls=0,
        terminal_report_sha256=actual['source_and_durable_files_sha256']['output/report.json'])
    with output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(receipt,stream,ensure_ascii=False,indent=2)
        stream.write('\n')
    print('Verified',len(deliverables),'delivery/status files,',len(archive_files),'archived execution files,',
          len(targets),'local document targets and',len(protected),'frozen slice 57 files.')


if __name__=='__main__':
    main()
