"""Assemble this one M2 acceptance packet; never run models or test suites."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path.cwd()
SOURCE = 'bcacbf78e4f071acd0a130c8dec85f5c95e4cc73'
PACK = ROOT / 'evidence/mainline/engineering/M2-root-acceptance'
TEMP = Path('C:/Users/Donson/AppData/Local/Temp')
FULL = ROOT / 'runs/mainline-M2-root-acceptance-20261105-01'


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


assert git('rev-parse', 'HEAD') == SOURCE
assert git('branch', '--show-current') == 'donson/full-facility-mainline'
assert not git('status', '--porcelain')
assert not PACK.exists()
summary = read(FULL / 'summary.json'); guard = read(FULL / 'source-guard.json')
assert summary['tests']['run'] == summary['tests']['executed'] == 359
assert summary['tests']['failures'] == summary['tests']['errors'] == summary['tests']['skipped'] == 0
assert guard['source_commit_before'] == guard['source_commit_after'] == SOURCE
assert guard['sources_unchanged'] and guard['head_unchanged'] and len(guard['actual_python_sources']) == 156
for name, expected in guard['actual_python_sources'].items():
    assert sha(ROOT / name) == expected, name

reviews = [
    ('12-standards', 'aegisdc-review-12-full-standards.md', 'aegisdc-review-12-full-standards-attachments', 7, 'b6fea7f266c8ec86413668cef462ace0e2f0ed66123a67459724072fb10b347f'),
    ('12-spec', 'aegisdc-review-12-full-spec.md', 'aegisdc-review-12-full-spec-attachments', 64, 'edc2d468bad1da49ebcfaee34181ab1377aa10040237c799105581e9f8130060'),
    ('13-spec', 'aegisdc-review-13-reader-v3-spec.md', 'aegisdc-review-13-reader-v3-spec-attachments', 78, 'd9cabf75e640fd8ac9c034ec73f6a158dcc8f39103dfdd5cba3c4898ab947c0d'),
]
archives = {}
for label, report, folder, count, expected in reviews:
    report = TEMP / report; folder = TEMP / folder
    assert report.is_file() and folder.is_dir() and sha(report) == expected
    files = sorted(p for p in folder.rglob('*') if p.is_file())
    assert len(files) == count
    entries = {'report.md': report}
    entries.update({'attachments/' + p.relative_to(folder).as_posix(): p for p in files})
    archives['reviews/' + label + '.zip'] = entries
std_report = TEMP / 'aegisdc-review-13-reader-v3-standards.md'
assert sha(std_report) == 'b39048fb17c4805755adaecc3ea6ec592934e26bcd20e29fb7be1f60c90d7f6b'
probe = TEMP / 'aegisdc-reader-v3-standards-rng9gzey'
files = sorted(p for p in probe.rglob('*') if p.is_file())
assert len(files) == 11 and sum(p.stat().st_size for p in files) == 29498
entries = {'report.md': std_report}
for name in ('standards-evidence', 'delivery-command', 'delivery', 'attribute-union'):
    path = TEMP / ('aegisdc-review-13-reader-v3-' + name + '.json')
    assert path.is_file()
    entries['attachments/' + path.name] = path
entries.update({'attachments/probe/' + p.relative_to(probe).as_posix(): p for p in files})
archives['reviews/13-standards.zip'] = entries
for entries in archives.values():
    for name, path in entries.items():
        assert path.is_file() and not path.is_symlink()
        assert '.git' not in Path(name).parts and '__pycache__' not in Path(name).parts
        assert Path(name).suffix not in {'.pyc', '.pyo'}

copy_sources = {f'raw/{n}': FULL / n for n in ('summary.json', 'tests.log', 'evidence.json', 'source-guard.json')}
copy_sources.update({
    'bridges/integrated-source.json': ROOT / '.work/M2-integrated-source-freeze-01.json',
    'bridges/physical-kernel.json': ROOT / '.work/M2-physical-kernel-bridge-precheck-02.json',
    'bridges/combined-raw.json': ROOT / '.work/M2-cross-source-combined-raw-bridge-01.json',
    'tools/root-full-wrapper.py': ROOT / '.work/run_M2_root_acceptance.py',
    'tools/build_packet.py': Path(__file__).resolve(),
    'verify_packet.py': ROOT / '.work/M2_verify_packet.py',
})
assert all(path.is_file() for path in copy_sources.values())
declared = sorted(['declaration.json', '.gitattributes', 'README.md', 'source-manifest.json', 'reviews/preservation.json', *copy_sources, *archives])
assert len(declared) == len(set(declared)) == 19
PACK.mkdir(parents=True, exist_ok=False)
write(PACK / 'declaration.json', {
    'schema': 'aegisdc-M2-root-durable-declaration-v1', 'classification': 'ROOT_ENGINEERING_ACCEPTANCE_NOT_RESEARCH',
    'tested_source': SOURCE, 'declared_artifacts': declared, 'terminal_receipt': 'receipt.json',
    'runtime_caches': 'NOT_DELIVERABLE', 'zip_policy': 'Exact inert original bytes; verify members lazily without extraction',
    'receipt_policy': 'receipt.json excluded from self-hash and verified independently against delivery Git blobs',
    'new_full_suite_runs': 0, 'new_model_runs': 0})
for name, path in copy_sources.items():
    destination = PACK / name; destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, destination)
    assert destination.read_bytes() == path.read_bytes()
preservation = {'schema': 'aegisdc-four-axis-original-preservation-v1', 'archives': {},
                'container_timestamp': 'Fixed ZIP container timestamp only; original member bytes are never normalized'}
for name, entries in archives.items():
    destination = PACK / name; destination.parent.mkdir(parents=True, exist_ok=True)
    members = {}
    with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for member, path in sorted(entries.items()):
            data = path.read_bytes()
            info = zipfile.ZipInfo(member, (2026, 11, 5, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
            members[member] = {'sha256': sha256(data).hexdigest(), 'bytes': len(data), 'source_original': str(path)}
    preservation['archives'][name] = {'members': members, 'member_count': len(members), 'uncompressed_bytes': sum(x['bytes'] for x in members.values())}
write(PACK / 'reviews/preservation.json', preservation)

old_indexes = ['docs/mainline/evidence/' + name for name in ('M1.json', '12.json', '13.json', '13-reader-v2.json', '13-reader-v3.json')]
linked = ['evidence/mainline/engineering/12-numerical/final-entry-01/summary.json',
          'evidence/mainline/engineering/12-numerical/final-entry-01/qualification-summary.png',
          'evidence/mainline/engineering/11-coupled/architecture-v2-01/facility-architecture-v2.png']
write(PACK / 'source-manifest.json', {
    'schema': 'aegisdc-M2-source-and-metadata-boundary-v1', 'tested_source': SOURCE,
    'replay_runtime_source': 'e4ecc1a8b30f7d85cb1b0fc31157c7d178289c40', 'preserved_legacy_source': '1309bc8273e39bd519ef6f22400568153078f373',
    'preserved_indexes': {n: sha(ROOT / n) for n in old_indexes}, 'linked_inputs': {n: sha(ROOT / n) for n in linked},
    'actual_root_toolchain': {k: guard[k] for k in ('python_executable', 'python_version', 'python_executable_sha256', 'numpy', 'torch')},
    'source_sets': {'numeric_runtime_entries': 16, 'replay_runtime_entries': 18, 'whole_identity_equal': False},
    'scope': 'Metadata Q/R are not the bcac full execution. Six old AST definitions and ONE saved combined h1 case form a finite bridge only.'})

readme = '''# M2 根接受：有限数值资格与可追溯重放

M2 已按同一 V6 合成设施接受。实际统一回归源为 `bcacbf78e4f071acd0a130c8dec85f5c95e4cc73`：359 项全执行，失败、错误、跳过均为 0；20 份历史原件通过，156 份 Python 源码和 HEAD 前后守卫一致。两项原可选 Torch 单元检查实际执行。原作者的 317/315、cf9 的 345/343 保留其原执行身份。

## 数据图与架构

![十一组有限数值资格见证](../12-numerical/final-entry-01/qualification-summary.png)

图来自数值作者的最终原件。指标是事件侧锚点／相位一致对齐，并保留闭区间振幅；同钟因果 raw 差异和实际事件时差另列。它不是未保存真轨迹的误差包络，也不是连续参数域保证。

![同一 V6 的四类关系与双向访问架构](../11-coupled/architecture-v2-01/facility-architecture-v2.png)

架构图保留原物理执行 b135、绘图源 2727 和 visual delivery eb5 的身份。物理、功能／容量、控制／信息及访问关系共用实体 ID；它不是现场 P&ID。

## 本次接受的内容

- [12 根权威](../../../../docs/mainline/evidence/12-root.json)：11 个声明工况、102 个原 ZIP／408 成员／306705 状态和 5 个实际执行身份。原 NO-GO、失败、表示边界与拒绝保持公开。
- 下一阶段显式选择最大步长 `.01 s`。五个旧工况仍采用 `.025` 对 `.02/.01` 的原阶梯；四个细化工况采用 `.01` 对 `.005/.0025`；两个进一步分辨工况采用 `.01` 对 `.0025/.00125`。五个旧工况没有新增更细的 `.01` 参考；各见证按其冻结阶梯解释。
- [13 根权威](../../../../docs/mainline/evidence/13-root.json)：外生需求／天气／故障与工程命令分开；版本、生命周期、请求实际时长／步长、区间时间轴和解释器身份受检。新 capture-05 有 4 个完成请求和 3 个真实 CLI 拒绝，26 项局部目标通过，作者本修订未运行全套。旧 01/02/04 和 pending receipts 不改写。
- 四轴最终评审分别保存在惰性 ZIP：[12 Standards](reviews/12-standards.zip)、[12 Spec](reviews/12-spec.zip)、[13 Standards](reviews/13-standards.zip)、[13 Spec](reviews/13-spec.zip)。[成员清单](reviews/preservation.json)记录每件字节数、SHA 和来源；ZIP 中的脚本、属性或探针不被解压为活动代码。
- [根原始日志](raw/tests.log)、[结果](raw/summary.json)、[源码守卫](raw/source-guard.json)、[初始收据](receipt.json)及[声明集合](declaration.json)保存实际证据。

## 有限源桥接

数值运行时身份为 16 项，重放运行时为 18 项，两者完整身份不同。8e→cf9 的六个旧定义（含整个 `_Plant`）相同，公共运行入口的命令来源、日志和输入 manifest 有变。旧 5bc 的 combined-240s/h1 与 cf9 同工况的参数赋值并集、作业、时长和步长一致；scenario、state、balance 三件逐字节相同，summary／work records 一致。[AST 桥接](bridges/physical-kernel.json)与[保存字节桥接](bridges/combined-raw.json)只支持这一有限对应，不扩为整个运行时相等或绝对误差界。

## 只读复核与下一入口

在封装提交的新 checkout 中运行以下定点校验，输出另用新路径；它只读 SHA／Git blobs、ZIP 成员、状态和有限桥接，不调用模型或全套测试：

```powershell
python -B evidence/mainline/engineering/M2-root-acceptance/verify_packet.py --delivery-commit PACKET_COMMIT --output NEW_PROOF.json
```

需要新工程轨迹时显式选择受述范围内的 V6／步长，并使用新输出目录；本封装没有执行该命令：

```powershell
$env:PYTHONPATH = 'src'
python -m aegis_dc simulate --model configs/full-facility-mainline-reserve-v6.json --step .01 --duration 10 --output NEW_OUTPUT_DIRECTORY
```

兼容 CLI 的 v2／h=1 s 默认保留原适用域；M2 数值入口显式使用上述 V6／.01 参数。原 05 verifier 在其历史 8ac checkout 验冻结属性；当前根 union 单独见证，不能冒充旧输入或任意跳过哈希。

[M2 权威与范围](../../../../docs/mainline/evidence/M2.json)接受的是声明的有限工况和方法。现场标定 pending；注册效果研究、LLM／训练、AI／RSI 增量均未启动。下一主票 14 为多源证据账，尚未分配；主场景存在稀疏固定传感器，允许历史／人工／工单／手持资料，后台真值不自动交给调度。M2 不是整个研究目标完成。
'''
(PACK / 'README.md').write_text(readme, encoding='utf-8', newline='\n')
format_rows = []
attribute_lines = ['# Exact native archival outputs; authored helper and source retain normal checks.']
for name in [n for n in copy_sources if n.startswith('raw/') or n == 'tools/root-full-wrapper.py']:
    data = (PACK / name).read_bytes(); lines = data.splitlines(keepends=True)
    cr = sum(line.endswith(b'\r\n') for line in lines)
    spaces = sum(line.rstrip(b'\r\n').endswith((b' ', b'\t')) for line in lines)
    flags = ['-blank-at-eol' if spaces else 'blank-at-eol', 'blank-at-eof', 'space-before-tab']
    if cr: flags.append('cr-at-eol')
    if cr or spaces: attribute_lines.append(name + ' whitespace=' + ','.join(flags))
    format_rows.append({'path': name, 'native_CRLF_lines': cr, 'native_tail_space_lines': spaces, 'sha256': sha(PACK / name)})
(PACK / '.gitattributes').write_text('\n'.join(attribute_lines) + '\n', encoding='utf-8', newline='\n')
write(PACK / 'receipt.json', {
    'schema': 'aegisdc-M2-root-acceptance-receipt-v1', 'status': 'ACCEPTED_ROOT_ENGINEERING', 'tested_source': SOURCE,
    'delivery_gate': 'PENDING_COMMIT_AND_FRESH_CHECKOUT', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'root_full_runs': 1, 'full_was_already_completed_before_packaging': True, 'root_tests': summary['tests'], 'verified_old_originals': 20,
    'toolchain': {k: guard[k] for k in ('python_version', 'python_executable_sha256', 'numpy', 'torch')},
    'review_axes': {'12_Standards': {'new': 0, 'open': 0, 'smells': 0}, '12_Spec': {'previous_closed': 1, 'new': 0, 'open': 0},
                    '13_Standards': {'balance_closed': 1, 'attribute_closed': 1, 'new': 0, 'open': 0, 'smells': 0},
                    '13_Spec': {'request_closed': 1, 'previous_version_closed': 1, 'new': 0, 'open': 0}},
    'raw_format_classification': format_rows, 'artifacts': {n: sha(PACK / n) for n in declared},
    'source_and_root_metadata_are_distinct': True, 'new_full_runs_by_packaging': 0, 'new_models_by_packaging': 0,
    'research_trials': 0, 'model_calls': 0, 'training_calls': 0, 'field_calibration': 'PENDING', 'AI_RSI': 'NOT_OPEN_BEFORE_ELIGIBILITY', 'overall_goal': 'ACTIVE'})

numeric = read(ROOT / linked[0]); base_gate = {'status': 'ACCEPTED', 'actual_root_source': SOURCE,
    'root_full_summary': str(PACK.relative_to(ROOT) / 'raw/summary.json').replace('\\', '/'),
    'packet': str(PACK.relative_to(ROOT)).replace('\\', '/'), 'packet_receipt_sha256': sha(PACK / 'receipt.json'),
    'root_tests': summary['tests'], 'old_originals': 20, 'research_trials': 0, 'model_calls': 0, 'training_calls': 0,
    'field_calibration': 'PENDING', 'overall_goal': 'ACTIVE'}
write(ROOT / 'docs/mainline/evidence/12-root.json', dict(base_gate, schema='aegisdc-ticket-root-acceptance-v1', ticket='12',
    accepted_candidate='37ebc676a9d18c7874ba4313062fbcb7a133867a', numerical_summary=linked[0], numerical_summary_sha256=sha(ROOT / linked[0]),
    finite_witnesses=11, original_archives=102, archive_members=408, stored_state_points=306705, actual_execution_identities=5,
    metric=numeric['metric_semantics'], declared_limits=numeric['limits'], recommended_explicit_maximum_step_s=.01,
    witness_ladders={'five_original': {'count': 5, 'candidate_s': .025, 'reference_pair_s': [.02, .01], 'new_finer_reference_for_chosen_point': False},
                     'four_refined': {'count': 4, 'candidate_s': .01, 'reference_pair_s': [.005, .0025]},
                     'two_resolution': {'count': 2, 'candidate_s': .01, 'reference_pair_s': [.0025, .00125]}},
    raw_and_actual_timing_reported_separately=True, continuous_parameter_box_or_true_error_bound=False, old_NO_GO_and_failures_preserved=True))
write(ROOT / 'docs/mainline/evidence/13-root.json', dict(base_gate, schema='aegisdc-ticket-root-acceptance-v1', ticket='13',
    accepted_candidate='73e5c5c15eecfcc00825069b126e82c9097125dd', reader_core='e59d3ec16a598dde80cb9dcd1a26e695e2f2360c',
    latest_author_execution='e4ecc1a8b30f7d85cb1b0fc31157c7d178289c40', latest_author_delivery='8ac3f7865f2fd36af4859116307b11df1726fae0',
    latest_capture={'completed': 4, 'staged_CLI_refusals': 3, 'focused_targets': 26, 'author_full_suite': 'NOT_RUN_THIS_REVISION'},
    preserved_historical_full={'source': 'cf9b33900d8f349b9a8145c042bbffe03503c858', 'collected': 345, 'executed': 343, 'optional_skips': 2},
    engineering_replay_only=True, source_interpreter_inputs_time_axis_and_origin_authority_checked=True,
    private_future_schedule_and_actual_state_not_dispatch_evidence=True, registered_research_gate='CLOSED_UNTIL_NEW_PROTOCOL_AND_BUDGET'))
write(ROOT / 'docs/mainline/evidence/M2.json', dict(base_gate, schema='aegisdc-milestone-root-acceptance-v1', milestone='M2',
    accepted_tickets=['12', '13'], authority_records=['docs/mainline/evidence/12-root.json', 'docs/mainline/evidence/13-root.json'],
    acceptance_scope='Finite same-V6 numerical witnesses and engineering replay/reader contracts, with independent axes and actual root359',
    bridge_scope='Six unchanged old definitions plus one actual combined240/h1 byte bridge; whole runtime identities differ16vs18',
    next_milestone='M3', next_primary_ticket='14', next_ticket_assigned=False,
    remaining_limits=['No conservative same-clock raw/unsampled-true-trajectory envelope or continuous parameter-box guarantee',
                      'Five original witness ladders have no newly finer .01 reference', 'Field calibration pending',
                      'Evidence availability, risk, diagnosis/intervention/recovery and independent effects remain later tickets',
                      'No registered effect trial or AI/RSI qualification has been opened']))

progress_path = ROOT / 'docs/mainline/progress.json'; progress = read(progress_path)
progress.update(current_ticket='14', current_milestone='M3')
for milestone in progress['milestones']:
    if milestone['id'] == 'M2': milestone.update(status='accepted', acceptance_evidence=['docs/mainline/evidence/12-root.json', 'docs/mainline/evidence/13-root.json', 'docs/mainline/evidence/M2.json'])
    if milestone['id'] == 'M3': milestone['status'] = 'in_progress'
assert all(item['ticket'] in {'12', '13'} for item in progress['active_implementations'])
progress['active_implementations'] = []
progress_path.write_text(json.dumps(progress, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
for number, filename in [('12', '12-numerical-verification.md'), ('13', '13-event-replay.md')]:
    path = ROOT / '.scratch/full-facility-mainline/issues' / filename
    text = path.read_text(encoding='utf-8').replace('**Status:** claimed', '**Status:** resolved')
    text += f'\n## Root acceptance 2026-11-05\n\nAccepted at actual integrated source `{SOURCE}`:359/359 executed,0 failure/error/skip,20 old originals and156 Python-byte/HEAD guards. Final independent axes have no open/new findings. Root authority: `docs/mainline/evidence/{number}-root.json`; shared M2 packet: `evidence/mainline/engineering/M2-root-acceptance/README.md`. Author candidate indexes/pending receipts and every prior failure remain historical originals. Root metadata/delivery commits do not replace the tested source. Next primary14 is unassigned; M2 is not the overall research goal.\n'
    path.write_text(text, encoding='utf-8', newline='\n')
current_path = ROOT / 'docs/current-research.json'; current = read(current_path)
current.update(phase='complete_facility_evidence_and_risk', implementation='M1 and bounded M2 accepted at root; current M3 starts with unassigned ticket14 multi-source evidence ledger. Risk/inspection/intervention/independent effects and conditional AI/RSI remain later.',
               M2_acceptance='docs/mainline/evidence/M2.json', current_primary_ticket='14', current_primary_ticket_assigned=False,
               numerical_entry={'model': 'configs/full-facility-mainline-reserve-v6.json', 'explicit_maximum_step_s': .01, 'scope': 'Declared finite witnesses and their distinct reference ladders; not a global parameter-box guarantee'})
current['runtime_verification_documents'] += ['docs/mainline/12-numerical-qualification.md', 'docs/mainline/13-replay-contract.md', 'evidence/mainline/engineering/M2-root-acceptance/README.md']
current_path.write_text(json.dumps(current, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
path = ROOT / 'docs/MAINLINE.md'; text = path.read_text(encoding='utf-8')
lines = text.splitlines()
for index, line in enumerate(lines):
    if line.startswith('当前M1已由根接受：'):
        lines[index] = 'M1 八域同场基线和 M2 有限数值／重放门槛现均由根接受：[M1 原快照](mainline/evidence/M1.json)、[M2 当前权威](mainline/evidence/M2.json)与[数据图、四轴评审和复核包](../evidence/mainline/engineering/M2-root-acceptance/README.md)。实际 M2 统一回归源 bcac 为359项全执行零跳过；11个数值见证按5/4/2三类冻结阶梯解释，原NO-GO、失败和作者执行身份保留。下一阶段显式运行选择V6与最大步长.01；这不构成任意参数域或真轨迹绝对误差界。当前M3主票14为多源证据账，尚未分配；风险、专业检查处置、恢复和独立方法比较继续。主场景存在稀疏固定传感器，并允许历史、人工、工单和手持结果；后台真值保持私有。整个研究目标仍active。'
path.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
path = ROOT / 'README.md'; text = path.read_text(encoding='utf-8')
text = text.replace('更深的M1/M2验证、风险证据与策略闭环仍按固定主线推进。', '当前分阶段资格以新的 M2 根记录为准，风险证据与策略闭环继续按固定主线推进。')
old = '**M1同一完整设施的八域工程基线已接受**：'
lines = text.splitlines()
for i, line in enumerate(lines):
    if line.startswith(old):
        lines[i] = '**M1 与有限 M2 已由根接受**：[M1 原工程基线](evidence/mainline/engineering/M1-root-acceptance/README.md)和[M2 数值图、正确架构及复核包](evidence/mainline/engineering/M2-root-acceptance/README.md)保留各自执行身份。M2 实际根源 bcac 的359项全执行零跳过、11组有限见证及重放契约已核对；事件侧指标、raw差异和各自参考阶梯分列。当前进入M3，主票14多源证据账待分配；完整研究目标仍active。数值研究显式使用 `--model configs/full-facility-mainline-reserve-v6.json --step .01` 和新输出目录，见复核包；兼容默认保持原样。'
    if line.startswith('结构与风险原型、M1八域工程基线均已交付；当前进行M2'):
        lines[i] = '结构／风险原型、M1八域基线与声明有限范围的M2数值／重放门槛已交付。当前M3从主票14多源证据账继续；检查处置、独立比较及条件式AI/RSI仍在后续。详见[主线进度](docs/mainline/progress.json)，现场标定pending。原会议笔记、浏览器缓存、依赖和重复导出不进入公开仓库；本地文件不删除。'
path.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
path = ROOT / 'docs/NEXT.md'; old = path.read_text(encoding='utf-8'); history = old.split('\n---\n', 1)[1]
prefix = '''# 当前执行：完整设施风险驱动检查与处置主线

固定目标见[MAINLINE](MAINLINE.md)，实际门槛见[progress](mainline/progress.json)，任务依赖见[任务图](../.scratch/full-facility-mainline/map.md)。

M1 和声明有限范围的 M2 已由根接受：[M1 原快照](mainline/evidence/M1.json)、[M2 根权威](mainline/evidence/M2.json)、[数值数据图／正确架构／四轴评审](../evidence/mainline/engineering/M2-root-acceptance/README.md)。实际 M2 根源 bcac 记录359项全执行零跳过、20历史原件与156 Python字节守卫。旧作者全检、NO-GO、失败及原 pending receipts 仍保留其原身份。

当前 M3 主票14为多源证据账，尚未分配，不自动启动。主场景有稀疏固定传感器，允许历史／人工／工单／手持数据；未覆盖位置不生成观测，后台真值不自动给调度。后续仍需风险认识、异质检查处置及恢复核验、独立效果对照和条件式AI/RSI资格。

下一阶段数值研究显式使用 `--model configs/full-facility-mainline-reserve-v6.json --step .01` 和全新输出目录。11个见证仍按5/4/2各自冻结阶梯解释；五个旧案没有新增更细的.01参考，事件侧指标不是同钟raw或未保存真轨迹的保守界。详见M2包的只读复核路径。

本次没有新注册研究、训练或LLM试验；不恢复会前确认集。现场标定pending，完整42任务研究目标保持active。
'''
path.write_text(prefix + '\n---\n' + history, encoding='utf-8', newline='\n')
print(json.dumps({'packet': str(PACK), 'declared_artifacts': len(declared), 'review_zip_members': sum(len(v) for v in archives.values()), 'tested_source': SOURCE, 'new_full_or_models': 0}, ensure_ascii=False))
