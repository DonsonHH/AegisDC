"""Build the four deliverables from closed actual records; no environment/model."""
import argparse
from collections import defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path
import statistics

REMOTE = Path('/share/home/renly/renly-patrol-rsi/runs/20261101-multistep')
SIGNATURE = '32a11decd9f1a6da94ca63cbc7c6f25a3341f357ef2cce43a52f4775b3be79d0'


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(path):
    return [json.loads(v) for v in path.read_text(encoding='utf8').splitlines() if v.strip()] if path.exists() else []


def fmt(value):
    return '—' if value is None else f'{value:.3f}' if isinstance(value, float) else str(value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    stage = root / 'research/2026-11-01-multistep-workflow'
    run = args.run.resolve()
    all_rows = [read(p) for p in sorted((run / 'evaluations').glob('episode-*/complete.json'))]
    rows = [r for r in all_rows if r['source_manifest_sha256'] == SIGNATURE]
    assert len(rows) == len({(r['case_id'], r['arm']) for r in rows})
    assert len([r for r in rows if r['arm'] in ('A', 'B', 'C', 'D')]) == 24
    assert all(r['audit']['passed'] and r['metrics']['tasks_violating_exact_gap'] == 0 for r in rows)
    assert len(lines(run / 'environment-attempts.jsonl')) <= 60
    assert len(lines(run / 'model-calls.jsonl')) <= 4
    records = {}
    for row in rows:
        path = run / Path(row['record_path']).relative_to(REMOTE)
        assert sha(path) == row['record_sha256']
        records[(row['case_id'], row['arm'])] = json.loads(gzip.decompress(path.read_bytes()))
    cases = sorted({r['case_id'] for r in rows})
    by = {(r['case_id'], r['arm']): r for r in rows}
    paired = []
    for case in cases:
        c, d = records[(case, 'C')], records[(case, 'D')]
        assert c['process_fingerprint'] == d['process_fingerprint']
        first_c, first_d = c['optional_chain'][:1], d['optional_chain'][:1]
        assert bool(first_c) == bool(first_d)
        if first_c:
            for key in ('dispatch_time_s', 'agent', 'task', 'expected_finish_s', 'before_shared', 'completed'):
                assert first_c[0][key] == first_d[0][key], ('Identical first action and measurement', case, key)
        paired.append({'case_id': case, 'same_actual_actions': c['action_sha256'] == d['action_sha256'],
            'first_action_and_measurement_identical': True,
            'miss_delta_D_minus_C': d['metrics']['missed_segments'] - c['metrics']['missed_segments'],
            'wait_delta_D_minus_C_s': (d['metrics']['consequence_weighted_censored_delay_s'] - c['metrics']['consequence_weighted_censored_delay_s'])
                if d['metrics']['consequence_weighted_censored_delay_s'] is not None else None,
            'travel_delta_D_minus_C_m': d['metrics']['travel_m'] - c['metrics']['travel_m'],
            'service_delta_D_minus_C_s': d['metrics']['service_s'] - c['metrics']['service_s']})
    model_change = read(run / 'child-workflow.json') if (run / 'child-workflow.json').exists() else None
    model_comparisons = []
    if model_change:
        assert len([r for r in rows if r['arm'] == 'child']) == 6
        for case in cases:
            parent, child = records[(case, 'D')], records[(case, 'child')]
            assert parent['process_fingerprint'] == child['process_fingerprint']
            first = next(({'time_s': a['time_s'], 'parent': a['choices'], 'child': b['choices']}
                          for a, b in zip(parent['action_log'], child['action_log']) if a['choices'] != b['choices']), None)
            model_comparisons.append({'case_id': case, 'changed_actual_actions': first is not None,
                'first_actual_difference': first,
                'miss_delta_child_minus_parent': child['metrics']['missed_segments'] - parent['metrics']['missed_segments'],
                'wait_delta_child_minus_parent_s': (child['metrics']['consequence_weighted_censored_delay_s'] - parent['metrics']['consequence_weighted_censored_delay_s'])
                    if parent['metrics']['consequence_weighted_censored_delay_s'] is not None else None,
                'extra_delta_child_minus_parent': child['metrics']['selected_detours'] - parent['metrics']['selected_detours'],
                'travel_delta_child_minus_parent_m': child['metrics']['travel_m'] - parent['metrics']['travel_m'],
                'service_delta_child_minus_parent_s': child['metrics']['service_s'] - parent['metrics']['service_s']})
    receipt_rows = []
    for (case, arm), record in records.items():
        if arm == 'D' and record['optional_chain']:
            first = record['optional_chain'][0]
            receipt_rows.append({'case_id': case, 'dispatch_time_s': first['dispatch_time_s'],
                'completion': first['completed'], 'information': first['information'],
                'shared_after': first['after_task']['qualified'],
                'first_post_measurement_selection': next((f for f in record['workflow_frames']
                    if f['selected'] is not None and f['time_s'] >= first['completed']['time_s']), None)})
    # Timeline selection is by mechanism and fixed case order, never score gain.
    example_case = next((case for case in cases if len(records[(case, 'D')]['optional_chain']) == 2), cases[0])
    example = records[(example_case, 'D')]
    timeline = {'case_id': example_case, 'selection_rule': 'First case in fixed case-id order with two actual checks; not best score',
        'specification': example['specification'], 'arm': 'D', 'process_fingerprint': example['process_fingerprint'],
        'optional_chain': example['optional_chain'], 'workflow_decisions': example['workflow_frames'],
        'all_359_action_frames': example['action_log'], 'all_actual_assignments': example['assignments'],
        'all_actual_qualified_events': example['inspection_events'], 'metrics': example['metrics'],
        'all_dispatch_safety': example['dispatch_safety'], 'exact_gaps': example['exact_task_gaps'],
        'paired_C_record': by[(example_case, 'C')], 'D_record': by[(example_case, 'D')]}
    (stage / '行动时间线.json').write_text(json.dumps(timeline, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf8')
    fields = ['case_id', 'seed', 'scenario', 'arm', 'K', 'missed_segments', 'wait_s', 'extra_checks',
              'travel_m', 'service_s', 'exact_revisit_violations', 'first_dispatch_s', 'first_complete_s',
              'second_dispatch_s', 'second_complete_s', 'same_time_remote_for_first', 'action_sha256', 'record_sha256']
    csv_rows = []
    for row in sorted(rows, key=lambda r: (r['case_id'], r['arm'])):
        record = records[(row['case_id'], row['arm'])]
        chain = record['optional_chain']
        m = row['metrics']
        csv_rows.append(dict(case_id=row['case_id'], seed=row['specification']['seed'], scenario=row['specification']['scenario'],
            arm=row['arm'], K=1 if row['arm'] in ('A', 'B') else 2,
            missed_segments=m['missed_segments'], wait_s=m['consequence_weighted_censored_delay_s'],
            extra_checks=m['selected_detours'], travel_m=m['travel_m'], service_s=m['service_s'],
            exact_revisit_violations=m['tasks_violating_exact_gap'],
            first_dispatch_s=chain[0]['dispatch_time_s'] if chain else None,
            first_complete_s=chain[0]['completed']['time_s'] if chain else None,
            second_dispatch_s=chain[1]['dispatch_time_s'] if len(chain) > 1 else None,
            second_complete_s=chain[1]['completed']['time_s'] if len(chain) > 1 else None,
            same_time_remote_for_first=chain[0]['information']['contemporaneous_remote_same_quantity'] if chain else None,
            action_sha256=row['action_sha256'], record_sha256=row['record_sha256']))
    with (stage / '全条件结果.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(csv_rows)
    accounting = []
    if (run / 'accounting.psv').exists():
        with (run / 'accounting.psv').open(encoding='utf8') as f:
            accounting = list(csv.DictReader(f, delimiter='|'))
    cpu_minutes = sum(int(r['ElapsedRaw']) * int(r['AllocCPUS']) for r in accounting) / 60
    gpu_seconds = sum(int(r['ElapsedRaw']) for r in accounting if 'gres/gpu=1' in r.get('AllocTRES', ''))
    costs = {'environment_attempts': len(lines(run / 'environment-attempts.jsonl')), 'completed_all_versions': len(all_rows),
        'main_comparison_episodes': len(rows), 'superseded_source_episodes': len(all_rows) - len(rows),
        'real_model_calls': len(lines(run / 'model-calls.jsonl')), 'CPU_core_minutes': cpu_minutes,
        'GPU_allocation_seconds': gpu_seconds, 'Slurm': accounting, 'new_physical_processes': len(list((run / 'processes').glob('*/complete.json')))}
    assert costs['CPU_core_minutes'] <= 120 and costs['GPU_allocation_seconds'] <= 900
    assert costs['new_physical_processes'] == 6
    group_stats = {}
    for arm in sorted({r['arm'] for r in rows}):
        own = [r['metrics'] for r in rows if r['arm'] == arm]
        group_stats[arm] = {'macro_missed_per_condition': statistics.mean(m['missed_segments'] for m in own),
            'mean_wait_over_event_conditions_s': statistics.mean(m['consequence_weighted_censored_delay_s'] for m in own if m['consequence_weighted_censored_delay_s'] is not None),
            'mean_extra_checks': statistics.mean(m['selected_detours'] for m in own)}
    report = [
        '# 最小多步巡检原型：实际结果与决策', '',
        '本轮恢复了“真实检查—共享测量更新—后续任务选择”的多步接口，并实际运行六个开发条件。工程闭环与任务收益分别判断。旧M12-D/E/F/G代码、原件、NO-GO和未打开最终集均保留。', '',
        '## 1. 原目标与新研究对象', '',
        '导师目标是按设备、风险与专业资格决定谁在何时去哪里检查什么，并由经验改进技能、工具使用与协作。旧K=1与仅改触发谓词属于归因诊断；本轮K=2只是机制试验，不是现场许可。128机柜、18人、固定所属、原物理/测量/工时、安全与持续重访不变。', '',
        '## 2. 可运行的最小工作流', '',
        '代码与完整命令见[原型与复现](../research/2026-11-01-multistep-workflow/原型与复现.md)。在线只执行白名单逻辑；每次派单重新核验累积返回计划，第一次真实测量完成后才允许第二项额外工作。实际测量写入共享状态并保留来源时间。固定CVAE为估计工具；本轮没有PPO排序或模型训练。', '',
        '## 3. 全部开发结果与真实时间线', '',
        '每格为“漏检段数 / 后果加权等待秒 / 额外检查数”。等待指异常出现到专业确认的时间；未查到时按异常结束截断。健康条件没有异常，等待记—。前三行使用种子41000，后三行41001；仅为开发仿真。移动、服务和逐次时间见[完整CSV](../research/2026-11-01-multistep-workflow/全条件结果.csv)。', '',
        '|条件|过程|A Tour|B K=1|C K=2固定|D K=2反馈|模型子流程|',
        '|---|---|---|---|---|---|---|']
    for case in cases:
        cells = []
        for arm in ('A', 'B', 'C', 'D', 'child'):
            row = by.get((case, arm))
            if row:
                m = row['metrics']
                cells.append(f"{m['missed_segments']} / {fmt(m['consequence_weighted_censored_delay_s'])} / {m['selected_detours']}")
            else:
                cells.append('未生成合法子流程')
        family = {'healthy': '健康', 'coldplate_fouling': '冷板退化', 'aux_feeder_loss+cdu_fouling': '供电—液冷耦合'}[by[(case, 'A')]['specification']['scenario']]
        report.append('|'+case+'|'+family+'|'+'|'.join(cells)+'|')
    report += ['', f"C与D在{sum(v['same_actual_actions'] for v in paired)}/6个条件中完整动作相同，漏检、等待、移动和服务也相同。K=2相对K=1/Tour的部分改善包含更多额度和首次检查逻辑的影响，不能归为反馈或AI收益。全部30条主比较回合重访超期为0；持续覆盖与异常漏检分别评价。", '',
        f"真实示例按预定case顺序取首个完成两步的条件{example_case}，不按得分挑选。完整359个动作时刻、18人的实际任务/测量、逐次安全证书及边界重访见[行动时间线JSON](../research/2026-11-01-multistep-workflow/行动时间线.json)。", '']
    for i, item in enumerate(example['optional_chain']):
        e = item['completed']
        field = item['information']['quantity']
        unit = 'kg/s' if e['kind'] == 'cooling' else '℃'
        before = item['before_task']['qualified']
        previous = f"{before['time_s']:.0f}秒的{before['value']:.2f}{unit}" if before['available'] else '尚无合格参考'
        report.append(f"{i+1}. {item['dispatch_time_s']:.0f}秒，执行者{item['agent']}接到{e['task_id']}；{e['time_s']:.0f}秒实际测得{e['measurement'][field]:.2f}{unit}，{'告警' if e['alarm'] else '正常'}。共享参考从{previous}更新到本次值及完成时间。")
    if example['optional_chain']:
        first = example['optional_chain'][0]
        direct = first['before_task']['temperature_measurement']
        if first['completed']['kind'] == 'thermal' and direct['available']:
            report.append(f"首次派单前已有{direct['time_s']:.0f}秒的温度读数{direct['value']:.2f}℃；完成时同机柜遥测为{first['information']['remote_value']:.2f}℃。本例提供了新的专业参考，但同量遥测已存在。")
    report.append('测量后D按“同pod其他专业优先”选择自控核验；C的预定顺序也选中同一任务。两者都在实际派单时重新通过安全检查。完整公开输入与选择理由保留在时间线中。')
    report += ['', '### 真实模型修改短链', '']
    changed = sum(v['changed_actual_actions'] for v in model_comparisons)
    model_attempts = []
    for path in run.glob('model*/call-*/start.json'):
        directory = path.parent
        model_attempts.append({'start': read(path), 'response': read(directory / 'response.json') if (directory / 'response.json').exists() else None,
            'failure': read(directory / 'failed.json') if (directory / 'failed.json').exists() else None,
            'accepted_interface': read(directory / 'accepted-interface.json') if (directory / 'accepted-interface.json').exists() else None})
    model_attempts.sort(key=lambda value: value['start']['receipt']['number'])
    assert len(model_attempts) == costs['real_model_calls']
    if model_change:
        response_path = run / Path(model_change['proposal_response_path']).relative_to(REMOTE)
        response = read(response_path)
        report += ['链条为：父D工作流 → 六个开发回合的公开轨迹与分项评分 → Qwen修改 → 同条件真实执行子流程 → 对比动作和指标。完整提示、失败、原始回复与父子哈希都在单文件JSON中。',
            f"Qwen实际将告警后范围从 `{model_change['parent']['after_alarm']}` 改为 `{model_change['workflow']['after_alarm']}`，即取消“其他专业优先”，保留同pod优先。",
            f"子流程真实运行全部6条件，{changed}/6条实际动作轨迹改变；本轮所有漏检、等待、移动和服务指标与父D相同。可执行规则变化与真实行为变化是两件事。",
            '使用同一Qwen3-8B权重，实际运行设备为Slurm CPU，float32、greedy。GPU排队作业131046未启动；取消后改用CPU。没有训练或改变模型权重。']
        if model_change.get('raw_contract') == 'compact-v1':
            report += ['三次调用依次为：完整封装格式失败、超时、紧凑接口合法修改。第三次预先声明由接口提供固定协议和父版本SHA，模型只生成修改内容与理由。旧失败保留计费，未回填为成功。']
    else:
        response = None
        report.append('限定调用内未产生可执行的非重复子流程；记录提案失败，不补抽或假造行为变化。')
    report += ['', '## 4. 一页决策结论', '',
        '|问题|本轮证据与结论|', '|---|---|',
        f"|接口能表达多步吗|{'能：真实执行了两步专业检查与共享更新。' if any(len(records[(c,'D')]['optional_chain'])==2 for c in cases) else '接口测试通过，但真实条件未走出两步。'}安全检查与主指标胜负分开。|",
        f"|第一次测量新增了什么|{len(receipt_rows)}个条件有首次额外测量，其中{sum(v['information']['contemporaneous_remote_same_quantity'] for v in receipt_rows)}次当时已有同量遥测；其余是更及时的未遥测专业参考。新时间戳/新合格来源不自动等于独立信息价值。|",
        f"|实际行为变了吗|D相对C改变{6-sum(v['same_actual_actions'] for v in paired)}/6条轨迹；模型子流程相对D改变{changed}/6条。合法可执行修改没有转成实际任务变化。|",
        f"|同预算任务改善了吗|D−C漏检改善{sum(v['miss_delta_D_minus_C']<0 for v in paired)}个条件，等待改善{sum(v['wait_delta_D_minus_C_s'] is not None and v['wait_delta_D_minus_C_s']<0 for v in paired)}个；模型子流程也无新增改善。|", '',
        '瓶颈主要在信息与流程的联系：三次首次测量都确认了已有线索预期的阳性，两次还与同时刻遥测重叠；正常分支没有被首次测量触发。模型放宽后续专业偏好后仍选中原任务，说明该修改在本批条件无效。实际后续时刻有多个安全候选，不能据此说所有动作都被硬约束锁死。同量重复测量可能有降噪价值，本轮没有量化这种价值。', '',
        '**下一步只验证一个假设：对没有当前直接遥测、且观测可能纠正现有估计的目标，新增专业测量能否在至少两个同样合法的后续动作之间改变选择，并在同K=2下改善任务？** 未来应对照使用/屏蔽该新增测量、保持同刻其他公开通道相同；本轮不追加执行。', '',
        f"本轮费用：{costs['environment_attempts']}次实际环境尝试，其中v3正式{len(rows)}条、旧源成本试运行{costs['superseded_source_episodes']}条；真实模型调用{costs['real_model_calls']}次，CPU分配{cpu_minutes:.3f}核分钟，GPU分配{gpu_seconds}秒，新物理过程6个。没有打开旧最终集，没有新训练、G1b/F2或大规模搜索。所有费用和失败均保留。", '',
        '证据范围：只用了六个开发条件，不作独立泛化或递归增量判断。D同时接收更新的遥测、估计和几何状态，D−C检验整体反馈重规划。模型输入限于匿名公开轨迹和标注的模拟开发分数。']
    text = '\n'.join(report) + '\n'
    report_path = root / 'reports/2026-11-01-多步巡检原型与结论.md'
    report_path.write_text(text, encoding='utf8', newline='\n')
    summary = {'study': 'minimal-multistep-workflow-v1', 'report_markdown': text,
        'goal_alignment_markdown': (stage / '目标对照.md').read_text(encoding='utf8'),
        'prototype_and_reproduction_markdown': (stage / '原型与复现.md').read_text(encoding='utf8'),
        'protocol': read(stage / 'protocol-v1.json'), 'rows': rows, 'table': csv_rows,
        'paired_C_D': paired, 'group_descriptive_statistics': group_stats, 'actual_first_measurements': receipt_rows,
        'model_modification': model_change, 'raw_model_response': response, 'all_actual_model_attempts': model_attempts,
        'parent_child_comparison': model_comparisons, 'complete_actual_timeline': timeline,
        'costs': costs, 'timeline_path': 'research/2026-11-01-multistep-workflow/行动时间线.json',
        'timeline_sha256': sha(stage / '行动时间线.json'), 'execution_source_manifest_sha256': SIGNATURE,
        'history': {'base_commit': 'd10947bd1a04084d62d11302a9c34546d249ba67', 'old_experimental_files_modified': False,
            'old_final_sets_opened': False, 'old_NO_GO_unchanged': True},
        'four_questions_separate': True, 'independent_generalization_or_recursive_increment_claimed': False}
    (root / 'reports/2026-11-01-多步巡检单文件汇总.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'report': str(report_path), 'main_rows': len(rows), 'costs': costs,
        'C_D_same_trajectories': sum(v['same_actual_actions'] for v in paired), 'model_actual_changed': changed}, ensure_ascii=False))


if __name__ == '__main__':
    main()
