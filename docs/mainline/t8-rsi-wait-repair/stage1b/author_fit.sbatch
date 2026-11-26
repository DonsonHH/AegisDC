#!/bin/bash
#SBATCH --job-name=t8-fit-input
#SBATCH --partition=cu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:04:00
#SBATCH --no-requeue
#SBATCH --export=NONE
set -euo pipefail
umask 077
cd "$SLURM_SUBMIT_DIR"
test "$#" -eq 1
test ! -e panel
sha256sum --quiet -c intake-source.sha256
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
unset PYTHONPATH
exec /share/home/renly/miniconda3/bin/python -I -S -B freeze_fit_inputs.py \
  --source-bundle "$PWD/source" --output "$PWD/panel" --revision "$1"
