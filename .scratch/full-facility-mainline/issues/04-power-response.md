# 04: 在全场传播供电容量和失电

**What to build:** 改变馈线、整流容量或供电状态，会按真实连接影响IT和辅机及服务。

**Blocked by:** 03

**Status:** resolved

**Milestone:** M1

- [x] 级次和转换损耗守恒，容量不足不能凭空多供电。
- [x] 停电后的发热取实际供电功率；需求缺额继续计量。
- [x] 馈线/负载关系有来源或假设，图可达不等于整站必停。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Assigned implementation: `donson/mainline-04-power`, worktree
`.work/worktrees/full-site-04`, owner `mainline_04_power`. The live assignment and
worktree were checked before claiming on 2026-11-04; starting integration commit
is `0ee160cdcdbd195acf35d552abd8040ef7e55b5c`. Public verification boundaries are
`simulate_scenario`/CLI and the electrical component interfaces used by that run.

Accepted implementation: `a50b1e5e6f87397a57b226f805992fd5470a6f7f`.
The existing grid/switchboard/rectifier/UPS/generator allocation is verified at
the declared aggregate ideal AC boundary. The actual code correction rejects
nonfinite/nonphysical electrical component inputs; two red runs and subsequent
green runs are preserved. Shared plant/loader/runtime/CLI and the accepted v2
snapshot were not changed by this ticket.

- Model, assumptions, independent hand budgets and limits:
  `docs/mainline/power-verification.md`.
- Public full-facility/CLI receipt:
  `evidence/mainline/engineering/04-power/run-01-committed-public-validation/receipt.json`;
  9 cases, 209 checks passed, 8 domains in every case, committed clean source.
- Fresh artifact verification: `artifact-integrity.json` beside that receipt;
  27 scenario/trajectory/balance files match manifest SHA-256 and record counts.
- Focused command: main Python with `PYTHONPATH=<worktree>/src`,
  `-m unittest discover -s tests -p test_mainline_power.py -v`: 9/9 passed.
- Prior plant/property/CLI command: same Python/path,
  `-m unittest discover -s tests -p test_full_facility_plant.py -v`: 22/22 passed.
- Full regression command: same Python/path,
  `-m unittest discover -s tests -v`: 188 collected, 186 executed, 2 declared
  existing optional Torch skips, zero failures/errors. Complete original log is
  `evidence/mainline/engineering/04-power/attempt-13-full-regression/tests.log`.
  Root enabled-Torch integration acceptance is separate; this is not a zero-skip
  claim.
- Reproduction command: same Python/path,
  `evidence/mainline/engineering/04-power/reproduce.py --output <new-directory>`.
  Actual CLI command/input/stdout/stderr and all input/source/property identities
  are stored in the receipt directory. Existing outputs are never reused.

Verified outcomes include half service under capacity limitation while pumps and
control stay powered, separate compute/network/storage response, selective UPS
coverage, finite conversion loss, and unchanged exogenous demand plus continuing
stored-heat transfer during outage/restoration. MV/LV distribution is explicitly
ideal/lumped: transformer/cable losses, voltage/current, branch protection and
real site availability are not claimed. Site feeder mapping remains unresolved.

Engineering fixtures only; zero registered research trials, training runs or AI
calls. Mainline progress was re-read before resolution: M1 remains in progress,
the complete-facility objective remains active, and this ticket does not resolve
M2-M7, field calibration or policy-effect/AI/RSI conclusions.
