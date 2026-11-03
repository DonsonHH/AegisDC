> 正文审阅版：正文、公式和数值表与单文件HTML同源；图版保留SVG链接，便于文本工具读取。

<a id="hotspots"></a>

## 2. 状态估计与全机房风险态势

系统为128个机柜各保留一个温度估计：以公开功率、供液温度和流量估计推进热平衡，每5秒更新；32个固定温度点持续校正，热巡检完成后校正对应机柜。它形成覆盖全机房的连续<strong>温度态势</strong>，再按统一公式产生风险提示。



[图：已有工程回看500秒的公开温度估计；与右图同一色标，红框叠加原热风险提示。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/estimated-temperature.svg)



[图：同一工程过程500秒的事后设备代表温度。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/offline-temperature.svg)



两图采用同一45—75°C色标，每格一柜，蓝—黄—红呈现连续温度梯度。左侧红框标出该帧原热风险分>0的64、67、70号柜；黑点是32个固定温度遥测点。第9组的热点在估计与事后温度中均可见。

这是一段已有辅助馈电故障工程过程的500秒帧，按16组设备布置展示。连续色阶用于读出温度分布，调度仍使用原有热风险式：

<div class="formula-scroll"><p class="formula" role="math">r<sub>i</sub> = min{4, max(T̂<sub>i</sub> − 65, 0)/20 + 0.25[1 − P<sub>del,i</sub>/max(P<sub>req,i</sub>, ε)]}</p></div>

温度越界和功率缺口共同产生严重度提示。RGB→IR外观参考与这一数值温度估计承担不同任务：前者面向视觉线索，后者形成巡检端可计算的状态和风险。原风险分布、热平衡细式及500秒数值表放在附录A，便于逐项核对。

<aside class="scope-note"><p><strong>图的量与来源：</strong>色阶为设备代表温度（°C），红框为原风险提示，65°C风险起算点保持原设定。该工程回看、第3节历史12过程和第4节补充测试分别记账。右图用于事后核查，在线派单使用公开观测及估计。</p></aside>

### 学习估计器：在名义热平衡上估计温度残差

新估计器将最近四个连续5秒端点的14维公开特征与当前名义温度拼成57通道输入，以8×16设备网格计算空间残差。两个下采样层、空间跳接和16维条件潜变量组成295,777参数的CVAE-U-Net。训练用物理温度监督，运行时使用条件先验均值；两种估计器都以当时刚完成的温度量测覆盖对应位置。



[图：本次真实训练的温度残差CVAE-U-Net。公开输入57通道，295,777个参数；训练后验只用于监督，在线取条件先验均值。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-unet.svg)



这是一项温度任务适配：输出为设备温度残差，输入为遥测和专业量测历史。条件先验／后验、空间编码与解码的依据分别见[条件生成模型](https://proceedings.neurips.cc/paper_files/paper/2015/file/8d55a249e6baa5c06772297520da2051-Paper.pdf)和[U-Net](https://arxiv.org/abs/1505.04597)；实际结构与训练设置在方法说明中逐项列出。

### 新测试过程的全机房态势与时序



[图：按编号选取首个测试条件、训练种子271和注入后90秒；名义与CVAE使用相同Tour观测流，三图共用45—75°C色标。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-heatmaps.svg)




[图：与温度图同一编号示例。阴影为故障注入窗口，点表示当前新温度量测；温度和流量阈值采用研究设定。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-process.svg)



两图固定使用测试案例00的耦合条件与训练种子271；快照取故障注入后90秒，时序取故障组内无固定温度点的局部1号柜。名义和CVAE读取同一份Tour观测流，刚量测标志包含固定遥测与专业热检查。误差总体结论使用全部48个主要条件，见第4节。
