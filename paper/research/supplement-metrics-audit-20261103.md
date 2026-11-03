# 新补充研究的数据、方法与统计设计审查

日期：2026-11-03。状态：**执行前的方法审查与建议，不是新实验结果或通过证明**。本次只读查看当前源码、既有指标 JSON、原论文全文抽取及本地历史训练包；唯一新增文件是本文件。未生成新物理过程，未运行策略、估计器、训练或 LLM。新研究的授权和身份独立于旧封存包；旧 108 次成功＋1 次失败及 108 次规则搜索的计数、阈值和结论不变。

## 1. 审查结论与先解决的实现问题

拟议六条件能补上当前确实缺失的温度估计误差、运行时间及跨故障类型证据，但必须同时建立两个问题的答案：**同一观测下估计器是否改善**，以及**各自闭环观测下完整巡检系统是否改善**。单独比较不同策略自己的 RMSE 会混合模型质量、采样位置和测量频率，不能直接归因于估计器。原论文也先用独立随机路径评价估计器，再作规划器及估计模块消融；参见原文 §5.2–5.4、保存全文第 806–840、957–985 行。[原论文机构库全文](https://idus.us.es/server/api/core/bitstreams/79e88506-ca7f-48f1-86b8-5504d9cb3e39/content)、[本地原文](../../runs/feedback-study-preparation/reference.txt)。

以下问题若不处理，新结果的标签或比较权限会失真：

|问题|当前直接证据|新补充应做的处理|
|---|---|---|
|当前 CVAE 不是 U-Net|`TemperatureCVAE` 的 prior、posterior、decoder 全是 `Linear`，没有卷积、上下采样或跳接|需要真实实现并训练有卷积收缩／扩张路径和跳接的温度适配 CVAE-U-Net，或将名称写成 MLP-CVAE；不能只改表格名字|
|现有 PPO 不是原论文 DRL 算法|`TaskPolicy` 为共享候选打分 actor／critic，`ppo_update` 为 PPO；原文采用多智能体 Double DQL／Dueling 网络|明确称“本任务 PPO 基线”；真实训练也不构成原 DDQL 复现|
|事件环境目前不接收预测器|`ResponseTask.__init__` 第 72 行固定调用 `super().__init__(spec,None)`；history 模式要求非空 predictor|新环境显式接入冻结预测器，禁止静默降级名义估计|
|直接套旧 PPO 将拿到全零候选特征|`ResponseTask.options` 第 107–114 行返回全零 feature；`choose` 才计算公开风险及实际事件候选|FIFO、Greedy、PPO 共用一个真实公开候选构造器，PPO 输入必须包含可追溯的公开特征|
|旧 `options` 与 `choose` 的预算过滤不同|额外访问剩余预算在 `choose` 第 127–130 行过滤、在 `step` 第 173–175 行拒绝；`options` 没有该过滤|候选生成统一处理返回证书、预约、当前批次已规划额外派单和剩余预算；不能让某方法在执行时被拒绝后临时选替代动作|

来源：[estimation_model.py:9–35](../../src/patrol_rsi/estimation_model.py)、[inspection_model.py:15–106](../../src/patrol_rsi/inspection_model.py)、[risk_response.py:67–175](../../src/patrol_rsi/risk_response.py)、[原论文 §4.1–4.7](../../runs/feedback-study-preparation/reference.txt)。以上是当前文件的事实；本文件没有实施修复。

## 2. 样本、分组与最小可实施预算

### 2.1 统计单位固定为新 master seed block

建议最终测试使用至少 12 个全新过程种子，每个种子均运行六条件：`aux_feeder_loss+cdu_fouling`、`dc_contact_hotspot`、`sensor_bias`、`secondary_pump_trip`、`healthy`、`healthy+synthetic cue`。同一种子跨条件的负荷、资产重要度等具有共同来源，所以是 **12 个独立种子块、72 个条件回合**，不是 72 个独立重复；柜、5 秒帧、测量事件和异常段均不是独立样本。[共同随机量生成](../../src/patrol_rsi/facility.py)、[过程生成与测量噪声](../../src/patrol_rsi/process.py)。

`healthy+synthetic cue` 必须复用同一 seed 的 healthy 物理过程与噪声，唯一变化是公开 cue；因此这两条件的 `process_sha256` 应相同。六条件每种子通常只有五条不同物理轨迹，12 种子预期共 60 条唯一物理轨迹；72 是条件配置数。应在索引中分别保存 `master_seed`、`condition`、`process_sha256`、`cue_sha256`，避免把同一健康过程计两次独立证据。公开 pulse 本就只修改风险，不修改物理过程。[patrol_task.py:38–43、79–87](../../src/patrol_rsi/patrol_task.py)。

当前默认故障位置是 `pod=seed%16`、`rack=pod*8+(seed*3)%8`，而远程流量只覆盖偶数 Pod，温度只覆盖 `rack%4==0` 的柜。因此应在冻结清单中平衡故障 Pod 奇偶、被遥测／不被遥测的位置及注入相位；可通过 `fault_rack` 显式解耦位置与负荷种子。若使用四个既有合法相位 150、335、520、705 秒，可在 12 个种子块中各分配 3 次，并在同一块的所有方法保持相同。此项是设计建议，不声称 12 个位置能代表全部设施布局。[facility.py:115–121、256–269](../../src/patrol_rsi/facility.py)、[process.py:101–105](../../src/patrol_rsi/process.py)。

### 2.2 必须在过程层面分离训练、开发和测试

训练／开发／最终测试先分配互不重叠的 master seed 集，整条过程及其全部相位、历史窗口、柜和六条件都留在所属 split。禁止先生成全部帧再随机按帧或按柜分割；相邻历史窗口和共享资产参数会泄漏。记录 seed 集不交叠，并检查过程 SHA／数据谱系；健康与 cue 的同 SHA 仅允许在同一 split 的配对条件内。模型初始化 seed 与物理过程 seed 是不同命名空间，不把 3 个初始化 seed 当 3 条新物理过程。[因果窗口实现](../../src/patrol_rsi/estimation.py)、[原论文训练／验证／测试拆分](../../runs/feedback-study-preparation/reference.txt)。

一个可实施起点是训练 16 个过程种子块、开发 4 个、最终测试 12 个；这只是预算建议，实际数量应在开发计时后冻结。原论文的 3000／100／100 真值和 20000 策略训练回合属于原任务预算，不必照抄，也不能用本任务较少预算声称同等训练充分性。[原文 §5.2–5.3](../../runs/feedback-study-preparation/reference.txt)。

|实现层级|最终测试回合数（72 条件配置）|可作的结论|
|---|---:|---|
|7 标签：名义 Tour／FIFO／Greedy／PPO；CVAE-U-Net＋FIFO／Greedy／PPO；每学习方法只 1 个 checkpoint|7×72＝504|对这些冻结 checkpoint 的探索性结果；不能证明训练稳定性|
|推荐：名义 Tour／FIFO／Greedy 各 1 份，名义 PPO 3 个训练 seed，三个 CVAE 组合各 3 个训练 seed|15×72＝1080|同时展示测试过程变化及有限的训练 seed 变化；统计独立过程块仍是 12|
|CVAE seed 与 PPO seed 完整 3×3 交叉|21×72＝1512|能更细拆训练随机性；本轮无必要默认扩大到此规模|

1080 方案只需 3 份 CVAE-U-Net 训练、3 份名义 PPO 训练、3 份 CVAE-U-Net＋PPO 训练。后一组使用配对 `(CVAE seed s, PPO seed s)`，不是 9 次组合；FIFO／Greedy 不训练。所有训练 seed 都保留，不能按最终测试选最佳 seed。每份模型只能按冻结的开发准则选 checkpoint。少量训练运行的点估计不反映全部不确定性，应同时给区间与逐 seed 数据；此原则与 [Agarwal 等的原始研究](https://papers.nips.cc/paper/2021/hash/f514cec81cb148559cf475e7426eed5e-Abstract.html)一致，本表数值预算是本次建议。

另保留一条**固定 Tour 观测流的估计器对照**：在同一份已记录公开输入和已完成测量上评价名义估计及三个 CVAE checkpoint，动作不由这些估计改变。这可复用新 Tour 轨迹，不增加物理过程生成数；额外神经推理与评价仍如实计数。闭环 1080 回合回答完整系统效果，这一同数据对照回答估计器效果，两张表不合并宣称因果。

### 2.3 故障 duration 的 pilot 只能在开发集选择

当前合法 duration 为 60／120／180／240／900 秒，故障修改在 `[start,end)` 生效，物理响应及恢复可越过注入终点。先用开发种子检查各故障是否产生至少 15 秒的可评价异常、在哪些专业产生异常、公开提示是否早于现场确认；冻结选择及理由后再生成／打开最终测试。不要按 FIFO、PPO 或 CVAE 谁更容易获胜来挑 duration，也不在看过 test 后延长故障或改阈值。[process.py:101–137](../../src/patrol_rsi/process.py)、[facility.py:128–149](../../src/patrol_rsi/facility.py)、[inspection_metrics.py:36–51](../../src/patrol_rsi/inspection_metrics.py)。

若某故障在 test 的部分 seed 不产生异常，应保留为该分布的零异常过程并报告分母，不删种子或追加“更有效”的替代种子。若公开风险只能由首次专业测量揭示，这属于可见性限制；不能把该方法的同刻风险事件说成提前预警。[风险来源](../../src/patrol_rsi/active_inspection.py)、[现场确认与事件观察顺序](../../src/patrol_rsi/risk_response.py)。

## 3. 公平比较的观察权和动作权

所有方法共享相同物理轨迹、远程遥测掩码、时间戳、固定噪声规则、人员、专业资格、任务所属、移动／服务时间、事件 TTL、额外派单预算和返回证书。当前测量噪声由 `(seed,task,tick)` 决定，适合维持配对；不能让某方法拥有更准确测量或预先看到完整任务真值。[process.py:85–95](../../src/patrol_rsi/process.py)、[patrol_task.py:29–94](../../src/patrol_rsi/patrol_task.py)、[ResponseChecker](../../src/patrol_rsi/risk_response.py)。

- **Tour 对事件方法**：Tour 没有插入动作是明确的机制对照。因此总效果包含事件访问权限的变化，不能单独归因于排序器。
- **FIFO／Greedy／PPO 之间**：统一候选＝本人的例行头＋当前公开待处理事件；统一资格、所属、预约、回合终点、返回证书和剩余额外派单过滤。按相同执行者顺序逐个更新 reservation 与批次预算。某方法若只在 FIFO 头与例行头二选一，其他方法也须遵守同一动作空间，或明确另列实验。
- **Greedy**：先冻结精确公式和 tie-break。例如固定资产权重×当前公开风险／预计移动及服务时间；分母下界和并列规则写入协议。该风险是严重度代理，不能叫期望经济收益或故障概率。现有 `priority='risk'` 仅按风险排序，不能未经定义就称原论文 Greedy 复现。
- **PPO**：只接收同一公开候选的特征及合法 mask。不能复用更宽权限的旧 `ActiveInspection.options`，不能把真实未来异常窗口、fault scenario、完整温度、process 数组或最终评价标签放入 actor／critic／训练回报。
- **控制未改变**：各方法的巡检只影响信息，不维修、不消除故障。若同一条件的物理 SHA 因策略而不同，应先视为实现错误并停住汇总。

这些边界来自当前固定所属、返回检查和 trace 防护机制；新排序器也应执行 `DeniedOnlineTrace`，但该防护只阻止直接读 `env.trace`，还需审查缓存、候选字段、训练 reward 及预处理器是否携带隐藏状态。[patrol_task.py](../../src/patrol_rsi/patrol_task.py)、[risk_response.py:107–210](../../src/patrol_rsi/risk_response.py)、[contracts.py:27–29](../../src/patrol_rsi/contracts.py)。

FIFO／Greedy 下更换估计器可直接检验估计模块效果。分别重训的名义 PPO 与 CVAE-PPO 之差包含估计器和策略适应，宜称“联合系统差异”；如需分离固定 PPO 对估计器的敏感性，另作预先声明的交叉 checkpoint 分析，不能事后只挑效果好的组合。

PPO 旧 reward 包含专业报警次数奖励，每次阳性检查都可能给奖，未等同于首次确认一个异常段。新训练应冻结公开 reward，并记录同一段重复阳性检查、额外访问和回报分解，防止把重复量当任务收益；不为追求 test 胜出反复重写 reward。[active_inspection.py:238–247](../../src/patrol_rsi/active_inspection.py)。

## 4. 每 5 秒应保存什么，以及误差如何计算

### 4.1 时间、输出和真值对齐

当前环境初始化在 5 秒，终止在 1800 秒；有 **360 个状态端点 `5,10,…,1800` 和 359 次决策／推进**。每个端点先接收当前遥测与本步已完成专业测量，再形成当前估计和后续动作；到达、派单和在途服务不是已完成测量。建议固定保存这个“同化后、下一决策前”时点，另标识初始帧及终端无决策帧。若另存同化前预测，使用不同字段，禁止混在一列。[active_inspection.py:58–91、175–247](../../src/patrol_rsi/active_inspection.py)、[ObservationState.update](../../src/patrol_rsi/estimation.py)。

每个方法每回合最低保留：

|数据|最低字段|
|---|---|
|过程共享真值|360×128 物理 `rack_temperature_c`、128 柜固定资产权重、实际时间向量、过程 SHA；其他专业标签所需 contact／flow／public-sensor 数组或独立保存的完整标签矩阵|
|公开输入|每端点原始 packet／其 hash、远程温度与流量 mask、完成测量列表及时间、合成 cue、公开状态；各方法自己的专业测量记录|
|估计输出|每端点实际交给风险／策略的 128 柜估计、估计器调用标志、最近刷新时间；每次模型的原始 prior 输出另列；每个 checkpoint SHA|
|掩码|当前远程输入 mask、当前校准热测量完成 mask、最后温度观测 stamp、最后校准检查 stamp、从未校准检查 mask；不能只存一个不明含义的 fresh|
|巡检与动作|候选／合法 mask、所选动作、预约和预算、返回证书、实际完成测量、每任务初始／中间／终端间隔、事件生命周期及额外派单数|
|计时|按端点及按调用保存的分阶段时间、是否调用、执行者／候选数、设备与线程配置；不能只留总秒数|

当前主包缺温度误差输入而非缺计算公式；`process_metadata`、digest、异常区间和稀疏图不是温度矩阵，不能补作真值。新文件需保留可重算矩阵及 mask，旧主表的 null 不倒填成新实验值。[现有指标定义与缺项](../source-data/report-comparison-metrics.json)、[保存数据复算说明](report-comparison-metrics-20261103.md)。

### 4.2 冻结温度误差口径

对每个过程条件、方法和 checkpoint，先在固定 `T×R=360×128` 网格上算一个回合分数。令 `e_tr=estimate_tr−truth_tr`，固定正资产权重为 `a_r`，有效支持为 `M_tr`：

\[
\mathrm{RMSE}=\sqrt{\frac{\sum_{tr}M_{tr}e_{tr}^2}{\sum_{tr}M_{tr}}},\qquad
\mathrm{WRMSE}=\sqrt{\frac{\sum_{tr}M_{tr}a_re_{tr}^2}{\sum_{tr}M_{tr}a_r}}.
\]

\[
R^2=1-\frac{\sum_{tr}M_{tr}e_{tr}^2}{\sum_{tr}M_{tr}(y_{tr}-\bar y_M)^2}.
\]

`a_r` 来自固定资产重要度，不使用 test 后果权重、真实超阈严重度或预测误差造权重。主 R² 为单回合全时空展平，之后按过程等权汇总；不要把逐帧 R² 平均冒充该值，不把所有回合先混池。R² 可负；若目标方差为零或小于冻结数值阈值，记录 `null`、SST 和有效数量，不强制改成 0／1，也不默默剔除负值。[现有温度指标实现](../../src/patrol_rsi/estimation.py)、[scikit-learn 官方 R² 语义](https://scikit-learn.org/1.6/modules/generated/sklearn.metrics.r2_score.html)。本式是本任务定义，原文未给出精确 WRMSE 归一分母。[原论文全文](../../runs/feedback-study-preparation/reference.txt)。

主表保留六条件各自结果，另可给预先定义的六条件等权宏平均。为避免健康背景掩盖局部故障，预先保存整回合、注入期间及恢复期间曲线／分层；故障期间切片是离线评价，不能流回 actor。物理温度用 °C；电气温度、流量、自控误差的不同单位不混入一个原始 RMSE。

### 4.3 “未观测”必须拆清楚

建议同时报告三种支持，并保存每种分母：

1. **固定无远程温度传感器柜**：`rack%4 != 0`，每帧共同 96 柜；这是各方法一致的空间支持，但其中可能已有现场校准测量。
2. **当前未得到直接温度输入**：补集于“当前远程输入或当前校准热测量完成”；随策略变化，需报告样本数和年龄分布，不能只比一个 RMSE 就声称同等未观测难度。
3. **尚未现场校准／过时子集**：按校准检查 stamp 定义，并预先指定年龄阈值；与公共遥测年龄分开。

当前 `fresh_measurement` 使用观测年龄 ≤10 秒，而 `current_history` 同化使用 `temperature_stamp==clock`；两者不同。`temperature_metrics(...,fresh=None)` 会把全部点当“unmeasured”，因此新评价不得遗漏 fresh/mask 后仍输出“未观测 RMSE”。[facility_observation.py:126–134](../../src/patrol_rsi/facility_observation.py)、[patrol_task.py:111–112](../../src/patrol_rsi/patrol_task.py)、[estimation.py:128–146](../../src/patrol_rsi/estimation.py)。

`sensor_bias` 条件把目标 Pod 的公开传感器偏置设为 −18°C，并同时影响物理控制反馈；这些公开读数是模型可用的观测，**不是校准的物理温度真值**。仍对 `rack_temperature_c` 评分，另外标识公开输入与专业校准来源。不能把 biased telemetry 写入 truth，或凭 scenario 名给模型“此传感器已坏”的标签。[facility.py:142、157–170](../../src/patrol_rsi/facility.py)、[process.py:85–95](../../src/patrol_rsi/process.py)。

### 4.4 模型训练与推理防泄漏

训练 posterior 可以接收训练 split 的目标，测试只允许 conditional prior 接受历史公开输入。测试不能调用带 `target` 的 `forward`，不能用未来帧填补历史；第一帧补齐、归一化、残差基准、输出裁剪、刷新周期和潜变量采样数均在开发后冻结。当前 `predict` 是把 prior 的潜变量均值送入非线性 decoder，不自动等于完整预测分布的数学期望；宜称“prior-mean latent 的确定性输出”。[estimation_model.py:25–35](../../src/patrol_rsi/estimation_model.py)、[history_context](../../src/patrol_rsi/estimation.py)。

若采用 30 秒刷新、其余端点保持／同化，360 帧评分应使用**实际部署输出**，同时报告刷新时的原始网络误差及调用数。不能拿每 30 秒的模型预测与每 5 秒名义估计无说明混成“同频单步模型精度”；固定路径同数据估计对照可统一到 30 秒端点。若改为每 5 秒推理，协议及计时随之改变。[patrol_task.py:96–112](../../src/patrol_rsi/patrol_task.py)。

现有 `temperature_metrics` 只明确检查预测形状与预测有限性，新汇总还应校验 truth 有限、mask 形状精确一致、权重有限非负且有效权重和为正、时间网格和 rack 顺序相同；不要依赖 NumPy 的意外广播或 NaN 排除。这是新实现的检查要求，不改变旧指标。[estimation.py:128–146](../../src/patrol_rsi/estimation.py)。

## 5. 异常分母、等待、年龄、成本和违规

### 5.1 沿用评价器语义，单列 cue 与误报

当前标签为热温度 >65°C、电气接触温度 >60°C、Pod 流量 <33.6 kg/s、自控公开传感器与物理温度的 Pod 平均误差绝对值 >1°C。只保留连续至少 3 个 5 秒正标签的异常段；异常可延迟出现、恢复后持续，且一个注入故障可产生多专业、多段异常。分母必须来自完整物理轨迹的标签，不等于注入次数、不等于事件账本数，也不等于测量次数。[inspection_metrics.py:9–51](../../src/patrol_rsi/inspection_metrics.py)。

同一 `(seed,condition)` 的所有方法／checkpoint 应有相同异常段键和后果权重，按 `(task_id,onset_s,end_s)` 比对后才汇总。跨 checkpoint 重复评价不能把同一异常复制成新的独立分母；可报告“3 个模型下平均确认段数／唯一物理异常段数”，同时给每模型原始整数计数。

有效确认必须是专业测量完成、alarm 为真、且该完成端点属于同一正标签段。当前标签 index=`int(completion_s/5)-1`，对连续保留段为 `onset_s < completion_s <= end_s`；恰在报告 onset 的报警不能自动记为确认。不要因新日志更细就悄悄改成闭区间定义。[inspection_metrics.py:54–70](../../src/patrol_rsi/inspection_metrics.py)、[既有端点核查](report-comparison-metrics-20261103.md)。

healthy 和 healthy＋cue 是否零异常由物理标签确认，不按名称假定。若某回合零异常，确认率与异常等待为 `null/NA`，同时报告 `0` 异常段、正常测量、误报、额外派单和成本；不能填“0%确认率”或把它当漏检。cue 只是公开风险提示，不能充作真异常或有效确认。

至少区分：①风险 cue／事件；②专业 alarm；③真正首次确认异常段。当前 `false_measured_confirmations` 是 alarm 落在**逐 bin 负标签**的次数；落在不足 15 秒的短暂正标签上会既不是该误报，也不确认任何保留段。新包宜另报“短暂正标签 alarm”和“保留段外 alarm”，不要把所有未确认 cue 均称物理误报。[inspection_metrics.py:36–79](../../src/patrol_rsi/inspection_metrics.py)。

### 5.2 等待是受异常寿命限制的描述指标

保留 `d_i=(首次确认时刻，未确认则 end_i)−onset_i`，后果权重 `q_i=固定任务权重×(1+段内平均超阈严重度)`，每回合 `Σq_i d_i/Σq_i`。零分母记 NA；必须同时给漏检率与异常持续时间。短异常漏检的截尾等待可能小于长异常成功确认的等待，所以这不是跨条件无条件的“平均检测时间”，也不是仅检出段平均；同物理过程内配对比较最容易解释。[inspection_metrics.py:36–78](../../src/patrol_rsi/inspection_metrics.py)。

### 5.3 年龄和硬约束分别核算

沿用固定资产重要度、任务期限归一、完成时年龄清零、初始虚拟起点 0 和终端积分边界 H 的连续时间年龄：

\[
I=\frac{\sum_j a_j\int_0^H\min\{(t-L_j(t))/D_j,1\}\,dt}{H\sum_j a_j}.
\]

从每个方法自己的完成时刻作解析积分；不能用公共遥测清零。该分数截断于 1，无法替代硬重访违规检查。违规按任务回合统计初始／中间／终端最大间隔 >`D_j+1e-9`，并另列非法资格、重复预约、预算越界、证书拒绝和运行失败。[既有精确定义](../source-data/report-comparison-metrics.json)、[exact_task_gaps](../../src/patrol_rsi/coverage_plan.py)。

成本同时报告 travel m、service s、idle s、专业完成数、额外**派单**数、额外**完成**数、事件正常测量数和未完成在途数。相同额外访问上限代表同权限上限，不代表实际等成本；Tour 配对移动百分比先逐过程算再平均。预算以派单为准，不能在回合末只数已完成访问而漏掉在途消耗。[risk_response.py:127–178、213–224](../../src/patrol_rsi/risk_response.py)。

## 6. 逐步耗时与预算记账

建议同时保存以下互不混淆的范围：

|计时|范围与分母|
|---|---|
|估计器调用延迟|输入 tensor／设备搬运、prior 推理、输出回传及反归一化；另存纯模型 forward；按实际调用计数|
|在线状态更新|遥测／已完成测量同化、特征构造、必要的网络推理、风险更新；每 5 秒端点含未刷新时的真实工作|
|调度延迟|候选生成、返回证书、预约／预算过滤、FIFO／Greedy 评分或全部 PPO actor 调用，以及动作整理；按 team 决策步和 individual call 均留计数|
|控制总延迟|在线状态更新与本次调度的完整墙钟时间，避免把嵌套 timer 再相加；不含物理真值预计算、离线评价、压缩与写盘|
|回合与训练总耗时|实际端到端墙钟、物理生成、训练、验证、最终评价和产物写盘分别列；用于复算真实研究成本|

CPU 固定线程、相同硬件／dtype／单设施 batch，神经模型 `eval()` 和 `inference_mode()`；保存冷启动／加载时间，预热仅用训练或开发输入。GPU 计时必须正确同步，单纯 `perf_counter` 包住异步 kernel launch 不是推理完成延迟；可以用 PyTorch `benchmark.Timer` 或显式同步的墙钟。保存预热数、测量重复数、设备、Torch／NumPy、CPU 线程和运行顺序。官方计时工具明确考虑预热、线程及异步设备同步。[PyTorch 官方 benchmark 文档](https://docs.pytorch.org/docs/stable/benchmark_utils.html?highlight=all)。

报告 p50、p95、最大值、总时间和调用数；“每次刷新 ms”与“摊到每个 5 秒决策步的 ms”同时给出。无神经调用的方法，其神经调用数是 0、每次神经推理延迟为 NA，状态更新和调度时间仍实际计量。当前 `history_estimator_inference_s` 仅计可选 predictor 的函数调用，未覆盖上述全流程，不能沿用它代表总在线成本。[patrol_task.py:103–108](../../src/patrol_rsi/patrol_task.py)、[inspection_metrics.py:87](../../src/patrol_rsi/inspection_metrics.py)。

新的记账字段至少拆成 `physical_trace_generations`、`episode_attempts/succeeded/failed`、`estimator_inference_calls`、`policy_actor_calls`、`neural_training_runs/updates`、`LLM_calls`。本轮可以 `LLM_calls=0`，但 CVAE／PPO 的训练与推理是实际神经模型执行，不能继续把总 `model_calls` 写 0。训练数据复用和失败尝试也纳入预算。

## 7. 统计汇总、负结果和停止规则

建议冻结一个小的主比较集合：固定 Tour 观测下的 CVAE 对名义估计 WRMSE；四个故障条件下 FIFO／Greedy／PPO 的确认与成本；FIFO、Greedy 下更换估计器。其他 R²、年龄、逐专业、相位及 healthy cue 负担为明确的辅助结果。不要在测试后从所有指标选一个显著方向宣布全面领先。

所有最终方法在同一 seed block 内配对。先得到每回合指标，学习方法先对全部预定训练 seed 平均，再在每个过程 seed 内按冻结条件权重汇总，最后形成 12 个配对差值。主要区间可对 **12 个完整 seed block** 作 10000 次配对 bootstrap，保留每块全部条件及全部方法；每次不能独立重抽异常段、帧或柜。报告均值差、95%区间及正／零／负块数，逐条件原值不隐藏。现有评价脚本已采用过程 seed cluster 的原则，新包需独立实现相同层级，不把旧 12 个 seed 补入样本。[event_validation.py:90–135](../../src/patrol_rsi/event_validation.py)。

该主区间条件于这 3 个冻结训练模型，只表达测试过程变化。另列每训练 seed 的结果、范围和训练失败；若补充交叉重采样模型 seed，应每次在全体过程上共同重抽模型 seed，不能把 `12×3=36` 个单元当独立。3 个训练 seed 仍不足以精确估计训练总体分布，12 个过程块也未作功效校准；结果保持探索性有限样本解释。[Agarwal 等原始研究](https://papers.nips.cc/paper/2021/hash/f514cec81cb148559cf475e7426eed5e-Abstract.html)。

若报告检验 p 值，预先限定比较族及多重比较处理；不必用一串 p 值替代效应大小和区间。若只报告描述区间，则明确“探索性区间”，不事后拿区间是否跨零决定换种子、改超参数或追加预算。确认率给原始分子／分母，但其区间仍按过程块重抽，不按异常段作独立二项分布。

停止规则建议：

1. **开发阶段可停**：数据／接口／数值不合法、预计预算无法完成或训练非有限；保留失败日志与实际消耗。按冻结的开发指标和 patience／最大更新数停止训练，仍保存所有已运行 seed，不能只保留成功 seed。
2. **最终测试不作效果早停**：一次性运行冻结清单。若出现资格、预算、返回证书或过程 SHA 错误，可因实现无效暂停；不把错误回合删掉后继续汇总胜率。
3. **代码修复后有身份**：保留修复前失败及原因，对所有受影响方法／条件一致重算。若修复由已见 test 效果引导、或改变科学设置，旧 test 已用于开发；后续称修订／探索分析，新的独立确认需另行冻结，不能伪装“从未见过”的最终集。
4. **负结果照交**：CVAE 误差更大、PPO 不及 FIFO、动作与 FIFO 完全相同、cue 增加成本、部分条件零异常或成本超限，都直接报告。训练曲线或“训练成功”不替代任务收益；本轮也不证明 LLM／反馈或 RSI。

## 8. 已有检查点与训练资料的可用性核查

本次只读读取本地归档成员，并重新计算下列权重 SHA；未加载模型推理。**可用**在此指权重文件和训练来源可核对，不指已通过新受保护事件任务的兼容性、精度或收益验证。

|历史材料|本次核实|新补充可怎样使用|
|---|---|---|
|M10 `cvae_current/history--seed-0/1/2.pt`，共 6 份|六份实际文件均与归档 `evidence/training.json` SHA 一致；每份 26145 参数、2000 更新、batch 1024；current/history 对照；源归档确认为逐柜 MLP-CVAE|可作历史 MLP-CVAE 对照或数据接口参考，不能冒充新 CVAE-U-Net|
|M10 训练资料|归档 index 有 224 train 条件回合（8 个物理 seed：100–107）、56 validation 回合（seed 200、201）；14 个原子故障／healthy×2 control；训练脚本只打开 train/validation，验证选 checkpoint|可参考因果特征、数据谱系与选择方式。224 不是 224 独立 seed；新最终 seed 不与这些及历史测试 seed 重合|
|M11 `nominal/history-seed-0/1/2/selected.pt`，共 6 份|六份权重均与各自 training.json SHA 一致；每份 48 回合、17232 team steps、192 PPO full-rollout epochs；含 scarce/provisioned、feedback/fixed_commands；history 依赖同一 M10 checkpoint|可作旧任务重现／初始化敏感性对照，不能直接当新同权限 PPO；应在新事件候选接口上重新训练|

直接来源：[M10 权重目录](../../.work/m10/selected-weights/)、[M10 交付包](../../.work/m10/delivery-v2.tar.gz)内 `evidence/training.json` 与 `evidence/training-data-index.json.gz`、[M10 源包](../../.work/m10/source-v2.tar.gz)内 `estimation_model.py / estimation_data.py / m10.py`、[M11 权重与训练日志](../../.work/m11/selected-policies/)、[M11 权重索引](../../.work/m11/selected-policy-weight-storage.json)、[M11 源包](../../.work/m11/source-v2.tar.gz)。

M10 源包的冻结拆分另列 test seeds 300–302、GW seeds 400–402；本次只读核查的是源中定义与 train/validation 索引，未重新执行那些历史测试。M11 的 3 个 history PPO 均绑定 M10 history seed-1 权重 SHA `2dc8399ee79fed254fb4b12f39b95b65a98d2ec6f942155c158c31d76df21caa`，因此不能声称这 3 份同时覆盖了 3 个估计器训练 seed。

原论文 §4.7 的 VAE-U-Net 处理稀疏重要度图与访问 mask，包含卷积上下采样、prior/posterior 和 VGG perceptual loss；本任务温度场、柜布局、服务时长和硬返回限制均不同。新网络若采用较小 U-Net、温度／历史／物理特征或省略 perceptual loss，应逐项写成领域适配，并保存实际网络、参数量、损失、训练曲线和 checkpoint。规则格点需固定柜→空间映射并说明跨 Pod 间距的近似，不能随意 reshape 128 个柜后声称精确保留真实机房几何。[原文 §4.7](../../runs/feedback-study-preparation/reference.txt)、[本任务柜坐标](../../src/patrol_rsi/facility_observation.py)。

本次读取的关键原件身份：

|文件|本次 SHA256|
|---|---|
|`paper/source-data/report-comparison-metrics.json`|`fdc96ef31db0492842823a240422e158bdeaf4cb785a1e1875468c27508c40ce`|
|`.work/m10/source-v2.tar.gz`|`5696d2a19cda53fc71be4699136828c24d4418540a32f1cf50451ad27f9ae88c`|
|`.work/m10/delivery-v2.tar.gz`|`ff1a73c8d2652e2e53bacb571d700285ac4f00fd488fc769d4c05f57123bb6e7`|
|`.work/m11/source-v2.tar.gz`|`4538d789ea54ed959bf1cd8945326140e1532caade523f59f7bc4dc0564a50ee`|

## 9. 最终 review 应能直接复核的交付条件

- 冻结协议包含新 split／seed／位置／相位／duration、方法精确名称、训练与 checkpoint 选择预算、共同观察／动作权、主比较及统计单位；旧封存计数独立呈现。
- 每一最终行能连接到过程 SHA、checkpoint SHA、完整 5 秒估计／真值／mask、动作和测量时间线；同过程异常分母及权重逐方法一致。
- 具有“固定观测估计器比较”和“完整闭环系统比较”两套结果，前者不冒充新物理独立样本，后者不单归因为模型精度。
- 温度误差、确认与等待、固定资产年龄、成本、误报／cue 负担、硬违规和逐步耗时都能从原件重算；NA、负 R²、零异常及失败都保留。
- 全部预定方法与模型 seed 的完成／失败账目齐全；论文语言只能支持已运行的领域适配与条件内结果，不能升级成原论文复现、现场验证或 RSI 成功。

这些是新结果可审查的证据要求。是否有收益应由冻结后的一次最终测试决定，不预设神经方法必须获胜。
