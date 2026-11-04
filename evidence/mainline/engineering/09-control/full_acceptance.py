"""One full repository acceptance on this worktree's actual primary runtime."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'scripts'))
from acceptance import verify
result=verify(ROOT,Path(sys.argv[1]))
print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
sys.exit(0 if result['overall']=='PASS' else 1)
