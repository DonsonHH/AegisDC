# 参考文献与来源核对

核对日期：2026-11-18。以下是正文所需的有限文献集，不构成系统综述，也不据此宣称本研究具有算法首创性。文献支持概念和来源事实；本文运行结果只由版本固定的项目记录支持。BibTeX 见 [references.bib](references.bib)。

## 正文参考文献

<a id="google2026london"></a>

**[1]** Google Cloud. *Multiple services were experiencing issues in the europe-west2 region: Incident Report*. 2026. [官方报告](https://status.cloud.google.com/incidents/Xs2XTHzAVC9YnafnPyzj)。采用页面标注为 **2026-11-04 13:15 PST** 的报告修订。事故发生于 2026-10-19 至 20 日（US/Pacific）。键：`google2026london`。

<a id="howard1966information"></a>

**[2]** Howard, R. A. Information Value Theory. *IEEE Transactions on Systems Science and Cybernetics*, 1966, **2**(1): 22–26. [DOI: 10.1109/TSSC.1966.300074](https://doi.org/10.1109/TSSC.1966.300074)。[出版者记录](https://ieeexplore.ieee.org/document/4082064/)。键：`howard1966information`。

<a id="heckerman1995troubleshooting"></a>

**[3]** Heckerman, D., Breese, J. S., Rommelse, K. Decision-Theoretic Troubleshooting. *Communications of the ACM*, 1995, **38**(3): 49–57. [DOI: 10.1145/203330.203341](https://doi.org/10.1145/203330.203341)。[Microsoft Research 作者稿](https://www.microsoft.com/en-us/research/wp-content/uploads/1999/01/Decision-Theoretic-Troubleshooting.pdf)。键：`heckerman1995troubleshooting`。

<a id="breese1996repair"></a>

**[4]** Breese, J. S., Heckerman, D. *Decision-Theoretic Troubleshooting: A Framework for Repair and Experiment*. Microsoft Research, MSR-TR-96-06, 1996-03，1996-05 修订。[作者机构全文](https://www.microsoft.com/en-us/research/wp-content/uploads/1996/03/Decision-Theoretic-Troubleshooting-A-Framework-for-Repair-and-Experiment.pdf)。引用对象是本次读取的技术报告；报告首页另注明有 UAI 1996 会议版本，不混用两个版本的页码。键：`breese1996repair`。

<a id="kaelbling1998pomdp"></a>

**[5]** Kaelbling, L. P., Littman, M. L., Cassandra, A. R. Planning and Acting in Partially Observable Stochastic Domains. *Artificial Intelligence*, 1998, **101**(1–2): 99–134. [DOI: 10.1016/S0004-3702(98)00023-X](https://doi.org/10.1016/S0004-3702(98)00023-X)。[MIT 作者站全文](https://people.csail.mit.edu/lpk/papers/aij98-pomdp.pdf)。键：`kaelbling1998pomdp`。

<a id="grall2002maintenance"></a>

**[6]** Grall, A., Bérenguer, C., Dieulle, L. A Condition-Based Maintenance Policy for Stochastically Deteriorating Systems. *Reliability Engineering & System Safety*, 2002, **76**(2): 167–180. [DOI: 10.1016/S0951-8320(01)00148-X](https://doi.org/10.1016/S0951-8320(01)00148-X)。[出版者记录与摘要](https://www.sciencedirect.com/science/article/pii/S095183200100148X)。键：`grall2002maintenance`。

<a id="sargent2010verification"></a>

**[7]** Sargent, R. G. Verification and Validation of Simulation Models. *Proceedings of the 2010 Winter Simulation Conference*, 2010: 166–183. [DOI: 10.1109/WSC.2010.5679166](https://doi.org/10.1109/WSC.2010.5679166)。[WSC 官方全文](https://www.informs-sim.org/wsc10papers/016.pdf)。键：`sargent2010verification`。

## 实际核对范围与引用边界

| 编号 | 本次实际读取的原始来源 | 可支持的正文用途 | 本文没有据此作出的主张 |
|---|---|---|---|
| [1] | Google Cloud 当前官方事故页；核对上述修订标识、根因与时间线 | B 路检修断开、上游仍有电、共享上游信号与相同 PLC 逻辑导致启动抑制的机制来源 | 现场剩余 UPS 能量、PRE 权限与工期、某一核查能够避免该事故 |
| [2] | IEEE 出版者检索页的完整摘要、卷期页码和 DOI；直接页面访问触发验证，未取得全文 | 信息价值须与决策后果共同评价 | 本文计算了贝叶斯期望信息价值，或本文规则达到最优 |
| [3] | Microsoft Research 作者稿全文，重点引言及观察—修复决策树 | 观察与修复都是有成本的行动，应联合考虑功能恢复和行动代价 | 本文复现了其贝叶斯规划器或优于它 |
| [4] | MSR-TR-96-06 全文，重点首页、摘要与引言 | 观察、修复后观察、改变配置后观察属于不同动作；行动后证据有状态语境 | 本文采用了该文的 persistence 概率推断算法 |
| [5] | 作者在 MIT 站点提供的期刊全文；并核对作者发表列表 | 世界状态与行动者观测的分离、部分可观察决策的基本背景 | 本文求解了 POMDP、学习了信念模型，或证明全局最优 |
| [6] | Elsevier 出版页由检索服务返回的摘要、引言和元数据；作者 HAL 列表核对作者与刊物 | 检查日程和维护阈值可联合影响成本，检查本身不应视为免费 | 将其随机磨损、完美检查及无限时域假设套用于本有限 PRE 实例 |
| [7] | WSC 官方 18 页全文，重点 pp. 166–167、178–179 | 实现核验、用途限定的模型有效性和外部认证需要区别对待 | 有限工程资格已构成现场有效性或独立确认 |

### 元数据与来源差异的处置

1. Microsoft 的 [3] 落地页面显示的月份、出版者和摘要与作者稿/刊物信息不一致。正文使用标题和作者明确的作者稿；刊物条目固定为 *Communications of the ACM* **38**(3):49–57，1995，DOI 末段为 **203341**。不复制该落地页的 “May” 或 IEEE 出版者字段。
2. [5] 也有 Brown 1996 年技术报告。本包引用已在作者 MIT 站点读取的 **1998 期刊版本**，没有将两个版本混写。
3. [6] 与同作者群 2002 年另一篇 *Continuous-time predictive-maintenance scheduling for a deteriorating system* 是不同论文。本包只引用上述三位作者、76(2):167–180 的文章。
4. [7] 有 2013 年期刊扩展版本；本包引用实际可读的 **2010 WSC 版本**，不混用 2013 页码或 DOI。
5. [1] 报告中的 22:53 外部供电事件、23:00 影响开始条目及部分服务描述并不提供一致的现场可用处置窗口。本文保留这一来源局限，不由时间差推算可用操作时长；页面所述约五分钟 UPS 自主时间也不作为事故时剩余能量。当前网页阅读不等于重新核验 R1 的历史下载字节。

本包使用简短转述，不复制论文长段正文或图片。保留原始论文题名属于书目识别；不再分发上述论文全文。
