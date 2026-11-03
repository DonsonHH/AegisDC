> 正文审阅版：正文、公式和数值表与单文件HTML同源；图版保留SVG链接，便于文本工具读取。

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
