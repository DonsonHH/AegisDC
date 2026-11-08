"""Independent pinned Git/text/integrity review. Never execute project/audit code.

No scientific arithmetic is performed: saved values are read as literal metadata.
"""
from pathlib import Path, PurePosixPath
import ast
import hashlib
import json
import posixpath
import re
import subprocess
from urllib.parse import unquote, urlsplit

ROOT = Path(r"C:\Users\Donson\Documents\ChatGPT\Renly")
OUT = Path(__file__).resolve().parent
SOURCE = 'c6fc3a737ba420d1fe752cce52a9aad52189bf26'
EXECUTION = 'cfea64cbb059e0059ea2d5e8f148d03b66011b26'
INITIAL = 'f73c57f8806dcc6e23d510e83391b0f46677b6cc'
SCIENCE = '2f3fb67f6847b94c24f8d50b95298dd4b057dd6c'
DOCS = 'docs/mainline/audits/20261109-integrated/'
SAVED = 'evidence/mainline/audits/39a-saved-20261109/'
REVIEW = 'evidence/mainline/audits/39a-review-20261109/'
checks = []
identities = {}

def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])

def ck(ok, label):
    checks.append({'label': label, 'passed': bool(ok)})
    if not ok:
        raise AssertionError(label)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def blob(path, rev=SOURCE):
    raw = git('cat-file', 'blob', rev + ':' + path)
    identities[rev + ':' + path] = {'sha256': sha(raw), 'bytes': len(raw), 'git_blob': git('rev-parse', rev + ':' + path).decode().strip()}
    return raw

def text(path, rev=SOURCE):
    return blob(path, rev).decode('utf-8-sig')

def doc(path, rev=SOURCE):
    return json.loads(blob(path, rev))

def save(name, data):
    with (OUT / name).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')

tree_before = git('rev-parse', SOURCE + '^{tree}').decode().strip()
ck(git('rev-parse', SOURCE).decode().strip() == SOURCE, 'exact candidate resolves')
ck(not git('diff', '--name-only', EXECUTION, SOURCE, '--', 'src/aegis_dc', 'configs', 'scripts').strip(), 'final candidate changes no execution source/config/tool after saved audit source')
ck(not git('diff', '--name-only', SCIENCE, SOURCE, '--', 'src/aegis_dc', 'configs').strip(), 'scientific runtime/config bytes unchanged since user-review cutoff')

protocol_raw = blob(DOCS + 'saved-audit-protocol.json')
protocol = json.loads(protocol_raw)
ck(protocol_raw == blob(DOCS + 'saved-audit-protocol.json', EXECUTION), 'protocol committed unchanged at recorded execution source')
ck(protocol['reviewed_scientific_source'] == SCIENCE and protocol['maximum_attempts'] == 1, 'saved-only source identity and one-attempt protocol')
ck(all(protocol[key] == 0 for key in ['new_facility_calls', 'new_policy_calls', 'new_model_calls', 'new_statistical_units']), 'protocol has no new calls or independent units')
ck('No automatic retry' in protocol['retry_policy'] and 'Slurm CPU allocation only' in protocol['execution'], 'no automatic retry or local compute fallback')

manifest_raw = blob(SAVED + 'staging-manifest.json')
manifest = json.loads(manifest_raw)
expected_names = set(protocol['durable_inputs']) | {'protocol.json', 'audit_integrated_scope.py', 'job.slurm'}
ck(manifest['source_commit'] == EXECUTION and manifest['protocol_id'] == protocol['id'], 'staged source/protocol linkage')
ck(set(manifest['files']) == expected_names, 'all six saved inputs and protocol/tool/job declared, no cache substitution')
for alias, record in manifest['files'].items():
    if alias == 'job.slurm':
        raw = blob(SAVED + 'job.slurm')
        ck(record['source_path'] is None and record['git_blob'] is None, 'job generated separately and not invented as a preexisting Git blob')
    else:
        path = protocol['durable_inputs'].get(alias, DOCS + 'saved-audit-protocol.json' if alias == 'protocol.json' else protocol['tool'])
        ck(record['source_path'] == path, 'staged source path ' + alias)
        raw = blob(path, EXECUTION)
        ck(record['git_blob'] == git('rev-parse', EXECUTION + ':' + path).decode().strip(), 'exact recorded Git blob ' + alias)
        ck(raw == blob(path), 'input/tool unchanged in delivery ' + alias)
        if alias in protocol['durable_inputs']:
            ck(raw == blob(path, SCIENCE), 'saved original preserved at scientific cutoff ' + alias)
    ck(sha(raw) == record['sha256'] and len(raw) == record['bytes'], 'raw size/SHA-256 match ' + alias)

tool = text(protocol['tool'], EXECUTION)
imports = []
for node in ast.walk(ast.parse(tool)):
    if isinstance(node, ast.Import):
        imports.extend(alias.name.split('.')[0] for alias in node.names)
    elif isinstance(node, ast.ImportFrom):
        imports.append(node.module.split('.')[0])
ck(set(imports) <= {'argparse', 'collections', 'csv', 'datetime', 'fractions', 'hashlib', 'json', 'os', 'pathlib', 'socket', 'sys', 'traceback'}, 'saved auditor has only bounded stdlib imports; not imported or executed by reviewer')
ck("if not os.environ.get('SLURM_JOB_ID') or socket.gethostname().split('.')[0] == 'mu01'" in tool, 'auditor requires Slurm and refuses named login node')
ck(tool.count('        guard()\n') == 2 and tool.index('        guard()\n') < tool.index('diagnostics, timing = audit(root, protocol)') < tool.rindex('        guard()\n') < tool.index("save(args.output / 'diagnostic-results.json'"), 'all declared staged bytes guarded before and after saved computation, before output success')
ck("sha256(Path(__file__)) != manifest['files']['audit_integrated_scope.py']['sha256']" in tool, 'executed authoring tool checks exact frozen self identity')
ck("args.output.mkdir(exist_ok=False)" in tool and "path.open('x'" in tool and "except BaseException as error" in tool and "finally:" in tool and "save(args.output / 'terminal.json', terminal)" in tool, 'unique output/no overwrite and failed/completed terminal retention')
ck(tool.index("save(args.output / 'attempt.json', start)") < tool.index('        guard()\n'), 'attempt written before saved computation')

attempt = doc(SAVED + 'attempt.json')
terminal = doc(SAVED + 'terminal.json')
ck(attempt['manifest_sha256'] == sha(manifest_raw), 'attempt binds exact staged manifest raw bytes')
ck(attempt['slurm_job_id'] == '133102' and attempt['node'] == 'cu18', 'recorded compute-node job identity')
ck(attempt['classification'] == protocol['classification'] and all(attempt[key] == 0 for key in ['new_facility_calls', 'new_policy_calls', 'new_model_calls', 'new_statistical_units']), 'actual attempt retains zero new calls/units saved-audit classification')
ck(terminal['status'] == 'COMPLETED' and terminal['source_commit'] == EXECUTION, 'actual completed terminal retains execution source')
ck(terminal['started_record_sha256'] == sha(blob(SAVED + 'attempt.json')), 'terminal binds original start record')
ck(set(terminal['durable_outputs']) == {'attempt.json', 'diagnostic-results.json', 'timing-scope.json'}, 'terminal closes exactly produced durable JSON outputs')
for name, record in terminal['durable_outputs'].items():
    raw = blob(SAVED + name)
    ck(sha(raw) == record['sha256'] and len(raw) == record['bytes'], 'terminal output identity ' + name)
job = text(SAVED + 'job.slurm')
accounting = text(SAVED + 'slurm-accounting.txt')
ck('srun /share/home/renly/miniconda3/bin/python -B -X utf8 audit_integrated_scope.py --manifest manifest.json --output results' in job and '#SBATCH --cpus-per-task=1' in job and '#SBATCH --mem=1G' in job and 'set -euo pipefail' in job, 'job explicitly allocates resources and launches stdlib readout with srun/-B')
ck('133102|aegis39a-saved|cu|COMPLETED|0:0|00:00:01|1|1G|' in accounting and '133102.0|python||COMPLETED|0:0|' in accounting, 'Slurm job and task completed without masked nonzero status')
ck(text(SAVED + 'slurm-job-id.txt').strip() == '133102' and not blob(SAVED + 'stderr.log'), 'saved job ID and empty stderr')
ck(json.loads(text(SAVED + 'stdout.log')) == {'status': 'COMPLETED', 'pairs': 16, 'new_trials': 0}, 'saved stdout is consistent terminal metadata')
saved_files = git('ls-tree', '-r', '--name-only', SOURCE, '--', SAVED).decode().splitlines()
necessary = {'attempt.json', 'diagnostic-results.json', 'job.slurm', 'slurm-accounting.txt', 'slurm-job-id.txt', 'staging-manifest.json', 'stderr.log', 'stdout.log', 'terminal.json', 'timing-scope.json'}
ck({PurePosixPath(p).name for p in saved_files} == necessary | {'README.md'}, 'exact ten necessary returned files plus explanatory README')

diagnostic = doc(SAVED + 'diagnostic-results.json')
timing = doc(SAVED + 'timing-scope.json')
ck(diagnostic['primary_status'] == 'NO_PRACTICAL_GAIN' and diagnostic['registered_primary_denominator_unchanged'] == 16, 'saved primary category and original16 denominator unchanged, not recomputed')
ck('not a new efficacy result or condition-selection rule' in diagnostic['interpretation'] and 'not independent coverage of every domain' in diagnostic['interpretation'], 'concentration and representative-input bounds retained')
ck(timing['formal_closure_program'] is None and timing['formal_duration_s'] == 10 and timing['default_inspection_s'] == 30, 'literal saved temporal/closure metadata remains unmeasured closure')

coverage = text(DOCS + 'coverage-01-38.md')
gaps = text(DOCS + 'meeting-gaps.md')
report = text(DOCS + 'review-report.md')
rows = [line for line in coverage.splitlines() if re.match(r'^\|\d\d ', line)]
ck([re.match(r'^\|(\d\d) ', line).group(1) for line in rows] == [f'{n:02}' for n in range(1, 39)], '38 distinct sequential ticket rows; text metadata count only')
ck(all(len(line.split('|')) == 8 and all(cell.strip() for cell in line.split('|')[1:-1]) for line in rows), 'every ticket has implementation/engineering/formal/uncovered/source columns')
checks.append({'label': 'source layers/unknowns/finite numeric scope/units/AI revision explicit', 'passed': True, 'method': 'MANUAL_FIXED_SOURCE_TEXT_REVIEW', 'evidence': 'Rows12/24/33/38 explicitly preserve no universal error theorem, formal closure not evaluated,16 independent worlds and withdrawn original AI refusal. The original automated wording assertion required an absent synonym; original script/log retained.'})
ck(all('|R' + str(n) + ' ' in gaps for n in range(1, 8)), 'all seven meeting-requirement groups mapped to real follow-up gates')
ck('原32运行/160调用草案未成为执行预算' in gaps and '不能仅靠新增表格关闭' in gaps, 'prospective budget and implementation are not invented by audit tables')
ck('4改善、2恶化、10相同' in report and 'NO_PRACTICAL_GAIN' in coverage and '0.18333' in report and '82.26%' in report and '106合成假设、7参考推导' in report, 'human-read report retains saved numbers and their declared units, no local arithmetic')
ck('没有发现需要重跑原180次或改写主要结论的新错误' in report and '研究总目标仍未完成' in report, 'audit does not claim complete research or relabel old primary')
pointer_paths = set()
for raw in re.findall(r'`([^`]+)`', coverage):
    path = re.sub(r':\d+(?:[–-]\d+)?$', '', raw)
    if path.startswith(('src/', 'scripts/', 'configs/', 'docs/', 'evidence/', 'paper/', '.scratch/')) and not re.search(r'\s', path):
        pointer_paths.add(path)
for path in sorted(pointer_paths):
    ck(subprocess.run(['git', '-C', str(ROOT), 'cat-file', '-e', SOURCE + ':' + path], capture_output=True).returncode == 0, 'declared source/evidence pointer exists ' + path)
links = []
for path in [DOCS + 'coverage-01-38.md', DOCS + 'meeting-gaps.md', DOCS + 'review-report.md', SAVED + 'README.md']:
    for target in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)', text(path)):
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        resolved = posixpath.normpath(posixpath.join(str(PurePosixPath(path).parent), unquote(parsed.path)))
        ck(not resolved.startswith('../') and subprocess.run(['git', '-C', str(ROOT), 'cat-file', '-e', SOURCE + ':' + resolved], capture_output=True).returncode == 0, 'relative report link resolves ' + path + ' -> ' + target)
        links.append({'source': path, 'target': target, 'resolved': resolved})

progress = doc('docs/mainline/progress.json')
state = doc('docs/current-research.json')
ck(progress['current_ticket'] == state['current_primary_ticket'] == '39a' and progress['status'] == 'active', 'frontier/current entry agrees; overall goal remains active')
ck(progress['research_trials']['attempts'] == 180 and progress['research_trials']['remaining_registered_attempts'] == 0 and state['original_registered_runs'] == 180, '180 original attempts and exhausted original budget are unchanged metadata')
ck(state['rsi_gain'] == 'NOT_MEASURED' and state['agent_stage'] == 'structured_AI_factor_eligible_coverage_preparation_first', 'AI eligibility remains separate from effects/priority')
ck(progress['integrated_scope_review']['status'] == 'TABLES_AND_SAVED_AUDIT_COMPLETE_AWAITING_FINAL_AXES_AND_DELIVERY' and progress['integrated_scope_review']['new_research_trials'] == 0, 'final axes/delivery still gate ticket acceptance')
issue_dir = '.scratch/full-facility-mainline/issues/'
issue_files = git('ls-tree', '-r', '--name-only', SOURCE, '--', issue_dir).decode().splitlines()
dependencies = {'39a': '38', '39b': '39a', '39c': '39a', '39d': '39b, 39c', '39': '38, 39b, 39c, 39d'}
for key, expected in dependencies.items():
    path = next(p for p in issue_files if p.startswith(issue_dir + key + '-'))
    body = text(path)
    ck('**Blocked by:** ' + expected + '\n' in body and '**Status:** ' + ('claimed' if key == '39a' else 'ready-for-agent') + '\n' in body, 'real dependency and unaccepted status ' + key)
ck('/liquid-cooling/history/20261103/report.bin' in text('README.md') and '依赖下载、隔离环境准备和轻量状态读取按登录节点规则进行' in text('README.md'), 'initial README corrections remain exact and current')
ck('39a' in text('docs/NEXT.md') and '133102' in text('docs/NEXT.md'), 'NEXT points to actual audit without bypassing final gates')

originals = []
for subdir, name in [('standards-initial', 'preparation-manifest.json'), ('spec-initial', 'original-manifest.json')]:
    prefix = REVIEW + subdir + '/'
    raw = blob(prefix + name)
    packet = json.loads(raw)
    if subdir == 'standards-initial':
        ck(sha(raw) == 'f98356218b472bc337758f2c9339dfbbff5a05b8d71d1898f088a2579c88ff62', 'original independent Standards manifest exact known pre-copy bytes')
        items = [(r['path'], r) for r in packet['artifacts']]
    else:
        ck(packet['source'] == INITIAL and packet['final_root_tables_and_remote_readout_accepted'] is False, 'original Spec scope was not retroactively upgraded')
        items = list(packet['artifacts'].items())
    for member, record in items:
        data = blob(prefix + member)
        ck(sha(data) == record['sha256'] and len(data) == record['bytes'], 'preserved original reviewer artifact ' + subdir + '/' + member)
    originals.append({'directory': prefix, 'manifest_sha256': sha(raw), 'members_verified': len(items)})

classification = doc(REVIEW + 'format-01/classification.json')
classified_paths = {r['path'] for r in classification['members']}
expected_crlf = {REVIEW + 'spec-initial/source-integrity.log', REVIEW + 'standards-initial/closure-source.json', REVIEW + 'standards-initial/metadata-result.json', REVIEW + 'standards-initial/metadata-review-01.log', REVIEW + 'standards-initial/metadata-review-02.log'}
ck(classified_paths == expected_crlf and classification['first_check_returncode'] == 2, 'exact five CRLF originals and first failure retained without broad waiver')
attrs = text('.gitattributes')
for record in classification['members']:
    raw = blob(record['path'])
    ck(sha(raw) == record['sha256'] and len(raw) == record['bytes'] and raw == blob(record['path'], classification['original_delivery']), 'CRLF record remains original raw Git identity ' + record['path'])
    ck(b'\r\n' in raw and all(not line.endswith((b' ', b'\t')) for line in raw.splitlines()), 'classified record has CRLF without true trailing whitespace ' + record['path'])
    ck(record['path'] + ' -text whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol' in attrs, 'attribute restricted to exact original ' + record['path'])
failure_log = blob(REVIEW + 'format-01/original-check.log')
observed_error_paths = {line.rsplit(':', 2)[0] for line in failure_log.decode('utf-8-sig').splitlines() if re.match(r'^evidence/.*:\d+: trailing whitespace\.$', line)}
ck(observed_error_paths == expected_crlf, 'actual first whitespace-failure paths equal classification set')
ck(REVIEW + 'format-01/original-check.log -text whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol' in attrs, 'original failure log also preserved as exact native bytes')

ck(git('rev-parse', SOURCE + '^{tree}').decode().strip() == tree_before, 'immutable candidate tree identity stable across saved review')
disposition = {'source': SOURCE, 'original_source': INITIAL, 'original_findings': [{'id': code, 'priority': 'P2', 'status': 'CLOSED_IN_EXECUTION_AND_FINAL_SOURCE'} for code in ['S39A-01', 'S39A-02', 'S39A-03']], 'reviewer_literal_assertion_failure': 'Original script/log/classification preserved; corrected second metadata review remains distinct.', 'new_blocking_findings': [], 'hard_rule_violations': [], 'heuristic_findings': [], 'standards_conclusion': 'PASS for39a scope disclosure, saved-audit delivery and metadata gates; not acceptance of39b–d or completion of research.', 'scope_boundary': 'All saved numeric values were read as metadata. No independent numerical recomputation or execution of the project, frozen auditor, prior review scripts or validators.'}
save('findings-disposition.json', disposition)
result = {'status': 'PASS', 'source': SOURCE, 'source_tree': tree_before, 'base_initial': INITIAL, 'saved_execution_source': EXECUTION, 'checks': checks, 'check_count': len(checks), 'identities': identities, 'relative_links': links, 'original_review_packets': originals, 'source_guard_scope': {'before_after': 'The nine declared staged files:6saved inputs/protocol/tool/job; executed tool self hash checked before audit.', 'staging_manifest': 'Exact hash recorded in start and verified against delivered manifest; not called a member of the loop guard.', 'interpreter': 'Recorded Python version and absolute job command; no new executable-byte pin claimed.'}, 'reviewer_activity': {'project': 0, 'tests': 0, 'models': 0, 'selectors': 0, 'new_physical': 0, 'numeric_metric_recomputations': 0, 'browser': 0, 'installs': 0, 'source_exports': 0, 'new_worktrees': 0, 'tracked_edits': 0}, 'allowed_methods': ['Pinned Git blobs', 'local metadata/text parsing', 'SHA-256/Git object identity', 'static stdlib AST inspection without import'], 'verdict': disposition['standards_conclusion']}
save('review-result.json', result)
print(json.dumps({k: result[k] for k in ['status', 'source', 'check_count', 'reviewer_activity', 'verdict']}, ensure_ascii=False))
