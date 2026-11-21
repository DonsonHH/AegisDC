#!/bin/bash
set -euo pipefail
umask 077
cd "$1"
unset PYTHONPATH PYTHONHOME PYTHONSTARTUP
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
exec /share/home/renly/miniconda3/bin/python -I -B "$1/scripts/cold3_study_launch.py" worker --manifest-sha "$2" --case "$3"
