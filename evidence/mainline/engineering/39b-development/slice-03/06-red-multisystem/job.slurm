#!/usr/bin/env bash
#SBATCH --job-name=aegis39b-run-red
#SBATCH --partition=cu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:03:00
#SBATCH --no-requeue
#SBATCH --output=/share/home/renly/renly-patrol-rsi/mainline/39b-development/06-red-multisystem/slice-%j.out
#SBATCH --error=/share/home/renly/renly-patrol-rsi/mainline/39b-development/06-red-multisystem/slice-%j.err
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1
cd /share/home/renly/renly-patrol-rsi/mainline/39b-development/06-red-multisystem
srun /share/home/renly/miniconda3/bin/python -B -X utf8 scripts/run_engineering_slice.py --manifest manifest.json --output results
