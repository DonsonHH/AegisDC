"""Development-only source/data contract freeze, keeping label/fit tools separate from rollout identity."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from patrol_rsi.multistep_workflow import digest
from patrol_rsi.limited_prediction import sha
from patrol_rsi.action_value_features import FEATURE_NAMES

STAGE=ROOT/'research/2026-11-01-action-value'


def main():
    p=argparse.ArgumentParser();p.add_argument('version');a=p.parse_args()
    if not a.version.startswith('v') or not a.version[1:].isdigit():raise ValueError('Explicit version')
    if not STAGE.exists():
        old=json.loads((ROOT/'research/2026-11-01-measurement-effect/protocol.json').read_bytes());cases=[]
        for index,c in enumerate(old['cases']):
            case={'case_id':f'dev-{index:02d}','group_id':c['specification']['seed'],'partition':'development',
                'source_declaration':c['group'],'specification':c['specification']}
            if c['group']=='already_seen_development':case.update(trace_folder=c['trace_folder'],expected_fingerprint=c['expected_fingerprint'])
            else:
                folder=ROOT/'.work/action-value/input-metadata/processes'/c['case_id'];m=json.loads((folder/'complete.json').read_bytes())
                case.update(trace_folder='/share/home/renly/renly-patrol-rsi/runs/20261101-measurement/processes/'+c['case_id'],
                    expected_fingerprint=m['fingerprint'],metadata_sha256=sha(folder/'complete.json'))
            cases.append(case)
        if len(cases)!=12 or {c['group_id'] for c in cases}!={41000,41001,42000,42001}:raise ValueError('Four declared development groups')
        STAGE.mkdir()
        protocol={'study':'full-local-action-value-v1','baseline':'5858abc552d7deef0e74358355bf8059aeb69ada',
            'execution_base':'8a9de5e86271c9fdd679011996e2f79acc9a673a','development':cases,
            'plan_sha256':sha(ROOT/'research/2026-11-01-action-value-plan/执行计划.md'),
            'limits':{'environment_attempts':180,'roots':24,'distinct_actions_per_root':6,'grouped_fit_runs':4,'Qwen_calls':0,'large_network_training':0,'new_confirmation':0},
            'feature_names':list(FEATURE_NAMES),'ridge':{'lambda':1.,'intercept':False,'center':False,'dtype':'float64','folds':'leave_one_seed_out','final_refit':False},
            'immutable':{k:sha(ROOT/k) for k in ('src/patrol_rsi/local_reorder.py','src/patrol_rsi/reorder_execution.py','src/patrol_rsi/baseline_correction.py','src/patrol_rsi/correction_execution.py','src/patrol_rsi/inspection_metrics.py','src/patrol_rsi/active_inspection.py','src/patrol_rsi/improver_task.py','src/patrol_rsi/estimation.py','src/patrol_rsi/facility.py')},
            'new_processes_generated':0,'feature_contract':'Fixed before any new labels or OOF scores; original zero36; label masks never inference inputs',
            'root_rule':'A first H/R shadow disagreement;B max public discrimination excludingA,1e-9 ties time/agent; never outcomes'}
        (STAGE/'protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        (STAGE/'.gitattributes').write_text('* -text -whitespace\n',encoding='utf8')
    dest=ROOT/'.work/action-value'/('code-'+a.version);dest.mkdir(parents=True,exist_ok=False)
    files=[*sorted((ROOT/'src').rglob('*.py')),*sorted((ROOT/'tests').glob('test_action_value*.py')),*sorted((ROOT/'scripts').glob('*action_value*.py')),
        *[ROOT/'scripts'/s for s in ('run_multistep.py','run_m12d_paired.py','audit_m11.py','audit_m111.py','audit_local_reorder.py')],
        *sorted((ROOT/'cluster').glob('action_value_*.sbatch')),STAGE/'protocol.json',ROOT/'research/2026-10-28-m111-coverage/frozen_estimator.json']
    hashes={}
    for file in files:
        name=file.relative_to(ROOT).as_posix();out=dest/name;out.parent.mkdir(parents=True,exist_ok=True)
        out.write_bytes(file.read_bytes().replace(b'\r\n',b'\n') if file.suffix=='.sbatch' else file.read_bytes());hashes[name]=sha(out)
    kernel={k:v for k,v in hashes.items() if k.startswith('src/') and k not in ('src/patrol_rsi/action_value_learning.py','src/patrol_rsi/action_value_evaluation.py')
        or k.startswith('research/') or k in ('scripts/run_action_value.py','scripts/run_multistep.py','scripts/run_m12d_paired.py','scripts/audit_m11.py','scripts/audit_m111.py','scripts/audit_local_reorder.py')}
    fit_code={k:v for k,v in hashes.items() if k in ('src/patrol_rsi/action_value_learning.py','scripts/fit_action_value.py') or k.startswith('research/')}
    m={'version':a.version,'files':hashes,'execution_files':kernel,'execution_signature':digest(kernel),'fit_files':fit_code,'fit_signature':digest(fit_code),
        'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()}
    (dest/'snapshot-manifest.json').write_text(json.dumps(m,indent=2)+'\n',encoding='utf8',newline='\n')
    area=STAGE/'source';area.mkdir(exist_ok=True);archive=area/('code-'+a.version+'.tar.gz')
    with archive.open('xb') as stream:
        with tarfile.open(fileobj=stream,mode='w:gz') as t:
            for f in sorted(dest.rglob('*')):
                if f.is_file():t.add(f,arcname=f.relative_to(dest).as_posix(),recursive=False)
    receipt={'archive_sha256':sha(archive),'execution_signature':m['execution_signature'],'fit_signature':m['fit_signature'],
        'source_manifest_sha256':sha(dest/'snapshot-manifest.json'),'archive_bytes':archive.stat().st_size}
    (area/('receipt-'+a.version+'.json')).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(receipt))


if __name__=='__main__':main()
