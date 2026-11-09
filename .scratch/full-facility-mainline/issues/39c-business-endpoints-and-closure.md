# 39c: 将业务端点与验证关闭纳入可执行评价

**What to build:** 先定义故障真值、可检测机会、提前时间和关闭准则，再把检查、实际处置、恢复与证据核验接入同一次评价；不沿用未定义指标为零。

**Blocked by:** 39a

**Status:** claimed

**Milestone:** M7

- [ ] 区分外部误报、读数发现、故障诊断、正常及未知；定义系统误判/漏报的机会分母与时间窗，标出不可检测和来不及执行的情形。
- [ ] 提前量明确相对故障/损失/处置截止节点，未观察到节点时按预定删失规则；预防效应须有匹配反事实或明确未识别。
- [ ] 启用适用的处置后复检/服务证据与验证关闭，动作完成、症状退去、未确认、风险接受和升级分别记时与计数。
- [ ] 人、工具、路程、等待、作业、推理和失败成本分列；所有正常、正例、反例及未测状态留在完整分母。
- [ ] 私有真值只进评价器；派工与关闭只能用已到达合法证据。先冻结工程契约，远端逐个公共行为红绿验证；不重标原180次的未测端点。

## Evidence

Initial ready-frontier snapshot after39a and39b acceptance; superseded below by first-slice development. User-review F3/F4 and original R6 coverage. Registered old comparison used closure_program=None and remains unchanged. Current predecessor evidence: `docs/mainline/evidence/39b-root.json`; a frozen39c behavior contract and remote red/green slices must precede new evaluation.

Planning only: `docs/mainline/39c-business-endpoints-plan.md` defines the proposed event/opportunity/closure denominators and remote behavior sequence. At that planning snapshot, no freeze or execution had started; first finite slice below is now complete, whole39c remains unaccepted.

Owner `/root`, existing canonical checkout, branch`donson/mainline-39c-endpoints`, base42252bf8. First frozen remote slice is `docs/mainline/39c-closure-endpoint-protocol-01.json`; it records actual closure timestamps only. All39c acceptance boxes remain open until the full endpoint/closure scope is implemented and verified.

First native closure-endpoint slice: `evidence/mainline/engineering/39c-development/slice-01/README.md`; frozen3e6fd367 red133147, implementation59acded7 green133150, one10s native horizon/eight returned decisions. Original red error retained. No closure threshold changed. Full truth/opportunity/lead/cost/dynamic-instance scope and negative qualification remain open; this is not a39c acceptance.
