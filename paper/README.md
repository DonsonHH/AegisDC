# 受约束事件确认机制稿

本版按用户2026-11-02确认的路线，先收束现有机制与负结果，供导师讨论。主文中心为RQ1任务价值与RQ2风险位置干预；同权限响应规则搜索作为开发诊断。后果反馈与递归改进留在独立备忘和展望，本轮没有新的实验计划。

## 建议阅读顺序

1. 汇报时打开[五屏离线汇报页](supervisor-briefing.html)，先建立模拟机房情境，再依次展示执行架构、数据结果、同一负责人案例和当前成果。[口语讲稿与追问准备](supervisor-talk.md)可用于约5分钟的预演，页面内也能按N查看当前讲稿、按Q查看追问。
2. [一页导师讨论摘要](supervisor-brief.md)：主要结果、负结果与需要讨论的贡献定位，适合会后阅读。
3. [研究问题与贡献表](research-map.md)：主文RQ1—RQ2与证据边界。
4. [正文](manuscript_zh.md)或[公式图表预览](manuscript_zh.html)：已收束的8章机制稿。

五屏汇报页使用9张可编辑SVG主图，包括机房结构、实际漏检时间轴、新旧执行架构、总确认量柱状图、12过程净增图、两张案例时间轴、成果图和登记规则比较图。3张论文原图另放在点击放大的区域，图表与讲稿均内嵌。下载`supervisor-briefing.html`后用Edge或Chrome打开即可离线展示，无需服务器。方向键、数字1—5及底部按钮均可切屏；原文链接需要联网。

[来源校验清单](generated/briefing-manifest.json)、[作图数据](generated/briefing-chart-data.json)、[SVG源图](figures/briefing-v2/)、[改版与验证记录](briefing-review.md)和[浏览器检查结果](generated/briefing-browser-verification.json)可复核当前交付。[原四屏成品](briefing-history/958e777c/supervisor-briefing.html)与[原讲稿](briefing-history/958e777c/supervisor-talk.md)按`958e777c`逐字节保留，供前后对比。

成品已包含在仓库中。重新生成时运行`python scripts/build_supervisor_briefing.py`，只需Python标准库；该命令还会逐项核对时间线原件，因此需将[主验证Release](https://github.com/DonsonHH/Zhinengti-RSI/releases/tag/event-validation-20261102-v1)中的`p02-coupled-tour.json.gz`与`p02-coupled-fifo.json.gz`放入`runs/event-validation-amended-20261102`。生成过程不新增研究执行。

本地浏览器复核命令为`node scripts/check_supervisor_briefing.cjs`，使用Node内置WebSocket与已安装的Chrome，验证单文件断网、1366×768与1920×1080的全部五屏及控制功能，输出对应截图和检查JSON。可用环境变量`BRIEFING_CHROME`指定浏览器程序路径。

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

## 复核与当前边界

`python scripts/build_paper_assets.py`只读取封存记录生成图表、表格与HTML，不执行研究。写作依赖见[requirements-writing.txt](requirements-writing.txt)，可放在隔离目录`.work/paper-writing-deps`；原研究依赖仍由`pyproject.toml`管理。

主机制比较为12个预定合成热—冷耦合过程，Tour/FIFO/位置置乱确认28/70/25段，共89段。额外搜索为9条规则在同12个已见过程的108次开发评价，确认28—60段，按门槛停止；两包的执行次数不增加独立过程数。原件均公开保留。

本版用于导师讨论，未认定达到ESWA录用标准。接下来由导师审阅任务特定贡献、证明及比较范围，决定是否还需补强直接比较，再确定目标刊会、作者信息、英文与模板。本次不恢复原搜索包或安排模型组。
