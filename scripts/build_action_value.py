"""Assemble true branch outcomes and freeze a trainable public36 dataset, no rollouts."""
import argparse
from pathlib import Path
import os
import numpy as np

from patrol_rsi.action_value_features import features,FEATURE_NAMES
from patrol_rsi.action_value_data import outcomes,event_pairs,classify_root
from patrol_rsi.multistep_workflow import digest
from run_action_value import STAGE,verify,read,write,sha,need,record


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args()
    need('SLURM_JOB_ID' in os.environ,'Data computation through Slurm')
    root=a.root.resolve();source=Path(__file__).resolve().parents[1];sig=verify(source)
    frozen=read(root/'roots-frozen.json');branches=read(root/'branches-complete.json');protocol=read(source/STAGE/'protocol.json')
    need(branches['execution_signature']==frozen['execution_signature']==sig and branches['frozen_roots_sha256']==sha(root/'roots-frozen.json'),'Frozen complete branch cohort')
    need(len(branches['groups'])==len(frozen['roots'])<=24,'All selected roots represented')
    groups=[];samples=[];checks={'prefix_states':0,'same_time_measurements':0,'all_legal_actions':True}
    for group in branches['groups']:
        r=next(r for r in frozen['roots'] if r['root_id']==group['root_id']);need(digest(r)==group['root_sha256'],'Root bytes before branch results')
        legal=[c for c in r['candidates'] if c['certificate']['ok']];original=next(c for c in legal if c['original'])
        actual={tuple(row['intervention']['execute_order']):row for row in group['rows']}
        need(len(actual)==len(legal) and set(actual)=={tuple(c['order']) for c in legal},'Every safe permutation, including original, actually executed')
        base_row=actual[tuple(r['window'])];base=record(base_row)
        base_event={(e['task'],e['time_s']):e['measurement'] for e in base['inspection_events']}
        own=[]
        for c in legal:
            row=actual[tuple(c['order'])];value=record(row)
            need(row['execution_signature']==sig and value['process_fingerprint']==r['process_fingerprint'],'Same kernel and physical process')
            state=value['intervention_verified'];need(digest(state['state_snapshot'])==state['state_sha256']==r['state_sha256'],'Actual full paired state')
            need(digest(value['action_log'][:state['prefix_steps']])==r['prefix_action_sha256'],'Actual paired prefix actions')
            checks['prefix_states']+=1
            for e in value['inspection_events']:
                key=(e['task'],e['time_s'])
                if key in base_event:need(e['measurement']==base_event[key],'Same channel/time noise');checks['same_time_measurements']+=1
            x=features(r['feature_rows'],original['certificate'],c['certificate'],r['time_s']).tolist()
            need(np.allclose(x,c['action_value_features'],rtol=0,atol=1e-12),'Frozen public feature calculation')
            if c['original']:need(x==[0.]*36,'Original zero features')
            y=outcomes(base,value)
            sample={'sample_id':r['root_id']+'-'+digest(c['order'])[:12],'root_id':r['root_id'],'case_id':r['case_id'],
                'group_id':r['group_id'],'process_fingerprint':r['process_fingerprint'],'action_id':digest(c['order']),
                'order':c['order'],'original':c['original'],'x':x,**y,
                'H_preference':c['h_preference'],'H_advantage':c['advantage'],'H_gain':c['gain'],
                'root_type':r['root_type'],'root_time_s':r['time_s'],'root_sha256':digest(r),
                'root_public_state':r['feature_rows'],'candidate_geometry':c['certificate'],
                'actual_metrics':value['metrics'],'original_actual_metrics':base['metrics'],
                'confirmation_events_labels_only':event_pairs(base,value,r['time_s']),
                'record_path':row['record_path'],'record_sha256':row['record_sha256'],'original_record_sha256':base_row['record_sha256'],
                'execution_signature':sig,'source_manifest_sha256':value['source_manifest_sha256']}
            need(y['wait_valid']==(base['metrics']['anomaly_segments']>0),'Wait label validity only')
            own.append(sample);samples.append(sample)
        groups.append({'root_id':r['root_id'],'case_id':r['case_id'],'group_id':r['group_id'],
            'legal_action_count':len(legal),**classify_root(own)})
    need(len(samples)<=144,'Finite action budget')
    value={'schema':'public36-local-action-outcome-v1','execution_signature':sig,'feature_names':list(FEATURE_NAMES),
        'heads':['missed','wait_s','travel_m','completed'],'source_plan_sha256':protocol['plan_sha256'],
        'root_manifest_sha256':sha(root/'roots-frozen.json'),'branch_receipts_sha256':sha(root/'branches-complete.json'),
        'feature_source_sha256':sha(source/'src/patrol_rsi/action_value_features.py'),
        'label_source_sha256':sha(source/'src/patrol_rsi/action_value_data.py'),'builder_sha256':sha(Path(__file__)),
        'all_development_groups':sorted({c['group_id'] for c in protocol['development']}),
        'samples':samples,'root_assessments':groups,'audit':checks,'missing_roots':frozen['missing'],
        'semantics':'One realized full-episode intervention then Tour, not expected POMDP value. Only x enters models; masks/group/event fields are labels/audit only.'}
    write(root/'dataset.json',value);write(root/'dataset-seal.json',{'dataset_sha256':sha(root/'dataset.json'),'sample_count':len(samples),
        'root_count':len(groups),'execution_signature':sig,'complete_all_safe_actions':True,'feature_source_sha256':value['feature_source_sha256']})
    print('DATASET',len(samples),'actions',len(groups),'roots',flush=True)


if __name__=='__main__':main()
