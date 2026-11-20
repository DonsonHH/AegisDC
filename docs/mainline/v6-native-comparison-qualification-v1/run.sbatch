#!/bin/bash
#SBATCH --partition=cu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:05:00
#SBATCH --job-name=v6-compare-eng
set -euo pipefail
umask 077
cd "$SLURM_SUBMIT_DIR/source"
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src" PYTHONHASHSEED=0
hostname > "$SLURM_SUBMIT_DIR/compute-node"
exec /share/home/renly/miniconda3/bin/python -B docs/mainline/v6-native-comparison-qualification-v1/attempt_receipt.py \
    --launch "$SLURM_SUBMIT_DIR/launch.json" --sha "$1" --output "$SLURM_SUBMIT_DIR/output"
