# 大型液冷算力设施的多系统巡检研究

导师自阅报告 · 三系统模型、学习估计与四专业独立基准 · 2026-11-03

<aside class="project-summary" aria-label="项目主线摘要"><strong>项目主线与现有成果</strong><p>本项目建立配电、双回路液冷与局部控制的耦合过程，以公开遥测、学习估计和专业巡检形成闭环。本次补充3个CVAE-U-Net、6个PPO的真实训练，在12个独立种子块、四故障和两检查条件上完成1080个最终测试回合。{{SUPPLEMENT_MAIN_FINDING}}此前事件包的28/89→70/89与九规则负结果作为历史基准保留。</p></aside>

<!-- section:overview -->
## 报告主线与完成概览

|导师关心的内容|本报告的主要材料|位置|
|---|---|---|
|配电及RGB转红外视觉工作|10 kV—380 V交流—直流机柜依赖链；已有视觉样例、参考入口和电气量测更新|[三系统与视觉](#model)|
|冷却塔、泵、CDU、冷板及自控|双回路架构、实际三路反馈方程、2026双国标的对照状态|[模型与控制](#model)|
|大型设施复杂度|El Capitan性能／功率参照；当前热状态、指令状态、任务规模及扩展条件|[规模参照](#scale)|
|全局风险态势|名义／CVAE与事后温度同流对照、耦合故障时序、原风险提示|[全局态势](#hotspots)|
|原论文指标与横向比较|估计器×调度器七方法、四专业确认、误差、成本、训练与区间|[独立比较](#comparison)|

本次主比较采用名义与CVAE两种估计，交叉FIFO、Greedy与PPO，并保留固定Tour基准。RGB生成研究作为独立视觉成果展示。完整方法见[补充基准说明](supplement-study-methods.md)；历史FIFO日志、九规则和逐条件数据放在[技术附录](#appendix)。

<!-- section:model -->
## 1. 三系统模型、视觉感知与大型设施参照

### 配电与双回路液冷怎样连起来

**供电既决定计算发热，也影响冷却设备的排热能力。** 模型按10 kV入口、380 V交流配电、UPS／整流及54 V直流机柜组织依赖链；辅助馈电可用性进入二次泵有效速度，泵送流量和CDU换热共同影响设备温度。

**CDU**是冷却液分配与换热单元。一次回路连接设施冷源，二次回路连接机柜冷板，两侧在CDU交换热量。El Capitan／Cray EX的官方资料提供了双回路、冷板和测控层次的工程参照。[LLNL](https://www.llnl.gov/article/54496/meet-machines-matter-how-el-capitan-keeps-its-cool)、[HPE](https://www.hpe.com/us/en/collaterals/collateral.a00094635enw.html)。

{{FIGURE:model}}

|计算对象|当前关系及其用途|
|---|---|
|机柜热状态|热容×温升速率＝送达IT功率−冷板换热−环境散热|
|CDU与一次回路|有效度、两侧热容流率和供回液温差决定换热；塔排热影响共享一次供液|
|泵送与供电|有效泵速包含“指令×√辅助供电可用性”，水力代理据此求流量与压差|
|电气接点|接触损耗驱动接点温升；合格电气检查更新该组接点温度观测|

### RGB→IR：已有视觉成果如何接到配电巡检

这里的<strong>PID</strong>指Physics-Informed Diffusion图像生成工作；RGB表示可见光图像，IR表示红外。已有PID及视觉项目分支B-PID保留了可见光到伪彩IR显示的实验材料。下面展示一个户外电气设备的实际样例，作为视觉支路的已有成果。[原PID方法](https://github.com/fangyuanmao/PID)。

{{FIGURE:pid-visual-sample}}

本课题拟面向开关柜、母排及交直流接点，把图像参考关联到待核查部位，再以专业测量完成电气确认。**当前Renly已有参考元数据入口，以及“合格接点测温→接触温度状态更新”通道**；RGB采集、生成推理、热点选点与调度之间的桥接按下图列为待接步骤。

{{FIGURE:visual-interface}}

图像支路提供外观参考，℃数值来自校准测温通道。当前更新为<strong>T̂<sub>contact,p</sub>←合格接点量测</strong>；接触电阻属于物理过程的设定参数，其反向辨识另需电流、热响应和换热条件。已有视觉样例与本轮机房基准分别记录。

<aside class="scope-note"><p><strong>视觉材料口径：</strong>三联图为户外绝缘子／铁塔／导线的同图精修示例，像素表示伪彩显示外观。PID主训练材料的1,367对属于野火域；电气应用及留出sanity另有记录，适用范围为显示图重建。当前机房主比较中的电气量测由合成专业通道提供。详见视觉接口核查。</p></aside>

<h3 id="standards">自控系统：实际反馈方程与2026双国标对照</h3>

当前本地控制器同时调节二次泵、塔风机和IT限功率。其输入为本地设备传感温度和一次液温；巡检侧另通过32个固定温度遥测点及完成的专业量测获取信息。

<div class="principle-box" id="principle-control">
<h3>已运行的三路控制目标</h3>
<div class="formula-scroll"><p class="formula" role="math">u*<sub>p</sub> = clip[0.85 + 0.035(max<sub>i∈p</sub>T<sup>sens</sup><sub>i</sub> − 58), 0.75, 1.2]</p><p class="formula" role="math">v* = clip[0.85 + 0.10(T<sub>primary</sub> − 32), 0.25, 1.2]</p><p class="formula" role="math">θ*<sub>i</sub> = clip[1 − 0.035(T<sup>sens</sup><sub>i</sub> − 65), 0.20, 1]</p><p class="formula" role="math">x<sub>k+1</sub> = x<sub>k</sub> + 0.25(x*<sub>k</sub> − x<sub>k</sub>)</p></div>
<p>u为泵指令，v为塔风机指令，θ为限功率系数；温度用°C，指令无量纲。5秒步长对应20秒一阶命令滞后。设备代理温度达到95°C时，模拟硬件保护将实际限功率系数置零。</p>
</div>

|2026液冷国家标准|官方发布／实施信息|本轮对照的实际状态|
|---|---|---|
|[GB/T 48023-2026《数据中心冷板式液冷系统技术规范》](https://std.samr.gov.cn/gb/search/gbDetailed?id=581F4B90BB7B80E8E06397BE0A0AF9E7)|2026-07-30发布；2027-02-01实施|已定位正式入口和元数据；正式目录、控制条款及阈值尚未取得可核读记录|
|[GB/T 48097-2026《数据中心冷板式液冷机柜通用规范》](https://std.samr.gov.cn/gb/search/gbDetailed?id=5A13050B0299303FE06397BE0A0ADA7D)|2026-08-28发布；2027-03-01实施|同上；按系统与机柜两层建立后续映射|

本模型已计算温度、流量和水力压差，并实现上述温度反馈与模拟断载。压差反馈、防凝露、低流量联锁和多模式控制属于下一版设计字段；将正式要求对应到测量、控制动作与验证工况后再接入。33.6 kg/s等现有异常界值采用本研究设定。

<h3 id="scale">面向E级设施的热负载参照与当前规模</h3>

本研究采用<strong>大功率液冷超算机房的负载数量级</strong>作为工程参照。以El Capitan为例，TOP500的2026年6月记录给出Rmax＝1.809 EFLOP/s、理论Rpeak＝2.82110 EFLOP/s、报告功率29.68462 MW（测量等级2）。E级以每秒10<sup>18</sup>次浮点运算描述计算性能。[TOP500原始记录](https://www.top500.org/system/180307/)。

|参照量／模型量|当前数值|解释|
|---|---:|---|
|El Capitan基准报告功率|29.68462 MW|绑定TOP500期次与测量等级|
|本模型名义IT功率|32 MW|128×250 kW，用于设置研究负载|
|历史12个主过程峰值总输入|23.15—24.14 MW|从保存过程元数据读取|
|机柜／设备组|128／16|每组8柜，形成共享冷源和组内耦合|
|热状态／指令滞后状态|161／145|前者含机柜、液温和接点温度；后者含泵、风机和限功率命令|
|专业任务／执行者|176／18|热、电气、制冷、自控四类持续检查|

32 MW名义负载用于研究这一功率数量级下的供电—排热联动；算力性能、额定IT与基准报告功率分别列示。底层按8柜组组织参数，端到端学习巡检固定为128柜／16组。本次另外执行512／1024柜的纯物理过程和静态人员巡回检查，名义IT参数积分别为128／256 MW。

### 已补充的物理规模检查

{{FIGURE:supplement-scale}}
{{SUPPLEMENT_SCALE_TABLE}}
{{SUPPLEMENT_SCALE_CYCLES_TABLE}}

每规模为三个独立种子×健康／耦合两条件，360个5秒物理步。耗时含Python内存追踪开销，内存列为追踪峰值；闭合周期按已构造的本人巡回与专业期限检查。{{SUPPLEMENT_SCALE_FINDING}}

18次物理运行记录的最大能量平衡残差为{{SUPPLEMENT_ENERGY_RESIDUAL}} kJ，最大电功率平衡残差为{{SUPPLEMENT_ELECTRIC_RESIDUAL}} kW，用于核对本次数值积分的守恒一致性。

<aside class="scope-note"><p><strong>工程范围：</strong>模型为集中参数研究设定，主算法评价为128柜。512／1024柜结果覆盖物理过程与静态构造巡回，大规模学习调度、现场校准和E/G算力映射继续作为独立工程任务。正式国标的访问与控制覆盖见工程核查。</p></aside>

<!-- section:hotspots -->
## 2. 状态估计与全机房风险态势

系统为128个机柜各保留一个温度估计：以公开功率、供液温度和流量估计推进热平衡，每5秒更新；32个固定温度点持续校正，热巡检完成后校正对应机柜。它形成覆盖全机房的连续<strong>温度态势</strong>，再按统一公式产生风险提示。

{{PAIR:estimated-temperature,offline-temperature}}

两图采用同一45—75°C色标，每格一柜，蓝—黄—红呈现连续温度梯度。左侧红框标出该帧原热风险分>0的64、67、70号柜；黑点是32个固定温度遥测点。第9组的热点在估计与事后温度中均可见。

这是一段已有辅助馈电故障工程过程的500秒帧，按16组设备布置展示。连续色阶用于读出温度分布，调度仍使用原有热风险式：

<div class="formula-scroll"><p class="formula" role="math">r<sub>i</sub> = min{4, max(T̂<sub>i</sub> − 65, 0)/20 + 0.25[1 − P<sub>del,i</sub>/max(P<sub>req,i</sub>, ε)]}</p></div>

温度越界和功率缺口共同产生严重度提示。RGB→IR外观参考与这一数值温度估计承担不同任务：前者面向视觉线索，后者形成巡检端可计算的状态和风险。原风险分布、热平衡细式及500秒数值表放在附录A，便于逐项核对。

<aside class="scope-note"><p><strong>图的量与来源：</strong>色阶为设备代表温度（°C），红框为原风险提示，65°C风险起算点保持原设定。该工程回看、第3节历史12过程和第4节补充测试分别记账。右图用于事后核查，在线派单使用公开观测及估计。</p></aside>

### 学习估计器：在名义热平衡上估计温度残差

新估计器将最近四个连续5秒端点的14维公开特征与当前名义温度拼成57通道输入，以8×16设备网格计算空间残差。两个下采样层、空间跳接和16维条件潜变量组成295,777参数的CVAE-U-Net。训练用物理温度监督，运行时使用条件先验均值；两种估计器都以当时刚完成的温度量测覆盖对应位置。

{{FIGURE:supplement-unet}}

这是一项温度任务适配：输出为设备温度残差，输入为遥测和专业量测历史。条件先验／后验、空间编码与解码的依据分别见[条件生成模型](https://proceedings.neurips.cc/paper_files/paper/2015/file/8d55a249e6baa5c06772297520da2051-Paper.pdf)和[U-Net](https://arxiv.org/abs/1505.04597)；实际结构与训练设置在方法说明中逐项列出。

### 新测试过程的全机房态势与时序

{{FIGURE:supplement-heatmaps}}
{{FIGURE:supplement-process}}

两图固定使用测试案例00的耦合条件与训练种子271；快照取故障注入后90秒，时序取故障组内无固定温度点的局部1号柜。名义和CVAE读取同一份Tour观测流，刚量测标志包含固定遥测与专业热检查。误差总体结论使用全部48个主要条件，见第4节。

<!-- section:fifo -->
## 3. 巡检机制与历史闭环基准

第一阶段采用<strong>名义估计＋返回保护FIFO</strong>作为机制基准。FIFO（First In, First Out，先入先出）在执行者空闲时，从本人合法风险请求中选择最早出现的一项；资格、预约、预算和返回时间先行核查，原例行循环持续保留。

每回合为1800秒、18名执行者，全体额外访问上限12次，请求待派有效期120秒。

{{FIGURE:inspection-architecture}}

临时加查前，程序计算“现在出发、完成加查、返回并完成原任务”是否赶上截止，并逐项核对完整所属循环：

<div class="formula-scroll"><p class="formula" role="math">t + τ(p,x) + τ(x,r) ≤ L<sub>r</sub> + D<sub>r</sub>；对完整循环每项F<sub>j</sub> ≤ L′<sub>j</sub> + D<sub>j</sub></p></div>

τ包含移动和目的任务服务，L为上次完成时刻、D为最大重访间隔；额外加查x与原定下一项r分别计账。完整取整、初始时刻和返回证书例子见附录B。

### 工况A：供电可用性下降引发热—冷传播

本批12个配对过程统一注入辅助馈电故障与CDU换热衰减，持续180秒；通过不同种子、目标设备组和开始时刻比较。辅助供电乘子为0.05、CDU换热乘子为0.20，形成77段热异常和12段制冷异常。电气接触温升及传感偏差仍按各自专业检查，但这批故障的评价段集中在热和制冷。

本次独立补充基准另行覆盖接触热点、传感偏差与二次泵故障，见第4节；RGB参考融合属于视觉支路后续验证。历史工况A的12行配置、四专业阈值和原件保持可回查。

{{FIGURE:confirmations}}

FIFO相对固定巡回新增45段、丢失3段，净增42段，平均每过程净增3.50段；探索性95%自举区间为[2.42,4.50]。硬重访、资格与预约违规均为0。此结果建立了<strong>耦合过程—部分观测—风险请求—受保护执行—专业确认</strong>的闭环基准。

{{FIGURE:outcome-costs}}

同权限的九个预登记响应／暂缓规则确认28—60段，最好两条均为60，低于FIFO的70。记录显示，高风险门槛压掉了加查，固定等待门槛也会改变短异常窗口内的检查机会。正文将它们作为开发对照；得分式、具体得失及原轨迹图保留在附录C。

<aside class="scope-note"><p><strong>验证单位：</strong>12是配对物理过程数，89是其中的连续异常段数。专业确认沿用原包5秒采样端点评价；一次测量需告警且落在原标签的有效采样端点。九规则来自同12个已见过程的开发比较，模型调用与训练均为0。</p></aside>

<!-- section:comparison -->
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

{{FIGURE:supplement-crossed-design}}

PPO在与FIFO、Greedy相同的合法候选集合中决策，使用21维公开候选特征和32×32共享actor。每估计条件训练三个种子，各120个完整回合，固定最终策略；配对种子采用相同初始参数与训练案例次序。训练采用公开奖励的[PPO裁剪目标](https://arxiv.org/abs/1707.06347)，事后异常标签只参与评价。

### 真实训练记录与模型选择

{{FIGURE:supplement-estimator-training}}
{{FIGURE:supplement-ppo-training}}
{{SUPPLEMENT_TRAINING_TABLE}}

三个CVAE均训练30轮，按各自开发集加权MSE选checkpoint；六个PPO共720个训练回合，均使用固定第120回合参数。测试开始前锁定九个checkpoint的SHA，完整曲线与实际参数归档可回查。奖励曲线说明训练过程，留出测试中的确认、误差与成本共同评价模型价值。

### 同一公开观测流上的估计误差

{{FIGURE:supplement-estimation}}
{{SUPPLEMENT_FIXED_TABLE}}

{{SUPPLEMENT_ESTIMATION_FINDING}}

表中为主要条件的逐回合误差均值，括号为95%物理种子块自举区间。**非刚量测加权RMSE**排除当前端点直接回填的温度量测，是预登记的估计主要比较；CVAE−名义差为{{SUPPLEMENT_FIXED_DELTA}}°C。R²采用逐回合SSE／SST计算后汇总，常量目标记NA。

### 七方法闭环总表与四专业结果

{{SUPPLEMENT_ERROR_TABLE}}
{{SUPPLEMENT_TASK_TABLE}}
{{FIGURE:supplement-methods}}
{{FIGURE:supplement-professions}}

48个主要条件共有{{SUPPLEMENT_SEGMENTS}}段唯一评价异常。各学习方法先平均三个模型种子，因此确认总数允许出现小数；这表示训练重复的平均效果。表中误差使用各自闭环形成的量测流，固定观测流的独立估计比较则使用上表。

{{SUPPLEMENT_TASK_FINDING}}

### 配对增量、训练差异与正常工况

{{FIGURE:supplement-contrasts}}
{{SUPPLEMENT_CONTRAST_TABLE}}

名义FIFO−Tour的每主要条件净增确认为{{SUPPLEMENT_FIFO_GAIN}}段；CVAE-FIFO−名义FIFO为{{SUPPLEMENT_CVAE_GAIN}}段；CVAE-PPO−CVAE-FIFO为{{SUPPLEMENT_PPO_GAIN}}段。先平均模型种子、再等权四故障族，对12种子块进行10,000次自举；三个训练种子的离散程度另见附录，区间表示物理过程变化。

{{SUPPLEMENT_HEALTHY_TABLE}}

健康和虚假提示工况各12个条件，无评价异常时确认比例与异常条件等待记NA，保留额外访问、误确认及完成量代价。{{SUPPLEMENT_HEALTHY_FINDING}}

### 推理与派单计算成本

{{FIGURE:supplement-latency}}
{{SUPPLEMENT_LATENCY_TABLE}}

硬件为{{SUPPLEMENT_RUNTIME}}，PyTorch 2.6.0＋CUDA 12.4，PyTorch CPU线程数2。表为主要条件逐回合p50／p95的平均；神经估计包括数据转换、设备复制、前向、取回及CUDA同步，加载后5次合成公开输入预热单列。完整控制周期包括执行记账、下一观测估计及事件生命周期；估计阶段已包含其中，物理预生成、记录和I/O另计。

加权年龄由各任务完成时刻解析积分，采用每过程共同的静态资产权重及专业重访期限：

<div class="formula-scroll"><p class="formula" role="math">A<sub>j</sub>(t) = min[(t − L<sub>j</sub>)/D<sub>j</sub>,1]</p><p class="formula" role="math">J<sub>age</sub> = [1/(1800Σ<sub>j</sub>w<sub>j</sub>)] ∫<sub>0</sub><sup>1800</sup>Σ<sub>j</sub>w<sub>j</sub>A<sub>j</sub>(t)dt</p></div>

w由共同静态资产记录取得，各自检查轨迹决定年龄；包含初始和1800秒终点的完整间隔。新基准先在每条件归一，再依登记的种子块与故障权重汇总。该定义保留“重要任务长期未查代价更高”的思想，单位为无量纲。

<aside class="scope-note"><p><strong>本轮证据范围：</strong>新基准共{{SUPPLEMENT_ATTEMPTS}}次环境尝试，含兼容回放、采集、训练、开发诊断及1080次最终测试，另有18次纯物理规模运行。主推断以12个独立种子块、48个主要条件为单位。旧包中“未留帧／未计时”的字段继续按原件保留，见附录E；合成物理温度误差用于本基准内比较。</p></aside>

<!-- section:roadmap -->
## 5. 结论与下一阶段安排

当前成果有三层：**供电—液冷—自控的耦合模型、同权限的专业巡检闭环、具备真实模型训练和独立测试的交叉基准**。{{SUPPLEMENT_CONCLUSION}}

|工作包|具体操作|交付与判断|
|---|---|---|
|工程与标准映射|取得两项正式条款，逐项对应供回液、压差、流量、露点与保护需求；区分已有温度反馈和新增测控状态|条款／测量／方程／动作／测试矩阵；标准参数与研究参数分别可追溯|
|电气视觉闭环|关联RGB/IR参考、资产标识与任务时间；热点候选由专业复核，℃输入由合格测量提供；接触热点、偏差与工况A分组登记|视觉线索对有效电气确认的独立贡献表；保留输入、标定与时间对应记录|
|同任务算法比较：已完成本轮|CVAE-U-Net／名义估计与FIFO、Greedy、PPO交叉，保留共同预测—真值帧和逐步计时|1080个留出测试回合、12个独立种子块；训练差异、配对区间、四专业确认、误差与代价见第4节|
|规模扩展：已完成物理检查|128／512／1024柜物理运行和静态巡回核查；下一步解除主算法固定项并重训|18次物理结果和构造巡回列于第1节；大规模学习调度为后续独立验证|

本次已经完成“输入与记录—共同基线—独立验证—物理规模检查”。模型<strong>自改进（RSI）</strong>继续按反馈相对无反馈的增量单独评价；本轮CVAE和DRL/PPO属于基准训练。九条线性门槛的负结果与本次交叉结果共同帮助导师选择下一项研究假设。

后续新假设继续在测试前冻结样本、权重、输入权限和执行预算。已有探索性收益参考为平均净增至少1段、95%自举区间下界>0、移动增加≤5%、完成量下降≤2%且检查约束零违规。它是研究决策参考；新基准的主要结论按预登记配对效应、误差和成本分别报告。

<!-- section:appendix -->
## 6. 技术附录

以下保留计算、执行和开发诊断细节，便于导师按需核查。正文主结论和横向比较已全部展开。

<!-- optional-case:start -->
### A. 名义估计与原风险分布

<div class="principle-box" id="principle-estimation">
<h3>温度预测与量测校正</h3>
<div class="formula-scroll"><p class="formula" role="math">T̂<sup>−</sup><sub>i,k+1</sub> = T̂<sub>i,k</sub> + (Δt/C)[P<sub>i</sub> − U<sub>i</sub>(T̂<sub>i,k</sub> − T<sub>s,p</sub>) − U<sub>a</sub>(T̂<sub>i,k</sub> − T<sub>a</sub>)]</p><p class="formula" role="math">U<sub>i</sub> = 12[max(q̂<sub>i</sub>,0)/6]<sup>0.8</sup>；收到新热测量y<sub>i</sub>时，T̂<sub>i</sub> ← y<sub>i</sub></p></div>
<p>Δt＝5秒，C＝800 kJ/K；P为公开送达IT功率，T<sub>s,p</sub>为组供液温度，T<sub>a</sub>＝28°C，U<sub>a</sub>＝0.12 kW/K。每柜q̂以kg/s计，U以kW/K计。各柜从50°C初始化；流量取最近量测，尚无量测的组按泵指令和额定流量估计，平均分给8柜。</p>
</div>

<div class="principle-box" id="principle-risk"><h3>原热风险评分保持不变</h3><div class="formula-scroll"><p class="formula" role="math">r<sub>i</sub> = min{4, max(T̂<sub>i</sub> − 65,0)/20 + 0.25[1 − P<sub>del,i</sub>/max(P<sub>req,i</sub>,10<sup>−12</sup>)]}</p></div><p>第一项为估计温度越界，第二项为功率需求缺口。下图展示这一本来就稀疏的报警严重度分布；正文连续温度图保留全部状态梯度。</p></div>

{{FIGURE:public-risk}}
{{HOTSPOT_TABLE}}

### B. 专业任务、FIFO与返回核算

{{TASK_TABLE}}
{{FIGURE:fifo-cycle}}

<div class="principle-box" id="principle-return"><h3>完整返回核算</h3><div class="formula-scroll"><p class="formula" role="math">t + τ(p,x) + τ(x,r) ≤ L<sub>r</sub> + D<sub>r</sub>；τ(a,b) = 5⌈[d(a,b)/v + s<sub>b</sub>]/5⌉</p><p class="formula" role="math">对完整循环：F<sub>j</sub> ≤ L′<sub>j</sub> + D<sub>j</sub>；最小余量≥0</p></div><p>此简式取额外加查x与原任务r不同。τ包括目的任务服务，v＝1 m/s；首次未检的L按0起算，L′随预计访问更新。程序核查候选自身、完整循环及重复周期；每次实际完成后重新选择。</p></div>

{{QUEUE_TABLE}}
{{FIGURE:fifo-actions}}
{{RETURN_TABLE}}

原0号任务245秒完成，截止545秒；实际540秒完成，间隔295秒。10号450秒早于8号455秒入队，因此即使风险分较低也先处理。当前日志保留了0.0081／0.0656总分，温度项与功率项将随新记录共同保存。额外加查保留原例行指针，合格测量完成后结单；请求待派有效期120秒，分数暂时回落时保留至测量或到期。

### C. 故障配置与开发诊断

{{FAULT_TABLE}}

异常段要求连续至少3个5秒格达到对应阈值：温度>65°C、接点温度>60°C、组流量<33.6 kg/s、组平均传感误差绝对值>1°C。该12过程分别形成77／0／12／0段。有效确认依照前一5秒采样格的正标签及告警测量核对，保留原结果的端点语义。

{{FIGURE:paired-net}}

九规则先由FIFO选定合法事件，再在事件与例行头之间决定响应／暂缓。R＝风险÷4，A＝等待秒数÷120，E＝两候选预计完成时差÷300，S＝两者完整循环最小余量差÷600；得分z≥0响应，否则执行例行头。

{{FIGURE:registered-rules}}

规则01的4R−1在229次二选一中全部为负，最高原风险0.7604，额外访问0，12条完整动作与Tour相同。规则06要求至少等待15秒，新增2段、丢失12段；这12段内均无完成量测，区间后首次量测正常。

{{FIGURE:rule-diagnosis}}

该例两条轨迹260秒首次分叉。FIFO在300秒例行派4、320秒告警，赶上310—335秒的异常；等待规则315秒先查12、340秒再查4、365秒正常。335秒是未选候选的预计完成端点，图中只展示已执行轨迹。

{{FIGURE:execution-chain}}
{{PAIR:task-17,task-21}}

17／21是另一组Tour—FIFO完整轨迹：17号665秒例行派出、685秒见风险、690秒确认；21号650秒见风险、705秒额外派出、725秒测量时已过710秒结束。两类案例分别支持机制时序与响应门槛诊断。

### D. 原论文内部比较

{{FIGURE:original-paper-scores}}

原文在水域任务内比较DRL、Greedy、VRP及VAE/Myopic估计组合，测试100个未参与训练的场景。图取表8／9的终值均值与95%区间；“约快30%”描述曲线更早降低。原文Average的归一分母随复现对齐；本任务主表另定义并补算资产加权年龄。

### E. 历史封存包的横向表

{{COMPARISON_TABLE}}

历史主比较采用同12个预登记过程；两条线性暂缓规则为九候选中并列60段的开发对照。原包没有保存统一预测—真值帧或逐步计时，因此“未留帧／未计时”继续保留。历史VAE两行表示当时包内未运行，新增适配与独立结果见第4节。

在该历史包中，Tour整体加权年龄0.310901，FIFO为0.313052；FIFO确认70/89，移动平均+0.50%、完成量下降约0.33%。这些数值与本轮四故障基准各有自己的样本分母。

### F. 新基准的逐故障族结果

{{SUPPLEMENT_FAMILY_TABLE}}

每故障族12个条件，学习方法先平均三个训练种子；表为逐条件均值。主要统计采用四故障族等权，无异常的健康与虚假提示条件另列于正文。

### G. 训练种子与物理种子块变化

{{SUPPLEMENT_SEED_TABLE}}
{{FIGURE:supplement-seed-blocks}}
{{SUPPLEMENT_POLICY_TRAINING_TABLE}}

种子271／811／1931列为每主要条件平均确认段，SD是三个训练种子间的样本标准差；误差SD采用闭环加权RMSE。图中每个柱对应独立物理种子块的配对差，四故障条件等权。

PPO的选择数按执行者实际可选集合计；只有一个合法候选时，策略没有排序自由。训练耗时为完整回合执行、评分、留存和四次更新的累计墙钟时间，加载与预热另计。这一比例帮助解释当前返回保护与任务设定给学习留下多大的决策空间。

<!-- optional-case:end -->

<!-- section:sources -->
## 来源与继续查阅

- [工程控制、规模与官方标准核查](research/report-engineering-alignment-20261103.md)。
- [RGB／IR视觉成果与接口核查](research/report-pid-interface-20261103.md)。
- [本任务横向指标、公式与只读复算](research/report-comparison-metrics-20261103.md)。
- [独立补充基准：完整方法](supplement-study-methods.md)、[新协议、模型参数及结果原件索引](../evidence/supplement-study/README.md)。
- [补充研究设计依据](research/supplement-study-design-20261103.md)、[评价与缺失指标核查](research/supplement-metrics-audit-20261103.md)。
- [主机制验证与完整原件](../evidence/event-validation/final/README.md)、[九规则开发记录](../evidence/response-defer/README.md)。
- [名义估计与故障原件核查](research/report-method-formulas-20261103.md)、[规则动作诊断](research/report-rule-diagnosis-20261103.md)。
- [原论文指标核查](research/original-paper-metrics-20261103.md)、[模型方程与参数](model-appendix.html)、[机制讨论稿](manuscript_zh.html)。

正文、图像、公式与表格全部内嵌，可单文件离线阅读。本次新增独立数据生成、九个模型训练、最终测试和物理规模检查；旧封存记录与新证据分别保留。环境尝试、连续观测帧、模型种子及独立物理种子块采用各自分母。
