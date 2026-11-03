> 正文审阅版：正文、公式和数值表与单文件HTML同源；图版保留SVG链接，便于文本工具读取。

<a id="fifo"></a>

## 3. 巡检决策层：受返回时间保护的多专业派单

<p class="chapter-lead">有了风险线索，接下来要决定派谁去、先查哪里。18名巡检员在各自专业与责任区内完成核查，每次加查前都要算清能否及时返回例行路线，保证原有检查不超时。</p>

### 3.1 闭环架构与执行契约

#### 3.1.1 四专业契约与两本任务账

每个模拟回合持续1800秒，共18名巡检员。12名测机柜温度，电气、制冷和自控各2名，分别检查接点温度、组流量和传感偏差。“重访期限”是同一任务相邻两次检查允许的最长间隔，热检查为300秒，其他专业为600秒；具体分工与服务耗时如下。系统分别保存例行检查进度和风险待办，避免加查打乱原有责任。

<div class="table-wrap"><table data-table="task-contract"><thead><tr><th>专业</th><th>完成检查后得到什么</th><th>人数</th><th>每次服务</th><th>最大重访间隔</th></tr></thead><tbody><tr><td>热检查</td><td>该机柜代表温度</td><td>12</td><td>10秒</td><td>300秒</td></tr><tr><td>电气检查</td><td>该组电气接触温度</td><td>2</td><td>20秒</td><td>600秒</td></tr><tr><td>制冷检查</td><td>该组冷却液流量</td><td>2</td><td>20秒</td><td>600秒</td></tr><tr><td>自控检查</td><td>传感读数误差（完成校验后）</td><td>2</td><td>15秒</td><td>600秒</td></tr></tbody></table></div>


<a id="figure-inspection-architecture"></a>

[图：根据本项目已实现接口重绘总体架构；上方在线决策只用公开信息，下方真值与日志用于事后评分。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/inspection-architecture.svg)



风险请求等待派单的有效期为120秒，全体额外访问上限12次。加查保留原例行任务的执行顺序；派出时占用访问额度并预约目标，检查完成后以专业量测更新温度或流量等观测，并记录结果。

#### 3.1.2 完整循环返回证书

能否加查，先看回来后还赶不赶得上例行任务。程序预测加查及原路线所有后续任务的完成时刻，逐项核对期限，并检查重复巡回是否仍可持续；这份核算结果称为“返回证书”。

<div class="principle-box" id="principle-return"><p class="principle-title">完整返回核算</p><div class="formula-scroll"><p class="formula" role="math">t + τ(p,x) + τ(x,r) ≤ L<sub>r</sub> + D<sub>r</sub>；τ(a,b) = 5⌈[d(a,b)/v + s<sub>b</sub>]/5⌉</p><p class="formula" role="math">对完整循环：F<sub>j</sub> ≤ L′<sub>j</sub> + D<sub>j</sub>；最小余量≥0</p></div><p>此简式取额外加查x与原任务r不同。τ包括目的任务服务，v＝1 m/s；首次未检的L按0起算，L′随预计访问更新。程序核查候选自身、完整循环及重复周期；每次实际完成后重新选择。</p></div>

### 3.2 共同合法候选集合下的策略族

#### 3.2.1 固定Tour与先入先出FIFO

Tour按原定路线循环检查。FIFO（First In, First Out，先入先出）在巡检员空闲时，从“原定下一项例行任务＋本人风险待办”中筛出当前允许执行的任务，优先处理最早出现的风险请求；没有可执行的风险请求时，继续原定下一项例行任务。所有响应方法共用资格、预约、返回、回合结束时的重访核查与访问额度检查。

#### 3.2.2 即时Greedy与响应／暂缓规则

Greedy优先处理风险高、预计完成时间短的任务，具体比较“当前公开风险／取整完成耗时”，平分时依次优先例行项、较早提示和较小任务编号。响应／暂缓线性规则则先由FIFO选定一个合法事件，再在该事件与原定下一项例行任务之间二选一；规则表达式与历史开发结果见[附录C](07-appendix.md#historical-benchmark)。

#### 3.2.3 共享PPO策略

PPO尝试从训练中学会：当几项任务都允许执行时，先查哪一项。选择网络（actor）读取21维公开候选特征，使用32×32共享网络；训练时另用10维公开全局特征的评价网络（critic）。特征包括专业、风险、距上次检查的时间、预计到达时间、量测状态、等待时间、访问额度和返回余量，巡检员按固定编号依次决策。



<a id="figure-supplement-crossed-design"></a>

[图：估计器与调度器的共同候选、约束和执行接口。PPO使用公开奖励训练，原始异常标签留给离线评价。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-crossed-design.svg)



训练采用公开观测奖励的[PPO裁剪目标](https://arxiv.org/abs/1707.06347)：每个完整359步回合更新4轮，学习率0.0003，γ＝0.99、GAE λ＝0.95、clip＝0.2。名义／CVAE条件下的配对种子采用相同初始参数和案例次序，各策略固定使用第120回合checkpoint。

### 3.3 观测、物理过程与评价边界

同一故障条件下，各方法面对相同的供电、温度与流量变化，设备由本地控制器调节。巡检决定走哪条路线、何时测量和怎样更新估计；本轮巡检动作是核查，设备仍按共同的本地控制过程运行。派单只使用当时已经收到的信息，完整故障过程留到回合结束后评分；同时逐项核对实际分配、完成和检查间隔。
