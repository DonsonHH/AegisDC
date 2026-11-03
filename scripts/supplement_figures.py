"""Reproducible static scientific figures from the completed study artifacts."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.work/supplement-plot-deps'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np

RUN = ROOT / 'runs/supplement-benchmark-20261103'
FOLDER = ROOT / 'paper/figures/supplement-study'
LABELS = {'nominal_tour': '名义 · Tour', 'nominal_fifo': '名义 · FIFO', 'nominal_greedy': '名义 · Greedy',
          'nominal_ppo': '名义 · PPO', 'cvae_fifo': 'CVAE · FIFO', 'cvae_greedy': 'CVAE · Greedy', 'cvae_ppo': 'CVAE · PPO'}
COLORS = {'nominal_tour': '#7b8790', 'nominal_fifo': '#147469', 'nominal_greedy': '#b27420',
          'nominal_ppo': '#b44e79', 'cvae_fifo': '#2369a5', 'cvae_greedy': '#805114', 'cvae_ppo': '#7b3153'}
SEED_COLORS = ['#2369a5', '#b27420', '#b44e79']
plt.rcParams.update({'font.family': 'Microsoft YaHei', 'font.size': 14, 'axes.labelsize': 14,
                     'axes.titlesize': 16, 'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.edgecolor': '#768895', 'axes.labelcolor': '#172d3b', 'text.color': '#172d3b',
                     'xtick.color': '#526675', 'ytick.color': '#526675', 'grid.color': '#dce4e9',
                     'svg.fonttype': 'none', 'svg.hashsalt': 'supplement-study-20261103',
                     'savefig.facecolor': 'white', 'figure.dpi': 120})


def save(figure, name, title):
    FOLDER.mkdir(parents=True, exist_ok=True)
    path = FOLDER / (name+'.svg')
    figure.savefig(path, format='svg', metadata={'Date': None, 'Title': title}, bbox_inches='tight', pad_inches=.15)
    figure.savefig(FOLDER / (name+'.png'), dpi=180, bbox_inches='tight', pad_inches=.15)
    plt.close(figure)
    root = ET.fromstring(path.read_text(encoding='utf-8'))
    root.set('data-chart', name)
    root.set('role', 'img')
    root.set('aria-label', title)
    identities = {node.attrib['id']:name+'-'+node.attrib['id'] for node in root.iter() if 'id' in node.attrib}
    for node in root.iter():
        for key, value in list(node.attrib.items()):
            if key == 'id':
                node.set(key, identities[value])
                continue
            if value.startswith('#') and value[1:] in identities:
                value = '#'+identities[value[1:]]
            for old, new in identities.items():
                value = value.replace('url(#'+old+')','url(#'+new+')')
            node.set(key, value)
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
    drawing = ET.tostring(root, encoding='unicode')
    path.write_text(drawing+'\n', encoding='utf-8', newline='\n')
    return drawing


def interval_bar(ax, methods, aggregates, key, title, unit='', zero=True):
    y = np.arange(len(methods))
    means = [aggregates[m][key]['mean'] for m in methods]
    bounds = np.asarray([aggregates[m][key]['percentile95'] for m in methods])
    errors = np.asarray([np.asarray(means)-bounds[:, 0], bounds[:, 1]-means])
    ax.barh(y, means, color=[COLORS[m] for m in methods], height=.62)
    ax.errorbar(means, y, xerr=errors, fmt='none', ecolor='#172d3b', capsize=3, linewidth=1.1)
    ax.set_yticks(y, [LABELS[m] for m in methods]); ax.invert_yaxis()
    ax.set_title(title, loc='left', pad=14)
    ax.set_xlabel(unit)
    ax.grid(axis='x', alpha=.6); ax.set_axisbelow(True)
    if zero:
        ax.set_xlim(left=0)
    ax.margins(x=.12)


def build(data,example=None):
    if example is None:
        example=json.loads((ROOT/'paper/source-data/supplement-example.json').read_text(encoding='utf-8'))
    drawings = {}
    methods, aggregates = data['method_order'], data['primary_aggregates']
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.3), layout='constrained')
    for ax, key, title, unit in zip(axes, ['confirmed_segments', 'consequence_weighted_censored_delay_s', 'weighted_normalized_age'],
                                   ['有效确认', '后果加权截尾等待', '资产加权归一年龄'], ['平均每故障条件 / 段 ↑', '秒 ↓', '无量纲 ↓']):
        interval_bar(ax, methods, aggregates, key, title, unit)
    drawings['supplement-methods'] = save(fig, 'supplement-methods', '七方法独立测试结果：12种子块、四故障条件等权，误差线为95%种子块自举区间')

    fig, axes = plt.subplots(2, 2, figsize=(13.5, 9.5), layout='constrained')
    for ax, role, label in zip(axes.flat, ['thermal', 'electrical', 'cooling', 'control'], ['热检查', '电气检查', '制冷检查', '自控检查']):
        rows = [aggregates[m]['by_role'][role] for m in methods]
        values = [r['confirmed']/r['segments'] if r['segments'] else np.nan for r in rows]
        y = np.arange(7)
        ax.barh(y, values, color=[COLORS[m] for m in methods], height=.62)
        ax.set_yticks(y, [LABELS[m] for m in methods]); ax.invert_yaxis()
        ax.set_xlim(0, 1.28); ax.set_xticks([0, .25, .5, .75, 1]); ax.xaxis.set_major_formatter(PercentFormatter(1))
        ax.set_title(label, loc='left', pad=12); ax.set_xlabel('有效确认比例（描述性汇总）')
        for i, row in enumerate(rows):
            ax.text(1.03, i, f"{row['confirmed']:g}/{row['segments']:g}", va='center', fontsize=11)
            if not row['segments']:
                ax.text(.02, i, 'NA', va='center')
        ax.grid(axis='x', alpha=.6); ax.set_axisbelow(True)
    drawings['supplement-professions'] = save(fig, 'supplement-professions', '四专业有效确认：分母为48个主要条件中的唯一专业异常段，CVAE/PPO先平均三个训练种子')

    fixed = data['fixed_stream']['aggregates']
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.7), layout='constrained')
    for ax, subset, metric, title in zip(axes, ['all', 'all', 'not_fresh'], ['rmse_c', 'weighted_rmse_c', 'weighted_rmse_c'],
                                       ['全部端点 · RMSE', '全部端点 · 加权RMSE', '盲区机柜 · 加权RMSE']):
        names = ['nominal', 'cvae']
        values = [fixed[f'{m}_{subset}_{metric}']['mean'] for m in names]
        bounds = np.asarray([fixed[f'{m}_{subset}_{metric}']['percentile95'] for m in names])
        ax.bar([0, 1], values, color=['#7b8790', '#2369a5'], width=.5)
        ax.errorbar([0, 1], values, yerr=np.asarray([np.asarray(values)-bounds[:, 0], bounds[:, 1]-values]), fmt='none', ecolor='#172d3b', capsize=4)
        ax.set_xticks([0, 1], ['名义热平衡', '残差 CVAE-U-Net']); ax.set_ylim(bottom=0)
        ax.set_title(title, loc='left', pad=12); ax.set_ylabel('平均逐回合误差 / °C ↓')
        ax.grid(axis='y', alpha=.6); ax.set_axisbelow(True)
        for i, value in enumerate(values):
            ax.annotate(f'{value:.3f}', (i, bounds[i, 1]), xytext=(0, 7), textcoords='offset points', ha='center')
        ax.margins(y=.2)
    drawings['supplement-estimation'] = save(fig, 'supplement-estimation', '同一Tour公开观测流上的估计误差：相同新鲜量测校正，95%物理种子块自举区间')

    fig, ax = plt.subplots(figsize=(10.5, 4.8), layout='constrained')
    for seed, color in zip(data['protocol']['model_seeds'], SEED_COLORS):
        history = data['training'][f'cvae-{seed}']['history']
        x = [r['epoch'] for r in history]; y = [r['development_weighted_rmse_c'] for r in history]
        ax.plot(x, y, color=color, label=f'训练种子 {seed}', linewidth=1.8)
        best = int(np.argmin(y)); ax.scatter(x[best], y[best], facecolors='white', edgecolors=color, s=58, zorder=4)
    ax.set_xlim(1, 30); ax.set_xticks([1, 5, 10, 15, 20, 25, 30]); ax.set_xlabel('训练轮次 / epoch')
    ax.set_ylabel('开发集加权 RMSE / °C'); ax.grid(alpha=.6); ax.legend(frameon=False)
    drawings['supplement-estimator-training'] = save(fig, 'supplement-estimator-training', '三个真实CVAE-U-Net训练过程，空心点为各自开发集最优checkpoint；最终测试不参与选择')

    fig, ax = plt.subplots(figsize=(10.5, 5.0), layout='constrained')
    for estimator, color, style, label in [('nominal', '#7b8790', '--', '名义估计＋PPO'), ('cvae', '#2369a5', '-', 'CVAE估计＋PPO')]:
        curves = []
        for seed in data['protocol']['model_seeds']:
            rows = data['training'][f'ppo-{estimator}-{seed}']['history']
            y = np.asarray([r['mean_public_reward'] for r in rows])
            smooth = np.convolve(y, np.ones(10)/10, mode='valid')
            ax.plot(np.arange(10, 121), smooth, color=color, alpha=.25, linewidth=.8, linestyle=style)
            curves.append(smooth)
        ax.plot(np.arange(10, 121), np.mean(curves, axis=0), color=color, linewidth=2, linestyle=style, label=label)
    ax.set_xlim(10, 120); ax.set_xticks([10, 30, 60, 90, 120]); ax.set_xlabel('完整训练回合 / episode')
    ax.set_ylabel('每步公开奖励（10回合滑动均值）'); ax.grid(alpha=.6); ax.legend(frameon=False)
    drawings['supplement-ppo-training'] = save(fig, 'supplement-ppo-training', '六个真实PPO训练过程：细线为三个训练种子，粗线为种子均值；奖励来自公开观测，非事后异常标签')

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2), layout='constrained')
    labels = [LABELS[c['first']]+' − '+LABELS[c['second']] for c in data['contrasts']]
    for ax, key, title, unit in zip(axes, ['confirmed_segments', 'weighted_normalized_age'], ['配对确认增量', '配对年龄变化'], ['段 / 故障条件 ↑', '无量纲 ↓']):
        for i, contrast in enumerate(data['contrasts']):
            value = contrast['metrics'][key]; center = value['mean']; low, high = value['percentile95']
            ax.errorbar(center, i, xerr=[[center-low], [high-center]], fmt='o', color='#2369a5', ecolor='#172d3b', capsize=4)
        ax.set_yticks(range(len(labels)), labels); ax.invert_yaxis(); ax.axvline(0, color='#768895', linewidth=1, linestyle='--')
        ax.set_title(title, loc='left', pad=12); ax.set_xlabel(unit); ax.grid(axis='x', alpha=.6)
    drawings['supplement-contrasts'] = save(fig, 'supplement-contrasts', '预登记配对比较：先平均训练种子和四故障条件，再对12物理种子块自举95%区间')

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5), layout='constrained')
    for first, second, color, label in [('nominal_fifo', 'nominal_tour', '#147469', '名义FIFO − Tour'),
                                         ('cvae_ppo', 'nominal_ppo', '#7b3153', 'CVAE·PPO − 名义·PPO')]:
        values = np.asarray([a['confirmed_segments']-b['confirmed_segments'] for a, b in zip(data['block_values'][first], data['block_values'][second])])
        ax = axes[0 if first == 'nominal_fifo' else 1]
        ax.bar(np.arange(1, 13), values, color=color, width=.65)
        ax.axhline(0, color='#768895', linewidth=1); ax.set_xticks(np.arange(1, 13)); ax.set_xlabel('预登记物理种子块编号')
        ax.set_ylabel('平均每故障条件净增确认 / 段'); ax.set_title(label, loc='left', pad=12); ax.grid(axis='y', alpha=.6); ax.set_axisbelow(True)
    drawings['supplement-seed-blocks'] = save(fig, 'supplement-seed-blocks', '逐物理种子块的配对效果，编号表示预登记身份，不表示时间趋势')

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.0), layout='constrained')
    for ax, stage, title in zip(axes, ['estimator_total_ms', 'policy_total_ms'], ['估计阶段', '候选准备与派单阶段']):
        values = [aggregates[m][stage+'_p95']['mean'] for m in methods]
        y = np.arange(7)
        ax.barh(y, values, color=[COLORS[m] for m in methods], height=.62)
        ax.set_yticks(y, [LABELS[m] for m in methods]); ax.invert_yaxis()
        ax.set_xlim(left=0); ax.margins(x=.2); ax.set_xlabel('逐回合p95的平均 / ms')
        ax.set_title(title, loc='left', pad=12); ax.grid(axis='x', alpha=.6); ax.set_axisbelow(True)
        for i, value in enumerate(values):
            ax.annotate(f'{value:.2f}', (value, i), xytext=(5, 0), textcoords='offset points', va='center', fontsize=11)
    drawings['supplement-latency'] = save(fig, 'supplement-latency', '最终测试的实测分阶段耗时；含实际转换和同步，不含预生成物理过程、记录和I/O')

    representative = example['case']
    assert representative == data['protocol']['case_sets']['test'][0] and example['model_seed']==271
    case_id = representative['id']
    sys.path.insert(0, str(ROOT / 'src'))
    from patrol_rsi.supplement_task import to_grid
    frame_time = example['frame_time_s']
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4), layout='constrained')
    images = []
    for ax, values, title in zip(axes, [example['frame_temperature_c'][key] for key in ['nominal','cvae','truth']], ['名义热平衡', 'CVAE-U-Net（种子271）', '事后物理温度']):
        image = ax.imshow(to_grid(values), vmin=45, vmax=75, cmap='cividis', aspect='equal'); images.append(image)
        ax.set_title(title, pad=12); ax.set_xticks([]); ax.set_yticks([])
    fig.colorbar(images[-1], ax=axes, location='bottom', shrink=.8, label='设备代表温度 / °C（共同45—75°C色标）', extend='both')
    drawings['supplement-heatmaps'] = save(fig, 'supplement-heatmaps', f'{case_id} {frame_time}秒，同一Tour观测流上的名义、CVAE估计及事后温度；按编号选首个条件和训练种子271')

    # Deterministic illustration: local rack1 in the injected pod has no fixed
    # temperature probe (fixed probes are local0/4), avoiding an all-fresh trace.
    pod = example['pod_index'];rack=example['trace_rack_index']
    clocks = np.asarray(example['clock_s']);trace=example['trace'];fresh=np.asarray(trace['fresh_mask'],dtype=bool)
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True, layout='constrained')
    for values, color, style, label in [(trace['truth_c'], '#172d3b', '-', '事后设备温度'),
                                        (trace['nominal_c'], '#7b8790', '--', '名义估计'),
                                        (trace['cvae_c'], '#2369a5', '-', 'CVAE估计')]:
        axes[0].plot(clocks, values, color=color, linestyle=style, linewidth=1.6, label=label)
    axes[0].scatter(clocks[fresh], np.asarray(trace['nominal_c'])[fresh], color='#b27420', s=17, label='刚量测（含固定遥测）', zorder=4)
    axes[0].axhline(65, color='#b44e79', linestyle=':', linewidth=1, label='研究热异常界值65°C')
    axes[0].set_ylabel(f'{rack}号柜温度 / °C'); axes[0].legend(frameon=False, ncols=3, fontsize=11)
    axes[1].plot(clocks, trace['pod_flow_kg_s'], color='#147469', linewidth=1.7)
    axes[1].axhline(33.6, color='#b44e79', linestyle=':', linewidth=1, label='研究制冷异常界值33.6 kg/s')
    axes[1].set_ylabel(f'第{pod+1}组总流量 / kg/s'); axes[1].set_xlabel('物理时间 / 秒'); axes[1].legend(frameon=False)
    start = representative['spec']['fault_start_s']; end = start+representative['spec']['duration_s']
    for ax in axes:
        ax.axvspan(start, end, color='#b27420', alpha=.12); ax.grid(alpha=.6); ax.set_xlim(5, 1800)
    axes[1].set_xticks([5, 300, 600, 900, 1200, 1500, 1800])
    drawings['supplement-process'] = save(fig, 'supplement-process', f'编号示例{case_id}：温度估计、实际流量与故障注入窗口；公开观测流完全相同')

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), layout='constrained')
    racks = [128, 512, 1024]
    values = [data['scale'][str(n)]['median_wall_s_with_tracemalloc'] for n in racks]
    bounds = np.asarray([data['scale'][str(n)]['wall_range_s'] for n in racks])
    axes[0].bar(range(3), values, color='#2369a5', width=.5)
    axes[0].errorbar(range(3), values, yerr=np.asarray([np.asarray(values)-bounds[:, 0], bounds[:, 1]-values]), fmt='none', ecolor='#172d3b', capsize=4)
    axes[0].set_ylabel('360物理步耗时 / 秒'); axes[0].set_title('物理过程耗时：中位数与实测范围', loc='left', pad=12)
    memory = [data['scale'][str(n)]['max_python_traced_peak_bytes']/1024**2 for n in racks]
    axes[1].bar(range(3), memory, color='#b27420', width=.5)
    axes[1].set_ylabel('Python追踪峰值 / MiB'); axes[1].set_title('Python追踪内存：六次运行最大值', loc='left', pad=12)
    for ax in axes:
        ax.set_xticks(range(3), [str(n) for n in racks]); ax.set_xlabel('机柜数'); ax.set_ylim(bottom=0); ax.grid(axis='y', alpha=.6); ax.set_axisbelow(True)
    drawings['supplement-scale'] = save(fig, 'supplement-scale', '三规模纯物理过程实测，每规模三种子×健康/耦合两条件；含tracemalloc开销，非大规模学习调度测试')
    return drawings


if __name__ == '__main__':
    data = json.loads((ROOT / 'paper/source-data/supplement-study.json').read_text(encoding='utf-8'))
    print('Built', len(build(data)), 'supplemental figures')
