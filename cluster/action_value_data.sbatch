#!/usr/bin/env bash
#SBATCH --job-name=rsi-action-data-fit
#SBATCH --partition=cu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=00:15:00
set -euo pipefail
source_root="$1"
run_root="$2"
mode="$3"
module purge
module load python/3.11-pytorch2.6-cu124
export PYTHONPATH="$source_root/src:$source_root/scripts"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
cd "$source_root"
task_python=/share/home/renly/renly-patrol-rsi/runs/20261026-m1/model-env/bin/python
if [[ "$mode" = build ]]; then
  "$task_python" scripts/build_action_value.py --root "$run_root"
else
  "$task_python" scripts/fit_action_value.py --root "$run_root" --fold "$mode"
fi
