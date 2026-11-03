> 正文审阅版：正文、公式和数值表与单文件HTML同源；图版保留SVG链接，便于文本工具读取。

> 4. 实验结果 · 第2/3部分。

[下一部分](05-comparison-part03.md)

#### 4.3.2 新基准总表、四专业与配对效应

<div class="table-guide" id="table-supplement-errors"><div class="exhibit-intro" data-guide-table="supplement-errors"><p class="exhibit-title"><span class="exhibit-number">表 11</span> <strong>各方案按自身巡检记录得到的温度误差</strong></p><p class="exhibit-purpose">查看完整系统运行后，路线、量测时机和估计器共同形成的状态精度。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>每行是一个估计＋派单组合；↑/↓沿用指标方向，最后一列说明确定性规则或3个模型种子重复。各行使用该方案自己完成的量测流，输入会随路线变化。</p><p><strong>◇ 读到什么：</strong>本表评价闭环系统的温度结果；前一张共同观测流表用于单独比较估计器，两种比较相互补充。</p></div></div>
<div class="table-wrap"><table data-table="supplement-errors" class="supplement-table"><thead><tr><th>方法</th><th>RMSE / °C↓</th><th>加权RMSE / °C↓</th><th>R²↑</th><th>盲区机柜加权RMSE / °C↓</th><th>模型／规则重复</th></tr></thead><tbody><tr data-supplement-method="nominal_tour"><td>名义＋Tour</td><td>0.528</td><td>0.535</td><td>0.9124</td><td>0.443</td><td>1个确定性规则</td></tr><tr data-supplement-method="nominal_fifo"><td>名义＋FIFO</td><td>0.532</td><td>0.535</td><td>0.9113</td><td>0.443</td><td>1个确定性规则</td></tr><tr data-supplement-method="nominal_greedy"><td>名义＋Greedy</td><td>0.533</td><td>0.537</td><td>0.9105</td><td>0.446</td><td>1个确定性规则</td></tr><tr data-supplement-method="nominal_ppo"><td>名义＋PPO</td><td>0.531</td><td>0.537</td><td>0.9112</td><td>0.445</td><td>3个独立训练种子</td></tr><tr data-supplement-method="cvae_fifo"><td>CVAE＋FIFO</td><td>0.323</td><td>0.327</td><td>0.9603</td><td>0.170</td><td>3个独立训练种子</td></tr><tr data-supplement-method="cvae_greedy"><td>CVAE＋Greedy</td><td>0.323</td><td>0.327</td><td>0.9602</td><td>0.171</td><td>3个独立训练种子</td></tr><tr data-supplement-method="cvae_ppo"><td>CVAE＋PPO</td><td>0.323</td><td>0.327</td><td>0.9602</td><td>0.171</td><td>3个独立训练种子</td></tr></tbody></table></div>
<div class="table-guide" id="table-supplement-tasks"><div class="exhibit-intro" data-guide-table="supplement-tasks"><p class="exhibit-title"><span class="exhibit-number">表 12</span> <strong>七方案究竟查到多少、付出多少代价</strong></p><p class="exhibit-purpose">用一张总表核对异常确认、例行覆盖与额外成本。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>确认a/210以唯一异常段为分母；每条件确认及区间以48个故障条件和12个独立测试组汇总。学习方案的小数来自模型种子平均。移动/完成量以Tour为基准，+表示增加、−表示减少；等待和年龄都取↓。</p><p><strong>◇ 读到什么：</strong>名义FIFO确认155/210，相比Tour的94/210更多，同时移动＋0.34%、完成量−0.15%、年龄略升；约束违规均为0。</p></div></div>
<div class="table-wrap"><table data-table="supplement-tasks" class="supplement-table"><thead><tr><th>方法</th><th>确认／唯一异常段</th><th>确认比例</th><th>每条件确认 [95%CI]</th><th>截尾等待 / 秒↓</th><th>加权年龄↓</th><th>移动相对Tour</th><th>完成量相对Tour</th><th>约束违规</th></tr></thead><tbody><tr data-supplement-method="nominal_tour"><td>名义＋Tour</td><td>94/210</td><td>44.8%</td><td>1.96 [1.31, 2.65]</td><td>106.75</td><td>0.310122</td><td>+0.00%</td><td>+0.00%</td><td>0</td></tr><tr data-supplement-method="nominal_fifo"><td>名义＋FIFO</td><td>155/210</td><td>73.8%</td><td>3.23 [2.83, 3.65]</td><td>94.24</td><td>0.311298</td><td>+0.34%</td><td>-0.15%</td><td>0</td></tr><tr data-supplement-method="nominal_greedy"><td>名义＋Greedy</td><td>154/210</td><td>73.3%</td><td>3.21 [2.81, 3.60]</td><td>94.36</td><td>0.311270</td><td>+0.34%</td><td>-0.15%</td><td>0</td></tr><tr data-supplement-method="nominal_ppo"><td>名义＋PPO</td><td>129.33/210</td><td>61.6%</td><td>2.69 [2.23, 3.17]</td><td>100.42</td><td>0.310877</td><td>+0.22%</td><td>-0.10%</td><td>0</td></tr><tr data-supplement-method="cvae_fifo"><td>CVAE＋FIFO</td><td>153/210</td><td>72.9%</td><td>3.19 [2.78, 3.61]</td><td>94.55</td><td>0.311256</td><td>+0.33%</td><td>-0.14%</td><td>0</td></tr><tr data-supplement-method="cvae_greedy"><td>CVAE＋Greedy</td><td>152/210</td><td>72.4%</td><td>3.17 [2.76, 3.58]</td><td>94.64</td><td>0.311217</td><td>+0.32%</td><td>-0.14%</td><td>0</td></tr><tr data-supplement-method="cvae_ppo"><td>CVAE＋PPO</td><td>153.67/210</td><td>73.2%</td><td>3.20 [2.78, 3.62]</td><td>94.65</td><td>0.311266</td><td>+0.33%</td><td>-0.14%</td><td>0</td></tr></tbody></table></div>


<a id="figure-supplement-methods"></a>

<div class="exhibit-intro" data-guide-figure="supplement-methods"><p class="exhibit-title"><span class="exhibit-number">图 12</span> <strong>七种方案在确认、等待和例行覆盖上的取舍</strong></p><p class="exhibit-purpose">同时查看“多查到异常”和“是否耽误例行检查”，避免用单个指标代替全部任务效果。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-methods.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>每行是一种方案，三列分别为每故障条件确认段数↑、后果加权截尾等待秒数↓、加权归一年龄↓。横向比较同一列，区间线表示95%测试组自举区间；三列单位不同，不能直接比较柱长。年龄越高表示例行检查平均更久未更新。</p><p><strong>◇ 读到什么：</strong>名义FIFO比Tour确认更多、等待更短，同时年龄略有上升；这张图把收益和例行覆盖的代价放在一起。</p></div><p class="exhibit-source">48个故障条件，先平均三个模型种子、再等权四故障族；误差线按12组独立测试集计算95%区间。等待对有异常的条件计算。</p>




<a id="figure-supplement-professions"></a>

<div class="exhibit-intro" data-guide-figure="supplement-professions"><p class="exhibit-title"><span class="exhibit-number">图 13</span> <strong>确认收益主要来自哪个专业</strong></p><p class="exhibit-purpose">把总确认数拆开，查看热、电气、制冷和自控是否得到相同改善。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-professions.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>四幅图使用相同百分比横轴，但专业分母依次是162、12、24、12段。行内a/b表示确认段数/该专业异常总段数，柱越长表示确认比例越高；学习方法的小数来自三个模型种子的平均。</p><p><strong>◇ 读到什么：</strong>方法差异主要出现在热检查和制冷；电气均为12/12，自控均为8/12。先看分母，再判断某专业的百分比与总量贡献。</p></div><p class="exhibit-source">四专业异常段的描述性确认比例，数字为确认数／专业异常总数；小数来自三个模型种子的平均。</p>



48个主要条件共210段唯一异常。学习方法确认总数的小数来自三个模型种子的平均；闭环误差使用各方法自身的量测流，同流估计结果则使用4.2节的共同输入。

名义FIFO相对Tour新增61段有效确认，截尾等待从106.75缩短至94.24秒，移动增加0.34%、完成量下降0.15%；整体加权年龄从0.310122升至0.311298。各方法资格、预约、预算和初终点重访审计均为0违规。

三个模型种子平均后，CVAE-FIFO、CVAE-Greedy和CVAE-PPO分别确认153、152和153.67段，均未超过名义FIFO的155段。方法差异集中在热检查与制冷；电气均为12/12，自控均为8/12；在当前观测与专业完成时机设置下，这两类结果在方法间一致。



<a id="figure-supplement-contrasts"></a>

<div class="exhibit-intro" data-guide-figure="supplement-contrasts"><p class="exhibit-title"><span class="exhibit-number">图 14</span> <strong>把方案差异直接画成A−B</strong></p><p class="exhibit-purpose">判断收益方向和不确定性，而不是只凭两个方案各自的均值猜测差异。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-contrasts.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>每行按名称计算Δ＝前者−后者，竖直0线表示无数值差。左图确认增量↑，点在右侧为更多确认；右图年龄变化↓，点在左侧为更及时的例行覆盖。横线是对应配对差的95%区间，跨0表示本批数据仍容许两种方向。</p><p><strong>◇ 读到什么：</strong>名义FIFO相对Tour有明确的确认增量；CVAE-PPO相对CVAE-FIFO的确认区间跨0。CVAE-PPO与名义PPO之差同时包含估计器和各自策略训练的变化。</p></div><p class="exhibit-source">预登记的配对比较，按独立测试集自举计算95%区间。确认、等待、年龄与误差分别解释；区间不包含完整训练不确定性。</p>


<div class="table-guide" id="table-supplement-contrasts"><div class="exhibit-intro" data-guide-table="supplement-contrasts"><p class="exhibit-title"><span class="exhibit-number">表 13</span> <strong>预先选定的方案差有多大</strong></p><p class="exhibit-purpose">直接阅读同条件配对后的增量及其方向。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>每行按Δ＝前者−后者计算；例如＋1.27段/条件表示前者平均多确认1.27段。方括号为对应差值的95%区间，确认看↑，等待/年龄/误差看↓；带符号的数不能只按正负判断好坏。</p><p><strong>◇ 读到什么：</strong>名义FIFO的确认增量区间在0以上；CVAE-PPO相对CVAE-FIFO的区间跨0，因此这批结果尚未明确给出学习派单增量。</p></div></div>
<div class="table-wrap"><table data-table="supplement-contrasts" class="supplement-table"><thead><tr><th>预登记比较</th><th>每条件确认差↑</th><th>截尾等待差 / 秒↓</th><th>归一年龄差↓</th><th>闭环加权RMSE差 / °C↓</th></tr></thead><tbody><tr><td>名义＋FIFO − 名义＋Tour</td><td>+1.27 [+0.62, +1.88]</td><td>-12.51 [-16.31, -8.75]</td><td>+0.001176 [+0.001052, +0.001292]</td><td>+0.001 [-0.053, +0.052]</td></tr><tr><td>CVAE＋FIFO − 名义＋FIFO</td><td>-0.04 [-0.09, +0.00]</td><td>+0.31 [+0.02, +0.70]</td><td>-0.000042 [-0.000072, -0.000015]</td><td>-0.208 [-0.311, -0.111]</td></tr><tr><td>CVAE＋Greedy − 名义＋Greedy</td><td>-0.04 [-0.09, +0.00]</td><td>+0.28 [+0.00, +0.67]</td><td>-0.000053 [-0.000093, -0.000021]</td><td>-0.210 [-0.314, -0.112]</td></tr><tr><td>名义＋PPO − 名义＋FIFO</td><td>-0.53 [-0.79, -0.26]</td><td>+6.18 [+4.23, +8.19]</td><td>-0.000421 [-0.000475, -0.000362]</td><td>+0.002 [-0.015, +0.018]</td></tr><tr><td>CVAE＋PPO − CVAE＋FIFO</td><td>+0.01 [-0.01, +0.04]</td><td>+0.10 [-0.15, +0.39]</td><td>+0.000010 [-0.000005, +0.000028]</td><td>+0.000 [-0.000, +0.000]</td></tr><tr><td>CVAE＋PPO − 名义＋PPO</td><td>+0.51 [+0.22, +0.78]</td><td>-5.77 [-7.59, -4.01]</td><td>+0.000389 [+0.000320, +0.000454]</td><td>-0.210 [-0.310, -0.115]</td></tr></tbody></table></div>

名义FIFO−Tour每主要条件净增+1.27 [+0.62, +1.88]段；CVAE-FIFO−名义FIFO为-0.04 [-0.09, +0.00]段；CVAE-PPO−CVAE-FIFO为+0.01 [-0.01, +0.04]段。区间表达物理种子块变化，[附录G](07-appendix-part03.md#training-seeds)另列训练种子离散程度。

#### 4.3.3 健康、虚假提示与计算耗时

<div class="table-guide" id="table-supplement-healthy"><div class="exhibit-intro" data-guide-table="supplement-healthy"><p class="exhibit-title"><span class="exhibit-number">表 14</span> <strong>正常运行或虚假提示会带来多少额外工作</strong></p><p class="exhibit-purpose">检查系统会不会在没有评价异常时增加访问或产生错误确认。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>每个数是对应12个条件的平均；分别比较健康与虚假提示的额外访问、误确认。NA表示该组没有异常段，确认比例和异常等待不适用。额外访问与误确认是两列不同的结果。</p><p><strong>◇ 读到什么：</strong>健康组均无额外访问和误确认；虚假提示使部分方案平均多访问0.75次/条件，但专业误确认为0。</p></div></div>
<div class="table-wrap"><table data-table="supplement-healthy" class="supplement-table"><thead><tr><th>方法</th><th>健康额外访问</th><th>虚假提示额外访问</th><th>健康误确认</th><th>虚假提示误确认</th><th>虚假提示完成量相对Tour</th><th>两组确认比例／等待</th></tr></thead><tbody><tr><td>名义＋Tour</td><td>0.00</td><td>0.00</td><td>0.00</td><td>0.00</td><td>+0.00%</td><td>NA / NA</td></tr><tr><td>名义＋FIFO</td><td>0.00</td><td>0.75</td><td>0.00</td><td>0.00</td><td>-0.04%</td><td>NA / NA</td></tr><tr><td>名义＋Greedy</td><td>0.00</td><td>0.75</td><td>0.00</td><td>0.00</td><td>-0.04%</td><td>NA / NA</td></tr><tr><td>名义＋PPO</td><td>0.00</td><td>0.42</td><td>0.00</td><td>0.00</td><td>-0.02%</td><td>NA / NA</td></tr><tr><td>CVAE＋FIFO</td><td>0.00</td><td>0.75</td><td>0.00</td><td>0.00</td><td>-0.04%</td><td>NA / NA</td></tr><tr><td>CVAE＋Greedy</td><td>0.00</td><td>0.75</td><td>0.00</td><td>0.00</td><td>-0.04%</td><td>NA / NA</td></tr><tr><td>CVAE＋PPO</td><td>0.00</td><td>0.75</td><td>0.00</td><td>0.00</td><td>-0.04%</td><td>NA / NA</td></tr></tbody></table></div>

健康与虚假提示各12条件。无评价异常时确认比例与异常等待为NA，额外访问及误确认按实测保留。所有方法在健康组均无额外访问和误确认。虚假提示下，FIFO、Greedy及CVAE-PPO平均各增加0.75次访问／条件，名义PPO为0.42次；这些跟进没有造成错误的专业确认。



<a id="figure-supplement-latency"></a>

<div class="exhibit-intro" data-guide-figure="supplement-latency"><p class="exhibit-title"><span class="exhibit-number">图 15</span> <strong>估计和派单各花多少计算时间</strong></p><p class="exhibit-purpose">比较引入神经估计或PPO后，单轮计算的主要代价来自哪一阶段。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-latency.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>左图为温度估计阶段，右图为候选准备与派单阶段，横轴都为毫秒ms、方向↓；两幅图刻度不同。数值先在每回合求p95，再对主要条件汇总取平均，因此读作“逐回合p95的平均”。</p><p><strong>◇ 读到什么：</strong>CVAE主要增加估计计算，PPO主要增加派单计算。完整周期还包含执行记账与下一观测等操作，估计已经包含其中，应结合耗时表阅读。</p></div><p class="exhibit-source">主要故障条件的逐回合p95均值，实测包含转换和CUDA同步。估计阶段已包含于完整控制周期，不能重复相加。</p>


<div class="table-guide" id="table-supplement-latency"><div class="exhibit-intro" data-guide-table="supplement-latency"><p class="exhibit-title"><span class="exhibit-number">表 15</span> <strong>单轮估计、派单和完整周期的实测耗时</strong></p><p class="exhibit-purpose">把阶段计算代价与完整一轮的时间放在同一张表中。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>单位为毫秒ms，p50为中位数，p95为95百分位；先逐回合计算，再汇总取平均。完整周期包含估计阶段，并由完整周期记录单独求分位数，阶段p95不可直接相加。</p><p><strong>◇ 读到什么：</strong>名义FIFO完整周期p95均值为1.47 ms，CVAE-PPO为8.10 ms；这是本次硬件与测量边界内的统计值。</p></div></div>
<div class="table-wrap"><table data-table="supplement-latency" class="supplement-table"><thead><tr><th>方法</th><th>估计p50 / ms</th><th>估计p95 / ms</th><th>派单p50 / ms</th><th>派单p95 / ms</th><th>完整周期p95 / ms</th></tr></thead><tbody><tr><td>名义＋Tour</td><td>0.17</td><td>0.23</td><td>0.45</td><td>0.90</td><td>1.53</td></tr><tr><td>名义＋FIFO</td><td>0.17</td><td>0.22</td><td>0.44</td><td>0.86</td><td>1.47</td></tr><tr><td>名义＋Greedy</td><td>0.17</td><td>0.22</td><td>0.44</td><td>0.87</td><td>1.48</td></tr><tr><td>名义＋PPO</td><td>0.18</td><td>0.24</td><td>1.28</td><td>2.95</td><td>3.59</td></tr><tr><td>CVAE＋FIFO</td><td>3.69</td><td>5.44</td><td>0.47</td><td>0.93</td><td>6.59</td></tr><tr><td>CVAE＋Greedy</td><td>3.53</td><td>5.07</td><td>0.48</td><td>0.95</td><td>6.27</td></tr><tr><td>CVAE＋PPO</td><td>3.63</td><td>5.34</td><td>1.31</td><td>3.00</td><td>8.10</td></tr></tbody></table></div>

硬件为NVIDIA GeForce RTX 4060 Laptop GPU，PyTorch 2.6.0＋CUDA 12.4、PyTorch CPU线程数2。上表是主要条件逐回合p50／p95的平均；神经估计包括转换、设备复制、前向、取回及CUDA同步，每次加载先做5次预热。完整周期包含选择、执行记账、下一观测估计和事件生命周期；物理轨迹预生成、记录、I/O与评分另计，估计阶段已包含于完整周期。

### 4.4 估计精度、队列时序与学习空间诊断

#### 4.4.1 连续重构误差与离散确认机会

CVAE-U-Net改善全局温度态势精度，及时确认还取决于局部提示、FIFO队列和合法访问的完成时机。原日志144组配对中，CVAE-FIFO新增2段、丢失8段，模型平均后净少2段，与155→153一致。

在`test04-cooling`、模型271中，CVAE将45号提示从860秒提前至840秒，但41号更早在835秒入队。860秒两候选均合法，CVAE-FIFO先查41号并在880秒确认，再于900秒检查45号，错过850—890秒评价段；名义FIFO在875秒确认45号、895秒才检查41号。这里出现一增一失的机会交换，完整时序见[附录H](07-appendix-part03.md#gap-diagnosis)。

#### 4.4.2 合法候选稀疏与PPO排序自由度

PPO只有在几项任务都允许执行时，才有机会体现先后排序的差别。训练记录中，约0.26%—0.27%的巡检员实际选择集合包含多个合法候选；只有一项可选时，策略没有排序空间。这个比例按每名执行者实际收到的选择集合计算，反映本轮责任区、返回保护和待办生成共同形成的机会，完整计数见[附录G](07-appendix-part03.md#training-seeds)。

在每策略120回合预算下，CVAE-PPO相对CVAE-FIFO的确认增量区间跨零；相对名义PPO的改善同时包含估计器与各自训练策略的变化。候选空间、奖励和训练预算的单独贡献可在下一轮独立比较中检验。
