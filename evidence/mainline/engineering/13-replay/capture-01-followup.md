# Retained first engineering capture refusal

`capture-01/receipt.json` remains FAIL, execution source
`79e2f926003248dbecf3d28bf5a343bebf82a7e9`. Its 139 durable files were committed
as `dcb118dc` before the authoring-tool correction. All 13 terminal attempt
records and six CLI calls were written; the full regression had not started.

The failure was `Actual engineering inputs differ from the frozen case` in the
unchanged M1 checker. That checker requires the legacy boundary-event list,
while ticket 13 deliberately separates engineering commands and canonically
orders independent equal-time parameters. The new ticket-13 checker now builds
the expected origin-separated input contract from the pinned original case,
checks events/commands/jobs against it, and adapts only that expected input
portion before reusing the original literal physical and balance checks.

No saved actual trajectory, original runbook outcome, old checker, receipt or
failure is changed. A diagnostic recheck under corrected tools is not promotion
of this receipt. A fresh, separately named capture and execution revision are
required for a passing delivery, with the updated shared runtime if applicable.

This is an authoring/verification failure in engineering preparation, not a
registered research trial, numerical qualification or scientific result.
