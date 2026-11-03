> 正文审阅版：正文、公式和数值表与单文件HTML同源；图版保留SVG链接，便于文本工具读取。

<a id="overview"></a>

## 报告主线与完成概览

|导师关心的内容|本报告的主要材料|位置|
|---|---|---|
|配电及RGB转红外视觉工作|10 kV—380 V交流—直流机柜依赖链；已有视觉样例、参考入口和电气量测更新|[三系统与视觉](#model)|
|冷却塔、泵、CDU、冷板及自控|双回路架构、实际三路反馈方程、2026双国标的对照状态|[模型与控制](#model)|
|大型设施复杂度|El Capitan性能／功率参照；当前热状态、指令状态、任务规模及扩展条件|[规模参照](#scale)|
|全局风险态势|名义／CVAE与事后温度同流对照、耦合故障时序、原风险提示|[全局态势](#hotspots)|
|原论文指标与横向比较|估计器×调度器七方法、四专业确认、误差、成本、训练与区间|[独立比较](#comparison)|

本次主比较采用名义与CVAE两种估计，交叉FIFO、Greedy与PPO，并保留固定Tour基准。RGB生成研究作为独立视觉成果展示。完整方法见[补充基准说明](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/supplement-study-methods.md)；历史FIFO日志、九规则和逐条件数据放在[技术附录](#appendix)。
