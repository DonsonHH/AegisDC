"""Verify the committed ticket 28 capture and its exact launch from a clean checkout."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

CAPTURE_ROOT = 'evidence/mainline/engineering/28-negative-controls'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_bytes())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def verify(root, delivery):
    root = root.resolve()
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=root)
    require(git('rev-parse','HEAD').decode().strip() == delivery and not git('status','--porcelain'),
            'Verification requires the requested clean committed checkout')
    require(git('rev-parse','pre-meeting-20261103^{}').decode().strip() == '076d9aa15c5bc99a5b7985f296e15543b7b0f3d7',
            'Pre-meeting source changed')
    sys.path.insert(0,str(root/'scripts'))
    from negative_control_delivery import PROTOCOL, verify as verify_author
    protocol = read(root/PROTOCOL)
    report = verify_author(protocol,delivery)
    cap = root/protocol['output']
    launch_name = 'capture-' + cap.name.rsplit('-',1)[-1] + '-launch'
    launch = root/CAPTURE_ROOT/launch_name
    manifest = read(launch/'manifest.json')
    expected = {'attempt.json','process.json','terminal.json','stdout.txt','stderr.txt','launcher.py'}
    tracked = set(git('ls-tree','-rz','--name-only',delivery,'--',launch.relative_to(root).as_posix()).decode().strip('\0').split('\0'))
    require(tracked == {(launch/name).relative_to(root).as_posix() for name in expected|{'manifest.json'}}
            and set(manifest['artifacts']) == set(manifest['identities']) == expected, 'Launch artifact set differs')
    for name in expected|{'manifest.json'}:
        path=launch/name
        require(path.read_bytes() == git('cat-file','blob',f'{delivery}:{path.relative_to(root).as_posix()}'),
                'Committed launch bytes differ: '+name)
        if name!='manifest.json':
            require(digest(path)==manifest['identities'][name],'Launch manifest identity differs: '+name)
    attempt, process, terminal = (read(launch/name) for name in ('attempt.json','process.json','terminal.json'))
    original, saved = (read(cap/name) for name in ('capture.json','receipt.json'))
    source = report['execution_source']
    require(attempt['status']=='STARTED' and terminal['status']=='COMPLETED' and terminal['returncode']==0
            and terminal['receipt_exists'] and attempt['source']==process['source']==terminal['source']==source,
            'Launch not successful or not bound to capture source')
    require(attempt['launcher_sha256']==digest(launch/'launcher.py')
            and attempt['executable_sha256']==original['executable_sha256']
            and attempt['review_hashes']=={axis:r['report_sha256'] for axis,r in original['reviews'].items()},
            'Launch interpreter, launcher or review identity differs')
    require(all(terminal[f'{name}_sha256']==digest(launch/f'{name}.txt') for name in ('stdout','stderr'))
            and read(launch/'stdout.txt')['status']=='PASS' and read(launch/'stdout.txt')['counters']==saved['counters'],
            'Original launch streams differ')
    require(report['completed_integrations']==4 and report['simulated_seconds']==21.5
            and report['new_physics']==report['new_selector_calls']==report['new_closure_calls']==0,
            'Author delivery scope differs')
    report.update(status='PASS_CLEAN_SAVED_DELIVERY', launch_artifacts=len(expected)+1,
                  all_case_artifacts=report['artifacts']+1, original_execution_pass=True,
                  fresh_checkout=str(root), capture=protocol['output'], original_repeated=False,
                  verifier_sha256=digest(Path(__file__)))
    require(not any(module=='aegis_dc' or module.startswith('aegis_dc.') for module in sys.modules),
            'Saved-only verifier imported project runtime')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--delivery',required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    result=verify(args.root,args.delivery)
    with args.output.open('x',encoding='utf-8',newline='\n') as f:
        f.write(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result,ensure_ascii=False))
