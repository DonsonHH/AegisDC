"""Keep native scontrol trailing Power field spaces on three exact log paths."""
from pathlib import Path
import hashlib
import json
import subprocess

root=Path.cwd();packet=root/'evidence/mainline/engineering/39b-root-acceptance'
folder=packet/'native-format';folder.mkdir(exist_ok=False)
result=subprocess.run(['git','diff','--cached','--check'],capture_output=True)
assert result.returncode==2
with (folder/'check-reproduction-01.log').open('xb') as f:f.write(result.stdout);f.write(result.stderr)
files={}
for name in ['stage-legacy-09.log','stage-submit-root-acceptance-02.log','submit-root-acceptance-01.log']:
 p=packet/'remote-preparation'/name;raw=p.read_bytes()
 trailing=[line for line in raw.splitlines() if line.endswith((b' ',b'\t'))]
 assert len(trailing)==1 and trailing[0].endswith(b'Power= ')
 files[p.relative_to(root).as_posix()]={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'native_trailing_power_lines':1}
with (folder/'classification.json').open('x',encoding='utf-8',newline='\n') as f:
 json.dump({'classification':'EXACT_NATIVE_SLURM_FORMAT_NOT_HASH_EXCEPTION','initial_failure':'Initial cached diff check refused commit for three native scontrol Power= trailing spaces; its output was in tool history. The stored check is an explicitly labelled reproduction before attributes correction.','files':files,'disposition':'Preserve exact original bytes; disable blank-at-eol only on these three native log paths. Source/tests style and every SHA/Git byte check remain enforced.'},f,indent=2);f.write('\n')
print('Classified three original scontrol log lines without rewriting their bytes.')
