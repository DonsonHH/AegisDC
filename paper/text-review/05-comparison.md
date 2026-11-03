> 正文审阅版：正文、公式和数值表与单文件HTML同源；图版保留SVG链接，便于文本工具读取。

<a id="comparison"></a>

## 4. 独立补充基准：估计质量、专业确认与计算代价

原论文以<strong>VAE（变分自编码器）</strong>重建重要度图，以<strong>DRL（深度强化学习）</strong>调度巡检。可借鉴的是把估计准确性、持续巡检质量、异常任务效果和计算成本分层评价，再将估计器与调度器交叉比较。[原论文](https://doi.org/10.1016/j.eswa.2025.126483)。

|维度|本任务报告的指标|方向|
|---|---|---|
|状态估计|温度RMSE、资产重要度加权RMSE、R²|误差越低、R²越高越好|
|持续巡检|资产重要度加权归一年龄（适配idleness）|越低越好|
|异常任务|有效确认段数／比例、加权截尾等待、硬重访违规|确认越高、等待越短，约束零违规|
|效率与代价|移动变化、完成量变化、单步推理毫秒|联合判断任务收益与资源开销|

### 设计：先隔离数据，再交叉估计器与调度器

|阶段|独立物理种子块|条件与用途|实际执行／训练|
|---|---:|---|---|
|训练|24|四故障＋健康／虚假提示；Tour、FIFO各一条观测流|288条观测流，34,560个快照；每模型种子120个PPO训练回合|
|开发|6|同六类条件；选择CVAE、诊断冻结PPO|72条观测流，8,640个快照；36次PPO诊断|
|最终测试|12|72条件，含60条唯一物理轨迹；训练与开发种子隔离|7个方法标签、每条件15个规则／模型实例，共1080回合|

四种主要故障分别为辅助馈电＋CDU衰减、电气接触热点、传感偏差、二次泵故障。健康与虚假提示共享同一物理过程，用来检查无异常时的额外工作。最终测试的统计单位为12个物理种子块；连续快照、模型重复和异常段分别计数。

同一登记条件下，各方法共享由本地控制器推进并预先生成的物理轨迹。巡检策略改变路线、专业量测时机和后续估计；设备温度、流量与供电过程继续按该本地控制轨迹演化。



<a id="figure-supplement-crossed-design"></a>

[图：估计器与调度器的共同候选、约束和执行接口。PPO使用公开奖励训练，原始异常标签留给离线评价。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-crossed-design.svg)



PPO在与FIFO、Greedy相同的合法候选集合中决策，使用21维公开候选特征和32×32共享actor。每估计条件训练三个种子，各120个完整回合，固定最终策略；配对种子采用相同初始参数与训练案例次序。训练采用公开奖励的[PPO裁剪目标](https://arxiv.org/abs/1707.06347)，事后异常标签只参与评价。

### 真实训练记录与模型选择



<a id="figure-supplement-estimator-training"></a>

[图：三个训练种子的真实30轮开发曲线，空心点为各自开发集最优checkpoint；测试集不参与选择。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-estimator-training.svg)




<a id="figure-supplement-ppo-training"></a>

[图：六个PPO的公开奖励训练曲线；细线表示训练种子，粗线为种子均值，采用10回合滑动窗口。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-ppo-training.svg)


<div class="table-wrap"><table data-table="supplement-training" class="supplement-table"><thead><tr><th>训练种子</th><th>实际epoch</th><th>训练快照</th><th>开发快照</th><th>选中epoch</th><th>开发加权RMSE / °C</th><th>训练分钟</th></tr></thead><tbody><tr><td>271</td><td>30</td><td>34560</td><td>8640</td><td>29</td><td>0.164</td><td>3.05</td></tr><tr><td>811</td><td>30</td><td>34560</td><td>8640</td><td>27</td><td>0.161</td><td>3.12</td></tr><tr><td>1931</td><td>30</td><td>34560</td><td>8640</td><td>25</td><td>0.165</td><td>2.97</td></tr></tbody></table></div>

三个CVAE均训练30轮，按各自开发集加权MSE选checkpoint；六个PPO共720个训练回合，均使用固定第120回合参数。测试开始前锁定九个checkpoint的SHA，完整曲线与实际参数归档可回查。奖励曲线说明训练过程，留出测试中的确认、误差与成本共同评价模型价值。

### 同一公开观测流上的估计误差



<a id="figure-supplement-estimation"></a>

[图：所有估计器接收同一份已保存Tour公开观测流，使用相同刚量测校正；误差线为95%物理种子块区间。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-estimation.svg)


<div class="table-wrap"><table data-table="supplement-fixed-stream" class="supplement-table"><thead><tr><th>估计器</th><th>RMSE / °C</th><th>加权RMSE / °C</th><th>R²</th><th>非刚量测加权RMSE / °C</th></tr></thead><tbody><tr><td>名义热平衡</td><td>0.528 [0.416, 0.646]</td><td>0.535 [0.419, 0.659]</td><td>0.9124 [0.8801, 0.9413]</td><td>0.443 [0.306, 0.589]</td></tr><tr><td>残差CVAE-U-Net</td><td>0.324 [0.303, 0.347]</td><td>0.328 [0.307, 0.350]</td><td>0.9602 [0.9580, 0.9621]</td><td>0.172 [0.145, 0.201]</td></tr></tbody></table></div>

残差CVAE-U-Net在相同公开输入上降低了温度误差：全部端点加权RMSE由0.535降至0.328°C，逐回合R²均值由0.9124提高到0.9602。非刚量测加权RMSE均值降低61.2%。这支持学习估计器改善状态表示；专业确认仍需通过后面的任务结果判断。

表中为主要条件的逐回合误差均值，括号为95%物理种子块自举区间。**非刚量测加权RMSE**排除当前端点直接回填的温度量测，是预登记的估计主要比较；CVAE−名义差为-0.271 [-0.398, -0.157]°C。R²采用逐回合SSE／SST计算后汇总，常量目标记NA。

### 七方法闭环总表与四专业结果

<div class="table-wrap"><table data-table="supplement-errors" class="supplement-table"><thead><tr><th>方法</th><th>RMSE / °C↓</th><th>加权RMSE / °C↓</th><th>R²↑</th><th>非刚量测加权RMSE / °C↓</th><th>模型／规则重复</th></tr></thead><tbody><tr data-supplement-method="nominal_tour"><td>名义＋Tour</td><td>0.528</td><td>0.535</td><td>0.9124</td><td>0.443</td><td>1个确定性规则</td></tr><tr data-supplement-method="nominal_fifo"><td>名义＋FIFO</td><td>0.532</td><td>0.535</td><td>0.9113</td><td>0.443</td><td>1个确定性规则</td></tr><tr data-supplement-method="nominal_greedy"><td>名义＋Greedy</td><td>0.533</td><td>0.537</td><td>0.9105</td><td>0.446</td><td>1个确定性规则</td></tr><tr data-supplement-method="nominal_ppo"><td>名义＋PPO</td><td>0.531</td><td>0.537</td><td>0.9112</td><td>0.445</td><td>3个独立训练种子</td></tr><tr data-supplement-method="cvae_fifo"><td>CVAE＋FIFO</td><td>0.323</td><td>0.327</td><td>0.9603</td><td>0.170</td><td>3个独立训练种子</td></tr><tr data-supplement-method="cvae_greedy"><td>CVAE＋Greedy</td><td>0.323</td><td>0.327</td><td>0.9602</td><td>0.171</td><td>3个独立训练种子</td></tr><tr data-supplement-method="cvae_ppo"><td>CVAE＋PPO</td><td>0.323</td><td>0.327</td><td>0.9602</td><td>0.171</td><td>3个独立训练种子</td></tr></tbody></table></div>
<div class="table-wrap"><table data-table="supplement-tasks" class="supplement-table"><thead><tr><th>方法</th><th>确认／唯一异常段</th><th>确认比例</th><th>每条件确认 [95%CI]</th><th>截尾等待 / 秒↓</th><th>加权年龄↓</th><th>移动相对Tour</th><th>完成量相对Tour</th><th>约束违规</th></tr></thead><tbody><tr data-supplement-method="nominal_tour"><td>名义＋Tour</td><td>94/210</td><td>44.8%</td><td>1.96 [1.31, 2.65]</td><td>106.75</td><td>0.310122</td><td>+0.00%</td><td>+0.00%</td><td>0</td></tr><tr data-supplement-method="nominal_fifo"><td>名义＋FIFO</td><td>155/210</td><td>73.8%</td><td>3.23 [2.83, 3.65]</td><td>94.24</td><td>0.311298</td><td>+0.34%</td><td>-0.15%</td><td>0</td></tr><tr data-supplement-method="nominal_greedy"><td>名义＋Greedy</td><td>154/210</td><td>73.3%</td><td>3.21 [2.81, 3.60]</td><td>94.36</td><td>0.311270</td><td>+0.34%</td><td>-0.15%</td><td>0</td></tr><tr data-supplement-method="nominal_ppo"><td>名义＋PPO</td><td>129.33/210</td><td>61.6%</td><td>2.69 [2.23, 3.17]</td><td>100.42</td><td>0.310877</td><td>+0.22%</td><td>-0.10%</td><td>0</td></tr><tr data-supplement-method="cvae_fifo"><td>CVAE＋FIFO</td><td>153/210</td><td>72.9%</td><td>3.19 [2.78, 3.61]</td><td>94.55</td><td>0.311256</td><td>+0.33%</td><td>-0.14%</td><td>0</td></tr><tr data-supplement-method="cvae_greedy"><td>CVAE＋Greedy</td><td>152/210</td><td>72.4%</td><td>3.17 [2.76, 3.58]</td><td>94.64</td><td>0.311217</td><td>+0.32%</td><td>-0.14%</td><td>0</td></tr><tr data-supplement-method="cvae_ppo"><td>CVAE＋PPO</td><td>153.67/210</td><td>73.2%</td><td>3.20 [2.78, 3.62]</td><td>94.65</td><td>0.311266</td><td>+0.33%</td><td>-0.14%</td><td>0</td></tr></tbody></table></div>


<a id="figure-supplement-methods"></a>

[图：48个主要条件，先平均三个模型种子、再等权四故障族；误差线为12个物理种子块的95%自举区间。等待对有异常的条件计算。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-methods.svg)




<a id="figure-supplement-professions"></a>

[图：四专业异常段的描述性确认比例，数字为确认数／专业异常总数；小数来自三个模型种子的平均。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-professions.svg)



48个主要条件共有210段唯一评价异常。各学习方法先平均三个模型种子，因此确认总数允许出现小数；这表示训练重复的平均效果。表中误差使用各自闭环形成的量测流，固定观测流的独立估计比较则使用上表。

名义FIFO相对Tour新增61段有效确认，截尾等待从106.75缩短至94.24秒，移动增加0.34%、完成量下降0.15%；整体加权年龄从0.310122升至0.311298。各方法资格、预约、预算和初终点重访审计均为0违规。

三个模型种子平均后，CVAE-FIFO、CVAE-Greedy和CVAE-PPO分别确认153、152和153.67段，均未超过名义FIFO的155段。方法差异集中在热检查与制冷；电气均为12/12，自控均为8/12；在当前观测与专业完成时机设置下，这两类结果在方法间一致。

### 为什么估计更准，确认数仍以名义FIFO为高？

CVAE-U-Net的已验证收益是**全局温度态势重构精度**；有效确认还取决于局部越阈值提示、FIFO队列和受保护访问的完成时机。连续误差降低，并不保证短异常窗口内的确认数同步增加。

事后逐事件核对48条件×3个模型种子的144组配对，CVAE-FIFO相对名义FIFO新增2段、丢失8段，按训练种子平均后净少2段。一个具体例子是制冷故障案例04：CVAE将45号柜的提示从860秒提前到840秒，但同一队列中的41号柜更早在835秒入队，860秒时先被选中。于是CVAE在880秒确认了41号，45号却到900秒才完成，错过850—890秒评价段；名义FIFO则在875秒确认45号、895秒才检查41号。这里发生的是确认机会的交换。

这些轨迹显示，局部估计偏差与队列先后会改变确认机会；现有日志不支持把全部差异统一归因于“名义温度普遍偏高”，也没有测得CVAE组更低的专业误确认率。逐段得失与时间核对见[附录H](07-appendix.md#gap-diagnosis)。

### 配对增量、训练差异与正常工况



<a id="figure-supplement-contrasts"></a>

[图：预登记的配对比较及95%物理种子块自举区间。确认、等待、年龄与误差分别解释；区间不包含完整训练不确定性。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-contrasts.svg)


<div class="table-wrap"><table data-table="supplement-contrasts" class="supplement-table"><thead><tr><th>预登记比较</th><th>每条件确认差↑</th><th>截尾等待差 / 秒↓</th><th>归一年龄差↓</th><th>闭环加权RMSE差 / °C↓</th></tr></thead><tbody><tr><td>名义＋FIFO − 名义＋Tour</td><td>+1.27 [+0.62, +1.88]</td><td>-12.51 [-16.31, -8.75]</td><td>+0.001176 [+0.001052, +0.001292]</td><td>+0.001 [-0.053, +0.052]</td></tr><tr><td>CVAE＋FIFO − 名义＋FIFO</td><td>-0.04 [-0.09, +0.00]</td><td>+0.31 [+0.02, +0.70]</td><td>-0.000042 [-0.000072, -0.000015]</td><td>-0.208 [-0.311, -0.111]</td></tr><tr><td>CVAE＋Greedy − 名义＋Greedy</td><td>-0.04 [-0.09, +0.00]</td><td>+0.28 [+0.00, +0.67]</td><td>-0.000053 [-0.000093, -0.000021]</td><td>-0.210 [-0.314, -0.112]</td></tr><tr><td>名义＋PPO − 名义＋FIFO</td><td>-0.53 [-0.79, -0.26]</td><td>+6.18 [+4.23, +8.19]</td><td>-0.000421 [-0.000475, -0.000362]</td><td>+0.002 [-0.015, +0.018]</td></tr><tr><td>CVAE＋PPO − CVAE＋FIFO</td><td>+0.01 [-0.01, +0.04]</td><td>+0.10 [-0.15, +0.39]</td><td>+0.000010 [-0.000005, +0.000028]</td><td>+0.000 [-0.000, +0.000]</td></tr><tr><td>CVAE＋PPO − 名义＋PPO</td><td>+0.51 [+0.22, +0.78]</td><td>-5.77 [-7.59, -4.01]</td><td>+0.000389 [+0.000320, +0.000454]</td><td>-0.210 [-0.310, -0.115]</td></tr></tbody></table></div>

名义FIFO−Tour的每主要条件净增确认为+1.27 [+0.62, +1.88]段；CVAE-FIFO−名义FIFO为-0.04 [-0.09, +0.00]段；CVAE-PPO−CVAE-FIFO为+0.01 [-0.01, +0.04]段。先平均模型种子、再等权四故障族，对12种子块进行10,000次自举；三个训练种子的离散程度另见附录，区间表示物理过程变化。

<div class="table-wrap"><table data-table="supplement-healthy" class="supplement-table"><thead><tr><th>方法</th><th>健康额外访问</th><th>虚假提示额外访问</th><th>健康误确认</th><th>虚假提示误确认</th><th>虚假提示完成量相对Tour</th><th>两组确认比例／等待</th></tr></thead><tbody><tr><td>名义＋Tour</td><td>0.00</td><td>0.00</td><td>0.00</td><td>0.00</td><td>+0.00%</td><td>NA / NA</td></tr><tr><td>名义＋FIFO</td><td>0.00</td><td>0.75</td><td>0.00</td><td>0.00</td><td>-0.04%</td><td>NA / NA</td></tr><tr><td>名义＋Greedy</td><td>0.00</td><td>0.75</td><td>0.00</td><td>0.00</td><td>-0.04%</td><td>NA / NA</td></tr><tr><td>名义＋PPO</td><td>0.00</td><td>0.42</td><td>0.00</td><td>0.00</td><td>-0.02%</td><td>NA / NA</td></tr><tr><td>CVAE＋FIFO</td><td>0.00</td><td>0.75</td><td>0.00</td><td>0.00</td><td>-0.04%</td><td>NA / NA</td></tr><tr><td>CVAE＋Greedy</td><td>0.00</td><td>0.75</td><td>0.00</td><td>0.00</td><td>-0.04%</td><td>NA / NA</td></tr><tr><td>CVAE＋PPO</td><td>0.00</td><td>0.75</td><td>0.00</td><td>0.00</td><td>-0.04%</td><td>NA / NA</td></tr></tbody></table></div>

健康和虚假提示工况各12个条件，无评价异常时确认比例与异常条件等待记NA，保留额外访问、误确认及完成量代价。所有方法在健康组均无额外访问和误确认。虚假提示下，FIFO、Greedy及CVAE-PPO平均各增加0.75次访问／条件，名义PPO为0.42次；这些跟进没有造成错误的专业确认。

### 推理与派单计算成本



<a id="figure-supplement-latency"></a>

[图：主要故障条件的逐回合p95均值，实测包含转换和CUDA同步。估计阶段已包含于完整控制周期，不能重复相加。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-latency.svg)


<div class="table-wrap"><table data-table="supplement-latency" class="supplement-table"><thead><tr><th>方法</th><th>估计p50 / ms</th><th>估计p95 / ms</th><th>派单p50 / ms</th><th>派单p95 / ms</th><th>完整周期p95 / ms</th></tr></thead><tbody><tr><td>名义＋Tour</td><td>0.17</td><td>0.23</td><td>0.45</td><td>0.90</td><td>1.53</td></tr><tr><td>名义＋FIFO</td><td>0.17</td><td>0.22</td><td>0.44</td><td>0.86</td><td>1.47</td></tr><tr><td>名义＋Greedy</td><td>0.17</td><td>0.22</td><td>0.44</td><td>0.87</td><td>1.48</td></tr><tr><td>名义＋PPO</td><td>0.18</td><td>0.24</td><td>1.28</td><td>2.95</td><td>3.59</td></tr><tr><td>CVAE＋FIFO</td><td>3.69</td><td>5.44</td><td>0.47</td><td>0.93</td><td>6.59</td></tr><tr><td>CVAE＋Greedy</td><td>3.53</td><td>5.07</td><td>0.48</td><td>0.95</td><td>6.27</td></tr><tr><td>CVAE＋PPO</td><td>3.63</td><td>5.34</td><td>1.31</td><td>3.00</td><td>8.10</td></tr></tbody></table></div>

硬件为NVIDIA GeForce RTX 4060 Laptop GPU，PyTorch 2.6.0＋CUDA 12.4，PyTorch CPU线程数2。表为主要条件逐回合p50／p95的平均；神经估计包括数据转换、设备复制、前向、取回及CUDA同步，加载后5次合成公开输入预热单列。完整控制周期包括执行记账、下一观测估计及事件生命周期；估计阶段已包含其中，物理预生成、记录和I/O另计。

加权年龄由各任务完成时刻解析积分，采用每过程共同的静态资产权重及专业重访期限：

<div class="formula-scroll"><p class="formula" role="math">A<sub>j</sub>(t) = min[(t − L<sub>j</sub>)/D<sub>j</sub>,1]</p><p class="formula" role="math">J<sub>age</sub> = [1/(1800Σ<sub>j</sub>w<sub>j</sub>)] ∫<sub>0</sub><sup>1800</sup>Σ<sub>j</sub>w<sub>j</sub>A<sub>j</sub>(t)dt</p></div>

w由共同静态资产记录取得，各自检查轨迹决定年龄；包含初始和1800秒终点的完整间隔。新基准先在每条件归一，再依登记的种子块与故障权重汇总。该定义保留“重要任务长期未查代价更高”的思想，单位为无量纲。

<aside class="scope-note"><p><strong>本轮证据范围：</strong>新基准共2204次环境尝试，含兼容回放、采集、训练、开发诊断及1080次最终测试，另有18次纯物理规模运行。主推断以12个独立种子块、48个主要条件为单位。旧包中“未留帧／未计时”的字段继续按原件保留，见附录E；合成物理温度误差用于本基准内比较。</p></aside>
