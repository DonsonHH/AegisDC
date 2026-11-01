"""Use the final authorized slot for actual child2, preserving all failed phase records."""
import argparse
import os
from pathlib import Path
import torch

from run_baseline_correction import (STAGE,verify,read,write,sha,need,validate,record,evaluate,CVAE,frozen_predictor)
from patrol_rsi.baseline_correction import rule_from_dict
from patrol_rsi.correction_selection import retain,adopt


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args()
    need('SLURM_JOB_ID' in os.environ,'Slurm only')
    source=Path(__file__).resolve().parents[1];root=a.root.resolve();sig=verify(source)
    need(read(root/'Q1-complete.json')['candidate'] is None,'Recovery is only for an initial failed phase, never a third actual candidate')
    cases=read(source/STAGE/'protocol.json')['development'];refs=read(root/'baselines-complete.json')
    for v in refs.values():validate(v,sig,cases)
    first=read(root/'Q2-complete.json');need(first['candidate'] is not None,'C1 actual six-condition evaluation required')
    for k in ('parent','candidate','selected'):validate(first[k],sig,cases)
    parent=first['selected'];candidate=None
    proposal=root/'Q3-proposal.json'
    if proposal.exists():
        proposed=read(proposal);need(proposed['parent_policy_id']==parent['policy_id'] and proposed['execution_signature']==sig,'C2 binds retained C1 kernel/parent')
        torch.set_num_threads(1);predictor=frozen_predictor(CVAE,source/'research/2026-10-28-m111-coverage/frozen_estimator.json')
        candidate=evaluate(root,source,cases,{'kind':'correction','rule':rule_from_dict(proposed['rule']).to_dict()},predictor)
        selected,decision=retain(parent,candidate,refs)
    else:selected=parent;decision={'accepted':False,'reason':'Final authorized call did not produce a legal child2'}
    second={'actual_candidate_slot':2,'parent':parent,'candidate':candidate,'selection':decision,'selected':selected,
        'previous_actual_candidate_receipt_sha256':sha(root/'Q2-complete.json')}
    write(root/'C2-complete.json',second)
    h=validate(read(root/'H-complete.json'),sig,cases);s=read(root/'S-complete.json')
    archive={'H':h,**{f'S{v["round"]}':validate(v['candidate'],sig,cases) for v in s['rounds']},'C1':first['candidate']}
    if candidate is not None:archive['C2']=candidate
    names={'C1':'Q1','C2':'Q2'}
    conventional={names.get(k,k):v for k,v in archive.items()};raw_adoption=adopt(refs['T'],{**conventional,'R':refs['R']})
    reverse={'Q1':'C1','Q2':'C2'}
    adoption={**raw_adoption,'selected':reverse.get(raw_adoption['selected'],raw_adoption['selected']),
        'eligible_in_fixed_order':[reverse.get(k,k) for k in raw_adoption['eligible_in_fixed_order']],
        'actual_candidate_order':'H,S1,S2,C1,C2; R reference only'}
    receipt_names=('roots-frozen.json','pairs-complete.json','H-complete.json','S-complete.json','Q1-complete.json','Q2-complete.json','C2-complete.json','study-complete.json')
    write(root/'actual-chain-complete.json',{'execution_signature':sig,'archive':archive,'references':refs,
        'actual_candidate_chain':[{'label':'C1','proposal_phase':2,'step':first},{'label':'C2','proposal_phase':3,'step':second}],
        'phase_history':{'Q1':read(root/'Q1-complete.json'),'Q2':first},'formal_adoption':adoption,
        'conventional_adoption':raw_adoption,'receipt_sha256':{n:sha(root/n) for n in receipt_names},
        'execution_adjustment':'First two H duplicates were failures, not evaluated candidates. Call3 C1 was evaluated; last globally authorized call4 attempts C2 with actual C1 feedback. At most2 evaluated model candidates,4calls,60episodes; old phase files untouched.'})


if __name__=='__main__':main()
