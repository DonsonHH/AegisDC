> 正文审阅版：正文、公式和数值表与单文件HTML同源；图版保留SVG链接，便于文本工具读取。

> 4. 实验结果 · 第3/3部分。

<h3 id="scale-results">4.5 模块化物理规模与数值一致性</h3>



<a id="figure-supplement-scale"></a>

<div class="exhibit-intro" data-guide-figure="supplement-scale"><p class="exhibit-title"><span class="exhibit-number">图 16</span> <strong>机柜增多后，纯物理计算与内存怎样变化</strong></p><p class="exhibit-purpose">核对模型扩展到512和1024柜时的资源开销。</p></div>

[查看图版](https://github.com/DonsonHH/Zhinengti-RSI/blob/donson/restart-alignment/paper/figures/supervisor-report/supplement-scale.svg)

<div class="reading-notes"><p><strong>↳ 怎么看：</strong>横轴是机柜数。左图纵轴为360个物理步的运行秒数，柱高为中位数，范围线为六次实测最小—最大值；右图为Python追踪峰值MiB，取该规模六次运行中的最大值。范围线不是95%置信区间。</p><p><strong>◇ 读到什么：</strong>这批物理运行耗时未呈单调上升，追踪内存随规模增加；它验证物理过程与静态巡回的扩展，端到端学习调度仍对应128柜。</p></div><p class="exhibit-source">每规模三种子×健康／耦合两工况的纯物理过程实测；带tracemalloc开销，范围为六次实测最小—最大，未作大规模学习调度。</p>


<div class="table-guide" id="table-supplement-scale"><div class="exhibit-intro" data-guide-table="supplement-scale"><p class="exhibit-title"><span class="exhibit-number">表 16</span> <strong>三种机柜规模的模型量与资源开销</strong></p><p class="exhibit-purpose">同时查看问题规模变大多少，以及物理计算用了多少时间和内存。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>各行按128→512→1024柜比较；斜杠两侧是表头指定的两种数量，例如热状态/指令状态。耗时是每规模六次纯物理运行的中位数，峰值内存以MiB计；静态检查列核对构造的循环路线。</p><p><strong>◇ 读到什么：</strong>状态、人员与任务数随规模扩展，追踪内存上升；本表资源数值对应物理过程，学习调度成绩仍来自128柜基准。</p></div></div>
<div class="table-wrap"><table data-table="supplement-scale" class="supplement-table"><thead><tr><th>机柜数</th><th>热状态／指令状态</th><th>执行者／专业任务</th><th>物理耗时中位数 / 秒</th><th>Python峰值 / MiB</th><th>静态检查</th></tr></thead><tbody><tr><td>128</td><td>161／145</td><td>18／176</td><td>0.517</td><td>0.50</td><td>构造闭合巡回满足</td></tr><tr><td>512</td><td>641／577</td><td>72／704</td><td>0.483</td><td>1.70</td><td>构造闭合巡回满足</td></tr><tr><td>1024</td><td>1281／1153</td><td>144／1408</td><td>0.500</td><td>3.32</td><td>构造闭合巡回满足</td></tr></tbody></table></div>
<div class="table-guide" id="table-supplement-scale-cycles"><div class="exhibit-intro" data-guide-table="supplement-scale-cycles"><p class="exhibit-title"><span class="exhibit-number">表 17</span> <strong>规模扩展后的例行路线能否按时走完</strong></p><p class="exhibit-purpose">核对增加机柜后，各专业是否配有满足重访期限的构造巡回。</p></div><div class="reading-notes"><p><strong>↳ 怎么看：</strong>每格“人数；周期/期限”先看人员配置，再读该专业所有已构造人员路线中的最长闭合巡回周期。例如240/300秒表示最长一轮240秒、允许间隔300秒；最长周期≤期限表示该专业的构造路线通过静态时间核查。</p><p><strong>◇ 读到什么：</strong>三种规模的已构造路线均满足对应专业期限；这给出了可行的例行底座。</p></div></div>
<div class="table-wrap"><table data-table="supplement-scale-cycles" class="supplement-table"><thead><tr><th>机柜数</th><th>热检查：人数；周期／期限</th><th>电气：人数；周期／期限</th><th>制冷：人数；周期／期限</th><th>自控：人数；周期／期限</th></tr></thead><tbody><tr><td>128</td><td>12人；240/300秒</td><td>2人；310/600秒</td><td>2人；310/600秒</td><td>2人；270/600秒</td></tr><tr><td>512</td><td>48人；240/300秒</td><td>8人；385/600秒</td><td>8人；385/600秒</td><td>8人；345/600秒</td></tr><tr><td>1024</td><td>96人；240/300秒</td><td>16人；465/600秒</td><td>16人；465/600秒</td><td>16人；425/600秒</td></tr></tbody></table></div>

每规模为三种子×健康／耦合两条件，360个5秒物理步。耗时含tracemalloc开销，内存范围为该物理段及温度序列留存；静态检查评价已构造的专业巡回。三规模的构造闭合巡回均满足各专业期限。360步物理耗时中位数约0.48—0.52秒，未随柜数呈单调上升；Python追踪峰值由0.50增至3.32 MiB，范围为该物理段及温度序列的留存。

18次运行的最大能量平衡残差为7.97e-08 kJ，最大电功率平衡残差为8.73e-11 kW，用于核对数值守恒一致性。512／1024柜验证覆盖物理过程与静态巡回，学习闭环结果对应128柜。
