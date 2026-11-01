"""Four fixed leave-seed-out runs only, no model selection or final refit."""
import argparse
from pathlib import Path
import os
import numpy as np

from patrol_rsi.action_value_learning import fit_fold,predict,load
from patrol_rsi.action_value_evaluation import head_errors,pair_rankings
from patrol_rsi.multistep_workflow import digest
from run_action_value import STAGE,verify,read,write,sha,need,reserve


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--fold',type=int,required=True,choices=(0,1,2,3));a=p.parse_args()
    need('SLURM_JOB_ID' in os.environ,'Real fitting through Slurm')
    source=Path(__file__).resolve().parents[1];root=a.root.resolve();sig=verify(source);manifest=read(source/'snapshot-manifest.json')
    data=read(root/'dataset.json');seal=read(root/'dataset-seal.json')
    need(sha(root/'dataset.json')==seal['dataset_sha256'] and data['execution_signature']==sig,'Sealed actual dataset')
    need(data['feature_source_sha256']==sha(source/'src/patrol_rsi/action_value_features.py'),'Frozen feature code')
    groups=data['all_development_groups'];need(len(groups)==4,'Four underlying development seed groups')
    group=groups[a.fold];folder=root/'fits'/f'fold-{a.fold}'
    if (folder/'complete.json').exists():
        done=read(folder/'complete.json');need(done['dataset_sha256']==sha(root/'dataset.json') and done['fit_signature']==manifest['fit_signature'],'Same finished fit cache')
        need(sha(folder/'model.json')==done['model_sha256'],'Frozen fitted artifact');print('CACHED_FIT',a.fold,flush=True);return
    # Complete structural/finite checks occur BEFORE the one counted fitting call.
    for r in data['samples']:
        need(len(r['x'])==36 and np.isfinite(r['x']).all(),'Finite fixed36')
        need(r['group_id'] in groups and len(r['y'])==4,'Grouped four-head labels')
        need(all(v is None or np.isfinite(v) for v in r['y']),'Finite valid labels')
        need((r['y'][1] is not None)==r['wait_valid'],'No healthy wait imputation')
    prior=[read(p) for p in (root/'fits').glob('fold-*/attempt.json')]
    need(not any(v['heldout_group']==group for v in prior),'Failed or running group cannot silently refit')
    receipt=reserve(root,'fit-attempts',4,{'fold':a.fold,'heldout_group':group,'dataset_sha256':sha(root/'dataset.json'),'fit_signature':manifest['fit_signature']})
    folder.mkdir(parents=True,exist_ok=False);write(folder/'attempt.json',receipt)
    try:
        model=fit_fold(data['samples'],group)
        model.update(dataset_sha256=sha(root/'dataset.json'),execution_signature=sig,fit_signature=manifest['fit_signature'],
            feature_source_sha256=data['feature_source_sha256'],fit_script_sha256=sha(Path(__file__)))
        write(folder/'model.json',model);restored=load(folder/'model.json')
        validation=[r for r in data['samples'] if r['group_id']==group];train=[r for r in data['samples'] if r['group_id']!=group]
        need(group not in model['training_groups'] and not(set(model['training_roots'])&{r['root_id'] for r in validation}),'No root/action/group crossing')
        x=np.asarray([r['x'] for r in validation],dtype=float).reshape(-1,36);pred=predict(restored,x)
        need(np.array_equal(predict(model,x),pred),'Saved/loaded model exactly predicts')
        need(np.array_equal(predict(restored,np.zeros((1,36))),np.zeros((1,4))),'Original relative zero prediction')
        oof=[{'sample_id':r['sample_id'],'group_id':r['group_id'],'root_id':r['root_id'],'prediction':p.tolist()} for r,p in zip(validation,pred)]
        write(folder/'oof.json',oof)
        result={'fold':a.fold,'heldout_group':group,'training_groups':model['training_groups'],'dataset_sha256':sha(root/'dataset.json'),
            'fit_signature':manifest['fit_signature'],'model_sha256':sha(folder/'model.json'),'oof_sha256':sha(folder/'oof.json'),
            'validation_rows':len(validation),'head_statuses':[h['status'] for h in model['heads']],
            'training_professions':model['training_professions'],
            'validation_rows_outside_training_feature_range':int(np.any((x<np.asarray(model['training_feature_min'])-1e-9)|(x>np.asarray(model['training_feature_max'])+1e-9),axis=1).sum()),
            'training_errors':head_errors(train,predict(model,[r['x'] for r in train])),
            'OOF_errors':head_errors(validation,pred),'zero_errors':head_errors(validation,np.zeros_like(pred)),
            'OOF_rankings':pair_rankings(validation,pred),'job_id':os.environ['SLURM_JOB_ID']}
        write(folder/'complete.json',result);print('FIT_COMPLETE',a.fold,group,result['head_statuses'],flush=True)
    except BaseException as exc:
        write(folder/'failed.json',{'type':type(exc).__name__,'error':str(exc),'fit_remains_charged':True});raise


if __name__=='__main__':main()
