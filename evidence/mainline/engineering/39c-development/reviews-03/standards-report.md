# 39c 诊断纠正 Standards 静态复核

固定 c2872932b3aa77804762861c7b46385c1bd79f3b，对比 3e81e7fa。结论：PUBLIC_AND_ORIGINALS_PASS / SAVED_GUARD_CORRECTION_REQUIRED；一项 P2，整39c未接受。

[P2] scripts/check_saved_diagnostic_qualification.py:25,33–53,59–104 用 assert 承担分配、源/原44文件及业务预期检查，却未显式拒绝 sys.flags.optimize。job.slurm 未清除 PYTHONOPTIMIZE，attempt 未记录模式；优化解释器可剥离检查而仍输出成功。应以不可剥离的入口检查拒绝优化，并记录模式；依据 AGENTS.md:39 和06协议:29的实际身份核验契约。这是门禁实现问题，不证明133280实际使用优化，不应改写其原回执。主代理已确认将单列前瞻纠正。

其余有限检查通过：04原133274仍FAILED，5测试/1失败、六运行/18决策原件留存；44个原输出中本地8件逐SHA匹配，另36件完整匹配私有索引，六摘要执行身份44文件均属原3e81。未重新打开服务器轨迹或重算指标。原180及配置Git范围未改。

05红133275/绿133279的52,360字节公开输入、测试/协议/工具完全一致，均零设施调用；1fc→5c仅condition_assessment.py改变资格筛选顺序，保留旧合格采样时标、被排除记录及私有隔离。

06仅读取旧结果的新保存核验，不重标旧测试；有限/空分母及UNKNOWN/null保持。四条新增属性均为精确路径，原CRLF及拒绝日志SHA保留，无宽泛豁免。未发现有实际影响的smell。零项目/测试/验证器/仿真/策略/指标调用。
