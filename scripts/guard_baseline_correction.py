"""Official stage entry: validate immutable current inputs without changing rollout code."""
import argparse
from copy import deepcopy
from pathlib import Path

from run_baseline_correction import (STAGE,verify,read,write,sha,need,validate,make_roots,main as run_stage)


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--mode',required=True);a=p.parse_args()
    root=a.root.resolve();source=Path(__file__).resolve().parents[1];sig=verify(source);cases=read(source/STAGE/'protocol.json')['development']
    inputs={}
    def result(name):
        value=read(root/name);inputs[name]=sha(root/name);return value
    if a.mode not in ('pilot','baselines'):
        refs=result('baselines-complete.json')
        for value in refs.values():validate(value,sig,cases)
        roots=result('roots-frozen.json')
        need(roots==make_roots(refs['T']),'Roots bound to actual current Tour, pool, state and prefix')
    if a.mode in ('human','simple','q1','q2','finish'):
        paired=result('pairs-complete.json');need(paired['frozen_roots_sha256']==sha(root/'roots-frozen.json'),'Pairs frozen-root receipt')
        for item in paired['pairs']:
            if item['root'] is not None:
                for arm in ('A','B'):
                    row=item[arm];need(row['execution_signature']==sig,'Paired source kernel')
                    need(row['case_identity']==next(v['case_identity'] for v in refs['T']['rows'] if v['case_id']==row['case_id']),'Paired case identity')
        labels=result('pair-classification.json');need(labels['raw_pairs_sha256']==sha(root/'pairs-complete.json'),'Explicit derived Pareto labels bind untouched raw pairs')
    if a.mode in ('simple','q1','q2','finish'):validate(result('H-complete.json'),sig,cases)
    if a.mode in ('q1','q2','finish'):
        for step in result('S-complete.json')['rounds']:
            for key in ('parent','candidate','selected'):validate(step[key],sig,cases)
    if a.mode in ('q2','finish'):
        for name in (('Q1-complete.json',) if a.mode=='q2' else ('Q1-complete.json','Q2-complete.json')):
            step=result(name)
            for key in ('parent','selected'):validate(step[key],sig,cases)
            if step['candidate'] is not None:validate(step['candidate'],sig,cases)
    run_stage()
    if a.mode=='pairs':
        paired=read(root/'pairs-complete.json');labels={}
        for item in paired['pairs']:
            if item['root'] is None:continue
            ds=item['B_minus_A'];equivalent=all(abs(ds[k] or 0.)<=1e-9 for k in ('missed_segments','consequence_weighted_censored_delay_s','travel_m'))
            labels[item['case_id']]='no_difference' if equivalent else item['category']
        write(root/'pair-classification.json',{'raw_pairs_sha256':sha(root/'pairs-complete.json'),'labels':labels,
            'note':'Derived tolerance-aware classification; original raw branch results not rewritten. All3 differences<=1e-9 means equivalent.'})
    write(root/f'guard-{a.mode}-complete.json',{'execution_signature':sig,'script_sha256':sha(Path(__file__)),
        'source_manifest_sha256':sha(source/'snapshot-manifest.json'),'validated_input_receipts':inputs,
        'new_numeric_rollout_kernel':False,'completed_stage':a.mode})


if __name__=='__main__':main()
