> 正文审阅版：正文、公式和数值表与单文件HTML同源；图版保留SVG链接，便于文本工具读取。

> 6. 技术附录 · 第1/3部分。

[下一部分](07-appendix-part02.md)

<a id="appendix"></a>

## 6. 技术附录与可追溯原件

<p class="chapter-lead">具体案例、历史对照、训练细节与原件索引集中在这里，供需要进一步核查时按项查阅。</p>

### 6.1 历史回看、执行记录与详细对照

以下材料保留历史基准、逐步核算及分组结果，正文以第4章的新留出比较为主。


<h4 id="engineering-history">附录 A. 500秒工程回看与原风险分布</h4>

本例来自已保存的固定巡回工程过程。估计／事后温度共用45—75°C色标；红框标出原风险分>0的64、67、70号柜，黑点为32个固定温度点。它与正文新测试案例00分别记账，名义递推原理见[2.2.1节](03-hotspots.md#principle-estimation)。



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

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>仍按同一组/机柜位置读图；色标数值是无量纲风险分r，黑点标出32个固定测温位置。r&gt;0触发待确认请求，具体分数结合温度越界与功率缺口计算；本帧色标范围只用于显示这一帧。</p><p><strong>◇ 读到什么：</strong>风险分提供核查线索，既不是℃数值，也不是故障概率；是否有效确认，最终要看专业量测和完成时机。</p></div><p class="exhibit-source">已有工程回看：固定巡回，500秒；风险分由公开观测和名义估计计算。</p>


<div class="table-guide" id="table-hotspot-values"><div class="exhibit-intro" data-guide-table="hotspot-values"><p class="exhibit-title"><span class="exhibit-number">表 19</span> <strong>历史热风险位置的估计值与事后值</strong></p><p class="exhibit-purpose">给红框机柜的温度图补上准确数值，便于检查估计差异。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>按柜号定位64、67、70号，再并排比较T̂名义估计与T事后代表温度，单位均为°C；风险分r另用无量纲数值。最后一列说明该柜是否具有固定温度遥测。</p><p><strong>◇ 读到什么：</strong>同一风险框可同时查看温度估计、事后值和观测条件；风险分的大小还结合了功率缺口。</p></div></div>
<div class="table-wrap"><table data-table="hotspot-values"><thead><tr><th>机柜</th><th>当时公开风险分</th><th>名义估计温度／°C</th><th>事后代表温度／°C</th><th>固定温度遥测点</th></tr></thead><tbody><tr><td>64</td><td>0.1296</td><td>67.35</td><td>67.63</td><td>是</td></tr><tr><td>67</td><td>0.2623</td><td>69.58</td><td>69.53</td><td>否</td></tr><tr><td>70</td><td>0.1323</td><td>67.36</td><td>67.31</td><td>否</td></tr></tbody></table></div>

<h4 id="fifo-detail">附录 B. FIFO队列与完整返回核算实例</h4>

任务契约和证书公式见[3.1节](04-fifo.md#principle-return)。下列历史记录说明例行账与风险账如何共同执行。



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
