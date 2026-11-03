> 正文审阅版：正文、公式和数值表与单文件HTML同源；图版保留SVG链接，便于文本工具读取。

<a id="appendix"></a>

## 6. 技术附录与可追溯原件

### 6.1 历史回看、执行记录与详细对照

以下材料保留历史基准、逐步核算及分组结果，正文以第4章的新留出比较为主。


<h4 id="engineering-history">附录 A. 500秒工程回看与原风险分布</h4>

本例来自已保存的固定巡回工程过程。估计／事后温度共用45—75°C色标；红框标出原风险分>0的64、67、70号柜，黑点为32个固定温度点。它与正文新测试案例00分别记账，名义递推原理见[2.2.1节](03-hotspots.md#principle-estimation)。



<a id="figure-estimated-temperature"></a>

[图：已有工程回看500秒的公开温度估计；与右图同一色标，红框叠加原热风险提示。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/estimated-temperature.svg)



<a id="figure-offline-temperature"></a>

[图：同一工程过程500秒的事后设备代表温度。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/offline-temperature.svg)




<a id="figure-public-risk"></a>

[图：已有工程回看：固定巡回，500秒；风险分由公开观测和名义估计计算。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/public-risk.svg)


<div class="table-wrap"><table data-table="hotspot-values"><thead><tr><th>机柜</th><th>当时公开风险分</th><th>名义估计温度／°C</th><th>事后代表温度／°C</th><th>固定温度遥测点</th></tr></thead><tbody><tr><td>64</td><td>0.1296</td><td>67.35</td><td>67.63</td><td>是</td></tr><tr><td>67</td><td>0.2623</td><td>69.58</td><td>69.53</td><td>否</td></tr><tr><td>70</td><td>0.1323</td><td>67.36</td><td>67.31</td><td>否</td></tr></tbody></table></div>

<h4 id="fifo-detail">附录 B. FIFO队列与完整返回核算实例</h4>

任务契约和证书公式见[3.1节](04-fifo.md#principle-return)。下列历史记录说明例行账与风险账如何共同执行。



<a id="figure-fifo-cycle"></a>

[图：每名执行者空闲时从本人合法请求中选择；完成量测后进入下一轮。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/fifo-cycle.svg)


<div class="table-wrap"><table data-table="fifo-queue"><thead><tr><th>本人的待确认请求</th><th>首次提示时间</th><th>470秒时风险分</th><th>当下检查</th><th>本次选择</th></tr></thead><tbody><tr><td>机柜10热检查</td><td>450秒</td><td>0.0081</td><td>资格、可行性和预算均通过</td><td>先查</td></tr><tr><td>机柜8热检查</td><td>455秒</td><td>0.0656</td><td>资格、可行性和预算均通过</td><td>继续等待</td></tr></tbody></table></div>


<a id="figure-fifo-actions"></a>

[图：主验证第2个过程，一名热巡检员的实际记录；色块宽度表示移动与服务时间。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/fifo-actions.svg)


<div class="table-wrap"><table data-table="return-budget"><thead><tr><th>重新决策时刻</th><th>批准的加查</th><th>预计完成加查</th><th>随后按原循环返回0号</th><th>0号截止</th><th>完整循环最小余量</th></tr></thead><tbody><tr><td>470秒</td><td>10</td><td>500秒</td><td>525秒</td><td>545秒</td><td>20秒</td></tr><tr><td>500秒</td><td>8</td><td>515秒</td><td>540秒</td><td>545秒</td><td>5秒</td></tr></tbody></table></div>

原0号245秒完成、截止545秒，实际540秒完成，间隔295秒。10号450秒早于8号455秒入队，因此即使风险较低也先处理。日志保留0.0081／0.0656总分；额外加查保留例行指针，请求在量测或到期前持续记账。

<h4 id="historical-benchmark">附录 C. 历史耦合基准与规则诊断</h4>

历史工况A的12过程采用辅助馈电故障与CDU衰减，持续180秒；77段热异常、12段制冷异常共89段。供电与换热乘子分别为0.05、0.20，峰值总输入23.15—24.14 MW。下列图与主文210段留出结果使用各自分母。



<a id="figure-confirmations"></a>

[图：历史耦合工况A：12个过程，共89段异常；三列为各策略的有效确认量。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/confirmations.svg)




<a id="figure-outcome-costs"></a>

[图：历史耦合工况A的FIFO相对Tour比较；区间、代价与探索性门槛均来自封存记录。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/outcome-costs.svg)



<div class="table-wrap"><table data-table="fault-cases"><thead><tr><th>过程</th><th>种子</th><th>目标柜号／设备组</th><th>故障开始→结束／秒</th><th>热／冷异常段</th></tr></thead><tbody><tr><td>01</td><td>101003</td><td>0号／第1组</td><td>150→330</td><td>8／1</td></tr><tr><td>02</td><td>101040</td><td>9号／第2组</td><td>335→515</td><td>6／1</td></tr><tr><td>03</td><td>101077</td><td>20号／第3组</td><td>520→700</td><td>6／1</td></tr><tr><td>04</td><td>101114</td><td>29号／第4组</td><td>705→885</td><td>7／1</td></tr><tr><td>05</td><td>101151</td><td>36号／第5组</td><td>150→330</td><td>7／1</td></tr><tr><td>06</td><td>101188</td><td>45号／第6组</td><td>335→515</td><td>7／1</td></tr><tr><td>07</td><td>101225</td><td>56号／第8组</td><td>520→700</td><td>6／1</td></tr><tr><td>08</td><td>101262</td><td>65号／第9组</td><td>705→885</td><td>6／1</td></tr><tr><td>09</td><td>101299</td><td>76号／第10组</td><td>150→330</td><td>7／1</td></tr><tr><td>10</td><td>101336</td><td>85号／第11组</td><td>335→515</td><td>7／1</td></tr><tr><td>11</td><td>101373</td><td>100号／第13组</td><td>520→700</td><td>4／1</td></tr><tr><td>12</td><td>101410</td><td>117号／第15组</td><td>705→885</td><td>6／1</td></tr></tbody></table></div>

异常段要求连续至少3个5秒格达到对应阈值：温度>65°C、接点温度>60°C、组流量<33.6 kg/s、组平均传感误差绝对值>1°C。该12过程分别形成77／0／12／0段。有效确认依照前一5秒采样格的正标签及告警测量核对，保留原结果的端点语义。



<a id="figure-paired-net"></a>

[图：过程01—12为预登记的12个配对过程；11个净增、1个持平。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/paired-net.svg)



九规则先由FIFO选定合法事件，再在事件与例行头之间决定响应／暂缓。R＝风险÷4，A＝等待秒数÷120，E＝两候选预计完成时差÷300，S＝两者完整循环最小余量差÷600；得分z≥0响应，否则执行例行头。



<a id="figure-registered-rules"></a>

[图：本项目9个唯一规则的得分式；R、A、E、S分别对应正文中的归一风险、等待、额外耗时与余量差。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/registered-rules.svg)



规则01的4R−1在229次二选一中全部为负，最高原风险0.7604，额外访问0，12条完整动作与Tour相同。规则06要求至少等待15秒，新增2段、丢失12段；这12段内均无完成量测，区间后首次量测正常。



<a id="figure-rule-diagnosis"></a>

[图：主过程01的完整策略轨迹对照，机柜4；等待规则为图中06号，按记录重绘。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/rule-diagnosis.svg)



该例两条轨迹260秒首次分叉。FIFO在300秒例行派4、320秒告警，赶上310—335秒的异常；等待规则315秒先查12、340秒再查4、365秒正常。335秒是未选候选的预计完成端点，图中只展示已执行轨迹。



<a id="figure-execution-chain"></a>

[图：p02-coupled，同一巡检员1，关键任务完成链；中间部分访问省略。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/execution-chain.svg)




<a id="figure-task-17"></a>

[图：17号665秒派出的是例行访问；其公开风险685秒才出现。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/task-17.svg)



<a id="figure-task-21"></a>

[图：21号650秒见风险，705秒额外派单，725秒完成，异常在710秒已结束。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/task-21.svg)



17／21是另一组Tour—FIFO完整轨迹：17号665秒例行派出、685秒见风险、690秒确认；21号650秒见风险、705秒额外派出、725秒测量时已过710秒结束。两类案例分别支持机制时序与响应门槛诊断。

#### 附录 D. 原论文水域任务对照



<a id="figure-original-paper-scores"></a>

[图：原文表8／9均值±95%CI。两种Greedy的藻华终值相同，按原表保留。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/original-paper-scores.svg)



原文在水域任务内比较DRL、Greedy、VRP及VAE/Myopic估计组合，测试100个未参与训练的场景。图取表8／9的终值均值与95%区间；“约快30%”描述曲线更早降低。原文Average的归一分母随复现对齐；本任务主表另定义并补算资产加权年龄。

#### 附录 E. 历史封存包横向表

<div class="table-wrap"><table class="comparison-table" data-table="method-comparison"><thead><tr><th rowspan="2">方法</th><th colspan="3">状态估计</th><th rowspan="2">适配idleness<br>加权年龄↓</th><th colspan="3">异常任务</th><th colspan="3">成本与效率</th><th rowspan="2">本任务状态</th></tr><tr><th>RMSE<br>°C↓</th><th>加权RMSE<br>°C↓</th><th>R²↑</th><th>确认段数<br>（比例）↑</th><th>截尾等待<br>秒↓</th><th>硬重访<br>违规</th><th>移动变化<br>%</th><th>完成量变化<br>%</th><th>单步推理<br>ms</th></tr></thead><tbody><tr data-comparison-method="tour" data-result-state="primary"><td>固定巡回Tour</td><td>未留帧</td><td>未留帧</td><td>未留帧</td><td>0.310901</td><td>28/89（31.5%）</td><td>78.16</td><td>0</td><td>+0.00</td><td>+0.00</td><td>未计时</td><td>已运行·主比较</td></tr><tr data-comparison-method="shuffled" data-result-state="primary"><td>名义估计＋风险位置置乱</td><td>未留帧</td><td>未留帧</td><td>未留帧</td><td>0.313138</td><td>25/89（28.1%）</td><td>81.06</td><td>0</td><td>+0.63</td><td>-0.34</td><td>未计时</td><td>已运行·主比较</td></tr><tr data-comparison-method="S1-age" data-result-state="development"><td>线性暂缓①：等待15秒</td><td>未留帧</td><td>未留帧</td><td>未留帧</td><td>0.312994</td><td>60/89（67.4%）</td><td>60.23</td><td>0</td><td>+0.55</td><td>-0.30</td><td>未计时</td><td>已运行·开发并列60</td></tr><tr data-comparison-method="S2-risk_time" data-result-state="development"><td>线性暂缓②：多特征</td><td>未留帧</td><td>未留帧</td><td>未留帧</td><td>0.312888</td><td>60/89（67.4%）</td><td>58.14</td><td>0</td><td>+0.49</td><td>-0.28</td><td>未计时</td><td>已运行·开发并列60</td></tr><tr data-comparison-method="fifo" data-result-state="primary"><td>名义估计＋返回保护FIFO</td><td>未留帧</td><td>未留帧</td><td>未留帧</td><td>0.313052</td><td>70/89（78.7%）</td><td>49.69</td><td>0</td><td>+0.50</td><td>-0.33</td><td>未计时</td><td>已运行·主比较</td></tr><tr data-comparison-method="vae_unet_greedy" data-result-state="not_run"><td>VAE-UNet + Greedy</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>历史封存状态；新结果见补充基准</td></tr><tr data-comparison-method="vae_unet_drl" data-result-state="not_run"><td>VAE-UNet + DRL</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>旧包未运行</td><td>历史封存状态；新结果见补充基准</td></tr></tbody></table></div>

历史主比较采用同12个预登记过程；两条线性暂缓规则为九候选中并列60段的开发对照。原包没有保存统一预测—真值帧或逐步计时，因此“未留帧／未计时”继续保留。历史VAE两行表示当时包内未运行，新增适配与独立结果见第4节。

在该历史包中，Tour整体加权年龄0.310901，FIFO为0.313052；FIFO确认70/89，移动平均+0.50%、完成量下降约0.33%。这些数值与本轮四故障基准各有自己的样本分母。

#### 附录 F. 新基准逐故障族结果

<div class="table-wrap"><table data-table="supplement-families" class="supplement-table"><thead><tr><th>故障条件</th><th>方法</th><th>平均确认段</th><th>平均异常段</th><th>平均截尾等待 / 秒</th><th>加权RMSE / °C</th><th>平均额外访问</th></tr></thead><tbody><tr><td>辅助馈电＋CDU</td><td>名义＋Tour</td><td>2.67</td><td>6.83</td><td>73.14</td><td>0.501</td><td>0.00</td></tr><tr><td>辅助馈电＋CDU</td><td>名义＋FIFO</td><td>4.83</td><td>6.83</td><td>51.71</td><td>0.501</td><td>6.33</td></tr><tr><td>辅助馈电＋CDU</td><td>名义＋Greedy</td><td>4.83</td><td>6.83</td><td>51.56</td><td>0.501</td><td>5.92</td></tr><tr><td>辅助馈电＋CDU</td><td>名义＋PPO</td><td>4.00</td><td>6.83</td><td>62.29</td><td>0.499</td><td>3.94</td></tr><tr><td>辅助馈电＋CDU</td><td>CVAE＋FIFO</td><td>4.75</td><td>6.83</td><td>52.57</td><td>0.199</td><td>6.03</td></tr><tr><td>辅助馈电＋CDU</td><td>CVAE＋Greedy</td><td>4.75</td><td>6.83</td><td>52.40</td><td>0.200</td><td>5.53</td></tr><tr><td>辅助馈电＋CDU</td><td>CVAE＋PPO</td><td>4.75</td><td>6.83</td><td>52.63</td><td>0.200</td><td>6.14</td></tr><tr><td>接触热点</td><td>名义＋Tour</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.210</td><td>0.00</td></tr><tr><td>接触热点</td><td>名义＋FIFO</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.210</td><td>0.00</td></tr><tr><td>接触热点</td><td>名义＋Greedy</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.210</td><td>0.00</td></tr><tr><td>接触热点</td><td>名义＋PPO</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.210</td><td>0.00</td></tr><tr><td>接触热点</td><td>CVAE＋FIFO</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.149</td><td>0.00</td></tr><tr><td>接触热点</td><td>CVAE＋Greedy</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.149</td><td>0.00</td></tr><tr><td>接触热点</td><td>CVAE＋PPO</td><td>1.00</td><td>1.00</td><td>163.33</td><td>0.149</td><td>0.00</td></tr><tr><td>传感偏差</td><td>名义＋Tour</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.753</td><td>0.00</td></tr><tr><td>传感偏差</td><td>名义＋FIFO</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.753</td><td>0.00</td></tr><tr><td>传感偏差</td><td>名义＋Greedy</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.753</td><td>0.00</td></tr><tr><td>传感偏差</td><td>名义＋PPO</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.753</td><td>0.00</td></tr><tr><td>传感偏差</td><td>CVAE＋FIFO</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.738</td><td>0.00</td></tr><tr><td>传感偏差</td><td>CVAE＋Greedy</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.738</td><td>0.00</td></tr><tr><td>传感偏差</td><td>CVAE＋PPO</td><td>0.67</td><td>1.00</td><td>107.92</td><td>0.738</td><td>0.00</td></tr><tr><td>二次泵故障</td><td>名义＋Tour</td><td>3.50</td><td>8.67</td><td>82.60</td><td>0.674</td><td>0.00</td></tr><tr><td>二次泵故障</td><td>名义＋FIFO</td><td>6.42</td><td>8.67</td><td>54.01</td><td>0.677</td><td>7.67</td></tr><tr><td>二次泵故障</td><td>名义＋Greedy</td><td>6.33</td><td>8.67</td><td>54.64</td><td>0.686</td><td>7.42</td></tr><tr><td>二次泵故障</td><td>名义＋PPO</td><td>5.11</td><td>8.67</td><td>68.12</td><td>0.684</td><td>4.81</td></tr><tr><td>二次泵故障</td><td>CVAE＋FIFO</td><td>6.33</td><td>8.67</td><td>54.37</td><td>0.221</td><td>7.36</td></tr><tr><td>二次泵故障</td><td>CVAE＋Greedy</td><td>6.25</td><td>8.67</td><td>54.92</td><td>0.222</td><td>7.19</td></tr><tr><td>二次泵故障</td><td>CVAE＋PPO</td><td>6.39</td><td>8.67</td><td>54.72</td><td>0.221</td><td>7.44</td></tr></tbody></table></div>

每故障族12个条件，学习方法先平均三个训练种子；表为逐条件均值。主要统计采用四故障族等权，无异常的健康与虚假提示条件另列于正文。

<h4 id="training-seeds">附录 G. 训练种子与候选集合统计</h4>

<div class="table-wrap"><table data-table="supplement-seeds" class="supplement-table"><thead><tr><th>方法</th><th>种子271</th><th>种子811</th><th>种子1931</th><th>确认训练种子SD</th><th>误差训练种子SD / °C</th></tr></thead><tbody><tr><td>名义＋PPO</td><td>2.90</td><td>3.23</td><td>1.96</td><td>0.659</td><td>0.0034</td></tr><tr><td>CVAE＋FIFO</td><td>3.17</td><td>3.19</td><td>3.21</td><td>0.021</td><td>0.0017</td></tr><tr><td>CVAE＋Greedy</td><td>3.15</td><td>3.17</td><td>3.19</td><td>0.021</td><td>0.0019</td></tr><tr><td>CVAE＋PPO</td><td>3.21</td><td>3.19</td><td>3.21</td><td>0.012</td><td>0.0021</td></tr></tbody></table></div>


<a id="figure-supplement-seed-blocks"></a>

[图：逐个种子块展示配对确认差；各块内四种故障等权，编号表示登记身份。](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-seed-blocks.svg)


<div class="table-wrap"><table data-table="supplement-policy-training" class="supplement-table"><thead><tr><th>策略</th><th>训练种子</th><th>回合</th><th>全局时间步</th><th>实际选择数</th><th>存在多个合法候选</th><th>有选择余地比例</th><th>执行＋更新分钟</th></tr></thead><tbody><tr><td>名义＋PPO</td><td>271</td><td>120</td><td>43080</td><td>170969</td><td>470</td><td>0.27%</td><td>2.57</td></tr><tr><td>CVAE＋PPO</td><td>271</td><td>120</td><td>43080</td><td>170956</td><td>437</td><td>0.26%</td><td>4.92</td></tr><tr><td>名义＋PPO</td><td>811</td><td>120</td><td>43080</td><td>170954</td><td>448</td><td>0.26%</td><td>2.39</td></tr><tr><td>CVAE＋PPO</td><td>811</td><td>120</td><td>43080</td><td>170961</td><td>460</td><td>0.27%</td><td>5.30</td></tr><tr><td>名义＋PPO</td><td>1931</td><td>120</td><td>43080</td><td>170957</td><td>466</td><td>0.27%</td><td>2.48</td></tr><tr><td>CVAE＋PPO</td><td>1931</td><td>120</td><td>43080</td><td>170950</td><td>453</td><td>0.26%</td><td>5.44</td></tr></tbody></table></div>

种子271／811／1931列为每主要条件平均确认段，SD是三个训练种子间的样本标准差；误差SD采用闭环加权RMSE。图中每个柱对应独立物理种子块的配对差，四故障条件等权。

PPO的选择数按执行者实际可选集合计；只有一个合法候选时，策略没有排序自由。训练耗时为完整回合执行、评分、留存和四次更新的累计墙钟时间，加载与预热另计。这一比例帮助解释当前返回保护与任务设定给学习留下多大的决策空间。

<h4 id="gap-diagnosis">附录 H. 估计—确认差异的逐事件核对</h4>

此处读取原留出日志，无新增环境、模型推理或训练。144组比较包含同一条件的三个模型重复，独立物理种子块仍为12。三个模型种子的“新增／丢失”分别为1／4、1／3、0／1，平均净差为−2段，与总表155→153一致。

<div class="table-wrap"><table data-table="estimation-confirmation-gap"><thead><tr><th>任务</th><th>原评价段</th><th>名义FIFO：提示→完成</th><th>CVAE-FIFO：提示→完成</th><th>确认变化</th></tr></thead><tbody><tr><td>41号热检查</td><td>855—885秒</td><td>865→895秒</td><td>835→880秒</td><td>CVAE新增</td></tr><tr><td>45号热检查</td><td>850—890秒</td><td>860→875秒</td><td>840→900秒</td><td>CVAE丢失</td></tr></tbody></table></div>

表取`test04-cooling`、模型种子271、同一执行者5。两条轨迹在860秒首次分叉：两项访问的资格、返回证书和预算都通过，CVAE-FIFO按835秒早于840秒的入队顺序选41号。41号的确认增加与45号的确认丢失在该回合相抵；其余净差来自案例02、06、07的局部提示与访问轨迹变化。此诊断解释本批记录，完整得失及首次分叉保存在[事后核对数据](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/source-data/estimation-confirmation-gap.json)。



<h3 id="sources">6.2 来源与原件索引</h3>

本轮共2204次环境尝试，覆盖兼容回放、观测采集、PPO训练／诊断与最终测试；另有3次估计器训练和18次纯物理规模运行。协议、追加式账本、模型身份与原件索引分别保存。

- [工程控制、规模与官方标准核查](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/report-engineering-alignment-20261103.md)。
- [RGB／IR视觉成果与接口核查](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/report-pid-interface-20261103.md)。
- [本任务横向指标、公式与只读复算](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/report-comparison-metrics-20261103.md)。
- [独立补充基准：完整方法](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/supplement-study-methods.md)、[新协议、模型参数及结果原件索引](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/evidence/supplement-study/README.md)。
- [补充研究设计依据](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/supplement-study-design-20261103.md)、[评价与缺失指标核查](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/supplement-metrics-audit-20261103.md)。
- [主机制验证与完整原件](https://github.com/DonsonHH/Zhinengti-RSI/blob/2db2adf146357ec35306503ed15183c0c4100d20/evidence/event-validation/final/README.md)、[九规则开发记录](https://github.com/DonsonHH/Zhinengti-RSI/blob/2db2adf146357ec35306503ed15183c0c4100d20/evidence/response-defer/README.md)。
- [名义估计与故障原件核查](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/report-method-formulas-20261103.md)、[规则动作诊断](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/report-rule-diagnosis-20261103.md)。
- [原论文指标核查](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/research/original-paper-metrics-20261103.md)、[模型方程与参数](https://github.com/DonsonHH/Zhinengti-RSI/blob/2db2adf146357ec35306503ed15183c0c4100d20/paper/model-appendix.md)、[机制讨论稿](https://github.com/DonsonHH/Zhinengti-RSI/blob/2db2adf146357ec35306503ed15183c0c4100d20/paper/manuscript_zh.md)。

单文件HTML内嵌图像、公式与表格，文本审阅包保留同源正文、数值表及图链接。原事件包、规则开发包与独立补充基准各自保存协议、数据和状态；完整方法与机器可读身份可由以上入口继续核对。
