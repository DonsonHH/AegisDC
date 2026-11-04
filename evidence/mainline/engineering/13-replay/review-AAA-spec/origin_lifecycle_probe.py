"""Reproduce interrupted/malformed replay-origin handling; no plant execution."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from hashlib import sha256
repo=Path('C:/Users/Donson/Documents/ChatGPT/Renly/.work/worktrees/full-site-13')
freeze='aaa4d8cba3738e47e700c2134000a72bd2390cc0'
p=repo/'src/aegis_dc/replay.py'
expected=sha256(subprocess.check_output(['git','cat-file','blob',freeze+':src/aegis_dc/replay.py'],cwd=repo)).hexdigest()
assert sha256(p.read_bytes()).hexdigest()==expected
sys.path.insert(0,str(repo/'src'))
from aegis_dc.replay import read_attempt,replay_attempt
with tempfile.TemporaryDirectory(prefix='aegisdc13-origin-repro-') as temporary:
    base=Path(temporary)
    declaration=(repo/'evidence/mainline/engineering/13-replay/capture-02/causal-baseline/declaration.json').read_bytes()
    incomplete=base/'declaration-only';incomplete.mkdir();(incomplete/'declaration.json').write_bytes(declaration)
    try:print('interrupted-declaration',read_attempt(incomplete)['record']['status'])
    except Exception as e:print('interrupted-declaration',type(e).__name__,str(e))
    invalid=base/'bad-row';invalid.mkdir();(invalid/'declaration.json').write_bytes(declaration)
    (invalid/'lifecycle.jsonl').write_bytes(b'42\n')
    output=base/'new-refusal'
    try:print('bad-row-replay',replay_attempt(invalid,output)['status'])
    except Exception as e:print('bad-row-replay',type(e).__name__,str(e))
    print('failed-terminal-created',(output/'attempt.json').exists())
assert sha256(p.read_bytes()).hexdigest()==expected
