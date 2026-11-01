"""At most two real Qwen calls using the existing compact changes/mechanism API."""
import argparse
import json
import os
from pathlib import Path
import signal
import time

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

from patrol_rsi.m12 import verify_open_model
from patrol_rsi.measurement_workflow import MeasurementWorkflow
from patrol_rsi.multistep_proposal import compile_compact
from run_measurement import STAGE, verify, rows, record, reserve, read, write, sha, need

MODEL=Path('/share/home/renly/renly-patrol-rsi/models/Qwen3-8B-b968826d')


def concise(value):
    return float(f'{value:.6g}') if isinstance(value,float) else value


def feedback(completed):
    scores=[];cards=[]
    for ordinal,case in enumerate(sorted({r['case_id'] for r in completed})):
        own=[r for r in completed if r['case_id']==case and r['arm'] in ('A','B','C')]
        if not own:continue
        scores.append({'case':f'dev-{ordinal:02d}', **{r['arm']:[concise(r['metrics'][k]) for k in
            ('missed_segments','consequence_weighted_censored_delay_s','travel_m','service_s','selected_detours')] for r in own}})
        current=record(next(r for r in own if r['arm']=='C'))
        context=current['first_post_measurement_context']
        if context is None:continue
        e=context['first_actual_event'];task=e['task']
        qualified=context['visible_state']['qualified'][str(task)]
        source_rows=context['masked_ranking'];after=context['visible_ranking']
        priority=[]
        ids=[]
        for ranking in (source_rows,after):
            ids += [v['task'] for v in ranking[:2]]
        for j in dict.fromkeys(ids):
            before=next(v for v in source_rows if v['task']==j);new=next(v for v in after if v['task']==j)
            priority.append({'task':j,'kind':new['kind'],'before_estimate':concise(before['estimate_at_finish']),
                'after_estimate':concise(new['estimate_at_finish']),'before_value':concise(before['value']),
                'after_value':concise(new['value']),'rank_before':before['rank'],'rank_after':new['rank'],
                'evidence':new['estimate_source'],'dependency':new['dependency']})
        cards.append({'case':f'dev-{ordinal:02d}','time_s':e['time_s'],'first_task':task,
            'first_kind':e['kind'],'actual_reference':e['measurement'],'observed_alarm':qualified['alarm'],
            'state_update':context['visible_state']['latest_update'], 'candidate_changes_same_current_state':priority,
            'actual_C_choice':context['actual_selected']})
    return scores,cards[:6]


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--root',type=Path,required=True);a=p.parse_args()
    need('SLURM_JOB_ID' in os.environ and not torch.cuda.is_available(),'Declared CPU Slurm execution')
    root,source=a.root.resolve(),a.source.resolve();signature=verify(source)
    gate=read(root/'gate'/signature/'complete.json');need(gate['passed'],'Interface/safety gate, no score gain gate')
    for group in ('old','new'):need(read(root/(group+'-paired.json'))['passed'],'Actual same-current-state pairing')
    completed=rows(root,signature)
    need(len([r for r in completed if r['arm'] in ('A','B','C')])==36,'All12developmentABC conditions')
    need(all(r['audit']['passed'] for r in completed),'Real completed safety audits')
    need(not(root/'child-workflow.json').exists(),'Only one legal child')
    area=root/'model-v4';area.mkdir(exist_ok=False)
    torch.set_num_threads(int(os.environ['SLURM_CPUS_PER_TASK']))
    verification=verify_open_model(MODEL)
    tokenizer=AutoTokenizer.from_pretrained(MODEL,local_files_only=True,trust_remote_code=False)
    model=AutoModelForCausalLM.from_pretrained(MODEL,torch_dtype=torch.float32,attn_implementation='eager',local_files_only=True,trust_remote_code=False).eval()
    need(all(v.dtype==torch.float32 for v in model.parameters()),'No precision downgrade')
    versions=tuple(v._version for v in model.parameters())
    write(area/'startup.json',{'device':'cpu','dtype':'float32','decoder':'greedy','model_verified':verification,
        'execution_signature':signature,'source_manifest_sha256':sha(source/'snapshot-manifest.json'),
        'model_script_sha256':sha(Path(__file__)),'job_id':os.environ['SLURM_JOB_ID'],'new_training':False})
    parent=MeasurementWorkflow();scores,cards=feedback(completed);failures=[]
    for _ in range(2):
        user={'task':'Propose one executable post-measurement workflow modification, not a geographic scope change.',
            'parent':parent.to_dict(),'raw_output_contract':{'changes':'ONE or TWO changed fields','mechanism':'Short explanation: public condition, affected estimates/tasks, why not equivalent'},
            'allowed_values':{'estimate_tool':['direct_priority','nominal_only'],
                'dependency_evidence':['physical','own_only'],'normal_followup':['positive_value','return_tour']},
            'semantics':'direct_priority uses fresh references ahead of old CVAE and a causal nominal forecast; nominal_only uses the nominal observer without CVAE residual in ranking. physical allows heat-balance residual as cooling-verification priority, own_only removes that diagnostic component. return_tour permanently skips further optional work after the first NORMAL actual reference; positive_value continues only if a safe task has positive net value. All tools retain the same clock; no double time stepping.',
            'immutable':'Exposure filter, safety, K=2, first diagnostic rule, physics, qualifications, owners, weights, score constants and evaluation.',
            'metadata':'Output exactly changes and mechanism; fixed schema and parent SHA are attached by the interface. No fields are repaired.',
            'score_label':'Completed SIMULATION DEVELOPMENT feedback. Online policy never reads scores. Null wait means no anomaly segment.',
            'score_columns':['missed_segments','weighted_censored_wait_s','travel_m','service_s','optional_checks'],
            'all_condition_scores':scores,'public_completed_feedback':cards,
            'parent_child_behavior_difference':{'current_child':'not_generated_yet','historical_fact':'Previous scope-only edit changed0of6actual trajectories; do not repeat equivalent scope changes.'},
            'instruction':'Explain which supplied public state activates the change and how it can change a task value or action. No positive human-result prerequisite. No code, extra keys, scope fields or hidden schedule. First legal nonduplicate child ends proposal sampling.',
            'prior_structural_failures':failures}
        dropped=0
        while True:
            rendered=tokenizer.apply_chat_template([{'role':'system','content':'Return exactly one JSON object with changes and mechanism. Use only supplied public development evidence. No markdown or Python.'},
                {'role':'user','content':json.dumps(user)}],tokenize=False,add_generation_prompt=True,enable_thinking=False)
            inputs=tokenizer(rendered,return_tensors='pt');count=int(inputs['input_ids'].numel())
            if count<=3072 or len(user['public_completed_feedback'])<=1:break
            user['public_completed_feedback'].pop();dropped+=1
        need(count<=4096,'Frozen input bound before generation')
        reservation=reserve(root,'model-calls',2,{'parent_sha256':parent.sha256,'source_manifest_sha256':sha(source/'snapshot-manifest.json')})
        call=area/f"call-{reservation['number']:02d}";call.mkdir()
        write(call/'start.json',{'receipt':reservation,'prompt':user,'rendered_prompt':rendered,'input_tokens':count,
            'output_cap':256,'thinking':False,'decoder':'greedy','dropped_last_cards':dropped,'dtype':'float32'})
        begin=time.perf_counter();response=None;phase='generation'
        def timeout(signum,frame):raise TimeoutError('240s actual generation timeout; call remains charged')
        previous=signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,240)
        try:
            with torch.inference_mode():generated=model.generate(**inputs,max_new_tokens=256,do_sample=False)
            response=tokenizer.decode(generated[0,count:],skip_special_tokens=True)
            write(call/'response.json',{'raw_response':response,'output_tokens':int(generated.shape[1]-count),'seconds':time.perf_counter()-begin})
            phase='compile_compact'
            child,envelope=compile_compact(response,parent)
            phase='persist_legal_child'
            need(tuple(v._version for v in model.parameters())==versions,'Frozen model parameters')
            write(call/'accepted-interface.json',{'workflow':child.to_dict(),'assembled_envelope':envelope,'raw_compact_valid':True,'raw_full_envelope_claimed':False})
            write(root/'child-workflow.json',{'workflow':child.to_dict(),'parent':parent.to_dict(),'parent_sha256':parent.sha256,
                'proposal_response_path':str(call/'response.json'),'proposal_response_sha256':sha(call/'response.json'),
                'source_manifest_sha256':sha(source/'snapshot-manifest.json'),'execution_signature':signature,'raw_contract':'compact-v1'})
            print('LEGAL_MEASUREMENT_CHILD',reservation['number'],child.to_dict(),flush=True)
            return
        except Exception as error:
            write(call/'failed.json',{'type':type(error).__name__,'error':str(error),'raw_response':response,
                'seconds':time.perf_counter()-begin,'charged':True,'unknown_output_upper_bound':256,'phase':phase})
            failures.append({'failure':str(error)})
            if phase!='compile_compact' or not isinstance(error,ValueError):
                write(root/'proposal-operational-stop.json',{'phase':phase,'error':str(error),'no_second_proposal_after_operational_failure':True})
                return
        finally:
            signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
    write(root/'proposal-failure.json',{'failures':failures,'no_extra_calls':True})


if __name__=='__main__':main()
