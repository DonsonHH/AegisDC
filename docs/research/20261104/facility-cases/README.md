# 三设施拓扑、状态方程与参数资料包

先打开[离线阅读版](report.html)，查看架构图、参数筛选、公式与主来源。HTML是单文件，可复制到其他目录离线打开；图表和公式均无需CDN。

|案例|参数记录|完全缺值|明细|
|---|---|---|---|
|Frontier · ORNL|35|5|[frontier](frontier.md)|
|El Capitan · LLNL|36|12|[el-capitan](el-capitan.md)|
|郑州核心节点 / 曙光8000|32|15|[zhengzhou](zhengzhou.md)|

共8幅原创SVG。图中实线表示公开功能/设计关系，虚线表示发表模型或研究提议，点线表示缺失连接；热流、流体、电能与信息分型。图不是竣工图或人员通行图。

- [共同模块与各站状态方程](state-equations.md)：SI单位、状态/代数/输入/观测、初值与闭合条件。
- [机器可读台账](casebook.json)：103条参数记录、逐节点/边来源和绘图布局。
- [Frontier参数CSV](parameters/frontier.csv)、[El Capitan参数CSV](parameters/el-capitan.csv)、[郑州参数CSV](parameters/zhengzhou.csv)。
- [源文件与工作簿有限核对](../../../../evidence/facility-case-models-20261104/reference-inspection.json)：关键PDF图页、20MB原始工作簿表头/前19时间戳及SHA。

当前三案例为`UNRESOLVED_CLOSURE`。公开站点描述、设计值、发表模型和厂家声明分别保留；未知字段为null，冲突不靠平均或拼接消除。物理模型的标定先于策略收益评价，智能体与RSI后置。本轮没有新增训练或注册实验。
