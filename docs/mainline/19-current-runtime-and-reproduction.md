# 第19项当前运行与复核入口

当前作者候选使用修正后的`src/aegis_dc/risk_scenarios.py`，运行源为`9c0efc4dbd198d3fbf35c459cd5710c058a60569`。原工程捕获在`1939cb2f`执行，原数据交付`7069f2be`；两个身份不能合并。

- [原接口和建模范围](19-risk-scenarios.md)：公开帧、条件联合后果、八域问题和专业选项。
- [数值表示更正](19-bound-rounding-correction.md)：精确有理上界采用最小向外binary64表示；保持未知量、量纲及模型范围。
- [当前更正候选](evidence/19-correction.json)：7个定点检查和原4帧结果一致，单独记录修正执行身份。
- [原捕获交付证明](evidence/19-original-delivery.json)和[修正交付证明](evidence/19-correction-delivery.json)：均由Root在干净管理检出中验证，无推断/物理/完整回归重跑。
- [图文工程报告](../../evidence/mainline/engineering/19-risk-scenarios/README.md)与[主来源适用性](research/19-source-applicability.md)。

原`19.json`是原作者候选记录，原`capture-01`/protocol/receipt保留；当前更新由`19-correction.json`承载。作者没有执行完整回归。Root仍须完成修正后运行源的独立闭环与统一完整验收，ticket19保持claimed，M3和总研究目标继续。
