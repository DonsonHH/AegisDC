#!/usr/bin/env bash
#SBATCH --job-name=aegis39c-run-red
#SBATCH --partition=cu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --no-requeue
#SBATCH --output=/share/home/renly/renly-patrol-rsi/mainline/39c-development/10-saved-verifier-mode-red/slice-%j.out
#SBATCH --error=/share/home/renly/renly-patrol-rsi/mainline/39c-development/10-saved-verifier-mode-red/slice-%j.err
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1
unset PYTHONOPTIMIZE
export AEGIS_SAVED_DIAGNOSTIC_MODE_PROTOCOL=39c-mode-07
cd /share/home/renly/renly-patrol-rsi/mainline/39c-development/10-saved-verifier-mode-red
srun /share/home/renly/renly-patrol-rsi/environments/aegisdc-verify-20261109/bin/python -B -X utf8 scripts/run_engineering_slice.py --manifest manifest.json --output results
