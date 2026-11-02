# 合成供电—液冷模型的物理依据与单位核查

核查日期：2026-11-02。本次只读取实现、现有测试和下列原始机构资料；未修改模型、重跑研究或执行测试。结论是：核心方程可以按能量平衡、热容流率及泵—管路关系解释；当前设备参数、故障幅度和控制增益仍是合成研究设定。

## 1 原始依据及实际读取范围

|代号／机构来源|实际读取位置|可支持的方程形式|不能由此标定的内容|
|---|---|---|---|
|P1 ASHRAE，2025 *Handbook—Fundamentals*，Chapter 4 “Heat Transfer”|官方HTML的“Transient Conduction / Lumped Mass Analysis”，式(12)及其适用说明；§5“NTU-Effectiveness Analysis”，式(45)—(46)与热容流率定义|集中热容的温度变化由净热流决定；换热可用有效度、最小热容流率与入口温差表示|机柜等效热容、冷板UA、0.8指数、CDU有效度0.85和机房温度／流量阈值|
|P2 U.S. DOE 与 Hydraulic Institute，2006 *Improving Pumping System Performance: A Sourcebook for Industry*, 2nd ed.|官方PDF印刷页9（PDF第13页）的流体功率与效率；印刷页48（PDF第52页）的二次摩擦压降；印刷页51—52（PDF第55—56页）的调速讨论|流体功率与流量及压头之积有关，输入功率再计效率；固定管路的摩擦损失可用二次流量近似|250/100 kPa泵曲线、效率0.70、支路质量流量6 kg/s、阀门开度—阻力关系的实物参数|
|P3 Hydraulic Institute，*HI Data Tool: Pump Curves*，页面更新2024-07-19|“Efficiency Curve”式1.B.3、“Pump Input Power Curve”式1.B.4—5、“Affinity Rules”式1.B.6a—c及其假设段|在规定的相似及效率假设下，同一叶轮调速有流量随转速、压头随转速平方、功率随转速立方的关系|任意变阀门／变介质状态下的精确性能，或本模型的固定效率真实性|

原始链接：[P1 ASHRAE Chapter 4](https://handbook.ashrae.org/Handbooks/F25/IP/F25_Ch04/F25_Ch04_ip.aspx)；[P2 DOE官方PDF](https://www.energy.gov/sites/default/files/2014/05/f16/pump.pdf)；[P3 HI官方页面](https://datatool.pumps.org/pump-fundamentals/pump-curves.html)。P1采用IP单位页面；本稿SI单位来自实现和量纲换算，不把手册中的英制示例参数作为模型输入。

## 2 与当前代码的对应

### 2.1 水力代数解与泵功率

`secondary_hydraulics()`将每个pod的8条支路视为并联、共享压差。令 $K_b=\Delta p_0/\dot m_0^2$，阀门开度为 $a_r$，$B_p=\sum_{r\in p}a_r/\sqrt{K_b}$。代码等价于联立

$$
\dot m_r=\frac{a_r}{\sqrt{K_b}}\sqrt{\Delta p_p},\qquad
\Delta p_p=p_{\rm shut}n_p^2-K_p\left(\sum_{r\in p}\dot m_r\right)^2,
$$

得到 $\Delta p_p=p_{\rm shut}n_p^2/(1+K_pB_p^2)$。这是给定开度下的准稳态泵—阻力曲线相交解；未加入流体惯性、运输时延、泵的汽蚀或随温度变化的黏度。固定阀门和固定效率时，该族解具有P3所述的调速尺度关系；改变开度会改变系统曲线。

泵功率使用

$$
P_p^{\rm pump}=\frac{\Delta p_p\sum_{r\in p}\dot m_r}{\rho\eta_p}.
$$

代码的数值除数1000对应隐含的 $\rho=1000\,\mathrm{kg/m^3}$：质量流量除以密度得到m³/s，再乘kPa得到kW。它不是把kPa再换成Pa的额外单位系数。一次泵公式也使用这一水等效密度，效率另固定为0.75。二次比热3.8 kJ/(kg·K)和这项恒定密度共同构成合成工质代理；不能据此声称已经选择并标定某种水／乙二醇浓度。

### 2.2 换热与零流量分支

设备—二次回路热流为 $Q_r=U_r(T_r-T_p^s)$；$U_r=12(\dot m_r/6)^{0.8}\mu_r$。其中0.8指数和UA量级是本模型的经验形式设定，本轮没有找到为具体冷板几何与流态标定这些数值的依据。

二次热容流率 $C_p^s=c_s\sum_r\dot m_r$的单位为kW/K。返回温升取 $\sum_rQ_r/C_p^s$；**代码在 $C_p^s\le10^{-12}$ 时令该温升为0**。这时各支路流量为零的极限也使对应冷板导通量趋零。CDU采用 $Q_p^{\rm CDU}=\varepsilon_p\min(C_p^s,C_p^p)(T_p^{s,\rm ret}-T^p)$，其形式与P1的有效度表达相符；有效度及其故障乘子保持合成常数。温差变号时允许反向热流，代码没有仅允许制冷方向的截断。

每个pod二次回路用一个均匀集中温度表示，一次回路用全设施共享的均匀温度表示。这里是把空间混合压缩成集中状态，而非不发生混合；管道运输、空间温度分布和瞬态水力未显式分辨。

### 2.3 储能及电气余额

各集中状态均按 $T^+=T+\Delta t\,Q_{\rm net}/C$显式更新。代码中的 $Q$为kW、$C$为kJ/K、$\Delta t$为秒，因此增量为K。所有内部换热使用同一步旧状态计算，并以相反符号进入相邻储能节点。总储能可写为

$$
E=C_r\sum_rT_r+C_s\sum_pT_p^s+N_pC_pT^p+C_e\sum_pT_p^e.
$$

选择摄氏参考零点只给该储能加入常数，不影响 $\Delta E$。泵输入功率全部计入对应冷却热容，风机、IT及辅助转换损耗作为即时排热；这是热量去向的集中记账假设。内部冷板及CDU热流相消后，实现检查 $\Delta E=\Delta t(P_{\rm source}-Q_{\rm rejected})$。

接触电气损耗 $k_pX_p^2$中的 $k_p=1000R_p/(V^2\mathrm{pf}^2)$将kW输入转换为等效电流，再得到kW的焦耳热。供电上限通过 $X_p+k_pX_p^2\le A_p$的稳定二次根限制。该表示是固定效率和等效容量模型，不是三相潮流、UPS开关或谐波模型。

## 3 参数与测试应怎样表述

- 250 kW/机柜、四类热容、UA、0.70/0.75泵效率、3.8/4.18比热、故障乘子与时长、异常阈值、比例增益和20秒控制滞后均来自当前代码的合成配置；上述资料只为方程形式提供依据。设备温度是等效状态代理，没有单独标定成芯片结温或机房空气温度。
- 控制律是pod内最大传感温度驱动的截断比例目标，叠加一阶趋近；`control='feedback'`不表示本轮使用经过辨识／整定的真实PID。95°C断功率是过程自身的仿真保护，不是巡检策略的维修或控制贡献。
- `tests/test_facility.py`已有电气余额、总储能余额、泵—支路方程和故障方向性检查。步长减半只覆盖一个16机柜非故障开发条件；该用例允许温度绝对差0.5 K。守恒残差检查是离散实现的代数／数值一致性，不能升级为所有故障的收敛性或现场模型有效性。
- `process.py`在巡检前生成过程，并保存公开包和隐藏状态指纹；巡检策略改变观测和确认时机，不改变物理过程。这有利于固定场景内配对比较，也限定了对维修效果或闭环设施控制收益的解释。

代码来源：[facility.py](../../src/patrol_rsi/facility.py)，SHA256 `18b4a5f72809d799073a8e443c6e8e5a80e4d04e89e4660b3853edafb191724d`；[process.py](../../src/patrol_rsi/process.py)，SHA256 `ba499582a0feb524480b3aa587e8e6a623522fe0513452c0b175f39ead8e49a6`；[test_facility.py](../../tests/test_facility.py)，SHA256 `4c3143a2d2ba6a186136219de373c07a83494d8539e2febf229d2bfe0b81196b`。

## 4 可直接接入附录的短段落

本过程采用集中热容能量平衡、质量流量与比热构成的热容流率、有效度换热以及准稳态泵—支路曲线。ASHRAE传热手册为集中状态及换热形式提供基础，DOE与Hydraulic Institute资料为泵功率和相似关系提供基础[P1—P3]。设备容量、热容、故障乘子和控制参数取合成研究值，用于形成公开线索、短时异常及受约束确认之间可复核的时序问题；本文的守恒及步长检查验证实现的一致性，现场标定属于独立工作。

## 5 BibTeX候选

```bibtex
@incollection{ashrae2025heattransfer,
  author = {{ASHRAE}},
  title = {Heat Transfer},
  booktitle = {2025 ASHRAE Handbook---Fundamentals},
  chapter = {4},
  year = {2025},
  url = {https://handbook.ashrae.org/Handbooks/F25/IP/F25_Ch04/F25_Ch04_ip.aspx},
  note = {Official IP edition, Lumped Mass Analysis and NTU-Effectiveness sections; accessed 2 November 2026}
}
@techreport{doe2006pumping,
  author = {{U.S. Department of Energy} and {Hydraulic Institute}},
  title = {Improving Pumping System Performance: A Sourcebook for Industry},
  edition = {2},
  institution = {U.S. Department of Energy},
  year = {2006},
  month = may,
  url = {https://www.energy.gov/sites/default/files/2014/05/f16/pump.pdf},
  note = {Printed pages 9, 48, 51--52; developed by DOE and HI}
}
@misc{hi2024pumpcurves,
  author = {{Hydraulic Institute}},
  title = {Pump Curves},
  howpublished = {HI Data Tool, Pump Fundamentals},
  year = {2024},
  url = {https://datatool.pumps.org/pump-fundamentals/pump-curves.html},
  note = {Last updated 19 July 2024; equations 1.B.3--1.B.6; accessed 2 November 2026}
}
```
