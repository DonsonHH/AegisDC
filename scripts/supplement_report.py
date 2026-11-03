"""Evidence-bound text/table substitutions for the completed supplement."""
from html import escape

LABELS = {'nominal_tour':'名义＋Tour','nominal_fifo':'名义＋FIFO','nominal_greedy':'名义＋Greedy',
          'nominal_ppo':'名义＋PPO','cvae_fifo':'CVAE＋FIFO','cvae_greedy':'CVAE＋Greedy','cvae_ppo':'CVAE＋PPO'}


def number(value, digits=2, signed=False):
    return 'NA' if value is None else format(value, ('+' if signed else '')+'.'+str(digits)+'f')


def count(value):
    return number(value, 2).rstrip('0').rstrip('.')


def estimate(item, digits=2, signed=False):
    if item['mean'] is None:
        return 'NA'
    low, high = item['percentile95']
    return f"{number(item['mean'],digits,signed)} [{number(low,digits,signed)}, {number(high,digits,signed)}]"


def table(headers, rows, kind, row_ids=None):
    header = '<thead><tr>'+''.join('<th>'+escape(str(h))+'</th>' for h in headers)+'</tr></thead>'
    body = []
    for index, row in enumerate(rows):
        attribute = f' data-supplement-method="{row_ids[index]}"' if row_ids else ''
        body.append('<tr'+attribute+'>'+''.join('<td>'+escape(str(v))+'</td>' for v in row)+'</tr>')
    return f'<div class="table-wrap"><table data-table="{kind}" class="supplement-table">'+header+'<tbody>'+''.join(body)+'</tbody></table></div>'


def substitutions(data):
    methods, aggregates = data['method_order'], data['primary_aggregates']
    estimators, tasks, latency = [], [], []
    for method in methods:
        row = aggregates[method]
        estimators.append([LABELS[method],number(row['all_rmse_c']['mean'],3),number(row['all_weighted_rmse_c']['mean'],3),
                           number(row['all_r2']['mean'],4),number(row['not_fresh_weighted_rmse_c']['mean'],3),
                           '1个确定性规则' if method in ('nominal_tour','nominal_fifo','nominal_greedy') else '3个独立训练种子'])
        safety = sum(row[k]['mean'] for k in ('invalid_assignments_audited','duplicate_reservations_audited','revisit_violations_audited','budget_violations_audited'))
        tasks.append([LABELS[method],count(row['total_confirmed_model_mean'])+'/'+count(row['total_unique_anomaly_segments']),
                      number(100*row['pooled_confirmation_ratio'],1)+'%',estimate(row['confirmed_segments']),
                      number(row['consequence_weighted_censored_delay_s']['mean']),number(row['weighted_normalized_age']['mean'],6),
                      number(row['travel_change_vs_tour_pct']['mean'],2,True)+'%',number(row['completion_change_vs_tour_pct']['mean'],2,True)+'%',int(safety)])
        latency.append([LABELS[method],number(row['estimator_total_ms_p50']['mean']),number(row['estimator_total_ms_p95']['mean']),
                        number(row['policy_total_ms_p50']['mean']),number(row['policy_total_ms_p95']['mean']),
                        number(row['online_control_cycle_ms_p95']['mean'])])
    contrasts = []
    for contrast in data['contrasts']:
        row = contrast['metrics']
        contrasts.append([LABELS[contrast['first']]+' − '+LABELS[contrast['second']],estimate(row['confirmed_segments'],2,True),
                          estimate(row['consequence_weighted_censored_delay_s'],2,True),estimate(row['weighted_normalized_age'],6,True),
                          estimate(row['all_weighted_rmse_c'],3,True)])
    fixed = data['fixed_stream']['aggregates']
    fixed_rows = []
    for estimator, label in [('nominal','名义热平衡'),('cvae','残差CVAE-U-Net')]:
        fixed_rows.append([label,estimate(fixed[estimator+'_all_rmse_c'],3),estimate(fixed[estimator+'_all_weighted_rmse_c'],3),
                           estimate(fixed[estimator+'_all_r2'],4),estimate(fixed[estimator+'_not_fresh_weighted_rmse_c'],3)])
    healthy = []
    for method in methods:
        normal = data['family_aggregates']['healthy'][method];spurious = data['family_aggregates']['spurious'][method]
        healthy.append([LABELS[method],number(normal['extra_event_visits']),number(spurious['extra_event_visits']),
                        number(normal['false_measured_confirmations']),number(spurious['false_measured_confirmations']),
                        number(spurious['completion_change_vs_tour_pct'],2,True)+'%','NA / NA'])
    families = []
    for family, label in [('compound','辅助馈电＋CDU'),('electrical','接触热点'),('control','传感偏差'),('cooling','二次泵故障')]:
        for method in methods:
            row = data['family_aggregates'][family][method]
            families.append([label,LABELS[method],number(row['confirmed_segments']),number(row['anomaly_segments']),
                             number(row['consequence_weighted_censored_delay_s']),number(row['all_weighted_rmse_c'],3),number(row['extra_event_visits'])])
    scale = [];scale_cycles=[]
    for racks, row in data['scale'].items():
        roles = row['feasibility']['roles']
        cycles = [number(roles[role]['agents'],0)+'人；'+number(max(c['closed_quantized_cycle_s'] for c in roles[role]['constructed_cycles']),0)+'/'+number(roles[role]['reference_revisit_s'],0)+'秒'
                  for role in ['thermal','electrical','cooling','control']]
        feasible = all(r['all_constructed_cycles_within_revisit'] for r in roles.values())
        n=int(racks);pods=n//8
        scale.append([racks,f'{n+2*pods+1}／{n+pods+1}',str(row['feasibility']['total_agents'])+'／'+str(sum(r['tasks'] for r in roles.values())),
                      number(row['median_wall_s_with_tracemalloc'],3),number(row['max_python_traced_peak_bytes']/1024**2,2),
                      '构造闭合巡回满足' if feasible else '部分构造巡回超期'])
        scale_cycles.append([racks,*cycles])
    training_rows = []
    for seed in data['protocol']['model_seeds']:
        record = data['training'][f'cvae-{seed}'];history=record['history']
        best = min(history,key=lambda r:r['development_weighted_mse_normalized'])
        training_rows.append([seed,len(history),record['training_snapshots'],record['development_snapshots'],best['epoch'],
                              number(best['development_weighted_rmse_c'],3),number(record['wall_s']/60,2)])
    variation = []
    for method, record in data['seed_variation'].items():
        variation.append([LABELS[method],*[number(record['per_seed'][str(seed)]['confirmed_segments']) for seed in data['protocol']['model_seeds']],
                          number(record['sample_sd']['confirmed_segments'],3),number(record['sample_sd']['all_weighted_rmse_c'],4)])
    policy_training=[]
    for row in data['policy_training_costs']:
        policy_training.append([('名义' if row['estimator']=='nominal' else 'CVAE')+'＋PPO',row['model_seed'],row['episodes'],
                                row['time_steps'],row['task_choices'],row['choice_sets_with_alternatives'],
                                number(100*row['choice_sets_with_alternatives']/row['task_choices'],2)+'%',number(row['episode_and_update_wall_s']/60,2)])
    fifo = next(c for c in data['contrasts'] if (c['first'],c['second'])==('nominal_fifo','nominal_tour'))
    cvae = next(c for c in data['contrasts'] if (c['first'],c['second'])==('cvae_fifo','nominal_fifo'))
    ppo = next(c for c in data['contrasts'] if (c['first'],c['second'])==('cvae_ppo','cvae_fifo'))
    return {
        'SUPPLEMENT_ERROR_TABLE':table(['方法','RMSE / °C↓','加权RMSE / °C↓','R²↑','盲区机柜加权RMSE / °C↓','模型／规则重复'],estimators,'supplement-errors',methods),
        'SUPPLEMENT_TASK_TABLE':table(['方法','确认／唯一异常段','确认比例','每条件确认 [95%CI]','截尾等待 / 秒↓','加权年龄↓','移动相对Tour','完成量相对Tour','约束违规'],tasks,'supplement-tasks',methods),
        'SUPPLEMENT_FIXED_TABLE':table(['估计器','RMSE / °C','加权RMSE / °C','R²','盲区机柜加权RMSE / °C'],fixed_rows,'supplement-fixed-stream'),
        'SUPPLEMENT_CONTRAST_TABLE':table(['预登记比较','每条件确认差↑','截尾等待差 / 秒↓','归一年龄差↓','闭环加权RMSE差 / °C↓'],contrasts,'supplement-contrasts'),
        'SUPPLEMENT_HEALTHY_TABLE':table(['方法','健康额外访问','虚假提示额外访问','健康误确认','虚假提示误确认','虚假提示完成量相对Tour','两组确认比例／等待'],healthy,'supplement-healthy'),
        'SUPPLEMENT_FAMILY_TABLE':table(['故障条件','方法','平均确认段','平均异常段','平均截尾等待 / 秒','加权RMSE / °C','平均额外访问'],families,'supplement-families'),
        'SUPPLEMENT_LATENCY_TABLE':table(['方法','估计p50 / ms','估计p95 / ms','派单p50 / ms','派单p95 / ms','完整周期p95 / ms'],latency,'supplement-latency'),
        'SUPPLEMENT_SCALE_TABLE':table(['机柜数','热状态／指令状态','执行者／专业任务','物理耗时中位数 / 秒','Python峰值 / MiB','静态检查'],scale,'supplement-scale'),
        'SUPPLEMENT_SCALE_CYCLES_TABLE':table(['机柜数','热检查：人数；周期／期限','电气：人数；周期／期限','制冷：人数；周期／期限','自控：人数；周期／期限'],scale_cycles,'supplement-scale-cycles'),
        'SUPPLEMENT_TRAINING_TABLE':table(['训练种子','实际epoch','训练快照','开发快照','选中epoch','开发加权RMSE / °C','训练分钟'],training_rows,'supplement-training'),
        'SUPPLEMENT_SEED_TABLE':table(['方法',*[f'种子{s}' for s in data['protocol']['model_seeds']],'确认训练种子SD','误差训练种子SD / °C'],variation,'supplement-seeds'),
        'SUPPLEMENT_POLICY_TRAINING_TABLE':table(['策略','训练种子','回合','全局时间步','实际选择数','存在多个合法候选','有选择余地比例','执行＋更新分钟'],policy_training,'supplement-policy-training'),
        'SUPPLEMENT_SEGMENTS':f"{aggregates['nominal_tour']['total_unique_anomaly_segments']:g}",
        'SUPPLEMENT_FIFO_GAIN':estimate(fifo['metrics']['confirmed_segments'],2,True),
        'SUPPLEMENT_CVAE_GAIN':estimate(cvae['metrics']['confirmed_segments'],2,True),
        'SUPPLEMENT_PPO_GAIN':estimate(ppo['metrics']['confirmed_segments'],2,True),
        'SUPPLEMENT_FIXED_DELTA':estimate(fixed['delta_not_fresh_weighted_rmse_c'],3,True),
        'SUPPLEMENT_RUNTIME':escape(data['seal']['runtime']['gpu']),
        'SUPPLEMENT_ATTEMPTS':str(data['environment_attempts']),
        'SUPPLEMENT_ENERGY_RESIDUAL':format(max(r['max_energy_residual_kj'] for r in data['scale'].values()),'.2e'),
        'SUPPLEMENT_ELECTRIC_RESIDUAL':format(max(r['max_electric_residual_kw'] for r in data['scale'].values()),'.2e'),
    }
