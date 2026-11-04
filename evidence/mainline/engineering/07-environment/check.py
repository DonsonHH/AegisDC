"""Record each fresh engineering check and its exact source/input identity."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[4]


def main():
    label, *arguments = sys.argv[1:]
    target = Path(__file__).parent / label
    target.mkdir(exist_ok=False)
    paths = list((ROOT / 'src/aegis_dc').glob('*.py'))
    paths += list((ROOT / 'tests').glob('test_full_facility*.py'))
    paths += list((ROOT / 'configs').glob('full-facility-mainline*.json'))
    paths += [ROOT / 'configs/materials/reference-r134a-saturation.json']
    hashes = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in sorted(paths)}
    environment = dict(os.environ, PYTHONPATH=str(ROOT / 'src'), PYTHONIOENCODING='utf-8')
    command = [sys.executable, *arguments]
    result = subprocess.run(command, cwd=ROOT, env=environment, text=True,
                            encoding='utf-8', errors='replace', capture_output=True)
    (target / 'stdout.txt').write_text(result.stdout, encoding='utf-8', newline='\n')
    (target / 'stderr.txt').write_text(result.stderr, encoding='utf-8', newline='\n')
    receipt = {'classification': 'ENGINEERING_CHECK_ONLY', 'research_trials': 0,
               'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
               'command': command, 'cwd': str(ROOT), 'PYTHONPATH': environment['PYTHONPATH'],
               'source_and_input_sha256': hashes, 'exit_code': result.returncode}
    (target / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'directory': str(target), 'exit_code': result.returncode}))
    print(result.stdout)
    print(result.stderr)
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
