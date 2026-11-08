# 39b：异步回执原失败与保存数据修正

原单次资格Slurm133138，源b028121e7cf737e31bbef8b08447d88e64be441c，**FAILED1:0**。原输入、源码、完整7秒运行和失败均保留，不把它改写成绿片，也不自动重复设施调用。

实际6次返回选择已通过前半段断言：初查0、1.75暂缓、2处置、3.75等待工作ACK、4复查、7不再派。失败在测试把既有证据状态写成`stale`，实际公共枚举为`expired`，并非执行器把过期测量当成当前信息。

显式08v2只修正该断言名称，Slurm133139已用同一保存摘要核对全部原行为预期，COMPLETED0:0，[回执](saved-correction-01/verification.json)为SAVED_ASSERTIONS_VERIFIED_NOT_NATIVE_RERUN，零设施/公开选单/模型调用。原资格预算已消耗；保存核对不是物理重试，原终态保持FAILED。

保存核对通过的独立预期：行动3.25生效、3.75回执先到，人员完成ACK4秒到达后才派复查，5.25采样、5.75到达。7秒时初查测量已过期，历史准入包络仍24.5人/工具秒、费用3；交付3.625、缺额3.375，实际工作3和门禁0.75人秒。详细轨迹留在`/share/home/renly/renly-patrol-rsi/mainline/39b-development/14-late-ack-qualification/results/actual-run`。
