# 导师自阅报告与机制工作稿

当前沟通材料按用户2026-11-03的新用途改为直接阅读的报告；研究主结果与机制工作稿保持原范围，未启动新实验。

## 建议入口

1. [自阅研究进展报告](supervisor-briefing.html)：先回应上次沟通要求，再看模型／规模、风险热点、FIFO真实流程、当前结果及原论文指标与对照。核心内容全部直接可见，文末回溯附例可按需展开。
2. [本次采用的导师要求](mentor-requests.md)、[工程参照核查](research/mentor-engineering-reference-20261103.md)、[原论文指标核查](research/original-paper-metrics-20261103.md)：分别对应截图要求、El Capitan／国家标准及原文评价设计。
3. [机制稿摘要](supervisor-brief.md)、[贡献表](research-map.md)、[正文](manuscript_zh.md)／[公式图表预览](manuscript_zh.html)：供进一步审阅论文，而非当前报告的操作说明。

网页没有动画、分步按钮或讲稿依赖。沿目录或直接向下阅读即可；图表已内嵌，可把单独一份HTML交给导师离线查看。进一步的源码、官方资料和完整工作稿链接需要网络或相应文件。移动端宽图可在图内横向查看。

## 来源与复建

- [报告Markdown源文](supervisor-report.md)、[绘图输入](generated/supervisor-report-data.json)、[完整SVG](figures/supervisor-report/)、[来源manifest](generated/briefing-manifest.json)。
- [用途变化与旧版](briefing-comparison.md)、[验证记录](briefing-review.md)、[浏览器验证](generated/supervisor-report-verification.json)、[原件独立核对](generated/supervisor-report-source-verification.json)、[打印验证](generated/supervisor-report-print-verification.json)。
- 已发布主结果仍见`evidence/event-validation/final`；工程热点图使用已保存的工程回看，未计作12主过程的新样本。原论文数值是原文内部对照，未冒充本项目实测。

构建：`python scripts/build_supervisor_report.py`，使用已有写作环境中的markdown-it-py和Python标准库；[写作依赖](requirements-writing.txt)可放在隔离目录`.work/paper-writing-deps`。数值来自有原件SHA的紧凑快照及原有JSON/SVG，不需要重跑模拟。旧命令`python scripts/build_supervisor_briefing.py`已转到同一静态报告构建，避免恢复旧动画。

浏览器检查：`node scripts/check_supervisor_report.cjs`，需要支持内置WebSocket的Node及本机Chrome；可用`BRIEFING_CHROME`指定路径。实际打印核对：`python scripts/check_report_print.py`，使用pypdf和Poppler；临时文件位于`.work/self-reading-check`。完整原件独立核对：`python scripts/verify_report_sources.py`，需本机已有的完整工程与封存研究目录。所有命令均不启动新研究。

## 历史沟通材料

- [18阶段演示版](briefing-history/2db2adf1/supervisor-briefing.html)及源文件按`2db2adf1`保存。
- [静态五屏版](briefing-history/c2e1dbec/supervisor-briefing.html)与[早期四屏版](briefing-history/958e777c/supervisor-briefing.html)也保留。

## 章节与材料

|章节|当前内容|讨论重点|
|---|---|---|
|1 引言|短时异常确认与持续重访的共同执行，提出RQ1—RQ2|问题重要性与贡献定位|
|2 相关工作|持续巡检、双任务、预测安全过滤及原论文关系|任务特定差别；R9全文约束仍待核验|
|3 问题定义|专业任务、观测、风险、异常与确认指标|合成假设、评价阈值和比较单位|
|4 事件确认机制|生命周期、FIFO、返回证书与条件性证明|充分条件、执行顺序和实际保证范围|
|5 同权限规则诊断|已实现的受限二选一和9条登记规则的搜索方法|同输入／权限比较；有限子集而非全局优化|
|6 实验|主结果、位置干预、成本、同一负责人时间线和搜索负结果|12个过程；新增、丢失和实际成本|
|7 分析与适用范围|机制取舍、合成范围、可复核性和反馈展望|不外推为现场或通用算法优势|
|8 结论|回答RQ1—RQ2，保留搜索未获改进的发现|按已完成证据收束|

- [模型附录](model-appendix.md)／[预览](model-appendix.html)：核心方程、单位、参数及物理形式来源。
- [补充材料](supplement.md)／[预览](supplement.html)：执行身份、修订、统计与轨迹来源。
- [文献比较](related-work.md)、[书目](references.bib)、[最近邻全文核查](research/closest-methods-20261102.md)、[物理依据](research/model-basis-20261102.md)。
- [证据映射](evidence-map.json)、[生成校验](generated/validation.json)、[可视抽查](generated/visual-review.json)。
- [后果反馈研究备忘](feedback-design.md)／[预览](feedback-design.html)：从主文移出的设计；不是当前完成贡献或新增调用安排。
- [审阅落实记录](revision-review.md)、[路线选择记录](decision-brief.md)、[写作辅助披露记录](authoring-disclosure.md)。

## 机制工作稿的复核与边界

`python scripts/build_paper_assets.py`只读取封存记录生成图表、表格与HTML，不执行研究。写作依赖见[requirements-writing.txt](requirements-writing.txt)，可放在隔离目录`.work/paper-writing-deps`；原研究依赖仍由`pyproject.toml`管理。

主机制比较为12个预定合成热—冷耦合过程，Tour/FIFO/位置置乱确认28/70/25段，共89段。额外搜索为9条规则在同12个已见过程的108次开发评价，确认28—60段，按门槛停止；两包的执行次数不增加独立过程数。原件均公开保留。

本版用于导师讨论，未认定达到ESWA录用标准。接下来由导师审阅任务特定贡献、证明及比较范围，决定是否还需补强直接比较，再确定目标刊会、作者信息、英文与模板。本次不恢复原搜索包或安排模型组。
