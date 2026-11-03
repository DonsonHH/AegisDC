# 新补充实验的实现接缝与行为核查

日期：2026-11-03。状态：**只读设计核查，尚未实现、运行或验证本文建议**。本次只读取源码、已有协议与研究记录，仅写本文件；没有调用项目环境、仿真、训练或模型。最新用户指令已经授权真正补足缺项；本文建议将补充实验作为独立新包实施，旧封存包的原始记录、协议、源码快照和结论继续保留。

核查时工作树 HEAD 为 `f35b172ee4d557a099680a8411fe89d5b324e55e`。下述行号指本次读取的原始源码；新实现应记录旧依赖和新模块各自的字节 SHA，不能仅记录 HEAD。

|原始依赖|本次读取的 SHA256|
|---|---|
|`risk_response.py`|`c8f28d8bc70f30ce84811848fa95d9c4286cbb9fb983b7d6b0e7a3985090bc4e`|
|`patrol_task.py`|`af15485b34a8d04d9b21bdeeb5bb746b100799b167f7b7c975a344dce7009335`|
|`active_inspection.py`|`8985435aaecc8a099f6e61bc2faac9d940a87b75025938ad8f49b847e31322cc`|
|`estimation.py`|`3b613b66de55a8b88a91be98c34d0bca2a817459abac54de432f0884d4254492`|
|`inspection_model.py`|`3d868ab07e4e4b443b0263e8ecaf874d2987e93c2f49a660209b0ea3f1e9976b`|
|`coverage_plan.py`|`21390989b7828655404b10d45c9ad252a48722438ac669fd7cb4b597d64403a2`|

## 1 可以直接复用的接缝

|职责|真实实现与边界|新包建议|
|---|---|---|
|公开观测|`ObservationState.update`仅接受冻结的10字段遥测 schema，先摄入遥测，再摄入已完成专业测量；拒绝未来完成事件。`features`输出每柜14维公开特征。[S1](../../src/patrol_rsi/estimation.py#L12)，原始行12–17、28–46、48–69|保留观测对象与特征定义；模型只收数组，不接收环境、trace、scenario、seed或完整带故障参数的config|
|物理先验|`FacilityObserver.update`按公开供电、二次供水和可获流量推进名义温度，当前遥测与专业热测量会覆盖对应位置。[S2](../../src/patrol_rsi/facility_observation.py#L69)，原始行69–109|将它作为同时间名义基线，学习残差；每个tick只更新一次|
|任务/人员|专业资格由`eligible`检查；任务有服务时长；固定任务将每人`allowed`收紧为本人tour。[S3](../../src/patrol_rsi/facility_observation.py#L23)，原始行23–24；[S4](../../src/patrol_rsi/patrol_task.py#L44)，原始行44–48|保留固定所属、专业和服务完成语义；学习策略只能排序合法候选|
|返回证书|`ResponseChecker`检查本人资格、预约与立即完成的1800秒边界；`ReturnPlan`检查候选及随后完整循环的期限可行性。[S5](../../src/patrol_rsi/risk_response.py#L53)，原始行53–64；[S6](../../src/patrol_rsi/coverage_plan.py#L12)，原始行12–73|复用同一证书，不以PPO旧`guard`代替|
|事件账本|`RiskEpisodes`使用公开风险正值上升沿、120秒TTL和实际测量闭合。[S7](../../src/patrol_rsi/risk_response.py#L14)，原始行14–43|复用，并保存事件身份、过期及晚测结果|
|实际执行|`ActiveInspection.step`先验证全部自由人员选择，再推进5秒；移动与服务都完成后才产生专业测量、更新检查年龄。[S8](../../src/patrol_rsi/active_inspection.py#L175)，原始行175–238|保留执行核，新增统一候选/派单接口满足它的验证约定|
|策略网络与PPO|`TaskPolicy`是16维候选共享actor、8维公开critic；`ppo_update`按团队5秒步聚合当步各人员log-prob，GAE和4轮clip更新。[S9](../../src/patrol_rsi/inspection_model.py#L15)，原始行15–30、61–106|可以复用网络/更新器；必须适配候选特征与派单，不能直接把旧`policy_decisions`接到事件环境|
|结果评价|`evaluate_episode`在执行结束后读取真值；`exact_task_gaps`包含0秒到首次完成及末次完成到1800秒。[S10](../../src/patrol_rsi/inspection_metrics.py#L54)，原始行54–99；[S6](../../src/patrol_rsi/coverage_plan.py#L76)，原始行76–87|保留确认/等待定义，再独立增加同时间全场温度误差与耗时记录|

## 2 必须先处理的真实陷阱

### 2.1 构造与matched5s更新

1. **`ResponseTask`不能直接接history predictor。** 它在原始行72固定调用`super().__init__(spec,None)`，而`FixedPatrolTask`原始行58–60拒绝没有predictor的history模式。构造后再注入predictor，也不能补回最初观测的正确初始化。[S5](../../src/patrol_rsi/risk_response.py#L67)，原始行67–96；[S4](../../src/patrol_rsi/patrol_task.py#L56)，原始行56–74。
2. **父类构造会动态调用子类`_update`。** `FixedPatrolTask.__init__`原始行72调用`self._update([])`；此时`ResponseTask`的`risk_episodes/checkers/dispatches`还未建立，`certificate_evaluations`也要到父构造原始行75才有。新`_update`需要的模型、历史、计数与输出容器必须预先建立；构造中不能访问尚不存在的事件账本或证书统计。父构造还会重置`frames`与`estimator_calls`，不能误以为构造前同名列表会保留。[S4](../../src/patrol_rsi/patrol_task.py#L64)，原始行64–77。
3. **原`refresh_s`不接受5秒。** 只接受30/60/120；原`_update`每30秒取一帧，取4帧并按refresh条件预测。不能把参数改成5后声称沿用旧实现。[S4](../../src/patrol_rsi/patrol_task.py#L18)，原始行18–24、96–112。
4. **不能先调用父`_update`再额外更新`ObservationState`。** `FacilityObserver.update`含一次`dt_s`物理积分，重复摄入同一packet会重复推进名义先验。新matched5s更新应一次完成：清风险缓存→packet→state.update→当前公开特征/先验→因果历史→推理→fresh覆盖→保存输出。[S2](../../src/patrol_rsi/facility_observation.py#L92)，原始行92–109。
5. **预测后仍须校正当前已测位置。** 原核以`temperature_stamp == clock`覆盖模型温度；该mask包含当前合法遥测与专业完成。先预测后覆盖可保证网络不会推翻当前实际读数。`state.update`内部先遥测后专业完成，同一目标同一tick时专业读数后写。模型输出不能改变`last_inspection/ever/thermal_counts`或清除专业义务。[S1](../../src/patrol_rsi/estimation.py#L34)，原始行34–38；[S4](../../src/patrol_rsi/patrol_task.py#L111)，原始行111–112；[S2](../../src/patrol_rsi/facility_observation.py#L74)，原始行74–88。

最小可行结构：新模块里的`SupplementTask(ResponseTask)`可以**显式调用`FixedPatrolTask.__init__(self,spec,predictor=...)`**，然后显式初始化原`ResponseTask`的响应字段，避开其固定None参数；只在新模块覆盖matched5s `_update`、统一候选、选择及派单。此建议会复制一小段响应初始化，需在新模块说明所依赖原始行并测试字段完备性。不要通过伪造`estimator='nominal'`的协议后暗中换为history来绕过构造检查。

### 2.2 选择、预算与派单记账

1. **旧事件`options`的16维特征全零。** 直接使用`policy_decisions`时，所有候选的actor输入相同；网络无法按风险、路程等区分候选。[S5](../../src/patrol_rsi/risk_response.py#L107)，原始行107–114。
2. **绕开`choose`会丢失派单记录。** `choose`写`pending_dispatch/dispatches`；`step`在完成时必须`pop(event['agent'])`并检查证书完成时刻。仅调用旧`policy_decisions`然后`env.step`会在完成时缺记录。[S5](../../src/patrol_rsi/risk_response.py#L165)，原始行165–195；[S9](../../src/patrol_rsi/inspection_model.py#L33)，原始行33–58。
3. **原`options`不含额外访问预算过滤。** 预算在`choose`原始行127–130和`step`原始行173–175处理。若预算用尽、例行头不合法而只剩证书合法事件，`choose`会选None，但`ActiveInspection.step`调用`options`后仍见候选，按“不能无故空闲”拒绝。新包应令候选枚举、None合法性与step验证使用相同预算语义，而不是只在actor外遮mask。[S5](../../src/patrol_rsi/risk_response.py#L107)，原始行107–130、172–177；[S8](../../src/patrol_rsi/active_inspection.py#L181)，原始行181–196。
4. **全局12次预算必须算同一tick的计划量。** 原`planned_extras`避免多个自由人员共同超支；预算在派出时收费，不是在完成时收费。例行头刚好也是事件时不算额外访问。[S5](../../src/patrol_rsi/risk_response.py#L116)，原始行116–130、162–178。
5. **人员选择顺序应共同固定。** 原`choose`固定枚举人员，旧`policy_decisions`按tick轮转。全局剩余预算有限时，这会改变谁先获得插入机会；不能把这种顺序差异混入算法比较。[S5](../../src/patrol_rsi/risk_response.py#L119)，原始行119–130；[S9](../../src/patrol_rsi/inspection_model.py#L37)，原始行37–44。
6. **候选生成应无副作用。** 原`choose`在`step`前就写派单与决策日志；新接口宜先生成所有候选及计划，再一次验证并提交日志。失败尝试不得留假派单或推进游标。执行时选例行头才在实际完成后推进游标；插入事件后保留原头。[S5](../../src/patrol_rsi/risk_response.py#L162)，原始行162–184。

建议的单一候选接口返回`task/head/event_id/certificate/budget_allowed/features`。候选宇宙仅为当前例行头与本人pending事件；先统一施加资格、预约、立即完成边界、返回证书与全局预算，再交给FIFO/Greedy/PPO。可显式调用`ActiveInspection.options(self,i,reserved,guard=False)`构造公开16维特征，然后按证书候选ID取行；这会保留`TaskPolicy/ppo_update`的16/8维契约。[S8](../../src/patrol_rsi/active_inspection.py#L139)，原始行139–173。

无候选时返回None、不创建Categorical、不新增伪动作样本；仅一个合法候选时强制执行、单独计数。若原安全头因返回期限失效而消失，应记录原因并使异常显性化，不能一直静默空闲直至最终违规。原PPO的`guard`只是按`age_ratio+eta_ratio>=0.9`缩为一项的启发式，既不是返回证书，也不是全局预算。[S8](../../src/patrol_rsi/active_inspection.py#L168)，原始行168–172；[S9](../../src/patrol_rsi/inspection_model.py#L23)，原始行23–27、41–44。

### 2.3 时间、TTL及1800秒端点

- 原环境`tick=0,clock=5`，`done`为tick≥359；每次step先tick+1，再对新tick取测量。因此完整估计矩阵应是`t=[5,10,…,1800]`的**360帧**，实际动作步是t=5至1795的**359步**。t=1800的专业完成有效，但不再发新任务。matched5s必须在t=5已有第一次预测，不能让前25秒保持固定50°C。[S4](../../src/patrol_rsi/patrol_task.py#L66)，原始行66–74；[S8](../../src/patrol_rsi/active_inspection.py#L64)，原始行64–66、206–238。
- 移动时长沿用1 m/s的代码数值约定；证书把“距离+服务”上取整到5秒。执行同一tick剩余时间先用于移动再用于服务，因而证书与实际完成应逐条相等。不能改为移动、服务分别上取整。[S6](../../src/patrol_rsi/coverage_plan.py#L22)，原始行22–30；[S8](../../src/patrol_rsi/active_inspection.py#L211)，原始行211–237；[S5](../../src/patrol_rsi/risk_response.py#L179)，原始行179–182。
- TTL在`now > expires_s`时才过期；恰等于expiry的测量仍可正常闭合。当前合法动作并不要求`candidate_finish_s<=expires_s`，所以120秒TTL不是强制服务完成期限；原账本允许`measured_late`。持续正风险过期后不自动重开，须有新的非正→正边沿。[S7](../../src/patrol_rsi/risk_response.py#L21)，原始行21–43；[S5](../../src/patrol_rsi/risk_response.py#L187)，原始行187–195。
- step顺序为：完成测量→更新观测/预测→观察当前公开风险及过期→按完成任务闭合账本。`complete`按当前pending的task查找，旧dispatch另有原event_id。若在途原事件过期、同任务新事件又出现，需保留两者身份与晚测语义，不能用一个可变pending引用替代原event_id；同一测量关闭新事件并被记录为旧事件晚测时，也不能算两次专业完成。[S5](../../src/patrol_rsi/risk_response.py#L172)，原始行172–195；[S7](../../src/patrol_rsi/risk_response.py#L38)，原始行38–43。
- 返回证书投影的完整fallback可以超过1800秒；它证明后续循环期限，立即候选另外受1800秒限制。不要错误要求fallback全在回合内完成。终端完整性仍须从实际完成时刻重算`[0,第一次,…,末次,1800]`全部间隔；1800只是边界，不能补造完成。[S5](../../src/patrol_rsi/risk_response.py#L62)，原始行62–64、208–210；[S6](../../src/patrol_rsi/coverage_plan.py#L50)，原始行50–87。

## 3 最小正当的conditional VAE-U-Net残差估计器

**形状先写清楚：源码是128机柜×14特征的一张帧，不是128个时间帧。** 原历史输入为4帧拼接的`(128,56)`，且历史间隔30秒。建议新matched5s明确登记`H=4`、输入`(batch,H,128,14)`，时间覆盖最近15秒；初期只复制第一张已公开帧左填充，不读未来。若决定保留90秒历史跨度，应另外登记长度/抽样，不能把不同历史窗口都称“同刷新率”。[S1](../../src/patrol_rsi/estimation.py#L12)，原始行12–14、60–79；[S4](../../src/patrol_rsi/patrol_task.py#L100)，原始行100–106。

建议只在新模块实现一个小型1D U-Net：沿固定机柜索引做下采样编码、瓶颈和上采样解码，保存跨层skip；将公开历史和归一化名义温度作为条件，使用条件prior `p(z|x)`和训练posterior `q(z|x,r)`。通道/latent/参数量在协议固定。预测温度为

`T_hat_raw(t) = T_nominal(t) + 20°C * residual_decoder(x, z)`，随后当前fresh位置用真实已获读数覆盖。

训练目标可沿现有CVAE的残差均方误差加KL形式，训练标签为离线真值残差`r=(T_true-T_nominal)/20°C`，在线只用prior均值进行确定性点预测。posterior和真值只能存在于训练损失/离线评价通道；模型推理签名只接公开张量。原`TemperatureCVAE`是按柜MLP prior/posterior/decoder，**没有U-Net下/上采样和skip**，不能改名后当新方法。[S11](../../src/patrol_rsi/estimation_model.py#L9)，原始行9–35。

这里“物理先验”指公开观测驱动的名义温度作为残差基线；没有加入PDE损失时，不写为PINN或守恒约束神经网络。1D机柜顺序也不等同真实二维机房距离：源码物理位置分pod和局部柜，走廊距离另由图给出；应披露是本任务的轻量适配，而非原论文原权重/原拓扑复现。[S2](../../src/patrol_rsi/facility_observation.py#L27)，原始行27–34、92–109；[S12](../../src/patrol_rsi/aisles.py#L34)，原始行34–60。

训练/开发样本必须按**过程seed**隔离，不能随机拆同一回合的重叠时间窗；同seed的不同故障也同属一个split。估计器训练可使用预登记的Tour/FIFO等训练期公开轨迹混合，标签只用于loss；PPO训练时冻结估计器。所有scaler、checkpoint选择、早停、随机初始化种子与开发选择次数记录在新包；测试72条件不用于归一化、早停、模型筛选或失败后改超参。这是对因果历史实现和新研究目的的设计要求，不是已经完成的训练事实。

## 4 Greedy/PPO最小比较与评价

建议同一`candidates()`供所有策略使用。Greedy可沿现有公开风险/资产权重/预计耗时形式，明确固定打分与稳定tie-break；PPO复用现有16维actor、8维critic与公开reward，不改变执行边界。原公开reward由新增专业覆盖、逾期、年龄、公开风险年龄、实际报警和移动构成；不是直接优化最终真值异常段确认率。[S8](../../src/patrol_rsi/active_inspection.py#L242)，原始行242–248、276–279。若另改reward，必须在新协议写明，不将原PPO名称当作同目标保证。

PPO rollout保存**选择当时**的候选ID、特征、mask、动作索引、log-prob、公开critic输入、reward及terminal。不可在更新时重算已受后续测量影响的特征/mask。原更新器以当步多人log-prob之和计算比率，原始行66–69只在完整回合末尾使用零bootstrap；不要把多个回合简单串接成一条rollout后直接使用它。批量训练时按episode独立计算GAE，或显式加入done边界。[S9](../../src/patrol_rsi/inspection_model.py#L54)，原始行54–58、61–106。

最小归因矩阵建议包含：Tour参考；名义+FIFO、残差模型+FIFO；名义+Greedy、残差模型+Greedy；名义+受保护PPO、残差模型+受保护PPO。若预算只保留部分，结论限定为“完整管线对比”，不能把估计与策略同时变化的差值单独归因于VAE或PPO。算法/估计器变更可能改变风险上升沿数量；应同时报告事件数、过期、正常闭合、晚测、额外访问和强制动作比例。[S7](../../src/patrol_rsi/risk_response.py#L28)，原始行28–36；[S5](../../src/patrol_rsi/risk_response.py#L211)，原始行211–224。

拟定的新测试为12个新过程seed×（4种故障+健康+健康虚假提示）=72条件。新seed须与训练/开发及已有包的seen/executed seeds求交集并拒绝重叠；故障位置独立登记，避免源码默认`seed%pods`与`seed*3%8`把位置绑定seed。位置可利用现有合法`fault_rack`覆盖，开始/时长只能用`PhasedTrace`当前支持的集合，除非新包显式提供新的过程适配。[S13](../../src/patrol_rsi/facility.py#L115)，原始行115–143；[S14](../../src/patrol_rsi/process.py#L101)，原始行101–137。

每个seed的六个条件构成一个相关block；统计重采样以12个seed为单位，不能把72条件、几千异常段或360帧当独立重复。四故障分别报告，健康与虚假提示报告消耗和误报警，不用无异常条件的null等待补0。PPO若只训练一个权重种子，应明确是单次训练适配；若登记多个权重种子，训练重复与环境seed分开呈现，不能只挑最好的一次测试模型。

每条方法自己的回合至少保存以下数据：

|数据|必要定义|
|---|---|
|温度输出|同一时间轴360×128的nominal、raw residual prediction、fresh校正后prediction；fresh mask与模型调用数|
|评价真值|执行外的`rack_temperature_c`同尺寸数组或独立带SHA的共同truth文件；在线runner不能得到truth张量|
|误差|每条件RMSE/MAE/资产加权RMSE/R²及unmeasured RMSE；R²分母近零用null；先按条件计算再汇总，另报pooled定义|
|任务结果|原确认段、截尾加权等待、实际完成、移动/服务/空闲、初始/中间/终端重访gap及动作日志|
|调度与事件|完整候选/证书/预算、event_id与闭合身份、dispatch与完成对应、None原因、实际额外派出与完成数|
|耗时|名义update、网络forward、策略forward、证书、整个决策步的调用数与预热后median/p95；冷启动、硬件、线程、batch、GPU同步方式另记|

`temperature_metrics`已有误差定义可复用，但它不会自动解决同时间/同目标对齐。[S1](../../src/patrol_rsi/estimation.py#L128)，原始行128–145。旧`history_estimator_inference_s=0`只意味着该计时块未运行，不能写名义估计0ms；新报告应区分forward与端到端成本。[S4](../../src/patrol_rsi/patrol_task.py#L105)，原始行105–108；[S10](../../src/patrol_rsi/inspection_metrics.py#L87)，原始行87–90。已有研究记录明确缺少上述全轨迹和同任务模型行，此新包补的是新增数据，不能回填为旧封存实验已经测得。[已有缺项记录](report-comparison-metrics-20261103.md#L89)，原始行89–101。

评价器原始行89将`invalid_assignments/duplicate_reservations`固定写0。这些零值本身不是额外独立的安全审计证据；新包宜从记录的派单、所属、预约、证书和实际完成作独立只读核对，并保存异常/失败尝试数。[S10](../../src/patrol_rsi/inspection_metrics.py#L89)。

## 5 可控尺度工程检验

先分清物理规模和调度规模。`FacilityConfig`允许8的整数倍机柜，`ProcessTrace(racks,...)`与`AisleGraph`可接受多规模；但`FixedPatrolTask`固定`graph_for(128,'open')`、16pod权重reshape、`PhasedTrace`也是默认128，绝不能仅在spec中写3200就宣称完成大规模调度。[S13](../../src/patrol_rsi/facility.py#L61)，原始行61–73；[S14](../../src/patrol_rsi/process.py#L49)，原始行49–83、101–133；[S4](../../src/patrol_rsi/patrol_task.py#L36)，原始行36、61–67。

建议独立工程矩阵固定128/512/3200柜，固定合法健康/代表故障和开发专用seed，只测物理时间/内存/电气与能量残差、温度/流量有限性，以及公开特征更新耗时；使用对应`FacilityConfig`和`ProcessTrace`，不使用硬编码128的任务构造器。若检查大规模调度，应另初始化graph、按规模人员、全部ReturnPlan和初始积压证书，再执行实际任务；仅服务负载下界或闭合周期不够证明初始积压可行。[S12](../../src/patrol_rsi/aisles.py#L101)，原始行101–164；[S6](../../src/patrol_rsi/coverage_plan.py#L24)，原始行24–26、32–61。

人员数随`max(1,pods//16)`阶梯缩放，而不是固定18人；大规模比较必须报人数和每人义务。图路径有缓存，ReturnPlan为每个owner的tour建立两两代价；记录冷/热缓存耗时、最大缓存或峰值内存，不能只报第二次运行。[S12](../../src/patrol_rsi/aisles.py#L62)，原始行62、101–106；[S6](../../src/patrol_rsi/coverage_plan.py#L19)，原始行19–24。工程尺度检验不等于已训练128柜网络的跨规模泛化，二者单列。

## 6 实施前必须有的行为测试

以下是建议的新行为测试，**本次未执行**。优先使用小图、固定packet、替身predictor与人工事件夹具；只有涉及完整执行不变量的项才用开发seed回合，不能先消费新测试seed。

|测试|需要证明的行为|
|---|---|
|构造动态分派|history predictor在第一次t=5调用；所有 `_update`依赖先存在；无事件账本提前访问；初始输出有限且shape正确|
|单次状态推进|每tick只调用state.update一次；名义与学习组使用同一packet/5秒时钟；360输出时间戳准确|
|因果历史|更改未来帧不改变当前输出；不同回合清空历史；首帧左填充；同seed全轨迹只属一个split|
|推理真值隔离|推理签名只收公开张量；把`env.trace`替换为`DeniedOnlineTrace`仍能选择；posterior只在训练loss调用|
|fresh校正|恶意或固定偏移predictor不能覆盖当前遥测/已完成专业测量；预测不改变专业检查账本|
|候选一致性|actor所见ID/mask等于step可执行集合；非头非事件、外人任务、错误专业和已预约任务均被拒绝|
|预算边界|0、11、12上限；同tick多人竞争最后1次；budget耗尽+仅事件可完成时None正确；例行头兼事件不额外收费|
|选择原子性|非法任一人员选择导致整批执行状态不变；日志无假派单；合法学习动作有对应pending_dispatch与证书|
|游标/完成|派出未完成不前进；例行头完成才前进；插入事件不跳头；证书candidate_finish与实际完成逐条相等|
|事件生命周期|TTL恰等于/超过边界；连续高值不重开；下降后上升重开；旧事件晚测与新event_id不串；正常测量闭合不等于真实异常确认|
|空候选/强制项|无候选不构造Categorical，单候选强制动作；无选择tick保留公开reward/critic；全回合无学习样本显性报出|
|PPO更新边界|候选数可变的padding mask正确；保存动作索引对应原候选；不同episode的GAE不串接；loss/权重有限且实际有更新|
|1800端点|恰1800完成接受，1805拒绝；t1800无新派单；fallback可投影到回合后；末段gap仍纳入并可检出违规|
|关闭新功能等价|名义估计+事件关闭与原Tour动作一致；名义+原FIFO选择与原ResponseTask动作一致，差异仅允许新记录字段|
|评价/归档|每种方法truth SHA、时钟、物理参数配对相同；坏shape/NaN/记录缺失失败；旧包SHA不变；新失败也入attempt账本|

可继承的行为参考包括：原TTL边沿测试`tests/test_risk_response.py:9–28`、身份/插入/权限测试56–87、原零规则FIFO等价`tests/test_response_rule.py:72–78`、完整返回轮次与初始/终端gap测试`tests/test_coverage_plan.py:20–53`。它们提供已存在的测试意图，不代表新接入通过测试。

本报告的实施建议是：先使统一候选、初始化与5秒时序可验证，再真实训练残差模型与PPO，开发冻结后才执行新72条件；最终报告按实际checkpoint、调用账本和完整评价矩阵填写。所有结论均以新包实际结果决定，不预填学习方法优于名义/FIFO，也不将失败或负结果移回“尚未开始”。
