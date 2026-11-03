> 正文审阅版：正文、公式和数值表与单文件HTML同源；图版保留SVG链接，便于文本工具读取。

# 大型液冷算力设施的多系统巡检研究

导师自阅报告 · 设施建模、态势估计、巡检决策与实验验证 · 2026-11-03

<a id="overview"></a>
## 0. 报告导读

### 0.1 核心进展摘要

<aside class="project-summary" aria-label="项目主线摘要"><strong>研究主线与阶段成果</strong><p>本研究建立供电、双回路液冷与局部控制的耦合模型，将公开遥测、温度估计和专业巡检连接为观测—派单—量测闭环。已完成3个CVAE-U-Net和6个PPO的真实训练，并在12个独立种子块上执行1080个留出测试回合。同一观测流中，非刚量测加权RMSE由0.443降至0.172°C；专业确认以名义FIFO的155/210段最高。CVAE主要改善连续温度态势，异常确认还由局部越阈值、队列与合法访问时机共同决定。</p></aside>

### 0.2 导师关切点与章节映射

|导师关心的内容|本报告对应材料|阅读位置|
|---|---|---|
|配电、液冷与设备自控|10 kV—380 V—54 V供电链、双回路CDU换热、三路反馈及国标对照状态|[第1章：设施物理层](#model)|
|RGB转红外与专业测温|已有B-PID电气显示样例、机房拟适配对象及合格接点观测通道|[2.1：配电视觉支路](#visual-branch)|
|大型设施复杂度|El Capitan工程参照、128柜状态与任务规模、512／1024柜扩展口径|[1.3：规模设置](#scale)、[4.5：规模实测](#scale-results)|
|全局态势与风险|名义估计、残差CVAE-U-Net、四专业风险生成及新测试态势示例|[第2章：感知方法](#hotspots)、[4.2：估计结果](#estimation-results)|
|原论文指标与横向比较|同信息同约束七方法、误差、确认、年龄、代价及机制诊断|[第3章：派单方法](#fifo)、[第4章：实验结果](#comparison)|

前3章依次定义设施、感知和决策方法；第4章统一展示新基准结果，第5章归纳结论与下一阶段工作。历史89段基准和500秒工程回看集中保留在[第6章附录](#appendix)，便于按需追溯。

<a id="model"></a>
## 1. 设施物理层：三系统耦合建模

<p class="chapter-lead">本章给出被巡检设施的物理对象、跨系统作用关系和控制边界，为后续估计与派单提供共同的状态与规模设置。</p>

### 1.1 供电—液冷—自控耦合机理

#### 1.1.1 供配电拓扑与负载

模型按10 kV入口、380 V交流配电、UPS／整流和54 V直流机柜组织供电链。送达IT功率形成设备热负荷，辅助馈电可用性同时约束二次泵的有效速度，将电气异常与排热能力连接起来。

#### 1.1.2 一次与二次液冷回路

**CDU**为冷却液分配与换热单元。一次回路连接设施冷源，二次回路连接机柜冷板，两侧在CDU交换热量；每8柜构成一组，128柜对应16组。El Capitan／Cray EX官方资料提供了冷却塔、循环泵、冷板和测控层次的工程参照。[LLNL](https://www.llnl.gov/article/54496/meet-machines-matter-how-el-capitan-keeps-its-cool)、[HPE](https://www.hpe.com/us/en/collaterals/collateral.a00094635enw.html)。



<a id="figure-model"></a>

[图：本项目集中参数模型的供电、双回路液冷与局部控制计算关系。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/model.svg)



#### 1.1.3 跨系统动态关系

|计算对象|当前关系及用途|
|---|---|
|机柜热状态|热容×温升速率＝送达IT功率−冷板换热−环境散热|
|CDU与一次回路|有效度、两侧热容流率和供回液温差决定换热；冷却塔排热影响共享一次供液|
|二次泵与供电|有效泵速包含“指令×√辅助供电可用性”，水力代理求得流量与压差|
|电气接点|接触损耗驱动接点温升；合格电气检查更新对应设备组的接点温度观测|

### 1.2 本地自控与2026液冷国标对照

#### 1.2.1 三路滞后反馈控制律

本地控制器根据设备传感温度与一次液温调节二次泵、塔风机和IT限功率。巡检感知侧另通过固定遥测和已完成的专业检查获得信息。

<div class="principle-box" id="principle-control">
<p class="principle-title">已运行的三路控制目标</p>
<div class="formula-scroll"><p class="formula" role="math">u*<sub>p</sub> = clip[0.85 + 0.035(max<sub>i∈p</sub>T<sup>sens</sup><sub>i</sub> − 58), 0.75, 1.2]</p><p class="formula" role="math">v* = clip[0.85 + 0.10(T<sub>primary</sub> − 32), 0.25, 1.2]</p><p class="formula" role="math">θ*<sub>i</sub> = clip[1 − 0.035(T<sup>sens</sup><sub>i</sub> − 65), 0.20, 1]</p><p class="formula" role="math">x<sub>k+1</sub> = x<sub>k</sub> + 0.25(x*<sub>k</sub> − x<sub>k</sub>)</p></div>
<p>u为泵指令，v为塔风机指令，θ为限功率系数；温度用°C，指令无量纲。5秒步长对应20秒一阶命令滞后。设备代理温度达到95°C时，模拟硬件保护将实际限功率系数置零。</p>
</div>

<h4 id="standards">1.2.2 系统／机柜两层标准映射</h4>

|2026液冷国家标准|官方发布／实施信息|当前对照状态|
|---|---|---|
|[GB/T 48023-2026《数据中心冷板式液冷系统技术规范》](https://std.samr.gov.cn/gb/search/gbDetailed?id=581F4B90BB7B80E8E06397BE0A0AF9E7)|2026-07-30发布；2027-02-01实施|正式入口与元数据已定位；目录、控制条款及阈值待取得可核读文本|
|[GB/T 48097-2026《数据中心冷板式液冷机柜通用规范》](https://std.samr.gov.cn/gb/search/gbDetailed?id=5A13050B0299303FE06397BE0A0ADA7D)|2026-08-28发布；2027-03-01实施|按系统与机柜两层建立后续映射，正式条款待核读|

当前实现包括温度、流量与水力压差计算，以及上述温度反馈和模拟断载。下一步将正式要求对应到测量、方程、动作与验证工况，扩展压差反馈、防凝露、低流量联锁及多模式控制。33.6 kg/s等现有异常界值采用本研究设定。

<h3 id="scale">1.3 大型设施参照与模块化规模设置</h3>

#### 1.3.1 E级超算工程参照

以El Capitan的负载数量级作为参照。TOP500的2026年6月记录给出Rmax＝1.809 EFLOP/s、理论Rpeak＝2.82110 EFLOP/s、报告功率29.68462 MW（测量等级2）；E级指每秒10<sup>18</sup>次浮点运算的性能数量级。[TOP500原始记录](https://www.top500.org/system/180307/)。

|参照量／模型量|数值|用途或边界|
|---|---:|---|
|El Capitan报告功率|29.68462 MW|绑定TOP500期次与测量等级的工程参照|
|本模型名义IT负荷|32 MW|128×250 kW的研究设置|
|机柜／设备组|128／16|每组8柜，共享冷源并具有组内耦合|
|热状态／指令状态|161／145|机柜、液温与接点温度；泵、风机与限功率滞后|
|专业任务／执行者|176／18|热、电气、制冷、自控四类检查|

#### 1.3.2 模块化扩展与验证口径

底层按8柜组组织参数。128／512／1024柜对应32／128／256 MW名义IT负荷，可分别检查物理积分、状态留存及构造巡回。当前学习估计网格与端到端巡检基准固定为128柜／16组；[4.5节](#scale-results)报告三规模的纯物理实测和静态人员巡回核查。

<aside class="scope-note"><p><strong>模型范围：</strong>当前采用集中参数与合成研究参数。额定IT功率、基准报告功率和算力性能分别列示；现场校准、E/G算力映射与更大规模学习调度构成后续工程验证对象。</p></aside>

<a id="hotspots"></a>
## 2. 态势感知层：视觉接口、温度估计与风险生成

<p class="chapter-lead">感知层把固定遥测和已完成检查转为全机房温度估计与专业风险请求，形成第3章调度方法可使用的公开输入。</p>

<h3 id="visual-branch">2.1 配电巡检视觉支路</h3>

#### 2.1.1 既有RGB→伪彩IR显示样例

<strong>PID</strong>指Physics-Informed Diffusion图像生成工作，B-PID为本地视觉项目分支；RGB为可见光图像，IR为红外。已有材料包括以下户外电气样例，用于展示前期的显示图重建路径。[原PID方法](https://github.com/fangyuanmao/PID)。



<a id="figure-pid-visual-sample"></a>

[图：PID项目既有户外电气样例，同图精修、显示域；三张原图逐字节保留，数值计量按独立测温通道处理。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/pid-visual-sample.svg)



户外绝缘子、铁塔与导线样例与机房配电具有电气设备外观感知这一共同接口。机房中的拟适配对象为10 kV／380 V开关柜、母排和54 V机柜交直流接点，后续经机房图像适配与校准测温接入后，开展热点复核和观测更新。

#### 2.1.2 图像参考与合格测温接口

Renly已有参考元数据入口，以及“合格接点测温→接触温度状态更新”通道。图像支路提供外观线索，℃数值由校准测温通道提供；RGB采集、生成推理、热点选点及真实仪器接入按下图逐步串接。



<a id="figure-visual-interface"></a>

[图：已实现的参考元数据入口与合成接点测量分层表示；虚线标出RGB推理、选点及现场仪器桥接。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/visual-interface.svg)



当前更新为<strong>T̂<sub>contact,p</sub>←合格接点量测</strong>。接触电阻属于物理过程设定参数，反向辨识还需电流、热响应和换热条件。

<aside class="scope-note"><p><strong>视觉证据范围：</strong>三联图为同一户外电气图像的精修显示样例；PID主训练材料1,367对属于野火域。机房主比较采用合成专业测量通道，视觉推理、机房图像适配与真实仪器桥接分别按接口状态记录。</p></aside>

### 2.2 连续温度估计器

#### 2.2.1 名义热平衡递推与量测校正

系统为128柜各保留一个温度估计，依据公开送达功率、供液温度与流量估计每5秒推进热平衡。32个固定温度点持续校正，热检查完成后校正对应柜号；每次更新都使用当前已到达的观测。

<div class="principle-box" id="principle-estimation">
<p class="principle-title">温度预测与量测校正</p>
<div class="formula-scroll"><p class="formula" role="math">T̂<sup>−</sup><sub>i,k+1</sub> = T̂<sub>i,k</sub> + (Δt/C)[P<sub>i</sub> − U<sub>i</sub>(T̂<sub>i,k</sub> − T<sub>s,p</sub>) − U<sub>a</sub>(T̂<sub>i,k</sub> − T<sub>a</sub>)]</p><p class="formula" role="math">U<sub>i</sub> = 12[max(q̂<sub>i</sub>,0)/6]<sup>0.8</sup>；收到新热测量y<sub>i</sub>时，T̂<sub>i</sub> ← y<sub>i</sub></p></div>
<p>Δt＝5秒，C＝800 kJ/K；P为公开送达IT功率，T<sub>s,p</sub>为组供液温度，T<sub>a</sub>＝28°C，U<sub>a</sub>＝0.12 kW/K。每柜q̂以kg/s计，U以kW/K计。各柜从50°C初始化；流量取最近量测，尚无量测的组按泵指令和额定流量估计，平均分给8柜。</p>
</div>

#### 2.2.2 温度残差CVAE-U-Net

学习估计器将最近四个连续5秒端点的14维公开特征与当前名义温度拼成57通道输入，在8×16设备网格上估计温度残差。两个下采样层、空间跳接和16维条件潜变量组成295,777参数的CVAE-U-Net；运行时取条件先验均值，两类估计器均以当前端点的新温度量测覆盖对应位置。



<a id="figure-supplement-unet"></a>

[图：本次真实训练的温度残差CVAE-U-Net。公开输入57通道，295,777个参数；训练后验只用于监督，在线取条件先验均值。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-unet.svg)



条件先验／后验与空间编码—解码分别参考[条件生成模型](https://proceedings.neurips.cc/paper_files/paper/2015/file/8d55a249e6baa5c06772297520da2051-Paper.pdf)和[U-Net](https://arxiv.org/abs/1505.04597)。监督目标为离线物理温度，输入为公开遥测和专业量测历史；训练记录与误差见[4.1—4.2节](#estimation-results)。

### 2.3 多专业风险映射

#### 2.3.1 连续态势与事件入口

温度场保留连续状态梯度；派单根据公开风险分建立待确认请求。热风险由温度越界项和功率缺口项组成：

<div class="principle-box" id="principle-risk"><p class="principle-title">原热风险评分保持不变</p><div class="formula-scroll"><p class="formula" role="math">r<sub>i</sub> = min{4, max(T̂<sub>i</sub> − 65,0)/20 + 0.25[1 − P<sub>del,i</sub>/max(P<sub>req,i</sub>,10<sup>−12</sup>)]}</p></div><p>第一项为估计温度越界，第二项为功率需求缺口。风险分用于建立待确认请求，温度色阶用于连续态势呈现。</p></div>

#### 2.3.2 四专业风险通道

记h<sub>i</sub>＝max(T̂<sub>i</sub>−65,0)/20，g<sub>i</sub>为公开功率缺口。c<sub>p</sub>＝max(T̂<sub>contact,p</sub>−60,0)/30，接点温度由专业量测更新；f<sub>p</sub>＝max(1−q̂<sub>p</sub>/33.6,0)，q̂为最近已获组流量，可来自固定遥测或专业检查。

b<sub>p</sub>初值为0，仅在专业校验时按组平均传感误差绝对值是否>1°C更新为1或0，保持至下次校验。组内最大h与平均g把柜级信息映射到设备组，最终分数上限均为4。

|专业|现有公开风险组成|完成检查后更新|
|---|---|---|
|热检查|h<sub>i</sub>＋0.25g<sub>i</sub>|该柜温度|
|电气检查|c<sub>p</sub>＋组平均g＋0.1×组最大h|该组接点温度|
|制冷检查|f<sub>p</sub>＋0.25×组最大h|该组冷却液流量|
|自控检查|b<sub>p</sub>＋0.25×组最大h|该组传感偏差校验状态|

风险分是待核查严重度代理；有效异常确认以专业量测及离线评价标签核对。新留出过程的态势三联图与局部时序在[4.2.2节](#estimation-example)统一展示，旧500秒工程帧在[附录A](#engineering-history)保留。

<a id="fifo"></a>
## 3. 巡检决策层：受返回时间保护的多专业派单

<p class="chapter-lead">决策层维护例行巡回与风险待办两套任务，在资格、预约、预算和完整循环重访约束下选择下一项检查。</p>

### 3.1 闭环架构与执行契约

#### 3.1.1 四专业契约与两本任务账

每回合为1800秒，共18名执行者；四专业的测量对象、人数、服务耗时和重访期限如下。例行账维持持续覆盖，事件账记录新出现且尚未完成专业核查的风险请求。

<div class="table-wrap"><table data-table="task-contract"><thead><tr><th>专业</th><th>完成检查后得到什么</th><th>人数</th><th>每次服务</th><th>最大重访间隔</th></tr></thead><tbody><tr><td>热检查</td><td>该机柜代表温度</td><td>12</td><td>10秒</td><td>300秒</td></tr><tr><td>电气检查</td><td>该组电气接触温度</td><td>2</td><td>20秒</td><td>600秒</td></tr><tr><td>制冷检查</td><td>该组冷却液流量</td><td>2</td><td>20秒</td><td>600秒</td></tr><tr><td>自控检查</td><td>传感读数误差（完成校验后）</td><td>2</td><td>15秒</td><td>600秒</td></tr></tbody></table></div>


<a id="figure-inspection-architecture"></a>

[图：根据本项目已实现接口重绘总体架构；上方在线决策只用公开信息，下方真值与日志用于事后评分。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/inspection-architecture.svg)



请求待派有效期为120秒，全体额外访问上限12次。额外加查保留原例行指针；派出时占用预算和预约，实际完成后以专业量测更新观测与任务账本。

#### 3.1.2 完整循环返回证书

批准加查前，程序预测当前候选与原循环所有后续任务的完成时刻，确认候选自身、完整返回循环和重复周期均满足期限。

<div class="principle-box" id="principle-return"><p class="principle-title">完整返回核算</p><div class="formula-scroll"><p class="formula" role="math">t + τ(p,x) + τ(x,r) ≤ L<sub>r</sub> + D<sub>r</sub>；τ(a,b) = 5⌈[d(a,b)/v + s<sub>b</sub>]/5⌉</p><p class="formula" role="math">对完整循环：F<sub>j</sub> ≤ L′<sub>j</sub> + D<sub>j</sub>；最小余量≥0</p></div><p>此简式取额外加查x与原任务r不同。τ包括目的任务服务，v＝1 m/s；首次未检的L按0起算，L′随预计访问更新。程序核查候选自身、完整循环及重复周期；每次实际完成后重新选择。</p></div>

### 3.2 共同合法候选集合下的策略族

#### 3.2.1 固定Tour与先入先出FIFO

Tour执行原定所属循环。FIFO（First In, First Out，先入先出）在执行者空闲时，从“本人例行下一项＋本人待确认请求”中先筛出合法候选，再选择首次提示最早的事件；没有合法事件时执行例行头。所有响应方法共用资格、预约、返回、终点与预算检查。

#### 3.2.2 即时Greedy与响应／暂缓规则

Greedy在所有合法候选中最大化“当前公开风险／取整完成耗时”，平分时依次优先例行项、较早提示和较小任务编号。响应／暂缓线性规则则先由FIFO选定一个合法事件，再在该事件与例行头之间二选一；规则表达式与历史开发结果见[附录C](#historical-benchmark)。

#### 3.2.3 共享PPO策略

PPO使用21维公开候选特征和32×32共享actor，在同一合法集合内选择；仅训练使用10维公开全局特征critic。特征涵盖专业、公开严重度、年龄、ETA、量测状态、等待、预算和返回余量，执行者按固定编号依次决策。



<a id="figure-supplement-crossed-design"></a>

[图：估计器与调度器的共同候选、约束和执行接口。PPO使用公开奖励训练，原始异常标签留给离线评价。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-crossed-design.svg)



训练采用公开观测奖励的[PPO裁剪目标](https://arxiv.org/abs/1707.06347)：每个完整359步回合更新4轮，学习率0.0003，γ＝0.99、GAE λ＝0.95、clip＝0.2。名义／CVAE条件下的配对种子采用相同初始参数和案例次序，各策略固定使用第120回合checkpoint。

### 3.3 观测、物理过程与评价边界

同一条件下，各方法共享由本地控制器推进并预先生成的供电、温度与流量轨迹。巡检改变路线、专业量测时机和后续估计，设备状态按该本地控制轨迹演化。在线选择使用公开观测，异常标签和未来端点用于回合后的评分；实际分配、完成及初终点重访间隔进入独立审计。

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

温度误差以物理柜温为目标，“非刚量测”排除当前端点的温度回填；R²按逐回合SSE／SST计算后汇总，常量目标记NA。本研究四专业正标签阈值为：柜温>65°C、接点温度>60°C、组流量<33.6 kg/s、组平均传感误差绝对值>1°C；连续至少3个5秒正标签形成异常段。确认需在正标签端点完成合格告警量测，未确认段按结束时刻截尾。

加权年龄对各方法实际完成时刻解析积分，包含初始和1800秒终点间隔：

<div class="formula-scroll"><p class="formula" role="math">A<sub>j</sub>(t) = min[(t − L<sub>j</sub>)/D<sub>j</sub>,1]</p><p class="formula" role="math">J<sub>age</sub> = [1/(1800Σ<sub>j</sub>w<sub>j</sub>)] ∫<sub>0</sub><sup>1800</sup>Σ<sub>j</sub>w<sub>j</sub>A<sub>j</sub>(t)dt</p></div>

w为共同静态资产权重，D为专业重访期限，L为最近完成时刻。每条件先归一，再按登记权重汇总。主要统计先在条件内平均学习方法的三个模型种子，再在各物理种子块内等权四故障族；95%探索性区间采用12块、10,000次自举，随机种子20261103，训练种子变化另列，未做多重比较校正。

#### 4.1.2 数据划分与训练过程

|阶段|独立物理种子块|条件与用途|执行与训练记录|
|---|---:|---|---|
|训练|24|四故障＋健康／虚假提示；Tour与FIFO各一条观测流|288条流、34,560个快照；每策略种子120个PPO回合|
|开发|6|同六类条件；CVAE选择与冻结PPO诊断|72条流、8,640个快照；36次PPO诊断|
|最终测试|12|72条件，含60条唯一物理轨迹；种子与训练／开发隔离|7方法标签、每条件15个规则／模型实例，共1080回合|

四故障族涵盖辅助馈电＋CDU衰减、接触热点、传感偏差和二次泵故障；故障族在训练中已见，留出新种子及登记的位置／相位组合。健康与虚假提示共享物理过程并单列，连续快照与模型重复分别计数。



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

前期12个耦合过程共有89段异常，Tour／FIFO确认28/89与70/89；九条线性规则最高60/89。这一阶段用于建立机制基准，完整图、故障配置与负结果在[附录C—E](#historical-benchmark)保留。以下主比较使用独立新基准的210段异常，两批结果分别记账。

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

名义FIFO−Tour每主要条件净增+1.27 [+0.62, +1.88]段；CVAE-FIFO−名义FIFO为-0.04 [-0.09, +0.00]段；CVAE-PPO−CVAE-FIFO为+0.01 [-0.01, +0.04]段。区间表达物理种子块变化，[附录G](#training-seeds)另列训练种子离散程度。

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

在`test04-cooling`、模型271中，CVAE将45号提示从860秒提前至840秒，但41号更早在835秒入队。860秒两候选均合法，CVAE-FIFO先查41号并在880秒确认，再于900秒检查45号，错过850—890秒评价段；名义FIFO在875秒确认45号、895秒才检查41号。这里出现一增一失的机会交换，完整时序见[附录H](#gap-diagnosis)。

#### 4.4.2 合法候选稀疏与PPO排序自由度

训练记录中，约0.26%—0.27%的执行者实际选择集合包含多个合法候选。只有一项合法时，策略没有排序自由；这描述了当前责任区、返回约束与待办生成共同形成的决策空间。该比例的分母是执行者选择集合，完整计数与耗时在[附录G](#training-seeds)。

在每策略120回合预算下，CVAE-PPO相对CVAE-FIFO的确认增量区间跨零；相对名义PPO的改善同时包含估计器与各自训练策略的变化。候选空间、奖励和训练预算的单独贡献可在下一轮独立比较中检验。

<h3 id="scale-results">4.5 模块化物理规模与数值一致性</h3>



<a id="figure-supplement-scale"></a>

[图：每规模三种子×健康／耦合两工况的纯物理过程实测；带tracemalloc开销，范围为六次实测最小—最大，未作大规模学习调度。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-scale.svg)


<div class="table-wrap"><table data-table="supplement-scale" class="supplement-table"><thead><tr><th>机柜数</th><th>热状态／指令状态</th><th>执行者／专业任务</th><th>物理耗时中位数 / 秒</th><th>Python峰值 / MiB</th><th>静态检查</th></tr></thead><tbody><tr><td>128</td><td>161／145</td><td>18／176</td><td>0.517</td><td>0.50</td><td>构造闭合巡回满足</td></tr><tr><td>512</td><td>641／577</td><td>72／704</td><td>0.483</td><td>1.70</td><td>构造闭合巡回满足</td></tr><tr><td>1024</td><td>1281／1153</td><td>144／1408</td><td>0.500</td><td>3.32</td><td>构造闭合巡回满足</td></tr></tbody></table></div>
<div class="table-wrap"><table data-table="supplement-scale-cycles" class="supplement-table"><thead><tr><th>机柜数</th><th>热检查：人数；周期／期限</th><th>电气：人数；周期／期限</th><th>制冷：人数；周期／期限</th><th>自控：人数；周期／期限</th></tr></thead><tbody><tr><td>128</td><td>12人；240/300秒</td><td>2人；310/600秒</td><td>2人；310/600秒</td><td>2人；270/600秒</td></tr><tr><td>512</td><td>48人；240/300秒</td><td>8人；385/600秒</td><td>8人；385/600秒</td><td>8人；345/600秒</td></tr><tr><td>1024</td><td>96人；240/300秒</td><td>16人；465/600秒</td><td>16人；465/600秒</td><td>16人；425/600秒</td></tr></tbody></table></div>

每规模为三种子×健康／耦合两条件，360个5秒物理步。耗时含tracemalloc开销，内存范围为该物理段及温度序列留存；静态检查评价已构造的专业巡回。三规模的构造闭合巡回均满足各专业期限。360步物理耗时中位数约0.48—0.52秒，未随柜数呈单调上升；Python追踪峰值由0.50增至3.32 MiB，范围为该物理段及温度序列的留存。

18次运行的最大能量平衡残差为7.97e-08 kJ，最大电功率平衡残差为8.73e-11 kW，用于核对数值守恒一致性。512／1024柜验证覆盖物理过程与静态巡回，学习闭环结果对应128柜。

<a id="roadmap"></a>
## 5. 阶段结论与下一阶段工作

### 5.1 研究结论

设施层已形成供电—液冷—自控耦合过程，感知层实现名义／残差CVAE估计，决策层把专业事件确认与持续重访放入共同执行边界。独立留出比较显示，CVAE降低了温度误差，名义FIFO以155/210取得本批最高的模型平均确认量；更多确认伴随约0.34%的移动增量和整体年龄的小幅上升。

CVAE-PPO较名义PPO每主要条件平均增加0.507段，相对同估计器FIFO仅增加0.014段且区间跨零。当前可将名义FIFO保留为任务基准、CVAE保留为状态估计支路，再以未确认段与候选稀疏记录确定下一项研究假设。

### 5.2 后续四项工作包

|工作包|下一项具体工作|交付与判断|
|---|---|---|
|正式国标映射|取得两项正式条款，对应供回液、压差、流量、露点及保护需求|条款／测量／方程／动作／工况矩阵，区分标准参数与研究参数|
|机房视觉接入|用机房图像做域适配，关联资产／时刻；以校准测温支持热点复核与接点观测更新|视觉线索对专业确认的独立贡献，保留标定及时间对应证据|
|调度机制研究|在保留资格和硬重访约束下设计可比较的多候选机会，分别检验奖励与训练预算|候选机会、实际轨迹与确认增量；RSI反馈增量另立协议|
|大规模学习调度|解除128柜／16组及固定网格项，重训并核查人员、时延与重访|512／1024柜端到端学习结果，与本轮18次纯物理结果分别记录|

新假设继续在测试前冻结样本、权重、权限与预算。已有探索性收益参考为平均净增至少1段、区间下界>0、移动增加≤5%、完成量下降≤2%且约束零违规；具体评价随新问题登记。

<a id="appendix"></a>
## 6. 技术附录与可追溯原件

### 6.1 历史回看、执行记录与详细对照

以下材料保留历史基准、逐步核算及分组结果，正文以第4章的新留出比较为主。


<h4 id="engineering-history">附录 A. 500秒工程回看与原风险分布</h4>

本例来自已保存的固定巡回工程过程。估计／事后温度共用45—75°C色标；红框标出原风险分>0的64、67、70号柜，黑点为32个固定温度点。它与正文新测试案例00分别记账，名义递推原理见[2.2.1节](#principle-estimation)。



<a id="figure-estimated-temperature"></a>

[图：已有工程回看500秒的公开温度估计；与右图同一色标，红框叠加原热风险提示。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/estimated-temperature.svg)



<a id="figure-offline-temperature"></a>

[图：同一工程过程500秒的事后设备代表温度。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/offline-temperature.svg)




<a id="figure-public-risk"></a>

[图：已有工程回看：固定巡回，500秒；风险分由公开观测和名义估计计算。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/public-risk.svg)


<div class="table-wrap"><table data-table="hotspot-values"><thead><tr><th>机柜</th><th>当时公开风险分</th><th>名义估计温度／°C</th><th>事后代表温度／°C</th><th>固定温度遥测点</th></tr></thead><tbody><tr><td>64</td><td>0.1296</td><td>67.35</td><td>67.63</td><td>是</td></tr><tr><td>67</td><td>0.2623</td><td>69.58</td><td>69.53</td><td>否</td></tr><tr><td>70</td><td>0.1323</td><td>67.36</td><td>67.31</td><td>否</td></tr></tbody></table></div>

<h4 id="fifo-detail">附录 B. FIFO队列与完整返回核算实例</h4>

任务契约和证书公式见[3.1节](#principle-return)。下列历史记录说明例行账与风险账如何共同执行。



<a id="figure-fifo-cycle"></a>

[图：每名执行者空闲时从本人合法请求中选择；完成量测后进入下一轮。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/fifo-cycle.svg)


<div class="table-wrap"><table data-table="fifo-queue"><thead><tr><th>本人的待确认请求</th><th>首次提示时间</th><th>470秒时风险分</th><th>当下检查</th><th>本次选择</th></tr></thead><tbody><tr><td>机柜10热检查</td><td>450秒</td><td>0.0081</td><td>资格、可行性和预算均通过</td><td>先查</td></tr><tr><td>机柜8热检查</td><td>455秒</td><td>0.0656</td><td>资格、可行性和预算均通过</td><td>继续等待</td></tr></tbody></table></div>


<a id="figure-fifo-actions"></a>

[图：主验证第2个过程，一名热巡检员的实际记录；色块宽度表示移动与服务时间。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/fifo-actions.svg)


<div class="table-wrap"><table data-table="return-budget"><thead><tr><th>重新决策时刻</th><th>批准的加查</th><th>预计完成加查</th><th>随后按原循环返回0号</th><th>0号截止</th><th>完整循环最小余量</th></tr></thead><tbody><tr><td>470秒</td><td>10</td><td>500秒</td><td>525秒</td><td>545秒</td><td>20秒</td></tr><tr><td>500秒</td><td>8</td><td>515秒</td><td>540秒</td><td>545秒</td><td>5秒</td></tr></tbody></table></div>

原0号245秒完成、截止545秒，实际540秒完成，间隔295秒。10号450秒早于8号455秒入队，因此即使风险较低也先处理。日志保留0.0081／0.0656总分；额外加查保留例行指针，请求在量测或到期前持续记账。

<h4 id="historical-benchmark">附录 C. 历史耦合基准与规则诊断</h4>

历史工况A的12过程采用辅助馈电故障与CDU衰减，持续180秒；77段热异常、12段制冷异常共89段。供电与换热乘子分别为0.05、0.20，峰值总输入23.15—24.14 MW。下列图与主文210段留出结果使用各自分母。



<a id="figure-confirmations"></a>

[图：历史耦合工况A：12个过程，共89段异常；三列为各策略的有效确认量。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/confirmations.svg)




<a id="figure-outcome-costs"></a>

[图：历史耦合工况A的FIFO相对Tour比较；区间、代价与探索性门槛均来自封存记录。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/outcome-costs.svg)



<div class="table-wrap"><table data-table="fault-cases"><thead><tr><th>过程</th><th>种子</th><th>目标柜号／设备组</th><th>故障开始→结束／秒</th><th>热／冷异常段</th></tr></thead><tbody><tr><td>01</td><td>101003</td><td>0号／第1组</td><td>150→330</td><td>8／1</td></tr><tr><td>02</td><td>101040</td><td>9号／第2组</td><td>335→515</td><td>6／1</td></tr><tr><td>03</td><td>101077</td><td>20号／第3组</td><td>520→700</td><td>6／1</td></tr><tr><td>04</td><td>101114</td><td>29号／第4组</td><td>705→885</td><td>7／1</td></tr><tr><td>05</td><td>101151</td><td>36号／第5组</td><td>150→330</td><td>7／1</td></tr><tr><td>06</td><td>101188</td><td>45号／第6组</td><td>335→515</td><td>7／1</td></tr><tr><td>07</td><td>101225</td><td>56号／第8组</td><td>520→700</td><td>6／1</td></tr><tr><td>08</td><td>101262</td><td>65号／第9组</td><td>705→885</td><td>6／1</td></tr><tr><td>09</td><td>101299</td><td>76号／第10组</td><td>150→330</td><td>7／1</td></tr><tr><td>10</td><td>101336</td><td>85号／第11组</td><td>335→515</td><td>7／1</td></tr><tr><td>11</td><td>101373</td><td>100号／第13组</td><td>520→700</td><td>4／1</td></tr><tr><td>12</td><td>101410</td><td>117号／第15组</td><td>705→885</td><td>6／1</td></tr></tbody></table></div>

异常阈值与最短持续时间见4.1.1节。该12过程按热／电气／制冷／自控分别形成77／0／12／0段。有效确认依照前一5秒采样格的正标签及告警测量核对，保留原结果的端点语义。



<a id="figure-paired-net"></a>

[图：过程01—12为预登记的12个配对过程；11个净增、1个持平。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/paired-net.svg)



九规则先由FIFO选定合法事件，再在事件与例行头之间决定响应／暂缓。R＝风险÷4，A＝等待秒数÷120，E＝两候选预计完成时差÷300，S＝两者完整循环最小余量差÷600；得分z≥0响应，否则执行例行头。



<a id="figure-registered-rules"></a>

[图：本项目9个唯一规则的得分式；R、A、E、S分别对应正文中的归一风险、等待、额外耗时与余量差。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/registered-rules.svg)



规则01的4R−1在229次二选一中全部为负，最高原风险0.7604，额外访问0，12条完整动作与Tour相同。规则06要求至少等待15秒，新增2段、丢失12段；这12段内均无完成量测，区间后首次量测正常。



<a id="figure-rule-diagnosis"></a>

[图：主过程01的完整策略轨迹对照，机柜4；等待规则为图中06号，按记录重绘。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/rule-diagnosis.svg)



该例两条轨迹260秒首次分叉。FIFO在300秒例行派4、320秒告警，赶上310—335秒的异常；等待规则315秒先查12、340秒再查4、365秒正常。335秒是未选候选的预计完成端点，图中只展示已执行轨迹。



<a id="figure-execution-chain"></a>

[图：p02-coupled，同一巡检员1，关键任务完成链；中间部分访问省略。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/execution-chain.svg)




<a id="figure-task-17"></a>

[图：17号665秒派出的是例行访问；其公开风险685秒才出现。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/task-17.svg)



<a id="figure-task-21"></a>

[图：21号650秒见风险，705秒额外派单，725秒完成，异常在710秒已结束。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/task-21.svg)



17／21是另一组Tour—FIFO完整轨迹：17号665秒例行派出、685秒见风险、690秒确认；21号650秒见风险、705秒额外派出、725秒测量时已过710秒结束。两类案例分别支持机制时序与响应门槛诊断。

#### 附录 D. 原论文水域任务对照



<a id="figure-original-paper-scores"></a>

[图：原文表8／9均值±95%CI。两种Greedy的藻华终值相同，按原表保留。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/original-paper-scores.svg)



原文在水域任务内比较DRL、Greedy、VRP及VAE/Myopic估计组合，测试100个未参与训练的场景。图取表8／9的终值均值与95%区间；“约快30%”描述曲线更早降低。原文Average的归一分母随复现对齐；本任务主表另定义并补算资产加权年龄。

#### 附录 E. 历史封存包横向表

<div class="table-wrap"><table class="comparison-table" data-table="method-comparison"><thead><tr><th rowspan="2">方法</th><th colspan="3">状态估计</th><th rowspan="2">适配idleness<br>加权年龄↓</th><th colspan="3">异常任务</th><th colspan="3">成本与效率</th><th rowspan="2">本任务状态</th></tr><tr><th>RMSE<br>°C↓</th><th>加权RMSE<br>°C↓</th><th>R²↑</th><th>确认段数<br>（比例）↑</th><th>截尾等待<br>秒↓</th><th>硬重访<br>违规</th><th>移动变化<br>%</th><th>完成量变化<br>%</th><th>单步推理<br>ms</th></tr></thead><tbody><tr data-comparison-method="tour" data-result-state="primary"><td>固定巡回Tour</td><td>未留帧</td><td>未留帧</td><td>未留帧</td><td>0.310901</td><td>28/89（31.5%）</td><td>78.16</td><td>0</td><td>+0.00</td><td>+0.00</td><td>未计时</td><td>已运行·主比较</td></tr><tr data-comparison-method="shuffled" data-result-state="primary"><td>名义估计＋风险位置置乱</td><td>未留帧</td><td>未留帧</td><td>未留帧</td><td>0.313138</td><td>25/89（28.1%）</td><td>81.06</td><td>0</td><td>+0.63</td><td>-0.34</td><td>未计时</td><td>已运行·主比较</td></tr><tr data-comparison-method="S1-age" data-result-state="development"><td>线性暂缓①：等待15秒</td><td>未留帧</td><td>未留帧</td><td>未留帧</td><td>0.312994</td><td>60/89（67.4%）</td><td>60.23</td><td>0</td><td>+0.55</td><td>-0.30</td><td>未计时</td><td>已运行·开发并列60</td></tr><tr data-comparison-method="S2-risk_time" data-result-state="development"><td>线性暂缓②：多特征</td><td>未留帧</td><td>未留帧</td><td>未留帧</td><td>0.312888</td><td>60/89（67.4%）</td><td>58.14</td><td>0</td><td>+0.49</td><td>-0.28</td><td>未计时</td><td>已运行·开发并列60</td></tr><tr data-comparison-method="fifo" data-result-state="primary"><td>名义估计＋返回保护FIFO</td><td>未留帧</td><td>未留帧</td><td>未留帧</td><td>0.313052</td><td>70/89（78.7%）</td><td>49.69</td><td>0</td><td>+0.50</td><td>-0.33</td><td>未计时</td><td>已运行·主比较</td></tr><tr data-comparison-method="vae_unet_greedy" data-result-state="not_run"><td>VAE-UNet + Greedy</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>历史封存状态；新结果见补充基准</td></tr><tr data-comparison-method="vae_unet_drl" data-result-state="not_run"><td>VAE-UNet + DRL</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>历史封存状态；新结果见补充基准</td></tr></tbody></table></div>

历史主比较采用同12个预登记过程；两条线性暂缓规则为九候选中并列60段的开发对照。原包没有保存统一预测—真值帧或逐步计时，因此“未留帧／未计时”继续保留。历史VAE两行表示当时包内未运行，新增适配与独立结果见第4节。

在该历史包中，Tour整体加权年龄0.310901，FIFO为0.313052；FIFO确认70/89，移动平均+0.50%、完成量下降约0.33%。这些数值与本轮四故障基准各有自己的样本分母。

#### 附录 F. 新基准逐故障族结果

<div class="table-wrap"><table data-table="supplement-families" class="supplement-table"><thead><tr><th>故障条件</th><th>方法</th><th>平均确认段</th><th>平均异常段</th><th>平均截尾等待 / 秒</th><th>加权RMSE / °C</th><th>平均额外访问</th></tr></thead><tbody><tr><td>辅助馈电＋CDU</td><td>名义＋Tour</td><td>2.67</td><td>6.83</td><td>73.14</td><td>0.501</td><td>0.00</td></tr><tr><td>辅助馈电＋CDU</td><td>名义＋FIFO</td><td>4.83</td><td>6.83</td><td>51.71</td><td>0.501</td><td>6.33</td></tr><tr><td>辅助馈电＋CDU</td><td>名义＋Greedy</td><td>4.83</td><td>6.83</td><td>51.56</td><td>0.501</td><td>5.92</td></tr><tr><td>辅助馈电＋CDU</td><td>名义＋PPO</td><td>4.00</td><td>6.83</td><td>62.29</td><td>0.499</td><td>3.94</td></tr><tr><td>辅助馈电＋CDU</td><td>CVAE＋FIFO</td><td>4.75</td><td>6.83</td><td>52.57</td><td>0.199</td><td>6.03</td></tr><tr><td>辅助馈电＋CDU</td><td>CVAE＋Greedy</td><td>4.75</td><td>6.83</td><td>52.40</td><td>0.200</td><td>5.53</td></tr><tr><td>辅助馈电＋CDU</td><td>CVAE＋PPO</td><td>4.75</td><td>6.83</td><td>52.63</td><td>0.200</td><td>6.14</td></tr><tr><td>接触热点</td><td>名义＋Tour</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.210</td><td>0.00</td></tr><tr><td>接触热点</td><td>名义＋FIFO</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.210</td><td>0.00</td></tr><tr><td>接触热点</td><td>名义＋Greedy</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.210</td><td>0.00</td></tr><tr><td>接触热点</td><td>名义＋PPO</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.210</td><td>0.00</td></tr><tr><td>接触热点</td><td>CVAE＋FIFO</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.149</td><td>0.00</td></tr><tr><td>接触热点</td><td>CVAE＋Greedy</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.149</td><td>0.00</td></tr><tr><td>接触热点</td><td>CVAE＋PPO</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.149</td><td>0.00</td></tr><tr><td>传感偏差</td><td>名义＋Tour</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.753</td><td>0.00</td></tr><tr><td>传感偏差</td><td>名义＋FIFO</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.753</td><td>0.00</td></tr><tr><td>传感偏差</td><td>名义＋Greedy</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.753</td><td>0.00</td></tr><tr><td>传感偏差</td><td>名义＋PPO</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.753</td><td>0.00</td></tr><tr><td>传感偏差</td><td>CVAE＋FIFO</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.738</td><td>0.00</td></tr><tr><td>传感偏差</td><td>CVAE＋Greedy</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.738</td><td>0.00</td></tr><tr><td>传感偏差</td><td>CVAE＋PPO</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.738</td><td>0.00</td></tr><tr><td>二次泵故障</td><td>名义＋Tour</td><td>3.50</td><td>8.67</td><td>82.60</td><td>0.674</td><td>0.00</td></tr><tr><td>二次泵故障</td><td>名义＋FIFO</td><td>6.42</td><td>8.67</td><td>54.01</td><td>0.677</td><td>7.67</td></tr><tr><td>二次泵故障</td><td>名义＋Greedy</td><td>6.33</td><td>8.67</td><td>54.64</td><td>0.686</td><td>7.42</td></tr><tr><td>二次泵故障</td><td>名义＋PPO</td><td>5.11</td><td>8.67</td><td>68.12</td><td>0.684</td><td>4.81</td></tr><tr><td>二次泵故障</td><td>CVAE＋FIFO</td><td>6.33</td><td>8.67</td><td>54.37</td><td>0.221</td><td>7.36</td></tr><tr><td>二次泵故障</td><td>CVAE＋Greedy</td><td>6.25</td><td>8.67</td><td>54.92</td><td>0.222</td><td>7.19</td></tr><tr><td>二次泵故障</td><td>CVAE＋PPO</td><td>6.39</td><td>8.67</td><td>54.72</td><td>0.221</td><td>7.44</td></tr></tbody></table></div>

每故障族12个条件，学习方法先平均三个训练种子；表为逐条件均值。主要统计采用四故障族等权，无异常的健康与虚假提示条件另列于正文。

<h4 id="training-seeds">附录 G. 训练种子与候选集合统计</h4>

<div class="table-wrap"><table data-table="supplement-seeds" class="supplement-table"><thead><tr><th>方法</th><th>种子271</th><th>种子811</th><th>种子1931</th><th>确认训练种子SD</th><th>误差训练种子SD / °C</th></tr></thead><tbody><tr><td>名义＋PPO</td><td>2.90</td><td>3.23</td><td>1.96</td><td>0.659</td><td>0.0034</td></tr><tr><td>CVAE＋FIFO</td><td>3.17</td><td>3.19</td><td>3.21</td><td>0.021</td><td>0.0017</td></tr><tr><td>CVAE＋Greedy</td><td>3.15</td><td>3.17</td><td>3.19</td><td>0.021</td><td>0.0019</td></tr><tr><td>CVAE＋PPO</td><td>3.21</td><td>3.19</td><td>3.21</td><td>0.012</td><td>0.0021</td></tr></tbody></table></div>


<a id="figure-supplement-seed-blocks"></a>

[图：逐个种子块展示配对确认差；各块内四种故障等权，编号表示登记身份。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-seed-blocks.svg)


<div class="table-wrap"><table data-table="supplement-policy-training" class="supplement-table"><thead><tr><th>策略</th><th>训练种子</th><th>回合</th><th>全局时间步</th><th>实际选择数</th><th>存在多个合法候选</th><th>有选择余地比例</th><th>执行＋更新分钟</th></tr></thead><tbody><tr><td>名义＋PPO</td><td>271</td><td>120</td><td>43080</td><td>170969</td><td>470</td><td>0.27%</td><td>2.57</td></tr><tr><td>CVAE＋PPO</td><td>271</td><td>120</td><td>43080</td><td>170956</td><td>437</td><td>0.26%</td><td>4.92</td></tr><tr><td>名义＋PPO</td><td>811</td><td>120</td><td>43080</td><td>170954</td><td>448</td><td>0.26%</td><td>2.39</td></tr><tr><td>CVAE＋PPO</td><td>811</td><td>120</td><td>43080</td><td>170961</td><td>460</td><td>0.27%</td><td>5.30</td></tr><tr><td>名义＋PPO</td><td>1931</td><td>120</td><td>43080</td><td>170957</td><td>466</td><td>0.27%</td><td>2.48</td></tr><tr><td>CVAE＋PPO</td><td>1931</td><td>120</td><td>43080</td><td>170950</td><td>453</td><td>0.26%</td><td>5.44</td></tr></tbody></table></div>

种子271／811／1931列为每主要条件平均确认段，SD是三个训练种子间的样本标准差；误差SD采用闭环加权RMSE。图中每个柱对应独立物理种子块的配对差，四故障条件等权。

PPO的选择数按执行者实际可选集合计；只有一个合法候选时，策略没有排序自由。训练耗时为完整回合执行、评分、留存和四次更新的累计墙钟时间，加载与预热另计。这一比例帮助解释当前返回保护与任务设定给学习留下多大的决策空间。

<h4 id="gap-diagnosis">附录 H. 估计—确认差异的逐事件核对</h4>

此处读取原留出日志，无新增环境、模型推理或训练。144组比较包含同一条件的三个模型重复，独立物理种子块仍为12。三个模型种子的“新增／丢失”分别为1／4、1／3、0／1，平均净差为−2段，与总表155→153一致。

<div class="table-wrap"><table data-table="estimation-confirmation-gap"><thead><tr><th>任务</th><th>原评价段</th><th>名义FIFO：提示→完成</th><th>CVAE-FIFO：提示→完成</th><th>确认变化</th></tr></thead><tbody><tr><td>41号热检查</td><td>855—885秒</td><td>865→895秒</td><td>835→880秒</td><td>CVAE新增</td></tr><tr><td>45号热检查</td><td>850—890秒</td><td>860→875秒</td><td>840→900秒</td><td>CVAE丢失</td></tr></tbody></table></div>

表取`test04-cooling`、模型种子271、同一执行者5。两条轨迹在860秒首次分叉：两项访问的资格、返回证书和预算都通过，CVAE-FIFO按835秒早于840秒的入队顺序选41号。41号的确认增加与45号的确认丢失在该回合相抵；其余净差来自案例02、06、07的局部提示与访问轨迹变化。此诊断解释本批记录，完整得失及首次分叉保存在[事后核对数据](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/source-data/estimation-confirmation-gap.json)。



<h3 id="sources">6.2 来源与原件索引</h3>

本轮共2204次环境尝试，覆盖兼容回放、观测采集、PPO训练／诊断与最终测试；另有3次估计器训练和18次纯物理规模运行。协议、追加式账本、模型身份与原件索引分别保存。

- [工程控制、规模与官方标准核查](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/report-engineering-alignment-20261103.md)。
- [RGB／IR视觉成果与接口核查](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/report-pid-interface-20261103.md)。
- [本任务横向指标、公式与只读复算](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/report-comparison-metrics-20261103.md)。
- [独立补充基准：完整方法](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/supplement-study-methods.md)、[新协议、模型参数及结果原件索引](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/evidence/supplement-study/README.md)。
- [补充研究设计依据](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/supplement-study-design-20261103.md)、[评价与缺失指标核查](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/supplement-metrics-audit-20261103.md)。
- [主机制验证与完整原件](https://github.com/DonsonHH/Zhinengti-RSI/blob/2db2adf146357ec35306503ed15183c0c4100d20/evidence/event-validation/final/README.md)、[九规则开发记录](https://github.com/DonsonHH/Zhinengti-RSI/blob/2db2adf146357ec35306503ed15183c0c4100d20/evidence/response-defer/README.md)。
- [名义估计与故障原件核查](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/report-method-formulas-20261103.md)、[规则动作诊断](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/report-rule-diagnosis-20261103.md)。
- [原论文指标核查](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/original-paper-metrics-20261103.md)、[模型方程与参数](https://github.com/DonsonHH/Zhinengti-RSI/blob/2db2adf146357ec35306503ed15183c0c4100d20/paper/model-appendix.md)、[机制讨论稿](https://github.com/DonsonHH/Zhinengti-RSI/blob/2db2adf146357ec35306503ed15183c0c4100d20/paper/manuscript_zh.md)。

单文件HTML内嵌图像、公式与表格，文本审阅包保留同源正文、数值表及图链接。原事件包、规则开发包与独立补充基准各自保存协议、数据和状态；完整方法与机器可读身份可由以上入口继续核对。
