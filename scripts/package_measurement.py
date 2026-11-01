"""Small immutable source snapshots with a separately bound execution kernel."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('version');a=p.parse_args()
    if not a.version.startswith('v') or not a.version[1:].isdigit():raise ValueError('Version')
    root=Path(__file__).resolve().parents[1];stage=root/'research/2026-11-01-measurement-effect'
    dest=root/'.work/measurement'/('code-'+a.version);dest.mkdir(parents=True,exist_ok=False)
    files=[*sorted((root/'src').rglob('*.py')),*sorted((root/'tests').glob('test_measurement_*.py')),
        *[root/'tests'/v for v in ('test_multistep_safety.py','test_multistep_workflow.py','test_multistep_proposal.py')],
        *sorted((root/'scripts').glob('*measurement*.py')),
        *[root/'scripts'/v for v in ('run_multistep.py','run_m12d_paired.py','audit_m11.py','audit_m111.py')],
        *sorted((root/'cluster').glob('measurement_*.sbatch')),
        stage/'protocol.json',stage/'historical-identities.json',
        root/'research/2026-10-28-m111-coverage/frozen_estimator.json']
    hashes={}
    for path in files:
        name=path.relative_to(root).as_posix();out=dest/name;out.parent.mkdir(parents=True,exist_ok=True)
        data=path.read_bytes().replace(b'\r\n',b'\n') if path.suffix=='.sbatch' else path.read_bytes()
        out.write_bytes(data);hashes[name]=sha(out)
    kernel={k:v for k,v in hashes.items() if k.startswith(('src/','tests/')) or k in (
        'scripts/run_measurement.py','scripts/run_multistep.py','scripts/run_m12d_paired.py','scripts/audit_m11.py','scripts/audit_m111.py')
        or k.endswith(('protocol.json','historical-identities.json','frozen_estimator.json'))}
    signature=hashlib.sha256(json.dumps(kernel,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    value={'files':hashes,'execution_files':kernel,'execution_signature':signature,
        'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(), 'version':a.version}
    (dest/'snapshot-manifest.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf8',newline='\n')
    (stage/'source').mkdir(exist_ok=True)
    archive=stage/'source'/('code-'+a.version+'.tar.gz')
    with archive.open('xb') as stream:
        with tarfile.open(fileobj=stream,mode='w:gz') as t:
            for f in sorted(dest.rglob('*')):
                if f.is_file():t.add(f,arcname=f.relative_to(dest).as_posix(),recursive=False)
    receipt={'archive_sha256':sha(archive),'execution_signature':signature,'source_manifest_sha256':sha(dest/'snapshot-manifest.json'),
        'files':len(hashes),'archive_bytes':archive.stat().st_size}
    (stage/'source'/('receipt-'+a.version+'.json')).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(receipt))


if __name__=='__main__':main()
