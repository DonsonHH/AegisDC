# Stage 3：精确算术检验包

[定理与判决表](../../../../docs/mainline/39r-ups-a1-stage3-theorem.md) · [可执行脚本](../../../../scripts/verify_theorem.py) · [逐行结果](result.json)

## 复现整包

在仓库根目录运行，使用 Python 3.11 或更新版本，无需安装依赖：

```sh
python -B scripts/verify_theorem.py verify-v1 --check evidence/mainline/engineering/39r-ups-a1-stage3-verification-v1/result.json
```

脚本先核对 v1 规范与结果的 SHA-256。用精确分数重算原 83 组，每组核对 101 个先验点，并检查存档区间的端点、解析根和相邻分界间的代表点。逐分支期望损失独立于端点求区间的实现；逐行比较暂缓、升级、直接恢复及最佳合法参照的原区间和网格计数。不可比较的行单列。三个额外例子分别覆盖逆序且无代价、逆序但端点平手、直接恢复中段不可行。

`--check` 的逐字节相等是与存档记录的一致性检查。分支求和用于核对算术实现，定理的正确性来自正文的端点解析证明。`--write <新路径>` 可生成另一份记录，已有文件不会被覆盖。用户另报的100组验证、本轮4,000组随机参数检查和3,000组误报扰动检查没有随包冻结，均不计入本包机器覆盖，也不构成现场交叉验证。

当前入口分派旧命令给[逐字节保留的 v1 脚本](../../../../scripts/verify_theorem_v1.py)。旧 `result.json` 的脚本路径和哈希对应记录当时的 `verify_theorem.py`；现在应以该归档文件核对旧脚本字节，旧结果没有重写。

## 代入一组参数

```sh
python -B scripts/verify_theorem.py pair --s 9/10 --t 9/10 --u0 1/10 --u1 1/10 --q-i 3/4 --q-r 3/4 --d-r 1/10 --d-fp 1/10 --k 1/50
```

得到 `alpha=71/1000`、`beta=-13/80`、斜率 `-467/2000`、严格胜区 `[0,142/467)`。`{142/467}` 是平手；`beta` 已扣除代价。概率参数须在 `[0,1]`，扰动和代价是同一负载叶子差的非负比例。

单组命令假定用户已核对两项策略的授权、截止和资源可行性。`--direct-ineligible` 或 `--inspection-ineligible` 返回 `NOT_COMPARABLE`。`--g 0` 只关闭查后处置分支；检查策略是否仍可行由调用者单独判断。这个接口使用 v1 的二值门；若现场记录显示许可概率依状态或先验而变，先按[判决表](../../../../docs/mainline/39r-ups-a1-stage3-theorem.md#现场证据清单)限定适用区段或重估条件损失。

另见[字段填写与条件比较](../../../../docs/mainline/39r-ups-field-tool.md)及[独立 CLI 核验](../39r-ups-field-cli-v1/result.json)。本包未产生现场概率、物理运行、策略调用、模型调用或新注册实验。
