---
title: ESWA 英文稿交审
subtitle: 维护降级计算设施的核查与处置调度
lang: zh
template: sheet
theme: paper
mode: light
cols: 2
---

## 英文正文与可编辑文件 {span=2}

目标期刊为 *Expert Systems with Applications*。全文采用 T11-0 推荐的主标题。八节依次呈现完整设施决策、方法、预注册比较、维护时长、事故族、事后开发面板、暴露频率情景及反馈改进。正式投稿由作者决定。

[英文 PDF（12 页）](manuscript.pdf) · [可编辑 Word](manuscript.docx) · [方法、数字与参考文献源稿](manuscript.md)

## 确认面板回答的问题

在相同的 144 个条件上，方法减两种透明直接规则的平均缺额分别为 −343.90 和 −390.48 秒。同策略仅切换初检权限时，差值为 −55.83 秒，双侧 95% 区间为 [−110.00, −11.61]。允许初检时平均用工 128.92 人秒，禁购时为 107.57 人秒。

[主张表 v3](claims-v3.md) · [补充 A（协议与身份）](supplement-A.pdf)

## 开发面板补充的问题

短视 VoI 在 72 条条件上逐行取得相同缺额，其中 3 行的派工和成本有差异。POMCP 使用更多人力、费用，窗末有效复核关闭为 52 项，中心为 36 项。两者服务差的区间跨零。分层和参数响应限定在已用开发材料内。

[补充 B（全表导读）](supplement-B.pdf) · [公开全表 ZIP](supplement-B-tables.zip) · [36 项原件索引](supplement-B-index.tsv)

## 数字与措辞核验

628 项追溯记录覆盖正文数值、文献标识、公式、图和版面编号。正文中的五个公式和六个表格均可编辑。正文第 9 页的反馈部分保守计为 0.219 页。

[逐项数字出处](numeric-trace.tsv) · [五条审核意见对照](wording-audit.md) · [补充 C（保管与签名）](supplement-C.pdf) · [SHA-256 清单](SHA256SUMS)

## 给编辑和作者的文件

附投稿信、五条 highlights、数据与代码声明、STRESS-DES 清单，以及待作者据实填写的署名、利益冲突和 CRediT 声明。参考文献采用 ESWA 作者—年份体例。50 篇登记文献全部在正文引用，另列 POMCP 首篇论文、两份事故报告、FEMA 技术资料和 STRESS 规范。

[投稿信](submission/cover-letter.docx) · [Highlights](submission/highlights.docx) · [STRESS 清单](submission/stress-checklist.docx) · [作者页](submission/title-page.docx) · [利益冲突](submission/competing-interests.docx) · [CRediT](submission/credit.docx) · [数据与代码](submission/data-and-code-availability.docx) · [AI 声明](submission/ai-declaration.docx) · [ESWA 的 CSL 样式登记](https://raw.githubusercontent.com/citation-style-language/styles/master/dependent/expert-systems-with-applications.csl)

## 作业账与核验边界 {span=2}

135652 和 135693 的分配行属于其他账号。原 63 个 T11-1 作业的计数和费用保持有效。本轮新增设施调用、Slurm 作业、科研分析、H2/H3 封存材料访问和投稿均为零。编辑使用了公开成绩，查账使用了 Slurm 会计记录。

[本轮账目](activity.json) · [回执和原始清单版本](https://github.com/DonsonHH/AegisDC/commit/10b3f7a08462623c22b87b3ae0dae7abe3c95378) · [复核命令与排版说明](HANDOFF.md)
