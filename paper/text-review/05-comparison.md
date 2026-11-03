> 正文审阅版：正文、公式和数值表与单文件HTML同源；图版保留SVG链接，便于文本工具读取。

<a id="comparison"></a>

## 4. 实验验证层：多算法结果与机制诊断

<p class="chapter-lead">本章先给出评价和数据隔离方案，再报告状态估计、专业确认、计算代价与规模结果，最后解释估计精度与任务效果之间的差异。</p>

### 4.1 评价体系与独立实验设计

#### 4.1.1 四维指标与统计单位

原论文以VAE重建重要度图、以DRL调度水域巡检。本研究借鉴其分层评价思路，将状态准确性、持续巡检质量、专业确认和计算代价用于同一机房任务。[原论文](https://doi.org/10.1016/j.eswa.2025.126483)。

|维度|本任务指标|方向|
|---|---|---|
|状态估计|温度RMSE、资产加权RMSE、非刚量测加权RMSE、R²|误差低、R²高|
|持续巡检|静态资产重要度加权归一年龄J<sub>age</sub>（适配idleness）|低|
|异常确认|有效确认段数／比例、后果加权截尾等待、硬重访违规|确认多、等待短、约束零违规|
|资源与计算|移动变化、完成量变化、阶段p50／p95和训练耗时|联合判断收益与代价|

温度误差以物理柜温为目标；“非刚量测”排除当前端点直接回填的温度点。R²按逐回合SSE／SST计算后汇总，常量目标记NA。有效异常段要求至少3个连续5秒正标签，确认需在正标签端点完成合格且告警的专业量测；未确认段按结束时刻截尾。

加权年龄对各方法实际完成时刻解析积分，包含初始和1800秒终点间隔：

<div class="formula-scroll"><p class="formula" role="math">A<sub>j</sub>(t) = min[(t − L<sub>j</sub>)/D<sub>j</sub>,1]</p><p class="formula" role="math">J<sub>age</sub> = [1/(1800Σ<sub>j</sub>w<sub>j</sub>)] ∫<sub>0</sub><sup>1800</sup>Σ<sub>j</sub>w<sub>j</sub>A<sub>j</sub>(t)dt</p></div>

w为共同静态资产权重，D为专业重访期限，L为最近完成时刻。每条件先归一，再按登记权重汇总。主要统计先在条件内平均学习方法的三个模型种子，再在各物理种子块内等权四故障族；95%探索性区间采用12块、10,000次自举，随机种子20261103，训练种子变化另列，未做多重比较校正。

#### 4.1.2 数据划分与训练过程

|阶段|独立物理种子块|条件与用途|执行与训练记录|
|---|---:|---|---|
|训练|24|四故障＋健康／虚假提示；Tour与FIFO各一条观测流|288条流、34,560个快照；每策略种子120个PPO回合|
|开发|6|同六类条件；CVAE选择与冻结PPO诊断|72条流、8,640个快照；36次PPO诊断|
|最终测试|12|72条件，含60条唯一物理轨迹；种子与训练／开发隔离|7方法标签、每条件15个规则／模型实例，共1080回合|

四故障族为辅助馈电＋CDU衰减、接触热点、传感偏差和二次泵故障。健康与虚假提示共享物理过程，单列检查额外工作。四故障族在训练中已出现，留出对象为新的物理种子及登记的位置／相位组合；连续快照和模型重复各自计数。



<a id="figure-supplement-estimator-training"></a>

[图：三个训练种子的真实30轮开发曲线，空心点为各自开发集最优checkpoint；测试集不参与选择。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-estimator-training.svg)




<a id="figure-supplement-ppo-training"></a>

[图：六个PPO的公开奖励训练曲线；细线表示训练种子，粗线为种子均值，采用10回合滑动窗口。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-ppo-training.svg)


<div class="table-wrap"><table data-table="supplement-training" class="supplement-table"><thead><tr><th>训练种子</th><th>实际epoch</th><th>训练快照</th><th>开发快照</th><th>选中epoch</th><th>开发加权RMSE / °C</th><th>训练分钟</th></tr></thead><tbody><tr><td>271</td><td>30</td><td>34560</td><td>8640</td><td>29</td><td>0.164</td><td>3.05</td></tr><tr><td>811</td><td>30</td><td>34560</td><td>8640</td><td>27</td><td>0.161</td><td>3.12</td></tr><tr><td>1931</td><td>30</td><td>34560</td><td>8640</td><td>25</td><td>0.165</td><td>2.97</td></tr></tbody></table></div>

三个CVAE均训练30轮，各按开发加权MSE选择checkpoint；六个PPO共720个训练回合，固定第120回合参数。测试前锁定九个checkpoint SHA。奖励曲线记录实际训练过程，最终效果由留出回合评价。

<h3 id="estimation-results">4.2 固定公开观测流下的状态估计结果</h3>

#### 4.2.1 全局与非刚量测端点误差



<a id="figure-supplement-estimation"></a>

[图：所有估计器接收同一份已保存Tour公开观测流，使用相同刚量测校正；误差线为95%物理种子块区间。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-estimation.svg)


<div class="table-wrap"><table data-table="supplement-fixed-stream" class="supplement-table"><thead><tr><th>估计器</th><th>RMSE / °C</th><th>加权RMSE / °C</th><th>R²</th><th>非刚量测加权RMSE / °C</th></tr></thead><tbody><tr><td>名义热平衡</td><td>0.528 [0.416, 0.646]</td><td>0.535 [0.419, 0.659]</td><td>0.9124 [0.8801, 0.9413]</td><td>0.443 [0.306, 0.589]</td></tr><tr><td>残差CVAE-U-Net</td><td>0.324 [0.303, 0.347]</td><td>0.328 [0.307, 0.350]</td><td>0.9602 [0.9580, 0.9621]</td><td>0.172 [0.145, 0.201]</td></tr></tbody></table></div>

残差CVAE-U-Net在相同公开输入上降低了温度误差：全部端点加权RMSE由0.535降至0.328°C，逐回合R²均值由0.9124提高到0.9602。非刚量测加权RMSE均值降低61.2%。这支持学习估计器改善状态表示；专业确认仍需通过后面的任务结果判断。

表中为48个主要条件的逐回合误差均值及95%物理种子块区间。预登记主要比较为同一Tour观测流上的非刚量测加权RMSE，CVAE−名义差为-0.271 [-0.398, -0.157]°C。

<h4 id="estimation-example">4.2.2 同流态势图与局部温度时序</h4>



<a id="figure-supplement-heatmaps"></a>

[图：按编号选取首个测试条件、训练种子271和注入后90秒；名义与CVAE使用相同Tour观测流，三图共用45—75°C色标。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-heatmaps.svg)




<a id="figure-supplement-process"></a>

[图：与温度图同一编号示例。阴影为故障注入窗口，点表示当前新温度量测；温度和流量阈值采用研究设定。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-process.svg)



示例按编号取`test00-compound`与训练种子271：快照为注入后90秒，时序为故障组内无固定温度点的局部1号柜。名义与CVAE读取同一Tour量测历史，三联图共用45—75°C色标；该例用于呈现重构差异，整体效应使用全部48个主要条件。

### 4.3 七方法专业确认与资源代价

#### 4.3.1 历史耦合工况A回顾

前期12个耦合过程共有89段异常，Tour／FIFO确认28/89与70/89；九条线性规则最高60/89。这一阶段用于建立机制基准，完整图、故障配置与负结果在[附录C—E](07-appendix.md#historical-benchmark)保留。以下主比较使用独立新基准的210段异常，两批结果分别记账。

#### 4.3.2 新基准总表、四专业与配对效应

<div class="table-wrap"><table data-table="supplement-errors" class="supplement-table"><thead><tr><th>方法</th><th>RMSE / °C↓</th><th>加权RMSE / °C↓</th><th>R²↑</th><th>非刚量测加权RMSE / °C↓</th><th>模型／规则重复</th></tr></thead><tbody><tr data-supplement-method="nominal_tour"><td>名义＋Tour</td><td>0.528</td><td>0.535</td><td>0.9124</td><td>0.443</td><td>1个确定性规则</td></tr><tr data-supplement-method="nominal_fifo"><td>名义＋FIFO</td><td>0.532</td><td>0.535</td><td>0.9113</td><td>0.443</td><td>1个确定性规则</td></tr><tr data-supplement-method="nominal_greedy"><td>名义＋Greedy</td><td>0.533</td><td>0.537</td><td>0.9105</td><td>0.446</td><td>1个确定性规则</td></tr><tr data-supplement-method="nominal_ppo"><td>名义＋PPO</td><td>0.531</td><td>0.537</td><td>0.9112</td><td>0.445</td><td>3个独立训练种子</td></tr><tr data-supplement-method="cvae_fifo"><td>CVAE＋FIFO</td><td>0.323</td><td>0.327</td><td>0.9603</td><td>0.170</td><td>3个独立训练种子</td></tr><tr data-supplement-method="cvae_greedy"><td>CVAE＋Greedy</td><td>0.323</td><td>0.327</td><td>0.9602</td><td>0.171</td><td>3个独立训练种子</td></tr><tr data-supplement-method="cvae_ppo"><td>CVAE＋PPO</td><td>0.323</td><td>0.327</td><td>0.9602</td><td>0.171</td><td>3个独立训练种子</td></tr></tbody></table></div>
<div class="table-wrap"><table data-table="supplement-tasks" class="supplement-table"><thead><tr><th>方法</th><th>确认／唯一异常段</th><th>确认比例</th><th>每条件确认 [95%CI]</th><th>截尾等待 / 秒↓</th><th>加权年龄↓</th><th>移动相对Tour</th><th>完成量相对Tour</th><th>约束违规</th></tr></thead><tbody><tr data-supplement-method="nominal_tour"><td>名义＋Tour</td><td>94/210</td><td>44.8%</td><td>1.96 [1.31, 2.65]</td><td>106.75</td><td>0.310122</td><td>+0.00%</td><td>+0.00%</td><td>0</td></tr><tr data-supplement-method="nominal_fifo"><td>名义＋FIFO</td><td>155/210</td><td>73.8%</td><td>3.23 [2.83, 3.65]</td><td>94.24</td><td>0.311298</td><td>+0.34%</td><td>-0.15%</td><td>0</td></tr><tr data-supplement-method="nominal_greedy"><td>名义＋Greedy</td><td>154/210</td><td>73.3%</td><td>3.21 [2.81, 3.60]</td><td>94.36</td><td>0.311270</td><td>+0.34%</td><td>-0.15%</td><td>0</td></tr><tr data-supplement-method="nominal_ppo"><td>名义＋PPO</td><td>129.33/210</td><td>61.6%</td><td>2.69 [2.23, 3.17]</td><td>100.42</td><td>0.310877</td><td>+0.22%</td><td>-0.10%</td><td>0</td></tr><tr data-supplement-method="cvae_fifo"><td>CVAE＋FIFO</td><td>153/210</td><td>72.9%</td><td>3.19 [2.78, 3.61]</td><td>94.55</td><td>0.311256</td><td>+0.33%</td><td>-0.14%</td><td>0</td></tr><tr data-supplement-method="cvae_greedy"><td>CVAE＋Greedy</td><td>152/210</td><td>72.4%</td><td>3.17 [2.76, 3.58]</td><td>94.64</td><td>0.311217</td><td>+0.32%</td><td>-0.14%</td><td>0</td></tr><tr data-supplement-method="cvae_ppo"><td>CVAE＋PPO</td><td>153.67/210</td><td>73.2%</td><td>3.20 [2.78, 3.62]</td><td>94.65</td><td>0.311266</td><td>+0.33%</td><td>-0.14%</td><td>0</td></tr></tbody></table></div>


<a id="figure-supplement-methods"></a>

[图：48个主要条件，先平均三个模型种子、再等权四故障族；误差线为12个物理种子块的95%自举区间。等待对有异常的条件计算。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-methods.svg)




<a id="figure-supplement-professions"></a>

[图：四专业异常段的描述性确认比例，数字为确认数／专业异常总数；小数来自三个模型种子的平均。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-professions.svg)



48个主要条件共210段唯一异常。学习方法确认总数的小数来自三个模型种子的平均；闭环误差使用各方法自身的量测流，同流估计结果则使用4.2节的共同输入。

名义FIFO相对Tour新增61段有效确认，截尾等待从106.75缩短至94.24秒，移动增加0.34%、完成量下降0.15%；整体加权年龄从0.310122升至0.311298。各方法资格、预约、预算和初终点重访审计均为0违规。

三个模型种子平均后，CVAE-FIFO、CVAE-Greedy和CVAE-PPO分别确认153、152和153.67段，均未超过名义FIFO的155段。方法差异集中在热检查与制冷；电气均为12/12，自控均为8/12；在当前观测与专业完成时机设置下，这两类结果在方法间一致。



<a id="figure-supplement-contrasts"></a>

[图：预登记的配对比较及95%物理种子块自举区间。确认、等待、年龄与误差分别解释；区间不包含完整训练不确定性。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-contrasts.svg)


<div class="table-wrap"><table data-table="supplement-contrasts" class="supplement-table"><thead><tr><th>预登记比较</th><th>每条件确认差↑</th><th>截尾等待差 / 秒↓</th><th>归一年龄差↓</th><th>闭环加权RMSE差 / °C↓</th></tr></thead><tbody><tr><td>名义＋FIFO − 名义＋Tour</td><td>+1.27 [+0.62, +1.88]</td><td>-12.51 [-16.31, -8.75]</td><td>+0.001176 [+0.001052, +0.001292]</td><td>+0.001 [-0.053, +0.052]</td></tr><tr><td>CVAE＋FIFO − 名义＋FIFO</td><td>-0.04 [-0.09, +0.00]</td><td>+0.31 [+0.02, +0.70]</td><td>-0.000042 [-0.000072, -0.000015]</td><td>-0.208 [-0.311, -0.111]</td></tr><tr><td>CVAE＋Greedy − 名义＋Greedy</td><td>-0.04 [-0.09, +0.00]</td><td>+0.28 [+0.00, +0.67]</td><td>-0.000053 [-0.000093, -0.000021]</td><td>-0.210 [-0.314, -0.112]</td></tr><tr><td>名义＋PPO − 名义＋FIFO</td><td>-0.53 [-0.79, -0.26]</td><td>+6.18 [+4.23, +8.19]</td><td>-0.000421 [-0.000475, -0.000362]</td><td>+0.002 [-0.015, +0.018]</td></tr><tr><td>CVAE＋PPO − CVAE＋FIFO</td><td>+0.01 [-0.01, +0.04]</td><td>+0.10 [-0.15, +0.39]</td><td>+0.000010 [-0.000005, +0.000028]</td><td>+0.000 [-0.000, +0.000]</td></tr><tr><td>CVAE＋PPO − 名义＋PPO</td><td>+0.51 [+0.22, +0.78]</td><td>-5.77 [-7.59, -4.01]</td><td>+0.000389 [+0.000320, +0.000454]</td><td>-0.210 [-0.310, -0.115]</td></tr></tbody></table></div>

名义FIFO−Tour每主要条件净增+1.27 [+0.62, +1.88]段；CVAE-FIFO−名义FIFO为-0.04 [-0.09, +0.00]段；CVAE-PPO−CVAE-FIFO为+0.01 [-0.01, +0.04]段。区间表达物理种子块变化，[附录G](07-appendix.md#training-seeds)另列训练种子离散程度。

#### 4.3.3 健康、虚假提示与计算耗时

<div class="table-wrap"><table data-table="supplement-healthy" class="supplement-table"><thead><tr><th>方法</th><th>健康额外访问</th><th>虚假提示额外访问</th><th>健康误确认</th><th>虚假提示误确认</th><th>虚假提示完成量相对Tour</th><th>两组确认比例／等待</th></tr></thead><tbody><tr><td>名义＋Tour</td><td>0.00</td><td>0.00</td><td>0.00</td><td>0.00</td><td>+0.00%</td><td>NA / NA</td></tr><tr><td>名义＋FIFO</td><td>0.00</td><td>0.75</td><td>0.00</td><td>0.00</td><td>-0.04%</td><td>NA / NA</td></tr><tr><td>名义＋Greedy</td><td>0.00</td><td>0.75</td><td>0.00</td><td>0.00</td><td>-0.04%</td><td>NA / NA</td></tr><tr><td>名义＋PPO</td><td>0.00</td><td>0.42</td><td>0.00</td><td>0.00</td><td>-0.02%</td><td>NA / NA</td></tr><tr><td>CVAE＋FIFO</td><td>0.00</td><td>0.75</td><td>0.00</td><td>0.00</td><td>-0.04%</td><td>NA / NA</td></tr><tr><td>CVAE＋Greedy</td><td>0.00</td><td>0.75</td><td>0.00</td><td>0.00</td><td>-0.04%</td><td>NA / NA</td></tr><tr><td>CVAE＋PPO</td><td>0.00</td><td>0.75</td><td>0.00</td><td>0.00</td><td>-0.04%</td><td>NA / NA</td></tr></tbody></table></div>

健康与虚假提示各12条件。无评价异常时确认比例与异常等待为NA，额外访问及误确认按实测保留。所有方法在健康组均无额外访问和误确认。虚假提示下，FIFO、Greedy及CVAE-PPO平均各增加0.75次访问／条件，名义PPO为0.42次；这些跟进没有造成错误的专业确认。



<a id="figure-supplement-latency"></a>

[图：主要故障条件的逐回合p95均值，实测包含转换和CUDA同步。估计阶段已包含于完整控制周期，不能重复相加。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-latency.svg)


<div class="table-wrap"><table data-table="supplement-latency" class="supplement-table"><thead><tr><th>方法</th><th>估计p50 / ms</th><th>估计p95 / ms</th><th>派单p50 / ms</th><th>派单p95 / ms</th><th>完整周期p95 / ms</th></tr></thead><tbody><tr><td>名义＋Tour</td><td>0.17</td><td>0.23</td><td>0.45</td><td>0.90</td><td>1.53</td></tr><tr><td>名义＋FIFO</td><td>0.17</td><td>0.22</td><td>0.44</td><td>0.86</td><td>1.47</td></tr><tr><td>名义＋Greedy</td><td>0.17</td><td>0.22</td><td>0.44</td><td>0.87</td><td>1.48</td></tr><tr><td>名义＋PPO</td><td>0.18</td><td>0.24</td><td>1.28</td><td>2.95</td><td>3.59</td></tr><tr><td>CVAE＋FIFO</td><td>3.69</td><td>5.44</td><td>0.47</td><td>0.93</td><td>6.59</td></tr><tr><td>CVAE＋Greedy</td><td>3.53</td><td>5.07</td><td>0.48</td><td>0.95</td><td>6.27</td></tr><tr><td>CVAE＋PPO</td><td>3.63</td><td>5.34</td><td>1.31</td><td>3.00</td><td>8.10</td></tr></tbody></table></div>

硬件为NVIDIA GeForce RTX 4060 Laptop GPU，PyTorch 2.6.0＋CUDA 12.4、PyTorch CPU线程数2。上表是主要条件逐回合p50／p95的平均；神经估计包括转换、设备复制、前向、取回及CUDA同步，每次加载先做5次预热。完整周期包含选择、执行记账、下一观测估计和事件生命周期；物理轨迹预生成、记录、I/O与评分另计，估计阶段已包含于完整周期。

### 4.4 估计精度、队列时序与学习空间诊断

#### 4.4.1 连续重构误差与离散确认机会

CVAE-U-Net改善全局温度态势精度，及时确认还取决于局部提示、FIFO队列和合法访问的完成时机。原日志144组配对中，CVAE-FIFO新增2段、丢失8段，模型平均后净少2段，与155→153一致。

在`test04-cooling`、模型271中，CVAE将45号提示从860秒提前至840秒，但41号更早在835秒入队。860秒两候选均合法，CFIFO先查41号并在880秒确认，再于900秒检查45号，错过850—890秒评价段；名义FIFO在875秒确认45号、895秒才检查41号。这里出现一增一失的机会交换，完整时序见[附录H](07-appendix.md#gap-diagnosis)。

#### 4.4.2 合法候选稀疏与PPO排序自由度

训练记录中，约0.26%—0.27%的执行者实际选择集合包含多个合法候选。只有一项合法时，策略没有排序自由；这描述了当前责任区、返回约束与待办生成共同形成的决策空间。该比例的分母是执行者选择集合，完整计数与耗时在[附录G](07-appendix.md#training-seeds)。

在每策略120回合预算下，CVAE-PPO相对CVAE-FIFO的确认增量区间跨零；相对名义PPO的改善同时包含估计器与各自训练策略的变化。候选空间、奖励和训练预算的单独贡献可在下一轮独立比较中检验。

<h3 id="scale-results">4.5 模块化物理规模与数值一致性</h3>



<a id="figure-supplement-scale"></a>

[图：每规模三种子×健康／耦合两工况的纯物理过程实测；带tracemalloc开销，范围为六次实测最小—最大，未作大规模学习调度。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-scale.svg)


<div class="table-wrap"><table data-table="supplement-scale" class="supplement-table"><thead><tr><th>机柜数</th><th>热状态／指令状态</th><th>执行者／专业任务</th><th>物理耗时中位数 / 秒</th><th>Python峰值 / MiB</th><th>静态检查</th></tr></thead><tbody><tr><td>128</td><td>161／145</td><td>18／176</td><td>0.517</td><td>0.50</td><td>构造闭合巡回满足</td></tr><tr><td>512</td><td>641／577</td><td>72／704</td><td>0.483</td><td>1.70</td><td>构造闭合巡回满足</td></tr><tr><td>1024</td><td>1281／1153</td><td>144／1408</td><td>0.500</td><td>3.32</td><td>构造闭合巡回满足</td></tr></tbody></table></div>
<div class="table-wrap"><table data-table="supplement-scale-cycles" class="supplement-table"><thead><tr><th>机柜数</th><th>热检查：人数；周期／期限</th><th>电气：人数；周期／期限</th><th>制冷：人数；周期／期限</th><th>自控：人数；周期／期限</th></tr></thead><tbody><tr><td>128</td><td>12人；240/300秒</td><td>2人；310/600秒</td><td>2人；310/600秒</td><td>2人；270/600秒</td></tr><tr><td>512</td><td>48人；240/300秒</td><td>8人；385/600秒</td><td>8人；385/600秒</td><td>8人；345/600秒</td></tr><tr><td>1024</td><td>96人；240/300秒</td><td>16人；465/600秒</td><td>16人；465/600秒</td><td>16人；425/600秒</td></tr></tbody></table></div>

每规模为三种子×健康／耦合两条件，360个5秒物理步。耗时含tracemalloc开销，内存范围为该物理段及温度序列留存；静态检查评价已构造的专业巡回。三规模的构造闭合巡回均满足各专业期限。360步物理耗时中位数约0.48—0.52秒，未随柜数呈单调上升；Python追踪峰值由0.50增至3.32 MiB，范围为该物理段及温度序列的留存。

18次运行的最大能量平衡残差为7.97e-08 kJ，最大电功率平衡残差为8.73e-11 kW，用于核对数值守恒一致性。512／1024柜验证覆盖物理过程与静态巡回，学习闭环结果对应128柜。
