"""Two sequential frozen-Qwen edits from public actions and offline dev feedback.

This is an offline proposer. It cannot change the scheduler, safety kernel or
confirmation policy. Every generation, including malformed output, is charged.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import time

from patrol_rsi.local_score import (ScoreExpression, parse_response,
    require_mutation, response_contract, response_example)

MODEL=Path('/share/home/renly/renly-patrol-rsi/models/Qwen3-8B-b968826d')
METRICS=('missed_segments','consequence_weighted_censored_delay_s','travel_m',
    'service_s','completed_inspections','current_round_unfinished_obligations',
    'unfinished_committed_tasks','reordered_plans')


def concise(x):
    return round(x,4) if isinstance(x,float) else x


def short_scores(results):
    """Only anonymous development IDs; no seed/scenario/fault schedule fields."""
    return [{'case':case,**{label:[concise(v['metrics'][k]) for k in METRICS]
        for label,r in results.items() for v in r['rows'] if v['case_id']==case}}
        for case in sorted({v['case_id'] for r in results.values() for v in r['rows']})]


def case_objective(row):
    m=row['metrics']
    return [m['missed_segments'],m['consequence_weighted_censored_delay_s'] or 0.,
        m['travel_m'],-m['completed_inspections']]


def evidence_card(row,reference,load_record,category):
    current,old=load_record(row),load_record(reference)
    choices=sorted(current['local_decisions'],key=lambda d:(d['time_s'],d['agent']))
    peer={(d['time_s'],d['agent']):d for d in old['local_decisions']}
    # First observed difference in the declared case/time ordering, not a chosen
    # favorable event. If all decisions match, expose the first real decision.
    different=[d for d in choices if (d['time_s'],d['agent']) not in peer or
        d['selected_order']!=peer[(d['time_s'],d['agent'])]['selected_order']]
    d=(different or choices)[0]
    observed={(e['agent'],e['round_id'],e['task']):e['time_s'] for e in current['obligation_events']}
    previous={(e['agent'],e['round_id'],e['task']):e['time_s'] for e in old['obligation_events']}
    public={v['task']:v for v in d['public_tasks']}
    shifts=[]
    for shift in d['completion_deltas_vs_original']:
        j=shift['task'];p=public[j];key=(d['agent'],d['round_id'],j)
        if shift['delta_completion_s']==0 and j not in d['window']:continue
        actual=observed.get(key);prior=previous.get(key)
        shifts.append([j,concise(p['risk']),concise(p['freshness']),p['risk_value_source'],
            p['direct_age_s'],shift['delta_completion_s'],actual,
            actual-prior if actual is not None and prior is not None else None])
    return {'case':row['case_id'],'category':category,'time_s':d['time_s'],
        'agent':d['agent'],'round':d['round_id'],'window':d['window'],
        'selected':d['selected_order'],'legal_count':d['legal_permutations'],
        'reference_selected_at_same_time':peer.get((d['time_s'],d['agent']),{}).get('selected_order'),
        'different_actual_decision_observed':bool(different),
        'task_columns':['task','public_risk','freshness','source','direct_age_s',
            'planned_delta_vs_same_state_original_s','actual_finish_s','actual_delta_vs_reference_same_round_s'],
        'tasks':shifts,
        'offline_outcome':{'reference':[concise(reference['metrics'][k]) for k in METRICS],
            'current':[concise(row['metrics'][k]) for k in METRICS]},
        'interpretation':'Planned deltas use deterministic same-state geometry, not oracle outcomes. Actual peer deltas match agent/round/task across complete trajectories.'}


def feedback(current,reference,load_record):
    from patrol_rsi.reorder_execution import lower
    peers={v['case_id']:v for v in reference['rows']};categories={}
    for row in sorted(current['rows'],key=lambda v:v['case_id']):
        prior=peers[row['case_id']]
        category='degradation' if lower(case_objective(prior),case_objective(row)) else 'improved_or_unchanged'
        if category not in categories:categories[category]=evidence_card(row,prior,load_record,category)
    return {name:categories.get(name,'NOT OBSERVED in the six fixed development conditions; no case fabricated.')
        for name in ('improved_or_unchanged','degradation')}


def make_prompt(parent,baseline,first_round,load_record):
    contract=response_contract()
    # The same two-field definition supplies both the prompt and real parser.
    parse_response(json.dumps(response_example()))
    results={name:baseline[name] for name in ('T','D','R')}
    current,reference=baseline['R'],baseline['T']
    if first_round is not None:
        results['Q1_parent']=first_round['parent']
        if first_round['candidate'] is not None:results['Q1_child']=first_round['candidate']
        current=first_round['candidate'] or first_round['parent'];reference=first_round['parent']
    return {'task':'Modify the supplied parent pure scoring expression once. Lower score wins among safe permutations. Return a different expression, not the unchanged example.',
        'parent_expression':parent['policy']['score_expression'],
        'contract':contract,
        'public_feature_meanings':{
            'risk_delay':'Mean public weight*risk*(first future completion-now)/deadline over ALL owned tasks; public risk proxy is not calibrated probability.',
            'deadline_pressure':'Mean squared (first completion-last actual check)/deadline.',
            'deadline_peak':'Maximum (first completion-last actual check)/deadline.',
            'travel_cost':'Current local segment plus bridge travel seconds /300.',
            'freshness_delay':'Mean public weight*direct-readout age capped at300s (missing=1)*(first completion-now)/deadline.'},
        'immutable':'Only next<=3 unfinished obligations of the current round are permuted; full safety filters all delayed tasks and next cycle. No added checks, transfers, new tasks or safety edits. The original order can win.',
        'score_label':'OFFLINE SIMULATION DEVELOPMENT feedback. These anonymous six conditions are known development data. Online expressions cannot read any evaluation score.',
        'score_columns':list(METRICS),'all_six_condition_scores':short_scores(results),
        'actual_public_action_and_outcome_cases':feedback(current,reference,load_record),
        'selection':'Safety and numeric validity first; global mean missed segments, then mean censored wait over event conditions, then mean travel, then negative total completions, lexicographic; ties keep parent. Per-condition losses are retained and reported.',
        'first_round_result':None if first_round is None else {
            'tried_expression':first_round['candidate']['policy']['score_expression'] if first_round['candidate'] else None,
            'selection':first_round['selection'],'retained_expression':first_round['selected']['policy']['score_expression']},
        'instruction':'Return exactly one JSON OBJECT. Both score_expression and mechanism MUST be strings, never lists/objects. Use only declared feature names and operators, no Python code, markdown, future labels or extra keys. The example illustrates valid structure and is not a suggested new candidate. Explain expected effect on order and a possible cost in <=80 words.'}


def main():
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM
    from patrol_rsi.m12 import verify_open_model
    from run_local_reorder import (STAGE,verify,read,write,sha,need,record,
        reserve,validate_result)
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--round',type=int,choices=(1,2),required=True);a=p.parse_args()
    need('SLURM_JOB_ID' in os.environ and not torch.cuda.is_available(),'Frozen CPU Slurm proposer')
    source=Path(__file__).resolve().parents[1];root=a.root.resolve();index=a.round
    signature=verify(source);protocol=read(source/STAGE/'protocol.json');cases=protocol['development']
    need(read(root/'gate'/signature/'complete.json')['passed'],'Exact executed interface gate')
    need(not(root/'selection-frozen.json').exists(),'No proposals after selection freeze')
    baseline=read(root/'baselines-complete.json')
    for r in baseline.values():validate_result(r,signature,cases)
    need(any(v['metrics']['decision_points_with_alternative']>0 for r in baseline.values() for v in r['rows']),'Real nonoriginal legal permutations exist')
    first=None
    if index==2:
        first=read(root/'Q1-complete.json')
        for k in ('parent','selected'):validate_result(first[k],signature,cases)
        if first['candidate'] is not None:validate_result(first['candidate'],signature,cases)
    parent=baseline['R'] if index==1 else first['selected']
    need(not(root/f'Q{index}-proposal.json').exists(),'First legal proposal ends this round')
    call_path=root/'model-calls.jsonl'
    prior=[json.loads(line) for line in call_path.read_text().splitlines()] if call_path.exists() else []
    need(not any(v.get('round')==index for v in prior),'Do not resample a completed or interrupted proposal phase')
    allowed=min(2,4-len(prior)) if index==1 else 4-len(prior)
    need(allowed>0,'Global four-call cap')
    prompt=make_prompt(parent,baseline,first,record);prompt['prior_structural_failures']=[]
    area=root/f'model-round-{index}';area.mkdir(exist_ok=False)
    torch.set_num_threads(int(os.environ['SLURM_CPUS_PER_TASK']))
    verification=verify_open_model(MODEL)
    tokenizer=AutoTokenizer.from_pretrained(MODEL,local_files_only=True,trust_remote_code=False)
    model=AutoModelForCausalLM.from_pretrained(MODEL,torch_dtype=torch.float32,attn_implementation='eager',local_files_only=True,trust_remote_code=False).eval()
    need(all(v.dtype==torch.float32 and v.device.type=='cpu' for v in model.parameters()),'Unchanged CPUfloat32 model')
    versions=tuple(v._version for v in model.parameters())
    write(area/'startup.json',{'job_id':os.environ['SLURM_JOB_ID'],'model_verified':verification,
        'execution_signature':signature,'model_script_sha256':sha(Path(__file__)),
        'source_manifest_sha256':sha(source/'snapshot-manifest.json'),'dtype':'float32','device':'cpu','new_training':False,
        'feedback_Q1_receipt_sha256':sha(root/'Q1-complete.json') if index==2 else None})
    seen=[]
    if first is not None and first['candidate'] is not None:seen.append(ScoreExpression(first['candidate']['policy']['score_expression']).identity)
    for _ in range(allowed):
        rendered=tokenizer.apply_chat_template([{'role':'system','content':'Return exactly one JSON object: score_expression is a STRING containing a numeric expression; mechanism is a STRING. No markdown, lists or extra fields.'},
            {'role':'user','content':json.dumps(prompt,separators=(',',':'))}],tokenize=False,add_generation_prompt=True,enable_thinking=False)
        inputs=tokenizer(rendered,return_tensors='pt');count=int(inputs['input_ids'].numel())
        need(count<=4096,'Hard4096-token input cap; no generation or call charged if preflight fails')
        reservation=reserve(root,'model-calls',4,{'round':index,'parent_policy_id':parent['policy_id'],
            'execution_signature':signature,'model_script_sha256':sha(Path(__file__))})
        call=area/f"call-{reservation['number']:02d}";call.mkdir()
        write(call/'start.json',{'receipt':reservation,'prompt':prompt,'rendered_prompt':rendered,'input_tokens':count,
            'input_target':3072,'output_cap':256,'thinking':False,'decoder':'greedy','dtype':'float32'})
        begin=time.perf_counter();response=None;phase='generation'
        def timeout(signum,frame):raise TimeoutError('240s real generation timeout; call remains charged')
        previous=signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,240)
        try:
            with torch.inference_mode():generated=model.generate(**inputs,max_new_tokens=256,do_sample=False)
            response=tokenizer.decode(generated[0,count:],skip_special_tokens=True)
            write(call/'response.json',{'raw_response':response,'output_tokens':int(generated.shape[1]-count),'seconds':time.perf_counter()-begin})
            phase='parse_and_mutation'
            expression,mechanism=parse_response(response)
            require_mutation(expression,ScoreExpression(parent['policy']['score_expression']),seen)
            phase='persist_legal_child'
            need(tuple(v._version for v in model.parameters())==versions,'Frozen model weights')
            value={'score_expression':expression.source,'mechanism':mechanism,'round':index,
                'parent_policy_id':parent['policy_id'],'proposal_response_path':str(call/'response.json'),
                'proposal_response_sha256':sha(call/'response.json'),'execution_signature':signature,
                'source_manifest_sha256':sha(source/'snapshot-manifest.json'),'machine_repaired_expression':False}
            write(call/'accepted-interface.json',value);write(root/f'Q{index}-proposal.json',value)
            print('LEGAL_LOCAL_REORDER_CHILD',index,reservation['number'],expression.source,flush=True)
            return
        except Exception as error:
            write(call/'failed.json',{'type':type(error).__name__,'error':str(error),'raw_response':response,
                'seconds':time.perf_counter()-begin,'charged':True,'unknown_output_upper_bound':256,'phase':phase})
            prompt['prior_structural_failures'].append({'error':str(error),'failed_raw_response':response})
            if phase!='parse_and_mutation' or not isinstance(error,ValueError):
                write(area/'operational-stop.json',{'phase':phase,'error':str(error),'no_resampling_after_operational_failure':True})
                return
        finally:
            signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
    write(area/'no-legal-child.json',{'charged_calls':allowed,'failure_details':prompt['prior_structural_failures']})


if __name__=='__main__':main()
