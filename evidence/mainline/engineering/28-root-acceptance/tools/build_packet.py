"""Build the ticket 28 root packet from the completed integration and saved records."""
import argparse
import json
from pathlib import Path
import shutil
import zipfile

import verify_28_root_packet as v

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT/'.work'
PACKET = ROOT/v.PACKET
RUN = ROOT/'runs/mainline-M4-28-root-acceptance-20261107-01'
LAUNCH = WORK/'28-root-full-launch-01'
AUTHORITY = ROOT/v.AUTHORITY


def review_inputs():
    files, reports = {}, []
    for axis in ('Spec','Standards'):
        folder=WORK/f'28-saved-{axis.lower()}-review-01'
        report=v.read(folder/'review.json')
        manifest_path=next(folder/name for name in ('manifest.json','delivery-manifest.json') if (folder/name).exists())
        members=v.read(manifest_path)['artifacts']
        v.require(v.files(folder)==set(members)|{manifest_path.name}, f'Unsealed durable review files: {axis}')
        for name, expected in members.items():
            v.require(v.identity((folder/name).read_bytes())==expected,'Saved review file changed: '+name)
        reviewed=report.get('delivery',report.get('data'))
        execution=report.get('execution_source',report.get('source'))
        v.require(reviewed==v.AUTHOR and execution==v.EXECUTION and report['axis']==axis
                  and report['status'].startswith('PASS') and not report['unresolved'] and report['checks']>0,
                  f'Final {axis} review not passed at exact saved data')
        files.update({axis+'/'+name:folder/name for name in set(members)|{manifest_path.name}})
        reports.append(dict(axis=axis,checks=report['checks'],report=axis+'/review.json',manifest=axis+'/'+manifest_path.name))
    return files,reports


def fixture_inputs(launch, source):
    selected, cases={},{}
    for group in v.FIXTURE_GROUPS:
        existing=set(launch['fixture_baseline'][group])
        now={path.name:path for path in (WORK/group).iterdir() if path.is_dir()}
        v.require(existing<=set(now),'A preexisting fixture directory was removed')
        cases[group]=sorted(set(now)-existing)
        for name in cases[group]:
            folder=now[name]
            attempt='development-attempt.json' if group=='27-replay-development' else 'attempt.json'
            v.require(v.read(folder/attempt)['source_commit']==source, 'Concurrent source outside integrated fixture scope')
            selected.update({f'{group}/{name}/{item}':folder/item for item in v.files(folder)})
    v.require({group:len(rows) for group,rows in cases.items()}==
              {'26-online-development':18,'27-development':1,'27-replay-development':2},'Integrated fixture scope incomplete')
    return selected,cases


def zip_files(path, selected):
    members={}
    with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for name,file in sorted(selected.items()):
            raw=file.read_bytes()
            archive.writestr(name,raw)
            members[name]=v.identity(raw)
    return members


def main(source):
    v.require(not PACKET.exists() and not AUTHORITY.exists(),'Packet already exists')
    v.require(v.git(ROOT,'rev-parse','HEAD').decode().strip()==source and not v.git(ROOT,'status','--porcelain'),
              'Assemble on the clean actual integrated source')
    summary,guard=(v.read(RUN/name) for name in ('summary.json','source-guard.json'))
    terminal,attempt=(v.read(LAUNCH/name) for name in ('terminal.json','attempt.json'))
    tests=summary['tests']
    v.require(terminal['status']=='COMPLETED' and terminal['returncode']==0 and terminal['source']==source
              and summary['overall']=='PASS' and tests['run']==tests['executed']==567
              and tests['errors']==tests['failures']==tests['skipped']==0
              and guard['source_commit_before']==guard['source_commit_after']==source
              and guard['sources_unchanged'] and guard['head_unchanged'] and summary['verified_original_files']==20,
              'Integrated root gate is incomplete')
    reviews, reports=review_inputs()
    fixtures, fixture_cases=fixture_inputs(attempt,source)
    support={
        'author-fresh.json':'28-fresh-author-01.json',
        'frozen-v4-review-gate.json':'28-v4-ready-to-capture-01.json',
        'frozen-v4-history-check.json':'28-v4-preflight-01.json',
        'initial-failure-spec-diagnosis.json':'28-startup-bound-spec-01/diagnosis.json',
        'initial-failure-standards-diagnosis.json':'28-startup-bound-standards-01/diagnosis.json',
    }
    role_paths={
        **{f'raw/{name}':RUN/name for name in ('summary.json','tests.log','evidence.json','source-guard.json')},
        **{f'launch/{name}':LAUNCH/name for name in ('attempt.json','process.json','terminal.json','stdout.txt','stderr.txt')},
        **{f'checks/{name}':WORK/loc for name,loc in support.items()},
        'tools/root_runner.py':WORK/'run_28_root_acceptance.py',
        'tools/root_launcher.py':WORK/'launch_28_root_full_01.py',
        'tools/verify_28_capture_delivery.py':WORK/'verify_28_capture_delivery.py',
        'tools/seal_28_launch.py':WORK/'seal_28_launch.py',
        'tools/build_packet.py':Path(__file__),
        'verify_packet.py':WORK/'verify_28_root_packet.py',
    }
    generated={'.gitattributes','declaration.json','inventory.json','README.md','reviews.zip','root-fixtures.zip'}
    declared=sorted(set(role_paths)|generated)
    PACKET.mkdir(parents=True)
    v.write_new(PACKET/'declaration.json',dict(schema='aegisdc-ticket28-root-packet-v1',source=source,
        artifacts=declared,terminal='receipt.json',archive_roles={'reviews.zip':sorted(reviews),'root-fixtures.zip':sorted(fixtures)},
        separate_source_captures=[v.AUTHOR,v.VISUALS],runtime_cache_exclusions=['__pycache__','*.pyc','*.pyo']))
    for name, origin in role_paths.items():
        path=PACKET/name
        path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(origin,path)
    archives={'reviews.zip':zip_files(PACKET/'reviews.zip',reviews),
              'root-fixtures.zip':zip_files(PACKET/'root-fixtures.zip',fixtures)}
    v.write_new(PACKET/'inventory.json',dict(archives=archives,reviews=reports,fixture_cases=fixture_cases,
        classification='Root engineering fixture originals and two independent saved-data review verdicts. No formal capture repeated.'))
    with (PACKET/'.gitattributes').open('x',encoding='utf-8',newline='\n') as stream:
        stream.write('# Preserve exact native integrated regression streams.\n')
        for name in ('raw/summary.json','raw/evidence.json','raw/tests.log','launch/stdout.txt','launch/stderr.txt','checks/initial-failure-spec-diagnosis.json'):
            stream.write(f'{name} -text whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol\n')
    with (PACKET/'README.md').open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(f"""# 第 28 项整合交付

[四例报告、两张数据图和八域架构入口](../28-negative-controls/README.md)是阅读入口。本包保存整合运行、独立保存复核和干净检出验证工具。四例的运行源固定为 `{v.EXECUTION}`，数据提交 `{v.AUTHOR}`；报告与图单独固定在 `{v.VISUALS}`。

整合源 `{source}` 执行 567 项回归，零失败、零错误、零跳过，20 份历史原件通过完整性检查。首轮真实尝试失败已保留，随后四例完成共 21.5 秒；总尝试上限 28.75 秒的含义见报告。根回归的短工程测试夹具与固定四例分开记账。

[整合日志](raw/tests.log) · [清单](declaration.json) · [两份独立保存审查](reviews.zip) · [验收记录](../../../../docs/mainline/evidence/28-root.json)。保存验证无需重新运行设施。
""")
    v.require(v.files(PACKET)==set(declared),'Actual artifact set differs from declaration')
    v.write_new(PACKET/'receipt.json',dict(status='CANDIDATE_PENDING_FRESH_DELIVERY',tested_source=source,
        artifacts={name:v.identity((PACKET/name).read_bytes()) for name in declared},registered_research_trials=0))
    gate=dict(status='CANDIDATE_PENDING_FRESH_DELIVERY',ticket='28',milestone='M4',actual_root_source=source,
        author_source=v.EXECUTION,author_data_delivery=v.AUTHOR,report_delivery=v.VISUALS,packet=v.PACKET,
        packet_receipt_sha256=v.digest((PACKET/'receipt.json').read_bytes()),root_tests=tests,
        guarded_files=len(guard['committed_sources']),historical_originals=20,
        independent_saved_checks={row['axis']:row['checks'] for row in reports},
        physical_attempts=5,completed_integrations=4,completed_simulated_seconds=21.5,
        charged_simulated_seconds_upper=28.75,original_failures_retained=1,original_repeated=False,
        registered_research_trials=0,field_calibration='PENDING',overall_goal='ACTIVE',
        remaining_gate='FRESH_COMMITTED_DELIVERY_VERIFICATION')
    v.write_new(AUTHORITY,gate)
    print(json.dumps(dict(status=gate['status'],root_tests=tests,guarded_files=gate['guarded_files'],artifacts=len(declared),
        members={k:len(items) for k,items in archives.items()},independent_checks=gate['independent_saved_checks']),ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True)
    args=parser.parse_args()
    main(args.source)