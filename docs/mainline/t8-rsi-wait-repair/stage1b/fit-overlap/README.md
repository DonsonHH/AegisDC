# FIT 整批查重回执

已对冻结的 48 条 FIT 输入发送并消费唯一一次请求。九字段回执记载 `PASS`，整批覆盖率 100%，全部必需测试完成。保管口径为同账号程序性查重，目录根与 PI 接受的 `61ba7c53` 一致。[原请求](request.json) · [原回执](receipt.json)

| 本次发布时的账目 | 实际值 |
|---|---:|
| 输入作业 | 135576，COMPLETED，退出码 0 |
| 冻结输入 / 正式请求 / 剩余机会 | 48 / 1 / 0 |
| 输入作业预留 / 实耗 CPU 秒 | 240 / 1.181 |
| 保管侧核对进程树 CPU 秒 | 2.500 |
| 制板与核对合计实耗 / 上限 CPU 秒 | 3.681 / 300 |
| 设施调用 / FIT 评分 / DEV 评分 | 0 / 0 / 0 |

初次发布 `a4f061f2` 时回执待签。PI 随后授权执行方在本机代签 [receipt-signing.bin](receipt-signing.bin) 的**全部 402 字节**，其 SHA-256 为 `f5378967de5d8a361136811d5156f8be9aff39e87afe7c0385d16dc1432a8cee`。正式验签器以原请求、原回执及 [64 字节分离签名](receipt.sig) 得到 `VERIFIED PROCEDURAL PASS`。这是同账号程序性放行。查重已经消费，后续核验只读保存材料。[代签记录](signature-provenance.json) · [版本与消费记录](attempt.json) · [Slurm 终态](authoring-accounting.psv)
