"""Seal completed or failed ticket 28 launch bytes without reexecuting the project."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess

FILES = ('attempt.json','process.json','terminal.json','stdout.txt','stderr.txt','launcher.py')
PACKAGE = 'evidence/mainline/engineering/28-negative-controls'


def read(path):
    return json.loads(path.read_bytes())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def seal(root, launcher, suffix):
    require(len(suffix)==2 and suffix.isdigit(), 'Use a two-digit capture identifier')
    pending = root / f'.work/28-frozen-launch-20261107-{suffix}'
    folder = root / PACKAGE / f'capture-20261107-{suffix}'
    output = root / PACKAGE / f'capture-{suffix}-launch'
    require(not output.exists(), 'Launch originals already sealed')
    attempt, process, terminal = (read(pending / name) for name in FILES[:3])
    receipt = read(folder / 'receipt.json')
    source = subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    require(attempt['status']=='STARTED' and
            attempt['source']==process['source']==terminal['source']==receipt['source']==source,
            'Capture or exact launch source differs')
    require(terminal['receipt_exists'] and receipt['source_guard'], 'Author execution source was not preserved')
    require((terminal['status'], terminal['returncode']==0, receipt['status']) in
            {('COMPLETED',True,'PASS'),('FAILED',False,'FAIL')}, 'Launch terminal and case receipt differ')
    require(attempt['launcher_sha256']==digest(launcher)
            and all(terminal[f'{name}_sha256']==digest(pending/f'{name}.txt') for name in ('stdout','stderr')),
            'Original launcher or streams changed')
    artifacts = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()
                 and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo')}
    require(artifacts==set(receipt['artifacts'])|{'receipt.json'}
            and all(digest(folder/name)==sha for name,sha in receipt['artifacts'].items()),
            'Captured files or receipt set changed')
    output.mkdir()
    for name in FILES:
        shutil.copyfile(launcher if name=='launcher.py' else pending/name,output/name)
    record = dict(artifacts=list(FILES),terminal='manifest.json',
                  classification='EXACT_CAPTURE_LAUNCH_ORIGINALS',source=source,
                  identities={name:digest(output/name) for name in FILES})
    with (output/'manifest.json').open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    attrs = root/PACKAGE/'.gitattributes'
    old = attrs.read_bytes()
    entries = ''.join(f'capture-{suffix}-launch/{name}.txt -text whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol\n'
                      for name in ('stdout','stderr')).encode()
    require(all(line not in old for line in entries.splitlines()), 'Native stream rule already exists')
    with attrs.open('ab') as stream:
        stream.write(entries)
    return dict(status='PASS_ORIGINALS_SEALED', author_terminal=receipt['status'], source=source,
                capture_artifacts=len(artifacts),launch_artifacts=len(FILES)+1, counters=receipt['counters'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--launcher',type=Path,required=True)
    p.add_argument('--id',required=True)
    args=p.parse_args()
    print(json.dumps(seal(args.root,args.launcher,args.id),ensure_ascii=False))
