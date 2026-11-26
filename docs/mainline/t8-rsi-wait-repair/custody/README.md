# T8 正式查重保管端

**本次 FIT 采用方案 C：同账号程序性查重。** PI 和执行方共用 Windows 登录，公钥配对挑战验签通过。此签名证明登记密钥能够签名。关于谁看过批次，依据是操作记录与审阅时的实际说明。覆盖声明、正式查重与 FIT 评分分别记账。[生效登记](../stage1b/fit-shared-account.json)

| 角色 | 保管与交接 |
|---|---|
| PI | 保管签名密钥，发布公钥并签署回执。公钥原始登记在 `ef37ca0e`，配对签名在 `5f1b50df`。 |
| 制板方 | 按冻结生成律一次制板，承诺整批根，经认证私交完整的新输入承诺和随机来源证明。提案方只能接收其获准看到的聚合信息。 |
| 保管端与审计方 | 同账号按角色核对完整旧目录、封存输入承诺、访问记录和一次性消费。逐行材料留在比对侧，审阅人如实说明人员的实际接触范围。 |
| 执行方 | 保存最初提交的四字段请求，用事前认可的 PI 公钥和已发布旧目录根只读核验回执。 |

### 对外载荷

| 文件 | 唯一允许的字段 |
|---|---|
| 请求 | `registration_id`、`split`、`batch_root`、`catalogue_root` |
| 回执 | 上述四项，加上 `custodian_id`、`auditor_id`、`aggregate_coverage_pct`、`all_required_tests_complete`、`decision` |

同账号 FIT 的登记 ID 取本次修订文件的 SHA-256；r0 原登记 ID 对应原独立口径。验签器同时核对公钥、凭据口径、登记 ID 和 split。同一笔签名不能在这两种口径间通用。两个根是整批承诺，两个公开角色代号仍与登记逐字匹配。公开回执仍为九字段，决定取 `PASS` 或 `BLOCKED`，分离签名为 64 字节。[请求格式](request.schema.json) · [回执格式](receipt.schema.json) · [r0 单次查询契约](../r0/design.json)

**聚合覆盖率按整批行数计算。** 令 N 为登记的批次大小，n 为已按完整冻结目录做完全部必要身份比较的输入行数，公开整数 `floor(100 × n / N)`。命中重合也算已完成比较。逐行结果、来源分解、匹配身份和失败原因保留在保管端。全局身份或权限核对尚有缺项时，完成标志为 false。只有覆盖率 100、全部必需测试完成、每项必需交集和批内重复均为零、权限有效，才能签发 `PASS`。完整核对后发现重合时仍应签 `BLOCKED`，此时覆盖率可以是 100。

### 只读验签

请求及回执的文件字节统一为 UTF-8 的紧凑 JSON，键按 ASCII 排序，ASCII 转义，一个结尾 LF，无 BOM。**签名消息是该 JSON 去掉唯一结尾 LF 后的字节**，与 r0 的对象编码相同。验签器拒绝重复键、额外字段、非规范载荷及身份或根替换。计算公钥指纹时，对原始 32 字节公钥取 SHA-256。

```sh
python -B verify_receipt.py --check
python -B verify_receipt.py --request original-request.json --receipt received-receipt.json --signature received-receipt.sig
```

代码使用 Python 标准库，Ed25519 验证固定使用 `cryptography==44.0.0`。自检核对公开的配对原件和 r1 工程样例。正式验签会拒绝工程公钥，并将本次公钥限定到同账号 FIT。自检成功退出码为 0；正式核验中，同账号回执显示 `VERIFIED PROCEDURAL PASS`（0）或 `VERIFIED PROCEDURAL BLOCKED`（3）。未就绪或无法验证为 1，用法错误为 2。[验签器](verify_receipt.py) · [所用验签 API](https://cryptography.io/en/44.0.0/hazmat/primitives/asymmetric/ed25519/)

完整旧目录的实际覆盖和根哈希是步骤 0 的另一项依据。配对签名不占用正式查询机会。[当前公钥登记](authority.json) · [覆盖声明](catalogue-coverage.json) · [交接与停止规则](handoff.md)
