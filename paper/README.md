# 受约束事件确认机制稿

本版按用户2026-11-02确认的路线，先收束现有机制与负结果，供导师讨论。主文中心为RQ1任务价值与RQ2风险位置干预；同权限响应规则搜索作为开发诊断。后果反馈与递归改进留在独立备忘和展望，本轮没有新的实验计划。

## 建议阅读顺序

1. 汇报时打开[五屏离线汇报页](supervisor-briefing.html)，按每屏的“下一步／上一步”手动讲解，或点“完整图”直接看全部内容。[阶段讲稿与追问准备](supervisor-talk.md)与18个阶段一一对应，仍按约5分钟安排；N查看当前阶段讲稿，Q查看追问。
2. [一页导师讨论摘要](supervisor-brief.md)：主要结果、负结果与需要讨论的贡献定位，适合会后阅读。
3. [研究问题与贡献表](research-map.md)：主文RQ1—RQ2与证据边界。
4. [正文](manuscript_zh.md)或[公式图表预览](manuscript_zh.html)：已收束的8章机制稿。

五屏汇报沿用现有图并增加同一巡检员的关键执行链。各屏分别4、4、4、3、3个阶段，以局部透明度高亮／淡入解释顺序。鼠标触发180毫秒过渡，键盘与减少动态效果模式即时切换，无自动播放或循环。3张论文原图仍可点击放大，SVG导出、原图弹窗与打印都显示完整内容。

下载`supervisor-briefing.html`后用Edge或Chrome打开即可离线展示，无需服务器。左右键、数字1—5和底部按钮翻页；空格下一步，Shift+空格上一步；“从头讲”只重置本屏。“完整图”可跳过阶段；翻页保留每屏进度。原文链接需要联网。

[来源校验清单](generated/briefing-manifest.json)、[作图数据](generated/briefing-chart-data.json)、[完整SVG源图](figures/briefing-v3/)、[改动前后对比](briefing-comparison.md)、[验证记录](briefing-review.md)、[浏览器检查](generated/briefing-browser-verification.json)及[实际打印检查](generated/briefing-print-verification.json)可复核当前交付。[静态五屏原版](briefing-history/c2e1dbec/supervisor-briefing.html)与源文件按`c2e1dbec`逐字节保存；更早的[四屏版](briefing-history/958e777c/supervisor-briefing.html)也保留。

成品已包含在仓库中。重新生成时运行`python scripts/build_supervisor_briefing.py`，只需Python标准库；该命令还会逐项核对时间线原件，因此需将[主验证Release](https://github.com/DonsonHH/Zhinengti-RSI/releases/tag/event-validation-20261102-v1)中的`p02-coupled-tour.json.gz`与`p02-coupled-fifo.json.gz`放入`runs/event-validation-amended-20261102`。生成过程不新增研究执行。

本地复核顺序为`node scripts/check_supervisor_briefing.cjs`、`python scripts/check_briefing_print.py`。浏览器脚本使用Node内置WebSocket与已安装的Chrome，核对单文件断网、两个指定分辨率下的全部18阶段和完整图、反向操作、减少动态效果、键盘及原图等功能，并输出阶段截图和临时完整打印PDF。可用`BRIEFING_CHROME`指定浏览器程序路径。打印脚本使用pypdf和Poppler读取、渲染这份PDF，核对五页及关键文字完整性；临时文件位于`.work/briefing-v3-browser`。

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
