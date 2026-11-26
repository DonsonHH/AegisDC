# T8 阶段 1b 交接

本次 FIT 在第 4 轮锁定两臂。O 和 R 都选中第 3 槽，把 `ORDER_FAR` 从 0 调到 3。每臂独立支付 16 个候选的 48 行评价。前三轮均无候选严格降低缺额，R 的改写条件一直未触发。两臂取得同一份策略描述符和相同的 FIT 均值。均值、候选分母和逐轮程序哈希见[逐轮报告](report.md)。

## 查重、回执与评分边界

冻结的 48 条输入只发送了一次正式查重请求。九字段回执记录 `PASS`，聚合覆盖率 100%，必需测试全部完成。保管标识为 `pi-custodian`，审计标识为 `pi-auditor`。Ed25519 公钥指纹为 `ae9b3a9714961a0f6f7e85288c414107c34df15934d382e97d9e11a947f74cb8`。执行方按 PI 的具名委托，对已发布的 402 字节回执代签。同一 Windows 账号承担保管和执行，登记口径为程序性查重。[权威登记](../../custody/authority.json) · [原请求](../fit-overlap/request.json) · [原回执](../fit-overlap/receipt.json) · [代签与验签记录](../fit-overlap/signature-provenance.json)

提案方只获得共享父或本臂已付候选的签名聚合分。接收代码逐包核对字段、签名、策略与槽位。逐条件分数和设施轨迹保存在私服。角色运行在不同的用户、挂载、PID 和网络命名空间，映射到同一宿主账号。服务方只读核对了 1,584 份完整位置记录、3,168 份角色访问审计、89 条签名事件及 8 个轮账。运行时评价器与复制后的执行代理各核一次原始轨迹哈希。终态读回重核了评分、入口与访问记录的字节，并核对轨迹摘要和文件大小。[公共聚合证据](public-proof.json) · [提案端接收规则](../scoring/public_roles.py) · [私服只读核对程序](../read_native_fit.py)

## 恢复与实际费用

共享父的首个分配 `135577` 使用了重复拼接的启动路径，Python 评分入口与全部 48 个位置都尚未启动。它占用一个作业，预留 8,640 CPU 秒，实际消耗 0.106 CPU 秒。恢复版从 Slurm 的实际工作目录解析发布路径，并在计算节点核实角色隔离。获准的唯一一次恢复 `135578` 对同批 48 个位置完成评分。登录节点和计算节点的 UID 映射配置不同，环境核对应采用实际分配节点。[首个作业终态](../scoring/parent-a1/terminal.json) · [恢复版启动脚本](../scoring/study.sbatch)

Slurm 的 10 个作业共实耗 133,217.287 CPU 秒，本地查重另耗 2.500 CPU 秒。试点的 384 个位置实耗 32,675 CPU 秒。余下 1,152 个位置的两倍外推额为 196,050 CPU 秒，实际预留 190,080。所有作业累计预留 276,720 CPU 秒，上限 285,900。[逐作业原账](sacct.psv) · [批量预留决定](../batch-budget.json)

O 和 R 签名轮账内的进程计时分别为 303.406027 和 303.230245 CPU 秒。两数与 Slurm 作业实耗的差额尚无法逐位置分摊。总成本采用 Slurm 作业行，配套的 `.batch` 行只作复核。即便把全部 133,219.787 CPU 秒计给单一臂，仍低于每臂 138,480 CPU 秒上限。[轮账聚合原件](results.json) · [Slurm 原账](sacct.psv)

每个位置和其子进程共用一个 CPU 核。额外的只读核对按核重建了占用窗口。执行代理收回前一位置后才能再次使用该核，同槽最后一个位置由签名的整槽历时封顶。逐一核对终态文件时间，并加回已计给各位置的监督进程 CPU 份额。得到的单位置 CPU 上界最大值分别为共享父 104.405628 秒、O 104.917396 秒、R 103.746435 秒（均向上取至微秒）。三者均低于 180 CPU 秒。[时间上界原件](cpu-scope.json) · [只读核对程序](../read_cpu_scope.py)

## 交审与复核

实际执行源码为 `75203c1f`，执行镜像与签名身份在 `26bc40f9` 发布。FIT 已锁定，留待 PI 审阅。DEV 评分、H2 访问、H3 原件访问均为 0。查重使用既有封存输入承诺索引。全部研究轨迹和失败现场继续保存在原私服根。[版本与文件清单](delivery.json) · [一页摘要](review.html)

新检出中可从仓库根运行以下只读命令。第一条验证研究交付和版本字节，第二条验证已消费的正式回执。

```powershell
$t8 = 'docs/mainline/t8-rsi-wait-repair'
python -B "$t8/stage1b/check_native_delivery.py" --check --checkout-bytes
python -B "$t8/custody/verify_receipt.py" --request "$t8/stage1b/fit-overlap/request.json" --receipt "$t8/stage1b/fit-overlap/receipt.json" --signature "$t8/stage1b/fit-overlap/receipt.sig"
```
