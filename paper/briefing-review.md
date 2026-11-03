# 工程主线报告：渲染与源值核对

当前入口是[导师自阅报告](supervisor-briefing.html)，源文为[supervisor-report.md](supervisor-report.md)。版本6集中呈现三系统、视觉接口、控制与规模、连续温度态势和本任务比较；FIFO及九规则技术材料放入可选附录。要求、取舍及两轴review见[本轮要求](report-focus-spec-20261103.md)、[完整review](report-review-20261103.md)。

## 核对覆盖

- [浏览器记录](generated/supervisor-report-verification.json)：在独立复制HTML上禁用网络，以1366×768、1920×1080和390×844检查正文及展开附录；核对正文8图、附录10图、比较表7行、三张内嵌PID图片、连续温度图与原风险叠加。检查目录、脚本／动画、页面溢出、SVG文字范围和重叠，以及打印公式宽度。视图、样图数量及HTML身份随记录保存。
- [原件核对](generated/supervisor-report-source-verification.json)：原两包340份文件保持SHA；18个SVG逐字节内嵌；384个风险／估计温度／事后温度编码与原帧相同，红框来自原风险>0。三张PID原图逐字节对应已保存样例。
- 比较指标：读取60份既有方法记录及固定公共任务权重，从10560组任务完成间隔独立积分；逐过程分母、五方法均值、保存确认与采样端点一致。三类误差和逐步推理计时保持缺项，VAE两方法按未运行状态列示。
- [打印记录](generated/supervisor-report-print-verification.json)：Chrome生成实际PDF，pypdf检查关键文字与数值，Poppler渲染后查看视觉接口、控制、态势、比较表和附录。打印包含附录全部内容，相关页数及PDF身份在记录中保存。
- 科研源代码、配置、协议、原研究结果及主指标保持身份；本轮新增报告、既有材料引用和只读派生计算。此前单文件报告按[调整前版本](briefing-history/e7fd9e26/)保留。

## 当前阅读样图

|内容|1366×768|1920×1080|
|---|---|---|
|已有RGB／IR视觉材料|[查看](generated/report-previews/1366x768-pid-sample.png)|[查看](generated/report-previews/1920x1080-pid-sample.png)|
|视觉与量测接入关系|[查看](generated/report-previews/1366x768-visual-interface.png)|[查看](generated/report-previews/1920x1080-visual-interface.png)|
|实际控制目标|[查看](generated/report-previews/1366x768-control.png)|[查看](generated/report-previews/1920x1080-control.png)|
|大型设施参照与当前规模|[查看](generated/report-previews/1366x768-scale.png)|[查看](generated/report-previews/1920x1080-scale.png)|
|连续温度态势|[查看](generated/report-previews/1366x768-hotspots.png)|[查看](generated/report-previews/1920x1080-hotspots.png)|
|机房方法比较表|[查看](generated/report-previews/1366x768-method-comparison.png)|[查看](generated/report-previews/1920x1080-method-comparison.png)|
|附录：九规则|[查看](generated/report-previews/1366x768-registered-rules.png)|[查看](generated/report-previews/1920x1080-registered-rules.png)|

验证分别提供来源身份、计算一致性和实际渲染证据；图文与事实审读另在完整review中记录。
