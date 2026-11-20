#!/bin/bash
set -euo pipefail
umask 077
activity=$1
export_dir=$2
phase=$3
release_sha=$4
shift 4
cd "$activity/$export_dir"
export PYTHONPATH="$PWD/src"
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
interpreter=/share/home/renly/miniconda3/bin/python
echo "5b2187174e57eb543b1800d101a5f115afc24e52c1519b6f09e4759ca4d6abe6  $interpreter" | sha256sum -c -
exec "$interpreter" -B scripts/qualify_v6_joint.py "$activity" "$phase" "$release_sha" "$@"
