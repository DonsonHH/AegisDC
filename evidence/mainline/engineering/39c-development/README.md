# 业务评价开发：从状态确认到证据关闭

[最新51／52私有管理端点](slice-52/README.md)及独立有限复核通过：完整保留实例证据与自身作业时标，另验证过期、历史有效但无当前选中、升级优先、实际样本审查误报。52为4窗口26秒／32返回；累计89进入／41窗口139.25秒／172返回。诊断兼容、联合评价／完整重放和整票门槛仍开放。后文旧快照按各自时点阅读。

**最新：[成本检查点](../../../../docs/mainline/39c-cost-checkpoint-20261110.md) · [离线HTML](../../../../docs/mainline/39c-cost-checkpoint-20261110.html)。** 实际中止／未完成成本保留，共享队列只计一次，个人、工具、费用、计算分列。70进入／35窗口101.25秒／126返回，原180次不变；联合评价／重放和整票门槛继续开放。

![实际成本与作业状态](figures-09/cost-checkpoint-48/actual-costs-and-outcomes.png)

**较早快照：[时序与删失检查点](../../../../docs/mainline/39c-temporal-checkpoint-20261110.md) · [离线HTML](../../../../docs/mainline/39c-temporal-checkpoint-20261110.html)。** 故障／服务采样节点lead为−0.75秒，计划截止余量1.75秒；四个边界通过，37首绿失败保留。累计44进入／23窗口86秒／104返回，成本、联合重放和整票门槛仍开放。

![实际负提前量与删失状态](figures-08/temporal-checkpoint-40/temporal-leads-and-censoring.png)

**2026年11月10日较早快照：[实例审查阅读检查点](../../../../docs/mainline/39c-review-checkpoint-20261110.md) · [离线HTML](../../../../docs/mainline/39c-review-checkpoint-20261110.html)。** 24个证据／来源／授权条件通过，实际状态为1误报审查、1接受风险、1升级、17保持开放、4输入拒绝；三个历史处置与当前状态分开。全部原失败保留，整票39c尚未接受。

![24条件实际数据](figures-07/review-checkpoint-36/review-qualification.png)

![实例审查架构](figures-07/review-checkpoint-36/review-architecture.png)

协议20–33共16份唯一回执、15项执行测试、38次直接公开选择，零设施及研究增量；工具35三个夹具、保存绘图34／36另列。37次设施进入／17完成窗口72.5秒／81返回决策保持，内部选择未插桩。新图已核验哈希并实际查看。详见[执行账](instance-review-execution-ledger.json)、[独立复核及记账纠正](reviews-10)。

以下保留此前物理、诊断与参考窗口的检查点；其中“下一步”等为各自时点快照，当前待办为提前量／删失、实际成本和联合重放。

**39c已接通动态实例自身的处置／复检链与联合证据关闭，整票仍在开发。** 公开状态判定、固定事件分母和四种参考窗口继续保留。原180次研究、NO_PRACTICAL_GAIN与所有失败保持，未新增AI或效果研究。

![实例自身的作业与联合证据核验](figures-05/22-saved-instance-closure-figure/instance-joint-verification.png)

[实际两例](slice-18/README.md)均3.25秒完成清滤、3.75秒收到报告、5秒完成自己的复检并在5.5秒收到证据。网络健康例5.5秒满足有限关闭；原网络容量0.25例虽冷却核验合格，仍因服务不合格保持待核验。两例只有一个声明的物理参数不同，不是方法收益对照。健康网络例在本窗口本来已交付服务，不能把核验关闭解释为新增服务收益。

这组原件保留了[16首绿失败](slice-16/README.md)、[17上传后未提交](slice-17-staged-only/status.json)及独立冻结18的两例资格。原测试、输入与审查包按版本保存，服务门槛未放宽。每例实际作业2人秒、移动2人秒、等待0.5人秒，其中门禁核对占全部等待0.5人秒，不能重复相加；准入预算另列。[新CSV](figures-05/22-saved-instance-closure-figure/instance-endpoints.csv)与逐时评估来自原133378，绘图133379未新增设施运行。

![参考机会与方法实际迟到](figures-04/18-saved-reference-windows/reference-windows.png)

[四种参考窗口](reference-window-checkpoint/README.md)均保留初始故障。前三例没有适用确认分母，率为null；主动暂缓例共同参考仍为1.75秒，实际2.25秒确认超过2秒截止，故适用事件1、未按时确认1。2秒观察窗外的2.5秒空心标记是预先声明的参考时间，不是已观察到的到达。另有1项测试验证10次非法输入拒绝，不能当作10次仿真。四次原红测与全部正例分别留档。

![六个实际场景的公开状态与私有事件计数](figures-03/12-saved-diagnostic-matrix-layout/diagnostic-state-and-denominators.png)

左侧只依据已到达证据，右侧在运行后用私有真值核对。六例各声明一个事件，不能当成六个独立确认样本。工单本身不等于故障；未建模根因不能由容量异常读数推断。适用分母为零时，率为null；图中零仅表示明确的事件计数。

|实际工程场景|到达证据下的结果|完整事件表|
|---|---|---|
|正常|专业测量到达后判正常|正常事件1，误判0|
|无人工／故障|三个决策时刻均未知|本例冻结的故障取证机会1，未按时确认1|
|无人工／正常|公开帧与上一故障世界完全相同|正常事件1，误判0；私有真值不回流|
|需求模型故意设错|实际容量0.5满足需求0.5，公开模型仍假设1而判异常|正常事件1，误判1；重复判断不重复计事件|
|误差区间跨阈值|点值0.25但误差界1，保持未知|故障机会1，未按时确认1|
|未建模根因|可判断容量状态，不能确认故障原因|根因真值未知1，两种适用率均null|

![公开状态与私有事件评价架构](figures-02/11-saved-diagnostic-figures/diagnostic-public-private-architecture.png)

公开侧先筛质量、来源和同刻冲突，再选最新合格观察，保留观察与到达时刻。较新但无误差界的数值记录不会抹掉仍有效的旧样本，也不会让旧样本变新。私有事件、真实轨迹及共同参考机会仅用于运行后评价。

状态首片[133254／133264](slice-03/README.md)及[六例原运行133274](slice-04/README.md)均保留；后者5项测试4通过、1项预期值断言失败，原状态仍FAILED，六条轨迹未重跑。实际受供电／需求限制的容量是0.5，原断言误写铭牌0.75；[保存纠正](slice-06/README.md)单列。

独立复核发现并纠正了[公开样本资格顺序](slice-05/README.md)与[保存核验工具优化模式门禁](slice-07/README.md)，均有冻结红绿及原始失败。原133280模式未记录的边界保留；新133282正常子进程明确记录模式0并核对44件原输出。图形133292原间距问题留档，133293只修数据图，CSV字节相同，当前两张新图均已实际查看。

![实际关闭、证据过期与删失时序](figures-01/closure-times-and-censoring.png)

点和星号表示各次实际公开评估，灰线只标运行窗口，不代表两次评估之间状态持续不变。无人工和8秒窗口没有观察到关闭，首次关闭/延迟保持null；过期例保存8.5秒首次关闭，也保存10秒当前待核验。四个工程变体共用合成设施基础，不作为四个统计独立研究样本。

![公开决策与私有业务评价数据流](figures-01/public-private-endpoint-architecture.png)

人员是设施域中的作业者，评价器在设施运行结束后读取实际工作和已生成的公开评估。旧关闭程序适配稳定风险问题；新增状态程序有固定的正常／故障／未知事件表及确认分母，实例程序已验证有限自身行动／复检与联合关闭。其余跨实例／过期／复制／冲突、风险接受／升级、提前量及完整成本仍须后续切片。预防因果效应保持未识别，不填零。

|记录|实际结果|
|---|---|
|[首个红/绿](slice-01/README.md)|133147保留接口TypeError；133150完成10秒、8次返回决策，观察6/6.5/8.5秒端点|
|[边界资格及原失败](slice-02/README.md)|133194零测试失败；133195两输入错误、8秒例通过；133223只执行修正两例并通过，17次返回决策|
|Spec复核|首片55ef及纠正24f分别静态PASS，范围各自固定；[原件](reviews-01/slice01-spec/report.md)、[纠正](reviews-01/qualification-correction-spec/report.md)|
|Standards复核|首片及纠正分别静态PASS，保留原pin，不接受整票；[原件](reviews-01/slice01-standards/report.md)、[纠正](reviews-01/qualification-correction-standards/report.md)|

39c开发累计37次设施接口进入、17个完成时间窗／72.5秒、81个返回决策；其中10次入口拒绝不计完成窗口，17只上传未执行也不计进入。另有2次直接公开状态判定、保存工具和绘图作业，分别记账。失败未返回部分不当作完成时长。LLM、训练与新增注册研究均0，内部预测／选择调用未插桩。运行和绘图使用远端Slurm；本地只编辑、传输、核对和看图，完整轨迹及实际输入留在既有私有服务器。

独立复核按固定版本保存：[最初发现](reviews-02/spec-report.md)、[样本纠正](reviews-03/spec-report.md)、[工具原发现](reviews-03/standards-report.md)、[工具关闭包](reviews-04/standards-report.md)，不覆盖旧发现。新诊断检查点4f2977bb实际CI42548898914成功：621项中执行619项，零失败／错误，2项既有可选神经检查跳过。实际回执、192件固定版本交付清单和完整日志见[检查点记录](../../../../docs/mainline/evidence/39c-diagnostic-checkpoint.json)。这是最小云端回归，不替代整票零跳过根验收。

[六例审计CSV](slice-07/10-saved-verifier-mode-green/outputs/normal-child/original-six-endpoints.csv) · [新绘图数据](figures-03/12-saved-diagnostic-matrix-layout/diagnostic-plot-data.csv)。下一步仍是39c剩余业务语义与动态关闭，之后整票独立复核、远端根回归及fresh交付；39d和新的AI比较保持依赖。

参考窗口有限组在10b2b21f的[Spec](reviews-05/spec-report.md)通过、[Standards](reviews-05/standards-report.md)发现1处当前进度误写“首红未运行”。原发现已保存，[c001b0d4元数据关闭记录](reviews-05/standards-closure-c001b0d4.json)确认未重跑。保存绘图133358通过并实际查看，新增图和[CSV](figures-04/18-saved-reference-windows/reference-windows.csv)来自四个原正例，不增加运行。第03检查点实际推送CI42557908713在14a6ae02成功：626项发现、624项执行、零失败／错误，2项既有可选Torch检查跳过；[回执及固定交付清单](../../../../docs/mainline/evidence/39c-reference-checkpoint.json)保存完整日志和原件身份。整39c尚未验收。

[数据表](figures-01/endpoints.csv) · [逐时评估](figures-01/assessments.csv) · [冻结契约](../../../../docs/mainline/39c-closure-endpoint-contract-01.md) · [完整39c任务](../../../../.scratch/full-facility-mainline/issues/39c-business-endpoints-and-closure.md)。本页为开发检查点，主线及M7保持active，39d和新的AI比较尚未开始。

动态实例有限实现与输入修订的[原审查](reviews-06/)及[18事前／事后分列复核](reviews-07/)均保存。实际18为2项测试、2个6秒完成窗口、12次返回，零失败／错误／跳过。第04检查点实际推送34c158bd的CI42561209542成功：628项发现、626项执行、零失败／错误，2项既有可选Torch跳过；[固定版本清单、完整日志与回执](../../../../docs/mainline/evidence/39c-instance-checkpoint.json)可查。当前整票尚需[其余资格、联合评价／版本重放](../../../../docs/mainline/39c-next-after-instance-notes.md)、零跳过根验收和fresh。
