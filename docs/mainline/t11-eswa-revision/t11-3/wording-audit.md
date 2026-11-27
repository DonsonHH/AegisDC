# 五条审核意见与正文位置

审查依据为 [T11-1 交付 93748f27](https://github.com/DonsonHH/AegisDC/tree/93748f272939166b81ae4188299f096b0fa23fe2/docs/mainline/t11-eswa-revision/t11-1) 和 [先于执行发布的解读表 c41ab910](https://github.com/DonsonHH/AegisDC/blob/c41ab91096c25399b24193f652dbb8b0b9d39ebd/docs/mainline/t11-eswa-revision/t11-1/interpretation-before-run.md)。本表核对当前英文稿；原英文面板保留作当时的记录。

| PI 意见 | 英文稿和补件采用的表述 | 已核对的记录 |
|---|---|---|
| 短视 VoI | §6、表 D 和补充 B 明写全部 72 项实际服务缺额逐行相同。3 行的派工次序、人时、工具和费用有差异。表 D 保留退化区间 [0.00, 0.00]。 | [原配对和逐行比较说明，行 9–16](https://github.com/DonsonHH/AegisDC/blob/93748f272939166b81ae4188299f096b0fa23fe2/docs/mainline/t11-eswa-revision/t11-1/results/analysis/panel.md#L9-L16) |
| POMCP | §6 表 D 采用中心减对照。服务差 −57.50 [−118.06, +9.36] 秒，方向未定。人员差 −72.78 [−93.96, −52.71] 人秒，费用差 −1.35 [−1.69, −1.00]。在同样 207 张具名工单中，窗末有效 PV 为中心 36、POMCP 52。4,392 次返回含 903 次 VALUE 和 3,156 次 NO_COMPLETE_ADMITTED_BRANCH。解释限于每个可选根 128 次模拟、深度 4。 | [主比较](https://github.com/DonsonHH/AegisDC/blob/93748f272939166b81ae4188299f096b0fa23fe2/docs/mainline/t11-eswa-revision/t11-1/results/analysis/panel.md#L9-L18) · [关闭](https://github.com/DonsonHH/AegisDC/blob/93748f272939166b81ae4188299f096b0fa23fe2/docs/mainline/t11-eswa-revision/t11-1/results/analysis/panel.md#L43-L47) · [路径分母](https://github.com/DonsonHH/AegisDC/blob/93748f272939166b81ae4188299f096b0fa23fe2/docs/mainline/t11-eswa-revision/t11-1/results/analysis/panel.md#L144-L151) |
| 描述性分层 | §4 表 B 是原确认面板上的禁购对照分层。§6 和补充 B 单列开发面板上中心减 POMCP 的子集，1,200 秒档 −200.96 [−296.92, −103.75]，备用切换族 −150.00 [−282.50, −32.50]。摘要和结论均未使用这两个数或提出按该分层选策略。 | [开发分层原表](https://github.com/DonsonHH/AegisDC/blob/93748f272939166b81ae4188299f096b0fa23fe2/docs/mainline/t11-eswa-revision/t11-1/results/analysis/panel.md#L76-L88) |
| λ = 2 | §6 切换到“变体减中心”方向。八个变体中只有该服务差区间排除零。缺额 +58.81 [+6.67, +124.69] 秒，人员 −42.22 [−57.85, −27.78] 人秒。仅解释人员价格提高后的工程取舍。 | [OAT 原表](https://github.com/DonsonHH/AegisDC/blob/93748f272939166b81ae4188299f096b0fa23fe2/docs/mainline/t11-eswa-revision/t11-1/results/analysis/panel.md#L62-L72) |
| 计时和资格 | §6 表 E 和图 A 图注均标作业 135631、隔离重放、外层 IPC 墙时及原工人内部 CPU 时钟未建立。表 E 给中心 1.292 / 4.200 / 17.065 ms。补充 B 保留 55d37ee8 的 9/10、JSON 2.0 与 2 的类型差、3a096231 的 worker.py 单行修复及 10/10 结果。ZIP 内保留两次具名回执及失败见证。 | [原资格与计时来源](https://github.com/DonsonHH/AegisDC/blob/93748f272939166b81ae4188299f096b0fa23fe2/docs/mainline/t11-eswa-revision/t11-1/stage0-receipt.md#L7-L20) · [工人修订](https://github.com/DonsonHH/AegisDC/commit/3a096231d6b7dd35c8661e4c29444fe7d78520f7) |

## 主张及版面

C1、C2 保留部分支持。C3 登记的迁移优势未获支持。C4 的独立改写增量未建立。判定、原数及反例与主张 v2 逐行对应。v3 唯一增加的研究措辞在 C1 格内。正文 §8 合并 C3、C4，在 PDF 第 9 页从该节标题顶部到下一标题基线的保守距离为 184.10 pt，整页高 841.92 pt，占 0.219 页。保管问题只在正文出现一句，争议和核验限度详见补充 C。

正式比较均引用既有公开成绩。这次核过提交、文件、表格单元、文献元数据、可编辑文件、实印页面以及图上各标记的位置。查账直接读取 Slurm 会计记录。私有逐步输出和封存 H2/H3 资料不在本次核验材料中。
