# Issue tracker: versioned local Markdown

**2026-11-16 current gate:** User accepted34201ef7 finite runner qualification and froze the public-development protocol. Only the [R4 original19-condition batch](../mainline/review-gated/R4/public-development-v1/scope.md) is authorized, core1c0b0c47 unchanged. Pin entry/manifest before calls; stop on fatal errors and deliver all19 rows. Confirmation and R5/RSI stay closed.

The user approved autonomous mainline planning and implementation on 2026-11-04. Planning granularity and routine implementation choices are delegated. Keep the task graph with the corresponding source revision in Git.

- Feature directory: `.scratch/full-facility-mainline/`.
- Specification: `spec.md` in that directory.
- One implementation ticket per file in `issues/`, numbered in dependency order.
- `Blocked by` names genuine predecessor tickets. A ticket may start only when every blocker is `resolved` with its acceptance evidence, except for the explicitly accounted conditional branch below.
- Ticket `Status` is authoritative: `ready-for-agent`, `claimed`, `resolved`, or `deferred-by-gate`. Ready-for-agent describes an executable ticket; blockers still determine whether it is on the ready frontier.
- Append implementation/check/source-commit pointers under the ticket's Evidence section. Resolve only after the behavior and stage gate are verified.
- `.scratch/full-facility-mainline/map.md` provides navigation. `docs/mainline/progress.json` records the active ticket, milestone gates and research conclusion; it does not replace the ticket evidence.
- During an assigned worktree implementation, its ticket lifecycle is on that branch until merge. Progress active-work entries locate it; check live agent and Git state before claiming/restarting. Exclude a confirmed live assigned ticket from the available frontier even if the integration copy still says ready-for-agent.
- Conditional agent/RSI tickets require their predecessor eligibility decision. A documented deferred branch is not evidence of a measured gain.

## Conditional eligibility branch

After 38 resolves a `NOT_ELIGIBLE` decision with evidence, 39 and 40 may be marked `deferred-by-gate` with that decision as their evidence; their experimental bodies have not run. Ticket 41 may consume either resolved results or these documented no-run states. No earlier physical, evidence, personnel or independent-comparison ticket accepts this exception. Ticket 42 checks that the branch is honestly accounted, not that an unrun increment was measured.

Publishing to this tracker means committing these files with the milestone. GitHub remains the source publication destination; this setup does not create an external task queue or send messages.
