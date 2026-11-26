# T8 正式查重保管端

本次交付七个骨架文件。`authority.json` 等 PI 本人发布签发身份，`catalogue-coverage.json` 等保管端声明实际覆盖。正式查重次数为 0。

| 角色 | 保管与交接 |
|---|---|
| PI | 离线建密钥，保管私钥，本人提交公钥登记。用已认证渠道告知制板方和执行方该提交与公钥指纹。 |
| 制板方 | 按冻结生成律一次制板，承诺整批根，经认证私交完整的新输入承诺和随机来源证明。提案方只能接收其获准看到的聚合信息。 |
| 保管端与审计方 | 保管端独立持有只读旧目录及 H3 的预封输入承诺索引，与开发、评分、Slurm、仓库写入凭据分离。独立审计方核验身份、覆盖、访问和单次消费记录。保管端签发整批结论。 |
| 执行方 | 保存最初提交的四字段请求，用事前认可的 PI 公钥和已发布旧目录根只读核验回执。 |

### 对外载荷

| 文件 | 唯一允许的字段 |
|---|---|
| 请求 | `registration_id`、`split`、`batch_root`、`catalogue_root` |
| 回执 | 上述四项，加上 `custodian_id`、`auditor_id`、`aggregate_coverage_pct`、`all_required_tests_complete`、`decision` |

登记 ID 取冻结的 r0 登记文件 SHA-256。两个根均为不透明的整批承诺。两个角色 ID 必须逐字匹配 PI 登记的公开代号。请求与回执的字段集均封闭，结果只取 `PASS` 或 `BLOCKED`。签名以独立的 64 字节二进制附件传递。[请求格式](request.schema.json) · [回执格式](receipt.schema.json) · [r0 单次查询契约](../r0/design.json)

**聚合覆盖率按整批行数计算。** 令 N 为登记的批次大小，n 为已按完整冻结目录做完全部必要身份比较的输入行数，公开整数 `floor(100 × n / N)`。命中重合也算已完成比较。逐行结果、来源分解、匹配身份和失败原因保留在保管端。全局身份或权限核对尚有缺项时，完成标志为 false。只有覆盖率 100、全部必需测试完成、每项必需交集和批内重复均为零、权限有效，才能签发 `PASS`。完整核对后发现重合时仍应签 `BLOCKED`，此时覆盖率可以是 100。

### 只读验签

请求及回执的文件字节统一为 UTF-8 的紧凑 JSON，键按 ASCII 排序，ASCII 转义，一个结尾 LF，无 BOM。**签名消息是该 JSON 去掉唯一结尾 LF 后的字节**，与 r0 的对象编码相同。验签器拒绝重复键、额外字段、非规范载荷及身份或根替换。计算公钥指纹时，对原始 32 字节公钥取 SHA-256。

```sh
python -B verify_receipt.py --check
python -B verify_receipt.py --request original-request.json --receipt received-receipt.json --signature received-receipt.sig
```

代码使用 Python 标准库，Ed25519 验证固定使用 `cryptography==44.0.0`。自检只读公开 r0、r1 和本目录，在内存中验证一份已封存的工程签名，并检查改动消息或签名后的拒绝行为。r1 两次工程作业中的签发公钥均排除在正式信任范围外。自检成功退出码为 0；正式核验时，0 表示验真的 `PASS`，3 表示验真的 `BLOCKED`，1 表示未就绪或无法验证，2 为命令行用法错误。[验签器](verify_receipt.py) · [所用验签 API](https://cryptography.io/en/44.0.0/hazmat/primitives/asymmetric/ed25519/)

下一步由 PI 审骨架并填写公钥登记。保管端发布覆盖声明后，执行方方可复核步骤 0。[PI 登记占位](authority.json) · [覆盖模板](catalogue-coverage.json) · [交接与停止规则](handoff.md)
