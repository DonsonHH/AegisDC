#!/bin/bash
#SBATCH --job-name=ordinary-v2-qual
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --no-requeue
set -eu
umask 077
activity=$1
identity=$2
cd "$activity/source"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
unset PYTHONPATH
mkdir "$activity/job-start"
printf '%s\n' "$SLURM_JOB_ID" > "$activity/job-start/id"
hostname > "$activity/job-start/host"
scontrol show job -o "$SLURM_JOB_ID" > "$activity/job-start/allocation"
exit_status=0
/share/home/renly/miniconda3/bin/python -B -s scripts/qualify_london_ordinary_v2.py \
    --manifest "$activity/execution-source.json" --manifest-sha "$identity" \
    --output "$activity/output" || exit_status=$?
printf '%d\n' "$exit_status" > "$activity/job-start/exit"
exit "$exit_status"
