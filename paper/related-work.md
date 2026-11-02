# 相关工作比较与新颖性核验

核验日期：2026-11-02。以下只记录本轮实际读取的原始论文、出版方页面或作者机构来源。摘要级核验与正文级核验分开；“与本文的差别”是作者对问题和实现的比较，不表示已证明其他论文没有某项能力。

|编号与工作|本轮核验范围|可支持的比较|本项目仍需回答什么|
|---|---|---|---|
|R1 Russo等，2016，数据中心移动环境监测|出版方正文的系统与实验部分|移动机器人形成可重配置的环境测量服务，并有真实场景实验|本稿聚焦例行重访和短时专业确认的共同执行；仿真结果不替代R1的现场证据|
|R2 Asghar等，2019，带latency约束的持续监测|arXiv摘要及正文问题定义|节点重访上限和机器人数量是明确的规划对象|本文人员与任务所属固定，研究确认义务插入，而非最少机器人配置|
|R3 Welikala与Cassandras，2021，事件驱动RHC|作者稿§II目标、事件模型；作者机构刊物元数据|基于事件决策并优化节点不确定度已有成熟研究|本稿区分调度触发事件与需要专业测量闭合的风险事件，评价有效确认与重访取舍|
|R4 Yanes Luis等，2025，非均匀水域持续巡检|作者机构库返回的论文首页／摘要与出版元数据；全文下载本轮403|模型辅助、部分观测下的多执行者巡检是导师指定研究基础|当前方法沿用问题思想；本轮采用名义估计和FIFO，未提供该学习算法的同任务实测比较。细部模型优劣保持pending_verification|
|R5 Alshiekh等，2018，shielding|arXiv摘要及AAAI原论文首页|学习策略外部过滤安全动作已有先例|本文证书针对固定所属、确定耗时的巡回返回；不以“存在安全过滤器”本身作为新颖性|
|R6 Shinn等，2023，Reflexion|arXiv摘要及框架正文|用语言反馈和记忆影响后续行为，不必更新模型权重|RQ3要检验相同规则空间、同预算下的运行后果增量，而非把反思框架当新贡献|
|R7 Agrawal等，GEPA，2025预印本／2026修订|arXiv v2摘要与算法1|轨迹反思、候选更新及Pareto选择已有明确算法|有限四组比较应控制搜索机会和反馈来源；不能由采用大模型直接推断新方法有效|
|R8 Cheng等，2026，LLM数据中心运维机器人|出版方摘要、系统设计与语义任务解析部分|LLM与层级3D场景图已用于数据中心运维任务和部署|本文的切口是独立确认义务、重访保护及受限规则改进，不以“LLM＋数据中心”作为创新依据|

## 原始来源

- **R1** Ludovico Orlando Russo, Stefano Rosa, Marcello Maggiora, Basilio Bona. *A Novel Cloud-Based Service Robotics Application to Data Center Environmental Monitoring*. Sensors 16(8), 1255 (2016). [出版方全文](https://www.mdpi.com/1424-8220/16/8/1255)。
- **R2** Ahmad Bilal Asghar, Stephen L. Smith, Shreyas Sundaram. *Multi-Robot Routing for Persistent Monitoring with Latency Constraints*. ACC详细作者稿，2019。[arXiv](https://arxiv.org/abs/1903.06105)、[正文](https://arxiv.org/html/1903.06105v1)。
- **R3** Shirantha Welikala, Christos G. Cassandras. *Event-driven receding horizon control for distributed persistent monitoring in network systems*. Automatica 127, 109519 (2021). [作者稿](https://arxiv.org/html/2003.11713v5)、[作者机构记录](https://researchwith.stevens.edu/en/publications/event-driven-receding-horizon-control-for-distributed-persistent-/)。
- **R4** Samuel Yanes Luis, Nicola Basilico, Michele Antonazzi, Daniel Gutiérrez-Reina, Sergio Toral Marín. *Variational model-based Deep Reinforcement Learning for Non-Homogeneous Patrolling aquatic environments with multiple unmanned surface vehicles*. Expert Systems with Applications 270, 126483 (2025). [DOI](https://doi.org/10.1016/j.eswa.2025.126483)、[作者机构库论文入口](https://idus.us.es/server/api/core/bitstreams/79e88506-ca7f-48f1-86b8-5504d9cb3e39/content)。
- **R5** Mohammed Alshiekh, Roderick Bloem, Ruediger Ehlers, Bettina Könighofer, Scott Niekum, Ufuk Topcu. *Safe Reinforcement Learning via Shielding*. AAAI (2018). [作者稿](https://arxiv.org/abs/1708.08611)、[AAAI论文](https://ojs.aaai.org/index.php/AAAI/article/download/11797/11656)。
- **R6** Noah Shinn, Federico Cassano, Edward Berman, Ashwin Gopinath, Karthik Narasimhan, Shunyu Yao. *Reflexion: Language Agents with Verbal Reinforcement Learning*. 2023。[作者稿](https://arxiv.org/html/2303.11366v4)。
- **R7** Lakshya A Agrawal et al. *GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning*. arXiv:2507.19457，v2 (2026-02-14)，首稿2025-07-25。[作者稿](https://arxiv.org/html/2507.19457v2)。
- **R8** Yao Cheng, Fengyang Jiang, Kai Song, Zhe Han, Haiyang Liu, Huaizhen Wang, Fengyu Zhou. *Design and deployment of an large language model-enhanced autonomous robot for intelligent operation and maintenance in data centers*. International Journal of Advanced Robotic Systems (2026). [出版方全文](https://journals.sagepub.com/doi/10.1177/17298806261450661)。题名的“an large”按原文保留。

## 对论文定位的直接影响

现有主结果支持机制价值，尚没有与R2、R3或R4的成熟调度方法做同任务性能比较。若稿件主张是“受约束确认接口及其经验驱动改进”，下一项关键比较是同空间等预算搜索和无反馈模型；若主张通用调度性能优势，则需要另选并适配更强调度基线。两种主张需要不同实验，不合并成一个未经验证的结论。

本轮是针对性定位核验，不是系统综述或“首次提出”的穷尽性检索。R4的逐节建模对照和目标刊会所需的最近文献范围列入投稿前工作，不阻碍现有方法及结果正文写作。
