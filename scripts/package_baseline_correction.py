"""Freeze development-only inputs and source without archived confirmation data."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from patrol_rsi.multistep_workflow import digest
from patrol_rsi.limited_prediction import sha
from patrol_rsi.baseline_correction import response_contract

STAGE=ROOT/'research/2026-11-01-baseline-correction'


def main():
    p=argparse.ArgumentParser();p.add_argument('version');a=p.parse_args()
    if not a.version.startswith('v') or not a.version[1:].isdigit():raise ValueError('Explicit version')
    if not STAGE.exists():
        old=json.loads((ROOT/'research/2026-11-01-local-reorder/protocol.json').read_bytes())
        refs=json.loads((ROOT/'research/2026-11-01-local-reorder/evidence/run/baselines-complete.json').read_bytes())
        cases=old['development']
        for c in cases:
            for label in ('T','R'):
                r=next(r for r in refs[label]['rows'] if r['case_id']==c['case_id'])
                c['legacy_'+label]={k:r[k] for k in ('record_path','record_sha256','action_sha256')}
        STAGE.mkdir()
        protocol={'study':'Tour-preserving-correction-v1','base':'dd6803e113e4a4f53a800d70613fe8dbba05f867',
            'plan':'research/2026-11-01-baseline-correction-plan/执行计划.md','plan_sha256':sha(ROOT/'research/2026-11-01-baseline-correction-plan/执行计划.md'),
            'development':cases,'limits':{'actual_environment_attempts':60,'actual_Qwen_calls':4,'neural_training':0,'confirmation':0},
            'model':{'id':'Qwen3-8B-b968826d','device':'cpu','dtype':'float32','greedy':True,'input_max':4096,'output_max':256,'generation_timeout_s':240},
            'contract':response_contract(),'physical_and_safety':{k:sha(ROOT/k) for k in ('src/patrol_rsi/local_reorder.py','src/patrol_rsi/active_inspection.py','src/patrol_rsi/improver_task.py','src/patrol_rsi/inspection_metrics.py','src/patrol_rsi/facility.py','src/patrol_rsi/reorder_execution.py')},
            'selection':'Pareto exactly per saved plan; T formal default, H exploration start',
            'root_rule':'First(time,agent) nonoriginal-legal Tour root with any owned original public risk>0, else first zero; no future scores',
            'all_phases_development_only':True,'budget_allocation':{'pairs':12,'T_R':12,'H':6,'S':12,'Q':12,'repairs':6}}
        (STAGE/'protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        (STAGE/'.gitattributes').write_text('* -text -whitespace\n',encoding='utf8')
    dest=ROOT/'.work/baseline-correction'/('code-'+a.version);dest.mkdir(parents=True,exist_ok=False)
    files=[*sorted((ROOT/'src').rglob('*.py')),*sorted((ROOT/'tests').glob('test_baseline_correction.py')),*sorted((ROOT/'tests').glob('test_correction_wire.py')),
        *sorted((ROOT/'scripts').glob('*baseline_correction*.py')),
        *[ROOT/'scripts'/v for v in ('run_multistep.py','run_m12d_paired.py','audit_m11.py','audit_m111.py','audit_local_reorder.py')],
        *sorted((ROOT/'cluster').glob('baseline_correction_*.sbatch')),STAGE/'protocol.json',ROOT/'research/2026-10-28-m111-coverage/frozen_estimator.json']
    hashes={}
    for f in files:
        name=f.relative_to(ROOT).as_posix();out=dest/name;out.parent.mkdir(parents=True,exist_ok=True)
        out.write_bytes(f.read_bytes().replace(b'\r\n',b'\n') if f.suffix=='.sbatch' else f.read_bytes());hashes[name]=sha(out)
    kernel={k:v for k,v in hashes.items() if k.startswith('src/') or k=='tests/test_baseline_correction.py' or k.startswith('research/') or k in ('scripts/run_baseline_correction.py','scripts/audit_baseline_correction.py','scripts/audit_local_reorder.py','scripts/run_m12d_paired.py','scripts/run_multistep.py','scripts/audit_m11.py','scripts/audit_m111.py')}
    m={'version':a.version,'files':hashes,'execution_files':kernel,'execution_signature':digest(kernel),'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()}
    (dest/'snapshot-manifest.json').write_text(json.dumps(m,indent=2)+'\n',encoding='utf8',newline='\n')
    area=STAGE/'source';area.mkdir(exist_ok=True);archive=area/('code-'+a.version+'.tar.gz')
    with archive.open('xb') as stream:
        with tarfile.open(fileobj=stream,mode='w:gz') as t:
            for f in sorted(dest.rglob('*')):
                if f.is_file():t.add(f,arcname=f.relative_to(dest).as_posix(),recursive=False)
    receipt={'archive_sha256':sha(archive),'execution_signature':m['execution_signature'],'source_manifest_sha256':sha(dest/'snapshot-manifest.json'),'archive_bytes':archive.stat().st_size}
    (area/('receipt-'+a.version+'.json')).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(receipt))


if __name__=='__main__':main()
