# AegisDC

AegisDC 研究完整算力设施在多系统耦合、多源稀疏证据下，如何形成风险问题，按需核查并受约束地处置和复核，以及固定策略、普通自改进与 RSI 各能贡献什么。原生研究对象是郑州工程参照启发的八域合成设施。Google 事故承担方法论文的有限有效性验证。

**研究入口**　[六阶段总路线](docs/mainline/master-roadmap.md) · [当前主线](docs/MAINLINE.md) · [进度账](docs/mainline/progress.json) · [工作区地图](docs/WORKSPACE.md)

## 当前状态

第一阶段的 17 个条件和 85 个处理已完成有限验收。V 与 D 在 17 行的实际服务均持平，三项省工均伴随关闭损失。第二阶段已有[部分验收](docs/mainline/v6-joint-engineering-v1/acceptance-20261121.json)。[终态接口有限验收](docs/mainline/v6-joint-terminal-v1/acceptance-20261121.json)已登记。第三阶段[冷态工程有限验收](docs/mainline/v6-stage-three-cold-v2/acceptance-20261121.json)已登记。[冷态启动有限验收](docs/mainline/v6-stage-three-cold-launch-full-walk-v1/acceptance-20261121.json)已登记。[第三阶段冷态正式结果](docs/mainline/v6-stage-three-cold-study-v2/README.md)已按[原有限范围验收](docs/mainline/v6-stage-three-cold-study-v2/acceptance-20261121.json)。[第四阶段普通改进协议 v1](docs/mainline/v6-stage-four-ordinary-improvement-v1/README.md)保留为未冻结、零执行原稿。[T1 研究余量诊断](docs/mainline/t1-research-margin-v1/README.md)已有限接受。[T2 基线面板](docs/mainline/t2-minute-facility-v1/acceptance-20261121.json)已在有限范围内接受。[T3 事前信息、关闭端点及两类事故开发面板](docs/mainline/t3-prior-information-v2/README.md)已交审。六族 72 条、288 个位置全部归档，正式 T4 目标 3 条。24 个 J–B 配对中 J 有 1 行改善、22 行持平、1 行较差；66 个正式位置均有返回。原 V1 前检失败按原件保留。原 S09 与两组半秒热工同轨失败继续保留。伦敦 PRE 的 R6 v1.3 继续作为有限事故验证章节。[本批结果](docs/mainline/v6-native-method-study-v1/README.md) · [原生方法说明](docs/mainline/full-facility-method-handoff.md) · [伦敦章节有限验收](docs/mainline/review-gated/R6/london-pre-manuscript-v1.3/acceptance-20261119.md)

维护 [PR #3](https://github.com/DonsonHH/AegisDC/pull/3) 经重新审查后已合入 `donson/mainline-39c-endpoints`，合并提交 `4a9dfdbe`。这不接受旧 39c 整票，也未合入 `main`。维护验证见[回执](docs/maintenance/20261112-workspace/result.json)。

以下为保留的历史研究状态，不能用其通过数量推算新主线进度：

- **39c 整票未验收。** [独立复核](docs/mainline/audits/20261112-39c-whole-ticket/README.md)保留五项开放问题。[57-R1 精确重放](evidence/mainline/engineering/39c-development/slice-57/result.json)及[58 零设施负向资格](evidence/mainline/engineering/39c-development/slice-58/result.json)的有限通过保持；完整根回归和 fresh 门槛仍开放。
- **原 180 次注册比较保持负结果。** 主平均改善 0.03515625 秒，低于 0.25 秒实际收益门槛。解释始终带上：**验证关闭未入环、仅 2 个预设实例、无现场标定**。[更正版报告](paper/preset-dispatch-scope-review-20261110/report.html)与[固定范围](docs/mainline/preset-study-scope.json)说明它能回答的问题。
- **旧队列冻结。** 39d、39t 数字资格、40–42、AI／RSI 未自动恢复；具体复用内容由新主线逐项决定。[重整前原始状态](docs/mainline/history/20261112-before-reset/README.md)保留旧接受范围和缺口。

以往研究材料：[历史论文结构稿](paper/conditional-inspection-value-structure-20261111.md) · [两域联合可行性与作业时长边界](docs/research/20261112-joint-cooling-access-feasibility/README.md) · [Frontier 实测与缺测](docs/research/20261111-frontier-field-pilot/README.md) · [V6 量级及全年参照](docs/research/20261112-frontier-v6-scale-reference/README.md) · [八域覆盖三档](docs/mainline/39r-coverage-criteria.md)。这些材料分别说明有限工程、外部参照与尚缺证据，不合并为现场收益结论。

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
