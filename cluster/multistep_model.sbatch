#!/usr/bin/env bash
#SBATCH --job-name=rsi-multistep-qwen
#SBATCH --partition=4gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:V100S:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=00:10:00
set -euo pipefail
source_root="$1"
run_root="$2"
module purge
module load python/3.11-pytorch2.6-cu124
export PYTHONPATH="$source_root/src:$source_root/scripts"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
cd "$source_root"
/share/home/renly/renly-patrol-rsi/runs/20261026-m1/model-env/bin/python scripts/run_multistep.py --root "$run_root" --mode model
