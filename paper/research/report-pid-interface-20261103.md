# RGB→红外 / PID 电气视觉支路：成果、接口与主文边界

日期：2026-11-03。核查对象为本仓库、`C:/Users/Donson/Documents/PID` 的现存代码和归档实验材料，以及下列一手公开来源。本次只读既有材料、核对文件哈希和查看既有图片；没有运行模型、训练、仿真或新实验，没有修改 PID 项目及其 canonical。历史实验的作业状态按保存记录表述，未重新登录服务器检查运行环境或远端 checkpoint。

**结论：已有 RGB→显示域 IR 的真实科研实现和电气场景生成样图；Renly 已实现未校准参考的元数据入口及合格测量的状态更新边界。两者尚未组成一条在线视觉巡检链。生成 IR 像素不能直接作为 °C 温度、故障概率或接触电阻估计。** 具体依据见下表及 [R1]、[R2]、[R6]、[R7]。

## 1. 本任务中的 PID 是什么

PID 的官方名称是 **Physics-Informed Diffusion Model for Infrared Image Generation**。原论文将任务定义为 RGB→IR 图像翻译；RGB 条件引导潜空间扩散，TeV 分解提供训练期物理约束。[W1] 官方仓库亦将 `indir` 定义为可见光图像目录，`outdir` 定义为翻译后的红外图像目录。[W2]

现存官方推理脚本从 RGB 文件构造条件，执行 DDIM、解码、截断至 `[0,1]`，再乘 255、转 `uint8` 存图。该输出接口没有把像素转换成摄氏温度、输出仪器标定信息或预测故障概率的步骤。[R3] 因此，本报告以“外观 IR 参考 / display-IR”描述当前可接入产物。TeV 内部变量或 physics-informed 名称本身不构成现场测温溯源。[R3] 这也与项目 DEC-004 对 LLVIP 结论的限定一致。[R10]

实际红外仪器的温度测量需要设置发射率、反射温度，并按条件处理距离、大气和 IR 窗口补偿；FLIR 官方手册列出了这些测量参数。[W3] **由 RGB 生成一幅像红外的图，与获得一份校准温度观测，是不同的证据等级。** 此处为对论文任务、输出代码和测量手册的综合判断。[W1] [R3] [W3]

## 2. Renly 当前真正实现到哪一步

| 工作流环节 | 当前状态 | 可核查实现与限制 |
|---|---|---|
| RGB 采集、样本身份、资产/接点关联 | 待接入 Renly | 当前参考入口不读取 RGB 文件，不记录资产 ID、图像路径、ROI、坐标变换或模型版本。[R1] |
| PID/B-PID 推理生成外观 IR | 外部 PID 项目有历史产物；未接入 Renly | `src` / `tests` 定向检索中，`ingest_reference` 仅有定义和边界测试调用；没有模型调用。外部真实成果见第 3 节。[R1] [R4] [R6] [R7] |
| 未校准参考接收 | **已实现：元数据隔离入口** | `FacilityObserver.ingest_reference(metadata)` 接受 `kind='apparent_ir_reference'` 且不允许 `calibrated=True`；只向 `external_references` 追加固定的 `kind/calibrated/meaning` 三项。传入的 `pixel_values` 并不被读取或保存。[R1] [R4] |
| 从外观 IR 提取热点候选、置信度并绑定巡检任务 | 待接入 Renly | `external_references` 没有进入 `public_risk`、任务创建或调度；目前不能称“视觉热点已驱动巡检”。当前风险来自既有观测/估计与功率、流量等代理量。[R1] [R5] |
| 专业测量资格与校准声明边界 | **已实现：合成研究中的接口契约** | 任务要求匹配专业、`external_sensing` 访问和校准声明；`electrical_contact_heat` 只接受合格/经验证的接点温度证据，普通外观 IR 不在温度证据列表中。[R1] [R2] |
| 合格电气检查后更新接触温度状态 | **已实现：合成测量通道** | `calibrated_inspection('electrical', p)` 返回 `pod_index/contact_temperature_c`，完成检查后写入 `last_contact[p]`。这些值由合成过程产生，`calibrated=True` 是调用侧声明；代码没有验证真实仪器证书或读取现场测温设备。[R1] [R11] |
| 电气异常判定与风险代理 | **已实现：研究阈值** | `measured_anomaly` 对合格接点温度使用 `>60°C`；电气公开分为接点超限项、功率缺口和同组热项之和，再统一截顶。60°C 是当前合成研究设定，不能写成标准规定或现场诊断精度。[R5] |
| 温度→接触电阻反演、故障概率校准 | 未实现 | 当前没有真实电流/电压观测通道；`capability_matrix` 对这两项明确为 `implemented=False`。接点温度证据只回答接点温度任务。[R2] |

边界测试明确检查：接收未校准 IR 参考后，温度数组不变；未校准观测不能完成热测量；错误专业不能完成任务；热检查计数仍为零。[R4] 另一项测试还验证：即使把 `apparent_ir_reference` 的校准布尔值设为真，它也不符合温度证据类型契约。[R12] 本次读取了测试源码，没有执行这些会涉及合成过程的测试，故此处是**静态实现核查**。

接口表中“已实现”只表示该段代码和边界存在，不能扩展为已安装真实测温硬件、已调用视觉模型或已完成端到端电气巡检实验。[R1] [R2] [R11]

## 3. PID/B-PID 既有成果：数据域与证据等级

| 分支/材料 | 已有成果 | 可以写进本报告的结论 |
|---|---|---|
| PID 主训练/开发域 | 主线 1,367 对样本来自 **USTC RGB-Thermal Wildfire Segmentation Dataset**；325/78 开发划分中的旧路径 `electrical_registered_clean_v1` 是保留的历史误名。 | 支持野火 RGB→LWIR 显示图生成研究；不能把这些样本称为电气训练集或电气测温验证。[R6] |
| 四层通用翻译验证 | 官方 KAIST 预览 smoke 部分通过，完整官方复现未完成；USTC 193 图为已暴露的回顾性同域评估；LLVIP 独立正式比较有效但未通过，254p 外部时序 screen 有效但未通过。 | 模型/权重推理链工作，能学习同域显示图映射；现有材料不支持跨域、时序普遍可靠的结论。[R13] |
| 独立电气源 pilot | 保存报告审计了 103 个直接 FLIR 可见/热像对，以及不构成配对的 816 张 IR 处理变体；未获得可接受的负荷、环境、设备状态与辐射测量元数据。Radiometric payload 状态为 `unresolved_without_authoritative_rjpeg_parser`。 | 可用于配对、方向、配准及采集流程试验；不能宣称已具备电气热状态训练数据。新同步采集 pilot 是预注册方案，不能写成已经采集完成。[R14] [R15] |
| **B-PID Electrical 应用分支** | 归档报告记载 TRAIN5、HELDOUT2 的冻结 CPU 配准和一次留出 sanity 评估；step800/EMA，`evaluation_count=1`。机器可读原始均值：MAE 52.3446、RMSE 60.8588（0–255 显示码值）、PSNR 12.4698 dB、color SSIM 0.5440。 | **确有少量电气应用产物**，任务名称严格为 `3-channel false-color thermal display reconstruction`。这是 alignment-assisted sanity，不是校准热成像、温度预测、辐射重建或跨模态像素对应的证明。[R7] [R8] [R20] |
| **特定电气图的 PID/B-PID 对比** | 存在 RGB、伪彩目标、Original PID、B-PID 和差值的现成图。B-PID 从 Electrical 应用 step800 初始化，再做 3,200 步同图精修；Original PID 为 4,000 步同图适配。相同 512×512、DDIM200、eta0、seed20260725 采样。B-PID 显示域 PSNR 28.1616 dB、SSIM 0.7960。 | 可展示“已有 RGB→伪彩 IR 的特定场景重建实物”。数值是**同图训练拟合诊断**，不是留出泛化或等总训练预算的算法优越性。实际电气图片是户外绝缘子、铁塔和导线，不能称作机房母排/柜内接点样本。[R9] 本次已查看整图并核对三份原图/输出哈希。 |

B-PID Electrical 应用分支与 PID 主线电气采集 pilot 的范围不同：不能因为主线缺少物理元数据而抹掉已有应用图，也不能用少量显示图应用反过来证明主线完成了电气测温。归档的科学使用边界明确禁止温度和辐射精度主张；Fire 的 HELDOUT4 高强度响应 IoU 为 0，也不能拿该结果证明热点定位已经可用。[R7] [R8]

### 冻结决定与证据索引

已按顺序读取 PID-BPID 的[当前状态](<C:/Users/Donson/Documents/个人知识库/30-学习与研究/科研/PID-BPID/01-当前状态.md>)、[冻结决定](<C:/Users/Donson/Documents/个人知识库/30-学习与研究/科研/PID-BPID/02-冻结决策.md>)、[Evidence Index](<C:/Users/Donson/Documents/个人知识库/30-学习与研究/科研/PID-BPID/03-证据索引.md>)与[实验登记](<C:/Users/Donson/Documents/个人知识库/30-学习与研究/科研/PID-BPID/04-实验登记.md>)。canonical 的来源是历史整理，`last_verified: null`，索引条目仍为 `pending_link/pending_verification`，本次没有升级或回写。

- **DEC-002：RGB Conditioner 为 `frozen_no_go`。** 当前 PID 工作区的独立实验报告同样记载：工程门禁通过，但 1,700 步同预算质量比较 `admissible=true/accepted=false`，高频/任务门禁失败且 ROI MAE 恶化；不能把“已实现模块”包装成生成质量提升。[R10] [R16]
- **DEC-003：Task-aware Hotspot 为短门控失败。** 原始工作区报告保存了任务头可学习、但生成图收益未达门槛的结果；不能将任务头的置信度或像素强度当成电气故障概率。[R10] [R17]
- **DEC-004：LLVIP 不证明绝对温度真实性。** 与上述输出、数据和计量边界一致。[R10]

本次找到了一批实际报告和机器可读指标，可作为后续人工补索引的候选指针；canonical 仍保留原有 `pending_link` 状态。该“索引未链接”不等于从未做过实验，也不等于所有历史结论已在本轮获得远端复核。[R8] [R9] [R10]

## 4. 可放入主文的电气视觉工作流

> 配电视觉支路面向开关柜、母排及机柜交直流接点，拟将 RGB 图像经既有 PID/B-PID 科研实现生成外观 IR 参考，用于提出待核查的热点候选，再交由具备相应专业资格的巡检员或设备进行校准测温；仅合格接点温度观测进入接触温度状态更新与异常确认。当前仓库已实现未校准参考的元数据入口、专业/访问边界和合成接点测温更新；RGB 采集、PID 推理、热点候选到任务的映射以及真实测温设备尚未串接。既有电气样图属于伪彩显示图重建证据，不提供 °C 温度、故障概率或接触电阻反演结果。

段落依据：[R1] [R2] [R4] [R7] [R8] [R9]。其中开关柜/母排/机柜接点为本报告的**拟接入资产范围**，不是第 3 节户外电气样例已覆盖的资产类别。

画图建议用下列节点和线型，避免图形暗示整链已打通：

| 节点/连接 | 主文线型与标注 |
|---|---|
| `apparent_ir_reference, calibrated=False` → 参考元数据记录 | 实线，**已实现**；仅保留参考类型，不进入温度/故障状态。 |
| 专业任务 + 合格接点测量 → `last_contact[p]` → 研究阈值/风险代理 | 实线，**已实现于合成研究**；真实仪器接入另用虚线。 |
| RGB → PID/B-PID → 外观 IR → 热点候选 → 专业复核任务 | 虚线，**待接入 Renly**；其中 PID/B-PID 外部历史产物可另放样图说明。 |
| 合格真实测温设备 → 合格接点测量 | 虚线，**现场接入与计量验证待完成**。 |

没有证据支持把“电气异常样本正在合并出表”“RGB→红外温度分布已进入闭环”“热点候选已自动改变当前调度”写成既成事实。源码虽然定义了 `dc_contact_hotspot` 合成场景，但场景枚举和前向过程存在，不能替代视觉接入实验的运行记录。[R1] [R5] [R11]

### 为什么不能从生成温度反推接触电阻

当前前向模型先按设定的接触电阻/故障乘子与功率计算接点发热，再按热容量和环境换热推进接点温度。代码没有执行反向参数辨识，也没有用合格温度更新 `contact_resistance_ohm`。[R11] 用物理关系概括，该辨识至少涉及

\[
C_c\frac{dT_c}{dt}=I^2R_c-G_c(T_c-T_a).
\]

这是对现有接点前向热模型的解释式，不是本次新增算法。单个温度值不能同时确定电流、接触电阻、换热和瞬态条件；生成的显示图还没有独立辐射测量约束。当前真实电流通道也未实现，因此“提取视觉温度后校正接触电阻损耗代理”超出代码与证据范围。[R2] [R11] [W3] 当前可写的状态更新仅是：合格电气检查完成后，`last_contact[p] ← measured_contact_temperature_c`。[R1]

## 5. 可复用的既有样图与架构图（只读，未复制）

| 资产 | 精确路径 | 数据域与完成状态 |
|---|---|---|
| RGB 输入单图 | [electrical_scene_001.png](<C:/Users/Donson/Documents/PID/data/user_validation_20260725/prepared/electrical/visible/electrical_scene_001.png>) | 用户提供的户外电气场景；已准备的 512×512 RGB 条件。 |
| 真实伪彩目标单图 | [electrical_scene_001.png](<C:/Users/Donson/Documents/PID/data/user_validation_20260725/prepared/electrical/lwir/electrical_scene_001.png>) | 同一场景热像显示截图的固定裁剪/缩放；温标、色条和 FLIR 标志被裁去，文件不是辐射温度矩阵。[R18] |
| 生成外观 IR 单图 | [electrical_bpid_refined_selected.png](<C:/Users/Donson/Documents/PID/reports/specific_scene_pid_bpid_comparison_20260730/final/electrical_bpid_refined_selected.png>) | 已有 B-PID EMA 输出；同图拟合、显示域，非留出样本推理证明。[R9] |
| 完整实际对比图 | [specific_scene_pid_vs_bpid_comparison.png](<C:/Users/Donson/Documents/PID/reports/specific_scene_pid_bpid_comparison_20260730/final/specific_scene_pid_vs_bpid_comparison.png>)；[SVG](<C:/Users/Donson/Documents/PID/reports/specific_scene_pid_bpid_comparison_20260730/final/specific_scene_pid_vs_bpid_comparison.svg>) | 4920×2250 PNG；上行为 Fire、下行为 Electrical，各含 RGB、目标、PID、B-PID、差值。已视觉查看，图内明确写有同图拟合边界。用于主文时建议保留该边界，不把两域合成图称为机房验证。[R9] |
| 配准/共同视场示意 | [electrical_cropped_abc_triplet.png](<C:/Users/Donson/Documents/PID/reports/registration_valid_mask_figure_20260730/final/electrical_cropped_abc_triplet.png>)；[electrical_thermal_sensor_plane_middle.png](<C:/Users/Donson/Documents/PID/reports/registration_valid_mask_figure_20260730/final/electrical_thermal_sensor_plane_middle.png>) | 已存最终图；70.75% mask 是二维配准加明确安全内缩的保守 common-FOV，不是内外参/深度标定后的物理投影有效性。旧 `valid_mask_figure_20260730` 中近全白 mask 已被声明取代。[R19] |
| 官方 PID 架构图 | [PID.png](<C:/Users/Donson/Documents/PID/third_party/PID/PID.png>) | 已视觉查看，官方 `(b) Train LDM`：道路车辆 RGB/IR、扩散网络、TeV 双损失。属于外部研究训练结构，不能标成 Renly 当前部署架构；采用时标注原作者来源。[W2] |
| 本地可编辑论文图源 | [Fig1-5_最终版_页3页5分界线_图4RGB裁剪.vsdx](<C:/Users/Donson/Documents/PID/Fig1-5_最终版_页3页5分界线_图4RGB裁剪.vsdx>) | 文件存在；本次未打开、渲染或核查内部图元，不能据文件名判定其内容或最终可用性。 |

三联图最合适的图注为：“**既有电气场景的 RGB→伪彩 IR 重建样例。** RGB 条件、真实热像显示目标与 B-PID 生成结果来自同一户外电气样本；生成结果经过同图适配，展示显示域重建能力，不代表留出泛化、校准测温或机房故障验证。”[R9] [R18]

本次核对到下列哈希与 `specific_scene_pid_vs_bpid_provenance.json` 一致：[R9]

```text
RGB condition: b00d7a1fc32c80060495b97b3fd061d5c4b8529695cc3c930b0250c2f07bff33
Thermal display target: 0c47931b43e9bee87a83460edede64e7afb27396accef77ab5b73702f5be7907
B-PID selected image: 4368d1de25e2d3c98e5e838a98a483c87c5531471046ae52a9c958367a8da02a
```

## 6. 来源与核查快照

公开一手来源于 2026-11-03 查询；本报告对它们只作简短方法与测量边界归纳。工程完成度来自本地源码，历史实验事实来自保存报告/JSON，未将公开论文的实验结果移植为本项目结果。

- [W1]：Mao 等 PID 原论文，§3、§4.1、§5.2–5.3；论文任务、生成方法与讨论。
- [W2]：作者官方 PID 仓库 README 与架构图。
- [W3]：FLIR T8xx 官方手册，Measurement parameters。
- [R1]：Renly `facility_observation.py`，第 11–24、50–88 行；参考入口及测量更新。
- [R2]：Renly `inspection_contracts.py`，第 7–40 行；任务/证据兼容边界。
- [R3]：官方 `rgb2ir_vqf8.py`，第 71–109 行；实际推理输入和图像输出。
- [R4]：`test_facility.py`，第 113–124 行；未校准参考不能改温度或完成检查。
- [R5]：`active_inspection.py`，第 28–35、93–115 行；测量异常与公开风险代理。
- [R6]：PID 当前 README 的 Dataset-domain status；数据域纠正。
- [R7]：B-PID 应用科学使用边界；Electrical/Fire 的结论范围。
- [R8]：Electrical 留出一次评估 JSON 及最终应用报告；原始码值指标、任务标签与评估次数。
- [R9]：特定场景对比 README、provenance JSON、CSV；同图拟合、预算与采样条件。
- [R10]：PID-BPID canonical 四件套，尤其 DEC-002/003/004；保留其 `pending_link` 状态。
- [R11]：Renly `facility.py`，第 12、130–144、176–219、271–281 行；合成场景、接点前向过程与合成测量。
- [R12]：`test_coverage_plan.py`，第 63–73 行；错误证据类型不因校准布尔值而变成温度测量。
- [R13]：PID 四层验证状态；同域/独立/时序证据区分。
- [R14]：电气候选源审计决定；103 对、816 变体、辐射载荷未决与获准用途。
- [R15]：电气 RGB/LWIR 同步数据 pilot 预注册；需要采集的字段和后续门禁。
- [R16]：RGB Conditioner 正式质量门禁报告，第 109–168 行；NO-GO 的直接工作区材料。
- [R17]：Task-aware Hotspot gate，第 3–35 行；可学习任务头与生成质量失败的区别。
- [R18]：Original PID 特定场景适配报告；固定截图裁剪和同图训练的性质。
- [R19]：最终 registration common-FOV 图 README；70.75% mask 的构造及测量边界。
- [R20]：B-PID Fire/Electrical 应用最终完成报告；TRAIN5/HELDOUT2、一次评估与完成范围。

当前核查的三个关键 Renly 文件 SHA-256：

```text
src/patrol_rsi/facility_observation.py  9637c0d2d1cdb83426035dd3fb2aaed0cb267783771d22ba024ccffda4f21a57
src/patrol_rsi/inspection_contracts.py 803bef71270d6a66ce985ae4b881865b4b3fd741567c02c67641adfb187a08ef
tests/test_facility.py                4c3143a2d2ba6a186136219de373c07a83494d8539e2febf229d2bfe0b81196b
```

[W1]: https://arxiv.org/html/2407.09299v2
[W2]: https://github.com/fangyuanmao/PID
[W3]: https://docs.flir.com/T810413/en-US/latest/s13.html
[R1]: <C:/Users/Donson/Documents/ChatGPT/Renly/src/patrol_rsi/facility_observation.py:63>
[R2]: <C:/Users/Donson/Documents/ChatGPT/Renly/src/patrol_rsi/inspection_contracts.py:7>
[R3]: <C:/Users/Donson/Documents/PID/third_party/PID/scripts/rgb2ir_vqf8.py:71>
[R4]: <C:/Users/Donson/Documents/ChatGPT/Renly/tests/test_facility.py:113>
[R5]: <C:/Users/Donson/Documents/ChatGPT/Renly/src/patrol_rsi/active_inspection.py:28>
[R6]: <C:/Users/Donson/Documents/PID/README.md:7>
[R7]: <C:/Users/Donson/Documents/PID/reports/valid_mask_figure_20260730/source_reports/APPLICATION_SCIENTIFIC_USE_BOUNDARY.md>
[R8]: <C:/Users/Donson/Documents/PID/reports/valid_mask_figure_20260730/source_reports/electrical_heldout_once_metrics.json>
[R9]: <C:/Users/Donson/Documents/PID/reports/specific_scene_pid_bpid_comparison_20260730/final/specific_scene_pid_vs_bpid_provenance.json>
[R10]: <C:/Users/Donson/Documents/个人知识库/30-学习与研究/科研/PID-BPID/02-冻结决策.md:28>
[R11]: <C:/Users/Donson/Documents/ChatGPT/Renly/src/patrol_rsi/facility.py:176>
[R12]: <C:/Users/Donson/Documents/ChatGPT/Renly/tests/test_coverage_plan.py:63>
[R13]: <C:/Users/Donson/Documents/PID/reports/PID_FOUR_LEVEL_VALIDATION_STATUS.md>
[R14]: <C:/Users/Donson/Documents/PID/reports/ELECTRICAL_PILOT_SOURCE_AUDIT_DECISION.md>
[R15]: <C:/Users/Donson/Documents/PID/reports/ELECTRICAL_DATA_PILOT_PREREGISTRATION.md>
[R16]: <C:/Users/Donson/Documents/PID/reports/RGB_CONDITIONER_V100_GATE.md:109>
[R17]: <C:/Users/Donson/Documents/PID/reports/HOTSPOT_TASK_PID.md:3>
[R18]: <C:/Users/Donson/Documents/PID/reports/SPECIFIC_SCENE_PID_ADAPTATION_20260725.md>
[R19]: <C:/Users/Donson/Documents/PID/reports/registration_valid_mask_figure_20260730/final/README.md>
[R20]: <C:/Users/Donson/Documents/PID/reports/valid_mask_figure_20260730/source_reports/FINAL_PAPER_READY_V1_COMPLETION_REPORT_20260724.md>
