# T6 正文：版本与核验

[论文正文](../manuscript.md) · [HTML 阅读版](../manuscript.html) · [本版台账](claims.json) · [数字索引](evidence-notes.md) · [核验输出](verification.txt)

本阶段采用用户委托选择的 A：讨论当前合成发生器、面板与合法服务端点下，RSI 的独立增量为何不可辨识。C4 的增量证据状态仍是“未建立”。这不评价 RSI 在真实设施或其他任务上的普遍价值。

阶段 2 原版、修正 C1.B 的 [r2](../r2/README.md) 和本阶段分别留存。本版台账从 r2 派生，保留全部原始数值、反例及成立条件；只给 C4 增加已经裁决的正文措辞和裁决记录。机器核验入口为本目录的 claims_check.py。先核 r2 的原始 H1 判定，再回读上一阶段的每个科学数值，最后检查正文、索引、源文件摘要和 HTML 中的定量报告。

Markdown 正文中的每个数字都有专属的本地来源锚点；HTML 中点击数字直接打开 r2 冻结台账的原始行范围，包含对应 ID、字段与精确原值。机器版 [manuscript-numbers.json](manuscript-numbers.json) 保存两种定位、舍入方式、封存提交、文件、运算和行索引。条件键、版本和策略名中的数字是标识符，与测量值分别检查。关于两起事件的叙述只引用留存的官方复盘定位，不把事后信息送回决策端。HTML 是同一篇连续阅读页，每章的结论、数字及反例在同一章面板内；不需要跳去附录才能看到章内限制。

只读复核：python docs/mainline/t6-paper-consolidation/stage3/claims_check.py --check。设施调用、Slurm 作业、H2 生成／读取／派生均为零。等用户审查。
