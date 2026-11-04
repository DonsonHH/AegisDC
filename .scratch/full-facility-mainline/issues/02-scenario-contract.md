# 02: 读取并核验独立全设施场景

**What to build:** 研究者通过公开加载器和CLI审查一套八域、四图、参数来源明确的郑州参照研究场景。

**Blocked by:** 01

**Status:** resolved

**Milestone:** M1

- [x] 场景覆盖八域，每域有状态/输入输出/行为/检查或作业入口及其服务/可行性作用定义。
- [x] 四图引用共享实体身份，电能/热/质量/信息/通行类型不能混用；资质/工具/位置可追踪。
- [x] 数值带单位、来源性质和有效范围；活动模型所需未知量、重复字段、非有限值和不一致端点拒绝。
- [x] CLI输出对象、参数、关联和未验证范围，状态只声明结构已定义，不声称模型已运行。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Code commits: `bb336cf672d124d4cbedd89f2e50a5d540aaecf7` and `d9b8de6898aa4811bc99c74ee95228b0cfbc1934`.

- Public interfaces: `aegis_dc.scenario.load_scenario(path)` returns a validated dictionary; `describe_scenario(scenario)` describes that validated contract; `python -m aegis_dc scenario [--model PATH]` loads/checks only.
- Default configuration: `configs/full-facility-mainline-v1.json`, a declared Zhengzhou-inspired synthetic facility with 8 domains, 38 shared entities, 38 SI parameters, four relation views (21 physical / 16 functional / 11 control-information / 5 access edges), four professional executors and null site-data gaps.
- Red/green observations: absent public module; incomplete domain contract; invalid SI/value/range/provenance accepted; duplicate/dangling/type-inconsistent relations accepted; incompatible fluid/electrical ports accepted; incompatible qualifications/tools/work references accepted; invalid site identity or zero-valued gap accepted; undeclared numeric shortcuts accepted; unknown CLI command; malformed symbols raised raw TypeError; unrepresentable integer raised OverflowError. Each new behavior was implemented after its failing case. The existing strict JSON helper already rejected duplicate fields and nonfinite constants; that integration guard was retained rather than represented as a newly failing feature.
- After merging the current integration branch, `PYTHONPATH=<worktree>/src python -X utf8 -m unittest discover -s tests -p test_full_facility_scenario.py -v`: 13 passed, 0 failures/errors/skips.
- Compatibility: the corresponding `test_facility_foundation.py` command passed 16 tests. CLI status/foundation/risk-demo/scenario smoke reads succeeded; legacy source/config/evidence were not changed by this ticket.
- `git diff --check` passed. A later integration review and full-suite acceptance are owned by the root agent.

The accepted scope is **STRUCTURE_DEFINED_NOT_SIMULATED**. Domain behaviors are declarations, individual parameter ranges do not establish coupled initialization, field calibration is PENDING and research gain is NOT_ESTABLISHED. No plant simulation, training or registered research trial was run. This resolves ticket 02, not M1 or the overall research goal.

## Integration acceptance

Accepted by root: source0564471a; Standards0, Spec0; enabled-Torch complete engineering/evidence acceptance155/155, zero skips/failures/errors. Gate record: docs/mainline/evidence/02.json. This remains structural-only and does not complete M1 or the research goal.
