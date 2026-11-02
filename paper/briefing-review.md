# 导师自阅报告：重构与核对记录

当前入口为[自阅报告](supervisor-briefing.html)，源文为[supervisor-report.md](supervisor-report.md)。本次用途按用户2026-11-03说明调整，默认连续阅读，取消演示动画、分步、N／Q讲稿操作和脚本依赖。技术要求来自[匿名整理的上次沟通内容](mentor-requests.md)，用途变化与[旧版对比](briefing-comparison.md)另存。

## 内容回应

- 模型：供电—一次／二次液冷—本地设备控制之间的关系、三条核心计算关系和161个集中温度状态；当前电气／管网／控制简化与规模未验证分别列出。
- 工程依据：核对LLNL、HPE原始资料；两项相关GB/T标准只确认元数据，明确2027实施、正式条款尚待核读，未宣称符合标准。
- 风险图：从已有工程回看截取500秒的原巡回公开风险与事后温度，128个柜号逐项对应。工程例不并入主研究样本，公开与事后信息区分，32个固定遥测点标出。
- FIFO：空闲时先筛自己的合法待办，再按首次提示时间排序；用10号450秒先提示／8号455秒后提示但分更高的真实队列解释。两次实际加查完成于500／515秒，原0号于540秒完成，早于545截止；两次完整返回核算余量20／5秒均来自原记录。
- 当前结果：12个主过程、89段异常（77热＋12冷），28／70／25及成本、零约束违规和有限规则负结果保持。原论文与本项目指标不可直接排性能名次，同任务实验、标准条款映射和E/G规模基准继续列为待补。
- 以本项目图为主：正文10张本项目架构／数据图，另1张原论文对照图、3张本项目附图。最新补入贯通观测与执行的总体架构、收益代价及九规则负结果，原来仅用文字概括的结果现在逐项可见。
- 原论文：逐页核对指标、式1／2、估计器与规划器对照，表8／9四方法均值和95%CI用于原文内部图；不把30%曲线描述改写成终值或推理速度改善。详见[指标核查](research/original-paper-metrics-20261103.md)。

## 实际核对范围

1. 构建器从原JSON、带原件SHA的紧凑快照、既有SVG和原始来源核查生成HTML；数值与基准编码交叉核对。生成过程不导入或调用研究模拟器。
2. [独立原件核对](generated/supervisor-report-source-verification.json)直接读取完整本地工程记录与主实验gzip，核对风险／温度数组、两条队列请求、两份返回证书、实际派单和测量，以及专业人数／服务时间／期限。另核对manifest来源身份、14份SVG确实逐字节嵌入HTML、256个热点编码、9条规则与3项代价及门槛；代价均值从原行记录重算。原两包340个文件与原索引SHA全部一致。
3. [浏览器核对](generated/supervisor-report-verification.json)在单独复制的HTML上禁用网络，检查1366×768、1920×1080各15个阅读区域，另检查390×844的4个区域，共34个视图。没有应用脚本、动画、分步控件、外部请求或浏览器异常；目录锚点可用，核心内容和11张主图默认可见。3张回溯图在可选附例中，另展开检查。
4. SVG文字范围与重叠检查通过；宽度检查未见页面横向溢出。窄屏较宽图在图内横向查看，保持标签字号，不把全图压成小字。
5. [打印核对](generated/supervisor-report-print-verification.json)使用实际Chrome打印15页PDF，核对模型、标准日期、队列、期限、结果和原论文数值的文字完整性；Poppler渲染后抽查第2、6、8、11、12页，检查架构、流程、实际派单、三项代价、九规则和文献比较图。打印包含可选附例。
6. 原主论文、原数值指标、研究代码和协议未修改；没有新增仿真、训练、研究模型推理或独立实验样本。原演示HTML及14份相关源文件按2db2adf1逐字节保留。

## 阅读预览

|内容|1366×768|1920×1080|
|---|---|---|
|要求与进度|[查看](generated/report-previews/1366x768-overview.png)|[查看](generated/report-previews/1920x1080-overview.png)|
|耦合模型|[查看](generated/report-previews/1366x768-model.png)|[查看](generated/report-previews/1920x1080-model.png)|
|风险热点|[查看](generated/report-previews/1366x768-hotspots.png)|[查看](generated/report-previews/1920x1080-hotspots.png)|
|FIFO队列|[查看](generated/report-previews/1366x768-fifo-queue.png)|[查看](generated/report-previews/1920x1080-fifo-queue.png)|
|实际执行与核算|[查看](generated/report-previews/1366x768-fifo-actions.png)|[查看](generated/report-previews/1920x1080-fifo-actions.png)|
|完整巡检系统架构|[查看](generated/report-previews/1366x768-inspection-architecture.png)|[查看](generated/report-previews/1920x1080-inspection-architecture.png)|
|收益与代价|[查看](generated/report-previews/1366x768-outcome-costs.png)|[查看](generated/report-previews/1920x1080-outcome-costs.png)|
|九规则负结果|[查看](generated/report-previews/1366x768-registered-rules.png)|[查看](generated/report-previews/1920x1080-registered-rules.png)|
|原论文数值对照|[查看](generated/report-previews/1366x768-paper-comparison.png)|[查看](generated/report-previews/1920x1080-paper-comparison.png)|

应用侧自动预览工具曾返回本地内核资产路径错误，因此采用本机Chrome直接验证相同HTML；这不作为网站渲染故障。完整单文件和本地HTTP预览继续可用。

两名独立审查分别核对规范和用户要求；新增两处图表展示缺口已修正并复看。详细意见与落实见[两轴审读](briefing-code-review.md)。这是图文审查与自动渲染核对，不代替导师的实际阅读反馈。
