#!/bin/bash
set -euo pipefail
umask 077
cd "$1"
unset PYTHONPATH PYTHONHOME PYTHONSTARTUP HTTP_PROXY HTTPS_PROXY ALL_PROXY
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONHASHSEED=0
exec /share/home/renly/miniconda3/bin/python -I -B scripts/v6_research_launch.py worker --manifest-sha "$2" --case "$3"
