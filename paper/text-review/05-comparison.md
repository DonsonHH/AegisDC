> 正文审阅版：正文、公式和数值表与单文件HTML同源；图版保留SVG链接，便于文本工具读取。

> 4. 实验结果 · 第1/3部分。

[下一部分](05-comparison-part02.md)

<a id="comparison"></a>

## 4. 实验验证层：多算法结果与机制诊断

<p class="chapter-lead">将温度估计与派单方法组合为7种方案，在1080个测试回合中比较：温度估计是否更准、异常能否及时查到，以及多走多少路、例行检查是否超时。随后用具体案例解释温度估计更准为何没有直接带来更多确认。</p>

### 4.1 评价体系与独立实验设计

#### 4.1.1 四维指标与统计单位

原论文以VAE重建重要度图、以DRL调度水域巡检。本研究借鉴其分层评价思路，将状态准确性、持续巡检质量、专业确认和计算代价用于同一机房任务。[原论文](https://doi.org/10.1016/j.eswa.2025.126483)。

<div class="table-guide" id="table-evaluation-metrics"><div class="exhibit-intro" data-guide-table="evaluation-metrics"><p class="exhibit-title"><span class="exhibit-number">表 7</span> <strong>四类指标分别回答什么问题</strong></p><p class="exhibit-purpose">建立“估得准、查得及时、覆盖持续、代价可接受”的评价框架。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>横向读指标与方向：RMSE↓/R²↑看温度估计，J_age↓看距上次检查的归一时间，确认数↑/等待↓看异常核查，距离和耗时看资源开销；约束违规要求为0。</p><p><strong>◇ 读到什么：</strong>不同指标对应不同任务目标，估计误差降低与确认数增加需要分别验证。</p></div></div>

|维度|本任务指标|方向|
|---|---|---|
|状态估计|温度RMSE、资产加权RMSE、盲区机柜加权RMSE、R²|误差低、R²高|
|持续巡检|静态资产重要度加权归一年龄J<sub>age</sub>（适配idleness）|低|
|异常确认|有效确认段数／比例、后果加权截尾等待、硬重访违规|确认多、等待短、约束零违规|
|资源与计算|移动变化、完成量变化、阶段p50／p95和训练耗时|联合判断收益与代价|

温度误差比较估计值与模拟机房的真实柜温。“盲区机柜加权RMSE”对应原指标“非刚量测加权RMSE”：排除当前时刻有新温度量测的位置，包括固定测温点和刚完成热检查的机柜，集中评价需要推算的温度。R²按每回合的误差平方和SSE与总离差平方和SST计算后汇总，温度目标恒定时记NA。

四专业的异常阈值为：柜温>65°C、接点温度>60°C、组流量<33.6 kg/s、组平均传感误差绝对值>1°C；连续至少3个5秒采样满足阈值才计为一段异常。巡检员需在仍处于异常的采样时刻完成合格测量，且测量值达到相应报警阈值，才记为有效确认；一直未确认的异常，等待时间计到该段结束。

加权年龄对各方法实际完成时刻解析积分，包含初始和1800秒终点间隔：

<div class="formula-scroll"><p class="formula" role="math">A<sub>j</sub>(t) = min[(t − L<sub>j</sub>)/D<sub>j</sub>,1]</p><p class="formula" role="math">J<sub>age</sub> = [1/(1800Σ<sub>j</sub>w<sub>j</sub>)] ∫<sub>0</sub><sup>1800</sup>Σ<sub>j</sub>w<sub>j</sub>A<sub>j</sub>(t)dt</p></div>

w为共同静态资产权重，D为专业重访期限，L为最近完成时刻。每条件先归一，再按登记权重汇总。主要统计先在条件内平均学习方法的三个模型种子，再在各物理种子块内等权四故障族；95%探索性区间采用12块、10,000次自举，随机种子20261103，训练种子变化另列，未做多重比较校正。

#### 4.1.2 数据划分与训练过程

<div class="table-guide" id="table-data-splits"><div class="exhibit-intro" data-guide-table="data-splits"><p class="exhibit-title"><span class="exhibit-number">表 8</span> <strong>训练、开发和测试分别使用哪些数据</strong></p><p class="exhibit-purpose">说明模型怎样学习、怎样选参数，以及最后成绩在哪批过程上计算。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>先读24/6/12组独立物理种子，再看快照与回合。每个测试条件下，名义Tour/FIFO/Greedy各1次，其余4个含训练模型组合各3次，合计3＋4×3＝15；72×15＝1080。快照为同一轨迹上的连续观测。</p><p><strong>◇ 读到什么：</strong>最终主要比较使用48个故障条件，统计区间以12组独立测试集为单位；快照数和模型重复数各自记录。</p></div></div>

|阶段|独立物理种子块|条件与用途|执行与训练记录|
|---|---:|---|---|
|训练|24|四故障＋健康／虚假提示；Tour与FIFO各一条观测流|288条流、34,560个快照；每策略种子120个PPO回合|
|开发|6|同六类条件；CVAE选择与冻结PPO诊断|72条流、8,640个快照；36次PPO诊断|
|最终测试|12|72条件，含60条唯一物理轨迹；种子与训练／开发隔离|7方法标签、每条件15个规则／模型实例，共1080回合|

四故障族涵盖辅助馈电＋CDU衰减、接触热点、传感偏差和二次泵故障；故障族在训练中已见，留出新种子及登记的位置／相位组合。健康与虚假提示共享物理过程并单列，连续快照与模型重复分别计数。



<a id="figure-supplement-estimator-training"></a>

<div class="exhibit-intro" data-guide-figure="supplement-estimator-training"><p class="exhibit-title"><span class="exhibit-number">图 7</span> <strong>温度估计器的开发误差怎样随训练变化</strong></p><p class="exhibit-purpose">检查三个模型是否学到有效的温度修正，并说明各自保存哪一轮参数。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-estimator-training.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>横轴为训练轮次epoch，纵轴为开发集加权RMSE，单位°C、方向↓；不同曲线对应271、811、1931三个训练种子。沿每条线向右看误差变化，○空心点标出该模型开发误差最小的轮次。</p><p><strong>◇ 读到什么：</strong>模型按开发集误差选定参数；这张图回答训练与选择过程，最终泛化效果接着看同观测流测试误差。</p></div><p class="exhibit-source">三个训练种子的真实30轮开发曲线，空心点为各自开发集最优checkpoint；测试集不参与选择。</p>




<a id="figure-supplement-ppo-training"></a>

<div class="exhibit-intro" data-guide-figure="supplement-ppo-training"><p class="exhibit-title"><span class="exhibit-number">图 8</span> <strong>PPO在训练中得到怎样的公开奖励</strong></p><p class="exhibit-purpose">了解派单策略在120回合内的学习过程，并与最终确认成绩区分阅读。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-ppo-training.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>横轴是完整训练回合，纵轴是每步公开奖励的10回合滑动均值；数值为负时，−0.000705仍高于−0.000725。细线表示各训练种子，粗线表示同估计条件下的种子均值，图例区分名义＋PPO与CVAE＋PPO。</p><p><strong>◇ 读到什么：</strong>曲线上移表示这一奖励数值提高；是否查到更多异常，要由后面的留出确认结果判断。测试策略固定采用第120回合参数。</p></div><p class="exhibit-source">六个PPO的公开奖励训练曲线；细线表示训练种子，粗线为种子均值，采用10回合滑动窗口。</p>


<div class="table-guide" id="table-supplement-training"><div class="exhibit-intro" data-guide-table="supplement-training"><p class="exhibit-title"><span class="exhibit-number">表 9</span> <strong>三个温度模型的训练与参数选择记录</strong></p><p class="exhibit-purpose">对照开发曲线，查看每个模型最终保留哪一轮。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>每行对应一个训练种子；实际epoch是总训练轮数，选中epoch是开发误差最小的轮次。34,560/8,640为训练/开发快照数，开发加权RMSE以°C计，训练时间以分钟计。</p><p><strong>◇ 读到什么：</strong>三个模型各自根据开发集选择参数，再冻结用于测试；开发误差与后面的留出测试误差分别阅读。</p></div></div>
<div class="table-wrap"><table data-table="supplement-training" class="supplement-table"><thead><tr><th>训练种子</th><th>实际epoch</th><th>训练快照</th><th>开发快照</th><th>选中epoch</th><th>开发加权RMSE / °C</th><th>训练分钟</th></tr></thead><tbody><tr><td>271</td><td>30</td><td>34560</td><td>8640</td><td>29</td><td>0.164</td><td>3.05</td></tr><tr><td>811</td><td>30</td><td>34560</td><td>8640</td><td>27</td><td>0.161</td><td>3.12</td></tr><tr><td>1931</td><td>30</td><td>34560</td><td>8640</td><td>25</td><td>0.165</td><td>2.97</td></tr></tbody></table></div>

三个CVAE均训练30轮，各按开发加权MSE选择checkpoint；六个PPO共720个训练回合，固定第120回合参数。测试前锁定九个checkpoint SHA。奖励曲线记录实际训练过程，最终效果由留出回合评价。

<h3 id="estimation-results">4.2 固定公开观测流下的状态估计结果</h3>

#### 4.2.1 全机房与盲区机柜的温度误差

先让两种估计器读取同一份固定巡回观测记录，比较它们补全温度的能力。盲区指标排除当前新测量的位置，避免把直接填入的测量值算成预测成绩。



<a id="figure-supplement-estimation"></a>

<div class="exhibit-intro" data-guide-figure="supplement-estimation"><p class="exhibit-title"><span class="exhibit-number">图 9</span> <strong>相同观测下，温度估计误差降低多少</strong></p><p class="exhibit-purpose">单独比较两种估计器补全温度的能力，避免把巡检路线不同混进估计比较。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-estimation.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>三幅小图依次为全部位置RMSE、资产加权RMSE、盲区加权RMSE，纵轴都以°C计、方向↓。灰柱是名义热平衡，蓝柱是残差CVAE；柱上数字为均值，竖线为12组独立测试集计算的95%区间。</p><p><strong>◇ 读到什么：</strong>盲区误差从0.443降到0.172°C，均值下降61.2%；这一结果对应同一Tour观测流，说明学习估计改善了需要推算位置的温度表示。</p></div><p class="exhibit-source">两种估计器读取同一份Tour观测记录，并用相同的新测温度校正；盲区误差排除当前新测位置，误差线为12组独立测试集的95%区间。</p>


<div class="table-guide" id="table-supplement-fixed-stream"><div class="exhibit-intro" data-guide-table="supplement-fixed-stream"><p class="exhibit-title"><span class="exhibit-number">表 10</span> <strong>相同观测记录下的温度误差数值</strong></p><p class="exhibit-purpose">给估计误差柱图提供可逐项查读的准确数值。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>每格a [l,u]表示均值与95%测试组区间。RMSE和加权RMSE以°C计、方向↓；R²为无量纲、方向↑；最后一列排除当前新测位置。两行输入完全相同，差别在估计器。</p><p><strong>◇ 读到什么：</strong>盲区加权RMSE为0.443→0.172°C；读这张表可以集中判断温度补全能力。</p></div></div>
<div class="table-wrap"><table data-table="supplement-fixed-stream" class="supplement-table"><thead><tr><th>估计器</th><th>RMSE / °C</th><th>加权RMSE / °C</th><th>R²</th><th>盲区机柜加权RMSE / °C</th></tr></thead><tbody><tr><td>名义热平衡</td><td>0.528 [0.416, 0.646]</td><td>0.535 [0.419, 0.659]</td><td>0.9124 [0.8801, 0.9413]</td><td>0.443 [0.306, 0.589]</td></tr><tr><td>残差CVAE-U-Net</td><td>0.324 [0.303, 0.347]</td><td>0.328 [0.307, 0.350]</td><td>0.9602 [0.9580, 0.9621]</td><td>0.172 [0.145, 0.201]</td></tr></tbody></table></div>

相同观测下，残差CVAE-U-Net对全机房的加权RMSE由0.535降至0.328°C，每回合R²的均值由0.9124提高到0.9602。盲区机柜加权RMSE均值降低61.2%，说明它能更准确地补全未新测位置的温度；能否及时查到异常，接着看派单后的实际完成结果。

表中为48个故障条件的逐回合误差均值，95%区间按12组独立测试集计算。预登记主要比较为同一Tour观测流上的盲区机柜加权RMSE，CVAE−名义差为-0.271 [-0.398, -0.157]°C。

<h4 id="estimation-example">4.2.2 同流态势图与局部温度时序</h4>



<a id="figure-supplement-heatmaps"></a>

<div class="exhibit-intro" data-guide-figure="supplement-heatmaps"><p class="exhibit-title"><span class="exhibit-number">图 10</span> <strong>同一时刻的两种估计与事后温度对照</strong></p><p class="exhibit-purpose">把上一图的整体误差转成能逐柜比较的温度分布。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-heatmaps.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>三列依次为名义估计、CVAE估计和事后物理温度；同一个格子在三图中对应同一机柜。共同色标为45—75°C，先定位偏热区域，再比较前两图与右图相同位置的颜色差异。机柜格子是离散设备索引。</p><p><strong>◇ 读到什么：</strong>这是一个固定测试案例、注入后90秒的空间快照，用于直观看修正发生在哪里；总体精度仍以全部48个故障条件的误差图和表为准。</p></div><p class="exhibit-source">按编号选取首个测试条件、训练种子271和注入后90秒；名义与CVAE使用相同Tour观测流，三图共用45—75°C色标。</p>




<a id="figure-supplement-process"></a>

<div class="exhibit-intro" data-guide-figure="supplement-process"><p class="exhibit-title"><span class="exhibit-number">图 11</span> <strong>故障前后，局部柜温与组流量怎样变化</strong></p><p class="exhibit-purpose">补充温度快照看不到的时间过程，观察估计误差何时出现、何时被新量测校正。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-process.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>横轴统一为仿真秒数。上图读9号柜的真实、名义和CVAE温度，●点表示当前新量测；下图读第2组总流量。阴影标出故障注入窗口，65°C和33.6 kg/s参考线分别是研究温度与流量异常界值，两幅图各用自己的纵轴单位。</p><p><strong>◇ 读到什么：</strong>估计曲线需要沿整个异常前后过程比较；某次温度贴合或一次越界，只是这一局部案例的证据，确认还取决于巡检完成时间。</p></div><p class="exhibit-source">与温度图同一编号示例。阴影为故障注入窗口，点表示当前新温度量测；温度和流量阈值采用研究设定。</p>



示例按编号取`test00-compound`与训练种子271：快照为注入后90秒，时序为故障组内无固定温度点的局部1号柜。名义与CVAE读取同一Tour量测历史，三联图共用45—75°C色标；该例用于呈现重构差异，整体效应使用全部48个主要条件。

### 4.3 七方法专业确认与资源代价

#### 4.3.1 历史耦合工况A回顾

前期12个耦合过程共有89段异常，Tour／FIFO确认28/89与70/89；九条线性规则最高60/89。这一阶段用于建立机制基准，完整图、故障配置与负结果在[附录C—E](07-appendix-part02.md#historical-benchmark)保留。以下主比较使用独立新基准的210段异常，两批结果分别记账。
