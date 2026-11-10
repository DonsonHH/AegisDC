# 51：私有实例管理端点实际通过

新私有v2端点保留同一次设施运行中的完整公开判定、各自作业身份，以及物理核验和管理处置的不同时标。[冻结契约](../../../../../docs/mainline/39c-instance-management-endpoint-contract-51.md) · [协议](../../../../../docs/mainline/39c-instance-management-endpoint-protocol-51.json) · [实际端点](green/private-v2/business-result.json) · [公开原件](green/private-v2/public-lifecycle.json)。

|同次运行的实际值|旧问题q0|新问题q1|
|---|---:|---:|
|打开时刻（秒）|0|5.75|
|自身行动完成／报告到达|3.25／3.75|未发生|
|自身复检完成／报告到达|5／5.5|未发生|
|首次核验关闭|5.5|未观察到|
|首次选中接受风险|未发生|5.75|
|管理记录观察／到达|无|5.75／5.75|
|该管理记录的实际评估时刻|无|5.75、6|
|末次状态|VERIFIED_CLOSED|RISK_ACCEPTED|
|末次risk_closed|true|false|

只有action-0与recheck-0实际执行；q1自身复检不通过、物理恢复声明false。端点assessment逐项等于公开原件，保留own_recheck、checks、trace及身份字段。错误复检槽位、旧私有v1混用公开v2均在积分前拒绝。

|封存阶段|运行源码|接口进入|完成窗口／秒数|返回决策|终态|
|---|---|---:|---:|---:|---|
|原红68|294e4f9b|3|0／0|0|预期契约缺口；2failures、1error保留|
|新绿69|8131aae0|3|1／6|7|0failure、0error、0skip|

[红摘要](red-result.json)、[绿摘要](green-result.json)保存独立控制／运行版本、原始成员哈希及完整source manifest。两包各58份源文件核对Git blobs；绿10份回传文件逐件匹配原terminal索引。完整轨迹和守恒记录留在私有服务器各自68／69目录。原运行没有.git元数据，code_identity.git_commit为空，按实际执行文件哈希绑定源码，未伪造提交。

本片新增6次接口进入、1个6秒窗口、7次返回；39c开发捕获累计85次进入、37窗口113.25秒、140次返回，直接公开选择仍38次，嵌套调用未仪器化。原180次研究、NO_PRACTICAL_GAIN及失败均保持，新增模型／注册研究0。后续管理分支资格、诊断兼容、联合评价与完整重放、整票独立复核／零跳过根／fresh仍开放。
