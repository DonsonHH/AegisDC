# 工作稿 v1.1 修订说明

**本次交审包括[修订后的论文](manuscript.pdf)和[R5 后继问题的可行性说明](../../R5/successor-feasibility.md)。** 论文另有[可编辑正文](manuscript.md)和[离线 HTML](manuscript.html)。初稿及其所有附件保存在原目录，审阅版本为 [`d5f86fb7`](https://github.com/DonsonHH/AegisDC/tree/d5f86fb74c8550621a0b7a3531a440f73188e3f6/docs/mainline/review-gated/R6/london-pre-manuscript-v1)，原研究证据基线为 `cf666ec5`。

| 位置 | 本版修订 |
|---|---|
| 副标题、摘要 | 副标题明确“固定策略的配对比较”。摘要给出 B01 的三臂缺额，并说明同一核查链在两种截止时刻的结果。 |
| §4.2、图 2、讨论与结论 | X02 与 B01 的完整输入仅相差 [0,2) 外部预约。B01 是已知机制在改变预约后的有限检验，也是 ext35 中有效的 I／D 反例。 |
| §4.3、图 3、讨论与结论 | 两行读取链、申请与名义提交时刻一致，仅故障起点 `tF` 改变，A 源均在第 19 秒恢复。配对可定位提交边界，不能估计多读一项的代价。 |
| §3.3 | 规格术语 `NO_OUTAGE` 对应扩展表 `service_recovery_status` 的 `NO_RECORDED_SERVICE_OUTAGE` 值。无停机与端点停机后恢复时长右删失分开报告。 |

四幅图、两条公式和完整配对附表沿用初稿。HTML 从本版 Markdown 排版并内嵌原图与 MathML，PDF 取自同一版 HTML。原始 [19／35 行附表](../london-pre-manuscript-v1/data/paired-tables.md)、[逐图来源](../london-pre-manuscript-v1/figure-map.md)、[版本与指标](../london-pre-manuscript-v1/reproducibility.md)可直接对照。此次只修订文字、排版和书面可行性说明，新增模型、测试、资格及研究运行均为零。

本轮停在研究问题与文稿 review。原 R5 v1 的 216 个开发回合、最多 105 个评估回合仍未执行且不可转拨。后继问题尚未取得执行授权，独立确认义务继续保留。
