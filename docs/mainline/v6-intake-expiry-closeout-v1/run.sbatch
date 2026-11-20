#!/bin/bash
#SBATCH --partition=cu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:03:00
#SBATCH --job-name=v6-expiry
set -euo pipefail
umask 077
cd "$SLURM_SUBMIT_DIR/source"
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src"
digest=$1
shift
hostname > "$SLURM_SUBMIT_DIR/compute-node"
exec /share/home/renly/miniconda3/bin/python -B scripts/qualify_v6_intake_expiry.py \
    --launch "$SLURM_SUBMIT_DIR/launch.json" --launch-sha "$digest" --output "$SLURM_SUBMIT_DIR/output" "$@"
