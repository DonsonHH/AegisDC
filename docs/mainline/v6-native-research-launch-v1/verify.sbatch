#!/bin/bash
#SBATCH --partition=cu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:02:00
#SBATCH --no-requeue
#SBATCH --job-name=v6-launch-verify
set -euo pipefail
umask 077
cd "$SLURM_SUBMIT_DIR/source"
unset PYTHONPATH PYTHONHOME PYTHONSTARTUP HTTP_PROXY HTTPS_PROXY ALL_PROXY
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONHASHSEED=0
hostname > "$SLURM_SUBMIT_DIR/compute-node"
exec /share/home/renly/miniconda3/bin/python -I -B docs/mainline/v6-native-research-launch-v1/qualify.py \
    --launch "$SLURM_SUBMIT_DIR/launch.json" --sha "$1" --output "$SLURM_SUBMIT_DIR/output"
