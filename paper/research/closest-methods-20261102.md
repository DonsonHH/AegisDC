# 最近邻方法与导师原论文的原始来源核查

核查日期：2026-11-02。用途是限定论文贡献并帮助选择直接对照。本轮只读论文和现有实现，未执行环境评价、模型推理或训练。PDF页码均从文件第一页计数；文献自己的印刷页码另行标注。以下“本文”指当前仓库的事件确认机制与尚待验证的RQ3设计。

## 1 核验层级与来源身份

|工作|准确发表信息|本轮实际取得的证据|核验结论|
|---|---|---|---|
|Zhang、Wu、Zhou，双任务巡逻与紧急处置|JunQi Zhang, YunZhe Wu, MengChu Zhou. IEEE Transactions on Intelligent Transportation Systems **25(11), 16288–16299 (2024)**. DOI **10.1109/TITS.2024.3421894**|[作者机构记录](https://researchwith.njit.edu/en/publications/cooperative-dual-task-path-planning-for-persistent-surveillance-a/)、[NJIT原始条目](https://digitalcommons.njit.edu/fac_pubs/805/)，以及公开IEEE排版PDF的索引片段。该[PDF入口](https://openreview.net/pdf/42713053ce9eeaac4e0bec84f3212711e246e6c5.pdf)实际下载403／浏览器验证；NJIT也注明正文不在该站提供。Crossref出版方元数据与卷页一致|**机构摘要与书目核验；全文约束比较pending_verification**|
|Wabersich、Zeilinger，预测安全过滤|Kim Peter Wabersich, Melanie N. Zeilinger. *A predictive safety filter for learning-based control of constrained nonlinear dynamical systems*. Automatica **129, 109597 (2021)**. DOI **10.1016/j.automatica.2021.109597**|[作者稿v4全文](https://arxiv.org/html/1812.05506v4)、[PDF](https://arxiv.org/pdf/1812.05506)，本地17页；期刊信息经Crossref核对。审阅给定的ETH条目本轮网页访问403，未以其未知正文替代核验|**作者全文＋正式出版元数据**|
|GEPA|*GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning*. **ICLR 2026**，正式书目页码 **8479–8565**|[正式论文页](https://proceedings.iclr.cc/paper_files/paper/2026/hash/0e9e708b6f48e14fd0ac29e167413f76-Abstract-Conference.html)、[正式论文PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/0e9e708b6f48e14fd0ac29e167413f76-Paper-Conference.pdf)、[正式BibTeX](https://proceedings.iclr.cc/paper_files/paper/6768-/bibtex)|**正式版本正文与书目**；应替换原先只列2025预印本的主条目|
|导师指定原论文|Samuel Yanes Luis, Nicola Basilico, Michele Antonazzi, Daniel Gutiérrez-Reina, Sergio Toral Marín. *Variational model-based Deep Reinforcement Learning for Non-Homogeneous Patrolling aquatic environments with multiple unmanned surface vehicles*. Expert Systems with Applications **270, 126483 (2025)**. DOI **10.1016/j.eswa.2025.126483**|[作者机构库PDF](https://idus.us.es/server/api/core/bitstreams/79e88506-ca7f-48f1-86b8-5504d9cb3e39/content)本机普通HTTP读取成功，取得13页出版排版全文；网页工具仍返回403。[出版方页面](https://www.sciencedirect.com/science/article/pii/S0957417425001058)|**全文已取得**，可以撤去R4“本轮只核验首页／摘要”的旧状态|

本地缓存（不提交或再分发PDF）：`.work/paper-literature/predictive-safety-filter.pdf`，SHA256 `f1604802bf91f0eb672ca04b7772eee536dfccebd4a42072456130ba74fe8f52`；`.work/paper-literature/yanes-2025.pdf`，SHA256 `a1f0b584a4b0502622b36f7bafb8e011d258177d257e5e807b88fca3c0f2c911`。同目录`.txt`是逐页文本提取，只作为定位辅助，不改变原文公式。

## 2 双任务与后备可行性分别说明什么

Zhang等已共同安排持续巡逻和紧急事件，使用目标奖励及协作选车，使部分车辆处置事件、其余继续巡逻。机构摘要足以否定“共同考虑例行与突发任务本身就是首次创新”的定位；**其最大重访、专业资格、固定所属及后备证书是否存在，不能由摘要作否定判断**。公开索引标示问题定义位于印刷p.16290，涉及加权道路图；页内引言和章节引用有不一致，待取得全文后再确认最终节号。

预测安全过滤的最直接对应位置是作者稿**§4.1，PDF pp.4–6，式(5)、算法1和图2**：候选输入由面向终端安全集的后备计划检验；新计划不可行时，沿旧计划尾段缩短时域延续。**§4.2，PDF pp.6–9，算法2、定理4.6；附录A.2**进一步处理模型不确定性及概率保证。本项目返回证书可以定位为离散专业巡检中的具体后备构造，不是新的通用预测安全过滤理论。[全文定位](https://arxiv.org/html/1812.05506v4)

GEPA正式论文**§2（PDF pp.2–4）、§3及算法1／图5、§3.1**分别给出预算化优化问题、轨迹反思更新和候选选择。它优化提示并固定模型权重。本项目若采用相近思想，贡献应由任务、规则接口和等预算实证识别；若主张新反馈方法，则还要验证任务特定后果表达或其他新增机制的增量。[正式论文](https://proceedings.iclr.cc/paper_files/paper/2026/file/0e9e708b6f48e14fd0ac29e167413f76-Paper-Conference.pdf)

## 3 导师原论文与本项目的逐项关系

|维度|Yanes Luis等的原始定义与定位|本项目当前对应及写作影响|
|---|---|---|
|观测|**§4.5，PDF p.5，图2；§4.7，pp.6–7**：自身中心的导航、重要度、idleness和位置信息；估计器输入为已采样重要度图与访问mask|公开遥测、历史专业测量及名义估计；估计目标与输入模式已经变化，不能将冻结CVAE源码存在写成该论文完整复现|
|动作|**§3，pp.3–4；§4.1，p.4**：8邻接网格上的可行移动，到访节点及邻域获得测量|选择带专业服务耗时的任务，移动与服务不可中断；后续选择在完成时发生，不是原来的网格动作|
|目标|**§3，p.4，式(1)–(2)；§4.6，p.6，式(8)**：节点重要度加权idleness与冗余修正的采样回报|有效专业确认、漏检截尾等待和执行成本是新评价对象；不能将不同指标上的收益称为超越原算法|
|约束|**§3，p.4；§4.4，pp.5–6，算法2**：路径邻接、任务时限和避障／多车碰撞动作审查；`W_MAX`是idleness指标的截断|本稿显式规定完成测量的最大重访间隔、资格与固定所属，并构造循环延续；原文的idleness截断不等于本稿式(1)的硬期限|
|方法模块|**§4.1–4.5，pp.4–6；§4.7，pp.6–7**：共享多智能体Double DQL／Dueling网络、safe-consensus与VAE-UNet重要度估计|本轮实际使用FIFO和名义估计；原来的safe-consensus处理碰撞，本稿证书保护所属巡回延续，保证对象不同|

这张表说明**研究问题和执行契约的延伸**。当前证据尚没有把原方法适配到同一任务后做实验，也没有证明新DDQL或新VAE结构。若以“原算法改进”为最终定位，还需要明确保留和修改的算法接口，并进行对应对照。[原论文全文](https://idus.us.es/server/api/core/bitstreams/79e88506-ca7f-48f1-86b8-5504d9cb3e39/content)

原文PDF p.5同时出现“single-channel image”与随后多类观测组成的文字，本文不据此自行认定输入张量通道数。上述表只列可确认的信息组成；需要逐层复现网络时应继续核对作者源码或原图，不能由文本提取自动修正原文。

## 4 可加入正文的短段落

**双任务背景：** 持续巡逻与紧急处置已有联合规划研究。Zhang等通过奖励与协作选车安排两类任务；本文关注专业确认服务与固定所属巡回的共同执行，显式检查测量重访期限和插入后的循环延续。两者约束与动作权限的完整差异将以全文和同接口比较为准。

**后备证书定位：** 预测安全过滤通过面向未来的可行计划审核候选输入，并在必要时沿后备计划延续。本文利用这一方法背景，为确定耗时的离散巡检构造候选完成、首轮返回和闭合周期检查。这里的命题是任务特定的可行性保持结果。

**反馈来源：** GEPA已使用执行及评价轨迹反思进行预算化提示优化。本文拟采用反馈优化思想，检验固定专业巡检执行器中响应／暂缓规则的任务增量；任务特定后果表达若被列为方法贡献，需要与通用反馈或相应消融直接比较。

## 5 建议书目条目

GEPA作者和页码采用正式出版方BibTeX；正式作者名为`Dimakis, Alex`，不沿用预印本中的另一种显示名。

```bibtex
@article{zhang2024dualtask,
  author = {Zhang, JunQi and Wu, YunZhe and Zhou, MengChu},
  title = {Cooperative Dual-Task Path Planning for Persistent Surveillance and Emergency Handling by Multiple Unmanned Ground Vehicles},
  journal = {IEEE Transactions on Intelligent Transportation Systems},
  year = {2024}, volume = {25}, number = {11}, pages = {16288--16299},
  doi = {10.1109/TITS.2024.3421894},
  url = {https://digitalcommons.njit.edu/fac_pubs/805/}
}
@article{wabersich2021predictive,
  author = {Wabersich, Kim Peter and Zeilinger, Melanie N.},
  title = {A predictive safety filter for learning-based control of constrained nonlinear dynamical systems},
  journal = {Automatica}, year = {2021}, volume = {129}, pages = {109597},
  doi = {10.1016/j.automatica.2021.109597},
  url = {https://arxiv.org/abs/1812.05506}
}
@inproceedings{agrawal2026gepa,
  author = {Agrawal, Lakshya A and Tan, Shangyin and Soylu, Dilara and Ziems, Noah and Khare, Rishi and Opsahl-Ong, Krista and Singhvi, Arnav and Shandilya, Herumb and Ryan, Michael J and Jiang, Meng and Potts, Christopher and Sen, Koushik and Dimakis, Alex and Stoica, Ion and Klein, Dan and Zaharia, Matei and Khattab, Omar},
  title = {{GEPA}: Reflective Prompt Evolution Can Outperform Reinforcement Learning},
  booktitle = {International Conference on Learning Representations},
  year = {2026}, volume = {2026}, pages = {8479--8565},
  url = {https://proceedings.iclr.cc/paper_files/paper/2026/file/0e9e708b6f48e14fd0ac29e167413f76-Paper-Conference.pdf}
}
```

## 6 仍需保留的核验边界

- 双任务论文的正文尚未成功取得；现在可以引用其联合任务主题与机构摘要确认的策略，但不能填写“没有最大重访／没有专业约束／没有安全计划”等负向对照格。
- 导师原论文与当前机制不是同一个实验契约；上述逐节核查完成了关系定位，不替代同任务算法竞争力实验。
- 本轮未访问ESWA投稿系统、未核验期刊录用标准，也未执行任何模型或环境评价。期刊竞争力仍需按最终贡献、同权限对照和RQ3结果判断。
