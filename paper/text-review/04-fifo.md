> 正文审阅版：正文、公式和数值表与单文件HTML同源；图版保留SVG链接，便于文本工具读取。

<a id="fifo"></a>

## 3. 巡检机制与历史闭环基准

第一阶段采用<strong>名义估计＋返回保护FIFO</strong>作为机制基准。FIFO（First In, First Out，先入先出）在执行者空闲时，从本人合法风险请求中选择最早出现的一项；资格、预约、预算和返回时间先行核查，原例行循环持续保留。

每回合为1800秒、18名执行者，全体额外访问上限12次，请求待派有效期120秒。



<a id="figure-inspection-architecture"></a>

[图：根据本项目已实现接口重绘总体架构；上方在线决策只用公开信息，下方真值与日志用于事后评分。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/inspection-architecture.svg)



临时加查前，程序计算“现在出发、完成加查、返回并完成原任务”是否赶上截止，并逐项核对完整所属循环：

<div class="formula-scroll"><p class="formula" role="math">t + τ(p,x) + τ(x,r) ≤ L<sub>r</sub> + D<sub>r</sub>；对完整循环每项F<sub>j</sub> ≤ L′<sub>j</sub> + D<sub>j</sub></p></div>

τ包含移动和目的任务服务，L为上次完成时刻、D为最大重访间隔；额外加查x与原定下一项r分别计账。完整取整、初始时刻和返回证书例子见附录B。

### 工况A：供电可用性下降引发热—冷传播

本批12个配对过程统一注入辅助馈电故障与CDU换热衰减，持续180秒；通过不同种子、目标设备组和开始时刻比较。辅助供电乘子为0.05、CDU换热乘子为0.20，形成77段热异常和12段制冷异常。电气接触温升及传感偏差仍按各自专业检查，但这批故障的评价段集中在热和制冷。

本次独立补充基准另行覆盖接触热点、传感偏差与二次泵故障，见第4节；RGB参考融合属于视觉支路后续验证。历史工况A的12行配置、四专业阈值和原件保持可回查。



<a id="figure-confirmations"></a>

[图：当前机房任务：12个主过程，共89段异常；三列为各策略的有效确认量。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/confirmations.svg)



FIFO相对固定巡回新增45段、丢失3段，净增42段，平均每过程净增3.50段；探索性95%自举区间为[2.42,4.50]。硬重访、资格与预约违规均为0。此结果建立了<strong>耦合过程—部分观测—风险请求—受保护执行—专业确认</strong>的闭环基准。



<a id="figure-outcome-costs"></a>

[图：本项目12个主过程的FIFO相对Tour比较；区间、代价与探索性门槛均来自封存记录。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/outcome-costs.svg)



同权限的九个预登记响应／暂缓规则确认28—60段，最好两条均为60，低于FIFO的70。记录显示，高风险门槛压掉了加查，固定等待门槛也会改变短异常窗口内的检查机会。正文将它们作为开发对照；得分式、具体得失及原轨迹图保留在附录C。

<aside class="scope-note"><p><strong>验证单位：</strong>12是配对物理过程数，89是其中的连续异常段数。专业确认沿用原包5秒采样端点评价；一次测量需告警且落在原标签的有效采样端点。九规则来自同12个已见过程的开发比较，模型调用与训练均为0。</p></aside>
