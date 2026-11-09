#!/usr/bin/env bash
#SBATCH --job-name=aegis39c-saved-figures
#SBATCH --partition=cu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --no-requeue
#SBATCH --output=/share/home/renly/renly-patrol-rsi/mainline/39c-development/05-saved-closure-figures-01/render-%j.out
#SBATCH --error=/share/home/renly/renly-patrol-rsi/mainline/39c-development/05-saved-closure-figures-01/render-%j.err
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1
cd /share/home/renly/renly-patrol-rsi/mainline/39c-development/05-saved-closure-figures-01
srun /share/home/renly/miniconda3/envs/diffv2ir/bin/python -B -X utf8 scripts/plot_business_closure_endpoints.py --manifest manifest.json --source-commit 2f29119e5eefe3c5eee3e57aab1734f1fc08b1c0 --output figures
