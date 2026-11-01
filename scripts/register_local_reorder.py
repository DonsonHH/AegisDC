"""Fresh seed registration metadata only, after both development rounds finish."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time


def main():
    p=argparse.ArgumentParser();p.add_argument('--receipts',type=Path,required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];area=a.receipts.resolve()
    names=('baselines-complete.json','S-complete.json','Q1-complete.json','Q2-complete.json')
    receipts={name:json.loads((area/name).read_bytes()) for name in names}
    if any(name not in receipts for name in names):raise ValueError('Development must be complete')
    if any(len(receipts[name]['selected']['rows'])!=6 for name in names[1:]):raise ValueError('Complete selected development cohort required')
    occupied=set();sources=[]
    def extract(value,seed_field=False):
        if type(value) is int and seed_field:occupied.add(value)
        elif isinstance(value,list):
            for child in value:extract(child,seed_field)
        elif isinstance(value,dict):
            for key,child in value.items():extract(child,seed_field or 'seed' in key.lower())
    for path in sorted((repo/'research').glob('*/*.json')):
        extract(json.loads(path.read_bytes()))
        sources.append({'path':path.relative_to(repo).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    result={'unix':time.time(),'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        'seed_groups':sorted(occupied),'checked_top_level_metadata':sources,
        'development_receipt_sha256':{name:hashlib.sha256((area/name).read_bytes()).hexdigest() for name in names},
        'raw_old_final_files_opened':False,'new_confirmation_generated':False,
        'rule':'After development; first two unused seed groups from43000; phase520 fixed before any result.'}
    with (area/'registration-at-freeze.json').open('x',encoding='utf8',newline='\n') as f:
        json.dump(result,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
    print(json.dumps({'metadata_files':len(sources),'occupied_seed_groups':len(occupied),'new_physical_processes_generated':0}))


if __name__=='__main__':main()
