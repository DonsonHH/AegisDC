# 39b：从公开线索形成问题实例与任务

依据会后R1–R4、R6–R7和用户审阅F1/F4。39a的覆盖表不是此票的实现；此票仍须真实多系统、执行与复检验证。当前先做一个公开决策竖切片，后续每片按发现补充契约，原180次输入和方法保持。

## 第一片公共行为

在已授权的证据限定决策接口`choose_work(frame, program, history)`加入独立的`aegisdc-problem-driven-policy-v1`声明。输入只包括当前合法frame、专业工时/能力、公开问题/检查模板和公开历史，没有实际设施句柄。第一片只接通人工/工单二值线索触发专业检查；没有现场测量、处置或恢复收益的声明。

程序字段为`schema/id/basis/time_unit/policy/workforce_profile/templates`，policy是`fifo`或`no_human`。模板字段为`id/question_id/domain_ids/task/trigger/max_instances/source_note`；trigger是`source_ids/target_id/observable_id/equals`，这一版只允许合法布尔记录。风险量化单独保留未知，不能将一个工单的存在变成故障真值或点风险。

公开历史在原`issued/work_feedback`外显式带`question_instances`。实例保存`id/template_id/slot/origin_id/trigger_record_id/opened_at_s`；同模板同来源根只开一个实例，复制消息不生成额外独立问题。来源新事件可有新实例，既有实例的槽位不随迟到消息排序改变。每模板有正整数容量，超额线索显式报告容量不足。

实例任务采用模板指定的专业接口、人员/工具及截止时刻，ID为`template-id/task-N`，问题ID为`template-id/question-N`。检查任务通过既有公开可行性、占用和`ALREADY_ISSUED`规则；不生成固定Tour。FIFO只是透明调度参照，不声称最优。关闭、后续行动和恢复核验须后续竖切片接入实际执行，不能借本片通过来接受整票。

## 独立预期与执行位置

首片手工指定：一条IT工单在1秒观察、2秒到达且仍有效；2秒frame应形成`it-desk/question-0`，绑定来源根`case-it-01`，选择`it-desk/task-0`，由IT专业人员调查network。没有规定其后台是否真坏，输出的故障概率/服务损失点值保持null，不能产生物理效果或关闭声明。

采用先红后绿：先提交一个公共行为测试和静态输入，红片须在Slurm因缺少新声明支持而失败；实现后以同一预期在新输出目录运行绿片。两次均源/工具/输入冻结、记录终态、保留日志；不在本地运行测试或项目，不安装桌面依赖。后续完整39b验收还包括多域、同信息隔离、新事件/复检、资源竞争及实际设施接口。
