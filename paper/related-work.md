# 相关工作比较与新颖性核验

核验日期：2026-11-02。以下只记录本轮实际读取的原始论文、出版方页面或作者机构来源。摘要级核验与正文级核验分开；“与本文的差别”是作者对问题和实现的比较，不表示已证明其他论文没有某项能力。

|编号与工作|本轮核验范围|可支持的比较|本项目仍需回答什么|
|---|---|---|---|
|R1 Russo等，2016，数据中心移动环境监测|出版方正文的系统与实验部分|移动机器人形成可重配置的环境测量服务，并有真实场景实验|本稿聚焦例行重访和短时专业确认的共同执行；仿真结果不替代R1的现场证据|
|R2 Asghar等，2019，带latency约束的持续监测|arXiv摘要及正文问题定义|节点重访上限和机器人数量是明确的规划对象|本文人员与任务所属固定，研究确认义务插入，而非最少机器人配置|
|R3 Welikala与Cassandras，2021，事件驱动RHC|作者稿§II目标、事件模型；作者机构刊物元数据|基于事件决策并优化节点不确定度已有成熟研究|本稿区分调度触发事件与需要专业测量闭合的风险事件，评价有效确认与重访取舍|
|R4 Yanes Luis等，2025，非均匀水域持续巡检|已取得13页机构库全文，§3、§4.1—4.7逐项核对|重要度加权idleness、网格移动、Double DQL／Dueling及VAE-UNet；safe-consensus检查避障／碰撞|本稿转为带服务时长的专业确认与硬重访；`W_MAX`是原指标截断，不等于本文硬期限。尚无同任务算法竞争力实测|
|R5 Alshiekh等，2018，shielding|arXiv摘要及AAAI原论文首页|学习策略外部过滤安全动作已有先例|本文证书针对固定所属、确定耗时的巡回返回；不以“存在安全过滤器”本身作为新颖性|
|R6 Shinn等，2023，Reflexion|arXiv摘要及框架正文|用语言反馈和记忆影响后续行为，不必更新模型权重|RQ3要检验相同规则空间、同预算下的运行后果增量，而非把反思框架当新贡献|
|R7 Agrawal等，GEPA，ICLR 2026|正式论文、算法1及出版方BibTeX|轨迹反思、候选更新及Pareto选择已有明确算法|RQ3采用反馈优化思想；任务特定表达若另主张贡献，需增加直接消融|
|R8 Cheng等，2026，LLM数据中心运维机器人|出版方摘要、系统设计与语义任务解析部分|LLM与层级3D场景图已用于数据中心运维任务和部署|本文的切口是独立确认义务、重访保护及受限规则改进，不以“LLM＋数据中心”作为创新依据|
|R9 Zhang、Wu、Zhou，2024，持续巡逻与紧急处置|作者机构摘要与正式卷页；全文尚未成功取得|已有联合两类任务及部分车辆响应紧急事件的策略|专业资格、最大重访与后备证书的完整差异保持pending_verification，不将“摘要没写”记为“没有”|
|R10 Wabersich、Zeilinger，2021，预测安全过滤|17页作者全文，§4.1算法1／图2及§4.2定理4.6|审核当前动作时保留未来可行计划，失败时沿后备策略延续已有方法基础|本稿是确定离散巡检任务的循环后备构造；命题不作为新的通用安全过滤理论|

## 原始来源

- **R1** Ludovico Orlando Russo, Stefano Rosa, Marcello Maggiora, Basilio Bona. *A Novel Cloud-Based Service Robotics Application to Data Center Environmental Monitoring*. Sensors 16(8), 1255 (2016). [出版方全文](https://www.mdpi.com/1424-8220/16/8/1255)。
- **R2** Ahmad Bilal Asghar, Stephen L. Smith, Shreyas Sundaram. *Multi-Robot Routing for Persistent Monitoring with Latency Constraints*. ACC详细作者稿，2019。[arXiv](https://arxiv.org/abs/1903.06105)、[正文](https://arxiv.org/html/1903.06105v1)。
- **R3** Shirantha Welikala, Christos G. Cassandras. *Event-driven receding horizon control for distributed persistent monitoring in network systems*. Automatica 127, 109519 (2021). [作者稿](https://arxiv.org/html/2003.11713v5)、[作者机构记录](https://researchwith.stevens.edu/en/publications/event-driven-receding-horizon-control-for-distributed-persistent-/)。
- **R4** Samuel Yanes Luis, Nicola Basilico, Michele Antonazzi, Daniel Gutiérrez-Reina, Sergio Toral Marín. *Variational model-based Deep Reinforcement Learning for Non-Homogeneous Patrolling aquatic environments with multiple unmanned surface vehicles*. Expert Systems with Applications 270, 126483 (2025). [DOI](https://doi.org/10.1016/j.eswa.2025.126483)、[作者机构库论文入口](https://idus.us.es/server/api/core/bitstreams/79e88506-ca7f-48f1-86b8-5504d9cb3e39/content)。
- **R5** Mohammed Alshiekh, Roderick Bloem, Ruediger Ehlers, Bettina Könighofer, Scott Niekum, Ufuk Topcu. *Safe Reinforcement Learning via Shielding*. AAAI (2018). [作者稿](https://arxiv.org/abs/1708.08611)、[AAAI论文](https://ojs.aaai.org/index.php/AAAI/article/download/11797/11656)。
- **R6** Noah Shinn, Federico Cassano, Edward Berman, Ashwin Gopinath, Karthik Narasimhan, Shunyu Yao. *Reflexion: Language Agents with Verbal Reinforcement Learning*. 2023。[作者稿](https://arxiv.org/html/2303.11366v4)。
- **R7** Lakshya A Agrawal et al. *GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning*. ICLR 2026，pp.8479—8565。[正式论文页](https://proceedings.iclr.cc/paper_files/paper/2026/hash/0e9e708b6f48e14fd0ac29e167413f76-Abstract-Conference.html)、[正式BibTeX](https://proceedings.iclr.cc/paper_files/paper/6768-/bibtex)。正式作者名按出版方使用Alex Dimakis。
- **R8** Yao Cheng, Fengyang Jiang, Kai Song, Zhe Han, Haiyang Liu, Huaizhen Wang, Fengyu Zhou. *Design and deployment of an large language model-enhanced autonomous robot for intelligent operation and maintenance in data centers*. International Journal of Advanced Robotic Systems (2026). [出版方全文](https://journals.sagepub.com/doi/10.1177/17298806261450661)。题名的“an large”按原文保留。
- **R9** Junqi Zhang, Yunzhe Wu, Mengchu Zhou. *Cooperative Dual-Task Path Planning for Persistent Surveillance and Emergency Handling by Multiple Unmanned Ground Vehicles*. IEEE TITS 25(11),16288—16299 (2024). [DOI](https://doi.org/10.1109/TITS.2024.3421894)、[作者机构记录](https://digitalcommons.njit.edu/fac_pubs/805/)。
- **R10** Kim Peter Wabersich, Melanie N. Zeilinger. *A predictive safety filter for learning-based control of constrained nonlinear dynamical systems*. Automatica 129,109597 (2021). [DOI](https://doi.org/10.1016/j.automatica.2021.109597)、[作者全文](https://arxiv.org/html/1812.05506v4)。

## 最近邻与具体贡献的对应

|比较维度|最近邻已经解决的内容|本稿具体处理|目前可验证的差别／仍需实验|
|---|---|---|---|
|两类任务|R9已共同安排持续巡逻与突发处置|专业测量闭合事件，固定所属例行义务保留|当前任务契约与轨迹可复核；R9完整约束差异待全文核实|
|当前动作与未来延续|R10已有候选输入审核和可行后备策略|检查候选完成、所属巡回首轮及闭合周期|任务特定充分证书与证明；不以一般后备思想作为创新|
|导师原算法关系|R4以重要度／idleness回报驱动网格移动，VAE-UNet估计|专业确认、服务时间、硬重访及受限插入|观测／动作／目标／约束已改变；目前是问题延伸，不是已验证优于原DDQL算法|
|反馈优化|R6、R7已有语言后果和轨迹反思更新|拟将经验映射到可审查的响应／暂缓规则|默认沿用已有思想的任务定位；四组等预算比较尚待完成|
|同权限竞争力|Tour检验新增访问权限，置乱检验位置干预|下一强搜索组使用风险、年龄、耗时、返回余量|须实际评价同空间规则族；现有89次选择机会不证明暂缓有收益|

详细页节、缓存身份及导师原论文的五维对照见[原始核查记录](research/closest-methods-20261102.md)。

## 对论文定位的直接影响

现有主结果支持机制价值，尚没有与R2、R3或R4的成熟调度方法做同任务性能比较。若稿件主张是“受约束确认接口及其经验驱动改进”，下一项关键比较是同空间等预算搜索和无反馈模型；若主张通用调度性能优势，则需要另选并适配更强调度基线。两种主张需要不同实验，不合并成一个未经验证的结论。

本轮是针对性定位核验，不是系统综述或“首次提出”的穷尽性检索。R4的逐节建模关系已核对，R9全文约束对照仍待取得原文；同权限竞争力需要RQ3补强包的实际比较。
