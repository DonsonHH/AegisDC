# 超算机房巡检与智能体流程改进

**研究问题：运行经验能否帮助智能体改进专业巡检流程，在满足资格、工时和持续重访要求的前提下，更早确认异常、减少无效检查？**

项目以指定巡检论文的部分观测、状态估计和多执行者学习思想为基础。当前保留供电—液冷—自控合成模型、专业任务、受保护巡回和有限流程修改；历史实验通过归档快照访问。

## 现在做到哪里

| 项目 | 当前状态 |
|---|---|
| 可维护的执行入口 | `status`、`demo`、`proposal`、`verify` 四个命令 |
| 默认巡检 | 名义状态估计＋固定巡回 Tour；可评价人工给定的受限局部规则 |
| 学习工具 | CVAE需要外部冻结权重；PPO源码保留，但不参与默认局部调度 |
| 已有科研证据 | 有真实仿真、模型修改和负结果；没有稳定任务增益或递归增益结论 |
| 下一研究问题 | 真实后果反馈是否帮助模型改进流程，见 [NEXT](docs/NEXT.md) |

## 从这里运行

需要 Python 3.11 或以上。以下命令从仓库根目录执行：

```bash
python -m pip install -e .
python -m patrol_rsi status
python -m patrol_rsi demo --output runs/demo
python -m patrol_rsi verify --output runs/verification
```

`demo`运行一次1800秒的合成巡检：128机柜、18名执行者，冷板故障在第335秒注入、持续180秒。`episode_horizon_s`是整次巡检时长，`fault_duration_s`是故障持续时间；两者不能混用。输出中的`timeline.csv`可查看谁在何时、何处完成了什么检查和测量。

`verify`分别报告工程检查、历史证据复算和科研执行状态。**测试通过不等于科研增益成立。** 每次使用新输出目录；重复运行可改为`runs/demo-2`、`runs/verification-2`等，已有结果不会覆盖。

查看一份人工候选如何经过同一修改接口：

```bash
python -m patrol_rsi proposal --candidate configs/candidate-example.json --output runs/proposal
```

这个候选是人工样例，不是大模型生成结果；运行记录会标注`provided_json_no_model_called`。以上命令不会下载或调用Qwen，不会重训科研模型，也不会自动启动下一轮研究。

未安装包时，Bash先运行 `export PYTHONPATH="$PWD/src"`；PowerShell先运行 `$env:PYTHONPATH="$PWD\src"`，然后使用相同的 `python -m patrol_rsi ...` 命令。

## 阅读顺序

1. [研究目标与边界](docs/RESEARCH.md)：为什么做、要证明什么。
2. [架构说明](docs/ARCHITECTURE.md)：输入怎样变成巡检动作和结果。
3. [当前证据](docs/EVIDENCE.md)：已经证明什么、没有证明什么。
4. [下一唯一任务](docs/NEXT.md)：继续开发时只推进这一项。

源码位于 `src/patrol_rsi/`，示例配置位于 `configs/`，保留证据的说明位于 [evidence/README.md](evidence/README.md)。运行产物放入 `runs/`，不混入源码或历史证据。

## 清理与恢复

完整历史保存在 [archive/pre-cleanup-20261102](https://github.com/DonsonHH/Zhinengti-RSI/tree/archive/pre-cleanup-20261102)，固定源提交为 `f2c20b3a642ff1df9426e523614d3da9a5cf1129`。清理范围见 [cleanup.json](cleanup.json)，保留材料的来源见 [evidence/provenance.json](evidence/provenance.json)。重要负结果仍保留在证据说明中。

当前系统使用合成参数，未完成现场部署或校准；声明条件内的重访保障不等于现场安全认证。
