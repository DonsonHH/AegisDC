# 12: 用独立算例验证数值与步长

**What to build:** 研究者能核对解析/手算守恒、事件顺序、量纲及步长收敛，发现误差边界。

**Blocked by:** 11

**Status:** ready-for-agent

**Milestone:** M2

- [ ] 预期来自独立手算/解析或外部可信参考，不由被测实现重新计算同一答案。
- [ ] 正常、零流、失电、容量紧张及相变域边界均有相应声明。
- [ ] 细化步长的关键结果变化可量化，误差大时不进入效果研究。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Pending implementation and acceptance.

## Preserved input for the later qualification

The independent 04–06 review retained a 432-case frozen-row mixture
representation probe, including five mass-scaled nominal pure-vapor inputs
strictly refused after encoded M/U/V reconstructs x=1.0000000000000002.
The exact inputs, hexadecimal values, outcomes, implementation/table identities
and a standalone reproducer are in
`evidence/mainline/engineering/04-06-root-acceptance/endpoint-representation/`.
Quantify this floating-point representation boundary together with the physical
domain; do not silently clip quality, assume every nominal construction is
exactly admissible, or call the finite probe empirical validation. This note
does not start ticket 12 ahead of blocker 11.
