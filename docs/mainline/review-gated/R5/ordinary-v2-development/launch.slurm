#!/bin/bash
#SBATCH --job-name=r5-ordinary-v2
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:15:00
#SBATCH --no-requeue
set -eu
umask 077
stage=$1
source_dir="$stage/source"
delivery="docs/mainline/review-gated/R5/ordinary-v2-development"
manifest="docs/mainline/review-gated/R5/ordinary-v2-qualification/research-manifest-review.json"
grant="$delivery/approval.json"
interpreter=/share/home/renly/miniconda3/bin/python
cd "$source_dir"
mkdir "$stage/job-start"
printf '%s\n' "$SLURM_JOB_ID" > "$stage/job-start/id"
hostname > "$stage/job-start/host"
scontrol show job -o "$SLURM_JOB_ID" > "$stage/job-start/allocation"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
unset PYTHONPATH
entry_exit=0
"$interpreter" -B -s "$delivery/preflight.py" "$source_dir" "$stage" || entry_exit=$?
if test "$entry_exit" -eq 0; then
    date --iso-8601=ns > "$stage/job-start/entry-started"
    "$interpreter" -B -s scripts/run_london_ordinary_v2.py \
        --manifest "$manifest" --manifest-sha '45b29f25522908e1aa14ffa2077a355f8c0d70bdaecfdfa3d680938bbd445e5b' \
        --approval "$grant" --approval-sha '9bf3c28e0a398e4b276b49df1ceafc46a669ea743c8a604196a508e6958912c9' || entry_exit=$?
fi
printf '%d\n' "$entry_exit" > "$stage/job-start/entry-exit"
export_exit=0
"$interpreter" -B -s "$delivery/export_results.py" "$source_dir" "$stage" "$entry_exit" || export_exit=$?
printf '%d\n' "$export_exit" > "$stage/job-start/export-exit"
if test "$entry_exit" -ne 0; then exit "$entry_exit"; fi
exit "$export_exit"
