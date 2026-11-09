# 39c 保存核验模式 P2 关闭复核

结论：PASS_STATIC_P2_CLOSED。固定 dc6a0380aa24397aca5594451466301d3d3e8e09，对比 c2872932；仅关闭原39C-DIAG-STANDARDS-01，不接受整39c。

scripts/check_saved_diagnostic_qualification.py:24–25 以显式if拒绝sys.flags.optimize，早于参数、manifest/旧数据读取及输出创建；正常attempt/terminal记模式0。stage_saved_mode_07.py:33清除PYTHONOPTIMIZE，冻结测试:29–41再次清除环境变量并检查-O拒绝、无输出，符合AGENTS持久身份核验及07契约。无新增硬问题或有实际影响的smell。

原红133281保留：旧工具-O返回0并产生子PASSED，父测试失败；这些产物只证明门禁缺陷，未冒充44文件核验。绿133282在同一冻结测试/协议/输入下拒绝-O，再以正常子进程检查原44输出，子attempt/terminal均记optimize0。独立核对两份清单9个Git-bound文件、红7/绿9个完整输出及嵌套哈希；子目录已实际进入Git，不只存在工作目录。

源码/原记录边界清楚：原133274仍FAILED；原133280模式未记录的限制保留，原04/06记录、域runtime、configs及180研究范围无改。原c287两份review字节原样复制；两份CSV为原CRLF和同一SHA，仅精确路径属性，不免身份核验。

此次只读Git/保存字节，不打开远端轨迹，不运行项目、测试、验证器、策略、仿真或指标；新的正常子进程核验依据来自已保存Slurm原件，不冒充本机执行。
