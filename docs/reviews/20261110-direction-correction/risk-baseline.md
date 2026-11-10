# 八域风险与检查价值基线（待审）

命令：`python -m aegis_dc risk-baseline`。目录复用原资产身份与条件模型，新增统一审查层；验证在私有服务器完成，零新增设施／AI／注册研究运行。[单一验证结果](result.json)保留red和green，完整日志与源码快照留远端。

|主域|主问题|条件风险|检查价值|
|---|---|---|---|
|供配电|power|条件模型|UNMODELED|
|后备能源|backup-support|UNMODELED|UNMODELED|
|设施冷却|cooling|条件模型|条件模型，时标未对齐|
|设备冷却与房间环境|room-boundary|UNMODELED|UNMODELED|
|计算／网络／存储服务|it-dependence|UNMODELED|UNMODELED|
|自动控制与监控|control-uncertainty|UNMODELED|UNMODELED|
|空间与保障|access-and-leak|UNMODELED|UNMODELED|
|异质人员、工具与作业|people-and-tools|UNMODELED|UNMODELED|

这里统计每域的主情景：cooling条件律也涉及设备环境，但不等于环境域的room-boundary风险已量化。六项风险与七项价值缺失都保留null，未赋0或排到低优先级。

FEMA适配目录把危险情景、资产／服务依赖、后果边界、现有保障、可用线索类型、专业能力／选项、待确认问题和缺失参数放在同一行。线索类型是允许的入口，实际测点覆盖以source登记为准。全场期望风险为null；已建模子集使用JOINT_OUTCOME_AND_WINDOW_UNION，不能把各问题重叠损失相加。

公共参照帧as_of=12秒，风险窗为未来2秒；cooling检查算例0.625秒、处置0.5秒。V6默认作业30秒、路径60／120秒、柴油启动30秒，时标没有对齐。输出因此阻止自动派工，执行许可false。条件模型与预算都是声明假设，不是现场概率或FEMA设备评分。

后续由用户选择具体风险问题和时间窗，再补观测性能、条件后果、可行动效果与时间依据。本包不把原180个预设派工比较回填为该基线的效果证据。
