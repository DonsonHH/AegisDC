"""Plot a saved engineering response; all data retain their execution identity."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / '.work/paper-writing-deps'
if DEPS.is_dir():
    sys.path.insert(0, str(DEPS))

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
    parser.add_argument('--title', required=True)
    args = parser.parse_args()
    folder = args.run_directory.resolve()
    outputs = [args.output.with_suffix(suffix) for suffix in ('.png', '.svg', '.json')]
    if any(path.exists() for path in outputs):
        raise ValueError('Use new engineering figure paths')
    manifest = json.loads((folder / 'run.json').read_text(encoding='utf-8'))
    if (manifest['research_trials'] != 0
            or manifest['state_visibility'] != 'PRIVATE_PLANT_EVALUATOR_ONLY'
            or manifest['code_identity']['implementation_has_changes']):
        raise ValueError('A committed-source, private engineering run is required')
    for name, record in manifest['artifacts'].items():
        if sha(folder / name) != record['sha256']:
            raise ValueError('Saved input SHA-256 mismatch: ' + name)
    rows = [json.loads(line) for line in (folder / 'private-state.jsonl').read_text(encoding='utf-8').splitlines()]
    balances = [json.loads(line) for line in (folder / 'balances.jsonl').read_text(encoding='utf-8').splitlines()]
    scenario = json.loads((folder / 'scenario.json').read_text(encoding='utf-8'))
    parameters = {item['id']: item['value'] for item in scenario['parameters']}
    times = [row['time_s'] for row in rows]
    if not all(a < b for a, b in zip(times, times[1:])):
        raise ValueError('Saved state times must increase')
    if not math.isclose(math.fsum(row['service_deficit_time_s'] for row in balances),
                        manifest['summary']['service_deficit_time_s'], abs_tol=1e-10):
        raise ValueError('Saved service account does not reconcile')
    font = Path('C:/Windows/Fonts/msyh.ttc')
    if font.exists():
        fontManager.addfont(str(font))
        plt.rcParams['font.family'] = FontProperties(fname=str(font)).get_name()
    plt.rcParams.update({'axes.unicode_minus': False, 'svg.fonttype': 'none',
                         'font.size': 11, 'axes.titlesize': 12,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.grid': True, 'grid.alpha': .16})
    colors = ['#196b78', '#ae6a25', '#73558f', '#677a48']
    styles = ['-', '--', '-.', ':']
    fig, axes = plt.subplots(3, 2, figsize=(14, 11), sharex=True)
    fig.subplots_adjust(top=.87, bottom=.12, hspace=.40, wspace=.22)

    def series(domain, *keys):
        values = []
        for row in rows:
            value = row['domains'][domain]
            for key in keys:
                value = value[key]
            values.append(value)
        return values

    def draw(ax, values, label, index=0, scale=1, step=False):
        function = ax.step if step else ax.plot
        options = {'where': 'post'} if step else {}
        function(times, [value * scale for value in values], label=label,
                 color=colors[index], ls=styles[index], lw=1.7, **options)

    boundary = manifest['inputs']['boundary_events']
    changed = {event['parameter_id'] for event in boundary}
    if changed not in ({'internal_valve_opening'}, {'plate_hx_conductance'}):
        raise ValueError('This authoring plot supports internal-valve or plate-HX input only')
    parameter = 'internal_valve_opening' if 'internal_valve_opening' in changed else 'plate_hx_conductance'
    setting = []
    for time_s in times:
        value = parameters[parameter]
        for event in boundary:
            if event['parameter_id'] == parameter and event['time_s'] <= time_s:
                value = event['value']
        setting.append(value)
    ax = axes[0, 0]
    is_valve = parameter == 'internal_valve_opening'
    draw(ax, setting, '内循环阀开度' if is_valve else '板换 UA', scale=100 if is_valve else .001, step=True)
    ax.set(title='已声明的工程输入', ylabel='开度 / %' if is_valve else 'UA / (kW/K)', ylim=(0, max(setting) * (110 if is_valve else .0011)))
    ax = axes[0, 1]
    for index, pump, label in ((0, 'internal_pump', '内循环'), (1, 'lake_pump', '湖水侧')):
        draw(ax, series('facility_cooling', pump, 'volume_flow_m3_s'), label, index, scale=1000, step=True)
    maximum_flow = max(series('facility_cooling', pump, 'volume_flow_m3_s')[i]
                       for pump in ('internal_pump', 'lake_pump') for i in range(len(rows)))
    ax.set(title='实际供电约束下的流量', ylabel='L/s', ylim=(0, max(maximum_flow * 1100, 1)))
    ax.legend(fontsize=9, loc='upper right')
    ax = axes[1, 0]
    for index, domain, key, label in ((0, 'equipment_environment', 'solid_coolant_heat_W', '固体→冷媒'),
                                      (1, 'facility_cooling', 'condenser_heat_W', '冷媒→内循环'),
                                      (2, 'facility_cooling', 'plate_hx_heat_W', '内循环→湖水')):
        draw(ax, series(domain, key), label, index, scale=1e-6, step=True)
    ax.set(title='分开记录的热传递', ylabel='MW')
    ax.legend(fontsize=9)
    ax = axes[1, 1]
    for index, domain, keys, label in ((0, 'equipment_environment', ('solid_temperature_K',), 'IT 固体'),
                                       (1, 'equipment_environment', ('refrigerant', 'temperature_K'), '参考冷媒'),
                                       (2, 'facility_cooling', ('hot_temperature_K',), '热回水'),
                                       (3, 'facility_cooling', ('cold_temperature_K',), '冷供水')):
        draw(ax, [value - 273.15 for value in series(domain, *keys)], label, index)
    ax.set(title='各自储热状态的温度', ylabel='°C')
    ax.legend(fontsize=9, ncol=2)
    ax = axes[2, 0]
    draw(ax, series('it_service', 'demand'), '外生需求', 1, step=True)
    draw(ax, series('it_service', 'delivered'), '实际交付', 0, step=True)
    ax.set(title='自动保护后的服务账', ylabel='归一服务单位', ylim=(-.04, 1.14))
    ax.legend(fontsize=9)
    ax = axes[2, 1]
    cumulative = [0.0]
    for row in balances:
        cumulative.append(cumulative[-1] + row['service_deficit_time_s'])
    ax.plot([balances[0]['start_s']] + [row['end_s'] for row in balances], cumulative,
            color=colors[0], lw=1.7)
    ax.set(title='未交付需求继续累计', ylabel='累计归一缺额时间 / s', ylim=(0, max(cumulative[-1] * 1.15, .1)))
    ax.text(.03, .90, f"累计 {cumulative[-1]:g} s", transform=ax.transAxes, va='top')
    for ax in axes.flat:
        ax.set_xlim(times[0], times[-1])
        for event in boundary:
            ax.axvline(event['time_s'], ls=':', lw=.8, color='#65727a', alpha=.65)
    for ax in axes[-1, :]:
        ax.set_xlabel('模拟时间 / s')
    protected = [row['time_s'] for row in rows if row['domains']['control_monitoring']['protection_latched']]
    first = f'首次保护 {protected[0]:g} s；' if protected else ''
    fig.suptitle(args.title, fontsize=16, fontweight='bold', y=.96)
    fig.text(.5, .915, '同一八域合成设施的单次工程响应；虚线标出外生输入时刻', ha='center', color='#46545c')
    fig.text(.075, .052,
             f"{first}本地采样 {parameters['control_sample_time']:g} s；温度保护/复位 "
             f"{parameters['protection_temperature']:g}/{parameters['protection_reset_temperature']:g} K。\n"
             f"原件执行源码 {manifest['code_identity']['git_commit'][:8]}；未作现场标定或方法效果对照。",
             fontsize=10, va='center', color='#46545c')
    outputs[0].parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outputs[0], dpi=160)
    fig.savefig(outputs[1])
    plt.close(fig)
    receipt = {'schema': 'aegisdc-engineering-response-figure-v1',
               'classification': 'ENGINEERING_FIXTURE_ONLY',
               'input_run': str(folder.relative_to(ROOT)).replace('\\', '/'),
               'input_manifest_sha256': sha(folder / 'run.json'),
               'input_artifacts': {name: sha(folder / name) for name in manifest['artifacts']},
               'original_execution_identity': manifest['code_identity'],
               'plot_script_sha256': sha(Path(__file__)),
               'artifacts': {path.name: sha(path) for path in outputs[:2]},
               'observed_first_protection_s': protected[0] if protected else None,
               'accounted_deficit_s': cumulative[-1], 'trace_rows': len(rows),
               'research_gain': 'NOT_ESTABLISHED'}
    outputs[2].write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'figure': str(outputs[0]), 'input_hashes': 'PASS',
                      'deficit_s': cumulative[-1]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
