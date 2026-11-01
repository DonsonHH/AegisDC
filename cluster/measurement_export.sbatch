#!/usr/bin/env bash
#SBATCH --job-name=rsi-measurement-export
#SBATCH --partition=cu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=00:05:00
set -euo pipefail
source_root="$1"
run_root="$2"
annotator="$3"
module purge
module load python/3.11-pytorch2.6-cu124
export PYTHONPATH="$source_root/src:$source_root/scripts"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
cd "$source_root"
/share/home/renly/renly-patrol-rsi/runs/20261026-m1/model-env/bin/python "$annotator" --source "$source_root" --root "$run_root"
python3 - "$run_root" <<'PY'
import pathlib,hashlib,json,sys
root=pathlib.Path(sys.argv[1]);files={}
for path in sorted(root.rglob('*')):
    name=path.relative_to(root).as_posix()
    if not path.is_file() or name.startswith('code-v') or name.startswith('jobs/export-') or name=='closed-results-SHA256.json':continue
    files[name]={'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
with (root/'closed-results-SHA256.json').open('x') as f:json.dump({'scope':'Current closed experiment only; source snapshots separate; old six input processes referenced by prior archive','files':files},f,indent=2)
print('CLOSED_FILES',len(files),flush=True)
PY
archive="${run_root}-evidence-v1.tar.gz"
test ! -e "$archive"
tar -czf "$archive" --exclude='./code-v*' --exclude='./jobs/export-*' -C "$run_root" .
sha256sum "$archive"
stat -c '%s' "$archive"
