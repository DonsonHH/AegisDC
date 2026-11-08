#!/usr/bin/env bash
#SBATCH --job-name=aegis39b-fresh
#SBATCH --partition=cu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --no-requeue
#SBATCH --output=/share/home/renly/renly-patrol-rsi/mainline/39b-fresh-delivery-02/verify-%j.out
#SBATCH --error=/share/home/renly/renly-patrol-rsi/mainline/39b-fresh-delivery-02/verify-%j.err
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1
cd /share/home/renly/renly-patrol-rsi/mainline/39b-fresh-delivery-02/repository
srun /share/home/renly/renly-patrol-rsi/environments/aegisdc-verify-20261109/bin/python -B -X utf8 scripts/verify_39b_delivery.py --delivery-commit dfa7ab521bdfa4e7f06554c836a16417759eab26 --output /share/home/renly/renly-patrol-rsi/mainline/39b-fresh-delivery-02/output
