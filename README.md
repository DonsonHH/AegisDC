# 超算机房巡检与智能体流程改进

**研究问题：运行经验能否帮助智能体改进专业巡检流程，在满足资格、工时和持续重访要求的前提下，更早确认异常、减少无效检查？**

项目以指定巡检论文的部分观测、状态估计和多执行者学习思想为基础。当前保留供电—液冷—自控合成模型、专业任务、受保护巡回和有限流程修改；历史实验通过归档快照访问。

历史论文材料保留为[机制稿导师讨论版](paper/README.md)：[一页讨论摘要](paper/supervisor-brief.md)、[贡献表](paper/research-map.md)、[正文](paper/manuscript_zh.md)及[公式图表预览](paper/manuscript_zh.html)。该稿以RQ1—RQ2及同权限搜索负结果为中心；反馈设计见[独立备忘](paper/feedback-design.md)。

当前给导师的入口是[自阅研究进展报告](paper/supervisor-briefing.html)。本次按新授权补充真实模型训练、四专业数据与独立留出比较：3个温度残差CVAE-U-Net、6个共享PPO，1080个留出测试回合、12个独立种子块，以及18次128／512／1024柜纯物理规模运行。报告包含模型架构、训练曲线、同观测流误差、专业确认、年龄和资源代价，图像、公式和表格内嵌，可单文件离线阅读。

文本工具审阅可使用[已展开的完整正文](paper/supervisor-report-text.md)或[8节正文审阅包](paper/generated/supervisor-text-review.zip)：不内嵌Base64或SVG代码，正文、公式及数值表与HTML同源，图版改为链接。

新结果和原件身份见[独立补充基准](evidence/supplement-study/README.md)、[完整方法](paper/supplement-study-methods.md)及[NEXT](docs/NEXT.md)。旧[响应／暂缓开发搜索](evidence/response-defer/README.md)的9条规则、108次开发评价与“均未超过FIFO”的负结果完整保留；本次模型训练和数据不并入旧协议预算。

## 现在做到哪里

| 项目 | 当前状态 |
|---|---|
| 可维护的执行入口 | `status`、`demo`、`explain`、`proposal`、`verify`；`study`显式启动冻结研究 |
| 默认巡检 | 名义状态估计＋固定巡回 Tour；可评价人工给定的受限局部规则 |
| 学习基准 | 3个295,777参数的残差CVAE-U-Net及6个共享PPO已真实训练；九个checkpoint与训练历史归档，默认CLI仍保留原机制流程 |
| 已有科研证据 | 新留出基准中名义FIFO确认155/210、Tour94/210；CVAE改善温度误差，学习调度的确认量未超过名义FIFO；模型后果反馈与递归增益仍待独立验证 |
| 历史机制研究 | 108次成功＋1次保留失败；原主过程Tour/FIFO/置乱确认28/70/25段（共89段）。见[原完整结果](evidence/event-validation/final/README.md) |
| 本轮独立补充 | 2204次环境尝试、3次估计器训练和18次纯物理运行完成，零失败；主推断采用12个种子块、48个故障条件，健康／虚假提示另列 |

## 从这里运行

需要 Python 3.11 或以上。以下命令从仓库根目录执行：

```bash
python -m pip install -e .
python -m patrol_rsi status
python -m patrol_rsi demo --output runs/demo
python -m patrol_rsi verify --output runs/verification
```

`demo`运行一次1800秒的合成巡检：128机柜、18名执行者，冷板故障在第335秒注入、持续180秒。`episode_horizon_s`是整次巡检时长，`fault_duration_s`是故障持续时间；两者不能混用。输出中的`timeline.csv`可查看谁在何时、何处完成了什么检查和测量。

首次理解项目，先运行一个供电—液冷耦合案例：

```bash
python -m patrol_rsi explain --output runs/coupled-case
```

打开 `runs/coupled-case/index.html`，可以拖动时间查看公开风险图、事后实际温度、各专业检查和一次真实排序决定，再对比固定路线与人工风险规则的整回合结果。页面独立运行，不依赖网络。原始数据保存在同目录 `case.json` 和两个方案的 `timeline.csv` 中。

这个案例固定为辅助馈线异常，不会调用VAE、PPO或大模型。遥测报警与专业人员现场确认分别呈现；更短路程、更早确认和更多完成量可能互有取舍，页面不会把换了顺序直接称为AI或RSI成功。

`verify`分别报告工程检查、历史证据复算和科研执行状态。**测试通过不等于科研增益成立。** 每次使用新输出目录；重复运行可改为`runs/demo-2`、`runs/verification-2`等，已有结果不会覆盖。

查看一份人工候选如何经过同一修改接口：

```bash
python -m patrol_rsi proposal --candidate configs/candidate-example.json --output runs/proposal
```

这个候选是人工样例，不是大模型生成结果；运行记录会标注`provided_json_no_model_called`。以上命令不会下载或调用Qwen，不会重训科研模型，也不会自动启动下一轮研究。

正式反馈研究使用单独的 `study` 命令，方案与预算固定在 [configs/feedback-study.json](configs/feedback-study.json)。它需要一个已准备、通过权重校验的离线Slurm推理任务；`--ssh-host`使用本机已解锁的SSH认证，密钥不进入仓库。运行步骤、完整结果与原件索引统一放在 [反馈研究交付](evidence/feedback-study/README.md)。

未安装包时，Bash先运行 `export PYTHONPATH="$PWD/src"`；PowerShell先运行 `$env:PYTHONPATH="$PWD\src"`，然后使用相同的 `python -m patrol_rsi ...` 命令。

补充研究使用独立入口`python scripts/run_supplement_study.py status`，由`configs/supplement-benchmark-20261103.json`登记。`all`显式执行该研究，需要Torch运行环境及原兼容记录；重建报告使用`python scripts/build_supervisor_report.py`，读取仓库内保存的图表输入，不启动训练或新仿真。完整逐帧原件保留在本地`runs/supplement-benchmark-20261103`，仓库包含评价明细、真实权重、执行源码快照与SHA索引。

## 阅读顺序

新风险确认机制已启动：`python -m patrol_rsi respond --output runs/risk-response`。参见[首轮机制试验](evidence/risk-response/README.md)：新增确认与退化案例一并报告，默认Tour不因此自动替换。

事件优先级对照：`python -m patrol_rsi prioritize --output runs/event-priority`。见[完整结果](evidence/event-priority/README.md)：新条件中事件响应改善了确认，但新排序与FIFO动作相同，尚无额外收益。

1. [研究目标与边界](docs/RESEARCH.md)：为什么做、要证明什么。
2. [架构说明](docs/ARCHITECTURE.md)：输入怎样变成巡检动作和结果。
3. [当前证据](docs/EVIDENCE.md)：已经证明什么、没有证明什么。
4. [下一唯一任务](docs/NEXT.md)：继续开发时只推进这一项。

源码位于 `src/patrol_rsi/`，示例配置位于 `configs/`，保留证据的说明位于 [evidence/README.md](evidence/README.md)。运行产物放入 `runs/`，不混入源码或历史证据。

## 清理与恢复

完整历史保存在 [archive/pre-cleanup-20261102](https://github.com/DonsonHH/Zhinengti-RSI/tree/archive/pre-cleanup-20261102)，固定源提交为 `f2c20b3a642ff1df9426e523614d3da9a5cf1129`。清理范围见 [cleanup.json](cleanup.json)，保留材料的来源见 [evidence/provenance.json](evidence/provenance.json)。重要负结果仍保留在证据说明中。

当前系统使用合成参数，未完成现场部署或校准；声明条件内的重访保障不等于现场安全认证。
