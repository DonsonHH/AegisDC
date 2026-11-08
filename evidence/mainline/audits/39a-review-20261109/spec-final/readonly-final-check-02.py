"""Final39a text/Git/hash review. No project execution or metric arithmetic."""
import hashlib,json
from pathlib import Path
import re,subprocess

ROOT=Path('C:/Users/Donson/Documents/ChatGPT/Renly')
OUT=Path(__file__).resolve().parent
SOURCE='c6fc3a737ba420d1fe752cce52a9aad52189bf26'
INITIAL='f73c57f8806dcc6e23d510e83391b0f46677b6cc'
REMOTE='cfea64cbb059e0059ea2d5e8f148d03b66011b26'
TABLES='docs/mainline/audits/20261109-integrated/'
SAVED='evidence/mainline/audits/39a-saved-20261109/'
REVIEW='evidence/mainline/audits/39a-review-20261109/'
sha=lambda raw:hashlib.sha256(raw).hexdigest()
git=lambda *args:subprocess.check_output(['git',*args],cwd=ROOT)
hashes={}

def blob(path,source=SOURCE):
    raw=git('show',source+':'+path)
    hashes[source+':'+path]=dict(sha256=sha(raw),bytes=len(raw))
    return raw

def read(path,source=SOURCE):return json.loads(blob(path,source))

def save(name,value):
    with (OUT/name).open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

matrix=blob(TABLES+'coverage-01-38.md').decode()
initial_matrix=blob(REVIEW+'spec-initial/coverage-01-38.md').decode()
assert re.findall(r'^\|\d\d .*$',matrix,re.M)==re.findall(r'^\|\d\d .*$',initial_matrix,re.M)
meeting=blob(TABLES+'meeting-gaps.md').decode();report=blob(TABLES+'review-report.md').decode()
assert '六项' in matrix or '6项' in matrix
assert 'UNMODELED' in matrix and '单cooling' in matrix and 'closure_program=None' in matrix
assert 'ALREADY_ISSUED' in matrix and '手编两任务' in matrix
assert '39b–39d' in meeting and '不能填0' in meeting and '原32运行/160调用草案未成为执行预算' in meeting
assert '不替换原主要分母' in report and '只是集中度诊断' in report
assert '38的窄结构化AI可检验性保持' in report
assert '表格、单例工程通过和CI都不能替代这些工作' in report
protocol=read(TABLES+'saved-audit-protocol.json')
assert protocol['classification']=='saved_artifact_audit_not_research_trial' and protocol['maximum_attempts']==1
assert protocol['execution']=='Slurm CPU allocation only; no local project execution'
for key in ('new_facility_calls','new_policy_calls','new_model_calls','new_statistical_units'):assert protocol[key]==0
staging=read(SAVED+'staging-manifest.json');attempt=read(SAVED+'attempt.json');terminal=read(SAVED+'terminal.json')
assert staging['source_commit']==terminal['source_commit']==REMOTE
assert attempt['slurm_job_id']=='133102' and attempt['node']=='cu18'
assert attempt['manifest_sha256']==sha(blob(SAVED+'staging-manifest.json'))
assert terminal['status']=='COMPLETED' and terminal['started_record_sha256']==sha(blob(SAVED+'attempt.json'))
staged_sources={}
for name,entry in staging['files'].items():
    if entry['source_path'] is not None:
        raw=blob(entry['source_path'],REMOTE)
        assert git('rev-parse',REMOTE+':'+entry['source_path']).decode().strip()==entry['git_blob']
    else:
        assert name=='job.slurm';raw=blob(SAVED+'job.slurm')
    assert sha(raw)==entry['sha256'] and len(raw)==entry['bytes'],name
    staged_sources[name]=entry
for name,entry in terminal['durable_outputs'].items():
    raw=blob(SAVED+name);assert sha(raw)==entry['sha256'] and len(raw)==entry['bytes'],name
diagnostics=read(SAVED+'diagnostic-results.json');timing=read(SAVED+'timing-scope.json')
assert diagnostics['primary_status']=='NO_PRACTICAL_GAIN' and diagnostics['registered_primary_denominator_unchanged']==16
assert timing['formal_closure_program'] is None
assert diagnostics['checks']['quantified_risk_questions']==['cooling','power']
assert diagnostics['checks']['value_question_ids']==['cooling']
assert 'not a new efficacy result' in diagnostics['interpretation']
assert 'Nonuniform time scaling' in timing['interpretation'] and 'Prestarted states remain distinct' in timing['interpretation']
accounting=blob(SAVED+'slurm-accounting.txt').decode()
assert '133102|aegis39a-saved|cu|COMPLETED|0:0|00:00:01|1|1G|' in accounting
assert blob(SAVED+'stderr.log')==b''
assert '"status": "COMPLETED"' in blob(SAVED+'stdout.log').decode()
tool=blob('scripts/audit_integrated_scope.py',REMOTE).decode()
assert 'requires a Slurm compute allocation' in tool
assert 'simulate_scenario(' not in tool and 'from aegis_dc' not in tool and 'import aegis_dc' not in tool
assert tool.count('        guard()')==2
original_bytes=blob(REVIEW+'spec-initial/original-manifest.json')
assert sha(original_bytes)=='af5c8f72d056712b81907c398e0b49dfdd10a6ecb516a2c2a3f6e9c278009e3b'
original=json.loads(original_bytes)
for name,entry in original['artifacts'].items():
    raw=blob(REVIEW+'spec-initial/'+name)
    assert sha(raw)==entry['sha256'] and len(raw)==entry['bytes'],name
format_classification=read(REVIEW+'format-01/classification.json')
assert format_classification['first_check_returncode']==2 and len(format_classification['members'])==5
for entry in format_classification['members']:
    raw=blob(entry['path']);assert sha(raw)==entry['sha256'] and len(raw)==entry['bytes']
    assert entry['classification']=='EXACT_ORIGINAL_CRLF_ONLY_NO_TRAILING_SPACES'
assert blob(REVIEW+'format-01/original-check.log')
readme=blob('README.md').decode();next_text=blob('docs/NEXT.md').decode()
assert '[v11历史HTML下载](https://lab.donson.top/liquid-cooling/history/20261103/report.bin)' in readme
assert '该早期工程基线及其M2数值资格属于历史验收范围' in readme
assert '桌面仅做编辑、SSH、完整性核对、小文件同步和结果查看' in readme
assert '不能自动改在本机计算' in readme and '仿真、风险计算、工程评价和重型验证通过Slurm作业' in readme
assert '两轴复核与交付门槛通过后才解决39a' in next_text
current=read('docs/current-research.json');progress=read('docs/mainline/progress.json')
assert current['current_primary_ticket']==progress['current_ticket']=='39a'
assert current['agent_stage']=='structured_AI_factor_eligible_coverage_preparation_first' and current['rsi_gain']=='NOT_MEASURED'
assert current['original_registered_runs']==progress['research_trials']['attempts']==180
assert current['new_research_trials_after_user_review']==0
assert progress['status']=='active'
assert progress['integrated_scope_review']['status']=='TABLES_AND_SAVED_AUDIT_COMPLETE_AWAITING_FINAL_AXES_AND_DELIVERY'
assert '**Status:** claimed' in blob('.scratch/full-facility-mainline/issues/39a-integrated-scope-review.md').decode()
for filename in ('39b-multisystem-questions-and-tasks.md','39c-business-endpoints-and-closure.md','39d-timescales-parameter-and-numeric-scope.md'):
    text=blob('.scratch/full-facility-mainline/issues/'+filename).decode()
    assert '**Status:** ready-for-agent' in text and '**Status:** resolved' not in text
assert '**Blocked by:** 38, 39b, 39c, 39d' in blob('.scratch/full-facility-mainline/issues/39-agent-increment.md').decode()
assert read('docs/mainline/evidence/38-root.json')['decision']=='ELIGIBLE_FOR_NARROW_STRUCTURED_POLICY_FACTOR'
assert not git('diff','--name-only','2f3fb67f',SOURCE,'--','src/aegis_dc','configs','evidence/mainline/research').strip()
save('source-pin.json',dict(source=SOURCE,initial_source=INITIAL,remote_saved_audit_source=REMOTE,
    original_spec_manifest_sha256=sha(original_bytes),files=hashes,
    local_scope='Pinned text/Git/hash and literal saved-field inspection only; no scientific arithmetic or source execution.'))
save('finding-closure.json',dict(source=SOURCE,status='PASS',unresolved=0,
    closed=[dict(id='39A-SPEC-DOC-01',scope='README v11 history points to archivedHTML; latest180 report separate.'),
            dict(id='39A-SPEC-DOC-02',scope='HistoricalM2/current entry and remote/Slurm-only execution boundaries explicit.')],
    initial_record='Original Spec packet retained byte-identically in committed spec-initial.',
    format_record='Exact5 CRLF originals and first failed format log retained; no broad hash waiver.',
    interpretation='Existing finite acceptances and primary negative result preserved.39a discloses scope;39b–39d still require implementation, remote engineering verification and acceptance.38 eligibility unchanged.'))
save('saved-readout-citation.json',dict(source=SOURCE,classification=protocol['classification'],
    slurm=dict(job='133102',state='COMPLETED',exit_code='0:0',allocation='1CPU/1GiB',elapsed='00:00:01'),
    quoted_saved_checks=diagnostics['checks'],quoted_saved_timing=timing,
    citation_review='Report uses the stored diagnostic fields and timing interpretation, with finite/descriptive scope. Percent/ratio metrics were not recomputed locally; original CSV/180 trajectories were not reevaluated.',
    local_metric_recomputation=False,project_calls=0,tests=0,models=0,physical_calls=0,browser_calls=0,installs=0,full_source_exports=0,clones=0,new_worktrees=0))
save('receipt.json',dict(status='PASS_SPEC_FINAL39A_NARROW_REVIEW',source=SOURCE,unresolved=0,
    tables_consistent=True,saved_job_citation_consistent=True,initial_findings_closed=True,initial_bytes_preserved=True,
    eligible38_preserved=True,coverage_39b_c_d_not_completed=True,old180_and_primary_unchanged=True,
    fresh_delivery_still_required=True,project_calls=0,tests=0,models=0,physical_calls=0,metric_recomputations=0,
    browser_calls=0,installs=0,full_source_exports=0,clones=0,new_worktrees=0))
report='''Spec：c6fc3a73窄复核通过，无未决阻塞，初审两项文档问题已闭合。

两表保留实现/工程/正式覆盖/未测分层：19两量化六未知、20单cooling、26两任务、24/27与正式closure=None、参数及数值边界均明确。38窄AI可检验性保持，39b–39d没有被表格冒充完成。

Slurm133102保存补读的源、9件输入/工具、终态及引用一致；集中度和删单工况仅作诊断，不替代16主要分母。原180与负结果未改。初审包及5件CRLF原件/失败日志按原字节保留。README远端边界和状态入口已同步。本地仅文本/Git/hash核对，未执行项目、测试、模型或指标重算；39a仍需交付复核。
'''
assert len(report)<400
with (OUT/'report.md').open('x',encoding='utf-8',newline='\n') as stream:stream.write(report)
print(json.dumps(dict(status='PASS_SPEC_FINAL39A_NARROW_REVIEW',source=SOURCE,unresolved=0,
    local_metric_recomputation=False,project_calls=0)))
