# El Capitan / LLNL：设施拓扑、状态方程与参数的主来源核查

核查日期：2026-11-04（Asia/Shanghai）。本笔记服务于三案例分别建模，重点是B453、ECFM与El Capitan之间的接口。来源直接发表的配置、设计能力、调试量和当前运行测量分别登记；本次没有取得竣工单线图、P&ID或在役时序。以下集中参数方程是本研究提出的模型，不是LLNL公布的现场控制方程。

## 1. 来源登记与实际读取范围

|ID|主来源、日期/版本|此次实际读取及定位|
|---|---|---|
|EC1|[LLNL：Powering up](https://www.llnl.gov/article/48101/powering-llnl-prepares-exascale-massive-energy-water-upgrade)，2021-10-18|官方HTML正文。定位：85MW/两台exascale段、30–35MW段、115kV/两台40MW变压器段、六台3000ton塔段；这是部署前报道。|
|EC2|[ECFM fact sheet](https://asc.llnl.gov/sites/asc/files/2022-09/ECFM-fact-sheet-v6_0.pdf)，2022年版，LLNL-MI/MISC-834245|两页PDF文字直接读取。物理页1列85MW/28000ton；物理页2列30in过程水管、13.8kV–480V、BMS连接。PDF图页请求成功但本工具返回未呈现可检查的图像，因此不据图猜接线。|
|EC3|[Chris DePrater：Commissioning Infrastructure for El Capitan](https://hpc.llnl.gov/sites/default/files/Comp-ERC-poster-deprater.pdf)，LLNL-POST-2004490，原件未标发布日期，含2024-02节点|单页PDF文字直接读取。定位：OS455/U450、underfloor infrastructure、5MW load banks及commissioning challenges；不是全负荷验收曲线。|
|EC4|[LLNL：How El Capitan keeps its cool](https://www.llnl.gov/article/54496/meet-machines-matter-how-el-capitan-keeps-its-cool)，2026-06-03|官方HTML正文直接读取。定位：two loops段、400kW/rack段、controls段、85degrees段。正文有[Dan Herchek原图链接](https://contenthub.llnl.gov/sites/contenthub/files/styles/scaled_877w/public/2026-06/Ext_MTMCooling_1200x800.jpg?itok=z6DJDeBw)，本笔记未完成该图的视觉核验。|
|EC5|[LLNL S&TR：Charging Up and Rolling Out](https://str.llnl.gov/past-issues/julyaugust-2022/charging-rolling-out)，2022年7/8月|官方域名检索返回完整相关正文；直接open两次超时。状态为`official_indexed_text`。定位Designing for the Future：24–29°C、CDU、不需冷机、双源负荷转移；须保留2022设计边界。|
|EC6|[HPC @ LLNL：Hardware Overview](https://hpc.llnl.gov/documentation/user-guides/using-el-capitan-systems/hardware-overview)，页面无独立发布日期，访问2026-11-04|官方HTML直接读取ATS-4 comparison表及System Interconnect节。El Capitan列有90计算柜、11520节点、36.0MW peak。|
|EC7|[LLNL ASC：Facilities](https://asc.llnl.gov/facilities)，页面无独立发布日期，访问2026-11-04|官方HTML直接读取ECFM升级段、B453旧介绍段；同页保留45MW旧介绍与85MW升级段，不合成同一时点。|
|EC8|[LLNL ASC：El Capitan](https://asc.llnl.gov/exascale/el-capitan)，页面无独立发布日期，访问2026-11-04|官方HTML直接读取Siting及details段。同页正文写约30MW，项目符号写约35MW；与EC6的36.0MW峰值并列保留，未获得统一计量边界。|

证据标签：`published_site`＝官方发表的该设施配置/功能；`design_capacity`＝额定或设计能力；`commissioning`＝调试记录；`published_hardware`＝官方系统规格；`model_proposal`＝本研究假设；`missing`＝本次主来源未取得。`published_site`仍是公开资料层面的确认，不等于此次现场实测。

## 2. 设施层级先分开

**B453是可容纳两代exascale系统的共享设施，El Capitan是其中一台机器。** ECFM把B453电力能力从45MW增至85MW，液冷能力从10000增至28000 refrigeration ton。ECFM增加40MW、18000ton的表述与此相容；2021所列“两台40MW变压器”是设备描述，不能据此把楼宇能力写为80MW、125MW或2N。[EC1，85MW段及变压器段；EC2，物理页1–2；EC3，OS455/U450段](https://asc.llnl.gov/sites/asc/files/2022-09/ECFM-fact-sheet-v6_0.pdf)

EC3给出**U450变电站、OS455冷却塔**设施标识，适合用作架构图节点。2022 S&TR描述双电源之间可自动转移负荷，但没有给出电源独立性、选择性保护、后备容量或切换秒数；这些仍不能简写为某种冗余等级。[EC3，页1](https://hpc.llnl.gov/sites/default/files/Comp-ERC-poster-deprater.pdf)、[EC5，Designing for the Future](https://str.llnl.gov/past-issues/julyaugust-2022/charging-rolling-out)

## 3. 第一幅图所需：供电、服务与控制关系

箭头表示供电或信息功能方向，不表示检修人员可沿线通行。

|起点→终点|证据等级|支持到哪一步；仍缺什么|
|---|---|---|
|115kV外部线路→ECFM新开关场/变电站|`published_site`，EC1变电站段、EC2页2|接入和新站有直接来源；原图母线、接地点、每条线路命名未知。|
|变电站变压/开关设备→13.8kV二次馈线|`published_site`，EC1、EC2页2|电压层级和设备类别明确；两台变压器并列方式、联锁及可用容量未知。|
|13.8kV馈线→B453室内13.8kV–480V配电|`published_site`，EC2页2|楼宇接口明确；各IT、泵、控制器支路馈线归属未知。|
|B453配电→El Capitan计算/网络/存储负荷|`published_site`，EC1/EC8；具体分支`missing`|ECFM服务机器有直接依据；不能把每个480V盘柜或双路电源的连接补成实线竣工图。|
|供电→泵/CDU/控制设备|`model_proposal`，功能上需要电力，但具体馈线`missing`|图中以待核实支路呈现。是否与IT共享失效域、是否受UPS保护均未知。|
|ECFM控制系统↔B453 BMS|`published_site`，EC2页2|连接有直接依据；网络分区、控制权限及失联逻辑未知。|
|温度/流量/压力传感→控制→减载/安全停机|`published_site`，EC4 controls段|源文给出观测类别及保护功能；不公开阈值、延时、采样周期和因果联锁表。|
|UPS/电池/柴油后备→IT或泵/控制|`missing`|本次未取得该站配置与覆盖证据；保留灰色缺口节点，不实例化成已部署全站后备。|
|节点之间的人员路径|`missing`|电缆和水管关系不能替代平面图、门禁、危险区域及访问许可。|

可据此画“115kV→变电站→13.8kV馈线→B453 480V→机器”的设施层级主链；具体支路、保护和备用链使用待证线型。双电源转移作为2022设计注记，不能画成未经核实的2N双实线拓扑。

## 4. 第二幅图所需：水、二醇介质与热排出

**该站公开报道明确存在处理水和二醇基液体两类回路，并明确设施水通过CDU服务机器。** 具体介质到每个换热器、泵及机器内回路的逐端口映射尚待P&ID或源图核验。[EC4，two loops段](https://www.llnl.gov/article/54496/meet-machines-matter-how-el-capitan-keeps-its-cool)、[EC5，Designing for the Future](https://str.llnl.gov/past-issues/julyaugust-2022/charging-rolling-out)

|关系/模块|证据等级|作图处理|
|---|---|---|
|ECFM过程冷却水供/回→B453|`published_site`，EC2页2的30in process cooling loop|画有供回语义的设施水接口，30in是该段管径。|
|B453架空地板下管路→CDU|`commissioning`，EC3的20in/10000GPM与CDU水平衡；EC5的水经CDU|可画CDU接口；不由20in和30in推断同一管段或以此估计单向流长。|
|机器热负荷→机器邻近液体回路→CDU/设施热交换→ECFM排热|`published_site`的功能链，EC3/EC4/EC5|功能链有依据；换热器数量、串并联、二醇所在侧和CDU柜组映射保持缺口。|
|处理水回路、二醇基液体回路|`published_site`，EC4|画两种介质与换热隔离边界；不自行标“乙二醇”“丙二醇”或浓度。若端口未核验，回路角色可用A/B及“映射待核实”。|
|ECFM/OS455塔→大气排热|`published_site`，EC3设施标识、EC4蒸发排热段|热量箭头指向大气；流体供回箭头另画，防止把热流当水流。|
|冷水机组模块及其实际支路|EC4发表全系统有chillers；具体连接`missing`|EC5描述ECFM设计可无冷机运行；这不否认楼宇其他冷机存在。用边界注记表示年代/服务范围，暂不把某台冷机串入主回路。|
|房间空气→辅助空调排热|EC7旧楼宇描述支持设备类别；当前映射`missing`|仅画辅助环境边界，不把旧7200ton空调与28000ton液冷重复相加。|

建议图旁保留三条边界说明：①设施水不直接等同于芯片冷却介质；②El Capitan“两类回路”不强制套入Frontier三段模型；③主机热负荷、泵热、其他机器热负荷和楼宇总冷却额定值分别记账。

## 5. 参数表：已发表数值与无值项并列

下表中的有值项均保留来源性质；只有获得运行曲线、测点边界和校准记录后才可升级为仿真校准参数。`null`表示未知，不当0。

|参数/符号|数值或状态|单位|性质、年代与定位|建模处理|
|---|---|---|---|---|
|高压接入电压|115|kV|`published_site`，EC1/EC2页2|电压层级参照；保护和电网暂态未闭合。|
|二次馈线电压|13.8|kV|`published_site`，EC2页2|保持馈线层级。|
|B453低压配电|480|V|`published_site`，EC2页2|具体线电压/支路图仍需电气图确认。|
|新站变压器配置|2×40|MW，沿用原文单位|`design_capacity`，EC1变电站段|不擅改为MVA，不据此推2N或楼宇总功率。|
|B453升级前/后电力能力|45 / 85|MW|`design_capacity`，EC2页1–2|共享设施能力，不作El Capitan负荷输入。|
|B453升级前/后液冷能力|10000 / 28000|refrigeration ton|`design_capacity`，EC2页1–2|热移除额定值，未给环境额定条件；不是电耗。|
|新增冷却塔配置|6×3000|refrigeration ton|`design_capacity`，EC1塔段|总增18000与EC2相容；串并联及冗余工况未知。|
|设施到B453过程水管径|30|in|`published_site`，EC2页2|名义管段标识，不反推有效内径和总水量。|
|机房下部管径|20|in|`commissioning`，EC3页1|与30in分别列项。|
|架空地板高度|4|ft|`commissioning`，EC3页1|空间参照，不作为全楼层高。|
|机房下配水能力|10000|GPM，原文未在此明示加仑制|`commissioning`，EC3页1|用于35MW调试描述；不当所有工况恒定流量，SI换算须注明US gallon约定。|
|调试参照计算负荷|35|MW|`commissioning`，EC3页1|工程参照，非此次运行曲线。|
|实际使用的局部负载箱|5|MW|`commissioning`，EC3页1|局部热负荷外推，不声称全35MW实载验收。|
|El Capitan系统发布峰值|36.0|MW|`published_hardware`，EC6 ATS-4表|与历史预测/调试参照分别保存，未作为实测均值。|
|计算机柜数|90|柜|`published_hardware`，EC6 ATS-4表|不包含所有楼宇设施对象；各CDU服务柜组未知。|
|计算节点数|11520|节点|`published_hardware`，EC6 ATS-4表|IT规模参照，不自动产生热参数。|
|机柜功率密度说明|约400|kW/柜|`published_site`，EC4 rack段|约数，与90×0.4＝36MW仅数量级相容，不是逐柜测量。|
|2021部署前单机峰值预测|30–35|MW|`design_capacity`，EC1部署段|保留历史预测，不替代EC6或实际电表曲线。|
|ASC概览峰值描述|约30（正文）/约35（清单）|MW|`published_site`，EC8 Siting/details|同页口径差异未解，不统一成校准点。|
|通常设施供水温度|24–29|°C|2022设计说明，EC5 Designing for the Future；`official_indexed_text`|不是2026现场设定值；可作为历史设计范围参照。|
|W32/W40表述|32/40分类端点|°C|2022设计分类说明，EC5|不是机器停机阈值或连续正常控制带。|
|2026新闻水温原始值|约85；温标`null`|degrees（原文）|EC4蒸发排热段|保留原文，不默认°F，也不将85输入SI模型。|
|总管路长度描述|>2000|ft|EC4组件段|集合长度，不是单程流长、回路容积或人员行程。|
|处理水/二醇基介质|两类；二醇种类/浓度`null`|类型、质量分数|EC4 two loops段|密度ρ、比热cp、黏度μ须按侧别/温度/配比另取。|
|CDU数量及柜组映射|`null`|台、关联表|`missing`，已核查EC3/EC4/EC5|阻止确定共享故障域和并联支路。|
|回路有效存水/存液量|`null`|kg或m³|`missing`；EC4仅有定性水量|阻止热惯性/失冷时间估计。|
|IT/液体/换热器有效热容C|`null`|J/K|`missing`|不由36MW或柜数反推C。|
|IT到液体、跨回路UA|`null`|W/K|`missing`|阻止动态温升和换热闭合。|
|泵曲线、阀阻力、扬程/压差|`null`|Pa、kg/s或m³/s|`missing`|10000GPM不能替代泵曲线。|
|风机/泵/执行器时间常数|`null`|s|`missing`|不将保护“快速”翻成某个秒数。|
|湿球温度/塔性能/结垢|`null`|°C、W、模型参数|`missing`|阻止季节容量与失冷余量计算。|
|冷机实际服务边界/COP|`null`|关联表、无量纲|`missing`；有组件存在与无冷机设计两个年代说明|不得默认为主回路常开冷机。|
|UPS/电池/发电机覆盖与容量|`null`|关联表、kWh、kW、s|`missing`|不生成未经证实的后备路径。|
|传感器误差、覆盖、采样和时延|`null`|°C、Pa、s等|`missing`；EC4仅确认测量类别|阻止观测模型/误报漏报校准。|
|保护阈值、减载和重启逻辑|`null`|°C、Pa、s、状态机|`missing`|采用可配置的离散模式，规则待证。|
|真实步行/门禁/检查耗时|`null`|m、min、权限|`missing`|不从管路长度生成巡检路线。|

## 6. 适配该站的集中参数状态方程建议

### 6.1 变量、边界与建模层级

建议先用微分–代数混合模型：连续状态`x=(T_IT,T_a,T_b,T_tr,m_a,m_b)`，分别表示IT等效温度、机器邻近与设施侧等效温度、变压器等效温度及两侧介质库存；代数量包括流量、压差、换热量和功率；离散模式`z`包括正常、降载、停止及待核实的备用支路启用状态。温度差用K，功率W，时间s，质量kg。`a/b`先按功能命名，介质映射等待图纸确认，不能默认二醇在芯片侧。

负荷`P_IT(t)`、环境`T_wb(t),T_amb(t)`、外部可供电量、执行器命令是输入；已有传感/历史/人工/手持结果只构成观测。EC6的36MW是已发表峰值参照，不能代替输入时序。`Q_other(t)`专门承接共享设施内其他负荷，避免把28000ton全部归一台机器。

### 6.2 供电与发热：先守恒，再谈电气暂态

```text
P_in,boundary = Σ_j P_served,j + P_loss
P_out,e = η_e P_in,e
C_tr dT_tr/dt = P_loss,tr − UA_tr (T_tr − T_amb)
```

第一式须先明确计量边界/馈线：B453计算侧85MW和泵/塔的供电是否同一边界尚未知。不能先把冷却电耗重复计入，再用85MW当全站限制。η、损耗曲线、热容和冷却系数均缺；115kV/13.8kV/480V说明层级，尚不足以建立保护配合、电压跌落或频率暂态模型。

### 6.3 IT—两功能侧—排热边界

```text
C_IT dT_IT/dt = β P_IT − Q_IT,a
Q_IT,a = UA_IT,a (T_IT − T_a)
C_a dT_a/dt = Q_IT,a + α_a P_pump,a − Q_ab
C_b dT_b/dt = Q_ab + Q_other + α_b P_pump,b − Q_rej
Q_ab = UA_ab(Vdot_a,Vdot_b,fouling) (T_a − T_b)
Q_rej = Φ_tower(T_b,T_wb,fan_command,Vdot_b) + Q_optional_chiller
```

这些是全混合回路的有效热节点近似，流量对换热的作用吸收进UA函数；不是逐管段温度分布或已验证控制器。β是入此液冷热账的IT功率比例，α是泵电功率留在所选流体边界内的比例，均待定。可选冷机项只有取得实际接口、服务边界和COP后才启用；2022无冷机设计与2026全组件叙述分别留作来源条件。C、UA、β、α和塔性能缺失时，不能据此输出真实失冷温升/截止时间。

为取得更细的供回温及延迟，可把每侧拆成带质量流的多个容积：`m_i cp_i dT_i/dt = Σ_in mdot cp(T_in−T_i) + Q_i`。这需要P&ID、侧别介质、每段液量、混合/分流比例和初值；不能由20/30in直径加集合管长补齐。

### 6.4 水力与库存

```text
A mdot = 0                                  # 非储存接点的质量守恒
Δp_pump(ω,mdot) = Σ_path Δp_e(mdot,valve)    # 准稳态闭合
P_pump = Δp_pump mdot / (ρ η_p η_m)
dm_l/dt = mdot_makeup,l − mdot_leak,l         # 封闭回路库存；内部循环不增减总质量
```

`mdot`用kg/s、压差Pa、ρ用kg/m³，因此泵功率单位W。泵/阀曲线、连接矩阵A及介质物性缺失；此式只能描述模型接口。若另建开式塔水量账，还须加入蒸发/排污/补水与水处理，不把塔蒸发直接从未经确认的芯片回路扣除。

### 6.5 保护模式与稀疏观测

```text
z_next = g(z, measured_or_control_signals, verified_thresholds)
y_s,k = h_s(x(t_observed),u) + b_s + ε_s
t_available ≥ t_observed ;  only t_available ≤ t_decision is usable
```

现场已有持续监控与保护是来源事实[EC4]；研究决策者可只接收可用快照、历史工单、人工报告和现场便携结果，观测掩码不要求全覆盖，也不把隐藏仿真真值自动变成报警。`g`的阈值、延时和重启联锁待规程；多条相关/陈旧观测的概率更新还需联合或时变似然，不用“每问一条观测”替代该要求。

## 7. 哪些缺口阻止闭合，优先取得什么

|优先级|最小资料|直接解除的阻碍|
|---|---|---|
|P0|ECFM–B453–CDU的带供回/介质标记P&ID，CDU柜组表|确定流体侧别、换热边界、支路、共享故障域；避免误画为Frontier同构三回路。|
|P0|供配电单线图、计量点表、备用覆盖及切换测试|明确85MW限制的负载集合、冷却和控制供电、后备与共因。|
|P0|同步P_IT、各侧供回温/流量/压差、环境、命令及缺失标志|辨识UA/热惯性、验证时间戳和边界能量闭合；峰值和额定能力不足以替代。|
|P1|介质配比、库存、泵阀曲线、塔性能与执行器响应|求动态过程和季节裕度；建立可识别参数而非同一轨迹多参数补偿。|
|P1|传感/保护/减载规程与故障/维修工单（含在役分母）|标定误差、时延、失效过程、实际处置效果和恢复模式。|
|P1|平面/门禁/检修许可和盲检耗时记录|单独建立可访问图与人工确认代价。|

目前可完成有来源的功能拓扑和明确未闭合项的状态方程模板。后续校准的目标是补上每个方程真正需要的连接、状态、输入、物性和测量账；智能体、RSI和策略收益不在本案例资料整理范围。
