# 39a保存数据补读：原件与范围

冻结源`cfea64cbb059e0059ea2d5e8f148d03b66011b26`；[协议](../../../../docs/mainline/audits/20261109-integrated/saved-audit-protocol.json)与[工具](../../../../scripts/audit_integrated_scope.py)在调用前提交。输入/工具9件的精确Git对象、SHA256及大小在[staging-manifest](staging-manifest.json)。缓存不是交付成员。

Slurm作业**133102**，cu计算节点、1CPU/1GiB、实际1秒，`COMPLETED 0:0`。这是保存结果审计，不是新增科研试验：设施/策略/模型调用及统计单位均0。唯一执行成功，没有自动重试。详细原180次轨迹未重跑。

- [集中度、无人工和风险/参数范围](diagnostic-results.json)
- [正式输入与默认时间轴](timing-scope.json)
- [调用前记录](attempt.json)、[终态/输出身份](terminal.json)、[Slurm账](slurm-accounting.txt)
- [提交脚本](job.slurm)、[stdout](stdout.log)、[stderr](stderr.log)

本地下载只包含必要摘要、元数据与完整性凭据；远端私有目录`mainline/39a-saved-audit-01`保留输入/工具和日志。回传已对比调用前本地清单及终态SHA，没有在桌面重算数值。

原16工况主均值及180次注册原件不变。去掉confirmation-12的补充值只是效应集中度描述，不能替代主要结果或作为下一轮选择确认条件的规则。单一代表输入说明共同配置的时间/任务范围，不证明所有域的业务端点已覆盖。
