# Triage roles

Local tracker roles use the canonical vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`.

Generated implementation tickets are `ready-for-agent` by construction and still obey their blocking edges. `claimed`, `resolved` and `deferred-by-gate` are execution lifecycle states. No GitHub labels or external queue were created.
