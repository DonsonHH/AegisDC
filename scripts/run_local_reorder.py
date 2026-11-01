"""Bounded real development/confirmation evaluations for local task reordering."""
import argparse
import gzip
import json
import os
from pathlib import Path
import statistics
import time
import traceback
import unittest
from unittest.mock import patch

import torch

from patrol_rsi.local_score import ScoreExpression,BASE_EXPRESSION
from patrol_rsi.reorder_execution import run_reorder,lower
from patrol_rsi.multistep_workflow import digest
from patrol_rsi.improver_task import PhasedTrace
from patrol_rsi.limited_prediction import read,write,sha,need
from patrol_rsi.m11 import frozen_predictor
from patrol_rsi.m9 import arrays_digest
from run_multistep import reserve
from run_m12d_paired import StoredTrace,save_trace,write_gz
from audit_m11 import independent_schedule,independent_events
from audit_local_reorder import audit_reorder

STAGE='research/2026-11-01-local-reorder'
CVAE=Path('/share/home/renly/renly-patrol-rsi/runs/20261028-m111/frozen-estimator.pt')


def policy(source,method='expression'):
    return {'method':method,**({'score_expression':source} if method=='expression' else {})}


def policy_id(value):
    return digest({'method':value['method'],'canonical_expression':ScoreExpression(value.get('score_expression',BASE_EXPRESSION)).tree})


def verify(source):
    manifest=read(source/'snapshot-manifest.json')
    for name,value in manifest['files'].items():need(sha(source/name)==value,'Source bytes: '+name)
    need(digest(manifest['execution_files'])==manifest['execution_signature'],'Execution kernel identity')
    return manifest['execution_signature']


def rows(root,signature):
    values=[read(p) for p in sorted((root/'evaluations').glob('episode-*/complete.json'))]
    return [v for v in values if v['execution_signature']==signature]


def record(row):
    path=Path(row['record_path']);need(sha(path)==row['record_sha256'],'Original actual record')
    return json.loads(gzip.decompress(path.read_bytes()))


def get_trace(root,source,case):
    spec=case['specification']
    if case['partition']=='development':
        trace=StoredTrace(Path(case['trace_folder']));need(trace.fingerprint==case['expected_fingerprint'],'Known development source')
    else:
        need((root/'selection-frozen.json').exists(),'No confirmation source before development selection freeze')
        frozen=read(root/'selection-frozen.json');need(case in frozen['confirmation_cases'],'Only frozen confirmation cases')
        folder=root/'confirmation-processes'/case['case_id'];folder.parent.mkdir(exist_ok=True)
        if not folder.exists():
            history=read(source/STAGE/'historical-identities.json')
            need(spec['seed'] not in history['seed_groups'],'New confirmation seed identity')
            trace=PhasedTrace(spec['seed'],spec['scenario'],spec['duration_s'],spec['fault_start_s'])
            need(trace.fingerprint not in history['numeric_fingerprints'],'No old physical process reuse')
            for p in folder.parent.glob('*/complete.json'):need(read(p)['fingerprint']!=trace.fingerprint,'Distinct confirmation processes')
            save_trace(trace,folder)
        trace=StoredTrace(folder)
    need(trace.seed==spec['seed'] and trace.scenario==spec['scenario'] and trace.config.fault_start_s==spec['fault_start_s'] and trace.config.fault_end_s==spec['fault_start_s']+spec['duration_s'],'Declared physical parameters')
    return trace


def evaluate_one(root,source,case,p,predictor):
    signature=verify(source)
    key=digest({'case':case,'policy_id':policy_id(p),'execution_signature':signature})
    cached=[v for v in rows(root,signature) if v['evaluation_key']==key]
    if cached:
        need(len(cached)==1 and sha(Path(cached[0]['record_path']))==cached[0]['record_sha256'],'Exact source/AST/condition cache')
        return cached[0]
    reservation=reserve(root,'environment-attempts',90,{'case_id':case['case_id'],'partition':case['partition'],'policy':p,'execution_signature':signature})
    area=root/'evaluations'/f"episode-{reservation['number']:02d}";area.mkdir(parents=True,exist_ok=False)
    write(area/'attempt.json',reservation);start=time.perf_counter()
    try:
        trace=get_trace(root,source,case);before=arrays_digest(trace.arrays)
        with patch('patrol_rsi.improver_task.phased_trace',return_value=trace):value,env=run_reorder(case['specification'],predictor,p)
        need(arrays_digest(trace.arrays)==before,'Inspection cannot modify plant')
        value.update(case_id=case['case_id'],partition=case['partition'],process_fingerprint=trace.fingerprint,
            execution_signature=signature,source_manifest_sha256=sha(source/'snapshot-manifest.json'))
        path=area/'record.json.gz';write_gz(path,value)
        independent_schedule(value,env);independent_events(value,env);audit=audit_reorder(value,env)
        legacy=None
        if p['method']=='T' and case['partition']=='development':
            ref=case['legacy_tour_record'];path=Path(ref['record_path'])
            need(sha(path)==ref['record_sha256'],'Original Tour regression record')
            old=json.loads(gzip.decompress(path.read_bytes()))
            need(old['process_fingerprint']==trace.fingerprint,'Same Tour regression physical source')
            need(value['action_log']==old['action_log'],'New T action-for-action original Tour equality')
            need(value['inspection_events']==old['inspection_events'],'Tour actual qualified completions unchanged')
            order=lambda a:(a['time_s'],a['agent'])
            need(sorted(value['assignments'],key=order)==sorted(old['assignments'],key=order),'Tour physical task/path equality')
            legacy={'passed':True,'source_record_sha256':ref['record_sha256'],'old_scores_used_as_research_baseline':False}
        counts={}
        for d in value['local_decisions']:
            for c in d['candidates']:
                if not c['certificate']['ok']:
                    reason=c['certificate']['reason'];counts[reason]=counts.get(reason,0)+1
        row={'case_id':case['case_id'],'partition':case['partition'],'specification':case['specification'],
            'policy':p,'policy_id':policy_id(p),'evaluation_key':key,'execution_signature':signature,
            'source_manifest_sha256':sha(source/'snapshot-manifest.json'),'process_fingerprint':trace.fingerprint,
            'metrics':value['metrics'],'record_path':str(path),'record_sha256':sha(path),'action_sha256':value['action_sha256'],
            'audit':audit,'legacy_Tour_regression':legacy,'rejection_counts':counts,
            'actual_wall_seconds':time.perf_counter()-start,'job_id':os.environ['SLURM_JOB_ID']}
        write(area/'complete.json',row)
        print('EVALUATED',case['case_id'],p['method'],policy_id(p)[:8],row['metrics']['reordered_plans'],round(row['actual_wall_seconds'],3),flush=True)
        return row
    except BaseException as error:
        write(area/'failed.json',{'type':type(error).__name__,'error':str(error),'traceback':traceback.format_exc()});raise


def evaluate(root,source,cases,p,predictor):
    return {'policy':p,'policy_id':policy_id(p),'rows':[evaluate_one(root,source,c,p,predictor) for c in cases]}


def objective(result):
    r=result['rows']
    if not r or any(not v['audit']['passed'] or v['metrics']['numeric_scoring_failures'] for v in r):return None
    wait=[v['metrics']['consequence_weighted_censored_delay_s'] for v in r if v['metrics']['consequence_weighted_censored_delay_s'] is not None]
    return [statistics.mean(v['metrics']['missed_segments'] for v in r),statistics.mean(wait) if wait else 0.,
        statistics.mean(v['metrics']['travel_m'] for v in r),-sum(v['metrics']['completed_inspections'] for v in r)]


def retain(parent,candidate):
    a,b=objective(parent),objective(candidate)
    accepted=b is not None and (a is None or lower(b,a))
    return (candidate if accepted else parent),{'accepted':accepted,'parent_objective':a,'candidate_objective':b,
        'rule':'Global preregistered lexicographic, not every-condition dominance; ties parent'}


def gate(root,source,signature):
    area=root/'gate'/signature;area.mkdir(parents=True,exist_ok=False)
    suite=unittest.defaultTestLoader.discover(str(source/'tests'),pattern='test_local_*.py')
    with (area/'tests.txt').open('x') as f:r=unittest.TextTestRunner(stream=f,verbosity=2).run(suite)
    value={'passed':r.wasSuccessful() and not r.skipped,'tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skipped':len(r.skipped),'execution_signature':signature,'job_id':os.environ['SLURM_JOB_ID']}
    write(area/'complete.json',value);need(value['passed'],'Ledger/safety/expression gate')


def freeze(root,source):
    need((root/'S-complete.json').exists() and (root/'Q2-complete.json').exists(),'Freeze only after two sequential search rounds')
    s=read(root/'S-complete.json')['selected'];q=read(root/'Q2-complete.json')['selected']
    protocol=read(source/STAGE/'protocol.json');history=read(source/STAGE/'historical-identities.json')
    registration=read(root/'registration-at-freeze.json')
    occupied=set(history['seed_groups'])|set(registration['seed_groups']);seeds=[];i=43000
    while len(seeds)<2:
        if i not in occupied:seeds.append(i)
        i+=1
    cases=[]
    for seed in seeds:
        for family,duration in protocol['confirmation_rule']['families']:
            cases.append({'case_id':f'confirm-{len(cases):02d}','partition':'confirmation','specification':{
                'phase':'confirmation','seed':seed,'scenario':family,'duration_s':duration,'fault_start_s':520,
                'noise_c':.2,'estimator':'history','control':'feedback','resources':'provisioned','variant':'open'}})
    value={'execution_signature':verify(source),'selected_S':s['policy'],'selected_Q':q['policy'],
        'selected_S_id':s['policy_id'],'selected_Q_id':q['policy_id'],
        'confirmation_cases':cases,'confirmation_generated':False,'development_receipts':{
            name:sha(root/name) for name in ('baselines-complete.json','S-complete.json','Q1-complete.json','Q2-complete.json')},
        'registration_excluded_seed_groups':sorted(occupied),'model_call_count':len((root/'model-calls.jsonl').read_text().splitlines()) if (root/'model-calls.jsonl').exists() else 0,
        'registration_at_freeze_sha256':sha(root/'registration-at-freeze.json'),
        'selection_not_changeable_by_confirmation':True}
    write(root/'selection-frozen.json',value)


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--mode',choices=('pilot','baselines','simple','q1','q2','freeze','confirmation'),required=True);a=p.parse_args()
    need('SLURM_JOB_ID' in os.environ,'Real compute only in Slurm')
    source=Path(__file__).resolve().parents[1];root=a.root.resolve();root.mkdir(exist_ok=True);torch.set_num_threads(1)
    signature=verify(source);protocol=read(source/STAGE/'protocol.json');cases=protocol['development']
    if a.mode=='freeze':freeze(root,source);return
    if a.mode=='pilot':gate(root,source,signature)
    else:need(read(root/'gate'/signature/'complete.json')['passed'],'Exact kernel gate')
    predictor=frozen_predictor(CVAE,source/'research/2026-10-28-m111-coverage/frozen_estimator.json')
    initial=policy(BASE_EXPRESSION)
    if a.mode=='pilot':
        r=evaluate(root,source,cases[:1],policy(BASE_EXPRESSION,'T'),predictor)
        write(root/('cost-probe-'+signature[:12]+'.json'),{'actual':r,'projection_s_per_case':r['rows'][0]['actual_wall_seconds']})
    elif a.mode=='baselines':
        result={label:evaluate(root,source,cases,policy(BASE_EXPRESSION,label) if label!='R' else initial,predictor) for label in ('T','D','R')}
        write(root/'baselines-complete.json',result)
    elif a.mode=='simple':
        parent=read(root/'baselines-complete.json')['R'];archive=[parent];rounds=[]
        for index in range(2):
            expr='risk_delay + deadline_pressure + 0.05*travel_cost' if index==0 else '('+parent['policy']['score_expression']+') + 0.2*travel_cost'
            candidate=evaluate(root,source,cases,policy(expr),predictor);kept,selection=retain(parent,candidate)
            rounds.append({'round':index+1,'parent':parent,'candidate':candidate,'selection':selection,'retained':kept})
            archive.append(candidate);parent=kept
        write(root/'S-complete.json',{'rounds':rounds,'archive':archive,'selected':parent})
    elif a.mode in ('q1','q2'):
        index=1 if a.mode=='q1' else 2
        parent=read(root/'baselines-complete.json')['R'] if index==1 else read(root/'Q1-complete.json')['selected']
        proposal=root/f'Q{index}-proposal.json';candidate=None
        if proposal.exists():
            value=read(proposal);candidate=evaluate(root,source,cases,policy(value['score_expression']),predictor)
            selected,decision=retain(parent,candidate)
        else:selected=parent;decision={'accepted':False,'reason':'No legal expression within charged call slots'}
        write(root/f'Q{index}-complete.json',{'round':index,'parent':parent,'candidate':candidate,'selection':decision,'selected':selected})
    else:
        frozen=read(root/'selection-frozen.json');need(frozen['execution_signature']==signature,'Frozen confirmation kernel')
        for name,value in frozen['development_receipts'].items():need(sha(root/name)==value,'Frozen development selection receipts')
        methods={'T':policy(BASE_EXPRESSION,'T'),'D':policy(BASE_EXPRESSION,'D'),'R':initial,
            'selected_S':frozen['selected_S'],'selected_Q':frozen['selected_Q']}
        result={name:evaluate(root,source,frozen['confirmation_cases'],value,predictor) for name,value in methods.items()}
        write(root/'confirmation-complete.json',{'selection_frozen_sha256':sha(root/'selection-frozen.json'),'methods':result,
            'actual_confirmation_identities':len({v['policy_id'] for v in result.values()}),'logical_method_labels':5})


if __name__=='__main__':main()
