"""Verify the ticket 28 integration packet, charts and immutable capture without rerunning."""
import argparse
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[4]
PACKET = 'evidence/mainline/engineering/28-root-acceptance'
CASE_DIR = 'evidence/mainline/engineering/28-negative-controls'
AUTHORITY = 'docs/mainline/evidence/28-root.json'
AUTHOR = '2c6ad4b36e87e61f0b0819bc76b32532a45e5dd3'
VISUALS = 'e7c8b5b156016aeec773ed1019eddc141a7960fa'
EXECUTION = 'd350cd96750612a8660e2854b217e9d5e49d2ab5'
PREMEETING = '076d9aa15c5bc99a5b7985f296e15543b7b0f3d7'
FIXTURE_GROUPS = ('26-online-development','27-development','27-replay-development')
CHECKOUT_CRLF = {
    'configs/candidate-example.json', 'configs/coupled-example.json', 'configs/demo.json',
    'configs/event-priority.json', 'configs/event-validation-amended.json', 'configs/event-validation-amendment-draft.json',
    'configs/event-validation.json', 'configs/facility-structure-v0.1.json', 'configs/feedback-study.json',
    'configs/parent-rule.json', 'configs/response-defer-study.json', 'configs/risk-method-demo.json',
    'configs/risk-response.json',
}


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(raw):
    return sha256(raw).hexdigest()


def identity(raw):
    return {'sha256':digest(raw),'bytes':len(raw)}


def read(path):
    return json.loads(path.read_bytes())


def write_new(path, value):
    with path.open('x',encoding='utf-8',newline='\n') as f:
        f.write(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def git(root,*args):
    return subprocess.check_output(['git',*args],cwd=root)


def is_durable(name):
    p=PurePosixPath(name)
    return '__pycache__' not in p.parts and p.suffix not in {'.pyc','.pyo'}


def files(path):
    return {p.relative_to(path).as_posix() for p in path.rglob('*')
            if p.is_file() and is_durable(p.relative_to(path).as_posix())}


def tree(root, rev, *scopes):
    return set(git(root,'ls-tree','-rz','--name-only',rev,'--',*scopes).decode().strip('\0').split('\0'))-{''}


def same_paths(root, before, after, paths):
    require(not git(root,'diff','--name-only',before,after,'--',*sorted(paths)), 'Preserved committed path changed')


def archive_check(path, items):
    with zipfile.ZipFile(path) as archive:
        require(len(archive.namelist())==len(set(archive.namelist())) and set(archive.namelist())==set(items),
                'Archive differs from predeclared member set: '+path.name)
        for name, item in items.items():
            pure=PurePosixPath(name)
            require(not pure.is_absolute() and '..' not in pure.parts and is_durable(name)
                    and identity(archive.read(name))==item, 'Archive original differs: '+name)
    return len(items)


def verify(root, delivery):
    root = root.resolve()
    p = root/PACKET
    require(git(root,'rev-parse','HEAD').decode().strip()==delivery and not git(root,'status','--porcelain'),
            'Use a clean checkout of the exact integrated packet')
    require(git(root,'rev-parse','pre-meeting-20261103^{}').decode().strip()==PREMEETING,'Pre-meeting tag changed')
    r,d = (read(p/name) for name in ('receipt.json','declaration.json'))
    names=set(d['artifacts'])
    require(len(d['artifacts'])==len(names) and names==set(r['artifacts']) and d['terminal']=='receipt.json'
            and files(p)==names|{'receipt.json'} and r['status']=='CANDIDATE_PENDING_FRESH_DELIVERY',
            'Root durable roles differ')
    full={f'{PACKET}/{name}' for name in names|{'receipt.json'}}
    require(tree(root,delivery,PACKET)==full,'Committed packet membership differs')
    for name in names|{'receipt.json'}:
        raw=(p/name).read_bytes()
        require(raw==git(root,'cat-file','blob',f'{delivery}:{PACKET}/{name}'),'Packet Git blob differs: '+name)
        if name!='receipt.json':
            require(identity(raw)==r['artifacts'][name],'Packet original differs: '+name)
    source=r['tested_source']
    require(d['source']==source and len(git(root,'show','-s','--format=%P',source).split())==2,
            'Actual root integrated source not verified')
    sys.path.insert(0,str(p/'tools'))
    from verify_28_capture_delivery import verify as verify_author
    author=verify_author(root,delivery)
    require(author['execution_source']==EXECUTION and author['all_case_artifacts']==38
            and author['launch_artifacts']==7 and author['retained_history']['retained_failure_attempts']==1,
            'Frozen author history differs')
    raw_paths=tree(root,AUTHOR,CASE_DIR+'/capture-20261107-04',CASE_DIR+'/capture-04-launch')
    require(len(raw_paths)==45,'Author data plus launch count differs')
    same_paths(root,AUTHOR,delivery,raw_paths)
    fresh=read(p/'checks/author-fresh.json')
    require(fresh['delivery']==AUTHOR and fresh['status']=='PASS_CLEAN_SAVED_DELIVERY'
            and fresh['verifier_sha256']==digest((p/'tools/verify_28_capture_delivery.py').read_bytes())
            and fresh['new_physics']==fresh['new_selector_calls']==fresh['new_closure_calls']==0,
            'Actual author checkout proof differs')
    vis_paths=tree(root,VISUALS,CASE_DIR+'/figures',CASE_DIR+'/README.md')
    require(len(vis_paths)==9,'Report and visual durable set differs')
    same_paths(root,VISUALS,delivery,vis_paths)
    fig=root/CASE_DIR/'figures'
    render,qa,draft=(read(fig/name) for name in ('render.json','visual-review.json','initial-render-receipt.json'))
    require(len(render['artifacts'])==4 and len(render['source'])==9 and render['execution_source']==EXECUTION
            and render['source']==draft['source'] and qa['status']=='PASS' and qa['actually_viewed_pngs']==2
            and qa['report_delivery']==AUTHOR and qa['initial_render_sha256']==digest((fig/'initial-render-receipt.json').read_bytes())
            and qa['verified_images']=={n:sha for n,sha in render['artifacts'].items() if n.endswith('.png')},
            'Visual inspection or exact origin binding differs')
    for relative, sha in render['source'].items():
        require(digest((root/CASE_DIR/'capture-20261107-04'/relative).read_bytes())==sha,'Figure input differs')
    for name,sha in render['artifacts'].items():
        require(digest((fig/name).read_bytes())==sha,'Final figure changed')
    require(digest((fig/'render_negative_controls.py').read_bytes())==render['renderer_sha256'],'Renderer changed')
    summary,guard,raw_evidence=(read(p/'raw'/name) for name in ('summary.json','source-guard.json','evidence.json'))
    tests=summary['tests']
    require(summary['overall']==summary['engineering']==summary['evidence']==tests['gate']=='PASS'
            and summary['research']=='NOT_RUN' and tests['run']==tests['executed']==567
            and tests['failures']==tests['errors']==tests['skipped']==0
            and summary['verified_original_files']==raw_evidence['verified_original_files']==20,'Integrated test gate differs')
    log=(p/'raw/tests.log').read_text(encoding='utf-8')
    require('Ran 567 tests in ' in log and log.rstrip().endswith('OK'),'Integrated full log is incomplete')
    require(guard['source_commit_before']==guard['source_commit_after']==source and
            guard['sources_unchanged'] and guard['head_unchanged'] and guard['sources_match_declared_git_checkout'],
            'Integrated source guard differs')
    source_paths={n for n in tree(root,source,'src','scripts','tests','configs') if n.endswith(('.py','.json'))}
    require(set(guard['committed_sources'])==set(guard['actual_sources'])==source_paths and len(source_paths)==301,
            'Integrated guarded source roles differ')
    same_paths(root,source,delivery,source_paths)
    from inspection_delivery import hashes
    require(hashes(source,source_paths)==hashes(delivery,source_paths)==guard['committed_sources'],
            'Recorded integrated source bytes differ')
    actual=guard['actual_sources']
    converts={}
    for name in source_paths:
        raw=(root/name).read_bytes()
        blob_hash=guard['committed_sources'][name]
        if digest(raw)!=blob_hash or actual[name]!=blob_hash:
            original=git(root,'cat-file','blob',f'{source}:{name}')
            require(name in CHECKOUT_CRLF and b'\r' not in original and raw in (original,original.replace(b'\n',b'\r\n')),
                    'Undeclared checkout transformation: '+name)
            converted=original.replace(b'\n',b'\r\n')
            if actual[name]!=blob_hash:
                require(actual[name]==digest(converted),'Integrated execution bytes differ: '+name)
                converts[name]=dict(rule='exact_lf_to_crlf_checkout',actual_sha256=digest(converted),
                    committed_sha256=blob_hash,crlf_count=original.count(b'\n'))
    require(converts==guard['checkout_classification'],'Integrated conversion classification differs')
    launch,process,terminal=(read(p/'launch'/name) for name in ('attempt.json','process.json','terminal.json'))
    require(launch['source']==process['source']==terminal['source']==source and terminal['status']=='COMPLETED'
            and terminal['returncode']==0 and terminal['summary_exists'] and launch['status']=='STARTED'
            and launch['runner_sha256']==guard['runner_sha256']==digest((p/'tools/root_runner.py').read_bytes())
            and launch['launcher_sha256']==digest((p/'tools/root_launcher.py').read_bytes())
            and launch['python_executable_sha256']==guard['python_executable_sha256'],
            'Integrated root launcher record differs')
    require(all(terminal[f'{n}_sha256']==digest((p/'launch'/f'{n}.txt').read_bytes()) for n in ('stdout','stderr'))
            and read(p/'launch/stdout.txt')['root_gate']=='PASS','Integrated native streams differ')
    inventory=read(p/'inventory.json')
    require(set(inventory['archives'])==set(d['archive_roles'])=={'root-fixtures.zip','reviews.zip'},'Unexpected archive roles')
    sizes={}
    for name,items in inventory['archives'].items():
        require(sorted(items)==d['archive_roles'][name],'Archive membership differs from declaration')
        sizes[name]=archive_check(p/name,items)
    with zipfile.ZipFile(p/'reviews.zip') as archive:
        final={}
        for row in inventory['reviews']:
            report=json.loads(archive.read(row['report']))
            sealed=json.loads(archive.read(row['manifest']))['artifacts']
            require(report['delivery']==AUTHOR and report['execution_source']==EXECUTION and report['axis']==row['axis']
                    and report['status'].startswith('PASS') and not report['unresolved'] and report['checks']==row['checks'],
                    'Independent saved-data review not passed on actual data')
            prefix=row['manifest'].rsplit('/',1)[0]+'/'
            require(all(identity(archive.read(prefix+name))==pin for name,pin in sealed.items()),
                    'Sealed independent report member differs')
            final[row['axis']]=row['checks']
        require(final=={'Spec':9793,'Standards':7932},'Both exact independent saved-data reviews are required')
    with zipfile.ZipFile(p/'root-fixtures.zip') as archive:
        items=inventory['archives']['root-fixtures.zip']
        cases=inventory['fixture_cases']
        require(set(cases)==set(launch['fixture_baseline'])==set(FIXTURE_GROUPS),'Fixture scopes differ')
        seen={(name.split('/')[0],name.split('/')[1]) for name in items}
        require(seen=={(group,case) for group in cases for case in cases[group]},'Fixture attempt set differs')
        runtime={n:sha for n,sha in actual.items() if n.startswith('src/') and n.endswith('.py')}
        for group in cases:
            require(not set(cases[group])&set(launch['fixture_baseline'][group]),'Root regression overwrote an earlier fixture')
            for case in cases[group]:
                prefix=f'{group}/{case}/'
                attempt_file='development-attempt.json' if group=='27-replay-development' else 'attempt.json'
                record=json.loads(archive.read(prefix+attempt_file))
                require(record['source_commit']==source and
                        {name:sha for name,sha in record['source_files'].items() if name in runtime}==runtime,
                        'Root engineering fixture belongs to a different source')
                snapshot='runtime-source/' if group=='26-online-development' else 'pre-call/'
                require(all(items[prefix+snapshot+name]['sha256']==sha for name,sha in record['source_files'].items()),
                        'Root fixture snapshot differs')
    gate=read(root/AUTHORITY)
    require(gate['status'] in {'CANDIDATE_PENDING_FRESH_DELIVERY','ACCEPTED'}
            and gate['actual_root_source']==source and gate['packet_receipt_sha256']==digest((p/'receipt.json').read_bytes()),
            'Root acceptance does not bind this packet')
    return dict(status='PASS',delivery_commit=delivery,actual_root_source=source,
        packet_artifacts=len(names),archive_members=sizes,root_tests=tests,guarded_files=len(source_paths),
        historical_originals=20,final_review_checks=final,author=author,visuals_viewed=2,author_original_artifacts=45,
        fixture_counts={k:len(rows) for k,rows in cases.items()},new_physics=0,new_selector_calls=0,new_full_regression=False,
        registered_research_trials=0,field_calibration='PENDING',overall_goal='ACTIVE',
        verifier_sha256=digest(Path(__file__).read_bytes()))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delivery-commit',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=verify(ROOT,args.delivery_commit)
    write_new(args.output,result)
    print(json.dumps(result,ensure_ascii=False))