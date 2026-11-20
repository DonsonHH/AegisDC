"""Public verification subprocess: copy designated historical files or return the frozen software fault."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

def main():
    original,destination,mode,pin=Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3],sys.argv[4]
    if mode=='no-return':return 7
    if mode not in ('copy','missing-count','divergent-H','cut-H5'):raise ValueError('Unknown synthetic return')
    raw=(original/'run.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('Original file pin differs')
    destination.mkdir()
    run=json.loads(raw)
    shutil.copyfile(original/'scenario.json',destination/'scenario.json')
    for name,field in [('private-state.jsonl','time_s'),('balances.jsonl','end_s')]:
        if mode!='cut-H5':
            shutil.copyfile(original/name,destination/name)
        else:
            with (original/name).open('rb') as source,(destination/name).open('xb') as out:
                h=hashlib.sha256();count=0
                for line in source:
                    if json.loads(line)[field]>5:break
                    out.write(line);h.update(line);count+=1
            run['artifacts'][name]=dict(sha256=h.hexdigest(),records=count)
    if mode=='missing-count':
        del run['policy_public_decisions']
    elif mode=='divergent-H':
        run['policy_public_decisions'][0]['choice']['reason']='FIXTURE_DIVERGENT_HISTORY'
    (destination/'run.json').write_bytes(raw if mode=='copy' else (json.dumps(run,ensure_ascii=False,allow_nan=False)+'\n').encode())
    return 0

if __name__=='__main__':sys.exit(main())
