"""Assemble only the already-accepted ticket14 root evidence; no suites/models."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path.cwd()
SOURCE = '65eddd6908510371a6fcc913742b6c4197114270'
PACK = ROOT / 'evidence/mainline/engineering/14-root-acceptance'
TEMP = Path('C:/Users/Donson/AppData/Local/Temp')
FULL = ROOT / 'runs/mainline-14-root-acceptance-20261105-01'


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def git(*arguments):
    return subprocess.check_output(['git', *arguments], cwd=ROOT, text=True).strip()


assert git('rev-parse', 'HEAD') == SOURCE and git('branch', '--show-current') == 'donson/full-facility-mainline'
assert not git('status', '--porcelain') and not PACK.exists()
summary = read(FULL / 'summary.json'); guard = read(FULL / 'source-guard.json')
assert summary['tests']['run'] == summary['tests']['executed'] == 377
assert summary['tests']['failures'] == summary['tests']['errors'] == summary['tests']['skipped'] == 0
assert guard['source_commit_before'] == guard['source_commit_after'] == SOURCE
assert guard['sources_unchanged'] and guard['head_unchanged'] and len(guard['actual_python_sources']) == 166
assert all(sha(ROOT / n) == h for n, h in guard['actual_python_sources'].items())
archives = {'reviews/standards.zip': {}, 'reviews/spec.zip': {}, 'reviews/math-probes.zip': {}, 'reviews/visual-qa.zip': {}}


def review(label, prefix, stem, directory, count, expected):
    report = TEMP / (stem + '.md'); folder = TEMP / directory
    assert report.is_file() and sha(report) == expected and folder.is_dir(), stem
    files = sorted(p for p in folder.rglob('*') if p.is_file()); assert len(files) == count, directory
    archives[label][prefix + '/report.md'] = report
    archives[label].update({prefix + '/attachments/' + p.relative_to(folder).as_posix(): p for p in files})


for prefix, stem, count, expected in [
    ('source', 'aegisdc-review-14-source-standards', 12, 'b93691e056b567d44a41eb3485eed0230a7c7f792d8b05467875ecefe2c0b095'),
    ('correction', 'aegisdc-review-14-correction-standards', 8, 'a84c269b702b07e629b78aff8e0e8685088a6847833f02f899db3e7df6db9c01'),
    ('final-core', 'aegisdc-review-14-final-standards', 4, 'b74fd72f4dd94700fe9fe20521d146bc5d43ed086510a5c01c6e0ca98c3d989c'),
    ('delivery', 'aegisdc-review-14-delivery-standards', 7, 'd97bb2f5f1937707d5676e3182bae331bb27aff87e0f467271b89ad9f77528ab')]:
    review('reviews/standards.zip', prefix, stem, stem + '-attachments', count, expected)
review('reviews/spec.zip', 'final', 'aegisdc-review-14-source-final-spec', 'aegisdc-review-14-source-final-spec-attachments', 37, '01cd23ed1977b6b7219f1e2d7e8fe39753583ffd685a2815d1c9b5df459ea289')
# Targeted original finding chains, not old physical/research packages.
review('reviews/spec.zip', 'history/source', 'aegisdc-review-14-source-spec', 'aegisdc-review-14-source-spec-attachments', 39, 'c9cc52a81964f641a01dbf42881313e3fa3905cbd2e025c85e9602bc19615557')
review('reviews/spec.zip', 'history/precision', 'aegisdc-review-14-precision-spec', 'aegisdc-review-14-precision-spec-attachments', 31, '0a7a9ecbb760e542d66bfd78a8b9e920620d248e17e6713e13aa31b11c13f7be')
review('reviews/spec.zip', 'history/domain', 'aegisdc-review-14-domain-source-spec', 'aegisdc-review-14-final-source-spec-closure-attachments', 29, '2cebea4678c955ba6ebdfb1b37be3dc714fc29d8e971bd4074b3b7b771a8632b')
for name in ('14-age-number-semantics-probe-01.json', '14-bound-domain-semantics-probe-01.json'):
    path = ROOT / '.work' / name; assert path.is_file(); archives['reviews/math-probes.zip'][name] = path
for version in ('01', '02'):
    folder = ROOT / ('.work/14-visual-qa-' + version)
    files = sorted(p for p in folder.rglob('*') if p.is_file()); assert len(files) == 4
    archives['reviews/visual-qa.zip'].update({version + '/' + p.relative_to(folder).as_posix(): p for p in files})
for entries in archives.values():
    for name, path in entries.items():
        assert path.is_file() and not path.is_symlink()
        assert not any(q in {'.git', '__pycache__', '..'} for q in Path(name).parts) and path.suffix.lower() not in {'.pyc', '.pyo'}

visual = read(ROOT / '.work/14-visual-qa-02/visual-review.json')
render = read(ROOT / '.work/14-visual-qa-02/render-receipt.json')
assert visual['closed'] == 1 and visual['open'] == visual['new_findings'] == 0
assert visual['browser_visual_qa'] is False and render['versions']['sharp'] == '0.35.5'
copy_sources = {f'raw/{n}': FULL / n for n in ('summary.json', 'tests.log', 'evidence.json', 'source-guard.json')}
copy_sources.update({'raw/integrated-source-freeze.json': ROOT / '.work/14-integrated-source-freeze-01.json',
                     'verify_packet.py': ROOT / '.work/verify_14_packet.py', 'tools/build_packet.py': Path(__file__).resolve()})
latest = {}
for record in render['records']:
    source_path = record['input'].replace('\\', '/'); relative = source_path[source_path.index('evidence/mainline/engineering/'):]
    name = Path(relative).stem + '.png'; path = ROOT / '.work/14-visual-qa-02' / name
    assert sha(path) == record['output_sha256'] and sha(ROOT / relative) == record['input_sha256']
    copy_sources['figures/' + name] = path
    latest['figures/' + name] = {'png_sha256': record['output_sha256'], 'svg_path': relative, 'svg_sha256': record['input_sha256']}
declared = sorted(['declaration.json', 'README.md', '.gitattributes', 'source-manifest.json', 'reviews/preservation.json', *copy_sources, *archives])
assert len(declared) == len(set(declared))
PACK.mkdir(parents=True, exist_ok=False)
write(PACK / 'declaration.json', {'schema': 'aegisdc-ticket14-root-declaration-v1', 'tested_source': SOURCE,
    'declared_artifacts': declared, 'terminal_receipt': 'receipt.json', 'runtime_caches': 'NOT_DELIVERABLE',
    'zip_policy': 'Inert exact original bytes, lazy member reads only; no source/gitattributes extraction', 'models_or_full_runs_by_packaging': 0})
for name, path in copy_sources.items():
    destination = PACK / name; destination.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, destination)
    assert destination.read_bytes() == path.read_bytes()
preservation = {'schema': 'aegisdc-ticket14-root-original-preservation-v1', 'archives': {}}
for name, entries in archives.items():
    path = PACK / name; path.parent.mkdir(parents=True, exist_ok=True); members = {}
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for member, original in sorted(entries.items()):
            data = original.read_bytes(); info = zipfile.ZipInfo(member, (2026, 11, 5, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o100644 << 16
            z.writestr(info, data); members[member] = {'sha256': sha256(data).hexdigest(), 'bytes': len(data), 'source_original': str(original)}
    preservation['archives'][name] = {'members': members, 'member_count': len(members), 'uncompressed_bytes': sum(v['bytes'] for v in members.values())}
write(PACK / 'reviews/preservation.json', preservation)
author = read(ROOT / 'docs/mainline/evidence/14.json')
protected = ['docs/mainline/evidence/' + n for n in ('M1.json', 'M2.json', 'M2-delivery.json', '12-root.json', '13-root.json', '14.json')]
protected += ['configs/full-facility-mainline-reserve-v6.json', 'configs/materials/reference-r134a-saturation.json', author['fixture'], author['contract'], author['current_index'], author['current_receipt']]
write(PACK / 'source-manifest.json', {'schema': 'aegisdc-ticket14-source-identity-v1', 'tested_source': SOURCE,
    'author_execution': author['execution_commit'], 'author_delivery': author['delivery_commit'],
    'protected_inputs': {n: sha(ROOT / n) for n in protected}, 'latest_visuals': latest,
    'visual_review': visual, 'sharp_version': render['versions']['sharp'], 'browser_visual_qa': False,
    'toolchain': {k: guard[k] for k in ('python_version', 'python_executable_sha256', 'numpy', 'torch')},
    'scope': '377 belongs to65ed; original371/369 belongs to3c; Q/R metadata are not execution revisions'})
readme = '''# 14 根接受：按可用时刻组织多源证据

证据账已在声明接口范围内接受：记录资产／设计、稀疏固定测点、历史维护、人工／工单和现场手持等来源，保存观测与到达时刻、共同来源、质量、过期、冲突及缺测。snapshot 只使用查询时刻已观测且已到达的记录，再形成可见记录间的关系；复制记录不被当成独立新来源。主场景含稀疏固定传感器，未覆盖位置不自动生成观察。

## 架构与时间图

![来源、入账与可见快照](figures/source-architecture.png)

![实际观测／到达／过期时间与显示窗口](figures/arrival-timeline.png)

这两件为根实际查看的 sharp0.35.5 本地栅格，不是 browser QA。新时间图对窗口两侧作 off-scale 标记，仍保留维护记录真实600s过期值。原版可视化1项发现、修订后1closed/open0/new0与两代PNG／render记录均惰性归档；原SVG字节不改。

## 实际根验收与历史身份

实际统一全检源为 `65eddd6908510371a6fcc913742b6c4197114270`：377/377，失败、错误、跳过均0；20份旧原件及166份Python／HEAD前后守卫通过。[原始日志](raw/tests.log)、[结果](raw/summary.json)、[守卫](raw/source-guard.json)保留原字节。本封装没有运行模型、目标批次或全套。

接口／工具执行源 f945、数据交付4b1997b7的[author候选索引](../../../../docs/mainline/evidence/14.json)和[CURRENT入口](../14-evidence/CURRENT.md)仍是原记录。最新9件产物＋收据、43旧原件、200前版来源以及50runtime／116tools／38inputs／20目标保留各自身份。原3c全检371/369及两旧可选跳过不追认为最新源全检。

## 评审、数学判别与范围

[Standards链](reviews/standards.zip)、[Spec最终与原发现](reviews/spec.zip)、[根独立数学诊断](reviews/math-probes.zip)、[两代视觉QA](reviews/visual-qa.zip)均为惰性ZIP。[每成员清单](reviews/preservation.json)逐项记录SHA／字节／原路径；其中脚本、属性或快照不会被解压为活动工作树。

最终Spec三项数值P2 closed3/open0/new0；Standards链接finding closed1/open0/new0，最终代码／格式无新增问题。区间、年龄、准入按已解码 finite int／binary64 的 Fraction 精确语义判别；派生数输出或不支持域遵循合同。这里没有引入EPS、修改原值／误差界，也不声称现场精度、真实概率或风险模型保证。

见[同一V6的证据fixture](../../../../configs/full-facility-evidence-v1.json)、[接口合同](../../../../docs/mainline/14-evidence-contract.md)及[14根权威](../../../../docs/mainline/evidence/14-root.json)。账本不替代15真值隔离、16稀疏渠道或17非固定检查机制的独立验收，也不构成诊断、修理、闭环恢复或方法收益。

## 只读交付复核

在封装提交的新checkout中用新的输出路径执行；仅核字节／Git／ZIP／状态，不调用证据或物理运行器：

```powershell
python -B evidence/mainline/engineering/14-root-acceptance/verify_packet.py --delivery-commit PACKET_COMMIT --output NEW_PROOF.json
```

独立fresh证明在后续metadata提交中单列，原packet收据保留pending状态。旧author fresh应在相应执行／交付revision核验，不能在任意新根下跳过哈希。

M3仍in_progress，当前primary15，15／16／17均ready且未分配。现场标定pending，注册效果、训练、LLM和AI／RSI资格尚未开启；完整研究目标保持active。M2sealed数据与既有站点设置保持原样。
'''
(PACK / 'README.md').write_text(readme, encoding='utf-8', newline='\n')
classes, lines = [], ['# Exact native root outputs; no global source-style relaxation.']
for name in [n for n in copy_sources if n.startswith('raw/')]:
    data = (PACK / name).read_bytes(); rows = data.splitlines(keepends=True)
    cr = sum(x.endswith(b'\r\n') for x in rows); spaces = sum(x.rstrip(b'\r\n').endswith((b' ', b'\t')) for x in rows)
    flags = ['-blank-at-eol' if spaces else 'blank-at-eol', 'blank-at-eof', 'space-before-tab'] + (['cr-at-eol'] if cr else [])
    if cr or spaces: lines.append(name + ' whitespace=' + ','.join(flags))
    classes.append({'path': name, 'native_CRLF_lines': cr, 'native_tail_space_lines': spaces, 'sha256': sha(PACK / name)})
(PACK / '.gitattributes').write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
write(PACK / 'receipt.json', {'schema': 'aegisdc-ticket14-root-receipt-v1', 'status': 'ACCEPTED_ROOT_ENGINEERING', 'tested_source': SOURCE,
    'delivery_gate': 'PENDING_COMMIT_AND_FRESH_CHECKOUT', 'actual_root_full_runs': 1, 'full_was_already_completed': True,
    'root_tests': summary['tests'], 'verified_old_originals': 20, 'python_byte_guard_files': 166,
    'review_axes': {'Standards': {'source_new': 0, 'final_core_new': 0, 'delivery_links_closed': 1, 'open': 0, 'new': 0, 'smells': 0},
                    'Spec': {'numeric_P2_closed': 3, 'open': 0, 'new': 0}, 'Root_visual': {'previous': 1, 'closed': 1, 'open': 0, 'new': 0}},
    'math_semantics': 'Fraction over decoded finite int/binary64; not physical precision or real probability calibration',
    'raw_format_classification': classes, 'artifacts': {n: sha(PACK / n) for n in declared},
    'new_models_by_packaging': 0, 'new_full_runs_by_packaging': 0, 'research_trials': 0, 'model_calls': 0, 'training_calls': 0,
    'field_calibration': 'PENDING', 'overall_goal': 'ACTIVE'})
write(ROOT / 'docs/mainline/evidence/14-root.json', {'schema': 'aegisdc-ticket-root-acceptance-v1', 'ticket': '14', 'status': 'ACCEPTED',
    'actual_root_source': SOURCE, 'root_tests': summary['tests'], 'old_originals': 20, 'python_files_guarded': 166,
    'packet': PACK.relative_to(ROOT).as_posix(), 'packet_receipt_sha256': sha(PACK / 'receipt.json'),
    'author_pending_index': 'docs/mainline/evidence/14.json', 'author_execution': author['execution_commit'], 'author_delivery': author['delivery_commit'],
    'latest_author_scope': author['durable_delivery'], 'original_full_scope': {'source': '3c4e9640', 'collected': 371, 'executed': 369, 'optional_skips': 2},
    'numeric_Spec_P2_closed': 3, 'Standards_links_closed': 1, 'visual_closed': 1, 'open_or_new_review_findings': 0,
    'scope': 'Detached timed multi-source evidence ledger, exact decoded-number interval/age/admission; not dispatch truth-isolation, channel coverage, risk or policy effect acceptance',
    'next_primary_ticket': '15', 'next_ready_unassigned': ['15', '16', '17'], 'M3': 'in_progress',
    'research_trials': 0, 'model_calls': 0, 'training_calls': 0, 'field_calibration': 'PENDING', 'overall_goal': 'ACTIVE'})
path = ROOT / '.scratch/full-facility-mainline/issues/14-evidence-ledger.md'; text = path.read_text(encoding='utf-8').replace('**Status:** claimed', '**Status:** resolved')
text += f'\n## Root acceptance 2026-11-05\n\nAccepted at actual source `{SOURCE}`:377/377,0fail/error/skip,20old originals,166Python/HEAD guards. Root authority `docs/mainline/evidence/14-root.json`; evidence packet `evidence/mainline/engineering/14-root-acceptance/README.md`. Author14.json/captures/red/fresh and prior371/369 remain their original snapshots. Three numeric Spec issues, one link issue and one visual issue are separately closed with no new finding. M3 remains active; primary15 and ready15/16/17 are unassigned.\n'
path.write_text(text, encoding='utf-8', newline='\n')
path = ROOT / 'docs/mainline/progress.json'; progress = read(path); progress['current_ticket'] = '15'
assert progress['current_milestone'] == 'M3' and all(x['ticket'] == '14' for x in progress['active_implementations'])
progress['active_implementations'] = []
next(x for x in progress['milestones'] if x['id'] == 'M3')['acceptance_evidence'].append('docs/mainline/evidence/14-root.json')
path.write_text(json.dumps(progress, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
path = ROOT / 'docs/current-research.json'; current = read(path)
current.update(implementation='M1/bounded M2 accepted; M3 timed evidence ledger14 accepted at source65ed/root377. Next15 truth-isolation,16 sparse channels and17 nonfixed inspection are ready/unassigned; risk, intervention and independent effects remain later.', current_primary_ticket='15', current_primary_ticket_assigned=False, next_ready_unassigned=['15', '16', '17'], evidence_ledger_acceptance='docs/mainline/evidence/14-root.json')
current['runtime_verification_documents'] += ['docs/mainline/14-evidence-contract.md', 'evidence/mainline/engineering/14-root-acceptance/README.md']
path.write_text(json.dumps(current, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
for filename in ['README.md', 'docs/MAINLINE.md', 'docs/NEXT.md']:
    path = ROOT / filename; text = path.read_text(encoding='utf-8')
    text = text.replace('当前M3主票14为多源证据账，已在独立工作树实施；', 'M3多源证据账14已由根接受：[377项原始结果、最新图及评审包](../evidence/mainline/engineering/14-root-acceptance/README.md)。当前主票15，15／16／17均ready且未分配；') if filename == 'docs/MAINLINE.md' else text
    if filename == 'docs/NEXT.md':
        text = text.replace('当前 M3 主票14为多源证据账，已在独立工作树实施。', 'M3多源证据账14已由根接受：[14根权威](mainline/evidence/14-root.json)、[数据图／377项根日志／惰性评审包](../evidence/mainline/engineering/14-root-acceptance/README.md)。当前primary15；15真值隔离、16稀疏渠道、17非固定检查均ready且未分配，不自动启动。')
    if filename == 'README.md':
        text = text.replace('当前进入M3，主票14多源证据账正在独立工作树实施；', 'M3多源证据账14现已接受：[377项根结果、最新图与闭环评审](evidence/mainline/engineering/14-root-acceptance/README.md)。当前primary15，15／16／17均ready且未分配；')
        text = text.replace('当前M3从主票14多源证据账继续；', '当前M3证据账14已接受，下一primary15及ready16／17未分配；')
    path.write_text(text, encoding='utf-8', newline='\n')
hint_path = ROOT / '.work/mainline-continuation-hints.json'; hints = read(hint_path)
hints.update(root_head=SOURCE, status='ACTIVE_TICKET14_ROOT377_PASSED_PACKET_READY_FOR_Q', primary_ticket='15', primary_ticket_assignment='UNASSIGNED;15/16/17parentwillallocate', active=[{'agent': '/root/mainline_02_merge', 'task': '14rootpacket Q/fresh/R;unique writer;no source changes'}], review_in_progress={})
hints['latest_root_code_regression'] = {'source': SOURCE, 'tests_run': 377, 'tests_executed': 377, 'failures': 0, 'errors': 0, 'skips': 0, 'historical_originals': 20, 'python_source_files_guarded': 166, 'folder': FULL.relative_to(ROOT).as_posix(), 'session': 91352, 'session_state': 'EXITED_0', 'rerun': 'DO_NOT_RERUN_FOR_PACKET_METADATA'}
hints['pending_actions'] = ['Commit14packet Q, actual fresh stdlib verification, independent14-delivery metadata R;0new models/full.', 'Parent review/publication, then allocate15/16/17;none started.', 'Source65ed377 alreadyPASS; no repeated full or bulk old verification for Q/R.']
hint_path.write_text(json.dumps(hints, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
print(json.dumps({'packet': str(PACK), 'declared_artifacts': len(declared), 'zip_members': sum(len(x) for x in archives.values()), 'root_full_source': SOURCE, 'new_model_or_full_runs': 0}, ensure_ascii=False))
