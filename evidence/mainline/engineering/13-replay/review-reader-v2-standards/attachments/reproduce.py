"""Pure Temp-copy reproducer for the cf9 balance timestamp authority gap; no simulation."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, required=True)
args = parser.parse_args()
root = args.root.resolve()
source = 'cf9b33900d8f349b9a8145c042bbffe03503c858'
subprocess.run(['git', 'diff', '--exit-code', source, '--', 'src'], cwd=root, check=True, stdout=subprocess.DEVNULL)
sys.dont_write_bytecode = True
sys.path.insert(0, str(root / 'src'))
from aegis_dc.replay import read_attempt
original = root / 'evidence/mainline/engineering/13-replay/capture-04/causal-baseline'
before = {p.relative_to(original).as_posix(): sha256(p.read_bytes()).hexdigest() for p in original.rglob('*') if p.is_file()}
output = Path(tempfile.mkdtemp(prefix='aegisdc-balance-time-reproduction-'))
copy = output / 'origin'
shutil.copytree(original, copy)
path = copy / 'trajectory/balances.jsonl'
rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
rows[0]['start_s'] = 'not-a-time'
path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows), encoding='utf-8', newline='\n')
run_path = copy / 'trajectory/run.json'
run = json.loads(run_path.read_text(encoding='utf-8'))
run['artifacts']['balances.jsonl']['sha256'] = sha256(path.read_bytes()).hexdigest()
run_path.write_text(json.dumps(run, allow_nan=False) + '\n', encoding='utf-8', newline='\n')
record_path = copy / 'attempt.json'
record = json.loads(record_path.read_text(encoding='utf-8'))
for name in ('trajectory/balances.jsonl', 'trajectory/run.json'):
    record['artifacts'][name] = sha256((copy / name).read_bytes()).hexdigest()
record_path.write_text(json.dumps(record, allow_nan=False) + '\n', encoding='utf-8', newline='\n')
try:
    result = read_attempt(copy)
    observed = {'outcome': 'ACCEPTED', 'status': result['record']['status'], 'balance_start_s': result['run']['balances'][0]['start_s']}
except ValueError as error:
    observed = {'outcome': 'REFUSED', 'error': str(error)}
assert before == {p.relative_to(original).as_posix(): sha256(p.read_bytes()).hexdigest() for p in original.rglob('*') if p.is_file()}
print(json.dumps({'source_pin': source, 'output': str(output), 'original_preserved': True, 'new_physics_runs': 0, 'observed': observed}, indent=2))
