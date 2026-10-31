#!/usr/bin/env bash
#SBATCH --job-name=rsi-multistep-export
#SBATCH --partition=cu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:01:00
set -euo pipefail
run_root="$1"
test -s "$run_root/baselines-complete.json"
test -s "$run_root/child-complete.json"
python3 - "$run_root" <<'PY'
import hashlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1])
files = {}
for path in sorted(root.rglob('*')):
    name = path.relative_to(root).as_posix()
    if not path.is_file() or name.startswith('code-v') or name.startswith('jobs/export-') or name == 'closed-results-SHA256.json':
        continue
    files[name] = {'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
with (root / 'closed-results-SHA256.json').open('x') as f:
    json.dump({'scope': 'Closed experiment files; source archives separate, export logs and subsequent accounting excluded', 'files': files}, f, indent=2)
print('CLOSED_FILES', len(files), flush=True)
PY
archive="${run_root}-evidence-v1.tar.gz"
test ! -e "$archive"
tar -czf "$archive" --exclude='./code-v*' --exclude='./jobs/export-*' -C "$run_root" .
sha256sum "$archive"
stat -c '%s' "$archive"
