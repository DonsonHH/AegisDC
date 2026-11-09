# 新实例不能借用旧实例关闭

Slurm133380在冻结源码334d2074完成1项公开接口资格：**旧question-0保持VERIFIED_CLOSED，新question-1仍OPEN_UNCONFIRMED**。新实例无自己的行动／复检支持，risk_closed=False，概率仍为null。

仅1次直接`choose_work`入口，无设施进入、原生时间窗、返回的设施决策或新增研究样本。复用18健康例真实5.5秒的公开帧、已到达回执和静态声明，另加一个明确的合成未确认工单与有限槽1声明，不伪造其执行。原run.json完整SHA核对，只有75550字节公开字段被导出为冻结输入；私有轨迹/真值未传给选择器。

原件见[唯一目录](23-public-instance-cross-scope/)，冻结[契约](../../../../../docs/mainline/39c-instance-cross-scope-contract-20.md)和[协议](../../../../../docs/mainline/39c-instance-cross-scope-qualification-20.json)。运行源、工具、输入前后守卫通过，测试零失败／错误／跳过，原18物理运行未重放。

原通用runner在无设施调用时把`internal_public_choice_calls`默认写0，这不是对子选择递归调用的测量。原terminal保留，该字段只按原工具默认值解释；本组仅证实直接入口1次，内部选择调用仍未插桩，不能归为0。后续工具记账修正另用新冻结版本，不重跑这一次。

后续21已从原20次运行的真实5.5秒公开帧冻结授权审查输入，新增线索和管理决定均明确标为合成记录。冻结红测133407于2026-11-09 14:08:42（本地时）提交；最后检查仍因Priority待调度。全cu分区20节点均分配中，现有任务时间限制显示UNLIMITED。当前无红测结果；保留同一作业，未重提、取消或在本机回退。见[协议21](../../../../../docs/mainline/39c-instance-review-protocol-21.json)。
