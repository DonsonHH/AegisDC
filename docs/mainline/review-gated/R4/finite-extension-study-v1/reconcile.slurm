#!/bin/bash
#SBATCH --job-name=ext-read-01
#SBATCH --partition=cu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:02:00
#SBATCH --no-requeue
#SBATCH --output=/share/home/renly/renly-patrol-rsi/mainline/R4-finite-extension-20261118/saved-study-audit-01/stdout.log
#SBATCH --error=/share/home/renly/renly-patrol-rsi/mainline/R4-finite-extension-20261118/saved-study-audit-01/stderr.log
set -uC
export OMP_NUM_THREADS=1
cd /share/home/renly/renly-patrol-rsi/mainline/R4-finite-extension-20261118/saved-study-audit-01/source || exit 1
echo '3d3424697d8a296374bc66eb416cec3b3469fca90c8987967c85e4d229ca2a9b  source-identity.json' | sha256sum --check --status || exit 1
hostname
srun /share/home/renly/miniconda3/bin/python -I -B /share/home/renly/renly-patrol-rsi/mainline/R4-finite-extension-20261118/saved-study-audit-01/source/audit_study.py --output /share/home/renly/renly-patrol-rsi/mainline/R4-finite-extension-20261118/saved-study-audit-01/output --tool-identity /share/home/renly/renly-patrol-rsi/mainline/R4-finite-extension-20261118/saved-study-audit-01/source/source-identity.json
rc=$?
printf '%s\n' "$rc" > /share/home/renly/renly-patrol-rsi/mainline/R4-finite-extension-20261118/saved-study-audit-01/exit-status
exit "$rc"
