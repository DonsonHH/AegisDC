> 正文审阅版：正文、公式和数值表与单文件HTML同源；图版保留SVG链接，便于文本工具读取。

# 大型液冷算力设施的多系统巡检研究

导师自阅报告 · 设施建模、态势估计、巡检决策与实验验证 · 2026-11-03

<a id="overview"></a>
## 0. 报告导读

### 0.1 核心进展摘要

<aside class="project-summary" aria-label="项目主线摘要"><strong>研究问题与运行过程</strong><p>在128柜模型中，巡检系统只能持续读取32柜的固定温度，其余96柜需要估计和到访测量，短时异常可能在两次检查之间漏过。系统先估计温度、生成风险待办，再安排加查，并确保后续例行检查不超时（热检查300秒，其他专业600秒）。48个故障条件中，名义FIFO将确认率从44.8%提高到73.8%（94/210→155/210段）；同一观测流下，CVAE将盲区机柜（非刚量测点）加权RMSE由0.443降至0.172°C，降低61.2%。</p></aside>

这里的盲区误差排除固定测温点和当前刚被巡检员测过的位置；加权RMSE按资产重要度计算温度误差，数值越小越准。后文分别比较温度估计是否准确、风险出现后能否及时完成专业核查。

本次已训练3个CVAE-U-Net和6个PPO，并在12个独立种子块上完成1080个留出测试回合。“12个独立种子块”即12组独立随机种子生成的故障测试集，每组包含多种故障与对照条件；同组条件在统计时一起处理。

### 0.2 导师关切点与章节映射

<div class="table-guide" id="table-chapter-map"><div class="exhibit-intro" data-guide-table="chapter-map"><p class="exhibit-title"><span class="exhibit-number">表 1</span> <strong>从导师关切定位到报告材料</strong></p><p class="exhibit-purpose">按自己想了解的问题选择阅读起点。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>每行按“关切→对应材料→阅读位置”横向阅读，最后一列可点击跳到章节。设施、视觉、规模、温度态势与横向比较分别对应不同证据。</p><p><strong>◇ 读到什么：</strong>这是一张导航表，帮助先建立全貌，再进入需要的模型或结果。</p></div></div>

|导师关心的内容|本报告对应材料|阅读位置|
|---|---|---|
|配电、液冷与设备自控|10 kV—380 V—54 V供电链、双回路CDU换热、三路反馈及国标对照状态|[第1章：设施物理层](#model)|
|RGB转红外与专业测温|已有B-PID电气显示样例、机房拟适配对象及合格接点观测通道|[2.1：配电视觉支路](#visual-branch)|
|大型设施复杂度|El Capitan工程参照、128柜状态与任务规模、512／1024柜扩展口径|[1.3：规模设置](#scale)、[4.5：规模实测](#scale-results)|
|全局态势与风险|名义估计、残差CVAE-U-Net、四专业风险生成及新测试态势示例|[第2章：感知方法](#hotspots)、[4.2：估计结果](#estimation-results)|
|原论文指标与横向比较|同信息同约束七方法、误差、确认、年龄、代价及机制诊断|[第3章：派单方法](#fifo)、[第4章：实验结果](#comparison)|

前3章依次定义设施、感知和决策方法；第4章统一展示新基准结果，第5章归纳结论与下一阶段工作。历史89段基准和500秒工程回看集中保留在[第6章附录](#appendix)，便于按需追溯。

### 0.3 图表与符号的读法

先读每幅图/表前的问题，按“怎么看”定位坐标、符号或关键列，再用“读到什么”连接到研究结论。正文与附录连续编号；同一符号的具体含义以该图说明为准。

<aside class="symbol-guide" id="reading-symbols" aria-label="图表常见符号"><dl><div><dt>↑ / ↓</dt><dd>评价方向：确认数↑表示越多越好；误差、等待和耗时↓表示越小越好。先看指标名称，再判断改善方向。</dd></div><div><dt>→ / ↺</dt><dd>架构图中沿箭头追踪信息、动作或热量；巡检流程中的回转箭头表示下一轮更新。每条线具体传递什么，以图内文字为准。</dd></div><div><dt>T / T̂ / ΔT̂</dt><dd>T是模拟设备温度，T̂是系统估计温度；帽子表示估计。ΔT̂是学习模型给名义估计的修正量，最终估计＝名义估计＋修正量。</dd></div><div><dt>Δ＝A−B</dt><dd>比较项按左边方法减右边方法计算。Δ&gt;0只表示数值增加；确认数增加是收益，等待或年龄增加则是代价。</dd></div><div><dt>点 / 柱 / 区间线</dt><dd>点的位置或柱长表示估计值；横竖短线表示该图注明的区间。95%区间、最小—最大实测范围和训练种子SD具有不同含义。</dd></div><div><dt>a [l,u] / NA</dt><dd>a为均值，[l,u]为表中注明的区间。NA表示指标在该条件下不适用；未留帧、未计时表示没有相应测量记录，都不能按0理解。</dd></div></dl></aside>

<a id="model"></a>
## 1. 设施物理层：三系统耦合建模

<p class="chapter-lead">先建立一个128柜的模拟机房，让供电、散热与自动调节之间的影响可以逐步计算。后续在模型中加入故障，观察异常怎样发生，再检验巡检能否及时发现。</p>

### 1.1 供电—液冷—自控耦合机理

#### 1.1.1 供配电拓扑与负载

模型按10 kV入口、380 V交流配电、UPS／整流和54 V直流机柜组织供电链。送达IT功率形成设备热负荷，辅助馈电可用性同时约束二次泵的有效速度，将电气异常与排热能力连接起来。

#### 1.1.2 一次与二次液冷回路

**CDU**为冷却液分配与换热单元。一次回路连接设施冷源，二次回路连接机柜冷板，两侧在CDU交换热量；每8柜构成一组，128柜对应16组。El Capitan／Cray EX官方资料提供了冷却塔、循环泵、冷板和测控层次的工程参照。[LLNL](https://www.llnl.gov/article/54496/meet-machines-matter-how-el-capitan-keeps-its-cool)、[HPE](https://www.hpe.com/us/en/collaterals/collateral.a00094635enw.html)。



<a id="figure-model"></a>

<div class="exhibit-intro" data-guide-figure="model"><p class="exhibit-title"><span class="exhibit-number">图 1</span> <strong>供电、液冷与自控怎样联动</strong></p><p class="exhibit-purpose">先看研究对象：一处供电异常为什么可能同时影响水泵和机柜温度。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/model.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>①沿上方供电链从10 kV入口读到54 V机柜，IT功率成为热源；②沿两条液体回路看冷板→CDU→冷却塔的排热路径；③沿下方回转箭头看温度如何改变泵、风机和限功率指令。CDU是两回路之间的换热单元。</p><p><strong>◇ 读到什么：</strong>辅助供电下降会约束泵的有效速度，继而改变流量和散热；这是后续故障过程与温度估计所依托的耦合模型。</p></div><p class="exhibit-source">本项目集中参数模型的供电、双回路液冷与局部控制计算关系。</p>



#### 1.1.3 跨系统动态关系

<div class="table-guide" id="table-physical-relations"><div class="exhibit-intro" data-guide-table="physical-relations"><p class="exhibit-title"><span class="exhibit-number">表 2</span> <strong>设施模型实际计算哪些关系</strong></p><p class="exhibit-purpose">把架构图中的设备方框对应到具体计算。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>每行是一段计算链：送达功率→发热，泵速→流量/压差，CDU→两侧换热，接触损耗→接点温升。左列说明计算对象，右列说明它怎样影响后续状态。</p><p><strong>◇ 读到什么：</strong>这些关系共同生成可随故障变化的温度、流量和接点状态，是后续估计与巡检的环境。</p></div></div>

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

<div class="table-guide" id="table-standards-mapping"><div class="exhibit-intro" data-guide-table="standards-mapping"><p class="exhibit-title"><span class="exhibit-number">表 3</span> <strong>两项液冷标准对应什么层级</strong></p><p class="exhibit-purpose">区分系统级参照、机柜级参照与当前已完成的核对范围。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>从标准名称看对象，再读发布/实施日期，最后读当前对照状态。“已定位元数据”和“正式条款待核读”分别表示资料入口与条文核查进度。</p><p><strong>◇ 读到什么：</strong>本表确定后续标准映射的对象；正文中的异常阈值仍按研究设置解释。</p></div></div>

|2026液冷国家标准|官方发布／实施信息|当前对照状态|
|---|---|---|
|[GB/T 48023-2026《数据中心冷板式液冷系统技术规范》](https://std.samr.gov.cn/gb/search/gbDetailed?id=581F4B90BB7B80E8E06397BE0A0AF9E7)|2026-07-30发布；2027-02-01实施|正式入口与元数据已定位；目录、控制条款及阈值待取得可核读文本|
|[GB/T 48097-2026《数据中心冷板式液冷机柜通用规范》](https://std.samr.gov.cn/gb/search/gbDetailed?id=5A13050B0299303FE06397BE0A0ADA7D)|2026-08-28发布；2027-03-01实施|按系统与机柜两层建立后续映射，正式条款待核读|

当前实现包括温度、流量与水力压差计算，以及上述温度反馈和模拟断载。下一步将正式要求对应到测量、方程、动作与验证工况，扩展压差反馈、防凝露、低流量联锁及多模式控制。33.6 kg/s等现有异常界值采用本研究设定。

<h3 id="scale">1.3 大型设施参照与模块化规模设置</h3>

#### 1.3.1 E级超算工程参照

以El Capitan的负载数量级作为参照。TOP500的2026年6月记录给出Rmax＝1.809 EFLOP/s、理论Rpeak＝2.82110 EFLOP/s、报告功率29.68462 MW（测量等级2）；E级指每秒10<sup>18</sup>次浮点运算的性能数量级。[TOP500原始记录](https://www.top500.org/system/180307/)。

<div class="table-guide" id="table-facility-scale"><div class="exhibit-intro" data-guide-table="facility-scale"><p class="exhibit-title"><span class="exhibit-number">表 4</span> <strong>工程参照与本模型规模如何区分</strong></p><p class="exhibit-purpose">给128柜模型的负荷和复杂度一个可理解的数量级。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>MW表示功率，EFLOP/s表示计算性能；同一表中要按“量名＋单位”读数。128/16是机柜/设备组，161/145是热状态/指令状态，176/18是任务/巡检员数量。</p><p><strong>◇ 读到什么：</strong>模型名义IT负荷为32 MW；与El Capitan的功率记录并列是工程数量级参照，算力性能另行列示。</p></div></div>

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

<p class="chapter-lead">机房模型建好后，巡检侧只能持续读取32柜的固定温度，其余96柜需要估计或到访测量补充。本章说明如何结合功率、冷却状态和历史量测补全温度图，再生成四专业的核查线索。</p>

<h3 id="visual-branch">2.1 配电巡检视觉支路</h3>

#### 2.1.1 既有RGB→伪彩IR显示样例

<strong>PID</strong>指Physics-Informed Diffusion图像生成工作，B-PID为本地视觉项目分支；RGB为可见光图像，IR为红外。已有材料包括以下户外电气样例，用于展示前期的显示图重建路径。[原PID方法](https://github.com/fangyuanmao/PID)。



<a id="figure-pid-visual-sample"></a>

<div class="exhibit-intro" data-guide-figure="pid-visual-sample"><p class="exhibit-title"><span class="exhibit-number">图 2</span> <strong>RGB输入、生成外观与目标显示怎样对照</strong></p><p class="exhibit-purpose">说明前期视觉工作的输入与输出，帮助理解图像支路能提供哪类信息。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/pid-visual-sample.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>从左向右比较同一位置：RGB可见光图→B-PID生成外观→目标伪彩显示。对照设备轮廓和亮暗/色块分布；三幅图是同一户外电气场景的精修显示样例，色彩按图像像素解释。</p><p><strong>◇ 读到什么：</strong>本组图展示外观重建路径；接点的℃数值来自下一图所示的合格测温通道，机房图像适配仍属于后续接入工作。</p></div><p class="exhibit-source">PID项目既有户外电气样例，同图精修、显示域；三张原图逐字节保留，数值计量按独立测温通道处理。</p>



户外绝缘子、铁塔与导线样例与机房配电具有电气设备外观感知这一共同接口。机房中的拟适配对象为10 kV／380 V开关柜、母排和54 V机柜交直流接点，后续经机房图像适配与校准测温接入后，开展热点复核和观测更新。

#### 2.1.2 图像参考与合格测温接口

本仿真系统已预留视觉参考元数据接口，可接收未校准图像参考；合格接点测温则用于更新接触温度。图像支路提供外观线索，℃数值由校准测温通道提供；RGB采集、生成推理、热点选点及真实仪器接入按下图逐步串接。



<a id="figure-visual-interface"></a>

<div class="exhibit-intro" data-guide-figure="visual-interface"><p class="exhibit-title"><span class="exhibit-number">图 3</span> <strong>图像线索怎样接到专业测温</strong></p><p class="exhibit-purpose">把“看图发现可疑位置”和“得到可用于确认的温度”放到同一流程中。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/visual-interface.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>上排沿RGB生成→参考登记→热点与任务关联阅读，虚线表示待连接的环节；下排实线表示已有合成测温→温度更新→风险与确认。T̂_contact←合格量测，意思是用检查得到的接点温度更新该组观测。</p><p><strong>◇ 读到什么：</strong>当前可运行的是合格接点量测的状态更新；图像推理、资产选点及真实仪器桥接按虚线接口继续接入。</p></div><p class="exhibit-source">已实现的参考元数据入口与合成接点测量分层表示；虚线标出RGB推理、选点及现场仪器桥接。</p>



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

CVAE-U-Net利用已测位置的温度及设备运行信息，学习修正物理公式的推算误差，从而补出其余机柜的温度。模型将最近四个连续5秒时刻的14维公开特征与当前名义温度拼成57通道输入，在8×16设备网格上估计温度残差。两个下采样层、空间跳接和16维条件潜变量组成295,777参数的CVAE-U-Net；运行时取条件先验均值，两类估计器均以当前时刻的新温度量测覆盖对应位置。



<a id="figure-supplement-unet"></a>

<div class="exhibit-intro" data-guide-figure="supplement-unet"><p class="exhibit-title"><span class="exhibit-number">图 4</span> <strong>CVAE-U-Net怎样补出未新测机柜的温度</strong></p><p class="exhibit-purpose">说明学习模型如何在物理估计上做修正，而不是直接把整张温度图当作已知输入。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-unet.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>从左到右看编码→瓶颈→解码，跨层连线把细节送回解码器；8×16×16表示网格高×宽×通道。x是公开历史，z是16维潜变量，μ是在线采用的条件先验均值；输出ΔT̂后计算T̂＝T̂_nominal＋ΔT̂，再用当前新测温度覆盖对应位置。</p><p><strong>◇ 读到什么：</strong>真实温度只进入训练监督和事后评价；在线预测由公开历史及先验分支完成，图中下方后验支路只在训练时使用。</p></div><p class="exhibit-source">本次真实训练的温度残差CVAE-U-Net。公开输入57通道，295,777个参数；训练后验只用于监督，在线取条件先验均值。</p>



条件先验／后验与空间编码—解码分别参考[条件生成模型](https://proceedings.neurips.cc/paper_files/paper/2015/file/8d55a249e6baa5c06772297520da2051-Paper.pdf)和[U-Net](https://arxiv.org/abs/1505.04597)。监督目标为离线物理温度，输入为公开遥测和专业量测历史；训练记录与误差见[4.1—4.2节](#estimation-results)。

### 2.3 多专业风险映射

#### 2.3.1 连续态势与事件入口

温度图描述全机房哪里更热，风险分把需要现场核查的位置转成待办任务。热风险同时考虑估计温度超标程度和供电功率缺口：

<div class="principle-box" id="principle-risk"><p class="principle-title">热风险的计算方法</p><div class="formula-scroll"><p class="formula" role="math">r<sub>i</sub> = min{4, max(T̂<sub>i</sub> − 65,0)/20 + 0.25[1 − P<sub>del,i</sub>/max(P<sub>req,i</sub>,10<sup>−12</sup>)]}</p></div><p>第一项为估计温度越界，第二项为功率需求缺口。风险分用于建立待确认请求，温度色阶用于连续态势呈现。</p></div>

#### 2.3.2 四专业风险通道

为了让四类巡检员知道哪里需要核查，系统分别汇总温度、接点发热、流量不足和传感偏差线索，计算各专业的风险分。

记h<sub>i</sub>＝max(T̂<sub>i</sub>−65,0)/20，g<sub>i</sub>为公开功率缺口。c<sub>p</sub>＝max(T̂<sub>contact,p</sub>−60,0)/30，接点温度由专业量测更新；f<sub>p</sub>＝max(1−q̂<sub>p</sub>/33.6,0)，q̂为最近已获组流量，可来自固定遥测或专业检查。

b<sub>p</sub>初值为0，仅在专业校验时按组平均传感误差绝对值是否>1°C更新为1或0，保持至下次校验。组内最大h与平均g把柜级信息映射到设备组，最终分数上限均为4。

<div class="table-guide" id="table-professional-risk"><div class="exhibit-intro" data-guide-table="professional-risk"><p class="exhibit-title"><span class="exhibit-number">表 5</span> <strong>同一机房信息怎样形成四类风险</strong></p><p class="exhibit-purpose">理解四个专业为什么不会只收到同一种温度报警。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>先看专业，再看风险组成和检查后更新的量。h为柜温超额，g为功率缺口，c为接点温度超额，f为流量缺口，b为最近专业校验的偏差标志；系数表示现有评分中的组合权重。</p><p><strong>◇ 读到什么：</strong>四类评分各有侧重，并在组内共享部分热/功率线索；风险上限为4，合格检查更新对应观测。</p></div></div>

|专业|现有公开风险组成|完成检查后更新|
|---|---|---|
|热检查|h<sub>i</sub>＋0.25g<sub>i</sub>|该柜温度|
|电气检查|c<sub>p</sub>＋组平均g＋0.1×组最大h|该组接点温度|
|制冷检查|f<sub>p</sub>＋0.25×组最大h|该组冷却液流量|
|自控检查|b<sub>p</sub>＋0.25×组最大h|该组传感偏差校验状态|

风险分是待核查严重度代理；有效异常确认以专业量测及离线评价标签核对。新留出过程的态势三联图与局部时序在[4.2.2节](#estimation-example)统一展示，旧500秒工程帧在[附录A](#engineering-history)保留。

<a id="fifo"></a>
## 3. 巡检决策层：受返回时间保护的多专业派单

<p class="chapter-lead">有了风险线索，接下来要决定派谁去、先查哪里。18名巡检员在各自专业与责任区内完成核查，每次加查前都要算清能否及时返回例行路线，保证原有检查不超时。</p>

### 3.1 闭环架构与执行契约

#### 3.1.1 四专业契约与两本任务账

每个模拟回合持续1800秒，共18名巡检员。12名测机柜温度，电气、制冷和自控各2名，分别检查接点温度、组流量和传感偏差。“重访期限”是同一任务相邻两次检查允许的最长间隔，热检查为300秒，其他专业为600秒；具体分工与服务耗时如下。系统分别保存例行检查进度和风险待办，避免加查打乱原有责任。

<div class="table-guide" id="table-task-contract"><div class="exhibit-intro" data-guide-table="task-contract"><p class="exhibit-title"><span class="exhibit-number">表 6</span> <strong>谁检查什么、一次多久、多久必须再查</strong></p><p class="exhibit-purpose">把18名巡检员的专业分工和时间规则放在一起。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>按一行读“专业→测到什么→人数→服务时间→最大检查间隔”。12＋2＋2＋2＝18人；10秒等服务时间是现场检查耗时，300/600秒是同一任务允许的最长重访间隔，移动时间另算。</p><p><strong>◇ 读到什么：</strong>派单先满足专业资格，再核算移动、服务和重访期限；一个人会路过某设备，并不等于具备完成该专业检查的资格。</p></div></div>
<div class="table-wrap"><table data-table="task-contract"><thead><tr><th>专业</th><th>完成检查后得到什么</th><th>人数</th><th>每次服务</th><th>最大重访间隔</th></tr></thead><tbody><tr><td>热检查</td><td>该机柜代表温度</td><td>12</td><td>10秒</td><td>300秒</td></tr><tr><td>电气检查</td><td>该组电气接触温度</td><td>2</td><td>20秒</td><td>600秒</td></tr><tr><td>制冷检查</td><td>该组冷却液流量</td><td>2</td><td>20秒</td><td>600秒</td></tr><tr><td>自控检查</td><td>传感读数误差（完成校验后）</td><td>2</td><td>15秒</td><td>600秒</td></tr></tbody></table></div>


<a id="figure-inspection-architecture"></a>

<div class="exhibit-intro" data-guide-figure="inspection-architecture"><p class="exhibit-title"><span class="exhibit-number">图 5</span> <strong>从观测到核查完成的一轮闭环</strong></p><p class="exhibit-purpose">把前两章的温度信息与本章的派单、执行和结果评价连接起来。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/inspection-architecture.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>上排顺着观测→风险待办→可行性与FIFO→移动/服务/测量阅读，回转线表示新量测进入下一轮。“两本任务账”分别记录例行进度和风险待办；下排读取真实异常与执行日志，计算确认、等待和约束结果。</p><p><strong>◇ 读到什么：</strong>风险提示决定去哪里核查，专业测量完成后才更新确认结果；设备自身的温控仍沿设施模型的控制回路运行。</p></div><p class="exhibit-source">根据本项目已实现接口重绘总体架构；上方在线决策只用公开信息，下方真值与日志用于事后评分。</p>



风险请求等待派单的有效期为120秒，全体额外访问上限12次。加查保留原例行任务的执行顺序；派出时占用访问额度并预约目标，检查完成后以专业量测更新温度或流量等观测，并记录结果。

#### 3.1.2 完整循环返回证书

能否加查，先看回来后还赶不赶得上例行任务。程序预测加查及原路线所有后续任务的完成时刻，逐项核对期限，并检查重复巡回是否仍可持续；这份核算结果称为“返回证书”。

<div class="principle-box" id="principle-return"><p class="principle-title">完整返回核算</p><div class="formula-scroll"><p class="formula" role="math">t + τ(p,x) + τ(x,r) ≤ L<sub>r</sub> + D<sub>r</sub>；τ(a,b) = 5⌈[d(a,b)/v + s<sub>b</sub>]/5⌉</p><p class="formula" role="math">对完整循环：F<sub>j</sub> ≤ L′<sub>j</sub> + D<sub>j</sub>；最小余量≥0</p></div><p>此简式取额外加查x与原任务r不同。τ包括目的任务服务，v＝1 m/s；首次未检的L按0起算，L′随预计访问更新。程序核查候选自身、完整循环及重复周期；每次实际完成后重新选择。</p></div>

### 3.2 共同合法候选集合下的策略族

#### 3.2.1 固定Tour与先入先出FIFO

Tour按原定路线循环检查。FIFO（First In, First Out，先入先出）在巡检员空闲时，从“原定下一项例行任务＋本人风险待办”中筛出当前允许执行的任务，优先处理最早出现的风险请求；没有可执行的风险请求时，继续原定下一项例行任务。所有响应方法共用资格、预约、返回、回合结束前完成检查的限制与访问额度检查。

#### 3.2.2 即时Greedy与响应／暂缓规则

Greedy优先处理风险高、预计完成时间短的任务，具体比较“当前公开风险／取整完成耗时”，平分时依次优先例行项、较早提示和较小任务编号。响应／暂缓线性规则则先由FIFO选定一个合法事件，再在该事件与原定下一项例行任务之间二选一；规则表达式与历史开发结果见[附录C](#historical-benchmark)。

#### 3.2.3 共享PPO策略

PPO尝试从训练中学会：当几项任务都允许执行时，先查哪一项。选择网络（actor）读取21维公开候选特征，使用32×32共享网络；训练时另用10维公开全局特征的评价网络（critic）。特征包括专业、风险、距上次检查的时间、预计完成检查的耗时、量测状态、等待时间、访问额度和返回余量，巡检员按固定编号依次决策。



<a id="figure-supplement-crossed-design"></a>

<div class="exhibit-intro" data-guide-figure="supplement-crossed-design"><p class="exhibit-title"><span class="exhibit-number">图 6</span> <strong>七种方案怎样进行同条件比较</strong></p><p class="exhibit-purpose">看清改变的是温度估计还是选任务的方法，以及各方案共同遵守什么规则。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-crossed-design.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>左端选择名义或CVAE估计，中部共用候选生成与资格/返回/预算筛选，之后由FIFO、Greedy或PPO选择。2种估计×3种派单，再加固定Tour，共7种方案；下方critic是训练用评价网络，在线选择使用上方actor。</p><p><strong>◇ 读到什么：</strong>选任务的方法变化时，执行资格和时间保护保持一致；专业确认仍由实际完成的量测核对，便于分别观察估计和派单的作用。</p></div><p class="exhibit-source">估计器与调度器的共同候选、约束和执行接口。PPO使用公开奖励训练，原始异常标签留给离线评价。</p>



训练采用公开观测奖励的[PPO裁剪目标](https://arxiv.org/abs/1707.06347)：每个完整359步回合更新4轮，学习率0.0003，γ＝0.99、GAE λ＝0.95、clip＝0.2。名义／CVAE条件下的配对种子采用相同初始参数和案例次序，各策略固定使用第120回合checkpoint。

### 3.3 观测、物理过程与评价边界

同一故障条件下，各方法面对相同的供电、温度与流量变化，设备由本地控制器调节。巡检决定走哪条路线、何时测量和怎样更新估计；本轮巡检动作是核查，设备仍按共同的本地控制过程运行。派单只使用当时已经收到的信息，完整故障过程留到回合结束后评分；同时逐项核对实际分配、完成和检查间隔。

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

前期12个耦合过程共有89段异常，Tour／FIFO确认28/89与70/89；九条线性规则最高60/89。这一阶段用于建立机制基准，完整图、故障配置与负结果在[附录C—E](#historical-benchmark)保留。以下主比较使用独立新基准的210段异常，两批结果分别记账。

#### 4.3.2 新基准总表、四专业与配对效应

<div class="table-guide" id="table-supplement-errors"><div class="exhibit-intro" data-guide-table="supplement-errors"><p class="exhibit-title"><span class="exhibit-number">表 11</span> <strong>各方案按自身巡检记录得到的温度误差</strong></p><p class="exhibit-purpose">查看完整系统运行后，路线、量测时机和估计器共同形成的状态精度。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>每行是一个估计＋派单组合；↑/↓沿用指标方向，最后一列说明确定性规则或3个模型种子重复。各行使用该方案自己完成的量测流，输入会随路线变化。</p><p><strong>◇ 读到什么：</strong>本表评价闭环系统的温度结果；前一张共同观测流表用于单独比较估计器，两种比较相互补充。</p></div></div>
<div class="table-wrap"><table data-table="supplement-errors" class="supplement-table"><thead><tr><th>方法</th><th>RMSE / °C↓</th><th>加权RMSE / °C↓</th><th>R²↑</th><th>盲区机柜加权RMSE / °C↓</th><th>模型／规则重复</th></tr></thead><tbody><tr data-supplement-method="nominal_tour"><td>名义＋Tour</td><td>0.528</td><td>0.535</td><td>0.9124</td><td>0.443</td><td>1个确定性规则</td></tr><tr data-supplement-method="nominal_fifo"><td>名义＋FIFO</td><td>0.532</td><td>0.535</td><td>0.9113</td><td>0.443</td><td>1个确定性规则</td></tr><tr data-supplement-method="nominal_greedy"><td>名义＋Greedy</td><td>0.533</td><td>0.537</td><td>0.9105</td><td>0.446</td><td>1个确定性规则</td></tr><tr data-supplement-method="nominal_ppo"><td>名义＋PPO</td><td>0.531</td><td>0.537</td><td>0.9112</td><td>0.445</td><td>3个独立训练种子</td></tr><tr data-supplement-method="cvae_fifo"><td>CVAE＋FIFO</td><td>0.323</td><td>0.327</td><td>0.9603</td><td>0.170</td><td>3个独立训练种子</td></tr><tr data-supplement-method="cvae_greedy"><td>CVAE＋Greedy</td><td>0.323</td><td>0.327</td><td>0.9602</td><td>0.171</td><td>3个独立训练种子</td></tr><tr data-supplement-method="cvae_ppo"><td>CVAE＋PPO</td><td>0.323</td><td>0.327</td><td>0.9602</td><td>0.171</td><td>3个独立训练种子</td></tr></tbody></table></div>
<div class="table-guide" id="table-supplement-tasks"><div class="exhibit-intro" data-guide-table="supplement-tasks"><p class="exhibit-title"><span class="exhibit-number">表 12</span> <strong>七方案究竟查到多少、付出多少代价</strong></p><p class="exhibit-purpose">用一张总表核对异常确认、例行覆盖与额外成本。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>确认a/210以唯一异常段为分母；每条件确认及区间以48个故障条件和12个独立测试组汇总。学习方案的小数来自模型种子平均。移动/完成量以Tour为基准，+表示增加、−表示减少；等待和年龄都取↓。</p><p><strong>◇ 读到什么：</strong>名义FIFO确认155/210，相比Tour的94/210更多，同时移动＋0.34%、完成量−0.15%、年龄略升；约束违规均为0。</p></div></div>
<div class="table-wrap"><table data-table="supplement-tasks" class="supplement-table"><thead><tr><th>方法</th><th>确认／唯一异常段</th><th>确认比例</th><th>每条件确认 [95%CI]</th><th>截尾等待 / 秒↓</th><th>加权年龄↓</th><th>移动相对Tour</th><th>完成量相对Tour</th><th>约束违规</th></tr></thead><tbody><tr data-supplement-method="nominal_tour"><td>名义＋Tour</td><td>94/210</td><td>44.8%</td><td>1.96 [1.31, 2.65]</td><td>106.75</td><td>0.310122</td><td>+0.00%</td><td>+0.00%</td><td>0</td></tr><tr data-supplement-method="nominal_fifo"><td>名义＋FIFO</td><td>155/210</td><td>73.8%</td><td>3.23 [2.83, 3.65]</td><td>94.24</td><td>0.311298</td><td>+0.34%</td><td>-0.15%</td><td>0</td></tr><tr data-supplement-method="nominal_greedy"><td>名义＋Greedy</td><td>154/210</td><td>73.3%</td><td>3.21 [2.81, 3.60]</td><td>94.36</td><td>0.311270</td><td>+0.34%</td><td>-0.15%</td><td>0</td></tr><tr data-supplement-method="nominal_ppo"><td>名义＋PPO</td><td>129.33/210</td><td>61.6%</td><td>2.69 [2.23, 3.17]</td><td>100.42</td><td>0.310877</td><td>+0.22%</td><td>-0.10%</td><td>0</td></tr><tr data-supplement-method="cvae_fifo"><td>CVAE＋FIFO</td><td>153/210</td><td>72.9%</td><td>3.19 [2.78, 3.61]</td><td>94.55</td><td>0.311256</td><td>+0.33%</td><td>-0.14%</td><td>0</td></tr><tr data-supplement-method="cvae_greedy"><td>CVAE＋Greedy</td><td>152/210</td><td>72.4%</td><td>3.17 [2.76, 3.58]</td><td>94.64</td><td>0.311217</td><td>+0.32%</td><td>-0.14%</td><td>0</td></tr><tr data-supplement-method="cvae_ppo"><td>CVAE＋PPO</td><td>153.67/210</td><td>73.2%</td><td>3.20 [2.78, 3.62]</td><td>94.65</td><td>0.311266</td><td>+0.33%</td><td>-0.14%</td><td>0</td></tr></tbody></table></div>


<a id="figure-supplement-methods"></a>

<div class="exhibit-intro" data-guide-figure="supplement-methods"><p class="exhibit-title"><span class="exhibit-number">图 12</span> <strong>七种方案在确认、等待和例行覆盖上的取舍</strong></p><p class="exhibit-purpose">同时查看“多查到异常”和“是否耽误例行检查”，避免用单个指标代替全部任务效果。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-methods.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>每行是一种方案，三列分别为每故障条件确认段数↑、后果加权截尾等待秒数↓、加权归一年龄↓。横向比较同一列，区间线表示95%测试组自举区间；三列单位不同，不能直接比较柱长。年龄越高表示例行检查平均更久未更新。</p><p><strong>◇ 读到什么：</strong>名义FIFO比Tour确认更多、等待更短，同时年龄略有上升；这张图把收益和例行覆盖的代价放在一起。</p></div><p class="exhibit-source">48个故障条件，先平均三个模型种子、再等权四故障族；误差线按12组独立测试集计算95%区间。等待对有异常的条件计算。</p>




<a id="figure-supplement-professions"></a>

<div class="exhibit-intro" data-guide-figure="supplement-professions"><p class="exhibit-title"><span class="exhibit-number">图 13</span> <strong>确认收益主要来自哪个专业</strong></p><p class="exhibit-purpose">把总确认数拆开，查看热、电气、制冷和自控是否得到相同改善。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-professions.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>四幅图使用相同百分比横轴，但专业分母依次是162、12、24、12段。行内a/b表示确认段数/该专业异常总段数，柱越长表示确认比例越高；学习方法的小数来自三个模型种子的平均。</p><p><strong>◇ 读到什么：</strong>方法差异主要出现在热检查和制冷；电气均为12/12，自控均为8/12。先看分母，再判断某专业的百分比与总量贡献。</p></div><p class="exhibit-source">四专业异常段的描述性确认比例，数字为确认数／专业异常总数；小数来自三个模型种子的平均。</p>



48个主要条件共210段唯一异常。学习方法确认总数的小数来自三个模型种子的平均；闭环误差使用各方法自身的量测流，同流估计结果则使用4.2节的共同输入。

名义FIFO相对Tour新增61段有效确认，截尾等待从106.75缩短至94.24秒，移动增加0.34%、完成量下降0.15%；整体加权年龄从0.310122升至0.311298。各方法资格、预约、预算和初终点重访审计均为0违规。

三个模型种子平均后，CVAE-FIFO、CVAE-Greedy和CVAE-PPO分别确认153、152和153.67段，均未超过名义FIFO的155段。方法差异集中在热检查与制冷；电气均为12/12，自控均为8/12；在当前观测与专业完成时机设置下，这两类结果在方法间一致。



<a id="figure-supplement-contrasts"></a>

<div class="exhibit-intro" data-guide-figure="supplement-contrasts"><p class="exhibit-title"><span class="exhibit-number">图 14</span> <strong>把方案差异直接画成A−B</strong></p><p class="exhibit-purpose">判断收益方向和不确定性，而不是只凭两个方案各自的均值猜测差异。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-contrasts.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>每行按名称计算Δ＝前者−后者，竖直0线表示无数值差。左图确认增量↑，点在右侧为更多确认；右图年龄变化↓，点在左侧为更及时的例行覆盖。横线是对应配对差的95%区间，跨0表示本批数据仍容许两种方向。</p><p><strong>◇ 读到什么：</strong>名义FIFO相对Tour有明确的确认增量；CVAE-PPO相对CVAE-FIFO的确认区间跨0。CVAE-PPO与名义PPO之差同时包含估计器和各自策略训练的变化。</p></div><p class="exhibit-source">预登记的配对比较，按独立测试集自举计算95%区间。确认、等待、年龄与误差分别解释；区间不包含完整训练不确定性。</p>


<div class="table-guide" id="table-supplement-contrasts"><div class="exhibit-intro" data-guide-table="supplement-contrasts"><p class="exhibit-title"><span class="exhibit-number">表 13</span> <strong>预先选定的方案差有多大</strong></p><p class="exhibit-purpose">直接阅读同条件配对后的增量及其方向。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>每行按Δ＝前者−后者计算；例如＋1.27段/条件表示前者平均多确认1.27段。方括号为对应差值的95%区间，确认看↑，等待/年龄/误差看↓；带符号的数不能只按正负判断好坏。</p><p><strong>◇ 读到什么：</strong>名义FIFO的确认增量区间在0以上；CVAE-PPO相对CVAE-FIFO的区间跨0，因此这批结果尚未明确给出学习派单增量。</p></div></div>
<div class="table-wrap"><table data-table="supplement-contrasts" class="supplement-table"><thead><tr><th>预登记比较</th><th>每条件确认差↑</th><th>截尾等待差 / 秒↓</th><th>归一年龄差↓</th><th>闭环加权RMSE差 / °C↓</th></tr></thead><tbody><tr><td>名义＋FIFO − 名义＋Tour</td><td>+1.27 [+0.62, +1.88]</td><td>-12.51 [-16.31, -8.75]</td><td>+0.001176 [+0.001052, +0.001292]</td><td>+0.001 [-0.053, +0.052]</td></tr><tr><td>CVAE＋FIFO − 名义＋FIFO</td><td>-0.04 [-0.09, +0.00]</td><td>+0.31 [+0.02, +0.70]</td><td>-0.000042 [-0.000072, -0.000015]</td><td>-0.208 [-0.311, -0.111]</td></tr><tr><td>CVAE＋Greedy − 名义＋Greedy</td><td>-0.04 [-0.09, +0.00]</td><td>+0.28 [+0.00, +0.67]</td><td>-0.000053 [-0.000093, -0.000021]</td><td>-0.210 [-0.314, -0.112]</td></tr><tr><td>名义＋PPO − 名义＋FIFO</td><td>-0.53 [-0.79, -0.26]</td><td>+6.18 [+4.23, +8.19]</td><td>-0.000421 [-0.000475, -0.000362]</td><td>+0.002 [-0.015, +0.018]</td></tr><tr><td>CVAE＋PPO − CVAE＋FIFO</td><td>+0.01 [-0.01, +0.04]</td><td>+0.10 [-0.15, +0.39]</td><td>+0.000010 [-0.000005, +0.000028]</td><td>+0.000 [-0.000, +0.000]</td></tr><tr><td>CVAE＋PPO − 名义＋PPO</td><td>+0.51 [+0.22, +0.78]</td><td>-5.77 [-7.59, -4.01]</td><td>+0.000389 [+0.000320, +0.000454]</td><td>-0.210 [-0.310, -0.115]</td></tr></tbody></table></div>

名义FIFO−Tour每主要条件净增+1.27 [+0.62, +1.88]段；CVAE-FIFO−名义FIFO为-0.04 [-0.09, +0.00]段；CVAE-PPO−CVAE-FIFO为+0.01 [-0.01, +0.04]段。区间表达物理种子块变化，[附录G](#training-seeds)另列训练种子离散程度。

#### 4.3.3 健康、虚假提示与计算耗时

<div class="table-guide" id="table-supplement-healthy"><div class="exhibit-intro" data-guide-table="supplement-healthy"><p class="exhibit-title"><span class="exhibit-number">表 14</span> <strong>正常运行或虚假提示会带来多少额外工作</strong></p><p class="exhibit-purpose">检查系统会不会在没有评价异常时增加访问或产生错误确认。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>每个数是对应12个条件的平均；分别比较健康与虚假提示的额外访问、误确认。NA表示该组没有异常段，确认比例和异常等待不适用。额外访问与误确认是两列不同的结果。</p><p><strong>◇ 读到什么：</strong>健康组均无额外访问和误确认；虚假提示使部分方案平均多访问0.75次/条件，但专业误确认为0。</p></div></div>
<div class="table-wrap"><table data-table="supplement-healthy" class="supplement-table"><thead><tr><th>方法</th><th>健康额外访问</th><th>虚假提示额外访问</th><th>健康误确认</th><th>虚假提示误确认</th><th>虚假提示完成量相对Tour</th><th>两组确认比例／等待</th></tr></thead><tbody><tr><td>名义＋Tour</td><td>0.00</td><td>0.00</td><td>0.00</td><td>0.00</td><td>+0.00%</td><td>NA / NA</td></tr><tr><td>名义＋FIFO</td><td>0.00</td><td>0.75</td><td>0.00</td><td>0.00</td><td>-0.04%</td><td>NA / NA</td></tr><tr><td>名义＋Greedy</td><td>0.00</td><td>0.75</td><td>0.00</td><td>0.00</td><td>-0.04%</td><td>NA / NA</td></tr><tr><td>名义＋PPO</td><td>0.00</td><td>0.42</td><td>0.00</td><td>0.00</td><td>-0.02%</td><td>NA / NA</td></tr><tr><td>CVAE＋FIFO</td><td>0.00</td><td>0.75</td><td>0.00</td><td>0.00</td><td>-0.04%</td><td>NA / NA</td></tr><tr><td>CVAE＋Greedy</td><td>0.00</td><td>0.75</td><td>0.00</td><td>0.00</td><td>-0.04%</td><td>NA / NA</td></tr><tr><td>CVAE＋PPO</td><td>0.00</td><td>0.75</td><td>0.00</td><td>0.00</td><td>-0.04%</td><td>NA / NA</td></tr></tbody></table></div>

健康与虚假提示各12条件。无评价异常时确认比例与异常等待为NA，额外访问及误确认按实测保留。所有方法在健康组均无额外访问和误确认。虚假提示下，FIFO、Greedy及CVAE-PPO平均各增加0.75次访问／条件，名义PPO为0.42次；这些跟进没有造成错误的专业确认。



<a id="figure-supplement-latency"></a>

<div class="exhibit-intro" data-guide-figure="supplement-latency"><p class="exhibit-title"><span class="exhibit-number">图 15</span> <strong>估计和派单各花多少计算时间</strong></p><p class="exhibit-purpose">比较引入神经估计或PPO后，单轮计算的主要代价来自哪一阶段。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-latency.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>左图为温度估计阶段，右图为候选准备与派单阶段，横轴都为毫秒ms、方向↓；两幅图刻度不同。数值先在每回合求p95，再对主要条件汇总取平均，因此读作“逐回合p95的平均”。</p><p><strong>◇ 读到什么：</strong>CVAE主要增加估计计算，PPO主要增加派单计算。完整周期还包含执行记账与下一观测等操作，估计已经包含其中，应结合耗时表阅读。</p></div><p class="exhibit-source">主要故障条件的逐回合p95均值，实测包含转换和CUDA同步。估计阶段已包含于完整控制周期，不能重复相加。</p>


<div class="table-guide" id="table-supplement-latency"><div class="exhibit-intro" data-guide-table="supplement-latency"><p class="exhibit-title"><span class="exhibit-number">表 15</span> <strong>单轮估计、派单和完整周期的实测耗时</strong></p><p class="exhibit-purpose">把阶段计算代价与完整一轮的时间放在同一张表中。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>单位为毫秒ms，p50为中位数，p95为95百分位；先逐回合计算，再汇总取平均。完整周期包含估计阶段，并由完整周期记录单独求分位数，阶段p95不可直接相加。</p><p><strong>◇ 读到什么：</strong>名义FIFO完整周期p95均值为1.47 ms，CVAE-PPO为8.10 ms；这是本次硬件与测量边界内的统计值。</p></div></div>
<div class="table-wrap"><table data-table="supplement-latency" class="supplement-table"><thead><tr><th>方法</th><th>估计p50 / ms</th><th>估计p95 / ms</th><th>派单p50 / ms</th><th>派单p95 / ms</th><th>完整周期p95 / ms</th></tr></thead><tbody><tr><td>名义＋Tour</td><td>0.17</td><td>0.23</td><td>0.45</td><td>0.90</td><td>1.53</td></tr><tr><td>名义＋FIFO</td><td>0.17</td><td>0.22</td><td>0.44</td><td>0.86</td><td>1.47</td></tr><tr><td>名义＋Greedy</td><td>0.17</td><td>0.22</td><td>0.44</td><td>0.87</td><td>1.48</td></tr><tr><td>名义＋PPO</td><td>0.18</td><td>0.24</td><td>1.28</td><td>2.95</td><td>3.59</td></tr><tr><td>CVAE＋FIFO</td><td>3.69</td><td>5.44</td><td>0.47</td><td>0.93</td><td>6.59</td></tr><tr><td>CVAE＋Greedy</td><td>3.53</td><td>5.07</td><td>0.48</td><td>0.95</td><td>6.27</td></tr><tr><td>CVAE＋PPO</td><td>3.63</td><td>5.34</td><td>1.31</td><td>3.00</td><td>8.10</td></tr></tbody></table></div>

硬件为NVIDIA GeForce RTX 4060 Laptop GPU，PyTorch 2.6.0＋CUDA 12.4、PyTorch CPU线程数2。上表是主要条件逐回合p50／p95的平均；神经估计包括转换、设备复制、前向、取回及CUDA同步，每次加载先做5次预热。完整周期包含选择、执行记账、下一观测估计和事件生命周期；物理轨迹预生成、记录、I/O与评分另计，估计阶段已包含于完整周期。

### 4.4 估计精度、队列时序与学习空间诊断

#### 4.4.1 连续重构误差与离散确认机会

CVAE-U-Net改善全局温度态势精度，及时确认还取决于局部提示、FIFO队列和合法访问的完成时机。原日志144组配对中，CVAE-FIFO新增2段、丢失8段，模型平均后净少2段，与155→153一致。

在`test04-cooling`、模型271中，CVAE将45号提示从860秒提前至840秒，但41号更早在835秒入队。860秒两候选均合法，CVAE-FIFO先查41号并在880秒确认，再于900秒检查45号，错过850—890秒评价段；名义FIFO在875秒确认45号、895秒才检查41号。这里出现一增一失的机会交换，完整时序见[附录H](#gap-diagnosis)。

#### 4.4.2 合法候选稀疏与PPO排序自由度

PPO只有在几项任务都允许执行时，才有机会体现先后排序的差别。训练记录中，约0.26%—0.27%的巡检员实际选择集合包含多个合法候选；只有一项可选时，策略没有排序空间。这个比例按每名执行者实际收到的选择集合计算，反映本轮责任区、返回保护和待办生成共同形成的机会，完整计数见[附录G](#training-seeds)。

在每策略120回合预算下，CVAE-PPO相对CVAE-FIFO的确认增量区间跨零；相对名义PPO的改善同时包含估计器与各自训练策略的变化。候选空间、奖励和训练预算的单独贡献可在下一轮独立比较中检验。

<h3 id="scale-results">4.5 模块化物理规模与数值一致性</h3>



<a id="figure-supplement-scale"></a>

<div class="exhibit-intro" data-guide-figure="supplement-scale"><p class="exhibit-title"><span class="exhibit-number">图 16</span> <strong>机柜增多后，纯物理计算与内存怎样变化</strong></p><p class="exhibit-purpose">核对模型扩展到512和1024柜时的资源开销。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-scale.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>横轴是机柜数。左图纵轴为360个物理步的运行秒数，柱高为中位数，范围线为六次实测最小—最大值；右图为Python追踪峰值MiB，取该规模六次运行中的最大值。范围线不是95%置信区间。</p><p><strong>◇ 读到什么：</strong>这批物理运行耗时未呈单调上升，追踪内存随规模增加；它验证物理过程与静态巡回的扩展，端到端学习调度仍对应128柜。</p></div><p class="exhibit-source">每规模三种子×健康／耦合两工况的纯物理过程实测；带tracemalloc开销，范围为六次实测最小—最大，未作大规模学习调度。</p>


<div class="table-guide" id="table-supplement-scale"><div class="exhibit-intro" data-guide-table="supplement-scale"><p class="exhibit-title"><span class="exhibit-number">表 16</span> <strong>三种机柜规模的模型量与资源开销</strong></p><p class="exhibit-purpose">同时查看问题规模变大多少，以及物理计算用了多少时间和内存。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>各行按128→512→1024柜比较；斜杠两侧是表头指定的两种数量，例如热状态/指令状态。耗时是每规模六次纯物理运行的中位数，峰值内存以MiB计；静态检查列核对构造的循环路线。</p><p><strong>◇ 读到什么：</strong>状态、人员与任务数随规模扩展，追踪内存上升；本表资源数值对应物理过程，学习调度成绩仍来自128柜基准。</p></div></div>
<div class="table-wrap"><table data-table="supplement-scale" class="supplement-table"><thead><tr><th>机柜数</th><th>热状态／指令状态</th><th>执行者／专业任务</th><th>物理耗时中位数 / 秒</th><th>Python峰值 / MiB</th><th>静态检查</th></tr></thead><tbody><tr><td>128</td><td>161／145</td><td>18／176</td><td>0.517</td><td>0.50</td><td>构造闭合巡回满足</td></tr><tr><td>512</td><td>641／577</td><td>72／704</td><td>0.483</td><td>1.70</td><td>构造闭合巡回满足</td></tr><tr><td>1024</td><td>1281／1153</td><td>144／1408</td><td>0.500</td><td>3.32</td><td>构造闭合巡回满足</td></tr></tbody></table></div>
<div class="table-guide" id="table-supplement-scale-cycles"><div class="exhibit-intro" data-guide-table="supplement-scale-cycles"><p class="exhibit-title"><span class="exhibit-number">表 17</span> <strong>规模扩展后的例行路线能否按时走完</strong></p><p class="exhibit-purpose">核对增加机柜后，各专业是否配有满足重访期限的构造巡回。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>每格“人数；周期/期限”先看人员配置，再读该专业所有已构造人员路线中的最长闭合巡回周期。例如240/300秒表示最长一轮240秒、允许间隔300秒；最长周期≤期限表示该专业的构造路线通过静态时间核查。</p><p><strong>◇ 读到什么：</strong>三种规模的已构造路线均满足对应专业期限；这给出了可行的例行底座。</p></div></div>
<div class="table-wrap"><table data-table="supplement-scale-cycles" class="supplement-table"><thead><tr><th>机柜数</th><th>热检查：人数；周期／期限</th><th>电气：人数；周期／期限</th><th>制冷：人数；周期／期限</th><th>自控：人数；周期／期限</th></tr></thead><tbody><tr><td>128</td><td>12人；240/300秒</td><td>2人；310/600秒</td><td>2人；310/600秒</td><td>2人；270/600秒</td></tr><tr><td>512</td><td>48人；240/300秒</td><td>8人；385/600秒</td><td>8人；385/600秒</td><td>8人；345/600秒</td></tr><tr><td>1024</td><td>96人；240/300秒</td><td>16人；465/600秒</td><td>16人；465/600秒</td><td>16人；425/600秒</td></tr></tbody></table></div>

每规模为三种子×健康／耦合两条件，360个5秒物理步。耗时含tracemalloc开销，内存范围为该物理段及温度序列留存；静态检查评价已构造的专业巡回。三规模的构造闭合巡回均满足各专业期限。360步物理耗时中位数约0.48—0.52秒，未随柜数呈单调上升；Python追踪峰值由0.50增至3.32 MiB，范围为该物理段及温度序列的留存。

18次运行的最大能量平衡残差为7.97e-08 kJ，最大电功率平衡残差为8.73e-11 kW，用于核对数值守恒一致性。512／1024柜验证覆盖物理过程与静态巡回，学习闭环结果对应128柜。

<a id="roadmap"></a>
## 5. 阶段结论与下一阶段工作

<p class="chapter-lead">实验分别回答了“温度能否估得更准”和“异常能否查得更多”。本章据此保留有证据支持的方法，再把下一阶段需要检验的问题列成具体工作。</p>

### 5.1 研究结论

设施层已形成供电—液冷—自控耦合过程，感知层实现名义／残差CVAE估计，决策层把专业事件确认与持续重访放入共同执行边界。独立留出比较显示，CVAE降低了温度误差，名义FIFO以155/210取得本批最高的模型平均确认量；更多确认伴随约0.34%的移动增量和整体年龄的小幅上升。

CVAE-PPO较名义PPO每主要条件平均增加0.507段，相对同估计器FIFO仅增加0.014段且区间跨零。当前可将名义FIFO保留为任务基准、CVAE保留为状态估计支路，再以未确认段与候选稀疏记录确定下一项研究假设。

### 5.2 后续四项工作包

<div class="table-guide" id="table-future-work"><div class="exhibit-intro" data-guide-table="future-work"><p class="exhibit-title"><span class="exhibit-number">表 18</span> <strong>下一步具体做什么、如何判断完成</strong></p><p class="exhibit-purpose">把结论对应到后续可检查的工作，而不是泛泛增加模型复杂度。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>每行按“工作包→具体动作→交付与判断”阅读；标准映射、视觉接入、调度机制和大规模学习分别列出产物。箭头在这里表示工作推进顺序。</p><p><strong>◇ 读到什么：</strong>这些是下一阶段安排；本轮已完成的依据仍是第4章的训练、测试和纯物理规模结果。</p></div></div>

|工作包|下一项具体工作|交付与判断|
|---|---|---|
|正式国标映射|取得两项正式条款，对应供回液、压差、流量、露点及保护需求|条款／测量／方程／动作／工况矩阵，区分标准参数与研究参数|
|机房视觉接入|用机房图像做域适配，关联资产／时刻；以校准测温支持热点复核与接点观测更新|视觉线索对专业确认的独立贡献，保留标定及时间对应证据|
|调度机制研究|在保留资格和硬重访约束下设计可比较的多候选机会，分别检验奖励与训练预算|候选机会、实际轨迹与确认增量；RSI反馈增量另立协议|
|大规模学习调度|解除128柜／16组及固定网格项，重训并核查人员、时延与重访|512／1024柜端到端学习结果，与本轮18次纯物理结果分别记录|

新假设继续在测试前冻结样本、权重、权限与预算。已有探索性收益参考为平均净增至少1段、区间下界>0、移动增加≤5%、完成量下降≤2%且约束零违规；具体评价随新问题登记。

<a id="appendix"></a>
## 6. 技术附录与可追溯原件

<p class="chapter-lead">具体案例、历史对照、训练细节与原件索引集中在这里，供需要进一步核查时按项查阅。</p>

### 6.1 历史回看、执行记录与详细对照

以下材料保留历史基准、逐步核算及分组结果，正文以第4章的新留出比较为主。


<h4 id="engineering-history">附录 A. 500秒工程回看与原风险分布</h4>

本例来自已保存的固定巡回工程过程。估计／事后温度共用45—75°C色标；红框标出原风险分>0的64、67、70号柜，黑点为32个固定温度点。它与正文新测试案例00分别记账，名义递推原理见[2.2.1节](#principle-estimation)。



<a id="figure-estimated-temperature"></a>

<div class="exhibit-intro" data-guide-figure="estimated-temperature"><p class="exhibit-title"><span class="exhibit-number">图 17</span> <strong>历史500秒时，系统认为哪里偏热</strong></p><p class="exhibit-purpose">回看早期工程示例中的公开估计，为相邻的真实温度对照和风险图提供位置索引。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/estimated-temperature.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>每小格代表1柜，每8柜组成一组，共16组；用45—75°C色标读温度。红框标出64、67、70号的原热风险提示，下一幅图保留相同格子位置与色标，便于逐柜对照。</p><p><strong>◇ 读到什么：</strong>这幅图表示巡检侧当时能估计到的温度，红框给出需要复核的位置；它属于历史工程例，正文新测试快照另行展示。</p></div><p class="exhibit-source">已有工程回看500秒的公开温度估计；与右图同一色标，红框叠加原热风险提示。</p>



<a id="figure-offline-temperature"></a>

<div class="exhibit-intro" data-guide-figure="offline-temperature"><p class="exhibit-title"><span class="exhibit-number">图 18</span> <strong>同一历史时刻的事后设备温度</strong></p><p class="exhibit-purpose">给上一幅估计图提供对照，判断偏热区域与温度数值是否接近。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/offline-temperature.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>格子位置与上一图一一对应，仍用45—75°C色标；先找到64、67、70号柜，再比较两图同位置的颜色。这里的温度来自模拟设备状态，属于回合后可读取的评价信息。</p><p><strong>◇ 读到什么：</strong>估计图与事后图的差异反映状态重构误差；这张对照图帮助评价估计，在线派单读取的仍是公开观测与估计。</p></div><p class="exhibit-source">同一工程过程500秒的事后设备代表温度。</p>




<a id="figure-public-risk"></a>

<div class="exhibit-intro" data-guide-figure="public-risk"><p class="exhibit-title"><span class="exhibit-number">图 19</span> <strong>怎样把偏热与功率缺口转成待办风险</strong></p><p class="exhibit-purpose">说明温度分布如何进入派单，而不是把温度颜色直接当作检查顺序。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/public-risk.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>仍按同一组/机柜位置读图；色标数值是无量纲风险分r，黑点标出32个固定测温位置。r由非正转正且没有现有待办时才新建请求，持续正值不会重复建单；具体分数结合温度越界与功率缺口计算，本帧色标用于显示这一帧。</p><p><strong>◇ 读到什么：</strong>风险分提供核查线索，既不是℃数值，也不是故障概率；是否有效确认，最终要看专业量测和完成时机。</p></div><p class="exhibit-source">已有工程回看：固定巡回，500秒；风险分由公开观测和名义估计计算。</p>


<div class="table-guide" id="table-hotspot-values"><div class="exhibit-intro" data-guide-table="hotspot-values"><p class="exhibit-title"><span class="exhibit-number">表 19</span> <strong>历史热风险位置的估计值与事后值</strong></p><p class="exhibit-purpose">给红框机柜的温度图补上准确数值，便于检查估计差异。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>按柜号定位64、67、70号，再并排比较T̂名义估计与T事后代表温度，单位均为°C；风险分r另用无量纲数值。最后一列说明该柜是否具有固定温度遥测。</p><p><strong>◇ 读到什么：</strong>同一风险框可同时查看温度估计、事后值和观测条件；风险分的大小还结合了功率缺口。</p></div></div>
<div class="table-wrap"><table data-table="hotspot-values"><thead><tr><th>机柜</th><th>当时公开风险分</th><th>名义估计温度／°C</th><th>事后代表温度／°C</th><th>固定温度遥测点</th></tr></thead><tbody><tr><td>64</td><td>0.1296</td><td>67.35</td><td>67.63</td><td>是</td></tr><tr><td>67</td><td>0.2623</td><td>69.58</td><td>69.53</td><td>否</td></tr><tr><td>70</td><td>0.1323</td><td>67.36</td><td>67.31</td><td>否</td></tr></tbody></table></div>

<h4 id="fifo-detail">附录 B. FIFO队列与完整返回核算实例</h4>

任务契约和证书公式见[3.1节](#principle-return)。下列历史记录说明例行账与风险账如何共同执行。



<a id="figure-fifo-cycle"></a>

<div class="exhibit-intro" data-guide-figure="fifo-cycle"><p class="exhibit-title"><span class="exhibit-number">图 20</span> <strong>FIFO怎样在例行任务之间安排加查</strong></p><p class="exhibit-purpose">用一次可重复的执行流程解释“有风险先核查，但例行任务仍要按时完成”。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/fifo-cycle.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>从左向右读：本人任务→可行性筛选→最早风险请求→移动和专业测量。下方回转箭头表示完成后重新选择；无可执行风险时回到原定下一项。加查保留例行进度，完成原定任务时才推进。</p><p><strong>◇ 读到什么：</strong>每次完成后都重新核算，队列排序和返回保护共同决定能否继续加查；一次合格测量也可以同时履行风险与例行义务。</p></div><p class="exhibit-source">每名执行者空闲时从本人合法请求中选择；完成量测后进入下一轮。</p>


<div class="table-guide" id="table-fifo-queue"><div class="exhibit-intro" data-guide-table="fifo-queue"><p class="exhibit-title"><span class="exhibit-number">表 20</span> <strong>为什么先查风险更小的10号柜</strong></p><p class="exhibit-purpose">用实际队列说明FIFO究竟按什么排序。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>两项请求都通过资格、可行性和预算检查，再比较首次提示：10号450秒&lt;8号455秒。470秒的风险0.0081&lt;0.0656，但FIFO优先最早提示，因此本轮10号→8号。</p><p><strong>◇ 读到什么：</strong>本次选择依据是进入队列的先后；风险分提供请求信息，专业资格和返回时间先决定能否执行。</p></div></div>
<div class="table-wrap"><table data-table="fifo-queue"><thead><tr><th>本人的待确认请求</th><th>首次提示时间</th><th>470秒时风险分</th><th>当下检查</th><th>本次选择</th></tr></thead><tbody><tr><td>机柜10热检查</td><td>450秒</td><td>0.0081</td><td>资格、可行性和预算均通过</td><td>先查</td></tr><tr><td>机柜8热检查</td><td>455秒</td><td>0.0656</td><td>资格、可行性和预算均通过</td><td>继续等待</td></tr></tbody></table></div>


<a id="figure-fifo-actions"></a>

<div class="exhibit-intro" data-guide-figure="fifo-actions"><p class="exhibit-title"><span class="exhibit-number">图 21</span> <strong>两次加查之后怎样仍赶上原定任务</strong></p><p class="exhibit-purpose">把返回核算表中的时间变成实际执行顺序。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/fifo-actions.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>横轴是仿真秒数，色块宽度为移动＋服务耗时；沿10号→8号→0号阅读，完成时刻依次为500、515、540秒。0号原定期限是545秒，第二次加查在500秒重新决策后才获批准。</p><p><strong>◇ 读到什么：</strong>540≤545，原定0号仍提前5秒完成；这说明两次加查各自核算后可行，不能把首次批准理解为后续任务也自动获批。</p></div><p class="exhibit-source">主验证第2个过程，一名热巡检员的实际记录；色块宽度表示移动与服务时间。</p>


<div class="table-guide" id="table-return-budget"><div class="exhibit-intro" data-guide-table="return-budget"><p class="exhibit-title"><span class="exhibit-number">表 21</span> <strong>每一次加查的返回时间怎样核算</strong></p><p class="exhibit-purpose">核对加查之后还能否在545秒前完成原定0号任务。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>每行是一轮重新决策。470秒选10号，预计回到0号完成于525秒；500秒再选8号，回到0号改为540秒。与545秒期限比较，余量由20秒降到5秒；完整循环最小余量≥0才通过。</p><p><strong>◇ 读到什么：</strong>允许加查依赖当时的位置、时间和剩余例行义务；第二行重新核算后，仍给原任务保留5秒余量。</p></div></div>
<div class="table-wrap"><table data-table="return-budget"><thead><tr><th>重新决策时刻</th><th>批准的加查</th><th>预计完成加查</th><th>随后按原循环返回0号</th><th>0号截止</th><th>完整循环最小余量</th></tr></thead><tbody><tr><td>470秒</td><td>10</td><td>500秒</td><td>525秒</td><td>545秒</td><td>20秒</td></tr><tr><td>500秒</td><td>8</td><td>515秒</td><td>540秒</td><td>545秒</td><td>5秒</td></tr></tbody></table></div>

原0号245秒完成、截止545秒，实际540秒完成，间隔295秒。10号450秒早于8号455秒入队，因此即使风险较低也先处理。日志保留0.0081／0.0656总分；额外加查保留例行指针，请求在量测或到期前持续记账。

<h4 id="historical-benchmark">附录 C. 历史耦合基准与规则诊断</h4>

历史工况A的12过程采用辅助馈电故障与CDU衰减，持续180秒；77段热异常、12段制冷异常共89段。供电与换热乘子分别为0.05、0.20，峰值总输入23.15—24.14 MW。下列图与主文210段留出结果使用各自分母。



<a id="figure-confirmations"></a>

<div class="exhibit-intro" data-guide-figure="confirmations"><p class="exhibit-title"><span class="exhibit-number">图 22</span> <strong>历史89段异常中，有多少被实际确认</strong></p><p class="exhibit-purpose">对照固定巡回、风险响应和风险位置打乱，观察事件线索是否有任务价值。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/confirmations.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>纵轴为确认段数，三柱的共同分母都是89；柱顶28/89、70/89、25/89分别对应Tour、FIFO和风险位置打乱。确认是异常窗口内完成合格告警量测，而不是发出提示的次数。</p><p><strong>◇ 读到什么：</strong>历史包中FIFO确认更多，位置打乱后下降；这组结果针对旧12个过程，正文210段新基准使用自己的分母。</p></div><p class="exhibit-source">历史耦合工况A：12个过程，共89段异常；三列为各策略的有效确认量。</p>




<a id="figure-outcome-costs"></a>

<div class="exhibit-intro" data-guide-figure="outcome-costs"><p class="exhibit-title"><span class="exhibit-number">图 23</span> <strong>历史收益是否落在预设代价范围内</strong></p><p class="exhibit-purpose">把增加确认与额外行走、完成检查量的变化一起判断。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/outcome-costs.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>三幅小图从左到右为净增确认↑、移动增加↓、完成量下降↓，各用自己的刻度。蓝色为实测结果，金色虚线为探索性门槛：至少1段、至多5%、至多2%；确认点的横线为95%自举区间。</p><p><strong>◇ 读到什么：</strong>历史结果为每过程净增3.50段、移动增加0.50%、完成量下降约0.33%，落在当时预设范围内；这些门槛用于研究取舍。</p></div><p class="exhibit-source">历史耦合工况A的FIFO相对Tour比较；区间、代价与探索性门槛均来自封存记录。</p>



<div class="table-guide" id="table-fault-cases"><div class="exhibit-intro" data-guide-table="fault-cases"><p class="exhibit-title"><span class="exhibit-number">表 22</span> <strong>历史12个过程分别注入了什么条件</strong></p><p class="exhibit-purpose">给旧89段比较提供可定位的案例清单。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>每行是一条物理过程，列出随机种子、目标柜/设备组及故障注入起止秒数。“热/冷异常段”中的a/b是两个专业的段数，不是a除以b的比例；注入时窗和形成的异常段分别记录。</p><p><strong>◇ 读到什么：</strong>旧包的89段由这些过程产生；同一过程上的多种策略比较共享这一故障条件。</p></div></div>
<div class="table-wrap"><table data-table="fault-cases"><thead><tr><th>过程</th><th>种子</th><th>目标柜号／设备组</th><th>故障开始→结束／秒</th><th>热／冷异常段</th></tr></thead><tbody><tr><td>01</td><td>101003</td><td>0号／第1组</td><td>150→330</td><td>8／1</td></tr><tr><td>02</td><td>101040</td><td>9号／第2组</td><td>335→515</td><td>6／1</td></tr><tr><td>03</td><td>101077</td><td>20号／第3组</td><td>520→700</td><td>6／1</td></tr><tr><td>04</td><td>101114</td><td>29号／第4组</td><td>705→885</td><td>7／1</td></tr><tr><td>05</td><td>101151</td><td>36号／第5组</td><td>150→330</td><td>7／1</td></tr><tr><td>06</td><td>101188</td><td>45号／第6组</td><td>335→515</td><td>7／1</td></tr><tr><td>07</td><td>101225</td><td>56号／第8组</td><td>520→700</td><td>6／1</td></tr><tr><td>08</td><td>101262</td><td>65号／第9组</td><td>705→885</td><td>6／1</td></tr><tr><td>09</td><td>101299</td><td>76号／第10组</td><td>150→330</td><td>7／1</td></tr><tr><td>10</td><td>101336</td><td>85号／第11组</td><td>335→515</td><td>7／1</td></tr><tr><td>11</td><td>101373</td><td>100号／第13组</td><td>520→700</td><td>4／1</td></tr><tr><td>12</td><td>101410</td><td>117号／第15组</td><td>705→885</td><td>6／1</td></tr></tbody></table></div>

异常阈值与最短持续时间见4.1.1节。该12过程按热／电气／制冷／自控分别形成77／0／12／0段；确认按完成时刻之前的5秒采样格是否异常及测量是否告警核对。



<a id="figure-paired-net"></a>

<div class="exhibit-intro" data-guide-figure="paired-net"><p class="exhibit-title"><span class="exhibit-number">图 24</span> <strong>历史净增是否只由少数过程贡献</strong></p><p class="exhibit-purpose">把总体收益拆到12个配对过程，查看结果在各过程中的分布。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/paired-net.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>每行先固定同一故障过程，再计算FIFO确认数−Tour确认数；+3表示该过程净多确认3段，0表示持平。过程01—12是登记编号，不代表连续时间。</p><p><strong>◇ 读到什么：</strong>这批历史过程有11个净增、1个持平，说明总体增量分布在多个过程；它描述这12个过程的结果。</p></div><p class="exhibit-source">过程01—12为预登记的12个配对过程；11个净增、1个持平。</p>



九规则先由FIFO选定合法事件，再在事件与原定下一项例行任务之间决定响应／暂缓。R＝风险÷4，A＝等待秒数÷120，E＝两候选预计完成时差÷300，S＝两者完整循环最小余量差÷600；得分z≥0响应，否则执行原定下一项例行任务。



<a id="figure-registered-rules"></a>

<div class="exhibit-intro" data-guide-figure="registered-rules"><p class="exhibit-title"><span class="exhibit-number">图 25</span> <strong>九条简单打分规则是否优于FIFO</strong></p><p class="exhibit-purpose">说明早期响应/暂缓搜索测试了哪些候选，以及为何保留FIFO。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/registered-rules.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>每行给出一个得分式z和确认段数，z≥0选择加查，z&lt;0先做原定任务。R为归一风险，A为归一等待，E为额外完成耗时差，S为返回余量差；横轴为同一89段中的确认量，FIFO的70段是参照。</p><p><strong>◇ 读到什么：</strong>九条已登记规则最高60段，未超过FIFO的70段；这里是已见过程上的开发搜索结果，后续时序图解释部分丢失来源。</p></div><p class="exhibit-source">本项目9个唯一规则的得分式；R、A、E、S分别对应正文中的归一风险、等待、额外耗时与余量差。</p>



规则01的4R−1在229次二选一中全部为负，最高原风险0.7604，额外访问0，12条完整动作与Tour相同。规则06要求至少等待15秒，新增2段、丢失12段；这12段内均无完成量测，区间后首次量测正常。



<a id="figure-rule-diagnosis"></a>

<div class="exhibit-intro" data-guide-figure="rule-diagnosis"><p class="exhibit-title"><span class="exhibit-number">图 26</span> <strong>一次暂缓怎样错过机柜4的异常</strong></p><p class="exhibit-purpose">给规则负结果提供一个可追踪的完成时间解释。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/rule-diagnosis.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>阴影标出310—335秒异常段，上下两轨迹是同一过程、同一巡检员。FIFO在320秒测到告警；等待规则先查12号，再加查4号，365秒才测量。把完成时刻与窗口比较：310&lt;320≤335&lt;365。</p><p><strong>◇ 读到什么：</strong>这次差异出在完成测量的时机：FIFO赶上窗口，等待规则在异常结束后才到；图中使用的是实际轨迹。</p></div><p class="exhibit-source">主过程01的完整策略轨迹对照，机柜4；等待规则为图中06号，按记录重绘。</p>



该例两条轨迹260秒首次分叉。FIFO在300秒例行派4、320秒告警，赶上310—335秒的异常；等待规则315秒先查12、340秒再查4、365秒正常。335秒是未选候选的预计完成端点，图中只展示已执行轨迹。



<a id="figure-execution-chain"></a>

<div class="exhibit-intro" data-guide-figure="execution-chain"><p class="exhibit-title"><span class="exhibit-number">图 27</span> <strong>同一巡检员的后续任务怎样被重新排开</strong></p><p class="exhibit-purpose">解释一次加查如何改变后面多项任务的到访时间，并引出一增一失两个案例。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/execution-chain.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>“任务@秒”表示该任务的完成时刻；从共同的11@605向右，分别沿Tour和FIFO轨迹阅读。橙框标额外访问，…表示省略的其他访问。重点比较17号与21号在两条轨迹中的位置和完成时间。</p><p><strong>◇ 读到什么：</strong>同一条FIFO轨迹可能把某个例行任务推入异常窗口，也可能让另一项检查过晚；下两图分别展开这两种结果。</p></div><p class="exhibit-source">p02-coupled，同一巡检员1，关键任务完成链；中间部分访问省略。</p>




<a id="figure-task-17"></a>

<div class="exhibit-intro" data-guide-figure="task-17"><p class="exhibit-title"><span class="exhibit-number">图 28</span> <strong>17号新增确认为什么来自例行访问</strong></p><p class="exhibit-purpose">说明路线变化带来的收益不一定对应一次额外风险派单。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/task-17.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>阴影为680—705秒异常窗口。Tour在645秒已测完，FIFO在665秒派出原定例行检查并于690秒完成；风险提示到685秒才出现。时间关系为645&lt;680&lt;690≤705，且派出早于风险提示。</p><p><strong>◇ 读到什么：</strong>FIFO的这次例行完成恰好进入异常窗口，形成新增确认；应按实际任务性质和完成记录解释收益。</p></div><p class="exhibit-source">17号665秒派出的是例行访问；其公开风险685秒才出现。</p>



<a id="figure-task-21"></a>

<div class="exhibit-intro" data-guide-figure="task-21"><p class="exhibit-title"><span class="exhibit-number">图 29</span> <strong>21号为什么加查了仍丢失确认</strong></p><p class="exhibit-purpose">强调派出检查和完成有效确认是两件有时间间隔的事。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/task-21.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>异常窗口为650—710秒。Tour在695秒测到异常；FIFO虽在705秒额外派出，但725秒才完成，读作650&lt;695≤710&lt;725。把完成点而非派单点与阴影比较。</p><p><strong>◇ 读到什么：</strong>FIFO的量测落在异常结束之后，因而未确认该段；这也是确认指标必须使用完成时刻的原因。</p></div><p class="exhibit-source">21号650秒见风险，705秒额外派单，725秒完成，异常在710秒已结束。</p>



17／21是另一组Tour—FIFO完整轨迹：17号665秒例行派出、685秒见风险、690秒确认；21号650秒见风险、705秒额外派出、725秒测量时已过710秒结束。两类案例分别支持机制时序与响应门槛诊断。

#### 附录 D. 原论文水域任务对照



<a id="figure-original-paper-scores"></a>

<div class="exhibit-intro" data-guide-figure="original-paper-scores"><p class="exhibit-title"><span class="exhibit-number">图 30</span> <strong>原论文自身的估计与调度组合效果</strong></p><p class="exhibit-purpose">交代借鉴的水域巡检研究如何比较方法，帮助理解本报告为何同时评价估计和任务。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/original-paper-scores.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>两幅小图分别对应水质参数WQP与静态藻华；横轴为原论文最终巡检分数，方向↓。点是均值，横线为95%置信区间，标签保留均值±区间半宽；在同一场景内比较四种组合。</p><p><strong>◇ 读到什么：</strong>原文中DRL＋VAE的分数更低；这里用于理解原研究内部证据，本机房任务的确认、等待和温度误差在第4章分别评价。</p></div><p class="exhibit-source">原文表8／9均值±95%CI。两种Greedy的藻华终值相同，按原表保留。</p>



原文在水域任务内比较DRL、Greedy、VRP及VAE/Myopic估计组合，测试100个未参与训练的场景。图取表8／9的终值均值与95%区间；“约快30%”描述曲线更早降低。原文Average的归一分母随复现对齐；本任务主表另定义并补算资产加权年龄。

#### 附录 E. 历史封存包横向表

<div class="table-guide" id="table-method-comparison"><div class="exhibit-intro" data-guide-table="method-comparison"><p class="exhibit-title"><span class="exhibit-number">表 23</span> <strong>历史封存包的五个已运行方法与未运行项</strong></p><p class="exhibit-purpose">完整保留早期结果，也交代当时哪些指标和方法没有产出。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>先读最右侧状态，再看确认、等待、年龄与成本。这里以旧89段为分母；未留帧表示无法从保存帧计算温度误差，未计时表示没有耗时记录，旧包未运行表示该方法当时未执行。</p><p><strong>◇ 读到什么：</strong>表中空缺按保存状态解释；已运行方法可在共同指标上比较，新CVAE/PPO结果使用第4章的新数据表。</p></div></div>
<div class="table-wrap"><table class="comparison-table" data-table="method-comparison"><thead><tr><th rowspan="2">方法</th><th colspan="3">状态估计</th><th rowspan="2">适配idleness<br>加权年龄↓</th><th colspan="3">异常任务</th><th colspan="3">成本与效率</th><th rowspan="2">本任务状态</th></tr><tr><th>RMSE<br>°C↓</th><th>加权RMSE<br>°C↓</th><th>R²↑</th><th>确认段数<br>（比例）↑</th><th>截尾等待<br>秒↓</th><th>硬重访<br>违规</th><th>移动变化<br>%</th><th>完成量变化<br>%</th><th>单步推理<br>ms</th></tr></thead><tbody><tr data-comparison-method="tour" data-result-state="primary"><td>固定巡回Tour</td><td>未留帧</td><td>未留帧</td><td>未留帧</td><td>0.310901</td><td>28/89（31.5%）</td><td>78.16</td><td>0</td><td>+0.00</td><td>+0.00</td><td>未计时</td><td>已运行·主比较</td></tr><tr data-comparison-method="shuffled" data-result-state="primary"><td>名义估计＋风险位置置乱</td><td>未留帧</td><td>未留帧</td><td>未留帧</td><td>0.313138</td><td>25/89（28.1%）</td><td>81.06</td><td>0</td><td>+0.63</td><td>-0.34</td><td>未计时</td><td>已运行·主比较</td></tr><tr data-comparison-method="S1-age" data-result-state="development"><td>线性暂缓①：等待15秒</td><td>未留帧</td><td>未留帧</td><td>未留帧</td><td>0.312994</td><td>60/89（67.4%）</td><td>60.23</td><td>0</td><td>+0.55</td><td>-0.30</td><td>未计时</td><td>已运行·开发并列60</td></tr><tr data-comparison-method="S2-risk_time" data-result-state="development"><td>线性暂缓②：多特征</td><td>未留帧</td><td>未留帧</td><td>未留帧</td><td>0.312888</td><td>60/89（67.4%）</td><td>58.14</td><td>0</td><td>+0.49</td><td>-0.28</td><td>未计时</td><td>已运行·开发并列60</td></tr><tr data-comparison-method="fifo" data-result-state="primary"><td>名义估计＋返回保护FIFO</td><td>未留帧</td><td>未留帧</td><td>未留帧</td><td>0.313052</td><td>70/89（78.7%）</td><td>49.69</td><td>0</td><td>+0.50</td><td>-0.33</td><td>未计时</td><td>已运行·主比较</td></tr><tr data-comparison-method="vae_unet_greedy" data-result-state="not_run"><td>VAE-UNet + Greedy</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>历史封存状态；新结果见补充基准</td></tr><tr data-comparison-method="vae_unet_drl" data-result-state="not_run"><td>VAE-UNet + DRL</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>历史封存状态；新结果见补充基准</td></tr></tbody></table></div>

历史主比较采用同12个预登记过程；两条线性暂缓规则为九候选中并列60段的开发对照。原包没有保存统一预测—真值帧或逐步计时，因此“未留帧／未计时”继续保留。历史VAE两行表示当时包内未运行，新增适配与独立结果见第4节。

在该历史包中，Tour整体加权年龄0.310901，FIFO为0.313052；FIFO确认70/89，移动平均+0.50%、完成量下降约0.33%。这些数值与本轮四故障基准各有自己的样本分母。

#### 附录 F. 新基准逐故障族结果

<div class="table-guide" id="table-supplement-families"><div class="exhibit-intro" data-guide-table="supplement-families"><p class="exhibit-title"><span class="exhibit-number">表 24</span> <strong>各类故障下的方法差异</strong></p><p class="exhibit-purpose">查看总体确认差主要出现在哪类故障，而不只看合并均值。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>先固定同一故障族，再在其内部比较方法的确认、等待、误差和额外访问。每行是条件及模型重复汇总后的均值；不同故障族的异常段数不同，跨族比较时同时看平均异常段这一列。</p><p><strong>◇ 读到什么：</strong>分组结果为总体差异提供来源线索；某类故障更难或异常更多，应结合该类分母解释。</p></div></div>
<div class="table-wrap"><table data-table="supplement-families" class="supplement-table"><thead><tr><th>故障条件</th><th>方法</th><th>平均确认段</th><th>平均异常段</th><th>平均截尾等待 / 秒</th><th>加权RMSE / °C</th><th>平均额外访问</th></tr></thead><tbody><tr><td>辅助馈电＋CDU</td><td>名义＋Tour</td><td>2.67</td><td>6.83</td><td>73.14</td><td>0.501</td><td>0.00</td></tr><tr><td>辅助馈电＋CDU</td><td>名义＋FIFO</td><td>4.83</td><td>6.83</td><td>51.71</td><td>0.501</td><td>6.33</td></tr><tr><td>辅助馈电＋CDU</td><td>名义＋Greedy</td><td>4.83</td><td>6.83</td><td>51.56</td><td>0.501</td><td>5.92</td></tr><tr><td>辅助馈电＋CDU</td><td>名义＋PPO</td><td>4.00</td><td>6.83</td><td>62.29</td><td>0.499</td><td>3.94</td></tr><tr><td>辅助馈电＋CDU</td><td>CVAE＋FIFO</td><td>4.75</td><td>6.83</td><td>52.57</td><td>0.199</td><td>6.03</td></tr><tr><td>辅助馈电＋CDU</td><td>CVAE＋Greedy</td><td>4.75</td><td>6.83</td><td>52.40</td><td>0.200</td><td>5.53</td></tr><tr><td>辅助馈电＋CDU</td><td>CVAE＋PPO</td><td>4.75</td><td>6.83</td><td>52.63</td><td>0.200</td><td>6.14</td></tr><tr><td>接触热点</td><td>名义＋Tour</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.210</td><td>0.00</td></tr><tr><td>接触热点</td><td>名义＋FIFO</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.210</td><td>0.00</td></tr><tr><td>接触热点</td><td>名义＋Greedy</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.210</td><td>0.00</td></tr><tr><td>接触热点</td><td>名义＋PPO</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.210</td><td>0.00</td></tr><tr><td>接触热点</td><td>CVAE＋FIFO</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.149</td><td>0.00</td></tr><tr><td>接触热点</td><td>CVAE＋Greedy</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.149</td><td>0.00</td></tr><tr><td>接触热点</td><td>CVAE＋PPO</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.149</td><td>0.00</td></tr><tr><td>传感偏差</td><td>名义＋Tour</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.753</td><td>0.00</td></tr><tr><td>传感偏差</td><td>名义＋FIFO</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.753</td><td>0.00</td></tr><tr><td>传感偏差</td><td>名义＋Greedy</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.753</td><td>0.00</td></tr><tr><td>传感偏差</td><td>名义＋PPO</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.753</td><td>0.00</td></tr><tr><td>传感偏差</td><td>CVAE＋FIFO</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.738</td><td>0.00</td></tr><tr><td>传感偏差</td><td>CVAE＋Greedy</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.738</td><td>0.00</td></tr><tr><td>传感偏差</td><td>CVAE＋PPO</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.738</td><td>0.00</td></tr><tr><td>二次泵故障</td><td>名义＋Tour</td><td>3.50</td><td>8.67</td><td>82.60</td><td>0.674</td><td>0.00</td></tr><tr><td>二次泵故障</td><td>名义＋FIFO</td><td>6.42</td><td>8.67</td><td>54.01</td><td>0.677</td><td>7.67</td></tr><tr><td>二次泵故障</td><td>名义＋Greedy</td><td>6.33</td><td>8.67</td><td>54.64</td><td>0.686</td><td>7.42</td></tr><tr><td>二次泵故障</td><td>名义＋PPO</td><td>5.11</td><td>8.67</td><td>68.12</td><td>0.684</td><td>4.81</td></tr><tr><td>二次泵故障</td><td>CVAE＋FIFO</td><td>6.33</td><td>8.67</td><td>54.37</td><td>0.221</td><td>7.36</td></tr><tr><td>二次泵故障</td><td>CVAE＋Greedy</td><td>6.25</td><td>8.67</td><td>54.92</td><td>0.222</td><td>7.19</td></tr><tr><td>二次泵故障</td><td>CVAE＋PPO</td><td>6.39</td><td>8.67</td><td>54.72</td><td>0.221</td><td>7.44</td></tr></tbody></table></div>

每故障族12个条件，学习方法先平均三个训练种子；表为逐条件均值。主要统计采用四故障族等权，无异常的健康与虚假提示条件另列于正文。

<h4 id="training-seeds">附录 G. 训练种子与候选集合统计</h4>

<div class="table-guide" id="table-supplement-seeds"><div class="exhibit-intro" data-guide-table="supplement-seeds"><p class="exhibit-title"><span class="exhibit-number">表 25</span> <strong>换一个训练种子，成绩变化多大</strong></p><p class="exhibit-purpose">补充物理测试组区间之外的模型训练波动。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>271、811、1931是三次模型训练的随机种子，前三个数是各自每故障条件的平均确认段数。SD是这三个训练种子间的样本标准差；最后一列描述闭环加权RMSE的训练种子波动。</p><p><strong>◇ 读到什么：</strong>本表描述已训练模型之间的离散程度；它与按12组物理测试集计算的95%区间使用不同的重复单位。</p></div></div>
<div class="table-wrap"><table data-table="supplement-seeds" class="supplement-table"><thead><tr><th>方法</th><th>种子271</th><th>种子811</th><th>种子1931</th><th>确认训练种子SD</th><th>误差训练种子SD / °C</th></tr></thead><tbody><tr><td>名义＋PPO</td><td>2.90</td><td>3.23</td><td>1.96</td><td>0.659</td><td>0.0034</td></tr><tr><td>CVAE＋FIFO</td><td>3.17</td><td>3.19</td><td>3.21</td><td>0.021</td><td>0.0017</td></tr><tr><td>CVAE＋Greedy</td><td>3.15</td><td>3.17</td><td>3.19</td><td>0.021</td><td>0.0019</td></tr><tr><td>CVAE＋PPO</td><td>3.21</td><td>3.19</td><td>3.21</td><td>0.012</td><td>0.0021</td></tr></tbody></table></div>


<a id="figure-supplement-seed-blocks"></a>

<div class="exhibit-intro" data-guide-figure="supplement-seed-blocks"><p class="exhibit-title"><span class="exhibit-number">图 31</span> <strong>新基准的确认差在12组测试集中怎样分布</strong></p><p class="exhibit-purpose">检查总体均值背后是否存在条件差异，补充平均效果与区间的读法。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-seed-blocks.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>横轴1—12是独立测试组编号；每柱先在组内等权四类故障，再计算图题中的方法差。柱高&gt;0为前者确认更多，&lt;0为更少，0线为持平。左图是名义FIFO−Tour，右图是CVAE-PPO−名义PPO。</p><p><strong>◇ 读到什么：</strong>不同组的增量并不相同；右图的差还包含估计器及各自训练策略的共同变化。编号表示样本身份，不应读成训练或时间趋势。</p></div><p class="exhibit-source">逐组展示独立测试集内的确认差，四种故障等权；编号是登记身份。</p>


<div class="table-guide" id="table-supplement-policy-training"><div class="exhibit-intro" data-guide-table="supplement-policy-training"><p class="exhibit-title"><span class="exhibit-number">表 26</span> <strong>PPO有多少次真正面临多个可选任务</strong></p><p class="exhibit-purpose">量化策略学习中的排序机会，而不是只统计总训练回合。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>按同一行读回合、全局时间步和执行者实际选择数；“有选择余地比例”＝多个合法候选次数÷实际选择数。例如470/170969≈0.27%。一个全局时间步可能包含多名巡检员的选择。</p><p><strong>◇ 读到什么：</strong>多候选选择集合约占0.26%—0.27%，说明本轮排序机会稀疏；下一步可据此设计新的比较，但这些计数本身不证明FIFO已达最优。</p></div></div>
<div class="table-wrap"><table data-table="supplement-policy-training" class="supplement-table"><thead><tr><th>策略</th><th>训练种子</th><th>回合</th><th>全局时间步</th><th>实际选择数</th><th>存在多个合法候选</th><th>有选择余地比例</th><th>执行＋更新分钟</th></tr></thead><tbody><tr><td>名义＋PPO</td><td>271</td><td>120</td><td>43080</td><td>170969</td><td>470</td><td>0.27%</td><td>2.57</td></tr><tr><td>CVAE＋PPO</td><td>271</td><td>120</td><td>43080</td><td>170956</td><td>437</td><td>0.26%</td><td>4.92</td></tr><tr><td>名义＋PPO</td><td>811</td><td>120</td><td>43080</td><td>170954</td><td>448</td><td>0.26%</td><td>2.39</td></tr><tr><td>CVAE＋PPO</td><td>811</td><td>120</td><td>43080</td><td>170961</td><td>460</td><td>0.27%</td><td>5.30</td></tr><tr><td>名义＋PPO</td><td>1931</td><td>120</td><td>43080</td><td>170957</td><td>466</td><td>0.27%</td><td>2.48</td></tr><tr><td>CVAE＋PPO</td><td>1931</td><td>120</td><td>43080</td><td>170950</td><td>453</td><td>0.26%</td><td>5.44</td></tr></tbody></table></div>

种子271／811／1931列为每主要条件平均确认段，SD是三个训练种子间的样本标准差；误差SD采用闭环加权RMSE。图中每个柱对应独立物理种子块的配对差，四故障条件等权。

PPO的选择数按执行者实际可选集合计；只有一个合法候选时，策略没有排序自由。训练耗时为完整回合执行、评分、留存和四次更新的累计墙钟时间，加载与预热另计。这一比例帮助解释当前返回保护与任务设定给学习留下多大的决策空间。

<h4 id="gap-diagnosis">附录 H. 估计—确认差异的逐事件核对</h4>

此处读取原留出日志，无新增环境、模型推理或训练。144组比较包含同一条件的三个模型重复，独立物理种子块仍为12。三个模型种子的“新增／丢失”分别为1／4、1／3、0／1，平均净差为−2段，与总表155→153一致。

<div class="table-guide" id="table-estimation-confirmation-gap"><div class="exhibit-intro" data-guide-table="estimation-confirmation-gap"><p class="exhibit-title"><span class="exhibit-number">表 27</span> <strong>提示提前为何出现一段新增、一段丢失</strong></p><p class="exhibit-purpose">解释CVAE温度误差更低，却没有让FIFO确认总数提高的一个具体例子。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>“提示→完成”中前者为进入待办的时刻，后者为量测完成时刻。41号窗口855—885秒：CVAE完成880秒在窗内，名义895秒在窗外；45号窗口850—890秒：名义875秒在窗内，CVAE900秒在窗外。</p><p><strong>◇ 读到什么：</strong>41号更早排队使访问顺序发生变化，这个案例形成一增一失；更早提示与更准确的温度，需要通过实际队列和完成时机转化为确认。</p></div></div>
<div class="table-wrap"><table data-table="estimation-confirmation-gap"><thead><tr><th>任务</th><th>原评价段</th><th>名义FIFO：提示→完成</th><th>CVAE-FIFO：提示→完成</th><th>确认变化</th></tr></thead><tbody><tr><td>41号热检查</td><td>855—885秒</td><td>865→895秒</td><td>835→880秒</td><td>CVAE新增</td></tr><tr><td>45号热检查</td><td>850—890秒</td><td>860→875秒</td><td>840→900秒</td><td>CVAE丢失</td></tr></tbody></table></div>

表取`test04-cooling`、模型种子271、同一执行者5。两条轨迹在860秒首次分叉：两项访问的资格、返回证书和预算都通过，CVAE-FIFO按835秒早于840秒的入队顺序选41号。41号的确认增加与45号的确认丢失在该回合相抵；其余净差来自案例02、06、07的局部提示与访问轨迹变化。此诊断解释本批记录，完整得失及首次分叉保存在[事后核对数据](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/source-data/estimation-confirmation-gap.json)。



<h3 id="sources">6.2 来源与原件索引</h3>

本轮共2204次环境尝试，含兼容回放、观测采集、PPO训练／诊断与测试；另有3次估计器训练和18次纯物理运行。协议、逐次执行记录、模型身份与原件索引分别保存。

- [工程控制、规模与官方标准核查](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/report-engineering-alignment-20261103.md)。
- [RGB／IR视觉成果与接口核查](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/report-pid-interface-20261103.md)。
- [本任务横向指标、公式与只读复算](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/report-comparison-metrics-20261103.md)。
- [独立补充基准：完整方法](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/supplement-study-methods.md)、[新协议、模型参数及结果原件索引](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/evidence/supplement-study/README.md)。
- [补充研究设计依据](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/supplement-study-design-20261103.md)、[评价与缺失指标核查](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/supplement-metrics-audit-20261103.md)。
- [主机制验证与完整原件](https://github.com/DonsonHH/Zhinengti-RSI/blob/2db2adf146357ec35306503ed15183c0c4100d20/evidence/event-validation/final/README.md)、[九规则开发记录](https://github.com/DonsonHH/Zhinengti-RSI/blob/2db2adf146357ec35306503ed15183c0c4100d20/evidence/response-defer/README.md)。
- [名义估计与故障原件核查](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/report-method-formulas-20261103.md)、[规则动作诊断](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/report-rule-diagnosis-20261103.md)。
- [原论文指标核查](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/original-paper-metrics-20261103.md)、[模型方程与参数](https://github.com/DonsonHH/Zhinengti-RSI/blob/2db2adf146357ec35306503ed15183c0c4100d20/paper/model-appendix.md)、[机制讨论稿](https://github.com/DonsonHH/Zhinengti-RSI/blob/2db2adf146357ec35306503ed15183c0c4100d20/paper/manuscript_zh.md)。

单文件HTML内嵌图像、公式与表格，文本审阅包保留同源正文、数值表及图链接。原事件包、规则开发包与独立补充基准各自保存协议、数据和状态；完整方法与机器可读身份可由以上入口继续核对。
