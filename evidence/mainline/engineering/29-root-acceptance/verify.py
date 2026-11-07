"""Build and verify the ticket 29 integrated acceptance packet without replaying captures."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path.cwd()
sys.path.insert(0,str(ROOT/'scripts'))
from inspection_delivery import durable, git, hashes, read, require, write
from run_parameter_domain_witnesses import PROTOCOL, _verify
from preserve_parameter_domain_development import verify as verify_development

PACKET = 'evidence/mainline/engineering/29-root-acceptance'
PACKAGE = 'evidence/mainline/engineering/29-uncertainty-domain'
CANDIDATE = '6b7606e1d739e821802bcd8c189a3cda94c35e61'
AUTHOR = '9e221a77663508b46e04c6d5f9de505baa34d927'
SOURCE = 'c6197fc857b8032109328f6e68aa75b03c717268'
PREMEETING = '076d9aa15c5bc99a5b7985f296e15543b7b0f3d7'
RAW = ('summary.json','evidence.json','tests.log','source-guard.json')
LAUNCH = ('attempt.json','process.json','terminal.json','stdout.txt','stderr.txt')
FIXTURES = {'26-online-development':18,'27-development':1,'27-replay-development':2}
ROOT_TOOLS = ('run_29_root_acceptance.py','launch_29_root_full_01.py')


def digest(raw):
    return sha256(raw).hexdigest()


def head():
    return git('rev-parse','HEAD').decode().strip()


def tree(revision,*paths):
    return set(git('ls-tree','-rz','--name-only',revision,'--',*paths).decode().split('\0')) - {''}


def verify_archive(path, members):
    with ZipFile(path) as archive:
        names = archive.namelist()
        require(len(set(names)) == len(names) and set(names) == set(members), f'Archive members differ: {path.name}')
        for name,sha in members.items():
            pure = Path(name)
            require(not pure.is_absolute() and '..' not in pure.parts
                    and '__pycache__' not in pure.parts and pure.suffix not in ('.pyc','.pyo')
                    and digest(archive.read(name)) == sha, f'Invalid archive member: {name}')
    return len(members)


def root_gate(p):
    summary, evidence, guard = (read(p/'raw'/name) for name in ('summary.json','evidence.json','source-guard.json'))
    tests = summary['tests']
    require(summary['overall']==summary['engineering']==summary['evidence']==tests['gate']=='PASS'
            and summary['research']=='NOT_RUN' and tests['run']==tests['executed']==576
            and tests['failures']==tests['errors']==tests['skipped']==0
            and summary['verified_original_files']==evidence['verified_original_files']==20,
            'Integrated test/evidence result differs')
    log = (p/'raw/tests.log').read_text(encoding='utf-8')
    require('Ran 576 tests in ' in log and log.rstrip().endswith('OK'), 'Integrated full log incomplete')
    start, process, terminal = (read(p/'launch'/name) for name in ('attempt.json','process.json','terminal.json'))
    require(start['status']=='STARTED' and start['source']==process['source']==terminal['source']==SOURCE
            and terminal['status']=='COMPLETED' and terminal['returncode']==0 and terminal['summary_exists']
            and start['cache_prefix_existed_before'] is False
            and read(p/'launch/stdout.txt')['root_gate']=='PASS', 'Integrated launcher result differs')
    require(all(terminal[f'{name}_sha256']==digest((p/'launch'/f'{name}.txt').read_bytes())
                for name in ('stdout','stderr')), 'Original launch bytes differ')
    require(start['runner_sha256']==guard['runner_sha256']==digest((p/'tools'/ROOT_TOOLS[0]).read_bytes())
            and start['launcher_sha256']==digest((p/'tools'/ROOT_TOOLS[1]).read_bytes())
            and start['python_executable_sha256']==guard['python_executable_sha256'],
            'Integrated tool identity differs')
    require(guard['source_commit_before']==guard['source_commit_after']==SOURCE
            and guard['sources_unchanged'] and guard['head_unchanged'] and guard['sources_match_declared_git_checkout'],
            'Integrated source guard differs')
    paths = {name for name in tree(SOURCE,'src','scripts','tests','configs') if name.endswith(('.py','.json'))}
    require(paths==set(guard['committed_sources'])==set(guard['actual_sources'])
            and guard['committed_sources']==hashes(SOURCE,paths)==hashes(head(),paths), 'Integrated source hashes differ')
    for name,sha in guard['committed_sources'].items():
        actual = guard['actual_sources'][name]
        working = digest((ROOT/name).read_bytes())
        if name in guard['checkout_classification']:
            item = guard['checkout_classification'][name]
            blob = git('cat-file','blob',f'{SOURCE}:{name}')
            require(b'\r' not in blob and item==dict(rule='exact_lf_to_crlf_checkout',actual_sha256=actual,
                    committed_sha256=sha,crlf_count=blob.count(b'\n'))
                    and actual==digest(blob.replace(b'\n',b'\r\n')) and working in (actual,sha),
                    'Undeclared checkout encoding change')
        else:
            require(working==actual==sha, 'Integrated working source differs')
    require(len(guard['checkout_classification'])<=4 and set(guard['checkout_classification'])<={
        'configs/candidate-example.json','configs/demo.json','configs/feedback-study.json','configs/parent-rule.json'},
        'Integrated checkout classification escaped the declared set')
    return tests,guard,start


def assemble():
    require(head()==SOURCE and not git('status','--porcelain'), 'Use the clean integration source')
    run = ROOT/'runs/mainline-M5-29-root-acceptance-20261107-01'
    launch = ROOT/'.work/29-root-full-launch-01'
    p = ROOT/PACKET
    p.mkdir()
    files = {f'raw/{name}':run/name for name in RAW}
    files.update({f'launch/{name}':launch/name for name in LAUNCH})
    files.update({f'tools/{name}':ROOT/'.work'/name for name in ROOT_TOOLS})
    files['verify.py'] = Path(__file__)
    for name,source in files.items():
        path = p/name
        path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,path)
    tests,guard,start = root_gate(p)
    selected,cases = {},{}
    for group,count in FIXTURES.items():
        folder = ROOT/'.work'/group
        existing = set(start['fixture_baseline'][group])
        current = {entry.name:entry for entry in folder.iterdir() if entry.is_dir()}
        require(existing<=set(current), 'An earlier fixture folder was removed')
        cases[group] = sorted(set(current)-existing)
        require(len(cases[group])==count, f'Unexpected integrated fixture count: {group}')
        for case in cases[group]:
            path=current[case]
            selected.update({f'{group}/{case}/{name}':path/name for name in durable(path)})
    with ZipFile(p/'root-fixtures.zip','x',compression=ZIP_DEFLATED,compresslevel=6) as archive:
        members = {}
        for name,path in sorted(selected.items()):
            raw = path.read_bytes()
            archive.writestr(name,raw)
            members[name] = digest(raw)
    write(p/'fixtures.json',dict(cases=cases,members=members,
        scope='Engineering regression fixtures only, not the eight sealed cases and not research trials.'))
    write(p/'.gitattributes',('# Preserve exact raw Windows regression streams.\n' + ''.join(
        f'{name} -text whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol\n'
        for name in ('raw/summary.json','raw/evidence.json','raw/tests.log','launch/stdout.txt','launch/stderr.txt'))).encode())
    write(p/'README.md',('''# 第 29 项整合回归和保存验证

[工程报告与图表](../29-uncertainty-domain/README.md)汇总八个原始仿真工况。本包保留一次整合回归的原始日志、源码守卫、执行工具和测试夹具。576 项测试全部执行，20 份旧原件完整性检查通过。正式八例没有重跑。

[测试日志](raw/tests.log) · [守卫](raw/source-guard.json) · [测试夹具清单](fixtures.json) · [包清单](receipt.json)
''').encode())
    declared = set(files)|{'root-fixtures.zip','fixtures.json','.gitattributes','README.md'}
    require(durable(p)==declared,'Unexpected root artifacts')
    write(p/'receipt.json',dict(status='CANDIDATE_PENDING_FRESH_DELIVERY',tested_source=SOURCE,
        candidate=CANDIDATE,original_data=AUTHOR,tests=tests,guarded_files=len(guard['actual_sources']),
        artifacts={name:digest((p/name).read_bytes()) for name in sorted(declared)},registered_research_trials=0))
    print(json.dumps(dict(tests=tests,fixture_members=len(members),guarded_files=len(guard['actual_sources']),
        packet_artifacts=len(declared))))


def verify(delivery):
    require(head()==delivery and not git('status','--porcelain'),'Use a clean checkout at the packet commit')
    require(git('rev-parse','pre-meeting-20261103^{}').decode().strip()==PREMEETING,'Pre-meeting tag changed')
    require(git('show','-s','--format=%P',SOURCE).decode().split()==[
        '03e2e3e0e42f468733356dee1bb68cd259aeff1e',CANDIDATE],'Integration parents differ')
    p=ROOT/PACKET
    receipt=read(p/'receipt.json')
    require(receipt['tested_source']==SOURCE and receipt['candidate']==CANDIDATE and receipt['original_data']==AUTHOR
            and receipt['registered_research_trials']==0,'Root packet identity differs')
    names=set(receipt['artifacts'])|{'receipt.json'}
    committed={f'{PACKET}/{name}' for name in names}
    require(durable(p)==names and tree(delivery,PACKET)==committed and
            hashes(delivery,committed)=={name:digest((ROOT/name).read_bytes()) for name in committed}
            and all(digest((p/name).read_bytes())==sha for name,sha in receipt['artifacts'].items()),
            'Integrated packet files or exact Git blobs differ')
    tests,guard,start=root_gate(p)
    require(tests==receipt['tests'] and len(guard['actual_sources'])==receipt['guarded_files'],'Integrated test summary differs')
    fixtures=read(p/'fixtures.json')
    fixture_count=verify_archive(p/'root-fixtures.zip',fixtures['members'])
    require({k:len(v) for k,v in fixtures['cases'].items()}==FIXTURES,'Fixture groups differ')
    runtime={name:sha for name,sha in guard['actual_sources'].items() if name.startswith('src/') and name.endswith('.py')}
    with ZipFile(p/'root-fixtures.zip') as archive:
        observed={(name.split('/')[0],name.split('/')[1]) for name in archive.namelist()}
        require(observed=={(group,case) for group,cases in fixtures['cases'].items() for case in cases},
                'Unclassified fixture directory')
        for group,cases in fixtures['cases'].items():
            require(not set(cases)&set(start['fixture_baseline'][group]),'Earlier fixture overwritten')
            for case in cases:
                prefix=f'{group}/{case}/'
                name='development-attempt.json' if group=='27-replay-development' else 'attempt.json'
                record=json.loads(archive.read(prefix+name))
                require(record['source_commit']==SOURCE and
                        {n:h for n,h in record['source_files'].items() if n in runtime}==runtime,
                        'Fixture source differs')
                location='runtime-source/' if group=='26-online-development' else 'pre-call/'
                require(all(fixtures['members'][prefix+location+n]==h for n,h in record['source_files'].items()),
                        'Fixture source snapshot differs')
    origin=ROOT/PACKAGE
    protocol=read(ROOT/PROTOCOL)
    author=_verify(origin,protocol,read(ROOT/protocol['declaration']),delivery)
    require(author['verified_cases']==8 and author['verified_trace_points']==3330 and author['physical_reruns']==0,
            'Author saved verification differs')
    for pin,paths in ((AUTHOR,('capture-01','capture-launch-01')),
                      (CANDIDATE,('figures','review','README.md','development'))):
        paths=tuple(f'{PACKAGE}/{name}' for name in paths)
        keys=tree(pin,*paths)
        require(tree(delivery,*paths)==keys and hashes(pin,keys)==hashes(delivery,keys)==
                {name:digest((ROOT/name).read_bytes()) for name in keys}, 'Original author output differs')
    launch=read(origin/'capture-launch-01/manifest.json')
    review=read(origin/'review/manifest.json')
    require(digest((origin/'capture-launch-01/launch-originals.zip').read_bytes())==launch['archive_sha256']
            and digest((origin/'review/independent-reviews.zip').read_bytes())==review['archive_sha256']
            and review['capture_delivery']==AUTHOR and review['review_unresolved_findings']==0
            and (review['spec_saved_checks'],review['standards_saved_checks'])==(106911,6915),
            'Original capture or review authority differs')
    launch_members=verify_archive(origin/'capture-launch-01/launch-originals.zip',launch['members'])
    review_members=verify_archive(origin/'review/independent-reviews.zip',review['members'])
    development_members=verify_development(origin/'development')
    fig=origin/'figures'
    render=read(fig/'figure-source.json')
    qa=read(fig/'visual-qa.json')
    require(qa['status']=='PASS' and len(qa['figures'])==2
            and all(row['viewed_actual_png'] for row in qa['figures'].values())
            and digest((ROOT/'scripts/render_parameter_domain_figures.py').read_bytes())==render['renderer_sha256']
            and all(digest((ROOT/n).read_bytes())==h for n,h in render['inputs'].items())
            and all(digest((fig/n).read_bytes())==h for n,h in render['artifacts'].items()), 'Figure origin differs')
    print(json.dumps(dict(status='PASS',delivery_commit=delivery,actual_root_source=SOURCE,
        packet_artifacts=len(names),fixture_members=fixture_count,root_tests=tests,
        guarded_files=len(guard['actual_sources']),historical_originals=20,author=author,
        independent_saved_checks={'Spec':106911,'Standards':6915},
        archive_members={'launch':launch_members,'review':review_members,'development':development_members},
        actual_pngs_viewed=2,field_calibration='PENDING',new_physical_runs=0,new_full_regression=False)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('assemble','verify'))
    parser.add_argument('--delivery')
    args=parser.parse_args()
    if args.mode=='assemble':
        assemble()
    else:
        verify(args.delivery)
