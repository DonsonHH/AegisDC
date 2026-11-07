"""Preserve both failed pre-capture reviews without invoking the facility."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'evidence/mainline/engineering/28-negative-controls/pre-capture-review-01'
FILES = {'declaration.json','members.json','originals.zip','receipt.json'}
SOURCE = '105a1cf53e72abccb047e2f1a5a1cf141d8980ae'


def digest(raw):
    return sha256(raw).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    with path.open('x',encoding='utf-8',newline='\n') as f:
        f.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def verify():
    assert {p.name for p in PACKAGE.iterdir() if p.is_file()} == FILES
    declaration,receipt,members = (read(PACKAGE/name) for name in ('declaration.json','receipt.json','members.json'))
    assert set(receipt['artifacts']) == set(declaration['artifacts']) == FILES-{'receipt.json'}
    assert receipt['authoring_tool_sha256'] == digest(Path(__file__).read_bytes())
    for name,sha in receipt['artifacts'].items():
        assert digest((PACKAGE/name).read_bytes()) == sha
    with zipfile.ZipFile(PACKAGE/'originals.zip') as archive:
        assert len(archive.namelist()) == len(set(archive.namelist())) and set(archive.namelist()) == set(members) == set(declaration['members'])
        for name,identity in members.items():
            raw=archive.read(name)
            assert digest(raw)==identity['sha256'] and len(raw)==identity['bytes']
        for axis,seal in declaration['seals'].items():
            manifest=json.loads(archive.read(f'{axis}/{seal}'))
            report=json.loads(archive.read(f'{axis}/review.json'))
            assert report['axis']==axis and report['source']==SOURCE and report['unresolved']
            for name,identity in manifest['artifacts'].items():
                assert members[f'{axis}/{name}']==identity
    return dict(status='PASS_PRESERVED_FAILED_REVIEWS',source=SOURCE,members=len(members),new_project_calls=0)


def seal(review_root):
    assert not PACKAGE.exists()
    selected={}
    seals={}
    for axis in ('Spec','Standards'):
        folder=review_root/f'28-frozen-{axis.lower()}-review-01'
        seal=next(name for name in ('manifest.json','delivery-manifest.json') if (folder/name).is_file())
        manifest=read(folder/seal)
        files={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.pyc','.pyo'}}
        assert files==set(manifest['artifacts'])|{seal}
        for name,identity in manifest['artifacts'].items():
            raw=(folder/name).read_bytes()
            assert digest(raw)==identity['sha256'] and len(raw)==identity['bytes']
        selected.update({f'{axis}/{name}':folder/name for name in files})
        seals[axis]=seal
    PACKAGE.mkdir(parents=True)
    write(PACKAGE/'declaration.json',dict(artifacts=sorted(FILES-{'receipt.json'}),terminal='receipt.json',
        members=sorted(selected),seals=seals,excluded_runtime_caches=['__pycache__','*.pyc','*.pyo'],
        classification='FAILED_SOURCE_REVIEWS_BEFORE_ANY_CASE_EXECUTION'))
    members={}
    with zipfile.ZipFile(PACKAGE/'originals.zip','x',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,path in sorted(selected.items()):
            raw=path.read_bytes()
            archive.writestr(name,raw)
            members[name]=dict(sha256=digest(raw),bytes=len(raw))
    write(PACKAGE/'members.json',members)
    write(PACKAGE/'receipt.json',dict(status='PRESERVED_NOT_A_PASS',source=SOURCE,new_physical_calls=0,
        authoring_tool_sha256=digest(Path(__file__).read_bytes()),
        artifacts={name:digest((PACKAGE/name).read_bytes()) for name in FILES-{'receipt.json'}}))
    return verify()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('seal','verify'))
    p.add_argument('--review-root',type=Path)
    args=p.parse_args()
    print(json.dumps(seal(args.review_root) if args.mode=='seal' else verify()))
