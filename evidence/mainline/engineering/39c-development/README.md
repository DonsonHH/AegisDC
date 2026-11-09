# 业务评价开发：处置何时才算经证据关闭

**39c已接通稳定问题ID下的实际关闭端点，并完成三个边界条件；整票仍在开发。** 6秒作业完成、6.5秒收到回执、8.5秒满足两组真实采样后才关闭，三者分别记账。原180次研究、NO_PRACTICAL_GAIN及所有失败保持。

![实际关闭、证据过期与删失时序](figures-01/closure-times-and-censoring.png)

点和星号表示各次实际公开评估，灰线只标运行窗口，不代表两次评估之间状态持续不变。无人工和8秒窗口没有观察到关闭，首次关闭/延迟保持null；过期例保存8.5秒首次关闭，也保存10秒当前待核验。四个工程变体共用合成设施基础，不作为四个统计独立研究样本。

![公开决策与私有业务评价数据流](figures-01/public-private-endpoint-architecture.png)

人员是设施域中的作业者，评价器只在设施运行结束后读取实际工作和已生成的公开评估。当前程序只适配已声明的稳定风险问题；39b动态实例的关闭、故障/正常/未知与机会分母、提前/反事实和完整成本仍须后续切片。诊断率和预防效应在当前输出明确未定义，不填零。

|记录|实际结果|
|---|---|
|[首个红/绿](slice-01/README.md)|133147保留接口TypeError；133150完成10秒、8次返回决策，观察6/6.5/8.5秒端点|
|[边界资格及原失败](slice-02/README.md)|133194零测试失败；133195两输入错误、8秒例通过；133223只执行修正两例并通过，17次返回决策|
|Spec复核|首片55ef及纠正24f分别静态PASS，范围各自固定；[原件](reviews-01/slice01-spec/report.md)、[纠正](reviews-01/qualification-correction-spec/report.md)|
|Standards复核|首片及纠正分别静态PASS，保留原pin，不接受整票；[原件](reviews-01/slice01-standards/report.md)、[纠正](reviews-01/qualification-correction-standards/report.md)|

当前累计7次设施接口进入、4个完成时间窗/38秒、33个返回决策。未完成失败调用保留原输入、源和错误栈，不能把完成时长当全部计算量。LLM/训练与新增注册研究均0，内部预测/选择调用未插桩。全部运行及绘图使用远端Slurm；本地只编辑、核对、回传必要摘要与查看图形，详细原件留服务器。

[数据表](figures-01/endpoints.csv) · [逐时评估](figures-01/assessments.csv) · [冻结契约](../../../../docs/mainline/39c-closure-endpoint-contract-01.md) · [完整39c任务](../../../../.scratch/full-facility-mainline/issues/39c-business-endpoints-and-closure.md)。本页为开发检查点，主线及M7保持active，39d和新的AI比较尚未开始。
