> 正文审阅版：正文、公式和数值表与单文件HTML同源；图版保留SVG链接，便于文本工具读取。

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



条件先验／后验与空间编码—解码分别参考[条件生成模型](https://proceedings.neurips.cc/paper_files/paper/2015/file/8d55a249e6baa5c06772297520da2051-Paper.pdf)和[U-Net](https://arxiv.org/abs/1505.04597)。监督目标为离线物理温度，输入为公开遥测和专业量测历史；训练记录与误差见[4.1—4.2节](05-comparison.md#estimation-results)。

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

风险分是待核查严重度代理；有效异常确认以专业量测及离线评价标签核对。新留出过程的态势三联图与局部时序在[4.2.2节](05-comparison.md#estimation-example)统一展示，旧500秒工程帧在[附录A](07-appendix.md#engineering-history)保留。
