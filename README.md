# AegisDC

现有实现是一套郑州工程参照启发的**八域合成算力设施**。新研究拟以真实事故机制为依据，验证专业核查、受约束处置及自改进的效果；旧设施作为待按新问题核验的复用资产。设施真实状态留在私有评估器，决策者只使用当时可用的记录。项目不控制真实设备。

**从这里开始：** [新研究主线](docs/MAINLINE.md) · [R0–R6 提案](docs/mainline/review-gated/plan.md) · [11.12 meeting](docs/meetings/2026-11-12-research-mainline-reset.md) · [当前进度](docs/mainline/progress.json) · [工作区地图](docs/WORKSPACE.md) · [脚本导航](scripts/README.md)

## 当前状态

**修正后的 [R1 资料基线](docs/mainline/review-gated/R1/README.md)已接受；狭义 R2 契约已接受，[关系表与取值域](docs/mainline/review-gated/R2/relations-v1.md)、[独立预期与覆盖矩阵](docs/mainline/review-gated/R2/coverage-v1.md) v1 等待 review。实现、实验及荷兰／事中响应扩展均未授权。** 本轮仅固定书面关系、取值域与预期，突出 Q04 成功／失败配对和 Q08 到达前后发布要求。没有执行资格检查。[来源台账](docs/mainline/review-gated/R1/sources.md)记录官方版本与证据限度；没有运行事故仿真或模型实验。旧票进度不再自动驱动工作。

维护 [PR #3](https://github.com/DonsonHH/AegisDC/pull/3) 经重新审查后已合入 `donson/mainline-39c-endpoints`，合并提交 `4a9dfdbe`。这不接受旧 39c 整票，也未合入 `main`。维护验证见[回执](docs/maintenance/20261112-workspace/result.json)。

以下为保留的历史研究状态，不能用其通过数量推算新主线进度：

- **39c 整票未验收。** [独立复核](docs/mainline/audits/20261112-39c-whole-ticket/README.md)保留五项开放问题。[57-R1 精确重放](evidence/mainline/engineering/39c-development/slice-57/result.json)及[58 零设施负向资格](evidence/mainline/engineering/39c-development/slice-58/result.json)的有限通过保持；完整根回归和 fresh 门槛仍开放。
- **原 180 次注册比较保持负结果。** 主平均改善 0.03515625 秒，低于 0.25 秒实际收益门槛。解释始终带上：**验证关闭未入环、仅 2 个预设实例、无现场标定**。[更正版报告](paper/preset-dispatch-scope-review-20261110/report.html)与[固定范围](docs/mainline/preset-study-scope.json)说明它能回答的问题。
- **旧队列冻结。** 39d、39t 数字资格、40–42、AI／RSI 未自动恢复；具体复用内容由新主线逐项决定。[重整前原始状态](docs/mainline/history/20261112-before-reset/README.md)保留旧接受范围和缺口。

最新研究材料：[论文结构稿](paper/conditional-inspection-value-structure-20261111.md) · [两域联合可行性与作业时长边界](docs/research/20261112-joint-cooling-access-feasibility/README.md) · [Frontier 实测与缺测](docs/research/20261111-frontier-field-pilot/README.md) · [V6 量级及全年参照](docs/research/20261112-frontier-v6-scale-reference/README.md) · [八域覆盖三档](docs/mainline/39r-coverage-criteria.md)。这些材料分别说明有限工程、外部参照与尚缺证据，不合并为现场收益结论。

## 代码与记录

| 目录 | 用途 |
|---|---|
| `src/aegis_dc/` | 当前设施、证据、调度、专业作业、私有评价与版本化重放 |
| `src/patrol_rsi/` | 会前研究基线、兼容 CLI，以及当前仍使用的 JSON 契约 |
| `tests/`、`configs/` | 公共接口测试、冻结 fixture 和版本化场景 |
| `scripts/` | 按[索引](scripts/README.md)使用的工程、分析、报告和历史复现工具 |
| `evidence/`、`docs/mainline/`、`paper/` | 原件、失败、协议、状态、图和报告；保留既有路径和身份 |
| `.scratch/` | 有依赖关系的主线票，以及独立维护票 |

[ADR-0001](docs/adr/0001-preserve-premeeting-and-reset-research.md)保留会前实现与证据；[完整设施 ADR](docs/adr/0003-complete-facility-mainline.md)固定八域研究对象。历史脚本和版本 fixture 并非看到旧编号就可删除。`.work/`、`runs/`、`outputs/` 也可能含唯一私有材料。

## 入口与执行位置

依赖安装、测试、仿真、训练及推理都在已有远端资源执行，桌面用于编辑、SSH、完整性核对与查看结果。mu01 的计算须进入 Slurm 分配；[计算与存储规则](docs/agents/compute-storage.md)说明预检、留存和失败处理。

在远端准备环境后：

```bash
python -m pip install -e .
aegis-dc status
python -m aegis_dc scenario
python -m aegis_dc --help
```

`status` 读取当前研究状态，不加载私有设施执行器。`scenario` 检查场景契约；`simulate`、`record`、`replay` 和风险算例涉及计算，按相应授权及协议运行。新源码改变执行身份，旧精确重放需要原 revision 和解释器。

旧入口继续可用：`python -m patrol_rsi status` 读取会前状态，`python -m patrol_rsi verify --output runs/verification-new` 执行工程／证据校验；当前常规检查允许两项既有可选 Torch 跳过，不替代 39c 的零跳过验收。历史用法见[会前 README](https://github.com/DonsonHH/AegisDC/blob/pre-meeting-20261103/README.md)。

[1–38 跨阶段复核](docs/mainline/audits/20261109-integrated/review-report.md) · [逐项证据](docs/mainline/audits/20261109-integrated/coverage-01-38.md) · [方向纠正包](docs/reviews/20261110-direction-correction/README.md) · [术语](GLOSSARY.md)
