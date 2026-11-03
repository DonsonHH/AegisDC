# Frontier：分站拓扑、状态方程与参数来源复核

复核日期：2026-11-04。本文将公开工程描述转成可建模台账，并提出集中参数方程；未运行仿真、训练或策略比较。

## 证据规则与来源

`published_site`表示主来源发表的站点描述，仍带资料年代；`published_model`表示原作者的近似/删减/参数；`design_or_capability`表示建设能力、额定能力或可扩展设计；`model_proposal`表示本研究提出的方程或连接；`missing`表示未取得可用于闭合模型的资料。来源之间的矛盾单列，不以平均或拼接消除。

|ID|主来源、版本与定位|本轮实际读取范围|
|---|---|---|
|F01|[OLCF，Powering Frontier，2020-09-23](https://www.olcf.ornl.gov/2020/09/23/powering-frontier/)；[同题图文页](https://www.olcf.ornl.gov/powering-frontier/)|官方搜索索引可读相关正文；直接访问403。供电线路及建设边界采用当年口径。|
|F02|[OLCF，Stunning Specs，2021-09-29](https://www.olcf.ornl.gov/2021/09/29/stunning-specs-whats-inside-the-nations-first-exascale-supercomputer-facility/)|官方索引返回完整相关正文，直接访问403。|
|F03|[Brewer等，ExaDigiT，arXiv v1，2024-10-07](https://arxiv.org/html/2410.05133v1)；[PDF](https://arxiv.org/pdf/2410.05133v1)|HTML及PDF提取文本，重点§III-B、III-C，Table I，Figs.3、5。|
|F04|[Kumar等，Thermo-Fluid Modeling Framework…Part 1](https://ecp.ep.liu.se/index.php/modelica/article/view/1145)；[原始9页PDF](https://ecp.ep.liu.se/index.php/modelica/article/download/1145/1052/1207)|会议为2024-10；网页发表2025-01-16。全文提取文本；重点§2.1–2.3、§3.2，物理页2–8/印刷页200–206。|
|F05|[Sun等，Scientific Data 11:1077，2024-10-03，作者全文PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC11450168/)|全文已读取，重点Methods、Data Records、Table1、Technical Validation；Nature直连重定向失败，以作者论文的PMC存档核验。|
|F06|[Frontier HPC & Facility Data，Figshare v4](https://doi.org/10.6084/m9.figshare.24391240.v4)；[版本API](https://api.figshare.com/v2/articles/24391240/versions/4)|API及XLSX在内存读取；只检查Readme、18列表头和前19个数据时间戳，未做全年统计或参数拟合。|
|F07|[Grant等，Providing Thermal Stability…，ORNL摘要，2026-01-25](https://impact.ornl.gov/en/publications/providing-thermal-stability-for-an-exascale-supercomputer-a-case-/)|官方摘要和书目信息；ACM全文403，未以摘要代替完整控制规程。|

## 1. 拓扑以F04的实物/模型分层说明为主

Frontier的热量依次经过**设备/CDU回路→中间HTW回路→冷却塔CTW回路→大气**。这些是热传递方向；隔开的流体不穿过换热器混合。供水、回水和控制信息应在图中另用线型表示。[F04，§2.1，Fig.2，PDF物理页2–3](https://ecp.ep.liu.se/index.php/modelica/article/download/1145/1052/1207#page=2)

### 1.1 节点与连接台账

|节点/边|关系类型与方向|证据状态、出处及边界|
|---|---|---|
|实验室变电站→新增13.8kV馈线→5600/5700/5800设施区|电能输入|`published_site`，F01；尚缺逐馈线单线图及各楼分配。|
|楼内配电变压器/开关板→机柜480VAC→整流380VDC→SIVOC48VDC→计算节点|电能路径|`published_site`，F04 §2.1，物理页2；柜内接口已描述，不能推导园区级A/B双路或整机UPS。|
|CTW冷却塔冷端→CTWP→EHX冷侧→冷却塔热端|同一CTW流体闭环|`published_site`，F04 §2.1，物理页3；节点连通不代表人员可沿管线通行。|
|EHX的HTW冷端→HTWP→HTW供水总管→CDU换热器设施侧→HTW回水总管→EHX|同一HTW流体闭环|`published_site`，F04 §2.1；总管下还有旁路和Orion支路，不能把总流量全分给计算柜。|
|CDU换热器设备侧→并联CDU泵→机柜/刀片/冷板→设备侧回水→同一CDU换热器|同一设备流体闭环|`published_site`，F04物理页3；真实柜内支路和27台CDU逐台映射仍缺。|
|CDU热侧→HTW→CTW|通过两级换热器传热|`published_site`，F04 Fig.2；热箭头可串联，供回水应画独立环路。|
|HTW供水→旁通阀→HTW回水混合点|旁路流体边|`published_site`，F04 §2.1；低流量时旁通占比约10–15%，不是全工况固定比率。|
|HTW供水→Orion文件系统→HTW回水|另一冷却负载支路|`published_site`，F04 §2.1；资料称供温低于18°C时约占流量10%，其实际开停和边界尚缺。|
|CDU压差→泵速；设备侧供温→设施侧阀门|控制信息|F04 §2.3/Fig.5描述的`published_model`，含取自现场及遥测调参项；不作为完整现场联锁。|
|HTW压差/泵速→HTWP投切；HTWS温度与CTW总管压力→塔投切；塔数→EHX投切|跨回路控制|`published_model`，F04 §2.3/Fig.4；控制存在交叉依赖和模型延迟函数。|
|房间空气处理、露点控制→房间环境|环境边界|`published_site`，F04 §2.1；该文模型未纳入，不能设其耗电或传热为0。|
|UPS/电池、柴油发电机、消防分区、检修通路|待实例化模块|`missing`：现有主来源不足以确认其配置、覆盖对象或拓扑。可在通用模板中保留，不画成该站已知实物。|

### 1.2 原理图建议

建议父报告分成三幅：①电能与散热的设施总览；②三种隔离流体的供回水回路及两处HX界面；③物理状态、现场自动控制和巡检证据三个不同层次。Fig.2只用作理解源接口，重画的抽象图标明“据公开资料整理”，不用原始图替代本研究拓扑台账。

## 2. 数量与口径：先区分安装、运行和模型删减

F04 §2.1明确**已安装27台CDU、其中25台运行，服务74柜；每台最多3柜，部分服务2柜**，因此74并不要求等于25×3。该文还明确：**现场5台EHX、5塔；当前模型4台EHX、4塔/16单元**。这是F03概述中现场20单元而输出16个风机的解释线索。[F04，物理页2–3](https://ecp.ep.liu.se/index.php/modelica/article/download/1145/1052/1207#page=2)

F05则描述4塔、4个次回路且3用1备，并把节点数写成9402；F04/F03给9472。这里将它们作为**不同原文的未完全对齐口径**保存，不能把F05的4塔直接认定为F04现场5塔的更新，或把9402自动改为9472。前述4塔/4HX“模型删减”的明确说明，仅直接解释F04自己的模型。[F05 Methods/Fig.3](https://pmc.ncbi.nlm.nih.gov/articles/PMC11450168/)

F05使用冷却塔回路=primary、中间回路=secondary、设备回路=tertiary；F04使用CTW/HTW/CDU，CDU的“primary side”又指设施侧。建议台账用功能名及介质ID，另存原文称谓。

## 3. 参数表：事实、能力、已发表模型和缺项

|参数/量|公开值或缺值|单位|证据类别及具体定位|用于模型时的处理|
|---|---|---|---|---|
|新增馈线电压|13.8|kV|`published_site`，F01|带2020年代；不自动覆盖所有设施。|
|新增馈线长度|约2.5|mile|`published_site`，F01|土建参照；不作为通行距离。|
|机房供电基础设施|>40|MW电功率|`design_or_capability`，F02|不是机器平均负荷。|
|机械厂电力基础设施|8|MW电功率|`design_or_capability`，F02|与热移除能力分列。|
|楼内新增变压器|9×4|台×MW|`published_site`，F02|未取得馈线映射；9×4不用于“修正”>40MW能力。|
|机械厂支持计算热负荷|40；可扩至70|MW热功率|`design_or_capability`，F02|扩容上限不等于现装容量。|
|建设报道系统水温|90|°F|`design_or_capability`，F02|不是所有回路的统一设定温度；换算约32.2°C仅单位转换。|
|建设报道总水量|约85000|US gallon|`published_site`，F02|跨系统总量不能直接赋给某一热容节点。|
|建设报道泵能力|4×350；每台最高10000|台×hp；US gpm|`design_or_capability`，F02|额定能力与运行点分开。|
|机柜输入/变换电压|480AC→380DC→48DC|V|`published_site`，F04 §2.1，物理页2|转换效率曲线仍缺。|
|计算柜数量|74|柜|`published_site`，F04 §2.1|不扩成75。|
|CDU安装/运行|27/25|台|`published_site`，F04 §2.1|数量与逐台可用状态分开。|
|每CDU柜组|最多3；部分2|柜/CDU|`published_site`，F04 §2.1|完整柜组映射仍`missing`。|
|CDU换热能力|约1.6|MW热功率/CDU|`design_or_capability`，F04 §2.1|不等于每台实时负荷。|
|CTW塔/每塔单元|5/4|台/单元|`published_site`，F04 §2.1|该文模型只4塔；F05不同原文口径另列。|
|HTWP/EHX数量|4/5|台|`published_site`，F04 §2.1|模型只纳4EHX，扩展至8为设计能力。|
|CTWP数量|4|台|`published_site`，F04 §2.1|运行投切日志缺；不假定4台同时运行。|
|CTW大致流量/压力|6000–10000/约1.5|US gpm/bar(g)|`published_site`，F04 §2.1，物理页3|范围不用于推断各泵/各塔独立流量。|
|HTW大致流量/压力|5000–6000/约6.2|US gpm/bar(g)|`published_site`，F04 §2.1|流量是回路描述，包含旁路/其他负载。|
|CDU设备侧大致流量/压力|250–300/约3.5|US gpm/bar(g)|`published_site`，F04 §2.1|不是25台同时各取上限的已测总流量。|
|HTW过程冷却温度范围|约12–32|°C|`design_or_capability`，F04 §2.1|范围不等于控制设定值和容许温升。|
|CDU泵控制|双泵同速且总在运行|逻辑|`published_model`，F04 §2.3|是近似，不是全工况规程。|
|模型启动延迟|1.0|s|`published_model`，F04 §2.3|数值初始化延迟，不当作设备启动/保护延迟。|
|电转换效率|0.96、0.98；合成约0.94|无量纲|`published_model`，F03 §III-B1|文中简化，真实随负载变化。|
|热/电换算与CDU泵功率|0.945；8.7|无量纲；kW/CDU|`published_model`，F03 §III-B2|数据拟合/固定近似，不直接套入新场景。|
|2023机器功率统计|均值12.2、idle8.5、peak28.5|MW|`published_site`，F05 Technical Validation|论文统计口径；未独立复算全年分母。|
|2023导出表间隔|Readme称10；前19时间戳确为10|min|F06有限原件核对；F05另称historian15min|原始采样、聚合/插值过程仍需说明。|
|2023缺失时长|约440|h|`published_site`，F05 Data Records|原文值，未从工作簿全量重算。|
|用于余热计算的物性|ρ1060；cp3.5；水/乙二醇50/50|kg/m³；kJ/(kg·K)；比例|`published_model`/计算依据，F05 Data Records|与F04“加少量添加剂、近似水”不同，不推广至三回路。|
|各容积、金属热容、传热UA/ε曲线|缺值|m³、J/K、W/K|`missing`|阻止可信瞬态温升和停冷缓冲时间预测。|
|泵曲线、阀Cv/阻力、管段长度与惯性|缺完整值|Pa、m³/s等|`missing`；F04称部分来自厂商/遥测，未逐项公开|阻止水力网络闭合与快瞬态复现。|
|PID、死区、延时、保护阈值、人工覆盖|缺完整值|s、K、Pa等|`missing`，F04 §2.3、§3.2|阻止控制/故障切换的现场重放。|
|环境湿球、房间露点的完整边界时序|缺本轮已校验输入|°C、时间戳|`missing`|阻止塔性能和凝露裕量的定量验证。|
|UPS/电池/柴油覆盖、故障率、检查检出率|缺值|kWh、s、h、概率等|`missing`|不能据PUE或设备计数反推可靠性/巡检收益。|

## 4. 建议状态方程：用于Frontier结构的自有集中参数近似

以下均为`model_proposal`，由守恒关系组织成可审查的ODE/DAE；没有把F03/F04的完整Modelica实现声称为本项目已复刻。取连续状态为每个流体/固体控制体的质量与温度、需要时的管段流量，以及控制器积分状态；塔/泵/阀的投切为离散状态。HTW、CTW和每个CDU设备侧使用各自介质和参数。

**质量与焓。** 每个控制体v：

\[
\frac{dm_v}{dt}=\sum_{in}\dot m-\sum_{out}\dot m,
\qquad
\frac{d(m_vu_v)}{dt}=\sum_{in}\dot m h_{in}-\sum_{out}\dot m h_v+Q_v+P_{diss,v}.
\]

m为kg，u为比内能、h为比焓（均J/kg），流量为kg/s，Q和P为W；固定控制体忽略动能/位能变化，流动功包含在端口焓中。固定容积、近似不可压缩且定物性时可化为`m cp dT/dt = Σ ṁ cp (Tin−T) + Q + Pdiss`；这一简化不描述水锤或显著压缩性。取全回路平均温度只能做低阶热缓冲，若要给出供回温差需分别保留入口/出口或至少两温度控制体。

**设备与液冷耦合。** 对机柜/器件热容：

\[
C_s\dot T_s=P_{device}-G_{sc}(T_s-T_c)-G_{sa}(T_s-T_a).
\]

Cs为J/K，G为W/K，温差为K；流体控制体相应加`+Gsc(Ts−Tc)`，房间加空气侧热项。这样液冷带走的热与未被液冷捕获的热分别记账；不能预置“全部电力都即时进入冷却水”。

**两级换热器。** 每台CDU及EHX使用独立热侧/冷侧端口：

\[
Q_{HX}=\varepsilon C_{min}(T_{h,in}-T_{c,in}),\quad
C_{min}=\min(\dot m_hc_{p,h},\dot m_cc_{p,c}).
\]

ε无量纲且在适用工况0–1；两侧分别加−QHX和+QHX。若引入换热器金属热容，必须另设壁温状态并分别算两侧热流，避免同时施加准稳态Q和额外蓄热造成重复记账。UA/ε、有效容积及污垢修正均待取得。

**水力。** 节点满足`ΣQ̇=0`；支路的准稳态式为`Δp_pump(n,Q̇)−R(u)Q̇|Q̇|−ρgΔz=0`。Q̇为m³/s，压差Pa；R为Pa·s²/m⁶。需要快速水力过程时再加`I dQ̇/dt`，I单位Pa·s²/m³，且需管径/长度及压缩性/边界信息。泵电力为`Ppump=Δp Q̇/ηpump`，流体热量仅计实际耗散份额，η与份额待定。

**塔、旁路与控制。** `QCT=f(TCT,return,Twb,Q̇CT,nfan,Ncell;θCT)`为待标定塔模型；HTW旁路与Orion回流通过质量加权焓混合。泵/阀控制可用有饱和、死区及抗积分饱和的PID候选，投切以带滞回/最小保持时间的离散状态表示；阈值、延时和人工覆盖由资料闭合，不套用F04的1s数值启动延迟。

**电能守恒。** 同一串联变换边界中：`Pload=ηRηS Pin`，`Ploss=Pin−Pload`；设施输入还需加泵、塔、空气处理等不同计量边界的辅助功率。F03 HTML与PDF Eq.(2)末项均显示额外的`P_RDC`乘在功率差前，量纲有疑点；本项目采用上面的W量纲守恒式，并保留此原式核查记录。[F03 §III-B1，PDF物理页5](https://arxiv.org/pdf/2410.05133v1#page=5)

F07仅支持“设施主冷却响应按分钟、组件热应力按秒”的相对时间尺度；没有给可直接使用的时间常数。状态方程尚未闭合的关键θ是容积/热容、物性归属、泵/HX曲线、边界时序与控制逻辑。

## 5. 数据原件的有限核对及缺口处理

F06 v4发布日期为2024-07-19T22:53:33Z，文件`Frontier HPC & Facility Data.xlsx`，文件ID47812750，20,164,974字节，CC BY4.0。内存读取的MD5为`f1832f7215e529f12f38d4087620d6e2`，与API一致；SHA256为`56a48dd66382896890dfc2e4940ec90f894bb85795ee8e85ea2708dda05796bf`。[原件下载](https://ndownloader.figshare.com/files/47812750)

Readme C11:E11写10-minute step。Frontier2023的18列表头包括：时间；三支路回温与流量；总体回温/供温/流量；三支路及总余热；compute/accessory/total功率；PUE。A3:A21的19个起始时间戳覆盖2023-01-01 00:00至03:00，连续间隔10分钟。只证明这一有限区间及发布表的自述；**全年间隔、重复、缺失、440h分母及公式缓存均未全量复核**。

F05的Data Records写10分钟，Technical Validation写historian15分钟，表原件支持导出层10分钟。原始采集、趋势查询、导出重采样之间的关系仍为`missing`。将导出数据插值到15秒不产生新观测，不能据10分钟级序列验证秒级保护或识别短时间常数。

|优先缺口|阻止的判断|最小需要取得的资料|
|---|---|---|
|三回路介质、有效容积与部件热容|温升、失冷热缓冲和参数可辨识性|分回路P&ID、介质清单/浓度、储液和金属质量、部件热容或校准阶跃|
|柜组映射及备用设备边界|共享故障影响域、冗余/共因分析|27台CDU台账、运行25台及74柜的映射、隔离阀和维修状态|
|泵/阀/HX曲线及旁路、Orion分流|全回路水力和低负荷热平衡|制造商曲线、阀位与流量同步记录、实际P&ID及管段数据|
|控制与自动保护、人工覆盖日志|切换顺序、误警/越限和稳定性|控制逻辑版本、设定值、滞回/延时、联锁与现场变更记录|
|带质量标志的多尺度原时序|独立验证与时间常数识别|原始时间戳/时区、采集及重采样说明、缺失原因、同步的负荷/天气/温压流记录|
|固定测点与人工/便携检查可用性|按问题触发的核查效果|传感器覆盖/校准记录、工单、现场检查规程和盲检结果；无实时全覆盖前提|

本轮交付为上述公开结构、参数来源和待闭合方程；现场校准与独立对照另行设计，智能体和RSI保持后续阶段。
