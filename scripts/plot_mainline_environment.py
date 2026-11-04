"""Render conserved leakage and work timing from one saved engineering run."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if (ROOT / '.work/paper-writing-deps').is_dir():
    sys.path.insert(0, str(ROOT / '.work/paper-writing-deps'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties, fontManager


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run_directory', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    folder = args.run_directory.resolve()
    outputs = [args.output.with_suffix(s) for s in ('.png', '.svg', '.json')]
    if any(p.exists() for p in outputs):
        raise ValueError('Use fresh figure paths')
    manifest = json.loads((folder / 'run.json').read_text(encoding='utf-8'))
    if (manifest['research_trials'] != 0 or manifest['state_visibility'] != 'PRIVATE_PLANT_EVALUATOR_ONLY'
            or manifest['code_identity']['implementation_has_changes']):
        raise ValueError('Use a committed-source private engineering fixture')
    for name, record in manifest['artifacts'].items():
        if sha(folder / name) != record['sha256']:
            raise ValueError('Input artifact mismatch: ' + name)
    rows = [json.loads(x) for x in (folder / 'private-state.jsonl').read_text(encoding='utf-8').splitlines()]
    balances = [json.loads(x) for x in (folder / 'balances.jsonl').read_text(encoding='utf-8').splitlines()]
    scenario = json.loads((folder / 'scenario.json').read_text(encoding='utf-8'))
    p = {record['id']: record['value'] for record in scenario['parameters']}
    times = [row['time_s'] for row in rows]
    if times != [balances[0]['start_s']] + [b['end_s'] for b in balances]:
        raise ValueError('State and interval time axes do not align')
    if any(b['floor_water_inlet_mass_kg'] != 0 for b in balances):
        raise ValueError('This figure is specifically for hot leakage without nuisance inflow')
    jobs = [j for j in manifest['work_records'] if j['status'] == 'aborted' and j['reason'] == 'access_changed']
    if len(jobs) != 1:
        raise ValueError('Use the single aborted-work engineering fixture')
    stop = jobs[0]['finished_at_s']

    def cumulative(key):
        return [0.0] + [math.fsum(b[key] for b in balances[:i]) for i in range(1, len(balances) + 1)]

    def values(domain, key):
        return [row['domains'][domain][key] for row in rows]

    leaked, drained = cumulative('internal_hot_leaked_mass_kg'), cumulative('floor_water_drained_mass_kg')
    floor = values('space_access', 'floor_water_mass_kg')
    if max(abs(a - (b - floor[0]) - c) for a, b, c in zip(leaked, floor, drained)) > 1e-8:
        raise ValueError('Displayed water masses do not reconcile')
    work = cumulative('worker_work_person_s')
    if not math.isclose(work[-1], manifest['summary']['worker_work_person_s'], abs_tol=1e-10):
        raise ValueError('Displayed work account does not reconcile')
    font = Path('C:/Windows/Fonts/msyh.ttc')
    if font.exists():
        fontManager.addfont(str(font))
        plt.rcParams['font.family'] = FontProperties(fname=str(font)).get_name()
    plt.rcParams.update({'axes.unicode_minus': False, 'svg.fonttype': 'none',
                         'svg.hashsalt': 'aegisdc-engineering-environment-v1', 'font.size': 11,
                         'axes.titlesize': 13, 'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.grid': True, 'grid.alpha': .16})
    colors = ['#196b78', '#ae6a25', '#73558f']
    styles = ['-', '--', '-.']
    fig, axes = plt.subplots(2, 2, figsize=(14, 9), sharex=True)
    fig.subplots_adjust(top=.84, bottom=.16, hspace=.37, wspace=.23)
    for i, (data, label) in enumerate(((leaked, '累计从内循环漏出'), (floor, '地面积水库存'), (drained, '累计排出'))):
        axes[0, 0].plot(times, data, color=colors[i], ls=styles[i], lw=1.7, label=label)
    axes[0, 0].axhline(p['access_block_mass'], color='#66717a', ls=':', lw=1)
    axes[0, 0].set(title='水量有来处，也有去向', ylabel='kg', ylim=(0, max(leaked) * 1.12))
    axes[0, 0].legend(fontsize=9, loc='upper left')
    axes[0, 0].annotate(f'{stop:.3f} s：作业中止', (stop, p['access_block_mass']),
                        xytext=(.57, .40), textcoords='axes fraction', fontsize=10,
                        arrowprops={'arrowstyle': '->', 'color': '#66717a'})
    retained = values('space_access', 'floor_water_sensible_energy_J')
    exported = cumulative('floor_drain_energy_J')
    incoming = cumulative('internal_hot_leak_energy_J')
    if max(abs(a - (b - retained[0]) - c) for a, b, c in zip(incoming, retained, exported)) > .01:
        raise ValueError('Displayed sensible-energy transfer does not reconcile')
    for i, (data, label) in enumerate(((incoming, '随漏液移入'), (retained, '留在积水中'), (exported, '随排水移出'))):
        axes[0, 1].plot(times, [x / 1e6 for x in data], color=colors[i], ls=styles[i], lw=1.7, label=label)
    axes[0, 1].set(title='显热转移与排水出口', ylabel='MJ', ylim=(0, max(incoming) * 1.12e-6))
    axes[0, 1].legend(fontsize=9, loc='upper left')
    axes[1, 0].plot(times, work, color=colors[0], lw=1.7)
    axes[1, 0].set(title='已投入工时不会因中止而归零', ylabel='累计作业 / 人·s', ylim=(0, work[-1] * 1.2))
    axes[1, 0].text(.05, .85, f'计划 {jobs[0]["work_duration_s"]:g} s；实际 {work[-1]:.3f} 人·s', transform=axes[1, 0].transAxes)
    axes[1, 1].step(times, values('it_service', 'demand'), where='post', color=colors[1], ls='--',
                    marker='o', markerfacecolor='white', markevery=max(1, len(rows) // 4), label='外生需求')
    axes[1, 1].step(times, values('it_service', 'delivered'), where='post', color=colors[0], lw=1.7, label='实际交付')
    axes[1, 1].set(title='本例服务仍持续交付', ylabel='归一服务单位', ylim=(-.04, 1.16))
    axes[1, 1].text(.05, .20, f'累计服务缺额 {manifest["summary"]["service_deficit_time_s"]:g} s', transform=axes[1, 1].transAxes)
    axes[1, 1].legend(fontsize=9, loc='center right')
    for ax in axes.flat:
        ax.set_xlim(times[0], times[-1])
        ax.axvline(stop, color='#66717a', ls=':', lw=.9)
    for ax in axes[-1]:
        ax.set_xlabel('模拟时间 / s')
    fig.suptitle('预设热水泄漏下的积水、显热与作业中止', fontsize=16, fontweight='bold', y=.95)
    fig.text(.5, .89, '同一八域合成设施的工程响应；中止作业不等于修复泄漏', ha='center', color='#46545c')
    fig.text(.075, .06, f'预设漏率 {p["internal_hot_leak_mass_flow"]:g} kg/s，排水 {p["drainage_mass_flow"]:g} kg/s，'
             f'积水阈值 {p["access_block_mass"]:g} kg；不模拟疏散。\n'
             f'原件源码 {manifest["code_identity"]["git_commit"][:8]}；未作现场标定或方法效果对照。', fontsize=10, color='#46545c')
    outputs[0].parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outputs[0], dpi=160)
    fig.savefig(outputs[1], metadata={'Date': None})
    plt.close(fig)
    receipt = {'schema': 'aegisdc-engineering-response-figure-v1', 'classification': 'ENGINEERING_FIXTURE_ONLY',
               'input_run': str(folder.relative_to(ROOT)).replace('\\', '/'),
               'input_manifest_sha256': sha(folder / 'run.json'),
               'input_artifacts': {name: sha(folder / name) for name in manifest['artifacts']},
               'original_execution_identity': manifest['code_identity'], 'plot_script_sha256': sha(Path(__file__)),
               'matplotlib': matplotlib.__version__, 'artifacts': {p.name: sha(p) for p in outputs[:2]},
               'work_aborted_at_s': stop, 'leaked_mass_kg': leaked[-1], 'floor_mass_kg': floor[-1],
               'drained_mass_kg': drained[-1], 'work_person_s': work[-1],
               'service_deficit_s': manifest['summary']['service_deficit_time_s'], 'research_gain': 'NOT_ESTABLISHED'}
    outputs[2].write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'figure': str(outputs[0]), 'input_and_displayed_accounts': 'PASS', 'aborted_at_s': stop}, ensure_ascii=False))


if __name__ == '__main__':
    main()
