# T6 正文修订 r3：确认区间及两站读数归属

[修订正文](manuscript.md) · [HTML 阅读版](manuscript.html) · [台账](claims.json) · [变更行与差异表](changes.md) · [完整核验输出](verification.txt)

相对 21a4624b，只修订摘要、C1 数字段和导师五问两站的第二问。C4 归属填写“用户授权执行者选择”；沿用 A，C4 的原陈述和“未建立”状态均保留。r3 的科学数据不是新运行结果。

每个新数字有旧台账 ID 或 r3 只读附记 ID。后者在 claims.json 的 r3_supplement.numbers，不覆盖四项主张原有 numbers。r3_supplement.conditions 同时记录各角色已买读数的原件指针，分开表示“实际没有”和“该臂没有运行”。JSONL 输入的字段路径以源档零基行号开头。资格按有实际签发、作业完成、读数已到达且有有效字段、截止前可供决策等条件核对。常规开工授权、施工状态与登记类事前风险提示分列。

Markdown 的本地数字索引和 HTML 数字来源页随报告交付。所有数值均能回到相关 Git 提交与 JSON 字段。同名样本键不代表输入字节相同。未修改阶段 2、r2 和已审阶段 3，也未读取 H2 种子或旧种子目录。

核验命令：python docs/mainline/t6-paper-consolidation/r3/claims_check.py --check。只读，无文件写入。完成后停在 r3 审查。
