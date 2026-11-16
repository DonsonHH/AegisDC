#!/bin/bash
#SBATCH --job-name=r4-public-dev19
#SBATCH --partition=cu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:05:00
#SBATCH --signal=B:TERM@10
#SBATCH --output=/share/home/renly/renly-patrol-rsi/mainline/R4-public-development-20261116/attempt-01/stdout.log
#SBATCH --error=/share/home/renly/renly-patrol-rsi/mainline/R4-public-development-20261116/attempt-01/stderr.log
set -euo pipefail
cd /share/home/renly/renly-patrol-rsi/mainline/R4-public-development-20261116/attempt-01/source
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1
hostname
/share/home/renly/miniconda3/bin/python --version
srun /share/home/renly/miniconda3/bin/python scripts/run_london_public_development.py --manifest docs/mainline/review-gated/R4/public-development-v1/launch-manifest.json --manifest-sha 8cbb680d29522cb29af5165b2bb2f3f4a1aaa51f41fecc101dbfab84379c5aa0 --output /share/home/renly/renly-patrol-rsi/mainline/R4-public-development-20261116/attempt-01/result
