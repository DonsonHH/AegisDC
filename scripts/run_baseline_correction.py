"""Bounded development only. No confirmation reader or process generator."""
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

from patrol_rsi.baseline_correction import Rule,rule_from_dict
from patrol_rsi.correction_execution import execute_correction
from patrol_rsi.correction_selection import retain,vector,dominates,adopt
from patrol_rsi.multistep_workflow import digest
from patrol_rsi.limited_prediction import read,write,sha,need
from patrol_rsi.m9 import arrays_digest
from patrol_rsi.m11 import frozen_predictor
from run_multistep import reserve
from run_m12d_paired import StoredTrace,write_gz
from audit_m11 import independent_schedule,independent_events
from audit_local_reorder import audit_reorder

STAGE='research/2026-11-01-baseline-correction'
CVAE=Path('/share/home/renly/renly-patrol-rsi/runs/20261028-m111/frozen-estimator.pt')


def verify(source):
    m=read(source/'snapshot-manifest.json')
    for k,v in m['files'].items():need(sha(source/k)==v,'Source bytes: '+k)
    need(digest(m['execution_files'])==m['execution_signature'],'Actual kernel identity')
    return m['execution_signature']


def policy_id(p):return digest(p)


def record(row):
    path=Path(row['record_path']);need(sha(path)==row['record_sha256'],'Actual raw bytes')
    value=json.loads(gzip.decompress(path.read_bytes()))
    need(value['execution_signature']==row['execution_signature'] and value['case_id']==row['case_id'] and policy_id(value['policy'])==row['policy_id'],'Actual raw identity')
    return value


def validate(result,signature,cases):
    need(len(result['rows'])==6 and {v['case_id'] for v in result['rows']}=={c['case_id'] for c in cases},'Complete six development cases')
    for row in result['rows']:
        need(row['execution_signature']==signature and row['policy_id']==policy_id(result['policy']),'Result kernel/policy')
        case=next(c for c in cases if c['case_id']==row['case_id']);need(row['case_identity']==digest(case),'Fixed case identity');record(row)
    return result


def evaluate_one(root,source,case,policy,predictor,intervention=None):
    signature=verify(source)
    need(case in read(source/STAGE/'protocol.json')['development'],'Only six whitelisted development conditions')
    identity={'case':case,'policy':policy,'execution_signature':signature,'intervention':intervention}
    key=digest(identity)
    for file in sorted((root/'evaluations').glob('episode-*/complete.json')):
        cached=read(file)
        if cached['evaluation_key']==key:
            record(cached);trace=StoredTrace(Path(case['trace_folder']))
            need(trace.fingerprint==cached['process_fingerprint']==case['expected_fingerprint'],'Cache physical source')
            return cached
    receipt=reserve(root,'environment-attempts',60,{'case_id':case['case_id'],'policy':policy,'execution_signature':signature,'paired':intervention is not None})
    area=root/'evaluations'/f"episode-{receipt['number']:02d}";area.mkdir(parents=True,exist_ok=False);write(area/'attempt.json',receipt)
    start=time.perf_counter()
    try:
        trace=StoredTrace(Path(case['trace_folder']));need(trace.fingerprint==case['expected_fingerprint'],'Known physical process')
        spec=case['specification'];need(trace.seed==spec['seed'] and trace.scenario==spec['scenario'] and trace.config.fault_start_s==335,'Fixed six known conditions')
        before=arrays_digest(trace.arrays)
        with patch('patrol_rsi.improver_task.phased_trace',return_value=trace):value,env=execute_correction(spec,predictor,policy,intervention)
        need(arrays_digest(trace.arrays)==before,'Plant bytes unchanged')
        value.update(case_id=case['case_id'],execution_signature=signature,process_fingerprint=trace.fingerprint,
            source_manifest_sha256=sha(source/'snapshot-manifest.json'),intervention=intervention)
        path=area/'record.json.gz';write_gz(path,value)
        independent_schedule(value,env);independent_events(value,env);audit=audit_reorder(value,env)
        if policy['kind'] in ('T','R') and intervention is None:
            legacy=case['legacy_'+policy['kind']];old_path=Path(legacy['record_path'])
            need(sha(old_path)==legacy['record_sha256'],'Known development reference bytes')
            old=json.loads(gzip.decompress(old_path.read_bytes()))
            need(old['action_log']==value['action_log'] and old['inspection_events']==value['inspection_events'],'T/R original behavior regression')
        row={'case_id':case['case_id'],'partition':'development','policy':policy,'policy_id':policy_id(policy),
            'evaluation_key':key,'case_identity':digest(case),'execution_signature':signature,
            'source_manifest_sha256':sha(source/'snapshot-manifest.json'),'process_fingerprint':trace.fingerprint,
            'record_path':str(path),'record_sha256':sha(path),'action_sha256':value['action_sha256'],
            'metrics':value['metrics'],'audit':audit,'intervention':intervention,
            'actual_wall_seconds':time.perf_counter()-start,'job_id':os.environ['SLURM_JOB_ID']}
        record(row);write(area/'complete.json',row)
        print('ACTUAL',receipt['number'],case['case_id'],policy['kind'],'pair' if intervention else 'full',value['metrics']['reordered_plans'],flush=True)
        return row
    except BaseException as exc:
        write(area/'failed.json',{'type':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc()});raise


def evaluate(root,source,cases,policy,predictor):
    return {'policy':policy,'policy_id':policy_id(policy),'rows':[evaluate_one(root,source,c,policy,predictor) for c in cases]}


def make_roots(tour):
    roots=[]
    for row in tour['rows']:
        value=record(row);choices=value['root_candidates'];chosen=choices.get('positive',choices.get('zero'))
        roots.append({'case_id':row['case_id'],'root':chosen,'tour_record_sha256':row['record_sha256'],
            'absent_reason':'No legal nonoriginal Tour root' if chosen is None else None})
    return {'roots':roots,'selected_before_branch_results':True,'rule':'First public positive root in(time,agent), else first zero root; original R alternative.'}


def run_pairs(root,source,cases,predictor):
    frozen=read(root/'roots-frozen.json');paired=[]
    for item in frozen['roots']:
        c=next(c for c in cases if c['case_id']==item['case_id']);r=item['root']
        if r is None:paired.append(item);continue
        outputs={}
        for arm,order in [('A',r['window']),('B',r['alternative_order'])]:
            intervention={k:r[k] for k in ('time_s','agent','round_id','window','state_sha256','prefix_action_sha256')}
            intervention['execute_order']=order
            outputs[arm]=evaluate_one(root,source,c,{'kind':'T'},predictor,intervention)
        a,b=record(outputs['A']),record(outputs['B'])
        need(a['intervention_verified']['state_sha256']==b['intervention_verified']['state_sha256']==r['state_sha256'],'Actual paired complete state')
        need(a['intervention_verified']['prefix_action_sha256']==b['intervention_verified']['prefix_action_sha256']==r['prefix_action_sha256'],'Actual paired prefix')
        tour=record(next(v for v in read(root/'baselines-complete.json')['T']['rows'] if v['case_id']==c['case_id']))
        need(a['action_log']==tour['action_log'] and a['inspection_events']==tour['inspection_events'],'A is genuine Tour regression')
        fields=('missed_segments','consequence_weighted_censored_delay_s','travel_m','service_s','completed_inspections','current_round_unfinished_obligations','tasks_violating_exact_gap')
        delta={k:b['metrics'][k]-a['metrics'][k] if a['metrics'][k] is not None else None for k in fields}
        av=[a['metrics']['missed_segments'],a['metrics']['consequence_weighted_censored_delay_s'] or 0.,a['metrics']['travel_m']]
        bv=[b['metrics']['missed_segments'],b['metrics']['consequence_weighted_censored_delay_s'] or 0.,b['metrics']['travel_m']]
        category='keep_baseline' if dominates(av,bv) else 'support_change' if dominates(bv,av) else 'tradeoff' if av!=bv else 'no_difference'
        paired.append({**item,'A':outputs['A'],'B':outputs['B'],'B_minus_A':delta,'category':category,
            'prefix_verified':True,'root_sha256':digest(r)})
    write(root/'pairs-complete.json',{'frozen_roots_sha256':sha(root/'roots-frozen.json'),'pairs':paired})


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--mode',choices=('pilot','baselines','pairs','human','simple','q1','q2','finish'),required=True);a=p.parse_args()
    need('SLURM_JOB_ID' in os.environ,'Compute through Slurm')
    source=Path(__file__).resolve().parents[1];root=a.root.resolve();root.mkdir(exist_ok=True);torch.set_num_threads(1)
    signature=verify(source);cases=read(source/STAGE/'protocol.json')['development']
    if a.mode=='pilot':
        gate=root/'gate'/signature;gate.mkdir(parents=True,exist_ok=False)
        suite=unittest.defaultTestLoader.discover(str(source/'tests'),pattern='test_baseline_correction.py')
        with (gate/'tests.txt').open('x') as f:test=unittest.TextTestRunner(stream=f,verbosity=2).run(suite)
        write(gate/'complete.json',{'passed':test.wasSuccessful() and not test.skipped,'tests':test.testsRun,'execution_signature':signature})
        need(test.wasSuccessful() and not test.skipped,'Contract and baseline semantics gate')
    else:need(read(root/'gate'/signature/'complete.json')['passed'],'Exact kernel tests')
    predictor=frozen_predictor(CVAE,source/'research/2026-10-28-m111-coverage/frozen_estimator.json')
    if a.mode=='pilot':
        result=evaluate(root,source,cases[:1],{'kind':'T'},predictor);write(root/'cost-probe.json',result)
    elif a.mode=='baselines':
        values={k:evaluate(root,source,cases,{'kind':k},predictor) for k in ('T','R')}
        write(root/'baselines-complete.json',values);write(root/'roots-frozen.json',make_roots(values['T']))
    elif a.mode=='pairs':run_pairs(root,source,cases,predictor)
    elif a.mode=='human':
        need((root/'pairs-complete.json').exists(),'Actual paired feedback first')
        write(root/'H-complete.json',evaluate(root,source,cases,{'kind':'correction','rule':Rule().to_dict()},predictor))
    elif a.mode=='simple':
        refs=read(root/'baselines-complete.json');parent=validate(read(root/'H-complete.json'),signature,cases);rounds=[]
        for index in (1,2):
            changed=deepcopy(parent['policy']['rule'])
            if index==1:changed['source_weights']['cross']=.5
            else:changed['travel_penalty']=.2
            candidate=evaluate(root,source,cases,{'kind':'correction','rule':rule_from_dict(changed).to_dict()},predictor)
            selected,decision=retain(parent,candidate,refs);rounds.append({'round':index,'parent':parent,'candidate':candidate,'selection':decision,'selected':selected});parent=selected
        write(root/'S-complete.json',{'rounds':rounds,'selected':parent})
    elif a.mode in ('q1','q2'):
        index=1 if a.mode=='q1' else 2;refs=read(root/'baselines-complete.json')
        parent=validate(read(root/'H-complete.json') if index==1 else read(root/'Q1-complete.json')['selected'],signature,cases)
        proposal=root/f'Q{index}-proposal.json';candidate=None
        if proposal.exists():
            proposed=read(proposal);need(proposed['execution_signature']==signature and proposed['parent_policy_id']==parent['policy_id'],'Exact model proposal parent/kernel')
            candidate=evaluate(root,source,cases,{'kind':'correction','rule':rule_from_dict(proposed['rule']).to_dict()},predictor)
            selected,decision=retain(parent,candidate,refs)
        else:selected=parent;decision={'accepted':False,'reason':'No legal nonduplicate child in billed slots'}
        write(root/f'Q{index}-complete.json',{'round':index,'parent':parent,'candidate':candidate,'selection':decision,'selected':selected})
    else:
        refs=read(root/'baselines-complete.json');h=validate(read(root/'H-complete.json'),signature,cases);s=read(root/'S-complete.json');q=[read(root/f'Q{i}-complete.json') for i in (1,2)]
        archive={'H':h,**{f'S{r["round"]}':validate(r['candidate'],signature,cases) for r in s['rounds']},
            **{f'Q{r["round"]}':validate(r['candidate'],signature,cases) for r in q if r['candidate'] is not None}}
        write(root/'study-complete.json',{'execution_signature':signature,'archive':archive,'references':refs,
            'formal_adoption':adopt(refs['T'],{**archive,'R':refs['R']}),'finished_within_development_only':True,
            'receipt_sha256':{name:sha(root/name) for name in ('roots-frozen.json','pairs-complete.json','H-complete.json','S-complete.json','Q1-complete.json','Q2-complete.json')}})


if __name__=='__main__':main()
