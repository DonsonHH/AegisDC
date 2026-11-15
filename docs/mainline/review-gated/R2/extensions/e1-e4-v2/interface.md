# 有限执行接口与固定输入格式

本文件只具体化序列化及调用，不改变relations的科学关系。所有有理数以JSON整数或`分子/分母`字符串表达；不使用浮点容差。缺关键配置拒绝构造，不借默认值补齐。冻结cases.json每单位包含完整input、refs、顺序steps与字面expected；多字段比较由select列出，全部实际返回仍保存。

- `E14Run(config)`是私有设施／评价实例；`advance(time)`仅沿同一实例推进单调时间至H，不能重建状态。`request(payload)`校验公开字段、权限、版本及预算，返回status。只读消费者只能获得`public_view()`，不持有实例或audit接口。
- `audit()`为私有资格输出，包含原输入、事件和操作记录、预算实耗／预留／余额、源和配置状态、G与设备状态、观察／回执、供电／服务分段及积分。不得传给决策规则。
- 观察记录通过已声明ACTION_RESULT模式发布；审批／执行分别用APPROVAL_RECEIPT与EXECUTION_RECEIPT。请求ID在单实例顺序唯一，成功执行身份为`ex-1`；观察ID按真实生成顺序`obs-1`等，副本不占新观察编号。
- 公共拒绝类别为INVALID_REQUEST、ACCESS_DENIED、INVALID_PARENT、BUDGET_UNAVAILABLE、NOT_STARTED_RESOURCE、WINDOW_UNAVAILABLE、INSUFFICIENT_INFORMATION、PRE_CLOSED；均只由公开条件决定。BUDGET_UNAVAILABLE在资源开工前判定，不能用私有故障取消一个本可公开准入的请求。
- `decide(public_view, method)`只接收公共视图及M0/B1标签。输出action/mode/reason；证书只能影响reason，PROPOSE_FIX两者mode均EVIDENCE。D系列只是一次固定规则入口调用，不运行收益比较或规划器。
- `local_control(family, signals, time)`只接收六个本地信号及其quality/sample_time，不接收World。C03的private_fixture仅属于检查器的隔离对照，不传给控制器；物理供给仍由运行实例独立判定。
- 检查器为每个单位记录构造、每次顺序调用及完整返回／异常。expected字段只从冻结输入读取。跨单位比较限冻结pairs路径；守恒核对由保存的功率分段独立积分，不调用模型积分函数。

初始READ完成后，在回执到达前read_status=PENDING_PUBLICATION；发布后为RESULT_AVAILABLE；中止为ABORTED_READ。spent/reserved/available在本单人单工具域各自数值相同，audit必须同时保留person/tool完整账，简写字段用于固定断言。phase/commit_result/verification_result与relations一致。recoveries为空表示NO_OUTAGE；全窗完整标COMPLETE，提前读取的积分标INCOMPLETE_TRACE，不能作为完整结果。

VERIFY观察的value/status固定为PASS/VERIFIED_FOR_TARGET、FAIL/VERIFY_FAILED或UNKNOWN/INCONCLUSIVE；来源probe-local，config_epoch及parent_execution_id绑定实际执行。审批grant_id固定grant-1，获批时执行器回执receiver_role=EXECUTOR、available_at=决定时刻；方法回执receiver_role=AUDITOR，available_at=决定时刻+发布延迟。执行回执成功状态EXECUTED_UNVERIFIED，失败状态NOT_IMPLEMENTED；失败committed_at/execution_id/target_config_epoch为null，available_at仍为该结果产生时刻+发布延迟。以上均为已有语义的确定序列化。

本轮只实现本包与固定见证的有限域；原london_pre.py及旧97单位原件保留。资格结果不自动成为用户验收或完整Q11资格。
