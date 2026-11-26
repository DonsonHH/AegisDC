# 完整设施中的成本感知信息价值调度：方法形式化草稿

本文形式化 T4c 冻结角色 V\*\* 的实际选择规则。全文将它称为 **cost-aware inspection and intervention policy**。形式化分清三个对象：设施产生实际服务，有限世界模型预测行动后果，统计比较使用已保存的实际运行成绩。在线规则没有训练步骤。[执行入口](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_action_cost/worker.py) · [版本冻结](https://github.com/DonsonHH/AegisDC/blob/cef45c0275ce330eaf2652362bfd5090dffd5aa6/docs/mainline/t4c-action-cost-v3/v-double-star-freeze.json)

## 1　决策问题

令 $t\in\{0,60,\ldots,3600\}$ 为公开决策点。窗口 $H=3600$ 秒，原生物理步长为 0.25 秒。私有状态 $x(t)$ 包含供配电、后备、设施冷却、设备冷却与环境、IT 服务、监控、通行、人员与工具的状态，以及需求、未到消息、真实动作结果和待办。物理传输、功能依赖、控制／信息、空间可达分别建模。原有自动保护在每个处理臂生效。共同外生条件相同，各臂的动态状态、预算、收据和证据均独立。

静态公开资料 $u$ 给出资产、作业、路由、时钟、许可窗和预算。历史 $h_t$ 只含截至 $t$ 已交付的记录、固定测量、本人付费读数、写入回执、工作回执及本人已发行任务。测量必须先采样后到达，并在有效期内。本人读数要与工单、执行 ID、工作者、工具及配置版本匹配。来源副本不产生第二份证据。现场待发消息、未来故障时刻、真实世界编号、评价端合法下界均在决策接口之外。[公开字段和时序校验](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_risk_dispatch/policy.py#L6-L43) · [来源与执行身份](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_risk_dispatch/belief.py#L20-L53)

实际动作 $a_t$ 为等待，或对一份具名工单发行一次初检 $I$、直接处置 $A$、本人复核 $R$ 或续核 $X$。每个决策点至多一份请求，每对象／阶段按已发行身份去重。公开门 $\mathcal A(h_t,u)$ 检查工单有效性、执行关联、工种、通行与行走时间、人员和工具位置／占用、班次和读写窗。成功写入的预测分支须排入本人复核；续核依资格、期限和可执行性。令 $d_j$ 为包含行走的计划耗时，则成功分支新增人员和工具占用分别受各自预算约束，发行次数受费用预算约束。执行版按较小的人／工具余额做共同预留，受阻的既有写入为未了结义务预留人员和发行额度。写入还必须满足公开共享许可的恢复时间。已就绪且可发的 $R$、$X$ 先于自选作业；没有可支持世界、正在等自己的初检，或找不到完整可行续排时，保留原因并等待。[作业门](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/docs/mainline/t3-prior-information-v2/public_work.py#L67-L133) · [共享变更许可](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_action_cost/permit.py) · [必需作业与等待](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_risk_dispatch/policy.py#L93-L133)

## 2　有限世界信念

$w$ 是公开设计先验中的假设世界，包含族、原因、资料发布情形、报警类别和有限的需求、故障、供能与热过程参数。普通架构对四族给等先验；两种事故架构各自对十二种设计组合边际化，同一世界的重复质量相加。实际条件的族标签不会交给策略。对有效证据按来源和采样时刻归并，重新从先验计算下式，避免在相邻决策点重复乘入同一记录。

$$
b_t(w)=\frac{b_0(w\mid u)\,\ell_{\rm rec}(h_t\mid w)\,\ell_{\rm alarm}(h_t\mid w)\,
{\bf1}_{\rm permit,paid,write}(w,h_t)\,\ell_{\rm fixed}(w,h_t)}
{\sum_{v\in\mathcal W(u)}b_0(v\mid u)\,\ell_{\rm rec}(h_t\mid v)\,\ell_{\rm alarm}(h_t\mid v)\,
{\bf1}_{\rm permit,paid,write}(v,h_t)\,\ell_{\rm fixed}(v,h_t)} .
$$

登记通道在可观测的有效窗口内分别提供“已见”和“应可见但未见”的似然。报警出现与静默按可到达时刻的质量计，过期也允许解释静默。许可／供电返回、可解码的最新本人读数、已完成写入结果与假设世界不符时权重为零。固定测点共享设施瓶颈。设 $m$ 为各类最近有效固定读数数、$k_w$ 为其中匹配数，执行版只乘**一个**混合因子 $\ell_{\rm fixed}=(1-p)+(2p-1)k_w/m$；$m=0$ 时取 1。默认 $p=0.95$。冲突或归一化常数为零时不产生自选行动。物理生效时刻已获回执才能当作既成事实；预测可对未终止的发行暂按计划完工，随后仍按世界内成功条件计分。[世界目录](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_risk_dispatch/knowledge.py#L9-L57) · [完整后验](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_risk_dispatch/belief.py#L64-L120)

## 3　整窗目标与一次读数的分支

设实际需求、交付为 $d(t),y(t)$，服务端点为 $L=\int_{d(t)>0}(d(t)-y(t))/d(t)\,dt$，单位为归一化缺额秒。未交付总量 $U=\int (d-y)\,dt$ 另计。多个限制作用于同一服务，只计一次交付缺口。实际人秒、工具秒、费用和带执行身份的有效关闭分别报告。在线用公开代理预测 $\widehat L,\widehat T_{\rm person},\widehat F$，在可行的计划 $\pi$ 上最小化

$$
J(\pi\mid h_t)=\mathbb E_{b_t}[\widehat L+\lambda(\widehat T_{\rm person}+\kappa\widehat F)].
$$

$\lambda=1$ 缺额秒／人秒，$\kappa=30$ 人秒／发行费单位。既发行成本在各候选间共同保留，未来费用只对情景内实际会发行的作业计入。工具有独立硬预算。这个排序分与窗口末的实测 $L$ 是两个量；事后选择效果使用后者。[代理服务曲线](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_action_cost/forecast.py) · [分支成本](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_action_cost/planning.py#L119-L141)

等待及直接处置的候选值是在当前信念下，从包括空序列的所有剩余具名写入排列前缀中择优。初检 $i$ 在计划采样时刻把世界按报告签名 $z=g(w,i,h_t)$ 分组，$\mu_z=\sum_{g(w)=z}b_t(w)$，$b_z(w)=b_t(w){\bf1}_{g(w)=z}/\mu_z$。$q=1/32$ 是计划中不能解释报告的概率。令 $C(i,\sigma;b)$ 包含该首步和可行后继序列的整窗成本，则

$$
Q(i)=(1-q)\sum_{z:\mu_z>0}\mu_z\min_{\sigma\in\mathcal S_{i,z}}C(i,\sigma;b_z)
+q\,C(i,\varnothing;b_t).
$$

一个可见签名只允许一份共用后继。UNKNOWN 分支暂停自选写入，保留现有义务。可解释、足够的报告会打开续核的可行性检查；缺任一正质量分支的完整可行计划则该首步不能参评。实际窗口下一公开时刻根据最新记录重新决策。计划内部并不会发行这些后继请求。候选先按九位小数的 $J$、人秒、费用排序，再优先等待和稳定首步标识；续排内部同分还按长度与序列决定。$q$ 是评分端的报告假设，调它不改变原生传感器。[报告分组与破平](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_action_cost/planning.py#L144-L209)

## 4　单个决策点的代价

令 $N$ 为世界数，$r$ 为视图记录数，$m$ 为未发行且尚在窗中的主处置数，$F$ 为可行根选择数，$g\le N$ 为一次读数的不同签名数，$K\le61$ 为余下公开时点数。以 $s$ 表示该点仍需考虑的主体和义务总数，$e$ 表示单世界预测曲线段数。已有初检或数据冲突时也会付出视图验证和后验计算成本。记这部分为 $C_b$。代码对世界逐一筛除；每世界扫描适用记录和预测，来源匹配中还含逐记录查找，设 $C_{\rm pred}$ 是一次假设世界的固定测点／付费签名预测成本，则保守地可写成 $C_b=O(r^2+N(r^2+(r+s)C_{\rm pred}))$（固定种类的外生资料通道）。该界保留来源匹配、目标查找和历史长度。

待比较首步至多为一个等待和每个主工单的两种自选请求，$F\le1+2s$。剩余写入的排列前缀数 $P_m=\sum_{j=0}^{m} m!/(m-j)!$。记 $C_{\rm cal}$ 为一次可行日历推进，$C_{\rm eval}$ 为一次单世界计划计分。保守上界为
$$
O\!\left(C_b+F\,P_m\,(g+1)(C_{\rm cal}+N C_{\rm eval})\right).
$$
$C_{\rm cal}$ 扫描至多 $K$ 个时点，每点排序义务、查询约束、路径及预算；有缓存时，同一主体／位置的行走时长可复用。$C_{\rm eval}$ 含步骤扫描、世界内写入效果、采样与服务曲线；v3 的区间重叠实现逐断点扫描各曲线段，缓存失配时这部分最坏为 $O(e^2+e\log e)$。分组实际只对相应子后验求值，所以上界偏松。空间包括 $N$ 个权重、枚举路径及各签名的续排，按单根流转时为 $O(N+P_m(m+s+K)+Fg(m+1))$，另加有界预测缓存和输入记录。这里给算法上界，实际延迟取决于开放工单、日历和缓存。基线的枚举／模拟预算在冻结协议中另计。[排列与日历](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_action_cost/planning.py#L10-L117) · [预测缓存与区间合并](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_action_cost/forecast.py#L22-L34)

## 5　与英文稿 [2]、[3]、[4] 的方法关系

| 原工作 | 它实际解决的问题 | 本研究增加的决策问题及比较边界 |
|---|---|---|
| [2] Memarzadeh 与 Pozzi | 在序贯维护中评估部件检查、持续监测及系统级排程的决策价值。 | 这里把付费初检、报告到达、单次发行和与本次执行绑定的复核置于同一时钟，用真实禁购消融估计可购买这项能力的服务差。本文的短视对照是本地单步 VoI 适配。 [原文](https://doi.org/10.1016/j.ress.2016.05.014) |
| [3] Andriotis 与 Papakonstantinou | 用深度强化学习求解信息不完整且有约束的检查维护规划，处理多部件风险与成本。 | 本方法逐决策点显式枚举有限世界与合法续排，给出可读的分支和作业身份。没有在本设施训练或评价该文的网络；树搜索对照只检验另一种在线规划方法。 [原文](https://doi.org/10.1016/j.ress.2021.107551) |
| [4] Fauriat 与 Zio | 按当前状况和未来检查的预期价值选择下一次检查或更换时机，研究随机退化和全生命周期成本。 | 本文关注当前工单的读数能否赶上一次有限许可窗，并用全窗服务缺额量化等候和处置的共同影响。单次购买的期望价值、每条件服务差及生命周期费用分别解释。 [原文](https://doi.org/10.1016/j.ress.2020.107133) |
