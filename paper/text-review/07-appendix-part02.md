> 正文审阅版：正文、公式和数值表与单文件HTML同源；图版保留SVG链接，便于文本工具读取。

> 6. 技术附录 · 第2/3部分。

[下一部分](07-appendix-part03.md)

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
