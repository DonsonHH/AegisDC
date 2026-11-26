#!/bin/bash
set -euo pipefail
umask 077
test "$#" -eq 2
name="$1"; revision="$2"
[[ "$revision" =~ ^[a-f0-9]{40}$ ]]
# --chdir sets the execution root; SLURM_SUBMIT_DIR may be a release subdirectory.
test -f "$PWD/execution-recovery.json" && test -d "$PWD/releases"
program="$PWD/releases/$revision/docs/mainline/t8-rsi-wait-repair/stage1b/scoring/study.py"
test -f "$program"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
unset PYTHONPATH
exec /share/home/renly/miniconda3/envs/sd/bin/python -B "$program" --job "$name" --revision "$revision"
