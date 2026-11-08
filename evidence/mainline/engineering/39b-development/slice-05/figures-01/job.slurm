#!/usr/bin/env bash
#SBATCH --job-name=aegis39b-figures
#SBATCH --partition=cu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:03:00
#SBATCH --no-requeue
#SBATCH --output=/share/home/renly/renly-patrol-rsi/mainline/39b-figures/action01/render-%j.out
#SBATCH --error=/share/home/renly/renly-patrol-rsi/mainline/39b-figures/action01/render-%j.err
set -euo pipefail
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1
cd /share/home/renly/renly-patrol-rsi/mainline/39b-figures/action01
srun /share/home/renly/miniconda3/envs/diffv2ir/bin/python -B -X utf8 render_problem_action_evidence.py --manifest manifest.json --output figures
