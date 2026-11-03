> 正文审阅版：正文、公式和数值表与单文件HTML同源；图版保留SVG链接，便于文本工具读取。

# 大型液冷算力设施的多系统巡检研究

导师自阅报告 · 三系统模型、学习估计与四专业独立基准 · 2026-11-03

<aside class="project-summary" aria-label="项目主线摘要"><strong>项目主线与现有成果</strong><p>本项目建立配电、双回路液冷与局部控制的耦合过程，以公开遥测、学习估计和专业巡检形成闭环。本次补充3个CVAE-U-Net、6个PPO的真实训练，在12个独立种子块、四故障和两检查条件上完成1080个最终测试回合。同一观测流中，非刚量测加权RMSE由0.443降至0.172°C；专业确认以名义FIFO的155/210段最高。CVAE主要改善连续温度态势，异常确认还由局部越阈值、队列与合法访问时机共同决定。此前事件包的28/89→70/89与九规则负结果作为历史基准保留。</p></aside>

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

<a id="model"></a>
## 1. 三系统模型、视觉感知与大型设施参照

### 配电与双回路液冷怎样连起来

**供电既决定计算发热，也影响冷却设备的排热能力。** 模型按10 kV入口、380 V交流配电、UPS／整流及54 V直流机柜组织依赖链；辅助馈电可用性进入二次泵有效速度，泵送流量和CDU换热共同影响设备温度。

**CDU**是冷却液分配与换热单元。一次回路连接设施冷源，二次回路连接机柜冷板，两侧在CDU交换热量。El Capitan／Cray EX的官方资料提供了双回路、冷板和测控层次的工程参照。[LLNL](https://www.llnl.gov/article/54496/meet-machines-matter-how-el-capitan-keeps-its-cool)、[HPE](https://www.hpe.com/us/en/collaterals/collateral.a00094635enw.html)。



[图：本项目集中参数模型的供电、双回路液冷与局部控制计算关系。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/model.svg)



|计算对象|当前关系及其用途|
|---|---|
|机柜热状态|热容×温升速率＝送达IT功率−冷板换热−环境散热|
|CDU与一次回路|有效度、两侧热容流率和供回液温差决定换热；塔排热影响共享一次供液|
|泵送与供电|有效泵速包含“指令×√辅助供电可用性”，水力代理据此求流量与压差|
|电气接点|接触损耗驱动接点温升；合格电气检查更新该组接点温度观测|

### RGB→IR：已有视觉成果如何接到配电巡检

这里的<strong>PID</strong>指Physics-Informed Diffusion图像生成工作；RGB表示可见光图像，IR表示红外。已有PID及视觉项目分支B-PID保留了可见光到伪彩IR显示的实验材料。下面展示一个户外电气设备的实际样例，作为视觉支路的已有成果。[原PID方法](https://github.com/fangyuanmao/PID)。



[图：PID项目既有户外电气样例，同图精修、显示域；三张原图逐字节保留，数值计量按独立测温通道处理。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/pid-visual-sample.svg)



户外绝缘子、铁塔与导线样例展示前期的电气显示图重建路径；机房中的对应应用对象为10 kV／380 V开关柜、母排及54 V机柜交直流接点。本课题拟复用跨模态图像参考接口，经机房图像适配与校准测温接入后，用于热点复核和观测更新。

**当前Renly已有参考元数据入口，以及“合格接点测温→接触温度状态更新”通道**；RGB采集、生成推理、热点选点与调度之间的桥接按下图列为待接步骤。



[图：已实现的参考元数据入口与合成接点测量分层表示；虚线标出RGB推理、选点及现场仪器桥接。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/visual-interface.svg)



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



[图：每规模三种子×健康／耦合两工况的纯物理过程实测；带tracemalloc开销，范围为六次实测最小—最大，未作大规模学习调度。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-scale.svg)


<div class="table-wrap"><table data-table="supplement-scale" class="supplement-table"><thead><tr><th>机柜数</th><th>热状态／指令状态</th><th>执行者／专业任务</th><th>物理耗时中位数 / 秒</th><th>Python峰值 / MiB</th><th>静态检查</th></tr></thead><tbody><tr><td>128</td><td>161／145</td><td>18／176</td><td>0.517</td><td>0.50</td><td>构造闭合巡回满足</td></tr><tr><td>512</td><td>641／577</td><td>72／704</td><td>0.483</td><td>1.70</td><td>构造闭合巡回满足</td></tr><tr><td>1024</td><td>1281／1153</td><td>144／1408</td><td>0.500</td><td>3.32</td><td>构造闭合巡回满足</td></tr></tbody></table></div>
<div class="table-wrap"><table data-table="supplement-scale-cycles" class="supplement-table"><thead><tr><th>机柜数</th><th>热检查：人数；周期／期限</th><th>电气：人数；周期／期限</th><th>制冷：人数；周期／期限</th><th>自控：人数；周期／期限</th></tr></thead><tbody><tr><td>128</td><td>12人；240/300秒</td><td>2人；310/600秒</td><td>2人；310/600秒</td><td>2人；270/600秒</td></tr><tr><td>512</td><td>48人；240/300秒</td><td>8人；385/600秒</td><td>8人；385/600秒</td><td>8人；345/600秒</td></tr><tr><td>1024</td><td>96人；240/300秒</td><td>16人；465/600秒</td><td>16人；465/600秒</td><td>16人；425/600秒</td></tr></tbody></table></div>

每规模为三个独立种子×健康／耦合两条件，360个5秒物理步。耗时含Python内存追踪开销，内存列为追踪峰值；闭合周期按已构造的本人巡回与专业期限检查。三规模的构造闭合巡回均满足各专业期限。360步物理耗时中位数约0.48—0.52秒，未随柜数呈单调上升；Python追踪峰值由0.50增至3.32 MiB，范围为该物理段及温度序列的留存。

18次物理运行记录的最大能量平衡残差为7.97e-08 kJ，最大电功率平衡残差为8.73e-11 kW，用于核对本次数值积分的守恒一致性。

<aside class="scope-note"><p><strong>工程范围：</strong>模型为集中参数研究设定，主算法评价为128柜。512／1024柜结果覆盖物理过程与静态构造巡回，大规模学习调度、现场校准和E/G算力映射继续作为独立工程任务。正式国标的访问与控制覆盖见工程核查。</p></aside>

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

<a id="fifo"></a>
## 3. 巡检机制与历史闭环基准

第一阶段采用<strong>名义估计＋返回保护FIFO</strong>作为机制基准。FIFO（First In, First Out，先入先出）在执行者空闲时，从本人合法风险请求中选择最早出现的一项；资格、预约、预算和返回时间先行核查，原例行循环持续保留。

每回合为1800秒、18名执行者，全体额外访问上限12次，请求待派有效期120秒。



[图：根据本项目已实现接口重绘总体架构；上方在线决策只用公开信息，下方真值与日志用于事后评分。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/inspection-architecture.svg)



临时加查前，程序计算“现在出发、完成加查、返回并完成原任务”是否赶上截止，并逐项核对完整所属循环：

<div class="formula-scroll"><p class="formula" role="math">t + τ(p,x) + τ(x,r) ≤ L<sub>r</sub> + D<sub>r</sub>；对完整循环每项F<sub>j</sub> ≤ L′<sub>j</sub> + D<sub>j</sub></p></div>

τ包含移动和目的任务服务，L为上次完成时刻、D为最大重访间隔；额外加查x与原定下一项r分别计账。完整取整、初始时刻和返回证书例子见附录B。

### 工况A：供电可用性下降引发热—冷传播

本批12个配对过程统一注入辅助馈电故障与CDU换热衰减，持续180秒；通过不同种子、目标设备组和开始时刻比较。辅助供电乘子为0.05、CDU换热乘子为0.20，形成77段热异常和12段制冷异常。电气接触温升及传感偏差仍按各自专业检查，但这批故障的评价段集中在热和制冷。

本次独立补充基准另行覆盖接触热点、传感偏差与二次泵故障，见第4节；RGB参考融合属于视觉支路后续验证。历史工况A的12行配置、四专业阈值和原件保持可回查。



[图：当前机房任务：12个主过程，共89段异常；三列为各策略的有效确认量。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/confirmations.svg)



FIFO相对固定巡回新增45段、丢失3段，净增42段，平均每过程净增3.50段；探索性95%自举区间为[2.42,4.50]。硬重访、资格与预约违规均为0。此结果建立了<strong>耦合过程—部分观测—风险请求—受保护执行—专业确认</strong>的闭环基准。



[图：本项目12个主过程的FIFO相对Tour比较；区间、代价与探索性门槛均来自封存记录。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/outcome-costs.svg)



同权限的九个预登记响应／暂缓规则确认28—60段，最好两条均为60，低于FIFO的70。记录显示，高风险门槛压掉了加查，固定等待门槛也会改变短异常窗口内的检查机会。正文将它们作为开发对照；得分式、具体得失及原轨迹图保留在附录C。

<aside class="scope-note"><p><strong>验证单位：</strong>12是配对物理过程数，89是其中的连续异常段数。专业确认沿用原包5秒采样端点评价；一次测量需告警且落在原标签的有效采样端点。九规则来自同12个已见过程的开发比较，模型调用与训练均为0。</p></aside>

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



[图：估计器与调度器的共同候选、约束和执行接口。PPO使用公开奖励训练，原始异常标签留给离线评价。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-crossed-design.svg)



PPO在与FIFO、Greedy相同的合法候选集合中决策，使用21维公开候选特征和32×32共享actor。每估计条件训练三个种子，各120个完整回合，固定最终策略；配对种子采用相同初始参数与训练案例次序。训练采用公开奖励的[PPO裁剪目标](https://arxiv.org/abs/1707.06347)，事后异常标签只参与评价。

### 真实训练记录与模型选择



[图：三个训练种子的真实30轮开发曲线，空心点为各自开发集最优checkpoint；测试集不参与选择。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-estimator-training.svg)




[图：六个PPO的公开奖励训练曲线；细线表示训练种子，粗线为种子均值，采用10回合滑动窗口。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-ppo-training.svg)


<div class="table-wrap"><table data-table="supplement-training" class="supplement-table"><thead><tr><th>训练种子</th><th>实际epoch</th><th>训练快照</th><th>开发快照</th><th>选中epoch</th><th>开发加权RMSE / °C</th><th>训练分钟</th></tr></thead><tbody><tr><td>271</td><td>30</td><td>34560</td><td>8640</td><td>29</td><td>0.164</td><td>3.05</td></tr><tr><td>811</td><td>30</td><td>34560</td><td>8640</td><td>27</td><td>0.161</td><td>3.12</td></tr><tr><td>1931</td><td>30</td><td>34560</td><td>8640</td><td>25</td><td>0.165</td><td>2.97</td></tr></tbody></table></div>

三个CVAE均训练30轮，按各自开发集加权MSE选checkpoint；六个PPO共720个训练回合，均使用固定第120回合参数。测试开始前锁定九个checkpoint的SHA，完整曲线与实际参数归档可回查。奖励曲线说明训练过程，留出测试中的确认、误差与成本共同评价模型价值。

### 同一公开观测流上的估计误差



[图：所有估计器接收同一份已保存Tour公开观测流，使用相同刚量测校正；误差线为95%物理种子块区间。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-estimation.svg)


<div class="table-wrap"><table data-table="supplement-fixed-stream" class="supplement-table"><thead><tr><th>估计器</th><th>RMSE / °C</th><th>加权RMSE / °C</th><th>R²</th><th>非刚量测加权RMSE / °C</th></tr></thead><tbody><tr><td>名义热平衡</td><td>0.528 [0.416, 0.646]</td><td>0.535 [0.419, 0.659]</td><td>0.9124 [0.8801, 0.9413]</td><td>0.443 [0.306, 0.589]</td></tr><tr><td>残差CVAE-U-Net</td><td>0.324 [0.303, 0.347]</td><td>0.328 [0.307, 0.350]</td><td>0.9602 [0.9580, 0.9621]</td><td>0.172 [0.145, 0.201]</td></tr></tbody></table></div>

残差CVAE-U-Net在相同公开输入上降低了温度误差：全部端点加权RMSE由0.535降至0.328°C，逐回合R²均值由0.9124提高到0.9602。非刚量测加权RMSE均值降低61.2%。这支持学习估计器改善状态表示；专业确认仍需通过后面的任务结果判断。

表中为主要条件的逐回合误差均值，括号为95%物理种子块自举区间。**非刚量测加权RMSE**排除当前端点直接回填的温度量测，是预登记的估计主要比较；CVAE−名义差为-0.271 [-0.398, -0.157]°C。R²采用逐回合SSE／SST计算后汇总，常量目标记NA。

### 七方法闭环总表与四专业结果

<div class="table-wrap"><table data-table="supplement-errors" class="supplement-table"><thead><tr><th>方法</th><th>RMSE / °C↓</th><th>加权RMSE / °C↓</th><th>R²↑</th><th>非刚量测加权RMSE / °C↓</th><th>模型／规则重复</th></tr></thead><tbody><tr data-supplement-method="nominal_tour"><td>名义＋Tour</td><td>0.528</td><td>0.535</td><td>0.9124</td><td>0.443</td><td>1个确定性规则</td></tr><tr data-supplement-method="nominal_fifo"><td>名义＋FIFO</td><td>0.532</td><td>0.535</td><td>0.9113</td><td>0.443</td><td>1个确定性规则</td></tr><tr data-supplement-method="nominal_greedy"><td>名义＋Greedy</td><td>0.533</td><td>0.537</td><td>0.9105</td><td>0.446</td><td>1个确定性规则</td></tr><tr data-supplement-method="nominal_ppo"><td>名义＋PPO</td><td>0.531</td><td>0.537</td><td>0.9112</td><td>0.445</td><td>3个独立训练种子</td></tr><tr data-supplement-method="cvae_fifo"><td>CVAE＋FIFO</td><td>0.323</td><td>0.327</td><td>0.9603</td><td>0.170</td><td>3个独立训练种子</td></tr><tr data-supplement-method="cvae_greedy"><td>CVAE＋Greedy</td><td>0.323</td><td>0.327</td><td>0.9602</td><td>0.171</td><td>3个独立训练种子</td></tr><tr data-supplement-method="cvae_ppo"><td>CVAE＋PPO</td><td>0.323</td><td>0.327</td><td>0.9602</td><td>0.171</td><td>3个独立训练种子</td></tr></tbody></table></div>
<div class="table-wrap"><table data-table="supplement-tasks" class="supplement-table"><thead><tr><th>方法</th><th>确认／唯一异常段</th><th>确认比例</th><th>每条件确认 [95%CI]</th><th>截尾等待 / 秒↓</th><th>加权年龄↓</th><th>移动相对Tour</th><th>完成量相对Tour</th><th>约束违规</th></tr></thead><tbody><tr data-supplement-method="nominal_tour"><td>名义＋Tour</td><td>94/210</td><td>44.8%</td><td>1.96 [1.31, 2.65]</td><td>106.75</td><td>0.310122</td><td>+0.00%</td><td>+0.00%</td><td>0</td></tr><tr data-supplement-method="nominal_fifo"><td>名义＋FIFO</td><td>155/210</td><td>73.8%</td><td>3.23 [2.83, 3.65]</td><td>94.24</td><td>0.311298</td><td>+0.34%</td><td>-0.15%</td><td>0</td></tr><tr data-supplement-method="nominal_greedy"><td>名义＋Greedy</td><td>154/210</td><td>73.3%</td><td>3.21 [2.81, 3.60]</td><td>94.36</td><td>0.311270</td><td>+0.34%</td><td>-0.15%</td><td>0</td></tr><tr data-supplement-method="nominal_ppo"><td>名义＋PPO</td><td>129.33/210</td><td>61.6%</td><td>2.69 [2.23, 3.17]</td><td>100.42</td><td>0.310877</td><td>+0.22%</td><td>-0.10%</td><td>0</td></tr><tr data-supplement-method="cvae_fifo"><td>CVAE＋FIFO</td><td>153/210</td><td>72.9%</td><td>3.19 [2.78, 3.61]</td><td>94.55</td><td>0.311256</td><td>+0.33%</td><td>-0.14%</td><td>0</td></tr><tr data-supplement-method="cvae_greedy"><td>CVAE＋Greedy</td><td>152/210</td><td>72.4%</td><td>3.17 [2.76, 3.58]</td><td>94.64</td><td>0.311217</td><td>+0.32%</td><td>-0.14%</td><td>0</td></tr><tr data-supplement-method="cvae_ppo"><td>CVAE＋PPO</td><td>153.67/210</td><td>73.2%</td><td>3.20 [2.78, 3.62]</td><td>94.65</td><td>0.311266</td><td>+0.33%</td><td>-0.14%</td><td>0</td></tr></tbody></table></div>


[图：48个主要条件，先平均三个模型种子、再等权四故障族；误差线为12个物理种子块的95%自举区间。等待对有异常的条件计算。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-methods.svg)




[图：四专业异常段的描述性确认比例，数字为确认数／专业异常总数；小数来自三个模型种子的平均。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-professions.svg)



48个主要条件共有210段唯一评价异常。各学习方法先平均三个模型种子，因此确认总数允许出现小数；这表示训练重复的平均效果。表中误差使用各自闭环形成的量测流，固定观测流的独立估计比较则使用上表。

名义FIFO相对Tour新增61段有效确认，截尾等待从106.75缩短至94.24秒，移动增加0.34%、完成量下降0.15%；整体加权年龄从0.310122升至0.311298。各方法资格、预约、预算和初终点重访审计均为0违规。

三个模型种子平均后，CVAE-FIFO、CVAE-Greedy和CVAE-PPO分别确认153、152和153.67段，均未超过名义FIFO的155段。方法差异集中在热检查与制冷；电气均为12/12，自控均为8/12；在当前观测与专业完成时机设置下，这两类结果在方法间一致。

### 为什么估计更准，确认数仍以名义FIFO为高？

CVAE-U-Net的已验证收益是**全局温度态势重构精度**；有效确认还取决于局部越阈值提示、FIFO队列和受保护访问的完成时机。连续误差降低，并不保证短异常窗口内的确认数同步增加。

事后逐事件核对48条件×3个模型种子的144组配对，CVAE-FIFO相对名义FIFO新增2段、丢失8段，按训练种子平均后净少2段。一个具体例子是制冷故障案例04：CVAE将45号柜的提示从860秒提前到840秒，但同一队列中的41号柜更早在835秒入队，860秒时先被选中。于是CVAE在880秒确认了41号，45号却到900秒才完成，错过850—890秒评价段；名义FIFO则在875秒确认45号、895秒才检查41号。这里发生的是确认机会的交换。

这些轨迹显示，局部估计偏差与队列先后会改变确认机会；现有日志不支持把全部差异统一归因于“名义温度普遍偏高”，也没有测得CVAE组更低的专业误确认率。逐段得失与时间核对见[附录H](#gap-diagnosis)。

### 配对增量、训练差异与正常工况



[图：预登记的配对比较及95%物理种子块自举区间。确认、等待、年龄与误差分别解释；区间不包含完整训练不确定性。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-contrasts.svg)


<div class="table-wrap"><table data-table="supplement-contrasts" class="supplement-table"><thead><tr><th>预登记比较</th><th>每条件确认差↑</th><th>截尾等待差 / 秒↓</th><th>归一年龄差↓</th><th>闭环加权RMSE差 / °C↓</th></tr></thead><tbody><tr><td>名义＋FIFO − 名义＋Tour</td><td>+1.27 [+0.62, +1.88]</td><td>-12.51 [-16.31, -8.75]</td><td>+0.001176 [+0.001052, +0.001292]</td><td>+0.001 [-0.053, +0.052]</td></tr><tr><td>CVAE＋FIFO − 名义＋FIFO</td><td>-0.04 [-0.09, +0.00]</td><td>+0.31 [+0.02, +0.70]</td><td>-0.000042 [-0.000072, -0.000015]</td><td>-0.208 [-0.311, -0.111]</td></tr><tr><td>CVAE＋Greedy − 名义＋Greedy</td><td>-0.04 [-0.09, +0.00]</td><td>+0.28 [+0.00, +0.67]</td><td>-0.000053 [-0.000093, -0.000021]</td><td>-0.210 [-0.314, -0.112]</td></tr><tr><td>名义＋PPO − 名义＋FIFO</td><td>-0.53 [-0.79, -0.26]</td><td>+6.18 [+4.23, +8.19]</td><td>-0.000421 [-0.000475, -0.000362]</td><td>+0.002 [-0.015, +0.018]</td></tr><tr><td>CVAE＋PPO − CVAE＋FIFO</td><td>+0.01 [-0.01, +0.04]</td><td>+0.10 [-0.15, +0.39]</td><td>+0.000010 [-0.000005, +0.000028]</td><td>+0.000 [-0.000, +0.000]</td></tr><tr><td>CVAE＋PPO − 名义＋PPO</td><td>+0.51 [+0.22, +0.78]</td><td>-5.77 [-7.59, -4.01]</td><td>+0.000389 [+0.000320, +0.000454]</td><td>-0.210 [-0.310, -0.115]</td></tr></tbody></table></div>

名义FIFO−Tour的每主要条件净增确认为+1.27 [+0.62, +1.88]段；CVAE-FIFO−名义FIFO为-0.04 [-0.09, +0.00]段；CVAE-PPO−CVAE-FIFO为+0.01 [-0.01, +0.04]段。先平均模型种子、再等权四故障族，对12种子块进行10,000次自举；三个训练种子的离散程度另见附录，区间表示物理过程变化。

<div class="table-wrap"><table data-table="supplement-healthy" class="supplement-table"><thead><tr><th>方法</th><th>健康额外访问</th><th>虚假提示额外访问</th><th>健康误确认</th><th>虚假提示误确认</th><th>虚假提示完成量相对Tour</th><th>两组确认比例／等待</th></tr></thead><tbody><tr><td>名义＋Tour</td><td>0.00</td><td>0.00</td><td>0.00</td><td>0.00</td><td>+0.00%</td><td>NA / NA</td></tr><tr><td>名义＋FIFO</td><td>0.00</td><td>0.75</td><td>0.00</td><td>0.00</td><td>-0.04%</td><td>NA / NA</td></tr><tr><td>名义＋Greedy</td><td>0.00</td><td>0.75</td><td>0.00</td><td>0.00</td><td>-0.04%</td><td>NA / NA</td></tr><tr><td>名义＋PPO</td><td>0.00</td><td>0.42</td><td>0.00</td><td>0.00</td><td>-0.02%</td><td>NA / NA</td></tr><tr><td>CVAE＋FIFO</td><td>0.00</td><td>0.75</td><td>0.00</td><td>0.00</td><td>-0.04%</td><td>NA / NA</td></tr><tr><td>CVAE＋Greedy</td><td>0.00</td><td>0.75</td><td>0.00</td><td>0.00</td><td>-0.04%</td><td>NA / NA</td></tr><tr><td>CVAE＋PPO</td><td>0.00</td><td>0.75</td><td>0.00</td><td>0.00</td><td>-0.04%</td><td>NA / NA</td></tr></tbody></table></div>

健康和虚假提示工况各12个条件，无评价异常时确认比例与异常条件等待记NA，保留额外访问、误确认及完成量代价。所有方法在健康组均无额外访问和误确认。虚假提示下，FIFO、Greedy及CVAE-PPO平均各增加0.75次访问／条件，名义PPO为0.42次；这些跟进没有造成错误的专业确认。

### 推理与派单计算成本



[图：主要故障条件的逐回合p95均值，实测包含转换和CUDA同步。估计阶段已包含于完整控制周期，不能重复相加。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-latency.svg)


<div class="table-wrap"><table data-table="supplement-latency" class="supplement-table"><thead><tr><th>方法</th><th>估计p50 / ms</th><th>估计p95 / ms</th><th>派单p50 / ms</th><th>派单p95 / ms</th><th>完整周期p95 / ms</th></tr></thead><tbody><tr><td>名义＋Tour</td><td>0.17</td><td>0.23</td><td>0.45</td><td>0.90</td><td>1.53</td></tr><tr><td>名义＋FIFO</td><td>0.17</td><td>0.22</td><td>0.44</td><td>0.86</td><td>1.47</td></tr><tr><td>名义＋Greedy</td><td>0.17</td><td>0.22</td><td>0.44</td><td>0.87</td><td>1.48</td></tr><tr><td>名义＋PPO</td><td>0.18</td><td>0.24</td><td>1.28</td><td>2.95</td><td>3.59</td></tr><tr><td>CVAE＋FIFO</td><td>3.69</td><td>5.44</td><td>0.47</td><td>0.93</td><td>6.59</td></tr><tr><td>CVAE＋Greedy</td><td>3.53</td><td>5.07</td><td>0.48</td><td>0.95</td><td>6.27</td></tr><tr><td>CVAE＋PPO</td><td>3.63</td><td>5.34</td><td>1.31</td><td>3.00</td><td>8.10</td></tr></tbody></table></div>

硬件为NVIDIA GeForce RTX 4060 Laptop GPU，PyTorch 2.6.0＋CUDA 12.4，PyTorch CPU线程数2。表为主要条件逐回合p50／p95的平均；神经估计包括数据转换、设备复制、前向、取回及CUDA同步，加载后5次合成公开输入预热单列。完整控制周期包括执行记账、下一观测估计及事件生命周期；估计阶段已包含其中，物理预生成、记录和I/O另计。

加权年龄由各任务完成时刻解析积分，采用每过程共同的静态资产权重及专业重访期限：

<div class="formula-scroll"><p class="formula" role="math">A<sub>j</sub>(t) = min[(t − L<sub>j</sub>)/D<sub>j</sub>,1]</p><p class="formula" role="math">J<sub>age</sub> = [1/(1800Σ<sub>j</sub>w<sub>j</sub>)] ∫<sub>0</sub><sup>1800</sup>Σ<sub>j</sub>w<sub>j</sub>A<sub>j</sub>(t)dt</p></div>

w由共同静态资产记录取得，各自检查轨迹决定年龄；包含初始和1800秒终点的完整间隔。新基准先在每条件归一，再依登记的种子块与故障权重汇总。该定义保留“重要任务长期未查代价更高”的思想，单位为无量纲。

<aside class="scope-note"><p><strong>本轮证据范围：</strong>新基准共2204次环境尝试，含兼容回放、采集、训练、开发诊断及1080次最终测试，另有18次纯物理规模运行。主推断以12个独立种子块、48个主要条件为单位。旧包中“未留帧／未计时”的字段继续按原件保留，见附录E；合成物理温度误差用于本基准内比较。</p></aside>

<a id="roadmap"></a>
## 5. 结论与下一阶段安排

当前成果有三层：**供电—液冷—自控的耦合模型、同权限的专业巡检闭环、具备真实模型训练和独立测试的交叉基准**。新数据把估计收益与任务收益分开：学习估计降低了温度误差，名义FIFO在七方法中取得最高的训练种子平均确认量。CVAE-PPO较名义PPO平均每主要条件增加0.507段，但相对同估计器下的FIFO仅增加0.014段，95%区间跨零。在每策略120回合预算下，尚未形成超越FIFO的学习调度增量。

建议保留名义FIFO作为任务基准，保留CVAE作为状态估计支路。训练记录中仅约0.26%—0.28%的实际选择包含多个合法候选；下一阶段可先围绕候选稀疏与未确认段建立新假设，再决定是否增加学习复杂度。

|工作包|具体操作|交付与判断|
|---|---|---|
|工程与标准映射|取得两项正式条款，逐项对应供回液、压差、流量、露点与保护需求；区分已有温度反馈和新增测控状态|条款／测量／方程／动作／测试矩阵；标准参数与研究参数分别可追溯|
|电气视觉闭环|关联RGB/IR参考、资产标识与任务时间；热点候选由专业复核，℃输入由合格测量提供；接触热点、偏差与工况A分组登记|视觉线索对有效电气确认的独立贡献表；保留输入、标定与时间对应记录|
|同任务算法比较：已完成本轮|CVAE-U-Net／名义估计与FIFO、Greedy、PPO交叉，保留共同预测—真值帧和逐步计时|1080个留出测试回合、12个独立种子块；训练差异、配对区间、四专业确认、误差与代价见第4节|
|规模扩展：已完成物理检查|128／512／1024柜物理运行和静态巡回核查；下一步解除主算法固定项并重训|18次物理结果和构造巡回列于第1节；大规模学习调度为后续独立验证|

本次已经完成“输入与记录—共同基线—独立验证—物理规模检查”。模型<strong>自改进（RSI）</strong>继续按反馈相对无反馈的增量单独评价；本轮CVAE和DRL/PPO属于基准训练。九条线性门槛的负结果与本次交叉结果共同帮助导师选择下一项研究假设。

后续新假设继续在测试前冻结样本、权重、输入权限和执行预算。已有探索性收益参考为平均净增至少1段、95%自举区间下界>0、移动增加≤5%、完成量下降≤2%且检查约束零违规。它是研究决策参考；新基准的主要结论按预登记配对效应、误差和成本分别报告。

<a id="appendix"></a>
## 6. 技术附录

以下保留计算、执行和开发诊断细节，便于导师按需核查。正文主结论和横向比较已全部展开。


### A. 名义估计与原风险分布

<div class="principle-box" id="principle-estimation">
<h3>温度预测与量测校正</h3>
<div class="formula-scroll"><p class="formula" role="math">T̂<sup>−</sup><sub>i,k+1</sub> = T̂<sub>i,k</sub> + (Δt/C)[P<sub>i</sub> − U<sub>i</sub>(T̂<sub>i,k</sub> − T<sub>s,p</sub>) − U<sub>a</sub>(T̂<sub>i,k</sub> − T<sub>a</sub>)]</p><p class="formula" role="math">U<sub>i</sub> = 12[max(q̂<sub>i</sub>,0)/6]<sup>0.8</sup>；收到新热测量y<sub>i</sub>时，T̂<sub>i</sub> ← y<sub>i</sub></p></div>
<p>Δt＝5秒，C＝800 kJ/K；P为公开送达IT功率，T<sub>s,p</sub>为组供液温度，T<sub>a</sub>＝28°C，U<sub>a</sub>＝0.12 kW/K。每柜q̂以kg/s计，U以kW/K计。各柜从50°C初始化；流量取最近量测，尚无量测的组按泵指令和额定流量估计，平均分给8柜。</p>
</div>

<div class="principle-box" id="principle-risk"><h3>原热风险评分保持不变</h3><div class="formula-scroll"><p class="formula" role="math">r<sub>i</sub> = min{4, max(T̂<sub>i</sub> − 65,0)/20 + 0.25[1 − P<sub>del,i</sub>/max(P<sub>req,i</sub>,10<sup>−12</sup>)]}</p></div><p>第一项为估计温度越界，第二项为功率需求缺口。下图展示这一本来就稀疏的报警严重度分布；正文连续温度图保留全部状态梯度。</p></div>



[图：已有工程回看：固定巡回，500秒；风险分由公开观测和名义估计计算。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/public-risk.svg)


<div class="table-wrap"><table data-table="hotspot-values"><thead><tr><th>机柜</th><th>当时公开风险分</th><th>名义估计温度／°C</th><th>事后代表温度／°C</th><th>固定温度遥测点</th></tr></thead><tbody><tr><td>64</td><td>0.1296</td><td>67.35</td><td>67.63</td><td>是</td></tr><tr><td>67</td><td>0.2623</td><td>69.58</td><td>69.53</td><td>否</td></tr><tr><td>70</td><td>0.1323</td><td>67.36</td><td>67.31</td><td>否</td></tr></tbody></table></div>

### B. 专业任务、FIFO与返回核算

<div class="table-wrap"><table data-table="task-contract"><thead><tr><th>专业</th><th>完成检查后得到什么</th><th>人数</th><th>每次服务</th><th>最大重访间隔</th></tr></thead><tbody><tr><td>热检查</td><td>该机柜代表温度</td><td>12</td><td>10秒</td><td>300秒</td></tr><tr><td>电气检查</td><td>该组电气接触温度</td><td>2</td><td>20秒</td><td>600秒</td></tr><tr><td>制冷检查</td><td>该组冷却液流量</td><td>2</td><td>20秒</td><td>600秒</td></tr><tr><td>自控检查</td><td>传感读数误差（完成校验后）</td><td>2</td><td>15秒</td><td>600秒</td></tr></tbody></table></div>


[图：每名执行者空闲时从本人合法请求中选择；完成量测后进入下一轮。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/fifo-cycle.svg)



<div class="principle-box" id="principle-return"><h3>完整返回核算</h3><div class="formula-scroll"><p class="formula" role="math">t + τ(p,x) + τ(x,r) ≤ L<sub>r</sub> + D<sub>r</sub>；τ(a,b) = 5⌈[d(a,b)/v + s<sub>b</sub>]/5⌉</p><p class="formula" role="math">对完整循环：F<sub>j</sub> ≤ L′<sub>j</sub> + D<sub>j</sub>；最小余量≥0</p></div><p>此简式取额外加查x与原任务r不同。τ包括目的任务服务，v＝1 m/s；首次未检的L按0起算，L′随预计访问更新。程序核查候选自身、完整循环及重复周期；每次实际完成后重新选择。</p></div>

<div class="table-wrap"><table data-table="fifo-queue"><thead><tr><th>本人的待确认请求</th><th>首次提示时间</th><th>470秒时风险分</th><th>当下检查</th><th>本次选择</th></tr></thead><tbody><tr><td>机柜10热检查</td><td>450秒</td><td>0.0081</td><td>资格、可行性和预算均通过</td><td>先查</td></tr><tr><td>机柜8热检查</td><td>455秒</td><td>0.0656</td><td>资格、可行性和预算均通过</td><td>继续等待</td></tr></tbody></table></div>


[图：主验证第2个过程，一名热巡检员的实际记录；色块宽度表示移动与服务时间。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/fifo-actions.svg)


<div class="table-wrap"><table data-table="return-budget"><thead><tr><th>重新决策时刻</th><th>批准的加查</th><th>预计完成加查</th><th>随后按原循环返回0号</th><th>0号截止</th><th>完整循环最小余量</th></tr></thead><tbody><tr><td>470秒</td><td>10</td><td>500秒</td><td>525秒</td><td>545秒</td><td>20秒</td></tr><tr><td>500秒</td><td>8</td><td>515秒</td><td>540秒</td><td>545秒</td><td>5秒</td></tr></tbody></table></div>

原0号任务245秒完成，截止545秒；实际540秒完成，间隔295秒。10号450秒早于8号455秒入队，因此即使风险分较低也先处理。当前日志保留了0.0081／0.0656总分，温度项与功率项将随新记录共同保存。额外加查保留原例行指针，合格测量完成后结单；请求待派有效期120秒，分数暂时回落时保留至测量或到期。

### C. 故障配置与开发诊断

<div class="table-wrap"><table data-table="fault-cases"><thead><tr><th>过程</th><th>种子</th><th>目标柜号／设备组</th><th>故障开始→结束／秒</th><th>热／冷异常段</th></tr></thead><tbody><tr><td>01</td><td>101003</td><td>0号／第1组</td><td>150→330</td><td>8／1</td></tr><tr><td>02</td><td>101040</td><td>9号／第2组</td><td>335→515</td><td>6／1</td></tr><tr><td>03</td><td>101077</td><td>20号／第3组</td><td>520→700</td><td>6／1</td></tr><tr><td>04</td><td>101114</td><td>29号／第4组</td><td>705→885</td><td>7／1</td></tr><tr><td>05</td><td>101151</td><td>36号／第5组</td><td>150→330</td><td>7／1</td></tr><tr><td>06</td><td>101188</td><td>45号／第6组</td><td>335→515</td><td>7／1</td></tr><tr><td>07</td><td>101225</td><td>56号／第8组</td><td>520→700</td><td>6／1</td></tr><tr><td>08</td><td>101262</td><td>65号／第9组</td><td>705→885</td><td>6／1</td></tr><tr><td>09</td><td>101299</td><td>76号／第10组</td><td>150→330</td><td>7／1</td></tr><tr><td>10</td><td>101336</td><td>85号／第11组</td><td>335→515</td><td>7／1</td></tr><tr><td>11</td><td>101373</td><td>100号／第13组</td><td>520→700</td><td>4／1</td></tr><tr><td>12</td><td>101410</td><td>117号／第15组</td><td>705→885</td><td>6／1</td></tr></tbody></table></div>

异常段要求连续至少3个5秒格达到对应阈值：温度>65°C、接点温度>60°C、组流量<33.6 kg/s、组平均传感误差绝对值>1°C。该12过程分别形成77／0／12／0段。有效确认依照前一5秒采样格的正标签及告警测量核对，保留原结果的端点语义。



[图：过程01—12为预登记的12个配对过程；11个净增、1个持平。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/paired-net.svg)



九规则先由FIFO选定合法事件，再在事件与例行头之间决定响应／暂缓。R＝风险÷4，A＝等待秒数÷120，E＝两候选预计完成时差÷300，S＝两者完整循环最小余量差÷600；得分z≥0响应，否则执行例行头。



[图：本项目9个唯一规则的得分式；R、A、E、S分别对应正文中的归一风险、等待、额外耗时与余量差。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/registered-rules.svg)



规则01的4R−1在229次二选一中全部为负，最高原风险0.7604，额外访问0，12条完整动作与Tour相同。规则06要求至少等待15秒，新增2段、丢失12段；这12段内均无完成量测，区间后首次量测正常。



[图：主过程01的完整策略轨迹对照，机柜4；等待规则为图中06号，按记录重绘。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/rule-diagnosis.svg)



该例两条轨迹260秒首次分叉。FIFO在300秒例行派4、320秒告警，赶上310—335秒的异常；等待规则315秒先查12、340秒再查4、365秒正常。335秒是未选候选的预计完成端点，图中只展示已执行轨迹。



[图：p02-coupled，同一巡检员1，关键任务完成链；中间部分访问省略。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/execution-chain.svg)




[图：17号665秒派出的是例行访问；其公开风险685秒才出现。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/task-17.svg)



[图：21号650秒见风险，705秒额外派单，725秒完成，异常在710秒已结束。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/task-21.svg)



17／21是另一组Tour—FIFO完整轨迹：17号665秒例行派出、685秒见风险、690秒确认；21号650秒见风险、705秒额外派出、725秒测量时已过710秒结束。两类案例分别支持机制时序与响应门槛诊断。

### D. 原论文内部比较



[图：原文表8／9均值±95%CI。两种Greedy的藻华终值相同，按原表保留。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/original-paper-scores.svg)



原文在水域任务内比较DRL、Greedy、VRP及VAE/Myopic估计组合，测试100个未参与训练的场景。图取表8／9的终值均值与95%区间；“约快30%”描述曲线更早降低。原文Average的归一分母随复现对齐；本任务主表另定义并补算资产加权年龄。

### E. 历史封存包的横向表

<div class="table-wrap"><table class="comparison-table" data-table="method-comparison"><thead><tr><th rowspan="2">方法</th><th colspan="3">状态估计</th><th rowspan="2">适配idleness<br>加权年龄↓</th><th colspan="3">异常任务</th><th colspan="3">成本与效率</th><th rowspan="2">本任务状态</th></tr><tr><th>RMSE<br>°C↓</th><th>加权RMSE<br>°C↓</th><th>R²↑</th><th>确认段数<br>（比例）↑</th><th>截尾等待<br>秒↓</th><th>硬重访<br>违规</th><th>移动变化<br>%</th><th>完成量变化<br>%</th><th>单步推理<br>ms</th></tr></thead><tbody><tr data-comparison-method="tour" data-result-state="primary"><td>固定巡回Tour</td><td>未留帧</td><td>未留帧</td><td>未留帧</td><td>0.310901</td><td>28/89（31.5%）</td><td>78.16</td><td>0</td><td>+0.00</td><td>+0.00</td><td>未计时</td><td>已运行·主比较</td></tr><tr data-comparison-method="shuffled" data-result-state="primary"><td>名义估计＋风险位置置乱</td><td>未留帧</td><td>未留帧</td><td>未留帧</td><td>0.313138</td><td>25/89（28.1%）</td><td>81.06</td><td>0</td><td>+0.63</td><td>-0.34</td><td>未计时</td><td>已运行·主比较</td></tr><tr data-comparison-method="S1-age" data-result-state="development"><td>线性暂缓①：等待15秒</td><td>未留帧</td><td>未留帧</td><td>未留帧</td><td>0.312994</td><td>60/89（67.4%）</td><td>60.23</td><td>0</td><td>+0.55</td><td>-0.30</td><td>未计时</td><td>已运行·开发并列60</td></tr><tr data-comparison-method="S2-risk_time" data-result-state="development"><td>线性暂缓②：多特征</td><td>未留帧</td><td>未留帧</td><td>未留帧</td><td>0.312888</td><td>60/89（67.4%）</td><td>58.14</td><td>0</td><td>+0.49</td><td>-0.28</td><td>未计时</td><td>已运行·开发并列60</td></tr><tr data-comparison-method="fifo" data-result-state="primary"><td>名义估计＋返回保护FIFO</td><td>未留帧</td><td>未留帧</td><td>未留帧</td><td>0.313052</td><td>70/89（78.7%）</td><td>49.69</td><td>0</td><td>+0.50</td><td>-0.33</td><td>未计时</td><td>已运行·主比较</td></tr><tr data-comparison-method="vae_unet_greedy" data-result-state="not_run"><td>VAE-UNet + Greedy</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>历史封存状态；新结果见补充基准</td></tr><tr data-comparison-method="vae_unet_drl" data-result-state="not_run"><td>VAE-UNet + DRL</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>历史封存状态；新结果见补充基准</td></tr></tbody></table></div>

历史主比较采用同12个预登记过程；两条线性暂缓规则为九候选中并列60段的开发对照。原包没有保存统一预测—真值帧或逐步计时，因此“未留帧／未计时”继续保留。历史VAE两行表示当时包内未运行，新增适配与独立结果见第4节。

在该历史包中，Tour整体加权年龄0.310901，FIFO为0.313052；FIFO确认70/89，移动平均+0.50%、完成量下降约0.33%。这些数值与本轮四故障基准各有自己的样本分母。

### F. 新基准的逐故障族结果

<div class="table-wrap"><table data-table="supplement-families" class="supplement-table"><thead><tr><th>故障条件</th><th>方法</th><th>平均确认段</th><th>平均异常段</th><th>平均截尾等待 / 秒</th><th>加权RMSE / °C</th><th>平均额外访问</th></tr></thead><tbody><tr><td>辅助馈电＋CDU</td><td>名义＋Tour</td><td>2.67</td><td>6.83</td><td>73.14</td><td>0.501</td><td>0.00</td></tr><tr><td>辅助馈电＋CDU</td><td>名义＋FIFO</td><td>4.83</td><td>6.83</td><td>51.71</td><td>0.501</td><td>6.33</td></tr><tr><td>辅助馈电＋CDU</td><td>名义＋Greedy</td><td>4.83</td><td>6.83</td><td>51.56</td><td>0.501</td><td>5.92</td></tr><tr><td>辅助馈电＋CDU</td><td>名义＋PPO</td><td>4.00</td><td>6.83</td><td>62.29</td><td>0.499</td><td>3.94</td></tr><tr><td>辅助馈电＋CDU</td><td>CVAE＋FIFO</td><td>4.75</td><td>6.83</td><td>52.57</td><td>0.199</td><td>6.03</td></tr><tr><td>辅助馈电＋CDU</td><td>CVAE＋Greedy</td><td>4.75</td><td>6.83</td><td>52.40</td><td>0.200</td><td>5.53</td></tr><tr><td>辅助馈电＋CDU</td><td>CVAE＋PPO</td><td>4.75</td><td>6.83</td><td>52.63</td><td>0.200</td><td>6.14</td></tr><tr><td>接触热点</td><td>名义＋Tour</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.210</td><td>0.00</td></tr><tr><td>接触热点</td><td>名义＋FIFO</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.210</td><td>0.00</td></tr><tr><td>接触热点</td><td>名义＋Greedy</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.210</td><td>0.00</td></tr><tr><td>接触热点</td><td>名义＋PPO</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.210</td><td>0.00</td></tr><tr><td>接触热点</td><td>CVAE＋FIFO</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.149</td><td>0.00</td></tr><tr><td>接触热点</td><td>CVAE＋Greedy</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.149</td><td>0.00</td></tr><tr><td>接触热点</td><td>CVAE＋PPO</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.149</td><td>0.00</td></tr><tr><td>传感偏差</td><td>名义＋Tour</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.753</td><td>0.00</td></tr><tr><td>传感偏差</td><td>名义＋FIFO</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.753</td><td>0.00</td></tr><tr><td>传感偏差</td><td>名义＋Greedy</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.753</td><td>0.00</td></tr><tr><td>传感偏差</td><td>名义＋PPO</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.753</td><td>0.00</td></tr><tr><td>传感偏差</td><td>CVAE＋FIFO</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.738</td><td>0.00</td></tr><tr><td>传感偏差</td><td>CVAE＋Greedy</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.738</td><td>0.00</td></tr><tr><td>传感偏差</td><td>CVAE＋PPO</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.738</td><td>0.00</td></tr><tr><td>二次泵故障</td><td>名义＋Tour</td><td>3.50</td><td>8.67</td><td>82.60</td><td>0.674</td><td>0.00</td></tr><tr><td>二次泵故障</td><td>名义＋FIFO</td><td>6.42</td><td>8.67</td><td>54.01</td><td>0.677</td><td>7.67</td></tr><tr><td>二次泵故障</td><td>名义＋Greedy</td><td>6.33</td><td>8.67</td><td>54.64</td><td>0.686</td><td>7.42</td></tr><tr><td>二次泵故障</td><td>名义＋PPO</td><td>5.11</td><td>8.67</td><td>68.12</td><td>0.684</td><td>4.81</td></tr><tr><td>二次泵故障</td><td>CVAE＋FIFO</td><td>6.33</td><td>8.67</td><td>54.37</td><td>0.221</td><td>7.36</td></tr><tr><td>二次泵故障</td><td>CVAE＋Greedy</td><td>6.25</td><td>8.67</td><td>54.92</td><td>0.222</td><td>7.19</td></tr><tr><td>二次泵故障</td><td>CVAE＋PPO</td><td>6.39</td><td>8.67</td><td>54.72</td><td>0.221</td><td>7.44</td></tr></tbody></table></div>

每故障族12个条件，学习方法先平均三个训练种子；表为逐条件均值。主要统计采用四故障族等权，无异常的健康与虚假提示条件另列于正文。

### G. 训练种子与物理种子块变化

<div class="table-wrap"><table data-table="supplement-seeds" class="supplement-table"><thead><tr><th>方法</th><th>种子271</th><th>种子811</th><th>种子1931</th><th>确认训练种子SD</th><th>误差训练种子SD / °C</th></tr></thead><tbody><tr><td>名义＋PPO</td><td>2.90</td><td>3.23</td><td>1.96</td><td>0.659</td><td>0.0034</td></tr><tr><td>CVAE＋FIFO</td><td>3.17</td><td>3.19</td><td>3.21</td><td>0.021</td><td>0.0017</td></tr><tr><td>CVAE＋Greedy</td><td>3.15</td><td>3.17</td><td>3.19</td><td>0.021</td><td>0.0019</td></tr><tr><td>CVAE＋PPO</td><td>3.21</td><td>3.19</td><td>3.21</td><td>0.012</td><td>0.0021</td></tr></tbody></table></div>


[图：逐个种子块展示配对确认差；各块内四种故障等权，编号表示登记身份。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-seed-blocks.svg)


<div class="table-wrap"><table data-table="supplement-policy-training" class="supplement-table"><thead><tr><th>策略</th><th>训练种子</th><th>回合</th><th>全局时间步</th><th>实际选择数</th><th>存在多个合法候选</th><th>有选择余地比例</th><th>执行＋更新分钟</th></tr></thead><tbody><tr><td>名义＋PPO</td><td>271</td><td>120</td><td>43080</td><td>170969</td><td>470</td><td>0.27%</td><td>2.57</td></tr><tr><td>CVAE＋PPO</td><td>271</td><td>120</td><td>43080</td><td>170956</td><td>437</td><td>0.26%</td><td>4.92</td></tr><tr><td>名义＋PPO</td><td>811</td><td>120</td><td>43080</td><td>170954</td><td>448</td><td>0.26%</td><td>2.39</td></tr><tr><td>CVAE＋PPO</td><td>811</td><td>120</td><td>43080</td><td>170961</td><td>460</td><td>0.27%</td><td>5.30</td></tr><tr><td>名义＋PPO</td><td>1931</td><td>120</td><td>43080</td><td>170957</td><td>466</td><td>0.27%</td><td>2.48</td></tr><tr><td>CVAE＋PPO</td><td>1931</td><td>120</td><td>43080</td><td>170950</td><td>453</td><td>0.26%</td><td>5.44</td></tr></tbody></table></div>

种子271／811／1931列为每主要条件平均确认段，SD是三个训练种子间的样本标准差；误差SD采用闭环加权RMSE。图中每个柱对应独立物理种子块的配对差，四故障条件等权。

PPO的选择数按执行者实际可选集合计；只有一个合法候选时，策略没有排序自由。训练耗时为完整回合执行、评分、留存和四次更新的累计墙钟时间，加载与预热另计。这一比例帮助解释当前返回保护与任务设定给学习留下多大的决策空间。

<h3 id="gap-diagnosis">H. 估计误差与确认段数的事后轨迹核对</h3>

此处读取原留出日志，无新增环境、模型推理或训练。144组比较包含同一条件的三个模型重复，独立物理种子块仍为12。三个模型种子的“新增／丢失”分别为1／4、1／3、0／1，平均净差为−2段，与总表155→153一致。

<div class="table-wrap"><table data-table="estimation-confirmation-gap"><thead><tr><th>任务</th><th>原评价段</th><th>名义FIFO：提示→完成</th><th>CVAE-FIFO：提示→完成</th><th>确认变化</th></tr></thead><tbody><tr><td>41号热检查</td><td>855—885秒</td><td>865→895秒</td><td>835→880秒</td><td>CVAE新增</td></tr><tr><td>45号热检查</td><td>850—890秒</td><td>860→875秒</td><td>840→900秒</td><td>CVAE丢失</td></tr></tbody></table></div>

表取`test04-cooling`、模型种子271、同一执行者5。两条轨迹在860秒首次分叉：两项访问的资格、返回证书和预算都通过，CVAE-FIFO按835秒早于840秒的入队顺序选41号。41号的确认增加与45号的确认丢失在该回合相抵；其余净差来自案例02、06、07的局部提示与访问轨迹变化。此诊断解释本批记录，完整得失及首次分叉保存在[事后核对数据](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/source-data/estimation-confirmation-gap.json)。



<a id="sources"></a>
## 来源与继续查阅

- [工程控制、规模与官方标准核查](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/report-engineering-alignment-20261103.md)。
- [RGB／IR视觉成果与接口核查](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/report-pid-interface-20261103.md)。
- [本任务横向指标、公式与只读复算](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/report-comparison-metrics-20261103.md)。
- [独立补充基准：完整方法](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/supplement-study-methods.md)、[新协议、模型参数及结果原件索引](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/evidence/supplement-study/README.md)。
- [补充研究设计依据](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/supplement-study-design-20261103.md)、[评价与缺失指标核查](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/supplement-metrics-audit-20261103.md)。
- [主机制验证与完整原件](https://github.com/DonsonHH/Zhinengti-RSI/blob/2db2adf146357ec35306503ed15183c0c4100d20/evidence/event-validation/final/README.md)、[九规则开发记录](https://github.com/DonsonHH/Zhinengti-RSI/blob/2db2adf146357ec35306503ed15183c0c4100d20/evidence/response-defer/README.md)。
- [名义估计与故障原件核查](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/report-method-formulas-20261103.md)、[规则动作诊断](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/report-rule-diagnosis-20261103.md)。
- [原论文指标核查](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/original-paper-metrics-20261103.md)、[模型方程与参数](https://github.com/DonsonHH/Zhinengti-RSI/blob/2db2adf146357ec35306503ed15183c0c4100d20/paper/model-appendix.md)、[机制讨论稿](https://github.com/DonsonHH/Zhinengti-RSI/blob/2db2adf146357ec35306503ed15183c0c4100d20/paper/manuscript_zh.md)。

正文、图像、公式与表格全部内嵌，可单文件离线阅读。本次新增独立数据生成、九个模型训练、最终测试和物理规模检查；旧封存记录与新证据分别保留。环境尝试、连续观测帧、模型种子及独立物理种子块采用各自分母。
