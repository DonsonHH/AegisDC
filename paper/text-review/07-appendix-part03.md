> 正文审阅版：正文、公式和数值表与单文件HTML同源；图版保留SVG链接，便于文本工具读取。

> 6. 技术附录 · 第3/3部分。

#### 附录 F. 新基准逐故障族结果

<div class="table-guide" id="table-supplement-families"><div class="exhibit-intro" data-guide-table="supplement-families"><p class="exhibit-title"><span class="exhibit-number">表 24</span> <strong>各类故障下的方法差异</strong></p><p class="exhibit-purpose">查看总体确认差主要出现在哪类故障，而不只看合并均值。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>先固定同一故障族，再在其内部比较方法的确认、等待、误差和额外访问。每行是条件及模型重复汇总后的均值；不同故障族的异常段数不同，跨族比较时同时看平均异常段这一列。</p><p><strong>◇ 读到什么：</strong>分组结果为总体差异提供来源线索；某类故障更难或异常更多，应结合该类分母解释。</p></div></div>
<div class="table-wrap"><table data-table="supplement-families" class="supplement-table"><thead><tr><th>故障条件</th><th>方法</th><th>平均确认段</th><th>平均异常段</th><th>平均截尾等待 / 秒</th><th>加权RMSE / °C</th><th>平均额外访问</th></tr></thead><tbody><tr><td>辅助馈电＋CDU</td><td>名义＋Tour</td><td>2.67</td><td>6.83</td><td>73.14</td><td>0.501</td><td>0.00</td></tr><tr><td>辅助馈电＋CDU</td><td>名义＋FIFO</td><td>4.83</td><td>6.83</td><td>51.71</td><td>0.501</td><td>6.33</td></tr><tr><td>辅助馈电＋CDU</td><td>名义＋Greedy</td><td>4.83</td><td>6.83</td><td>51.56</td><td>0.501</td><td>5.92</td></tr><tr><td>辅助馈电＋CDU</td><td>名义＋PPO</td><td>4.00</td><td>6.83</td><td>62.29</td><td>0.499</td><td>3.94</td></tr><tr><td>辅助馈电＋CDU</td><td>CVAE＋FIFO</td><td>4.75</td><td>6.83</td><td>52.57</td><td>0.199</td><td>6.03</td></tr><tr><td>辅助馈电＋CDU</td><td>CVAE＋Greedy</td><td>4.75</td><td>6.83</td><td>52.40</td><td>0.200</td><td>5.53</td></tr><tr><td>辅助馈电＋CDU</td><td>CVAE＋PPO</td><td>4.75</td><td>6.83</td><td>52.63</td><td>0.200</td><td>6.14</td></tr><tr><td>接触热点</td><td>名义＋Tour</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.210</td><td>0.00</td></tr><tr><td>接触热点</td><td>名义＋FIFO</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.210</td><td>0.00</td></tr><tr><td>接触热点</td><td>名义＋Greedy</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.210</td><td>0.00</td></tr><tr><td>接触热点</td><td>名义＋PPO</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.210</td><td>0.00</td></tr><tr><td>接触热点</td><td>CVAE＋FIFO</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.149</td><td>0.00</td></tr><tr><td>接触热点</td><td>CVAE＋Greedy</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.149</td><td>0.00</td></tr><tr><td>接触热点</td><td>CVAE＋PPO</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.149</td><td>0.00</td></tr><tr><td>传感偏差</td><td>名义＋Tour</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.753</td><td>0.00</td></tr><tr><td>传感偏差</td><td>名义＋FIFO</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.753</td><td>0.00</td></tr><tr><td>传感偏差</td><td>名义＋Greedy</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.753</td><td>0.00</td></tr><tr><td>传感偏差</td><td>名义＋PPO</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.753</td><td>0.00</td></tr><tr><td>传感偏差</td><td>CVAE＋FIFO</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.738</td><td>0.00</td></tr><tr><td>传感偏差</td><td>CVAE＋Greedy</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.738</td><td>0.00</td></tr><tr><td>传感偏差</td><td>CVAE＋PPO</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.738</td><td>0.00</td></tr><tr><td>二次泵故障</td><td>名义＋Tour</td><td>3.50</td><td>8.67</td><td>82.60</td><td>0.674</td><td>0.00</td></tr><tr><td>二次泵故障</td><td>名义＋FIFO</td><td>6.42</td><td>8.67</td><td>54.01</td><td>0.677</td><td>7.67</td></tr><tr><td>二次泵故障</td><td>名义＋Greedy</td><td>6.33</td><td>8.67</td><td>54.64</td><td>0.686</td><td>7.42</td></tr><tr><td>二次泵故障</td><td>名义＋PPO</td><td>5.11</td><td>8.67</td><td>68.12</td><td>0.684</td><td>4.81</td></tr><tr><td>二次泵故障</td><td>CVAE＋FIFO</td><td>6.33</td><td>8.67</td><td>54.37</td><td>0.221</td><td>7.36</td></tr><tr><td>二次泵故障</td><td>CVAE＋Greedy</td><td>6.25</td><td>8.67</td><td>54.92</td><td>0.222</td><td>7.19</td></tr><tr><td>二次泵故障</td><td>CVAE＋PPO</td><td>6.39</td><td>8.67</td><td>54.72</td><td>0.221</td><td>7.44</td></tr></tbody></table></div>

每故障族12个条件，学习方法先平均三个训练种子；表为逐条件均值。主要统计采用四故障族等权，无异常的健康与虚假提示条件另列于正文。

<h4 id="training-seeds">附录 G. 训练种子与候选集合统计</h4>

<div class="table-guide" id="table-supplement-seeds"><div class="exhibit-intro" data-guide-table="supplement-seeds"><p class="exhibit-title"><span class="exhibit-number">表 25</span> <strong>换一个训练种子，成绩变化多大</strong></p><p class="exhibit-purpose">补充物理测试组区间之外的模型训练波动。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>271、811、1931是三次模型训练的随机种子，前三个数是各自每故障条件的平均确认段数。SD是这三个训练种子间的样本标准差；最后一列描述闭环加权RMSE的训练种子波动。</p><p><strong>◇ 读到什么：</strong>本表描述已训练模型之间的离散程度；它与按12组物理测试集计算的95%区间使用不同的重复单位。</p></div></div>
<div class="table-wrap"><table data-table="supplement-seeds" class="supplement-table"><thead><tr><th>方法</th><th>种子271</th><th>种子811</th><th>种子1931</th><th>确认训练种子SD</th><th>误差训练种子SD / °C</th></tr></thead><tbody><tr><td>名义＋PPO</td><td>2.90</td><td>3.23</td><td>1.96</td><td>0.659</td><td>0.0034</td></tr><tr><td>CVAE＋FIFO</td><td>3.17</td><td>3.19</td><td>3.21</td><td>0.021</td><td>0.0017</td></tr><tr><td>CVAE＋Greedy</td><td>3.15</td><td>3.17</td><td>3.19</td><td>0.021</td><td>0.0019</td></tr><tr><td>CVAE＋PPO</td><td>3.21</td><td>3.19</td><td>3.21</td><td>0.012</td><td>0.0021</td></tr></tbody></table></div>


<a id="figure-supplement-seed-blocks"></a>

<div class="exhibit-intro" data-guide-figure="supplement-seed-blocks"><p class="exhibit-title"><span class="exhibit-number">图 31</span> <strong>新基准的确认差在12组测试集中怎样分布</strong></p><p class="exhibit-purpose">检查总体均值背后是否存在条件差异，补充平均效果与区间的读法。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-seed-blocks.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>横轴1—12是独立测试组编号；每柱先在组内等权四类故障，再计算图题中的方法差。柱高&gt;0为前者确认更多，&lt;0为更少，0线为持平。左图是名义FIFO−Tour，右图是CVAE-PPO−名义PPO。</p><p><strong>◇ 读到什么：</strong>不同组的增量并不相同；右图的差还包含估计器及各自训练策略的共同变化。编号表示样本身份，不应读成训练或时间趋势。</p></div><p class="exhibit-source">逐组展示独立测试集内的确认差，四种故障等权；编号是登记身份。</p>


<div class="table-guide" id="table-supplement-policy-training"><div class="exhibit-intro" data-guide-table="supplement-policy-training"><p class="exhibit-title"><span class="exhibit-number">表 26</span> <strong>PPO有多少次真正面临多个可选任务</strong></p><p class="exhibit-purpose">量化策略学习中的排序机会，而不是只统计总训练回合。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>按同一行读回合、全局时间步和执行者实际选择数；“有选择余地比例”＝多个合法候选次数÷实际选择数。例如470/170969≈0.27%。一个全局时间步可能包含多名巡检员的选择。</p><p><strong>◇ 读到什么：</strong>多候选选择集合约占0.26%—0.27%，说明本轮排序机会稀疏；下一步可据此设计新的比较，但这些计数本身不证明FIFO已达最优。</p></div></div>
<div class="table-wrap"><table data-table="supplement-policy-training" class="supplement-table"><thead><tr><th>策略</th><th>训练种子</th><th>回合</th><th>全局时间步</th><th>实际选择数</th><th>存在多个合法候选</th><th>有选择余地比例</th><th>执行＋更新分钟</th></tr></thead><tbody><tr><td>名义＋PPO</td><td>271</td><td>120</td><td>43080</td><td>170969</td><td>470</td><td>0.27%</td><td>2.57</td></tr><tr><td>CVAE＋PPO</td><td>271</td><td>120</td><td>43080</td><td>170956</td><td>437</td><td>0.26%</td><td>4.92</td></tr><tr><td>名义＋PPO</td><td>811</td><td>120</td><td>43080</td><td>170954</td><td>448</td><td>0.26%</td><td>2.39</td></tr><tr><td>CVAE＋PPO</td><td>811</td><td>120</td><td>43080</td><td>170961</td><td>460</td><td>0.27%</td><td>5.30</td></tr><tr><td>名义＋PPO</td><td>1931</td><td>120</td><td>43080</td><td>170957</td><td>466</td><td>0.27%</td><td>2.48</td></tr><tr><td>CVAE＋PPO</td><td>1931</td><td>120</td><td>43080</td><td>170950</td><td>453</td><td>0.26%</td><td>5.44</td></tr></tbody></table></div>

种子271／811／1931列为每主要条件平均确认段，SD是三个训练种子间的样本标准差；误差SD采用闭环加权RMSE。图中每个柱对应独立物理种子块的配对差，四故障条件等权。

PPO的选择数按执行者实际可选集合计；只有一个合法候选时，策略没有排序自由。训练耗时为完整回合执行、评分、留存和四次更新的累计墙钟时间，加载与预热另计。这一比例帮助解释当前返回保护与任务设定给学习留下多大的决策空间。

<h4 id="gap-diagnosis">附录 H. 估计—确认差异的逐事件核对</h4>

此处读取原留出日志，无新增环境、模型推理或训练。144组比较包含同一条件的三个模型重复，独立物理种子块仍为12。三个模型种子的“新增／丢失”分别为1／4、1／3、0／1，平均净差为−2段，与总表155→153一致。

<div class="table-guide" id="table-estimation-confirmation-gap"><div class="exhibit-intro" data-guide-table="estimation-confirmation-gap"><p class="exhibit-title"><span class="exhibit-number">表 27</span> <strong>提示提前为何出现一段新增、一段丢失</strong></p><p class="exhibit-purpose">解释CVAE温度误差更低，却没有让FIFO确认总数提高的一个具体例子。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>“提示→完成”中前者为进入待办的时刻，后者为量测完成时刻。41号窗口855—885秒：CVAE完成880秒在窗内，名义895秒在窗外；45号窗口850—890秒：名义875秒在窗内，CVAE900秒在窗外。</p><p><strong>◇ 读到什么：</strong>41号更早排队使访问顺序发生变化，这个案例形成一增一失；更早提示与更准确的温度，需要通过实际队列和完成时机转化为确认。</p></div></div>
<div class="table-wrap"><table data-table="estimation-confirmation-gap"><thead><tr><th>任务</th><th>原评价段</th><th>名义FIFO：提示→完成</th><th>CVAE-FIFO：提示→完成</th><th>确认变化</th></tr></thead><tbody><tr><td>41号热检查</td><td>855—885秒</td><td>865→895秒</td><td>835→880秒</td><td>CVAE新增</td></tr><tr><td>45号热检查</td><td>850—890秒</td><td>860→875秒</td><td>840→900秒</td><td>CVAE丢失</td></tr></tbody></table></div>

表取`test04-cooling`、模型种子271、同一执行者5。两条轨迹在860秒首次分叉：两项访问的资格、返回证书和预算都通过，CVAE-FIFO按835秒早于840秒的入队顺序选41号。41号的确认增加与45号的确认丢失在该回合相抵；其余净差来自案例02、06、07的局部提示与访问轨迹变化。此诊断解释本批记录，完整得失及首次分叉保存在[事后核对数据](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/source-data/estimation-confirmation-gap.json)。



<h3 id="sources">6.2 来源与原件索引</h3>

本轮共2204次环境尝试，含兼容回放、观测采集、PPO训练／诊断与测试；另有3次估计器训练和18次纯物理运行。协议、逐次执行记录、模型身份与原件索引分别保存。

- [工程控制、规模与官方标准核查](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/report-engineering-alignment-20261103.md)。
- [RGB／IR视觉成果与接口核查](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/report-pid-interface-20261103.md)。
- [本任务横向指标、公式与只读复算](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/report-comparison-metrics-20261103.md)。
- [独立补充基准：完整方法](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/supplement-study-methods.md)、[新协议、模型参数及结果原件索引](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/evidence/supplement-study/README.md)。
- [补充研究设计依据](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/supplement-study-design-20261103.md)、[评价与缺失指标核查](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/supplement-metrics-audit-20261103.md)。
- [主机制验证与完整原件](https://github.com/DonsonHH/Zhinengti-RSI/blob/2db2adf146357ec35306503ed15183c0c4100d20/evidence/event-validation/final/README.md)、[九规则开发记录](https://github.com/DonsonHH/Zhinengti-RSI/blob/2db2adf146357ec35306503ed15183c0c4100d20/evidence/response-defer/README.md)。
- [名义估计与故障原件核查](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/report-method-formulas-20261103.md)、[规则动作诊断](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/report-rule-diagnosis-20261103.md)。
- [原论文指标核查](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/original-paper-metrics-20261103.md)、[模型方程与参数](https://github.com/DonsonHH/Zhinengti-RSI/blob/2db2adf146357ec35306503ed15183c0c4100d20/paper/model-appendix.md)、[机制讨论稿](https://github.com/DonsonHH/Zhinengti-RSI/blob/2db2adf146357ec35306503ed15183c0c4100d20/paper/manuscript_zh.md)。

单文件HTML内嵌图像、公式与表格，文本审阅包保留同源正文、数值表及图链接。原事件包、规则开发包与独立补充基准各自保存协议、数据和状态；完整方法与机器可读身份可由以上入口继续核对。
