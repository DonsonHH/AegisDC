#!/usr/bin/env bash
#SBATCH --job-name=aegis39b-rootfull
#SBATCH --partition=cu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --no-requeue
#SBATCH --output=/share/home/renly/renly-patrol-rsi/mainline/39b-root-acceptance-20261109/root-%j.out
#SBATCH --error=/share/home/renly/renly-patrol-rsi/mainline/39b-root-acceptance-20261109/root-%j.err
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
export MKL_NUM_THREADS=2
unset AEGIS_ENGINEERING_RESULT_DIR
cd /share/home/renly/renly-patrol-rsi/mainline/39b-root-acceptance-20261109/repository-02
export PYTHONPATH="$PWD/src"
srun /share/home/renly/renly-patrol-rsi/environments/aegisdc-verify-20261109/bin/python -B -X utf8 scripts/run_remote_root_acceptance.py --source 04ed91bea1c2ff7d05181de2bf5a1a5079f5d7c2 --output runs/39b-root-regression-01
