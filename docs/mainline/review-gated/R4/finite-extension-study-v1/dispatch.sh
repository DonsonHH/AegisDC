#!/bin/bash
# Invoke the accepted submitter exactly once. This wrapper only records its exit.
set -eu
set -C
base=/share/home/renly/renly-patrol-rsi/mainline/R4-finite-extension-20261118
auth=$base/execution-authorization-01
printf '%s\n' "$$" > "$auth/dispatcher-pid"
rc=0
/share/home/renly/miniconda3/bin/python -I -B "$base/source-24cc268d/scripts/finite_extension/submit.py" \
  "$base/review-01/output/execution-manifest.json" fa5478798a47d9b37c05e25775337e59f4ac0e2425d495e393852f9dd28164d0 \
  --approval "$auth/approved.json" --approval-sha 871489cf0165631ae1b9ccf54df9cba3b0ca93131cc90b5799c745487362737c || rc=$?
printf '%s\n' "$rc" > "$auth/dispatcher-exit"
exit "$rc"
