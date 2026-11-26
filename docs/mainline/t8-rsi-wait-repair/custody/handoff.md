# 保管端交接

### 1. PI 发布签发身份

PI 在 `ef37ca0e` 发布 Ed25519 公钥，并在 `5f1b50df` 发布对原挑战的分离签名，执行方验签通过。按 PI 最新决定，本次 FIT 采用同一 Windows 账号，按程序分工保管与比对。PI 原登记和配对证据在各自提交中保留。公开签名用于核实签名内容；人员是否预览需按实际操作记录另行说明。[本次修订](../stage1b/fit-shared-account.json)

| 登记字段 | PI 填写值 |
|---|---|
| `custodian_id`、`auditor_id` | 两个不同的事前公开角色代号。首字符为小写字母，后续可用小写字母、数字、下划线或连字符，总长至多 32。代号在查看批次前固定。 |
| `algorithm`、`signing_method` | 分别填 `Ed25519`、`detached`。保管端对规范回执字节签名。审计方的身份、核验记录和签署证据由保管端留存。 |
| `public_key_hex`、`fingerprint_sha256` | 前者为原始公钥的 64 位小写十六进制，后者为该 32 字节公钥的 SHA-256 小写十六进制。 |
| `generated_at_utc` | 实际生成时刻，采用 `YYYY-MM-DDTHH:MM:SSZ`。 |
| `credential_separation` | 本次已确认同账号，生效值为 `shared_account`。验签器拒绝用本次公钥声明 r0 的 `independent`。 |
| `device_separation` | 独立设备填 `separate_device`。若 PI 在本机使用隔离身份签名，填 `pi_local_no_device_separation`，明确设备共用。 |

制板方和执行方经已认证的当面或私有渠道确认 PI 的发布提交和公钥指纹，保留这份可信副本。来件中附送的公钥不能更换这次登记。[公钥登记](authority.json)

### 2. 保管端发布覆盖声明

旧目录副本及 H3 既有封存输入承诺只用于目录核对和整批比对。方案 C 按程序约束访问，不对同账号作设备或凭据隔离背书。模板列出十项公共版本参照、计数来源和所需编码。保管端核对原目录后填写每行的 `custodian.version`、`expected_counts`、`identity_encodings`。实际扩展、复用、工程包装和别名纳入完整私有目录后，填写 `issued_by`、整目录根 `catalogue_root` 及 `additional_realizations_and_aliases_reconciled`。根承诺的是核实过的版本、基数、编码、别名关系和输入承诺。

| 编码 | 保管端的核对对象 |
|---|---|
| `historical_full` | 按各历史版本的原始完整输入编码比较，保留该版本的行尾、包装和规范化约定。 |
| `v3_operative` | 对 `native`、`attachment`、`maintenance` 三字段的排序紧凑 JSON（无 LF）取 SHA-256。 |
| `legacy_common` | 针对旧 T3，在新旧两侧对称比较 `native`、`attachment`。新的有维护输入只按 r0 的精确签发令规则还原 `OPEN`，保留其余实际状态和时间。 |
| `sealed_full`、`sealed_operative` | 使用旧 H3 索引已封存的两种逐输入承诺。新侧提供可比编码；H3 种子、原始条件、轨迹和成绩保持封存。 |

T5 v3b 复用 v3a 的 36 行，两者指向 r0 同一计数条目。v3c 的旧板与新板分列，T7 阶段 1 的 24 行保留其 T3 别名。保管端私下证明复用关系并核对原件，保留额外实现的去重证据。对尚未证实的覆盖项保持待填状态。模板里的公开条数不能替代对原件的核验。[覆盖模板](catalogue-coverage.json) · [冻结的条数与编码出处](../r0/panel-law.json)

### 3. 步骤 0 复核，然后单次交接

1. 执行方用已配对的 PI 公钥、同账号 FIT 修订和已发布的完整覆盖声明复核步骤 0。覆盖待填时，状态为“目录覆盖待核实”。自检可在这个状态下独立通过。
2. 获准后，制板方一次冻结完整批次，以认证渠道交付原请求及私有清单。清单承诺登记、split、完整有序输入和签名随机来源。FIT 是两族合计 48 行的一次请求。将来获准的 DEV 另有一次机会，其私有清单还须承诺此前的 FIT 索引和双锁回执。保管端核验请求者身份、登记规模和清单内容，以 r0 规范对象字节重算 SHA-256，与公开请求中的 `batch_root` 比对。公开请求始终只有四个字段。
3. 保管端按 `(父登记 ID, split)` 在持久账中原子占用一次机会，再开展全量核对。r0 和本次修订归入同一个 FIT 消费位置。请求与回执签名绑定实际采用的登记 ID。按冻结投影比较批内重复和与所有旧输入的相交，最后一次性发布整批结论。
4. 保管端按九字段格式签发一份回执。由 PI 或获授权的发布者把**原回执和分离签名**带回当轮结果记录；执行方用事前保留的请求、可信公钥和目录根运行只读验签。保管端的行级材料、覆盖分项、来源计数和审计底稿留在私有边界内。[回执格式和核验命令](README.md)

### 4. 保存停止现场

收到 `BLOCKED` 后保留原请求、批次、原回执、签名、消费记录及私有核查现场，停止该 split 的评分并交审。字段缺失、签名不可验、来件遗失或中途退出，也保持停止和原尝试记录。可离线反复核验**同一份**来件；正式查询不得重发、拆分、换根、补抽或按来源排查。真实 FIT 只在正式回执验得 `PASS` 后才按阶段 1b 任务书继续。

### 初版骨架自审（`9cb06a4d`）

以下是占位版的 `--check` 完整输出，退出码为 0。独立的 PowerShell `Test-Json` 校验器另验 65 个案例，13 个接受，52 个拒绝，全部符合预期。观察自检期间的文件打开操作，只读取了 9 个仓库内公开文件，没有写入、联网或启动子进程。正常验签入口在两个占位文件下返回 `NOT READY`，退出码为 1。

```text
PASS request schema: 4 required fields; closed payload, duplicate keys and noncanonical bytes checked
PASS receipt schema: 9 required fields; aggregate coverage, complete BLOCKED and trusted bindings checked
PASS authority: all 9 fields PENDING_PI; formal verification unavailable
PASS catalogue: 10 named sources checked against r0 count references; custodian declarations pending
PASS Ed25519 / cryptography 44.0.0: archived engineering signature verified; message change, signature change and cross-use rejected; engineering signers excluded
SELF-CHECK ONLY; no official request, receipt, signature creation or file write
```

密钥核对覆盖本次目录的全部文件及其可达提交版本，同时检查全库可达引用和 reflog 中曾出现的常见密钥容器文件名。公开源码及文本日志另查私钥封装、SSH 公钥、私有 JWK 和明文签名密钥赋值，只统计命中数。七个文件中的长十六进制字面量均可对应既有公开登记、版本或文件摘要。旧 r1 工程归档含既有工程公钥和签名，本轮仅作只读自检。H2 和 H3 封存原件未纳入内容扫描。

```sh
git diff --name-status 663cadee HEAD
git log --all --reflog --full-history --no-renames --format=%h --name-status -- docs/mainline/t8-rsi-wait-repair/custody/
git rev-list --objects --all --reflog -- docs/mainline/t8-rsi-wait-repair/custody/
git log --all --reflog --full-history --format= --name-only -- ':(icase,glob)**/*.pem' ':(icase,glob)**/*.key' ':(icase,glob)**/*.p12' ':(icase,glob)**/*.pfx' ':(icase,glob)**/id_ed25519' ':(icase,glob)**/id_rsa'
```
