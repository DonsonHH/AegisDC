# 第19项当前运行与复核入口

当前作者候选使用修正后的`src/aegis_dc/risk_scenarios.py`，运行源为`99a2afeabf25f2d3d31f3ddbb1819ef15dbc153f`。第一次9c0数值更正保留其原身份。原工程捕获在`1939cb2f`执行，原数据交付`7069f2be`；两个身份不能合并。

- [原接口和建模范围](19-risk-scenarios.md)：公开帧、条件联合后果、八域问题和专业选项。
- [数值表示更正](19-bound-rounding-correction.md)：精确有理上界采用最小向外binary64表示；保持未知量、量纲及模型范围。
- [第一次更正候选](evidence/19-correction.json)：7个定点检查和原4帧结果一致，保留第一次修正执行身份。
- [当前第二版更正](evidence/19-correction-v2.json)与[完整时段输出更正](19-full-horizon-correction.md)：新增完整时段数值域校验，4个新API/CLI检查、7个先前检查和原4帧一致。
- [原捕获交付证明](evidence/19-original-delivery.json)和[修正交付证明](evidence/19-correction-delivery.json)：均由Root在干净管理检出中验证，无推断/物理/完整回归重跑。
- [图文工程报告](../../evidence/mainline/engineering/19-risk-scenarios/README.md)与[主来源适用性](research/19-source-applicability.md)。

原`19.json`是原作者候选记录，原`capture-01`/protocol/receipt保留；当前更新由`19-correction-v2.json`承载。作者没有执行完整回归。Root仍须完成修正后运行源的独立闭环与统一完整验收，ticket19保持claimed，M3和总研究目标继续。

首次根源码7b9的448项全执行结果保持为历史PASS；其后发现完整时段输出溢出问题，因此不能代表当前接受。当前源码需经新独立闭环、保存原件交付证明与新的Root统一完整回归。作者不重复原捕获或旧全回归。
