# 机房横向比较：保存证据可复算的指标与真实缺项

日期：2026-11-03。范围：只读解析已封存的 gzip、协议、逐条件结果、任务记录及源码，补算描述性指标。**新增环境评价、过程／策略／估计器重演、训练和模型调用均为0。** 本次算术派生不增加独立实验数，不改变既有阈值、检测器或资格／重访规则。机器可复核数据为 [report-comparison-metrics.json](../source-data/report-comparison-metrics.json)。

## 1 主表可直接使用的结果

全部已运行行使用**同一预定12个热—冷耦合主过程**（p00-coupled至p11-coupled），每过程1800秒、128柜、176项专业任务。确认比率为合计确认数／同一89段异常；年龄、加权截尾等待与移动变化先逐过程计算，再对12过程等权平均。异常段不是独立重复。原主比较的协议、输入索引与结果分别见 [协议](../../evidence/event-validation/final/protocol.json)、[逐条件记录](../../evidence/event-validation/final/rows.json)、[SHA索引](../../evidence/event-validation/final/local-artifacts.json)。

|方法|温度RMSE／°C ↓|资产加权RMSE／°C ↓|R² ↑|资产重要度加权归一年龄 ↓|有效确认／比率 ↑|加权截尾等待／s ↓|硬重访违规任务数 ↓|移动变化（对Tour）↓|单步推理／ms ↓|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|固定巡回 Tour|未留存|未留存|未留存|0.310901|28/89（31.46%）|78.16|0|+0.000%|未计时|
|名义估计＋位置置乱 Shuffled|未留存|未留存|未留存|0.313138|25/89（28.09%）|81.06|0|+0.628%|未计时|
|Best of 9 并列：S1-age|未留存|未留存|未留存|0.312994|60/89（67.42%）|60.23|0|+0.552%|未计时|
|Best of 9 并列：S2-risk_time|未留存|未留存|未留存|0.312888|60/89（67.42%）|58.14|0|+0.488%|未计时|
|名义估计＋返回保护 FIFO|未留存|未留存|未留存|0.313052|70/89（78.65%）|49.69|0|+0.500%|未计时|
|VAE-UNet + Greedy（本任务未运行）|未运行|未运行|未运行|未运行|未运行|未运行|未运行|未运行|未运行|
|VAE-UNet + DRL（本任务未运行）|未运行|未运行|未运行|未运行|未运行|未运行|未运行|未运行|未运行|

“未留存”指缺少该指标需要的完整输入；“未计时”指没有对应测量。它们不是0。重访违规列为12×176项任务回合的违规总数，含初始与终端间隔。移动列是相对同过程Tour的配对变化；Tour的+0.000%是定义上的参照值。所有已运行行都使用名义估计，不能将方法名写成已跑VAE。[保存原件](../../runs/event-validation-amended-20261102/)、[线性规则原件](../../runs/response-defer-search-20261102/)、[评价器](../../src/patrol_rsi/inspection_metrics.py)、[精确间隔定义](../../src/patrol_rsi/coverage_plan.py)。

**Best of 9必须保留并列状态。** 九条唯一规则中，S1-age与S2-risk_time都达到60段；三个搜索链的`selected_proposal`均为null，所有候选均未通过既定开发门槛。表中并列展示两条，不按新增年龄、等待或成本再事后择优。它们来自已见开发过程，不能称为独立确认集上的最佳方法，也没有替代FIFO。[提案与聚合](../../evidence/response-defer/proposals.json)、[实际选择](../../evidence/response-defer/selected-search.json)、[停止状态](../../evidence/response-defer/summary.json)。

FIFO确认更多且截尾等待更短，同时整体归一巡检年龄略高于Tour。这个年龄指标主要反映全任务测量新鲜度；短时异常确认回答能否赶上异常窗口，二者可以出现取舍。本表支持有限条件下的机制比较，不能写成FIFO在全部指标上领先。年龄是本次保存数据的回顾性描述结果，未作为原实验预登记的通过门槛。[原门槛](../../evidence/event-validation/final/protocol.json)、[原主结论](../../evidence/event-validation/final/README.md)。

## 2 为什么现在可以算加权年龄

### 2.1 全176项的固定权重确实被保存

每份Tour原件的`local_decisions[].public_tasks[]`都保留`task`、`weight`和`deadline_s`。本次逐项核查12个过程：均覆盖176项；同一项在回合内所有保存记录中的权重与期限完全一致。源码明确保存`weight=asset_weights[j]/2`；热任务使用所属柜的固定资产重要度，其他三专业使用所属Pod八柜重要度均值。因此本次取资产权重`a_j=2×保存weight`，不猜权重。归一分母也乘以权重和，所以公共缩放因子2不影响分数。[封存导出源码](../../runs/event-validation-amended-20261102/source/reorder_execution.py) `public_tasks`、[封存任务初始化](../../runs/event-validation-amended-20261102/source/patrol_task.py) `asset_weights`、[固定资产重要度来源](../../runs/event-validation-amended-20261102/source/facility.py) `criticality`。

五种方法在各配对过程具有相同`spec`及`process_sha256`；事件包与规则包的任务初始化、资产权重映射、期限和评价器封存源码SHA一致。这里只从Tour取出**共同、固定的任务参数**，然后分别使用每个方法自己的完成记录；没有转借Tour的温度、风险或估计轨迹。JSON保存每过程176个原始资产权重、公共176项期限向量、权重来源指针、原件路径／SHA和逐过程积分分子分母。[两包源码身份](../../evidence/response-defer/seal.json)、[事件包源码身份](../../evidence/event-validation/final/seal.json)、[可复算数据](../source-data/report-comparison-metrics.json) `common_tasks/cases/sources`。

### 2.2 本任务的定义与单位

以专业测量**完成**为年龄清零点。对方法m、过程c的任务j，`L_cjm(t)`是t时刻之前最近一次实际专业测量完成时刻；首次完成前用虚拟年龄起点0。这个0只是初始年龄约定，不声称任务在0秒已被检查。远程遥测、派单、到达或未完成的服务均不清零。

\[
A_{cjm}(t)=\min\left(\frac{t-L_{cjm}(t)}{D_j},1\right),\qquad
I_{cm}=\frac{1}{H\sum_j a_{cj}}\int_0^H\sum_j a_{cj}A_{cjm}(t)\,dt,\quad H=1800\,\mathrm{s}.
\]

热任务`D_j=300 s`，电气、制冷、自控任务各`D_j=600 s`，全部来自保存期限并与冻结`DEADLINES`核对。`I`无量纲，范围[0,1]，越小代表按资产重要度加权的专业测量年龄越低。先对每过程以自身权重和归一，再平均12个过程，不把所有过程的资产权重混成一个池。[保存期限](../../runs/event-validation-amended-20261102/p00-coupled-tour.json.gz) `local_decisions/*/public_tasks/*/deadline_s`、[冻结期限](../../runs/event-validation-amended-20261102/source/aisles.py)。

从任务自己的保存完成时刻`t_1,…,t_n`建立边界`0,t_1,…,t_n,H`。H只是积分边界，不能当虚构完成；若实际恰在H完成，末段长度为0，对积分无贡献。每个无重置间隔长度为g时，解析积分为

\[
F_D(g)=\begin{cases}g^2/(2D),&0\le g\le D,\\g-D/2,&g>D.\end{cases}
\]

故`I_cm = Σ_j a_cj Σ_k F_Dj(g_jk) / (H Σ_j a_cj)`。本次所有完整间隔都不超过相应期限；上限截断未产生正长度的饱和段。初始、任务间及终端间隔全部纳入，未丢弃初次巡检前或回合结束后的剩余年龄。[`exact_task_gaps`边界规则](../../src/patrol_rsi/coverage_plan.py)、JSON `definitions.weighted_normalized_age`。

### 2.3 与原VAE论文指标的差别

原文式(1)按决策步以τ累加节点idleness、测量邻域采样后清零、以`W_MAX`截断，式(2)写终止时刻的节点加权求和。本任务改为有服务时长的专业完成、秒制年龄、专业期限归一、固定资产权重及整个回合的时间平均。表中应命名为“**本任务资产重要度加权归一年龄（idleness适配）**”，不能冠为已复现原文同尺度分数，也不能拿0.31与原文0.462等数直接排名。原文内容见[保留的全文抽取](../../runs/feedback-study-preparation/reference.txt) §3、式(1)–(2)，及[原文指标核查](original-paper-metrics-20261103.md)。

现有Tour `scalar_trace.mean_age_ratio`按5秒端点采样、年龄比截断6；`public_risk_age`还乘动态公开风险、截断4。本次没有把它们冒充上述固定资产权重、连续时间、截断1的指标。作为独立完整性核查，本次从专业完成时刻重建Tour全部360×12个端点的`mean_age_ratio`并与原值一致。[公开标量定义](../../src/patrol_rsi/active_inspection.py) `public_metrics`。

## 3 逐过程年龄，保持原配对单位

|配对过程|异常段|Tour|Shuffled|S1-age（并列）|S2-risk_time（并列）|FIFO|
|---|---:|---:|---:|---:|---:|---:|
|p00-coupled|9|0.311476|0.314106|0.314301|0.313843|0.313566|
|p01-coupled|7|0.309245|0.310638|0.312861|0.312635|0.312058|
|p02-coupled|7|0.311430|0.313387|0.313707|0.313712|0.314205|
|p03-coupled|8|0.310626|0.312242|0.312797|0.312804|0.312936|
|p04-coupled|8|0.311244|0.313070|0.312383|0.312383|0.312652|
|p05-coupled|8|0.311085|0.314018|0.312263|0.312263|0.312627|
|p06-coupled|7|0.311149|0.313979|0.313672|0.313489|0.313699|
|p07-coupled|7|0.310975|0.313514|0.313034|0.313055|0.313064|
|p08-coupled|8|0.308877|0.311512|0.310584|0.310273|0.311397|
|p09-coupled|8|0.310683|0.312980|0.312957|0.312758|0.312758|
|p10-coupled|5|0.312906|0.314517|0.314584|0.314389|0.314350|
|p11-coupled|7|0.311121|0.313690|0.312790|0.313056|0.313311|

表中每行仍是一个已有过程，不是新增实验。不同种子有各自保存的固定资产权重，因此相同Tour执行时序的加权年龄也会略有不同。JSON同时保留逐过程的`weighted_age_time_integral_s`、`weighted_age_denominator_s`、完整权重及任务积分摘要SHA，可由原`exact_task_gaps`重算。

作为辅助校核，可另列所有任务同等权重的结果；它不是重要度加权分数：

|方法|同等任务权重归一年龄 ↓|平均移动／m|平均完成专业测量|额外事件访问合计|
|---|---:|---:|---:|---:|
|固定巡回 Tour|0.310160|11793.40|1426.00|0|
|名义估计＋位置置乱 Shuffled|0.312400|11867.47|1421.17|81|
|Best of 9 并列：S1-age|0.312217|11858.53|1421.67|78|
|Best of 9 并列：S2-risk_time|0.312114|11850.94|1422.00|79|
|名义估计＋返回保护 FIFO|0.312287|11852.32|1421.33|89|

额外访问和完成量展示成本差别，不能称这些方法严格等成本。原共同上限是每回合12次补查，实际用量不同。[冻结事件协议](../../evidence/event-validation/final/protocol.json)、[原件响应配置](../../runs/event-validation-amended-20261102/p00-coupled-fifo.json.gz) `response_config`。

## 4 不能补出的列，以及还缺哪些字段

|指标|已保存的相关信息|为什么仍不足／最低缺项|
|---|---|---|
|温度RMSE|名义估计公式、Tour稀疏任务快照、专业测量和异常区间|缺每个方法自己的完整、同时间同目标对齐的估计温度矩阵与物理真值矩阵（例如360×128），以及共同有效目标mask；热专业测量带噪声，不能直接当全图真值|
|资产加权RMSE|已恢复全176任务资产权重；可对应128柜权重|仍缺上述估计／真值对齐帧；权重存在不能代替误差数据|
|R²|部分观测及异常标签|缺完整真实目标与残差；还需明确全时空展平或逐帧／逐过程平均方式，不以确认率替代|
|单步推理ms|`history_estimator_inference_s=0`；主包和搜索包模型调用及训练均为0|该计时字段只覆盖可选history预测器调用；名义估计更新与调度没有逐调用计时、调用数及共同硬件／预热／batch信息，不能写0 ms|
|VAE-UNet＋Greedy／DRL|保留可选MLP TemperatureCVAE及PPO工具、任务合法性检查；另有旧阶段本地检查点|未发现本次12过程中的VAE-UNet＋Greedy或原论文Double-DQL运行原件；不能将工具存在写成适配完成，也不能写“正在训练出数”|

Tour的`process`与其他主方法的`process_metadata`是配置、汇总值及过程digest，**不是360×128真值数组**；两条线性规则原件仅保留`process_sha256`，同样没有全真值。可用的`anomaly_intervals`只包含区间标签及后果权重；它们不足以反推温度残差。`paper/source-data/engineering-snapshot-500.json`虽有128柜估计／真值快照，但属于seed41000、`aux_feeder_loss`工程解释案例，不属于本表12个主过程；不能拿这一帧补四种策略的全回合主结果。[工程快照及scope](../source-data/engineering-snapshot-500.json)、[主过程输入界定](report-method-formulas-20261103.md)、[源码估计器](../../src/patrol_rsi/estimation_model.py)、[源码PPO](../../src/patrol_rsi/inspection_model.py)、[算法关系](../../docs/RESEARCH.md)。

VAE两行的真实状态应写“**本任务未运行／未形成同任务结果**”。“0模型调用／0训练”仅指本次所引用的封存事件包、线性搜索包和本次数值派生；并不抹除本地旧阶段曾保存其他模型的事实。[事件包计数](../../evidence/event-validation/final/summary.json)、[搜索包计数](../../evidence/response-defer/summary.json)。

## 5 保持既有确认与等待定义

有效确认沿用保存评价结果：专业测量完成且报警与该异常段匹配，取`first_confirmation_s`；未确认段在自身`end_s`截尾，等待`d_i=(首次确认时刻或截尾终点)-onset_s`。每过程计算`Σ_i q_i d_i / Σ_i q_i`，其中`q_i=anomaly_intervals[].weight`，再对12过程取均值。q是**异常后果权重**，来自固定资产权重乘`1+异常段平均超阈严重度`；它与全任务年龄使用的固定a权重不是同一个量。[冻结评价器](../../runs/event-validation-amended-20261102/source/inspection_metrics.py) `anomaly_intervals/evaluate_episode`。

确认列不把事件账本`measured`等同于异常确认；等待也不是只对已检出段求平均。保存评价器按`int(completion_s/5)-1`取前一个5秒标签，因此对本次已保存的连续异常段，有效阳性端点落在`onset_s < completion_s <= end_s`，**恰在报告起点的报警不能只因时间落入闭区间就自动算确认**。例如p09-coupled Shuffled的thermal:87区间[500,520]，500秒虽有`alarm=True`，其前一采样bin不在本段，保存的`detected=False`保持原样。完整真值标签未重演。[原件](../../runs/event-validation-amended-20261102/p09-coupled-shuffled.json.gz) `anomaly_intervals/inspection_events`、[评价器索引规则](../../src/patrol_rsi/inspection_metrics.py)、JSON `validation.onset_endpoint_alarms_excluded_by_saved_bin_semantics`。

## 6 本次数值核查与复算入口

- 60份已有gzip的原字节SHA与各自发布索引一致；12个过程内五方法的`spec`、过程SHA、异常区间键及后果权重一致。
- 61440条保存公开任务行确认固定权重／期限，12×176项权重完整；热任务权重与三类Pod平均权重映射一致。
- 85346次专业完成事件与10560组任务完整间隔逐项核对，完成数、任务ID、初始／终端边界及保存最大间隔一致；全部重访违规0。
- 解析积分另用各方法自己的`inspection_events`作5秒区间中点积分交叉核对，任务积分最大绝对误差2.27e-13秒；Tour 4320个保存标量年龄端点重建最大误差5.55e-17。
- 逐段首次确认／截尾等待与保存事件一致，重算加权等待最大误差2.84e-14秒；主确认数28／25／60／60／70、成本与封存汇总吻合。
- 本次92份证据输入最终再读SHA一致；JSON无NaN，缺项使用null，原决策门槛和结果未改。

JSON的`sources`逐项记录本次所用相对路径、原字节SHA256和大小；`cases`保存各方法自己的原件路径、加权年龄积分与分母、等待分子分母、移动变化和共同任务权重。未导出原始大轨迹。无需导入`patrol_rsi`，也无需运行环境或估计器即可复算，核心只读算式如下：

```python
import gzip, hashlib, json
from pathlib import Path
root = Path.cwd()
data = json.loads((root / "paper/source-data/report-comparison-metrics.json").read_text(encoding="utf-8"))
D = data["common_tasks"]["deadlines_s"]
expected_sha = {s["path"]: s["sha256"] for s in data["sources"]}
for case in data["cases"]:
    weights = case["asset_weights"]
    for method, saved in case["methods"].items():
        raw = (root / saved["record_path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected_sha[saved["record_path"]]
        record = json.loads(gzip.decompress(raw))
        numerator = 0.0
        for task in record["exact_task_gaps"]:
            j = task["task"]
            times = [0.0] + task["completion_times_s"] + [1800.0]
            gaps = [b-a for a, b in zip(times, times[1:])]
            area = sum(g*g/(2*D[j]) if g <= D[j] else g-D[j]/2 for g in gaps)
            numerator += weights[j] * area
        value = numerator / (1800.0 * sum(weights))
        assert abs(value - saved["weighted_normalized_age"]) < 1e-12
```

若后续需要长期保留自动复核入口，可另加只读报告派生脚本；本次只写本研究记录与紧凑JSON，没有修改研究执行程序。
