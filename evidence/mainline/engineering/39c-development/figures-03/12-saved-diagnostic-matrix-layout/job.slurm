#!/usr/bin/env bash
#SBATCH --job-name=aegis39c-run-qualification
#SBATCH --partition=cu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --no-requeue
#SBATCH --output=/share/home/renly/renly-patrol-rsi/mainline/39c-development/12-saved-diagnostic-matrix-layout/slice-%j.out
#SBATCH --error=/share/home/renly/renly-patrol-rsi/mainline/39c-development/12-saved-diagnostic-matrix-layout/slice-%j.err
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1
unset PYTHONOPTIMIZE
cd /share/home/renly/renly-patrol-rsi/mainline/39c-development/12-saved-diagnostic-matrix-layout
srun /share/home/renly/miniconda3/envs/diffv2ir/bin/python -B -X utf8 scripts/plot_business_diagnostic_endpoints.py --manifest manifest.json --output results --matrix-only
