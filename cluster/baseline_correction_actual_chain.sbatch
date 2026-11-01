#!/usr/bin/env bash
#SBATCH --job-name=rsi-actual-child2
#SBATCH --partition=cu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=00:15:00
set -euo pipefail
module purge
module load python/3.11-pytorch2.6-cu124
export PYTHONPATH="$1/src:$1/scripts"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
cd "$1"
/share/home/renly/renly-patrol-rsi/runs/20261026-m1/model-env/bin/python scripts/run_baseline_correction_actual_chain.py --root "$2"
