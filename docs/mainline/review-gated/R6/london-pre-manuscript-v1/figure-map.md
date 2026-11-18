# 图表来源、图注与重绘

本包的四幅图是既有保存记录的出版视图，不构成新的设施运行、重新评分、工程资格或研究样本。图中所有时间与能量均属于合成模型。两个面板分别呈现；不得把图 1 的条件计数解释为总体发生概率或独立事故样本量。

## 1. 来源身份

读取基线为 `cf666ec5c3f390ecb3b07818365cf4be2c475cde`。下列三个来源在本轮通过 GitHub 读取，传至临时编制目录后，用 SHA-256 和 Git blob 身份同时核对。没有在本轮重新登录私有服务器核对逐臂原始日志。

| 来源别名 | 原件 | SHA-256 |
|---|---|---|
| dev19 | [公开开发终态记录](https://github.com/DonsonHH/AegisDC/blob/cf666ec5c3f390ecb3b07818365cf4be2c475cde/docs/mainline/review-gated/R4/public-development-v1/terminal.json) | `f554b18a916ad3cf7fb0785e4aeb2b8a16df53d5ba5e896949634e3297f254f5` |
| ext35 | [有限扩展逐条件配对记录](https://github.com/DonsonHH/AegisDC/blob/cf666ec5c3f390ecb3b07818365cf4be2c475cde/docs/mainline/review-gated/R4/finite-extension-study-v1/paired-results.json) | `e167cbe40b7791a9e94d0658e28fb8786244b3e40856f6d07aec025a20dd0bdc` |
| ext35_conditions | [有限扩展冻结条件](https://github.com/DonsonHH/AegisDC/blob/cf666ec5c3f390ecb3b07818365cf4be2c475cde/docs/mainline/review-gated/R4/finite-extension-v1/conditions.json) | `4b025bbb29e3652ff70a0a0ccd53556aaa131177bb3b6b9830c6c4e0053aa7d9` |

提取数据见 [figure-data.json](data/figure-data.json)。每一行保留带面板前缀的 ID、原 JSON Pointer、I／D／P 的 L／U、人员和工具实耗、阶段、合规性及恢复记录。五个机制实例另保存图示所需的原始分段、请求、回执与观察字段。原有整数和字符串形式的精确值直接复制；绘图库仅在设置坐标时转为浮点数。

## 2. 四幅图及中文图注

### 图 1：两个面板中的服务缺额比较

[SVG](figures/fig01-panel-comparisons.svg) · [PNG](figures/fig01-panel-comparisons.png)

**图注。** 公开开发面板有 19 行，其中 18 行符合有效比较条件；有限扩展面板有 35 行，其中 34 行符合有效比较条件。颜色分别表示 I 的服务缺额比比较处理更小、相同或更大。公开开发中，I 对 D 为 0／10／8，对 P 为 0／17／1；有限扩展中，I 对 D 为 1／28／5，对 P 为 1／32／1。非合规行 dev19.C09b 和 ext35.B03 的原始缺额分别为 13／19／0 秒、11／18／0 秒，单独保留且不作为有效获益。横轴是该有限清单的条件计数，不是概率。I 为核查后依证据处置，D 为合法直接修订，P 为既有保护。

**字段与转换。** dev19 使用 `/rows/{i}/valid_comparison` 与 `/rows/{i}/arms/{arm}/L`；ext35 使用 `/rows/{i}/eligible` 与相同的 `arms` 子路径。计数仅对冻结有效比较标志为真的行，按精确有理数比较 I 与 D／P 的 L。非合规原行仍保留在提取数据，图中另框列示。没有依据“谁获胜”重新筛选，没有把两个面板合并。

### 图 2：B01 避开隔离作业的服务机制

[SVG](figures/fig02-b01-service-timeline.svg) · [PNG](figures/fig02-b01-service-timeline.png)

**图注。** ext35.B01 中，I 在第 4 秒获得位置值为 1 的合法否定证据后停止，未发起修订，整个评价窗服务连续。D 的合法修订引起第 2—7 秒负荷隔离；第 7 秒恢复供电后，设备仍需启动至第 9 秒。D 的服务缺额为 7 秒，I 和 P 均为 0。D 的实际配置提交在第 5 秒完成，第 6 秒收到执行回执，第 9 秒收到复核记录。I／D／P 的人员实耗为 1／6／0 秒，工具实耗与之相同。这一优势针对 D 的作业副作用，并不表示 I 优于 P，也不表示避免了一次现场外生故障。

**字段与转换。** ext35 `/rows/3/arms/{arm}` 中的 `service_states` 提供半开服务分段；`observations/0/available_at` 提供 I 的证据到达；`execution_receipts/0/{committed_at,available_at}` 和 `verify_records/0/available_at` 提供 D 的事件。人员实耗与 L 直接读取，不从图形像素重算。绿色为实际服务，红色为隔离 OFF，黄色为已有电但设备 BOOTING。图中文字“service resumes; VERIFY arrives”表示两个事件在该实例同刻发生，不表示复核导致设备恢复。

### 图 3：G05／G06 的提交—截断边界

[SVG](figures/fig03-g05-g06-boundary.svg) · [PNG](figures/fig03-g05-g06-boundary.png)

**图注。** 两行除故障时刻外背景相同：ext35.G05 在第 12 秒截断，I 未完成实际提交；ext35.G06 在第 13 秒截断，I 已在第 12 秒完成提交，但尚未发出复核请求。菱形为实际完成的配置提交，空心圆为合法复核结果到达，红叉仅表示截断后未实施，不能解读为一次失败的提交尝试。条带颜色为实际供电来源，斜线表示虽已恢复 A 源但设备尚在启动、没有服务。G05 的 I／D／P 缺额为 5／0／5 秒；G06 为 0／0／4 秒。G06 的 I 具有实际服务后果，但仍是 `EXECUTED_UNVERIFIED`。D 两行都已合法复核；图示不支持取消复核要求。

**字段与转换。** ext35 `/rows/19`、`/rows/20` 的 `arms/{arm}/service_states`、`execution_receipts`、`verify_records`、`stage` 和 `L`；故障时点来自 ext35_conditions `/conditions/19/common/tF`、`/conditions/20/common/tF`。`service_states[*].state` 的第 0 项为供给来源、第 3 项为服务量、第 4 项为设备状态。图中截断之后继续绘到 H，保留供给恢复、设备启动及完整窗口缺额；没有把策略停止当作评价结束。

### 图 4：F01／F02 的 UPS 窗口端点

[SVG](figures/fig04-ups-horizon.svg) · [PNG](figures/fig04-ups-horizon.png)

**图注。** ext35.F01 缺设备就绪，ext35.F02 缺物理许可。六个 I／D／P 运行都由 A 源供给至第 17 秒，再由 UPS 在 `[17,20)` 交付 3 kJ；窗内服务连续，因此 L／U 都为 0。设备恰在 H＝20 转为 OFF，恢复记录为右删失、已观察下界为 0 秒。I 和 D 的 G 终态为 `FAILED`，P 为 `IDLE`。上图能量曲线是用已记录的 UPS 区间、冻结功率 1 kW 和初始能量 3 kJ 分段重建的出版曲线；其他条带和终态直接来自保存记录。零窗内缺额不能替代后备接管、恢复或长期连续性成功。

**字段与转换。** ext35 `/rows/13`、`/rows/14` 的 `arms/{arm}/{supply,service_states,ups_energy,ending_UPS,final_G,final_device,recoveries,L,U}`；条件中的 H／P／E0 来自 ext35_conditions `/conditions/13/common` 和 `/conditions/14/common`。对 0—17 秒，重建能量保持 E0；仅在保存记录明确为 UPS 的区间按 P 线性扣减。重绘器核对六个供给和服务分段相同后才画共享曲线。图中 H 处服务的空心点表示左侧极限，实心零点表示保存的 OFF 终态；这不延长研究窗，也不补算 H 之后的损失。

## 3. 重绘命令与工具身份

本轮使用已经安装的 Python 3.12.14、Matplotlib 3.10.8；未安装依赖。其他已装绘图依赖为 NumPy 2.3.5、Pillow 13.0.0、fontTools 4.61.1、kiwisolver 1.4.9、cycler 0.12.1、pyparsing 3.3.2、packaging 26.3、python-dateutil 4.0.0。SVG 保留文字，PNG 为 240 dpi。脚本固定颜色、字体选择和 SVG 哈希盐；不同绘图库版本可能改变图片字节，但不应改变数值来源或分类。

在仓库根目录执行下面命令可由已交付的提取数据重绘：

```bash
python docs/mainline/review-gated/R6/london-pre-manuscript-v1/tools/build_figures.py
```

若要从原件重新生成提取数据，先将上述三份精确原件放入一目录，分别命名为 `terminal.json`、`paired-results.json`、`conditions.json`，再执行：

```bash
python docs/mainline/review-gated/R6/london-pre-manuscript-v1/tools/extract_figure_data.py --source-dir /absolute/path/to/pinned-originals
```

提取器先验证原件的 SHA-256 和 Git blob；任一不符即停止。两份脚本不导入项目设施、策略、评分器、检查器或研究运行入口。

本轮仅运行上述既有记录提取和出版渲染。首次渲染后逐张查看 PNG，调整图 3 的文字位置，再完成最终渲染；这种排版迭代不增加模型调用或研究样本。最终数据、输出文件哈希与精确分类计数见 [render-receipt.json](figures/render-receipt.json)。正文图注解释英文图内标签，避免依赖机器上未安装的中文字库。
