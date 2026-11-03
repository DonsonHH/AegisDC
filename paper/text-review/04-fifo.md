> 正文审阅版：正文、公式和数值表与单文件HTML同源；图版保留SVG链接，便于文本工具读取。

<a id="fifo"></a>

## 3. 巡检决策层：受返回时间保护的多专业派单

<p class="chapter-lead">决策层维护例行巡回与风险待办两套任务，在资格、预约、预算和完整循环重访约束下选择下一项检查。</p>

### 3.1 闭环架构与执行契约

#### 3.1.1 四专业契约与两本任务账

每回合为1800秒，共18名执行者；四专业的测量对象、人数、服务耗时和重访期限如下。例行账维持持续覆盖，事件账记录新出现且尚未完成专业核查的风险请求。

<div class="table-wrap"><table data-table="task-contract"><thead><tr><th>专业</th><th>完成检查后得到什么</th><th>人数</th><th>每次服务</th><th>最大重访间隔</th></tr></thead><tbody><tr><td>热检查</td><td>该机柜代表温度</td><td>12</td><td>10秒</td><td>300秒</td></tr><tr><td>电气检查</td><td>该组电气接触温度</td><td>2</td><td>20秒</td><td>600秒</td></tr><tr><td>制冷检查</td><td>该组冷却液流量</td><td>2</td><td>20秒</td><td>600秒</td></tr><tr><td>自控检查</td><td>传感读数误差（完成校验后）</td><td>2</td><td>15秒</td><td>600秒</td></tr></tbody></table></div>


<a id="figure-inspection-architecture"></a>

[图：根据本项目已实现接口重绘总体架构；上方在线决策只用公开信息，下方真值与日志用于事后评分。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/inspection-architecture.svg)



请求待派有效期为120秒，全体额外访问上限12次。额外加查保留原例行指针；派出时占用预算和预约，实际完成后以专业量测更新观测与任务账本。

#### 3.1.2 完整循环返回证书

批准加查前，程序预测当前候选与原循环所有后续任务的完成时刻，确认候选自身、完整返回循环和重复周期均满足期限。

<div class="principle-box" id="principle-return"><p class="principle-title">完整返回核算</p><div class="formula-scroll"><p class="formula" role="math">t + τ(p,x) + τ(x,r) ≤ L<sub>r</sub> + D<sub>r</sub>；τ(a,b) = 5⌈[d(a,b)/v + s<sub>b</sub>]/5⌉</p><p class="formula" role="math">对完整循环：F<sub>j</sub> ≤ L′<sub>j</sub> + D<sub>j</sub>；最小余量≥0</p></div><p>此简式取额外加查x与原任务r不同。τ包括目的任务服务，v＝1 m/s；首次未检的L按0起算，L′随预计访问更新。程序核查候选自身、完整循环及重复周期；每次实际完成后重新选择。</p></div>

### 3.2 共同合法候选集合下的策略族

#### 3.2.1 固定Tour与先入先出FIFO

Tour执行原定所属循环。FIFO（First In, First Out，先入先出）在执行者空闲时，从“本人例行下一项＋本人待确认请求”中先筛出合法候选，再选择首次提示最早的事件；没有合法事件时执行例行头。所有响应方法共用资格、预约、返回、终点与预算检查。

#### 3.2.2 即时Greedy与响应／暂缓规则

Greedy在所有合法候选中最大化“当前公开风险／取整完成耗时”，平分时依次优先例行项、较早提示和较小任务编号。响应／暂缓线性规则则先由FIFO选定一个合法事件，再在该事件与例行头之间二选一；规则表达式与历史开发结果见[附录C](07-appendix.md#historical-benchmark)。

#### 3.2.3 共享PPO策略

PPO使用21维公开候选特征和32×32共享actor，在同一合法集合内选择；仅训练使用10维公开全局特征critic。特征涵盖专业、公开严重度、年龄、ETA、量测状态、等待、预算和返回余量，执行者按固定编号依次决策。



<a id="figure-supplement-crossed-design"></a>

[图：估计器与调度器的共同候选、约束和执行接口。PPO使用公开奖励训练，原始异常标签留给离线评价。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-crossed-design.svg)



训练采用公开观测奖励的[PPO裁剪目标](https://arxiv.org/abs/1707.06347)：每个完整359步回合更新4轮，学习率0.0003，γ＝0.99、GAE λ＝0.95、clip＝0.2。名义／CVAE条件下的配对种子采用相同初始参数和案例次序，各策略固定使用第120回合checkpoint。

### 3.3 观测、物理过程与评价边界

同一条件下，各方法共享由本地控制器推进并预先生成的供电、温度与流量轨迹。巡检改变路线、专业量测时机和后续估计，设备状态按该本地控制轨迹演化。在线选择使用公开观测，异常标签和未来端点用于回合后的评分；实际分配、完成及初终点重访间隔进入独立审计。
