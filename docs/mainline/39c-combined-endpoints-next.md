# 39c下一步：完整业务记录与精确重放

当前实现源316fc3cc。53已把诊断v3、实例关闭v2、实际成本v2绑定到同一次RunResult；55核对原53/54完整保存数据，新增设施调用0。原54保持FAILED：少计逐边门禁的预期由独立手算更正为10.25人秒、5.75工具秒、首次实际关闭7秒；无人工和服务负例原通过子项保留。56仅调整架构图连线并生成灰度预览，不重做资格。各原件／勘误见slice-53/54/55和对应协议。

开发捕获累计100接口进入、45完成窗口164.25秒、207返回，直接公开选择38，内部嵌套未仪器化。原180研究及NO_PRACTICAL_GAIN保持；云端回归、保存资格和绘图另计。整39c未接受，39d继续保留依赖。

## 已接通的联合边界

- 同一scenario、完整dispatch及生产者声明/realizations、规范化boundary/engineering commands、实际duration/maximum_step共同绑定；私有业务声明不进派工。
- 原生v5与诊断v3兼容，旧诊断v1/v2仍限原生v4。实例物理关闭、当前选中管理处置及历史有效记录分开；不跨实例借用行动/复检。
- 非空反序整数事件同时保留旧诊断reference的raw哈希与联合程序实际规范化排序哈希；服务负例不因冷却复检合格就关闭。
- 两人实际集合等待1.25人秒已在原保存轨迹中资格化；无人策略仍留在适用确认机会分母，管理接受不代替物理改善。

## 下一个竖切片：record / read / exact replay

现有save_run已经保存inputs.business_program和business_evaluation；缺口在录制入口、执行转发、reader业务绑定和语义比较。当前replay输入、attempt/declaration只有v1/v2；文档13的v3是早期reader修正，不是输入v3。若封套字段/文件角色不变，保留attempt/declaration-v2，只新增闭合业务输入v3。

1. 输入v3携带原有seed/exogenous_events/action_commands/work_requests及dispatch_program/business_program。业务程序必须由现有验证器验证，不能只保存一个任意dict。旧v1/v2继续拒绝额外业务字段。
2. **保留v3提交的原始列表顺序。** 当前旧_inputs会排序，若直接用于54的raw[2,1]事件，会破坏合法诊断reference哈希。v3冻结原声明；真正执行仍由plant规范化/排序。旧v1/v2行为保留。reader从冻结声明推导实际规范化事件/命令后再比较run.inputs，不能把raw与actual哈希混用。
3. 录制转发business_program；reader核对frozen、run.inputs、业务/组件程序ID与schema、完整程序哈希、设施/窗口、运行输入binding及源码身份。缺失业务结果、注入业务字段、跨程序/跨工况组件须拒绝。读旧版本不能默默忽略注入字段。
4. 推荐首个新录制/重放例使用54服务负例的反序raw事件，同时保留冷却合格但服务失败、管理接受与实际成本；原录制与精确重放分别存完整attempt/lifecycle/原件。新协议新目录，不重跑54来改标。COMPLETED只说明执行结束，另验完整语义相等。

录制红测可在实际simulate之前拒绝新格式，所以其设施进入可能为0；不要沿用37runner的至少1次设施进入规则或把record/read次数冒充设施次数。新冻结runner应分别记录直接record/replay/read调用、实际进入simulate的execution_kind、完成窗口/秒数/返回；未观测内部调用保留null。原runtime/解释器须按现有EXACT_RUNTIME_BYTES_AND_INTERPRETER规则匹配。

## 精确的计时和来源比较

联合成本根已确定为C=run.business_evaluation.components.costs。只允许以下已声明ns**数值叶**变化：

- run.policy_computation_audit[*].elapsed_ns
- run.policy_computation_audit[*].condition_assessment_elapsed_ns
- C.computation.audit_record_details[*].elapsed_ns
- C.computation.audit_record_details[*].condition_assessment_elapsed_ns
- C.computation.selector_elapsed_ns.value
- C.computation.condition_assessment_elapsed_ns.value

每份结果先验证raw审计副本等于自身顶层audit、聚合等于自身raw和。保留存在/null、非负整数类型、单位、状态、覆盖/计数。物理轨迹/成本、费用、作业状态、确认时刻、来源/同源关系、模型计数及原文件哈希严格比较，不能按任意elapsed_ns字段名整类跳过。

既有replay允许“不同Git提交但相同runtime bytes/解释器”。新比较器须分别验证每份实际来源及组件源码副本；若处理这种允许的来源差异，明确记录经验证的Git/dirty元数据差异及精确位置，不把源文件哈希或任意业务字段纳入豁免。当前首个资格可在同一冻结提交内完成，后续来源边界另验。

记录链之后，补missing/injected字段、source/window/component错配和计时覆盖/类型等reader与比较资格。随后整39c独立Spec/Standards、零跳过根、原件身份及fresh交付；之后39d检查人员/设备时间比例、尺度/敏感性及新数值范围，再进原39AI协议和40–42。GPU已具备独立Torch/CUDA环境，效果仍须新协议与完整成本预算，不从资格推断增益。
