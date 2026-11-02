# 自阅报告的方法公式与主过程原始依据核查

日期：2026-11-03。此次仅解析已保存的源码、协议和gzip记录；未运行仿真、估计器重放、训练或模型调用。当前研究状态依据 `docs/RESEARCH.md`、`docs/NEXT.md`：机制讨论稿已收束，没有新的主动研究执行。

## 1. 主机制实际使用哪条估计与风险链

主验证的12个 `group=coupled` 条件在冻结协议中均设 `estimator=nominal`、`control=feedback`、`resources=provisioned`、温度遥测噪声标准差 `noise_c=0.2`。`FixedPatrolTask` 初始化 `ObservationState`，并以 `phased_trace` 提供已经规定发生相位的物理过程；`ObservationState.update` 先调用 `FacilityObserver.update(packet)`，再按完成记录调用专业测量校正。因此实际调用链是：

`ResponseTask → FixedPatrolTask → ObservationState → FacilityObserver`，风险则由继承的 `ActiveInspection.public_risk` 计算。

依据：`evidence/event-validation/final/protocol.json` 的 `cases[group=coupled].spec`；[patrol_task.py](../../src/patrol_rsi/patrol_task.py) 第27–74、79–112行；[estimation.py](../../src/patrol_rsi/estimation.py) 第20–46行；冻结运行源 `runs/event-validation-amended-20261102/source/risk_response.py` 第66–99行。

这里应区分两个事实：**`FacilityObserver` 的温度递推仍在主机制中使用；其 `readout` 中的另一种混合严重度不是主机制的任务风险分。** 主机制采用 `ActiveInspection.public_risk` 第93–115行按专业分别形成风险；不能把 `FacilityObserver.readout` 第118–129行的 `0.45×热 + 0.20×接触 + 0.25×功率缺口 + 0.10×流量缺口` 写作本次热任务公式。名义模式的风险也没有模型分歧、VAE输出、资产权重或测量年龄加项；分歧另行返回，名义模式为零。[active_inspection.py](../../src/patrol_rsi/active_inspection.py) 第93–115行；[facility_observation.py](../../src/patrol_rsi/facility_observation.py) 第112–134行。

相关当前源码 `active_inspection.py`、`estimation.py`、`facility_observation.py`、`facility.py`、`aisles.py`、`patrol_task.py`、`inspection_metrics.py` 的文件SHA-256均与主验证 `seal.json.source_sha256` 及继承记录的 `prior/source` 相同。当前 `process.py` 增加了允许的持续时间值，当前 `risk_response.py` 增加了后续规则接口；本笔记对这两份文件的历史运行依据使用封存 `source/`，不将当前文件身份冒充运行时身份。哈希和路径已保存至 [report-method-evidence.json](../source-data/report-method-evidence.json) 的 `sources`。

## 2. 可直接用于正文的六行公式

令 \(i=0,\ldots,127\) 为机柜，\(p(i)=\lfloor i/8\rfloor\) 为设备组，\(k\) 为5秒步；\(\mathcal M_k\) 是本步完成合格热测量的机柜集合。温度差以K计，温度读数以°C计。主机制的名义估计与热任务风险可写为：

\[
\begin{aligned}
\widehat T_{i,0}&=50\,{}^\circ\mathrm C,\qquad \mathcal S_T=\{0,4,\ldots,124\};\\
\widehat F_{p,k}&=\begin{cases}F^{\mathrm{last}}_{p,k},&\text{预测前已有该组流量测量},\\48u_{p,k}\;\mathrm{kg/s},&\text{否则},\end{cases}\qquad \widehat f_{i,k}=\widehat F_{p(i),k}/8;\\
\widehat G_{i,k}&=12\;\mathrm{kW/K}\left(\frac{\max(0,\widehat f_{i,k})}{6\;\mathrm{kg/s}}\right)^{0.8};\\
\widehat T^-_{i,k}&=\widehat T_{i,k-1}+\frac{5\;\mathrm s}{800\;\mathrm{kJ/K}}\!\left[P^{\mathrm{del}}_{i,k}-\widehat G_{i,k}(\widehat T_{i,k-1}-T^{\mathrm{sec}}_{p(i),k})-0.12\;\mathrm{kW/K}(\widehat T_{i,k-1}-28\,{}^\circ\mathrm C)\right];\\
\widehat T_{i,k}&=\begin{cases}z^{\mathrm{mobile}}_{i,k},&i\in\mathcal M_k,\\z^{\mathrm{fixed}}_{i,k},&i\in\mathcal S_T\setminus\mathcal M_k,\\\widehat T^-_{i,k},&\text{否则};\end{cases}\\
r^{\mathrm{thermal}}_{i,k}&=\min\!\left\{4,\;\frac{[\widehat T_{i,k}-65\,{}^\circ\mathrm C]_+}{20\;\mathrm K}+\frac14\!\left(1-\frac{P^{\mathrm{del}}_{i,k}}{\max(P^{\mathrm{req}}_{i,k},10^{-12}\;\mathrm{kW})}\right)\right\}.
\end{aligned}
\]

其中：

- \(\widehat T\)：每柜保存的名义温度估计，初值50°C是估计器假设，不是隐藏真值；\(\widehat T^-\) 为当前步量测覆盖前的一步预测。
- \(u\)：公开的组泵命令，无量纲，不是故障作用后的实际泵速；\(\widehat F\) 是组总流量，\(\widehat f\) 是按8柜均分后的单柜流量，单位kg/s。\(F^{\mathrm{last}}\) 指**本步固定流量包已处理、而本步移动测量尚未写入时**的最近可用值。
- \(\widehat G\)：名义冷板热导，单位kW/K；\(T^{\mathrm{sec}}\) 是公开的该组二次供液温度；\(P^{\mathrm{del}}\)、\(P^{\mathrm{req}}\) 是每柜公开实供和请求IT功率，单位kW。800 kJ/K为每柜热容量，0.12 kW/K为环境换热系数，28°C为环境温度；这些数值是合成研究参数。
- \(z^{\mathrm{fixed}}\)、\(z^{\mathrm{mobile}}\) 为固定遥测及合格移动测量；\([x]_+=\max(x,0)\)。\(r\) 无量纲，表示合成风险提示，不能写成故障概率或百分比。

公式依据：[facility_observation.py](../../src/patrol_rsi/facility_observation.py) 第50–61、69–88、92–109行；[facility.py](../../src/patrol_rsi/facility.py) 第19–59行；[active_inspection.py](../../src/patrol_rsi/active_inspection.py) 第93–115行。

必须保留两个实现细节：第一，热超限项只截断负值，**没有先在2处截顶**；最后是总分在4处截顶。第二，功率缺口项确实存在，源码没有另加 `max(gap,0)`；分母的 `1e-12` 仅用于防止除零。功率请求发生在本地节流之前，实供功率含节流和供电可用性，因此功率缺口不专指某一种馈电故障。[active_inspection.py](../../src/patrol_rsi/active_inspection.py) 第99–115行；[facility.py](../../src/patrol_rsi/facility.py) 第151–155、161–190行。

## 3. 32个固定测温点怎样支持128个估计

固定温度遥测位置为 `rack_index % 4 == 0`，即0、4、8、…、124，共32柜、每组2柜；固定组总流量遥测只覆盖偶数组0、2、…、14，共8组。每5秒收到的包还包括全部128柜的请求/实供功率、16组泵命令、16组二次供液温度及共享一次供液温度。温度递推实际使用的是每组二次供液温度；共享一次供液温度虽在公开包内，不直接代入上述每柜一步式。[facility.py](../../src/patrol_rsi/facility.py) 第256–269行；[estimation.py](../../src/patrol_rsi/estimation.py) 第15–17行；[facility_observation.py](../../src/patrol_rsi/facility_observation.py) 第92–109行。

因此128柜并非由32个读数做空间插值。估计器为全部128柜保存独立温度状态，先用公开功率、同组供液温度与名义热平衡各自向前推进一步，再将本步32个固定温度位置替换为读数，最后将本步完成的合格热检查位置替换为移动读数。移动与固定同刻覆盖同一柜时，移动测量最后写入。未被本步测量覆盖的柜继续沿预测推进。固定温度遥测标准差在12主过程中为0.2°C，移动热测量的噪声标准差为0.1°C。[estimation.py](../../src/patrol_rsi/estimation.py) 第28–46行；[patrol_task.py](../../src/patrol_rsi/patrol_task.py) 第89–99行；封存 `source/process.py` 第85–95行。

流量有“最近有效测量保持”的细节：在温度预测前，先更新本步固定流量点；从未取得流量测量的组才用 `48×泵命令` 推算。一旦固定遥测或合格移动检查留下流量值，该值会保持到下一次流量测量，不会每步被泵命令重新覆盖。本步移动流量检查写入发生在温度预测之后，影响后续步的温度预测。估计式也不读取隐藏的冷板劣化乘子、故障标签或未公开温度，所以它是名义模型推算，不是精确故障辨识。[facility_observation.py](../../src/patrol_rsi/facility_observation.py) 第84–86、92–109行；[estimation.py](../../src/patrol_rsi/estimation.py) 第36–38行。

## 4. 470秒两项风险能核对到哪一级

封存原件：`runs/event-validation-amended-20261102/p01-coupled-fifo.json.gz`；文件SHA-256为 `ddd471aef1065ea1030051073fe77e52a26849d5d5e0c844ed8b9827eb2a940d`，已与 `evidence/event-validation/final/local-artifacts.json` 的同名条目核对。

|任务|470秒原件总风险|总分所在JSON字段|首次提示|核对状态|
|---|---:|---|---:|---|
|热检查10|0.008122894711187073|`/decisions/387/candidates/2/public_risk`|450 s|总分与队列时序可核对；组成项未保存|
|热检查8|0.06563121182584858|`/decisions/387/candidates/1/public_risk`|455 s|总分与队列时序可核对；组成项未保存|

该决策的 `time_s=470`、`agent=0`、`routine_head=0`、`selected=10`；两项的 `certificate.ok` 与 `budget_allowed` 均为真。可核对FIFO按更早提示选择10号，不能由此声称0.00812全由温度项组成，或把两个数换算为精确温度。

**不能从这份保留原件逐项重算两项分数。** 文件没有保存470秒FIFO的 `predicted_temperature[10/8]`，也没有保存该步 `current_packet.public_delivered_it_kw[10/8]` 和 `public_requested_it_kw[10/8]`。它保存的是总风险、调度证书、动作、完成测量和过程元数据，没有当步公开包、估计器状态或 `risk_components`。三项输入缺失，热超限与功率缺口两项不能唯一分解。进一步核对一步递推还需要上一估计值、有关流量/泵命令/供液温度和固定测量历史。过程数字摘要用于身份核验，不能代替这些数值。

Tour记录有其自身的 `local_decisions.public_tasks`，其他工程案例也有回看帧；这些属于不同检查轨迹或过程，不能替代FIFO在470秒的估计状态。本次没有运行重放，也没有从总风险反推温度。导出的 [report-method-evidence.json](../source-data/report-method-evidence.json) 只保留可核对的原件总分、字段路径、源SHA与缺失清单；`risk_470s.component_recomputation_status` 为 `not_recomputable_from_retained_inputs`，缺失输入及组成项为 `null`，不表示零。

## 5. 12个主过程的实际注入条件

下表的机柜、设备组均按代码从0编号；如正文采用“第几组”，须给组号加1。`fault_rack` 在本场景用于确定设备组，两种故障都作用于该组，不是只损坏该锚点机柜。场景 **A+C** 的完整名称为 `aux_feeder_loss+cdu_fouling`：组辅助馈电可用乘子降为0.05，CDU换热乘子降为0.20；后者乘在基准有效度0.85之上，不是直接把基准参数改成0.20。组合器对这些独立乘子逐项相乘。[facility.py](../../src/patrol_rsi/facility.py) 第115–149、182、211行；封存 `source/process.py` 第15–37、101–107行。

|过程|种子|故障锚点机柜|设备组（影响柜号）|发生时刻/s|持续时间/s|结束时刻/s（不含）|场景|
|---|---:|---:|---|---:|---:|---:|---|
|p00-coupled|101003|0|0（0–7）|150|180|330|A+C|
|p01-coupled|101040|9|1（8–15）|335|180|515|A+C|
|p02-coupled|101077|20|2（16–23）|520|180|700|A+C|
|p03-coupled|101114|29|3（24–31）|705|180|885|A+C|
|p04-coupled|101151|36|4（32–39）|150|180|330|A+C|
|p05-coupled|101188|45|5（40–47）|335|180|515|A+C|
|p06-coupled|101225|56|7（56–63）|520|180|700|A+C|
|p07-coupled|101262|65|8（64–71）|705|180|885|A+C|
|p08-coupled|101299|76|9（72–79）|150|180|330|A+C|
|p09-coupled|101336|85|10（80–87）|335|180|515|A+C|
|p10-coupled|101373|100|12（96–103）|520|180|700|A+C|
|p11-coupled|101410|117|14（112–119）|705|180|885|A+C|

来源：冻结 `protocol.json` 的 `cases` 中12项 `group=coupled` 的 `id`、`spec.seed`、`spec.fault_rack`、`spec.fault_start_s`、`spec.duration_s`、`spec.scenario`，以及对应36份 Tour/FIFO/shuffled gzip 的 `spec`、`process_metadata.configuration`。本次逐项核对协议/运行一致、文件SHA与发布索引一致；导出JSON的 `primary_processes.cases` 保存每份原件路径与SHA。

表中时间是故障乘子的注入区间，不是异常首次发生或最后消失时间。实现以步首时刻判断半开区间 `[fault_start_s, fault_end_s)`，故障后的温度状态可因热惯性持续；例如335秒起的故障首次改变335→340秒积分步。[facility.py](../../src/patrol_rsi/facility.py) 第128、157–161、216–222行。

## 6. 四专业异常的严格阈值，以及为何两类为零

|专业|事后物理异常标签|完成专业测量时的报警条件|本12过程异常段|
|---|---|---|---:|
|热|机柜代表温度 \(T_i>65\,{}^\circ\mathrm C\)|测得温度 \(z_i>65\,{}^\circ\mathrm C\)|77|
|电气|设备组接触点温度 \(T^{contact}_p>60\,{}^\circ\mathrm C\)|测得接触温度 \(>60\,{}^\circ\mathrm C\)|0|
|液冷|设备组8柜总质量流量 \(F_p<33.6\,\mathrm{kg/s}\)|测得组总流量 \(<33.6\,\mathrm{kg/s}\)|12|
|自控|设备组平均传感偏差的绝对值 \(\left\lvert\frac18\sum_{i\in p}(T_i^{sensor}-T_i)\right\rvert>1\,{}^\circ\mathrm C\)|测得 `abs(controller_sensor_error_c)>1`|0|

这些均是严格不等式：等于阈值不记异常。33.6 kg/s是本模型的组总流量界值（`0.7×8×6 kg/s`），不是每柜流量，也不是某部国家标准的报警条款。阈值依据：[inspection_metrics.py](../../src/patrol_rsi/inspection_metrics.py) 第9–32行；[active_inspection.py](../../src/patrol_rsi/active_inspection.py) 第28–35行；专业测量定义见封存 `source/process.py` 第85–95行。合成参数来源声明见 [facility.py](../../src/patrol_rsi/facility.py) 第1–4、75–79行。

事后异常段还要求标签连续至少3个5秒样本，即15秒。端点标签代表其前一5秒区间；有效确认要求合格专业完成测量报警，并与该时刻相应真值标签匹配。故障持续180秒与某一个异常段持续时间不必相同。[inspection_metrics.py](../../src/patrol_rsi/inspection_metrics.py) 第36–70行。

12个主条件只注入辅助馈电和CDU复合扰动，没有注入 `dc_contact_hotspot`、传感偏置或控制器冻结。辅助馈电故障影响泵速与冷却，**不等同于电气评价通道的“接触点过热”**；本批也没有传感偏置。自控标签当前只检测组平均传感偏差，并未将“本地控制正在节流”本身定义为自控异常。因此封存评价中只有热和液冷异常，不能按“故障涉及供电和自控反馈”便计成电气或自控异常。实现允许电气、自控任务的公开风险因同组热风险而上升，但那是跨系统确认提示，不改变它们各自的真值阈值。[facility.py](../../src/patrol_rsi/facility.py) 第133–143、163–190行；[active_inspection.py](../../src/patrol_rsi/active_inspection.py) 第103–114行；[inspection_metrics.py](../../src/patrol_rsi/inspection_metrics.py) 第14、29–32行。

本次对每个过程核对三方法记录的 `(task_id, kind, onset_s, end_s)` 完全相同；12过程 `by_role.*.segments` 合计为热77、电气0、液冷12、自控0，共89段。Tour完成测量记录中的接触温度最大值为46.0467512696332°C，自控误差绝对值最大为0°C；这两项是**已完成专业测量的范围**，不是完整物理轨迹最大值。零段的直接结果依据仍是各冻结记录的 `anomaly_intervals` 与 `by_role`，不能推广成电气或自控巡检没有价值。导出JSON的 `primary_processes` 保留计数、每过程条件及原件身份，未复制完整轨迹。
