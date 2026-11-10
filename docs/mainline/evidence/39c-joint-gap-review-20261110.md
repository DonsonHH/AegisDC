# 联合执行与重放缺口：固定40e2f8b只读复核

Independent reviewers `/root/review39c33_spec`、`/root/review39c33_standards`；未修改源码、运行测试或访问服务器。本记录给下一竖切片，不接受39c。

## 原生与联合评价

- `policy_execution.py:15–24`只识别执行v1–v4，字段按live/lifecycle/diagnostics版本选择；第55行只接实例关闭v1。新增执行版本须保留第43–54行的空反馈、真实检查／干预声明身份约束，不能只扩大白名单。
- `diagnostic_endpoints.py:25`底层验证硬限定执行v4。若新增原生v5，诊断版本组合也须显式声明和验证；`business_endpoints.py:35`的私有实例评价同样只接公开关闭v1。
- 实例端点目前主要提取物理首次关闭，未完整保留own_recheck/checks/trace/review_evaluations/historical_dispositions。新版须绑定实际打开身份、自身行动／复检，并分别报告管理处置观察、到达、当前评估及首次有效时刻；管理关闭不改物理关闭或诊断分母。
- 联合组件必须来自同一实际scenario、外生输入、完整dispatch、生产者声明及realizations，使用同一源码、设施与窗口。方法无关机会不由实际收到的有利记录反选。

## 记录与读取的真实现状

`save_run`已经完整保存`inputs.business_program`及`business_evaluation`，见plant.py:873/881/893。缺口在replay冻结入口、执行转发、reader业务绑定与比较，而不是另拼结果文件。

存储输入、attempt/declaration目前仅v1/v2；第13项文档所谓v3是reader绑定修正，不是第三种存储格式。新输入契约须闭合地携带私有业务声明及dispatch，旧格式继续拒绝额外字段；必要的新attempt/declaration也继承origin、生命周期、源码／解释器和文件角色约束。replay.py:79、236、361及replay_format.py:83为核查入口。

## 精确的非确定计时范围

现有测试只豁免顶层`run.policy_computation_audit[*].elapsed_ns`。新增比较至少还须明示：

- `run.policy_computation_audit[*].condition_assessment_elapsed_ns`
- `C.computation.audit_record_details[*].elapsed_ns`
- `C.computation.audit_record_details[*].condition_assessment_elapsed_ns`
- `C.computation.selector_elapsed_ns.value`
- `C.computation.condition_assessment_elapsed_ns.value`

当前成本根C为run.business_evaluation；联合版本须先冻结新的精确根路径。只处理这些计时数值，仍比较字段存在/null、非负整数类型、记录覆盖／状态／计数。每次结果先独立证明审计副本一致、聚合等于自身raw和；物理成本、费用、任务状态、确认时刻和模型计数严格比较，原始文件哈希仍完整。

`replay_attempt`的COMPLETED只表示重执行结束，不证明与原运行语义相等。

## 第一可执行竖切片

先以18健康网络输入构造新的原生接纳红／绿：加入到时的新来源问题及精确授权接受，私有端暂用已通过成本v2，避免新联合schema先挡住原生执行门。应同时观察旧实例靠自己的链关闭、新实例仅管理接受且risk_closed=false，并验证生产者身份不匹配拒绝。之后再冻联合组件、record／read／exact replay，包含无人工和服务证据不合格负例；不重跑原180次或覆盖旧原件。
