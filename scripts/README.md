# 工具导航

这里保留工具的原路径。脚本名带版本或日期，经常是已执行协议的一部分；它们不自动构成可删的旧副本。日常入口优先用 `python -m aegis_dc`（安装后为 `aegis-dc`），旧基线为 `python -m patrol_rsi`。所有安装、计算及测试遵循[远端规则](../docs/agents/compute-storage.md)。

| 类别 | 代表工具 | 使用边界 |
|---|---|---|
| 常规工程／证据检查 | `acceptance.py`、`verify_evidence.py`、`verify_facility_cases.py` | `patrol_rsi verify` 会运行工程测试及既有证据检查；默认允许两项既有可选 Torch 跳过，不等于 39c 零跳过根验收。 |
| 有限工程切片 | `run_engineering_slice.py`、`capture_*`、`*_engineering_checks.py` | 按具体切片的已授权输入和预算使用。不要将任意新源码代入旧冻结协议。 |
| 特定历史根验收 | `run_remote_root_acceptance.py`、`verify_*_delivery.py`、`*_delivery.py` | 有固定分支、解释器、路径、清单或提交要求，先读对应回执。不是通用运行器。 |
| 数值与参数资格 | `verify_mainline_numerics.py`、`verify_numerical_*`、`run_parameter_domain_witnesses.py` | 只支持原声明的模型和有效域；新研究范围需要新授权／协议。 |
| 注册研究 | `registered_comparison.py`、`registered_development.py`、`registered_confirmation.py`、`registered_ablation.py`、`registered_robustness.py` | 原 180 次研究的执行工具，不因维护而重跑或改写。 |
| 研究输入与锁定 | `prepare_negative_control_inputs*.py`、`negative_control_public_preflight*.py`、`full_loop_development*.py`、`comparison_release.py`、`robustness_release.py` | 版本化路径由执行锁绑定；同名 v2–v6 仍是复现输入。 |
| 已存结果分析／图文 | `analyze_*`、`plot_*`、`build_*`、`render_*` | 先查输入原件及结果目录；输出到新目录，保留旧图与失败。 |
| 环境与基础设施 | `prepare_gpu4090_runtime_02.py` 等 | 读取环境计划和原终态；安装在专用远端，不自动重新配置共享环境。 |

精确绑定入口：[确认执行锁](../docs/mainline/evidence/30-confirmation-execution-lock.json)、[消融执行锁](../docs/mainline/evidence/30-ablation-execution-lock.json)、[稳健性执行锁](../docs/mainline/evidence/30-robustness-execution-lock.json)。

增加新工具前先确认这里是否已有相同职责。一次性验证器和完整运行日志优先留在私有远端，仓库只保存轻量结果和工具身份；需要长期复用的工具才成为新的维护入口。
