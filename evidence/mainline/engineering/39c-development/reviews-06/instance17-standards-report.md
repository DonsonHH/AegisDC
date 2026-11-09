# 39c-17 实例服务绑定：静态关闭增补

结论：PASS_STATIC_CODE_CLOSURE。固定efa60470e84d2dde0f399fa78db38b01b88ffab5，对比16fcedfd；原39C-INSTANCE16-STANDARDS-01的额外纯functional-path门槛已静态关闭，实际17绿测尚待回收。

唯一runtime改动problem_closure.py:46,56–58，改为绑定已校验nominal实体中kind=service的显式服务ID；服务检查仍强制同ID及声明来源覆盖。自己的行动、复检、当前证据、误差/同源/跨度和两类样本规则不变。图、物理、权限、安全和阈值未改，也不把联合有限证据升级为因果服务恢复证明。未发现新增硬问题或有实际影响smell。

原16冻结test/descriptor/两份基础输入/contract/protocol/stager与红源5b35417f、16f及本候选逐字一致。已提交133377的七件小原件与前次保存raw身份一致，仍FAILED，0返回native/决策；原16f审查两文件SHA未变。17在原两phase用尽后另立唯一20命名空间，限1测试/1接口/6秒/最多6决策，零新增注册研究；完整输入预登记242997字节、d959880e…，与原失败输入身份相同。实际生成输入仍须回收后核此SHA，当前未假验收。

旧180/config/runner/workflow无改。首次只读Git查询误猜17工具名而返回path-not-found，按协议给出的真实工具名继续静态读取；未执行项目或产生试验。全程零项目、测试、验证器、策略、仿真、指标或远端任务；整39c尚未接受。
