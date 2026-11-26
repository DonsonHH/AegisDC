# T11-0｜ESWA 重新定位与补充协议（待 PI 审阅）

**建议主语为“维护降级计算设施中的成本感知信息价值调度”。** 论文回答何时检查、等待、直接处置或复核，按共同服务交付评价决策。原 H1–H3 保持确认地位；两种新对照和八个参数变体只有事后补充资格。递归改写留给另项研究。本次提交停在协议和文书，没有启动 T11-1。

| 交付 | 用途 |
|---|---|
| [导师一页说明（PDF）](advisor-note.pdf) · [网页](advisor-note.html) · [可编辑原文](advisor-note.md) | 一页内说明完整设施方法、已有证据、情景风险和 RSI 分工。 |
| [定位、三个标题和目录](positioning-and-outline.md) · [主张表 v2](claims-v2.md) | 逐节 16 页预算，C1–C4 逐行对应原表、数字和反例。 |
| [六项 ESWA 缺口与 v3 工程依据](gap-audit.md) | 区分现有证据、可直接做的写作和真正需要的新运行。 |
| [50 篇候选文献](literature-map.md) · [DOI 登记核验回执](doi-verification.json) | 2022–2026 年 43 篇，期刊内直接应用 8 篇，每篇有题名、年份、去向及选用理由。 |
| [方法形式化](method-formalization.md) | 状态与公开边界、共同可行域、后验、J、UNKNOWN、算法复杂度及与三篇既有工作的差异。 |
| [有效冻结入口 v1.1](protocol-freeze.json) · [补充协议](supplement-protocol.md) · [四项裁定](protocol-addendum.md) · [机器清单](design.json) · [原冻结回执](protocol-lock.json) | 实施时先读 v1.1 的优先关系。该入口绑定所有规范字节。 |
| [FEMA 式情景分析](risk-reweighting.md) · [六族均值](risk-family-means.tsv) · [三组权重的完整结果](risk-scenarios.tsv) · [公开读表程序](public-weighting.py) | 使用原开发行和同输入 B_cost，分别给出服务和资源差，现场频率未识别。 |
| [自审、两路复核及账目](review-and-receipt.md) · [只读核验器](verify.py) · [逐文件 SHA-256](SHA256SUMS.txt) | 从新检出复核输入、版本、数字、DOI 表与版面。 |

[原始协议冻结 `0a97b43a`](https://github.com/DonsonHH/AegisDC/commit/0a97b43aefd8f6b6fe1af8af57e7d990b223749a) 先固定了 72 行、频率、两项基线、八个 OAT 变体和预算。[执行前 v1.1 冻结 `4f6843a8`](https://github.com/DonsonHH/AegisDC/commit/4f6843a8c56de353cfaaedcafb88f9e46a84e5f1) 补足共同合法动作、树内观察、违规推断与叶计量。**有效协议 SHA-256 为 `8dfc03a7c1df9c254f246e1d40add424a0c04218ffdd345acc2b05ade6dc7284`**，对应 `protocol-freeze.json` 的原字节。

## 执行交接

后续如获授权，最多 720 次新设施运行、63 个单核作业、229,800 预留 CPU 秒。新基线目前没有研究结果，场站年损和逐决策点耗时也仍未实测。公开读表算术及文献检索属于本轮文书。设施调用、Slurm 作业和 H2/H3 封存材料生成、读取、派生均为 0。

在独立检出的仓库内运行 `python -X utf8 -B docs/mainline/t11-eswa-revision/verify.py --check --checkout-bytes`。需要 Python、Git 和 pypdf；物理页数也可用 Poppler 的 `pdfinfo` 交叉读取。核验读取既有的公开开发汇总、文档元数据和 Git 对象，不登录服务器或调用策略。另加 `--live-dois` 可通过 requests 逐篇重查 Crossref 题名、年份及 DOI Handle；普通检出核验只读随包回执。目录清单覆盖所有交付项，清单自身摘要见交付消息。
