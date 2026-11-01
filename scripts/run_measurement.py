"""Actual bounded measurement-exposure experiment; failures count before execution."""
import argparse
import gzip
import json
import os
from pathlib import Path
import time
import traceback
from unittest.mock import patch
import unittest

import torch

from patrol_rsi.improver_task import PhasedTrace
from patrol_rsi.limited_prediction import read, write, sha, need
from patrol_rsi.m11 import frozen_predictor
from patrol_rsi.m9 import arrays_digest
from patrol_rsi.measurement_execution import run_measurement_episode
from patrol_rsi.measurement_workflow import MeasurementWorkflow
from patrol_rsi.multistep_workflow import Workflow, digest
from patrol_rsi.multistep_execution import run_workflow_episode
from run_multistep import reserve
from run_m12d_paired import StoredTrace, save_trace, write_gz
from audit_m11 import independent_schedule, independent_events
from audit_m111 import independent_certificates

STAGE = 'research/2026-11-01-measurement-effect'
CVAE = Path('/share/home/renly/renly-patrol-rsi/runs/20261028-m111/frozen-estimator.pt')


def verify(source):
    manifest = read(source/'snapshot-manifest.json')
    for name, value in manifest['files'].items():
        need(sha(source/name) == value, 'Exact archived source: '+name)
    need(digest(manifest['execution_files']) == manifest['execution_signature'], 'Complete execution identity')
    return manifest['execution_signature']


def rows(root, signature):
    return [read(p) for p in sorted((root/'evaluations').glob('episode-*/complete.json')) if read(p)['execution_signature'] == signature]


def record(row):
    path = Path(row['record_path'])
    need(sha(path) == row['record_sha256'], 'Original feedback record')
    return json.loads(gzip.decompress(path.read_bytes()))


def get_trace(root, source, case):
    spec = case['specification']
    if case['group'] == 'already_seen_development':
        trace = StoredTrace(Path(case['trace_folder']))
        need(trace.fingerprint == case['expected_fingerprint'], 'Known development identity')
    else:
        folder = root/'processes'/case['case_id']
        folder.parent.mkdir(exist_ok=True)
        if not folder.exists():
            history = read(source/STAGE/'historical-identities.json')
            need(spec['seed'] not in history['seed_groups'], 'New seed not old registration')
            trace = PhasedTrace(spec['seed'], spec['scenario'], spec['duration_s'], spec['fault_start_s'])
            need(trace.fingerprint not in history['numeric_fingerprints'], 'No old process reuse')
            for p in folder.parent.glob('*/complete.json'):
                need(read(p)['fingerprint'] != trace.fingerprint, 'Unique new process')
            save_trace(trace, folder)
        trace = StoredTrace(folder)
    need(trace.seed == spec['seed'] and trace.scenario == spec['scenario'] and trace.config.fault_start_s == spec['fault_start_s']
         and trace.config.fault_end_s == spec['fault_start_s']+spec['duration_s'], 'Declared source unchanged')
    return trace


def run_one(root, source, case, arm, workflow, predictor):
    signature = verify(source)
    key = digest({'case':case,'arm':arm,'workflow':workflow.to_dict(),'execution_signature':signature})
    cached = [r for r in rows(root,signature) if r['evaluation_key']==key]
    if cached:
        need(len(cached)==1 and sha(Path(cached[0]['record_path']))==cached[0]['record_sha256'],'Exact source-bound finished cache')
        return cached[0]
    receipt = reserve(root,'environment-attempts',60,{'case_id':case['case_id'],'arm':arm,'execution_signature':signature,'workflow':workflow.to_dict()})
    folder = root/'evaluations'/f"episode-{receipt['number']:02d}";folder.mkdir(parents=True,exist_ok=False)
    write(folder/'attempt.json',receipt);started=time.perf_counter()
    try:
        trace = get_trace(root,source,case);before=arrays_digest(trace.arrays)
        with patch('patrol_rsi.improver_task.phased_trace',return_value=trace):
            if arm=='R':
                value,env=run_workflow_episode(case['specification'],Workflow(),predictor,2,'D')
                value['reference']='Unchanged original positive-first two-step workflow'
            else:
                value,env=run_measurement_episode(case['specification'],workflow,predictor,arm)
        need(arrays_digest(trace.arrays)==before,'No physical modification')
        independent_schedule(value,env);independent_events(value,env);accepted,plans=independent_certificates(value,env)
        need(value['team']['count']==18 and len(env.tasks)==176,'Original team and128racks')
        need(value['metrics']['selected_detours']==len(value['optional_chain'])<=2,'Exact two-check completion count')
        for first,second in zip(value['optional_chain'],value['optional_chain'][1:]):
            need(second['dispatch_time_s']>=first['completed']['time_s'],'Actual first reference before second dispatch')
        value.update(experiment='measurement-effect-v1',case_id=case['case_id'],arm=arm,process_fingerprint=trace.fingerprint,
            execution_signature=signature,source_manifest_sha256=sha(source/'snapshot-manifest.json'))
        path=folder/'record.json.gz';write_gz(path,value)
        row={'case_id':case['case_id'],'group':case['group'],'arm':arm,'specification':case['specification'],
            'evaluation_key':key,'execution_signature':signature,'workflow':workflow.to_dict(),
            'source_manifest_sha256':sha(source/'snapshot-manifest.json'),'process_fingerprint':trace.fingerprint,
            'record_path':str(path),'record_sha256':sha(path),'action_sha256':value['action_sha256'],
            'metrics':value['metrics'],'actual_wall_seconds':time.perf_counter()-started,'job_id':os.environ['SLURM_JOB_ID'],
            'first_triggered':bool(value.get('first_request')) if arm!='R' else bool(value['optional_chain']),
            'audit':{'passed':True,'qualified_measurements':len(value['inspection_events']),
                'independent_full_return_certificates':accepted,'all_assignment_plans':plans,'physical_unchanged':True}}
        write(folder/'complete.json',row)
        print('ACTUAL',case['case_id'],arm,row['metrics']['selected_detours'],round(row['actual_wall_seconds'],3),flush=True)
        return row
    except BaseException as error:
        write(folder/'failed.json',{'type':type(error).__name__,'error':str(error),'traceback':traceback.format_exc()})
        raise


def audit_pairs(root, signature, cases, label):
    completed=rows(root,signature);out=[]
    for case in cases:
        paired={arm:record(next(r for r in completed if r['case_id']==case['case_id'] and r['arm']==arm)) for arm in ('A','B','C')}
        a,b,c=(paired[k] for k in ('A','B','C'))
        need(len({v['process_fingerprint'] for v in paired.values()})==1,'Same physical process')
        need(digest(a['first_request'])==digest(b['first_request'])==digest(c['first_request']),'Identical shared first selection')
        x,y=b['first_post_measurement_context'],c['first_post_measurement_context']
        if x is not None or y is not None:
            need(x is not None and y is not None,'Same first completion opportunity')
            for field in ('physical','first_actual_event','masked_state','visible_state','masked_ranking','visible_ranking'):
                need(digest(x[field])==digest(y[field]),'First paired current context: '+field)
            t=x['physical']['time_s']
            need([v for v in b['action_log'] if v['time_s']<t]==[v for v in c['action_log'] if v['time_s']<t],'Same true prefix before replan')
            different_states=digest(x['masked_state'])!=digest(x['visible_state'])
            priority_changed=any(v['value']!=next(w['value'] for w in x['masked_ranking'] if w['task']==v['task']) for v in x['visible_ranking'])
            item={'case_id':case['case_id'],'first_time_s':t,'state_changed':different_states,'priority_changed_at_first':priority_changed,
                'first_B_choice':x['actual_selected'],'first_C_choice':y['actual_selected'],
                'first_alarm':x['first_actual_event']['alarm'],'first_reference':x['first_actual_event']['measurement']}
        else:
            item={'case_id':case['case_id'],'first_time_s':None,'not_applicable':'No first diagnostic check'}
        item.update(actual_trajectory_changed=b['action_sha256']!=c['action_sha256'],
            missed_delta=c['metrics']['missed_segments']-b['metrics']['missed_segments'],
            wait_delta=(c['metrics']['consequence_weighted_censored_delay_s']-b['metrics']['consequence_weighted_censored_delay_s'])
                if b['metrics']['consequence_weighted_censored_delay_s'] is not None else None,
            actual_B_record=next(r['record_path'] for r in completed if r['case_id']==case['case_id'] and r['arm']=='B'),
            actual_C_record=next(r['record_path'] for r in completed if r['case_id']==case['case_id'] and r['arm']=='C'))
        out.append(item)
    write(root/(label+'-paired.json'),{'passed':True,'pairs':out,'shadow_ranks_not_world_outcomes':True})


def gate(root,source,signature):
    area=root/'gate'/signature;area.mkdir(parents=True,exist_ok=False)
    suite=unittest.TestSuite()
    for pattern in ('test_measurement_*.py','test_multistep_safety.py','test_multistep_workflow.py','test_multistep_proposal.py'):
        suite.addTests(unittest.defaultTestLoader.discover(str(source/'tests'),pattern=pattern))
    with (area/'tests.txt').open('x') as stream:
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    value={'passed':result.wasSuccessful() and not result.skipped,'tests':result.testsRun,'failures':len(result.failures),
        'errors':len(result.errors),'skipped':len(result.skipped),'execution_signature':signature,'job_id':os.environ['SLURM_JOB_ID']}
    write(area/'complete.json',value);need(value['passed'],'Interface and safety gate')


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--mode',choices=('pilot','old','new','child'),required=True);a=p.parse_args()
    need('SLURM_JOB_ID' in os.environ,'Slurm only')
    root=a.root.resolve();root.mkdir(exist_ok=True);source=Path(__file__).resolve().parents[1];torch.set_num_threads(1)
    signature=verify(source);protocol=read(source/STAGE/'protocol.json')
    if a.mode=='pilot':gate(root,source,signature)
    else:need(read(root/'gate'/signature/'complete.json')['passed'],'Exact kernel gate')
    predictor=frozen_predictor(CVAE,source/'research/2026-10-28-m111-coverage/frozen_estimator.json')
    cases=protocol['cases']
    if a.mode=='pilot':
        for arm in ('A','B','C'):run_one(root,source,cases[0],arm,MeasurementWorkflow(),predictor)
        audit_pairs(root,signature,cases[:1],'pilot')
    elif a.mode in ('old','new'):
        selected=cases[:6] if a.mode=='old' else cases[6:]
        for case in selected:
            for arm in ('A','B','C'):run_one(root,source,case,arm,MeasurementWorkflow(),predictor)
            if a.mode=='old':run_one(root,source,case,'R',MeasurementWorkflow(),predictor)
        audit_pairs(root,signature,selected,a.mode)
        write(root/(a.mode+'-complete.json'),{'rows':rows(root,signature)})
    else:
        workflow=MeasurementWorkflow.from_dict(read(root/'child-workflow.json')['workflow'])
        for case in cases:run_one(root,source,case,'child',workflow,predictor)
        write(root/'child-complete.json',{'rows':[r for r in rows(root,signature) if r['arm']=='child']})


if __name__=='__main__':main()
