#!/bin/bash
set -euo pipefail
umask 077
test "$#" -eq 2
name="$1"; revision="$2"
[[ "$revision" =~ ^[a-f0-9]{40}$ ]]
cd "$SLURM_SUBMIT_DIR"
program="$PWD/releases/$revision/docs/mainline/t8-rsi-wait-repair/stage1b/scoring/study.py"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
unset PYTHONPATH
export XDG_RUNTIME_DIR
XDG_RUNTIME_DIR=$(mktemp -d "${TMPDIR:-/tmp}/t8-ns-${SLURM_JOB_ID}-XXXXXXXX")
exec /usr/bin/podman --root "$XDG_RUNTIME_DIR/store" --runroot "$XDG_RUNTIME_DIR/run" \
    --storage-driver=vfs --events-backend=file unshare /share/home/renly/miniconda3/envs/sd/bin/python \
    -B "$program" --job "$name" --revision "$revision"
