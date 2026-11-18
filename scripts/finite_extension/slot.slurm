#!/bin/bash
# Submitted by submit.py with explicit allocation, unique stdout and stderr.
set -eu
export OMP_NUM_THREADS=1
exec /share/home/renly/miniconda3/bin/python -I -B -u "$1/scripts/finite_extension/launch.py" "$@"
