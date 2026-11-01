"""Real Tour and all-action branches. Whitelisted known development sources only."""
import argparse
from copy import deepcopy
import gzip
import json
import os
from pathlib import Path
import time
import traceback
import unittest
from unittest.mock import patch
import torch

from patrol_rsi.action_value_execution import execute
from patrol_rsi.multistep_workflow import digest
from patrol_rsi.m11 import frozen_predictor
from patrol_rsi.m9 import arrays_digest
from patrol_rsi.limited_prediction import read,write,sha,need
from run_multistep import reserve
from run_m12d_paired import StoredTrace,write_gz
from audit_m11 import independent_schedule,independent_events
from audit_local_reorder import audit_reorder

STAGE='research/2026-11-01-action-value'
CVAE=Path('/share/home/renly/renly-patrol-rsi/runs/20261028-m111/frozen-estimator.pt')


def verify(source):
    m=read(source/'snapshot-manifest.json')
    for k,v in m['files'].items():need(sha(source/k)==v,'Source bytes: '+k)
    need(digest(m['execution_files'])==m['execution_signature'],'Rollout closure identity')
    return m['execution_signature']


def record(row):
    p=Path(row['record_path']);need(sha(p)==row['record_sha256'],'Actual raw bytes')
    value=json.loads(gzip.decompress(p.read_bytes()))
    need(value['execution_signature']==row['execution_signature'] and value['case_id']==row['case_id'] and value['evaluation_key']==row['evaluation_key'],'Actual raw identity')
    return value


def trace_for(case):
    trace=StoredTrace(Path(case['trace_folder']));spec=case['specification']
    need(trace.fingerprint==case['expected_fingerprint'] and trace.seed==spec['seed'] and trace.scenario==spec['scenario'],'Declared process identity')
    need(trace.config.fault_start_s==335 and trace.config.fault_end_s==335+spec['duration_s'],'Frozen phase and duration')
    need(spec['noise_c']==.2 and spec['estimator']=='history' and case['group_id'] in (41000,41001,42000,42001),'Only four existing development groups')
    return trace


def evaluate_one(root,source,case,predictor,intervention=None):
    signature=verify(source);need(case in read(source/STAGE/'protocol.json')['development'],'Whitelisted case')
    key=digest({'case':case,'execution_signature':signature,'intervention':intervention})
    for file in sorted((root/'evaluations').glob('episode-*/complete.json')):
        r=read(file)
        if r['evaluation_key']==key:
            record(r);need(trace_for(case).fingerprint==r['process_fingerprint'],'Cache actual source');return r
    receipt=reserve(root,'environment-attempts',180,{'case_id':case['case_id'],'execution_signature':signature,'intervention':intervention})
    area=root/'evaluations'/f"episode-{receipt['number']:03d}";area.mkdir(parents=True,exist_ok=False);write(area/'attempt.json',receipt)
    begin=time.perf_counter()
    try:
        trace=trace_for(case);before=arrays_digest(trace.arrays)
        with patch('patrol_rsi.improver_task.phased_trace',return_value=trace):value,env=execute(case['specification'],predictor,intervention is None,intervention)
        need(arrays_digest(trace.arrays)==before,'Fixed physical arrays')
        value.update(case_id=case['case_id'],group_id=case['group_id'],execution_signature=signature,evaluation_key=key,
            source_manifest_sha256=sha(source/'snapshot-manifest.json'),process_fingerprint=trace.fingerprint,intervention=intervention)
        p=area/'record.json.gz';write_gz(p,value)
        independent_schedule(value,env);independent_events(value,env);audit=audit_reorder(value,env)
        if intervention is not None:
            tour=next(r for r in read(root/'tours-complete.json')['rows'] if r['case_id']==case['case_id'])
            root_row=next(r for r in read(root/'roots-frozen.json')['roots'] if r['root_id']==intervention['root_id'])
            verified=value['intervention_verified']
            need(verified['state_sha256']==root_row['state_sha256'] and verified['prefix_action_sha256']==root_row['prefix_action_sha256'],'Actual complete paired prefix')
            need(digest(value['action_log'][:verified['prefix_steps']])==root_row['prefix_action_sha256'],'Actual action prefix')
            if intervention['execute_order']==intervention['window']:
                original=record(tour);need(value['action_log']==original['action_log'] and value['inspection_events']==original['inspection_events'],'Original branch equals actual Tour')
        r={'case_id':case['case_id'],'group_id':case['group_id'],'execution_signature':signature,'evaluation_key':key,
            'case_identity':digest(case),'process_fingerprint':trace.fingerprint,'metrics':value['metrics'],'audit':audit,
            'intervention':intervention,'record_path':str(p),'record_sha256':sha(p),'action_sha256':value['action_sha256'],
            'actual_wall_seconds':time.perf_counter()-begin,'job_id':os.environ['SLURM_JOB_ID']}
        record(r);write(area/'complete.json',r)
        print('ACTUAL',receipt['number'],case['case_id'],'branch' if intervention else 'Tour',round(r['actual_wall_seconds'],3),flush=True)
        return r
    except BaseException as exc:
        write(area/'failed.json',{'type':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc()});raise


def freeze_roots(root,tours,signature):
    selected=[];missing=[]
    for row in tours:
        value=record(row);present=set()
        for r in value['action_value_roots']:
            r=deepcopy(r);r.update(root_id=row['case_id']+'-'+r['root_type'],case_id=row['case_id'],group_id=row['group_id'],
                process_fingerprint=row['process_fingerprint'],tour_record_sha256=row['record_sha256'])
            selected.append(r);present.add(r['root_type'])
        for kind in ('A','B'):
            if kind not in present:missing.append({'case_id':row['case_id'],'root_type':kind,'reason':'No eligible public root under frozen rule'})
    need(len(selected)<=24,'Root limit')
    write(root/'roots-frozen.json',{'execution_signature':signature,'roots':selected,'missing':missing,
        'tour_receipts_sha256':sha(root/'tours-complete.json'),'frozen_before_branch_execution':True})


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--mode',choices=('inputs','pilot','tours','branches'),required=True);a=p.parse_args()
    need('SLURM_JOB_ID' in os.environ,'Actual compute through Slurm');torch.set_num_threads(1)
    source=Path(__file__).resolve().parents[1];root=a.root.resolve();root.mkdir(exist_ok=True);signature=verify(source)
    protocol=read(source/STAGE/'protocol.json');cases=protocol['development']
    for k,v in protocol['immutable'].items():need(sha(source/k)==v,'Old execution/safety bytes: '+k)
    if a.mode=='inputs':
        values=[]
        for c in cases:
            t=trace_for(c);values.append({'case_id':c['case_id'],'fingerprint':t.fingerprint,'metadata_sha256':sha(Path(c['trace_folder'])/'complete.json')})
        frozen_predictor(CVAE,source/'research/2026-10-28-m111-coverage/frozen_estimator.json')
        write(root/('inputs-verified-'+signature[:12]+'.json'),{'cases':values,'new_processes':0,'execution_signature':signature,'checkpoint_sha256':sha(CVAE)});return
    need(read(root/('inputs-verified-'+signature[:12]+'.json'))['execution_signature']==signature,'Verified exact inputs')
    if a.mode=='pilot':
        gate=root/'gate'/signature;gate.mkdir(parents=True,exist_ok=False)
        suite=unittest.defaultTestLoader.discover(str(source/'tests'),pattern='test_action_value.py')
        with (gate/'tests.txt').open('x') as f:r=unittest.TextTestRunner(stream=f,verbosity=2).run(suite)
        write(gate/'complete.json',{'passed':r.wasSuccessful() and not r.skipped,'tests':r.testsRun,'synthetic_interface_fits_only':True});need(r.wasSuccessful() and not r.skipped,'Interface gate')
    else:need(read(root/'gate'/signature/'complete.json')['passed'],'Current interface gate')
    predictor=frozen_predictor(CVAE,source/'research/2026-10-28-m111-coverage/frozen_estimator.json')
    if a.mode=='pilot':write(root/('cost-probe-'+signature[:12]+'.json'),evaluate_one(root,source,cases[0],predictor))
    elif a.mode=='tours':
        values=[evaluate_one(root,source,c,predictor) for c in cases]
        write(root/'tours-complete.json',{'execution_signature':signature,'rows':values});freeze_roots(root,values,signature)
    else:
        frozen=read(root/'roots-frozen.json');need(frozen['execution_signature']==signature and frozen['tour_receipts_sha256']==sha(root/'tours-complete.json'),'Frozen Tour/root closure')
        groups=[]
        for r in frozen['roots']:
            case=next(c for c in cases if c['case_id']==r['case_id']);values=[]
            legal=[c for c in r['candidates'] if c['certificate']['ok']]
            need(len(legal)<=6 and any(c['original'] for c in legal),'All original safe permutations, no risk filter')
            for c in legal:
                intervention={k:r[k] for k in ('root_id','time_s','agent','round_id','window','state_sha256','prefix_action_sha256')}
                intervention['execute_order']=c['order']
                values.append(evaluate_one(root,source,case,predictor,intervention))
            groups.append({'root_id':r['root_id'],'rows':values,'root_sha256':digest(r)})
            write(root/('branch-group-'+r['root_id']+'.json'),groups[-1])
        write(root/'branches-complete.json',{'execution_signature':signature,'frozen_roots_sha256':sha(root/'roots-frozen.json'),'groups':groups})


if __name__=='__main__':main()
