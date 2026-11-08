#!/usr/bin/env bash
#SBATCH --job-name=aegis39a-saved
#SBATCH --partition=cu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:03:00
#SBATCH --output=/share/home/renly/renly-patrol-rsi/mainline/39a-saved-audit-01/audit-%j.out
#SBATCH --error=/share/home/renly/renly-patrol-rsi/mainline/39a-saved-audit-01/audit-%j.err
set -euo pipefail
export OMP_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1
cd /share/home/renly/renly-patrol-rsi/mainline/39a-saved-audit-01
srun /share/home/renly/miniconda3/bin/python -B -X utf8 audit_integrated_scope.py --manifest manifest.json --output results
