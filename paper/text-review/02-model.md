> 正文审阅版：正文、公式和数值表与单文件HTML同源；图版保留SVG链接，便于文本工具读取。

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

底层按8柜组组织参数。128／512／1024柜对应32／128／256 MW名义IT负荷，可分别检查物理积分、状态留存及构造巡回。当前学习估计网格与端到端巡检基准固定为128柜／16组；[4.5节](05-comparison.md#scale-results)报告三规模的纯物理实测和静态人员巡回核查。

<aside class="scope-note"><p><strong>模型范围：</strong>当前采用集中参数与合成研究参数。额定IT功率、基准报告功率和算力性能分别列示；现场校准、E/G算力映射与更大规模学习调度构成后续工程验证对象。</p></aside>
