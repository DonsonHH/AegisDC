# 1–38跨阶段覆盖矩阵：Spec轴

固定检查源：`f73c57f8806dcc6e23d510e83391b0f46677b6cc`；功能基点：`8e32a8075fb86de0818f8149d4e47cdae3170ad9`；用户科学审阅参考：`2f3fb67f`。39a是跨阶段范围复核，不重审180份历史轨迹，不重跑旧验收，不在本地重算任何研究指标。

1–35复用`docs/mainline/audits/20261108-pre36/ticket-matrix.md`及其原审计/补正包；该矩阵的`2dfe5537`时点和当时F1发现保留。F1的**读出披露遗漏已在进入36前补正**；故障真值、机会分母、预防与正式关闭仍未操作化/未评价，二者不能混成“原读出仍失败”或“业务指标已测”。36–38引用其已接受原件。所有旧接受均按原声明有限范围保留。

源码/原件列给出实际源码、原验收记录或原件入口，完整原始文件集沿对应记录追溯；不是新的执行收据。

“正式比较覆盖”说明原31/33/35/36究竟检验了什么。某模块在八域设施中运行，并不等于其全部失效模式、参数域或独立业务效应已被正式比较。表中后续工作是用户指定39b–39d补全，不是宣称旧有限结论被推翻。

|票|实现/接口|既有工程验收范围|正式比较覆盖|尚未覆盖及后续|实际源码/原件定位|
|---|---|---|---|---|---|
|01 固定主线|单一合成设施、八域四图、阶段与条件分支|目标、领域边界和依赖契约|为180次提供共同定义，不是效果试验|总目标未完成；39a→39b/39c→39d→39；资格与优先级分开|`docs/MAINLINE.md`；`docs/adr/0003-complete-facility-mainline.md`；`.scratch/full-facility-mainline/spec.md`；issue01|
|02 场景契约|闭合场景加载、身份/图/单位/范围及未知检查|V6结构及输入拒绝边界|同一V6作为正式运行底座|结构合法不等于动态真实或现场校准|`src/aegis_dc/scenario.py`；`src/aegis_dc/runtime_contract.py`；`configs/full-facility-mainline-reserve-v6.json`；`docs/mainline/evidence/02.json`|
|03 正常全场|电热、水、服务、控制、空间与人员同场演化|正常运行与无自动巡回见证|正式运行沿用耦合设施，不是对每域分别作效果估计|原v2见证有原版本；V6与现场真实性分开|`src/aegis_dc/plant.py`；`src/aegis_dc/workforce.py`；`evidence/mainline/engineering/03-root-demonstration/README.md`|
|04 供电传播|容量分配、受保负载和供电约束|供电/整流/分配与失电反例|部分负荷、断电、备用条件进入正式研究|MV/LV是理想聚合边界；独立变压器损耗/电压/支路保护未建模，不冒称全站电气仿真|`src/aegis_dc/power.py`；`src/aegis_dc/plant.py`；`docs/mainline/evidence/04.json`；工程11原件|
|05 水热响应|泵、滤阻、阀、板换与内循环耦合|有限拓扑的水力/换热及守恒见证|滤阻与冷却掩蔽核等有限工况|不是通用任意管网；水力参数尚非现场标定|`src/aegis_dc/heat_transfer.py`；`src/aegis_dc/plant.py`；`docs/mainline/evidence/05.json`；工程11原件|
|06 相变库存|参考R134a同表质量/内能/容积状态与冷凝接口|有限物性域、相态/库存及域外拒绝|正式设施包含该热状态；没有实测工质或相变方案对比|真实介质未知；冻结表范围不是全EOS域或任意时程误差界|`src/aegis_dc/thermodynamics.py`；`src/aegis_dc/refrigerant_initialization.py`；`configs/materials/reference-r134a-saturation.json`；`docs/mainline/evidence/06.json`|
|07 环境与访问|房间、泄漏/排水和可达/安全限制|房间/积水/门禁及实际中止见证|有限保护/访问条件影响执行|不覆盖全部环境事故或现场人员安全标准|`src/aegis_dc/environment.py`；`src/aegis_dc/plant.py`；`src/aegis_dc/workforce_dispatch.py`；`docs/mainline/evidence/07.json`；工程21安全原件|
|08 服务账|需求外生保留，实际交付受共同瓶颈限制；实际功率供热|服务、容量及未交付需求账|主要结果和各阶段实际服务结果|归一化服务单位，不等于实际FLOP/s、业务SLA或现场可靠性|`src/aegis_dc/power.py`；`src/aegis_dc/plant.py`；`docs/mainline/evidence/08.json`；`evidence/mainline/research/34-paired-analysis/results.json`|
|09 本地控制|本地采样、控制、保护和失联规则独立于上层调度|传感偏差、链路和保护反例|本地保护保留在所有方法中，不能归为人工收益|未全面覆盖控制器/仪表故障分布；本地可见状态不是调度遥测权限|`src/aegis_dc/local_control.py`；`src/aegis_dc/plant.py`；`docs/mainline/evidence/09.json`；工程11原件|
|10 有效备用|UPS能量、燃料/启动器、维护与切换，备用冷源延时|有限储能、柴油和备用冷却工程案例|36的UPS在役/下线与相同断电是有限结构变体|不是设备数量可用度；10秒比较不能代表所有备用过程，39d复核相对时轴|`src/aegis_dc/reserve.py`；`src/aegis_dc/power.py`；`docs/mainline/evidence/10.json`；工程23备用案例；36原件|
|11 全设施工程门槛|八域共享身份、服务瓶颈和执行约束|命名跨域事件/容量/人员工程见证|八域设施承载正式比较|工程跨域覆盖不是八域风险均量化，更不是所有事故已比较|`src/aegis_dc/plant.py`；`src/aegis_dc/runtime_contract.py`；`docs/mainline/evidence/11.json`；`evidence/mainline/engineering/M1-root-acceptance/README.md`|
|12 数值资格|解析/参考、守恒、步长、事件与域外处理|冻结案例/步长阶梯及原NO-GO、失败保留|正式研究使用声明的V6及最大步长|没有普适误差定理；39d的新窗口/扰动需对应资格，不能套旧有限见证|`docs/mainline/evidence/12-root.json`；`evidence/mainline/engineering/M2-root-acceptance/README.md`；`src/aegis_dc/thermodynamics.py`；`src/aegis_dc/heat_transfer.py`|
|13 外生重放|记录外生事件、输入、源码、解释器与运行生命周期|因果、拒绝与重放工程原件|保障原件身份；重放不增加独立统计单位|不等于新未见确认；不授权重新挑选/重跑原180|`src/aegis_dc/replay.py`；`src/aegis_dc/replay_format.py`；`docs/mainline/evidence/13-root.json`|
|14 证据台账|观测/到达/有效期、来源、复制/相关、冲突与缺失|明确时标和未知/阴性反例|正式策略使用到时可用记录|台账能力不等于所有报障真值/误报漏报端点已定义|`src/aegis_dc/evidence_ledger.py`；`docs/mainline/evidence/14-root.json`；pre36保存读出|
|15 真值隔离|封闭公开frame与声明静态知识，后台状态留私有|同公开信息、不同隐藏状态的有限非干扰见证|正式运行相同公开接口/历史下比较|不是对敌意宿主的安全证明；39b新问题/任务规则仍须同信息检查|`src/aegis_dc/decision_view.py`；`src/aegis_dc/policy_execution.py`；`docs/mainline/evidence/15-root.json`|
|16 稀疏固定测点|可停用、有延迟/误差的公开观测律与私有实现分离|稀疏、缺失、偏差和时标工程验证|36只改变一个整流表计的启用状态；其他正式固定误差有明确设定|不推广为一般传感覆盖最优性/现场噪声性能|`src/aegis_dc/sensor_channels.py`；`src/aegis_dc/live_sensor_execution.py`；`docs/mainline/evidence/16-root.json`；36 R2|
|17 非固定信息|历史/人工/工单/手持数值或二值结果|有限声明误差与迟到原件|人工提示、有效期与便携流量测量进入正式条件|二值夹具的错检例不等于正式通用误报/漏报率；39c补真值和机会分母|`src/aegis_dc/nonfixed_evidence.py`；`docs/mainline/evidence/17-root.json`；`src/aegis_dc/inspection_execution.py`|
|18 认识更新|有限隐状态、年龄、关联/副本、冲突与未知处理|合成列举/校准和错误比较器|正式策略沿用声明先验/似然及认识更新|非现场经验校准；有限模式不等于完整资产状态辨识|`src/aegis_dc/belief.py`；`docs/mainline/evidence/18-root.json`；`configs/full-facility-belief-model-v1.json`|
|19 风险情景|8问题目录、联合服务后果、时窗/能力和未知|cooling/power两项有限条件法则；其余6项UNMODELED，有路径/界和转介|正式核只保留手编的有限问题结构，不代表目录八问题均进入动态选择|后备、IT、控制、访问、人员、房间6项概率/点风险仍未知；39b需代表性多系统问题实例及任务映射|`src/aegis_dc/risk_scenarios.py:263`及323–324；`configs/full-facility-risk-scenarios-v1.json`；`evidence/mainline/engineering/19-root-acceptance/README.md`|
|20 检查/行动价值|每个被覆盖问题比较暂缓、直接处置、检查后处置，服务与成本分列|单cooling、100秒二元有限树；多个先验/边界例验证计算|正式核仍是有限单问题的手编预测容量/观测律；不是从全设施自动生成的全场VOI|缺多问题竞争/一般选单与动态后续任务；预测值不等于实际效果，未知问题不赋零；39b补全|`src/aegis_dc/action_value.py:194`；`configs/full-facility-action-value-v1.json:33–36`；`docs/mainline/20-action-value-contract.md`；`evidence/mainline/engineering/20-root-acceptance/README.md`|
|21 专业执行|资质、工具、移动、排队/会合、班次、安全与实际占用|单/多人及拒绝/中止工程原件|正式任务按真实执行器运行；联合团队消融只操作规划选项|不等于全局最优团队分配；研究1秒工时/1–2秒路径与默认时间分层，39d补相对时尺度|`src/aegis_dc/workforce_dispatch.py`；`docs/mainline/evidence/21-root.json`；工程21原件；35 masks|
|22 真实检查|实际完成和资质/工具/工时后采样，延迟送达|采样与报告到达分别记录的工程见证|正式便携结果与命名信号阈值读数|阈值确认不是故障诊断/风险关闭；不能据此填误报漏报为0，39c补端点|`src/aegis_dc/inspection_execution.py`；`docs/mainline/evidence/22-root.json`；工程22原件；pre36读出|
|23 实际处置|授权/实际完成后一次性命名参数变化，失败无效果|网络恢复、清滤、算力请求和备用冷源等有限操作|正式只使用冻结输入中的有限操作/设定|集总参数变化不是现场修复；实际效果、反馈与验证关闭分别记账|`src/aegis_dc/intervention_execution.py`；`src/aegis_dc/plant.py`；`docs/mainline/evidence/23-root.json`；工程23原件|
|24 验证关闭|动作完成、症状退去、验证关闭、误报复核/接受风险/升级分离|有限条件/服务样本与授权案例；A02复核时钟另修并保留原失败|原31–36均closure_program=None，正式验证关闭NOT_EVALUATED|工程接口可用不等于业务端点已测；39c启用适当的处置后复检和时间窗，不能重标旧180|`src/aegis_dc/verified_closure.py`；工程24原件；`evidence/mainline/engineering/pre36-closure-review`；`scripts/prepare_comparison_worlds.py:24`|
|25 透明参照|无人工、周期、FIFO、风险优先及价值策略共享边界|有限公开选择、执行与成本案例|31/33六种方法；35/36按各自预定设计|周期只作参照；多参照不是多个因素分别被因果隔离|`src/aegis_dc/dispatch_policy.py`；`src/aegis_dc/policy_execution.py`；`docs/mainline/evidence/25-root.json`；协议30|
|26 候选方法|预期报告与到时证据更新一致的有限机制|手编两任务、实际检查/处置及网络瓶颈反例|主要确认在固定两任务下有真实选择差异；不是没有选择空间|ALREADY_ISSUED适用于同一实例；没有全场问题发现/新事件复检池或一般优化；39b增动态实例，38窄AI资格不撤回|`src/aegis_dc/lookahead_policy.py`；`src/aegis_dc/evidence_projection.py`；`dispatch_policy.py:145`；`scripts/prepare_comparison_worlds.py`；`docs/mainline/26-root-acceptance.md`|
|27 全闭环例|同设施外生扰动、本地保护、专业行动和后续证据|4秒自动恢复、6秒清滤、8.5秒关闭的工程轨迹|没有作为正式策略净收益/关闭样本加入180|自动恢复不得归为人工增益；单工程闭环不替代正式端点|`evidence/mainline/engineering/27-root-acceptance/README.md`；`src/aegis_dc/policy_execution.py`；`src/aegis_dc/verified_closure.py`|
|28 正常/负例|正常、提示、保护及来不及行动等有限情况|冻结工程正反例与实际成本/失败|正式包含有限误导提示/保护访问族|不是一般故障诊断性能或现场负例分布；39c补机会/真值定义|`evidence/mainline/engineering/28-root-acceptance/README.md`；`src/aegis_dc/inspection_execution.py`；`src/aegis_dc/intervention_execution.py`|
|29 参数与可行域|来源/单位/未知、标量域与联合可行性区分|八条命名联合轨迹；参考物性与四项现场缺口|为本轮选定工作点提供输入资格|106合成/7推导不是现场测量；非连续笛卡尔域或参数敏感度结论；39d补决策敏感参数及时间轴|`src/aegis_dc/parameter_domain.py`；`src/aegis_dc/water_envelope.py`；`docs/mainline/29-public-evidence-scope.md`；`docs/mainline/29-root-acceptance.md`；工程29参数台账|
|30 注册设计|主配对/独立单位、阈值、成本、种子、预算与失败规则冻结|输入/源冻结及释放门槛原件|原180设计与主要结果保持|原18标签的披露补正不等于未定义业务端点已测；原预算不授权39新试验，39c/39d与新39协议前置|`docs/mainline/30-comparison-protocol-v1.json`；`scripts/comparison_release.py`；pre36保存读出/补正|
|31 开发评价|6工况×6方法的预定开发、机会与实际账|原启动/终态/来源/失败政策交付|36次开发；不得充独立确认|10秒、手编任务；开发负结果不外推总体；端点仍受39c范围限制|`scripts/registered_development.py`；`scripts/development_journal.py`；`evidence/mainline/research/31-development/README.md`|
|32 确认冻结|独立输入、执行代码、解释器和原件完整性|96输入；水力/种子接口修订与原失败保留|为33的16独立工况提供身份门槛|完整性门槛不是业务价值证明；未见性不从重复重放取得|`scripts/prepare_confirmation.py`；`scripts/comparison_release.py`；`docs/mainline/32-confirmation-freeze.md`|
|33 独立确认|先收费后调用、唯一终态、完整原生原件与零自动重试|原96执行及保存身份已独立接受|16工况×6方法；独立分母为16而非帧/96次轨迹|两任务/10秒/固定问题结构；closureNone，泛化/诊断/预防未测|`scripts/registered_confirmation.py`；`scripts/development_journal.py`；`evidence/mainline/research/33-confirmation/README.md`|
|34 配对结论|固定分母的主结果、成本、分族/去族及无人工参照|保存分析、缺失规则与源数据审查|NO_PRACTICAL_GAIN、原16单位和六方法对照保持|效应有集中/抵消；无人工与候选均值相同不能只报省工。新集中度数值仅远端补读，不重挑确认|`evidence/mainline/research/34-paired-analysis/README.md`和`evidence/mainline/research/34-paired-analysis/results.json`；`scripts/analyze_registered_confirmation.py`；`scripts/summarize_comparison_facts.py`|
|35 机制消融|实际设施不变，屏蔽非固定信息、依赖/后果或多人选项|真实执行与公开/私有提交映射的原件|8工况×4视图；服务/成本方向分列|依赖与后果捆绑，不是纯图因果；团队选项不等于最优协作；不推广全场一般任务集|`scripts/ablation_planner.py`；`scripts/ablation_run_evidence.py`；`evidence/mainline/research/35-ablation/README.md`及`evidence/mainline/research/35-ablation/results.json`|
|36 稳健性|冻结负荷/单表计/UPS可用性/共享预测误差四轴|独立输入、源码、账与原件已接受|4区组、8工况、16运行；描述性有限差异|不是连续敏感性或场景分布总体证明；预测改变两法共同获益不归候选，实际动作.75保留|`scripts/robustness_release.py`；`scripts/registered_robustness.py`；`evidence/mainline/research/36-robustness/README.md`及`evidence/mainline/research/36-robustness/analysis-01/results.json`|
|37 报告与复算|来源绑定全文、架构/数据图、下载、原件索引|静态/字节与新Git交付；浏览器限制单列|展示原180已有结论，没有新增样本/收益|报告完整不等于会后业务目标全覆盖；网站补4工程图不增加正式比较量|`paper/mainline-report-20261108/report.md`；`paper/mainline-report-20261108/source-manifest.json`；`docs/mainline/evidence/37-root.json`；Lab发布记录|
|38 AI资格|窄结构化求解器替换可独立检验，能力/效果分开|原NOT_ELIGIBLE撤回与P2修订、原件和状态保留|定性可检验性结论；没有AI/RSI效果试验|39–42仍未完成。39b–39d是用户要求的研究优先级/覆盖前置，不重新否定窄AI资格|`docs/mainline/38-eligibility-audit-v2.md`；`docs/mainline/38-eligibility-decision-v2.json`；`docs/mainline/evidence/38-root.json`；`docs/reviews/20261109-user-review/response.md`|

## 保存数字的使用界限

主要结果、无人工参照、分族与去族描述只引用已接受的34报告/原JSON；本矩阵没有本地积分、求和、均值、集中度或时尺度比例运算。任何39a新集中度/单工况补读，以及39d新比例/敏感度数值，交由root在Slurm执行一次保存数据补读或另冻结工程验证。本矩阵不能代替该远端记录，也不能代替39b–39d的实质实现/验证。
