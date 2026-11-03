# 独立补充基准：机房状态估计与四专业巡检

本包来自2026-11-03新授权的数据与模型补充。原事件验证包、九规则搜索和原失败记录保持原件身份。

实际环境尝试2204次，另有18次纯物理规模运行；新包失败尝试0次。

最终测试包含12个独立物理种子块、72个条件、60条唯一物理轨迹、1080个闭环回合；主要分析为四故障族共48条件。
三个CVAE-U-Net各训练30轮，六个PPO各训练120回合。条件内先平均三个模型种子，四故障族等权，再对12个物理种子块计算区间。

|方法|平均模型确认总数／唯一异常段|每主要条件确认|闭环加权RMSE / °C|加权归一年龄|
|---|---:|---:|---:|---:|
|nominal_tour|94.00/210|1.958|0.535|0.310122|
|nominal_fifo|155.00/210|3.229|0.535|0.311298|
|nominal_greedy|154.00/210|3.208|0.537|0.311270|
|nominal_ppo|129.33/210|2.694|0.537|0.310877|
|cvae_fifo|153.00/210|3.188|0.327|0.311256|
|cvae_greedy|152.00/210|3.167|0.327|0.311217|
|cvae_ppo|153.67/210|3.201|0.327|0.311266|

确认总数的小数表示训练种子平均，不增加独立样本。误差在本合成物理基准内解释；共同Tour观测流的主要估计对照、配对区间、四专业结果与成本见完整报告。

## 检查与原件

分析器独立重建1080个回合的专业异常与确认、等待和实际成本，核对1,538,717条完成记录；216个共同观测流误差重新计算，九个模型SHA及训练身份核对通过。

- `protocol.json`、`seal.json`、`amendments.json`和`attempts.jsonl`：原登记、源身份与追加式执行记录。
- `test-rows.json`：1080条测试评价明细及原始文件SHA；训练曲线在`training/`，实际九个checkpoint在`checkpoints.zip`。
- `source-executed.zip`及同名JSON：本轮实际执行的34个源文件和逐文件SHA，保留执行版本与随后工程维护的区别。
- `local-artifacts.json`：本地完整逐帧数组、执行日志与物理记录索引，根目录`runs/supplement-benchmark-20261103`。这些大体积原件留在共享本地工作区。
- `paper/source-data/supplement-study.json`与`supplement-example.json`：仓库内可检查的图表输入和编号示例，HTML重建无需训练或新环境执行。

## 阅读与复算

先打开`paper/supervisor-briefing.html`离线阅读；完整方法为`paper/supplement-study-methods.md`。
在已有写作依赖环境运行`python scripts/build_supervisor_report.py`可由保存输入重建报告。
完整原件复算需保留本地`runs/`原件及隔离的Torch环境：`python scripts/analyze_supplement_study.py`；静态来源核对使用`python scripts/verify_report_sources.py`。
执行器为`python scripts/run_supplement_study.py status`；`all`显式运行登记研究，不属于报告重建。研究环境为Python3.12.14、NumPy2.3.5、Torch2.6.0+cu124和RTX4060 Laptop GPU，环境身份见seal。
