#!/bin/bash
#SBATCH --partition=cu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:05:00
set -euo pipefail
umask 077
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
base=/share/home/renly/renly-patrol-rsi/mainline/T1-margin-20261121-v1
cd "$base/source"
exec /share/home/renly/miniconda3/bin/python -B docs/mainline/t1-research-margin-v1/diagnose.py "$1" "$base/attempts/$2"
