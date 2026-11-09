#!/usr/bin/env bash
#SBATCH --job-name=aegis39c-run-green
#SBATCH --partition=cu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --no-requeue
#SBATCH --output=/share/home/renly/renly-patrol-rsi/mainline/39c-development/08-public-record-selection-green/slice-%j.out
#SBATCH --error=/share/home/renly/renly-patrol-rsi/mainline/39c-development/08-public-record-selection-green/slice-%j.err
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1
cd /share/home/renly/renly-patrol-rsi/mainline/39c-development/08-public-record-selection-green
srun /share/home/renly/renly-patrol-rsi/environments/aegisdc-verify-20261109/bin/python -B -X utf8 scripts/run_engineering_slice.py --manifest manifest.json --output results
