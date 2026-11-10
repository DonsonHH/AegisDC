# Spec review: historical opening identity

Fixed range: d286f8cd50adb089337a230a224cb5a9fac6c7fb...93b4b3cffbb627eb4c2375b7a39a74b4c17f2236.
Independent reviewer: /root/review39c28_spec.
Status: preliminary finding delivered; the reviewer's final turn failed and no independent
final PASS was received. The finding below remains actionable; do not label it a complete review.

The same-target protocol27 witness and protocol28 selection path agree with their narrow
expectations by source.

Finding 39C-HISTORY-SPEC-03: historical replay filters away an actual question instance that
opened after a review record arrived. open_questions can then manufacture the same slot ID
from an earlier trigger at the historical clock. A record observed at2s can be attached as
historical ESCALATED to question-0 actually opened at6s from a different origin, after the
earlier trigger has expired. Projection matches only the slot/question ID.

Contract21 requires review observation not precede the actual instance opening; protocol28
preserves exact scope. Current dispatch is unaffected, but the historical lifecycle can
misattribute a management event.

Remediation: guard using the actual instance's opening and identity, and qualify through
the public decision interface. Preserve completed red/green outcomes and do not rerun them.
False-alarm dossiers and combined business-endpoint evaluation remain outside this finite review.
