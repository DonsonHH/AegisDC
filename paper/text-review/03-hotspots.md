> 正文审阅版：正文、公式和数值表与单文件HTML同源；图版保留SVG链接，便于文本工具读取。

> 2. 感知估计 · 第1/1部分。

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



条件先验／后验与空间编码—解码分别参考[条件生成模型](https://proceedings.neurips.cc/paper_files/paper/2015/file/8d55a249e6baa5c06772297520da2051-Paper.pdf)和[U-Net](https://arxiv.org/abs/1505.04597)。监督目标为离线物理温度，输入为公开遥测和专业量测历史；训练记录与误差见[4.1—4.2节](05-comparison.md#estimation-results)。

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

风险分是待核查严重度代理；有效异常确认以专业量测及离线评价标签核对。新留出过程的态势三联图与局部时序在[4.2.2节](05-comparison.md#estimation-example)统一展示，旧500秒工程帧在[附录A](07-appendix.md#engineering-history)保留。
