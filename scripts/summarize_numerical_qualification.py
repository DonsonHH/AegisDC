"""Read all eleven original cases with the revised matcher; never simulate.

Five originally passing fixtures retain their distinct .025/.02/.01 ladder;
six refined fixtures use the additive .01/.005/.0025 ladder. No six-case flag
is promoted into an eleven-case result without this explicit fresh readback.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

from numerical_engineering_checks import read_archive
from numerical_alignment_v3 import epoch_compare
from numerical_refinement_checks import inspect_refinement_run
from verify_reserve_delivery import file_sha, git_blob_sha, safe_path


def summary(root):
    v1 = root / 'evidence/mainline/engineering/12-numerical/capture-04'
    v2 = root / 'evidence/mainline/engineering/12-numerical/refinement-01'
    v3 = root / 'evidence/mainline/engineering/12-numerical/resolution-v3-01'
    original = json.loads((v1 / 'runbook-copy.json').read_text(encoding='utf-8'))
    refinement = json.loads((v2 / 'protocol-copy.json').read_text(encoding='utf-8'))
    old_receipt = json.loads((v1 / 'receipt.json').read_text(encoding='utf-8'))
    new_receipt = json.loads((v2 / 'receipt.json').read_text(encoding='utf-8'))
    resolution = json.loads((v3 / 'protocol-copy.json').read_text(encoding='utf-8'))
    resolution_receipt = json.loads((v3 / 'receipt.json').read_text(encoding='utf-8'))
    if any(receipt['engineering_capture'] != 'PASS' for receipt in (old_receipt,new_receipt,resolution_receipt)):
        raise ValueError('Both actual engineering captures must have completed')
    if any(receipt['runtime_sources'] != old_receipt['runtime_sources'] for receipt in (new_receipt,resolution_receipt)):
        raise ValueError('Cannot aggregate different physical runtime bytes')
    old_index = json.loads((v1 / 'runs-index.json').read_text(encoding='utf-8'))
    new_index = json.loads((v2 / 'runs-index.json').read_text(encoding='utf-8'))
    resolution_index = json.loads((v3 / 'runs-index.json').read_text(encoding='utf-8'))
    refined_names = {item['id'] for item in refinement['cases']}
    resolution_names = {item['id'] for item in resolution['cases']}
    all_100=json.loads((root/'evidence/mainline/engineering/12-numerical/reanalysis-v3-01/assessment.json').read_text(encoding='utf-8'))
    all_100_receipt=json.loads((root/'evidence/mainline/engineering/12-numerical/reanalysis-v3-01/receipt.json').read_text(encoding='utf-8'))
    all_original_inputs={name:identity for name,identity in all_100_receipt['original_inputs'].items() if name.endswith('.zip')}
    for name in resolution_names:
        record=resolution_index[name]['0.00125']
        all_original_inputs[record['original_path']]=record['archive_sha256']
    cases, inputs, runtime_commits = {}, {}, set()
    for item in original['cases']:
        name = item['id']
        refined = name in refined_names
        candidate, middle, fine = (.01,.0025,.00125) if name in resolution_names else ((.01,.005,.0025) if refined else (.025,.02,.01))
        analyses, originals = {}, []
        for h in (candidate, middle, fine):
            if name in resolution_names:
                record=resolution_index[name][str(h)]
                path=safe_path(root,record['original_path'])
            else:
                record = new_index[name][str(h)] if refined else old_index[name][str(h)]
                folder = v2 if refined and record['archive_root'] == 'refinement' else v1
                path = safe_path(folder, record['archive'])
            identity = file_sha(path)
            if identity != record['archive_sha256']:
                raise ValueError('Input original differs from committed capture index')
            manifest, scenario, trace, balances = read_archive(path)
            if manifest['code_identity']['files'] != old_receipt['runtime_sources']:
                raise ValueError('Actual runtime changed in summary input')
            analyses[h] = inspect_refinement_run(item, manifest, scenario, trace, balances)
            relative = path.relative_to(root).as_posix()
            inputs[relative] = identity
            originals.append(dict(path=relative, sha256=identity,
                runtime_execution_commit=manifest['code_identity']['git_commit'],
                scenario_sha256=manifest['scenario_sha256'], maximum_step_s=h))
            runtime_commits.add(manifest['code_identity']['git_commit'])
        comparison = epoch_compare(analyses[candidate], analyses[fine], original['limits'])
        reference_check = epoch_compare(analyses[middle], analyses[fine], original['limits'], factor=.25)
        analytic = name != 'isolated-room' or analyses[candidate]['metrics']['analytic_max_temperature_error_K'] <= item['qualified_analytic_absolute_error_K']
        cases[name] = dict(candidate_maximum_step_s=candidate, reference_refinement_steps_s=[middle, fine],
            original_qualified_candidate_step_s=candidate,chosen_operating_step_s=.01,
            operating_step_evidence=('Independent .01 candidate with separately finer reference ladder' if refined
                else 'Operating .01 equals this original ladder fine reference; its self-comparison zero is not an absolute true-error or newly finer-reference claim.'),
            candidate_comparison=comparison, reference_self_check=reference_check,
            ladder='V3_ADDITIONAL_RESOLUTION' if name in resolution_names else ('V2_FINE_ORIGINALS_RECHECKED_WITH_V3' if refined else 'V1_ORIGINALS_RECHECKED_WITH_V3'),
            analytic_gate=analytic,
            analytic_max_error_K=analyses[candidate]['metrics'].get('analytic_max_temperature_error_K'),
            qualified_for_declared_fixture=bool(comparison['within_predeclared_limits'] and reference_check['within_predeclared_limits'] and analytic),
            scope='DECLARED_FULL_V6_PARAMETER_AND_EVENT_POINT_ONLY', duration_s=item['duration_s'],
            original_inputs=originals, declared_condition=item,
            candidate_observed_ranges=analyses[candidate]['observed_ranges'],
            candidate_observed_quality_range=analyses[candidate]['observed_quality_range'],
            candidate_absolute_integrals=analyses[candidate]['metrics'],
            candidate_literal_checkpoint_matches=analyses[candidate]['literal_checkpoint_matches'])
    return dict(schema='aegisdc-eleven-case-numerical-qualification-summary-v1',
        analysis_method='FIXED_PAIRED_EPOCH_WITH_CLOSED_INTERVAL_AMPLITUDE_GUARD_V3',
        metric_semantics='Event-side anchor / phase-consistent diagnostic, with every closed-window amplitude retained. Not a conservative bound on same-clock causal raw or an unsampled true trajectory. Causal raw maxima and actual event-time discrepancies are separately retained.',
        cases=cases, full_case_count=len(cases),
        all_eleven_declared_fixtures_qualified=all(row['qualified_for_declared_fixture'] for row in cases.values()),
        original_v1_numeric_gate_preserved=old_receipt['numerical_gate'],
        additive_six_case_gate=new_receipt['numerical_gate'],
        additional_resolution_gate=resolution_receipt['numerical_gate'],
        recommended_operational_maximum_step_s=.01,
        recommendation_scope='Two resolution fixtures use .01/.0025-.00125; four other refined fixtures use .01/.005-.0025. Five original fixtures retain independent .025/.02-.01 ladders. All102 originals are separately rechecked; not a proof for arbitrary steps or new parameter/event combinations.',
        limits=original['limits'], reference_fraction_of_limits=.25,
        runtime_sources=old_receipt['runtime_sources'],selected_ladder_runtime_execution_commits=sorted(runtime_commits),
        actual_runtime_execution_commits=sorted(set(all_100['actual_runtime_commits'])|{resolution_receipt['execution_commit']}),
        all_original_archives=all_100['original_archives']+resolution_receipt['new_physical_runs'],
        all_original_state_points=all_100['state_points']+sum(resolution_index[name]['0.00125']['analysis']['state_points'] for name in resolution_names),
        all_originals_readback_receipt_sha256=file_sha(root/'evidence/mainline/engineering/12-numerical/reanalysis-v3-01/receipt.json'),
        all_original_inputs=all_original_inputs,
        source_capture_receipts={(folder/'receipt.json').relative_to(root).as_posix():file_sha(folder/'receipt.json') for folder in (v1,v2,v3)},
        original_inputs=inputs, authoring_tool_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        authoring_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        physics_rerun=False, full_suite_rerun=False, field_calibration='PENDING',
        research_trials=0, model_calls=0, training_calls=0, research_gain='NOT_ESTABLISHED')


def markdown(result):
    status='PASS' if result['all_eleven_declared_fixtures_qualified'] else 'NO-GO'
    lines = ['# 十一案例数值资格入口：'+status+'（仅声明工况）', '',
        '本页只汇总同一完整 V6 的已声明工程工况。旧 v1 NO-GO、legacy forward-peek、因果 raw 和新 epoch 视图分别保留。', '',
        '|案例|原见证候选 s|选定运行步长 s|参考自检 s|候选阶段/raw温差 K|候选阶段/raw压差 Pa|候选阶段/raw热流 kW|参考阶段热流 kW / 6.25|实际切换误差 s|资格|',
        '|---|---:|---:|---|---:|---:|---:|---:|---:|---|']
    for name, row in result['cases'].items():
        candidate, checked = row['candidate_comparison'], row['reference_self_check']
        a, b = candidate['maximum_absolute_series_error'], checked['maximum_absolute_series_error']
        temperature = max(value for key,value in a.items() if key.endswith('_K'))
        heat = max(value for key,value in a.items() if key.endswith('_W')) / 1000
        ref_heat = max(value for key,value in b.items() if key.endswith('_W')) / 1000
        raw=candidate['raw_causal']['maximum_absolute_series_error']
        raw_temperature=max(value for key,value in raw.items() if key.endswith('_K'))
        raw_heat=max(value for key,value in raw.items() if key.endswith('_W'))/1000
        switch = candidate['maximum_switch_time_error_s']
        lines.append(f"|{name}|{row['candidate_maximum_step_s']}|{row['chosen_operating_step_s']}|{row['reference_refinement_steps_s'][0]} / {row['reference_refinement_steps_s'][1]}|{temperature:.6g} / {raw_temperature:.6g}|{a['pressure_Pa']:.6g} / {raw['pressure_Pa']:.6g}|{heat:.6g} / {raw_heat:.6g}|{ref_heat:.6g}|{switch if switch is None else format(switch,'.6g')}|{'PASS' if row['qualified_for_declared_fixture'] else 'NOT_QUALIFIED'}|")
    lines += ['', '所有误差界和 25% 参考自检规则未放宽。实际服务缺额、未服务单位秒、人员人秒、工具秒和供能持续时间的原值／误差分量在 summary.json 中逐量纲保存。', '',
        '数值门槛施加于“事件侧锚点／阶段一致差异”：温度 0.05 K、压力 1000 Pa、热流 25 kW，参考自检为各自界的 25%。上表并列因果同钟表 raw 最大值和实际事件时差；阶段界不是所有 raw 差异或未保存真实连续轨迹的保守包络，也不是一般 retiming 距离保证。', '',
        '统一建议最大积分步长为 0.01 s，适用范围是本表的参数／事件工况与已测步长：两案追加 0.0025／0.00125 参考，四案沿用 0.005／0.0025，其他五案保留 0.025 候选和独立 0.02／0.01 阶梯；不用参考对自身的零差异冒充独立验证。新参数、扰动组合或更长工况必须另做相应检查。', '',
        '其中五个原通过工况的选定 0.01 s 恰是旧 fine reference，没有因此新增 0.01 对更细参考的验证；其自比较零差异不表示绝对真实误差为零。表中资格见证仍是原候选 0.025 对 0.01 及 0.02／0.01 参考自检。有限阶梯见证不等于整个连续步长／参数域的保证。', '',
        '现场校准 pending，注册效果试验／训练／LLM 调用均为 0。此页不完成 M2 根验收或整个研究目标。', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--verify',type=Path,help='Read-only comparison with a committed summary.json')
    parser.add_argument('--plot-dependencies',type=Path)
    args=parser.parse_args();root=args.root.resolve();result=summary(root)
    if args.verify:
        expected=json.loads(args.verify.read_text(encoding='utf-8'))
        if git_blob_sha(root,expected['authoring_commit'],'scripts/summarize_numerical_qualification.py') != expected['authoring_tool_sha256']:
            raise ValueError('Summary authoring tool differs from its recorded Git revision')
        # The verifier runs in a delivery checkout; the original authoring
        # revision remains separately pinned, not rewritten to the checkout tip.
        result['authoring_commit']=expected['authoring_commit']
        if result != expected: raise ValueError('Eleven-case summary does not reproduce')
        with args.output.open('x',encoding='utf-8',newline='\n') as stream:
            json.dump(dict(status='PASS',cases=len(result['cases']),all_eleven_declared_fixtures_qualified=result['all_eleven_declared_fixtures_qualified'],physics_rerun=False,full_suite_rerun=False),stream,indent=2);stream.write('\n')
    else:
        planned=['declaration.json','summary.json','README.md','qualification-summary.png','qualification-summary.svg','figure-receipt.json']
        tools=['scripts/'+name for name in ('summarize_numerical_qualification.py','verify_numerical_summary.py','plot_numerical_qualification_final.py','numerical_alignment_v3.py','numerical_refinement_checks.py','numerical_engineering_checks.py','coupled_engineering_checks.py','verify_reserve_delivery.py')]
        extra=['evidence/mainline/engineering/12-numerical/reanalysis-v3-01/'+name for name in ('receipt.json','assessment.json')]
        extra += ['evidence/mainline/engineering/12-numerical/'+name for name in ('v1-fresh-proof-01.json','v2-fresh-proof-01.json','v3-fresh-proof-01.json')]
        pinned_tools={name:file_sha(root/name) for name in tools}
        frozen_inputs=dict(result['all_original_inputs'],**result['source_capture_receipts'])
        frozen_inputs.update({name:file_sha(root/name) for name in extra})
        for name,identity in {**pinned_tools,**frozen_inputs}.items():
            if git_blob_sha(root,result['authoring_commit'],name)!=identity:raise ValueError('Freeze summary tools/input first: '+name)
        args.output.mkdir(parents=True,exist_ok=False)
        with (args.output/'declaration.json').open('x',encoding='utf-8',newline='\n') as stream:
            json.dump(dict(declared_artifacts=planned,declared_tools=tools,declared_inputs=sorted(frozen_inputs),runtime_cache_policy='Exclude __pycache__/.pyc/.pyo by type BEFORE hashing',physics_rerun=False,full_suite_rerun=False),stream,indent=2);stream.write('\n')
        with (args.output/'summary.json').open('x',encoding='utf-8',newline='\n') as stream:
            json.dump(result,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
        (args.output/'README.md').write_text(markdown(result),encoding='utf-8',newline='\n')
        import numpy
        if numpy.__version__!='2.3.5':raise ValueError('Use the project-pinned NumPy')
        if args.plot_dependencies:sys.path.insert(0,str(args.plot_dependencies.resolve()))
        from plot_numerical_qualification_final import render
        render(args.output)
        with (args.output/'receipt.json').open('x',encoding='utf-8',newline='\n') as stream:
            json.dump(dict(schema='aegisdc-eleven-case-final-entry-delivery-v1',authoring_commit=result['authoring_commit'],delivery_gate='PENDING_COMMIT_AND_FRESH_CHECKOUT',pinned_tools=pinned_tools,execution_inputs=frozen_inputs,artifacts={name:file_sha(args.output/name) for name in planned},runtime_sources=result['runtime_sources'],all_eleven_declared_fixtures_qualified=result['all_eleven_declared_fixtures_qualified'],physical_runs=0,full_regression_runs=0,research_trials=0,model_calls=0,training_calls=0),stream,indent=2);stream.write('\n')
    print(json.dumps(dict(cases=len(result['cases']),qualified=result['all_eleven_declared_fixtures_qualified'],physics_rerun=False)))
