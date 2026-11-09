**窄纠正Standards静态PASS，无新增硬规则或有实际影响的smell发现。** 固定源`24f35d8312a860325a7737cfcc363d0d69911822`，基点`9efc9564`。

可选test_names只在提供清单时走命名加载；冻结清单为expiry和no-human两个唯一、完整方法名，不含8秒window方法，当前模块无额外加载/初始化执行。未提供时原discover不变，因此不会在此分配发现并重跑成功例。

输入准备仅清no_human无用options、将实际TTL同步至公开projection；原断言、variant/base和59ac业务/plant源码未改。v3 stage固定正确文件、两方法、2入口及17返回上限，源码/输入/runner/协议在新调用前冻结。

133194零测试失败及133195三测试两错误均保留，后者8秒成功原件不重跑；新增一次只分配原失败两例，累计reserved/实际及完成窗口分开，不是自动重试。符合AGENTS来源、预算、remote与原件边界。

仅静态文本/Git/必要SHA；项目、测试、验证器、指标运行均0，旧55ef报告未改。实际新job结果未接受，整票39c仍claimed。详细身份与范围见`source-pin.json`。
