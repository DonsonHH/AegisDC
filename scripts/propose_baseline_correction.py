"""Fixed Qwen proposes only declared source/gate parameters from paired dev feedback."""
import argparse
import json
import os
import re
from pathlib import Path
import signal
import time

from patrol_rsi.baseline_correction import (Rule,rule_from_dict,parse_response,require_mutation,response_contract,response_example)
from patrol_rsi.multistep_workflow import digest
from patrol_rsi.local_score import ScoreExpression,BASE_EXPRESSION

MODEL=Path('/share/home/renly/renly-patrol-rsi/models/Qwen3-8B-b968826d')
COLUMNS=('missed_segments','consequence_weighted_censored_delay_s','travel_m','service_s',
    'completed_inspections','current_round_unfinished_obligations','unfinished_committed_tasks','numeric_scoring_failures')


def short(x):return float(f'{x:.5g}') if isinstance(x,float) else x
def metrics(row):return [short(row['metrics'][k]) for k in COLUMNS]


def parse_model_response(raw):
    rule,mechanism=parse_response(raw)
    value=rule.to_dict()
    # Numeric representation only: -0.0==0.0 exactly. No value clipping,
    # field completion, inferred coefficients or semantic repair is allowed.
    value['source_weights']={k:0.0 if v==0 else v for k,v in value['source_weights'].items()}
    for k in ('travel_penalty','deadline_penalty','margin'):
        if value[k]==0:value[k]=0.0
    return rule_from_dict(value),mechanism


def paired_feedback(value):
    frames={};cards=[];mappings={}
    for n,pair in enumerate(value['pairs']):
        if pair['root'] is None:cards.append({'case':'c'+str(n),'no_root':True});continue
        root=pair['root'];rows=root['public_tasks'];ids={row['task']:'t'+str(k) for k,row in enumerate(rows)}
        # AisleGraph sorts by profession: thermal0:128, electrical128:144,
        # cooling144:160, control160:176. It is not pod-interleaved.
        podof=lambda row:row['task']//8 if row['kind']=='thermal' else row['task']-{'electrical':128,'cooling':144,'control':160}[row['kind']]
        pods={p:'p'+str(k) for k,p in enumerate(sorted({podof(row) for row in rows}))}
        mappings['c'+str(n)]={'tasks':ids,'pods':pods,'original_agent':root['agent']}
        frame=[]
        for row in rows:
            components=[]
            for c in row['evidence_components']:
                # Contributor counts + local rack labels preserve max-pool/source
                # relationships; never transfer raw rack IDs into the prompt.
                contributors=[]
                for v in c['contributors']:
                    rack=v['rack'];pod=rack//8
                    if pod not in pods:pods[pod]='p'+str(len(pods))
                    contributors.append([pods[pod]+'.r'+str(rack%8),v.get('group'),v.get('time_s')])
                components.append([c['name'],c['group'],short(c['value']),c['time_s'],c['age_s'],c['source'],contributors])
            frame.append([ids[row['task']],row['kind'],pods[podof(row)],short(row['risk']),row['direct_age_s'],
                row['value_output_time_s'],components])
        frame_id='e'+str(len(frames));ident=digest(frame)
        previous=next((name for name,v in frames.items() if digest(v)==ident),None)
        if previous is None:frames[frame_id]=frame
        else:frame_id=previous
        orig=next(c for c in root['candidate_pool'] if c['original']);alt=next(c for c in root['candidate_pool'] if c['order']==root['alternative_order'])
        f0=orig['certificate']['first_completion_s'];f1=alt['certificate']['first_completion_s']
        get=lambda d,j:d[str(j)] if str(j) in d else d[j]
        shifts=[[ids[row['task']],get(f1,row['task'])-get(f0,row['task']),
            root['round_id']+(row['task'] not in orig['certificate']['remaining_before'])] for row in rows]
        cards.append({'case':'c'+str(n),'time_s':root['time_s'],'actor':'u0','round':root['round_id'],
            'evidence':frame_id,'original':[ids[j] for j in root['window']],
            'alternative':[ids[j] for j in root['alternative_order']],
            'planned_shifts_task_delta_s_target_round':shifts,
            'actual_A':metrics(pair['A']),'actual_B':metrics(pair['B']),
            'actual_B_minus_A_exact_before_display':[short(pair['B']['metrics'][k]-pair['A']['metrics'][k]) if pair['A']['metrics'][k] is not None else None for k in COLUMNS],
            'category':pair['category'],'R_prefers_B':ScoreExpression(BASE_EXPRESSION).evaluate(alt['features'])<ScoreExpression(BASE_EXPRESSION).evaluate(orig['features'])-1e-9,
            'paired_prefix_verified':pair['prefix_verified']})
    return {'evidence_columns':['task','profession','pod','original_public_risk','direct_age_s','estimate_output_s','components'],
        'component_columns':['name','group','value_or_null','time_s','age_s','source','max_or_power_contributors'],
        'evidence_frames':frames,'paired_cards':cards},mappings


def prompt_data(baselines,h,pairs,first):
    feedback,mapping=paired_feedback(pairs)
    results={'T':baselines['T'],'R':baselines['R'],'H':h}
    if first is not None:
        results['Q1_parent']=first['parent']
        if first['candidate'] is not None:results['Q1_child']=first['candidate']
    parent=h if first is None else first['selected']
    data={'task':'Modify the parent rule once. Keep Tour unless public weighted risk gain and penalized advantage are positive.',
        'parent':parent['policy']['rule'],'contract':response_contract(),
        'formula':'rho=clip(sum(nonnegative source_weight*freshness*known existing component),0,4); G=mean(weight*rho*(F_original-F_candidate)/deadline) over ALL owned tasks. advantage=G-travel_penalty*max(delta_travel/300s,0)-deadline_penalty*max(delta_mean_squared_age_ratio,0). Change only if G>1e-9 and advantage>margin+1e-9. Otherwise original. Safe pool external.',
        'source_semantics':'direct=qualified or telemetry own signal; model=frozen CVAE own temperature; power=public supply/demand proxy; cross=same-pod thermal proxy. Unknown null is not normal and is excluded, not calibrated probability. Source/time belong to each component. No positive qualified alarm prerequisite.',
        'freshness_semantics':'flat=1 for known components; linear300=max(0,1-age/300s). Costs cannot be negative. Existing physics thresholds and safety cannot change.',
        'feedback_label':'OFFLINE SIMULATION DEVELOPMENT only: true single-intervention paired branches share prefix/state then correctly restore Tour. Not oracle actions or generalization data. Future observations never backfilled.',
        'score_columns':list(COLUMNS),'six_condition_full_rollouts':[
            {'case':'c'+str(i),**{name:metrics(result['rows'][i]) for name,result in results.items()}} for i in range(6)],
        **feedback,
        'parent_selection':'Child must Pareto-dominate parent on mean missed/wait/travel and not be dominated by T/R; otherwise keep parent and archive tradeoff. Formal default remains T unless strict qualification. Healthy wait is null, not zero.',
        'Q1_actual_result':None if first is None else {'decision':first['selection'],
            'tried_rule':first['candidate']['policy']['rule'] if first['candidate'] else None,
            'retained_rule':first['selected']['policy']['rule']},
        'instruction':'Return the exact JSON object with all six fields. source_weights is an object, mechanism a string <=12 English words. Do not copy the unchanged example or any evaluated rule. No markdown, additional keys or code. No repair is applied.'}
    return data,mapping


def compact_tables(data):
    """Factor repeated provenance strings/tuples; retain every task/component."""
    names=[];origins=[];source_names=[];group_names=[]
    def index(value,table):
        if value not in table:table.append(value)
        return table.index(value)
    for frame in data['evidence_frames'].values():
        for row in frame:
            new=[]
            for name,group,value,stamp,age,source,contributors in row[-1]:
                grouped={}
                for location,subgroup,subtime in contributors:
                    pod,rack=location.split('.r');key=(pod,subgroup,subtime)
                    grouped.setdefault(key,[]).append(int(rack))
                compressed=[[pod,indices,subgroup,subtime] for (pod,subgroup,subtime),indices in grouped.items()]
                origin=index([index(group,group_names),stamp,index(source,source_names),compressed],origins)
                new.append([index(name,names),value,origin])
            row[-1]=new
    data['component_names']=names;data['origins_group_time_source_contributors']=origins
    data['origin_group_names']=group_names;data['origin_source_names']=source_names
    data['component_columns']=['name_index','value_or_null','origin_index']
    data['provenance_note']='Origin=[group_index,time_s,source_index,contributors]. Contributors=[pod,local_rack_indices,group,time]; grouped equal origins preserve all members. Age=paired current time minus origin time; task direct age separate.5-significant-digit display; deltas calculated before rounding and Pareto uses full precision.'
    for card in data['paired_cards']:
        if card.get('no_root'):continue
        card.pop('actual_A');card.pop('actual_B')
        card['actual_A_ref']='T rollout in six_condition_full_rollouts; actual A was action/measurement verified identical.'
        card['actual_B_minus_A']=card.pop('actual_B_minus_A_exact_before_display')
    return data


def render_user(data):
    """Human-readable column text, not opaque compression; all six cards retained."""
    dumps=lambda x:json.dumps(x,separators=(',',':'))
    def rule_text(rule):
        base=Rule().to_dict();diff=[]
        for k,v in rule.items():
            if k=='source_weights':diff.extend(s+'='+str(w) for s,w in v.items() if w!=base[k][s])
            elif v!=base[k]:diff.append(k+'='+str(v))
        return 'H' if not diff else 'H except '+','.join(diff)
    lines=['Return one complete JSON object, all6 fields. mechanism<=12 English words. No markdown/code/extra fields.',
        'Example shape (already evaluated; do NOT copy):'+dumps(response_example()),
        'Domains: each source weight in[0,.5,1,2], not all0; freshness flat|linear300; penalties in[0,.05,.2,1]; margin in[0,.001,.01]. Same numeric values including -0 share identity.',
        'Parent:'+rule_text(data['parent']),
        'Already evaluated, forbidden duplicates:'+';'.join(rule_text(v) for v in data.get('already_evaluated_rules_no_resubmission',[])),
        data['formula'],data['source_semantics'],data['freshness_semantics'],
        'OFFLINE DEVELOPMENT: A/B are real single interventions from identical state/prefix, then restore Tour. No new validation. Unknown is not normal; proxy is not fault confirmation.',
        'Pareto parent update only if dominates parent in missed/wait/travel and not dominated by T/R. Tradeoffs archived, not formal progress; T remains reliable default.',
        'Metric vector M=missed,W=weighted censored wait(null healthy),C=travel m,V=service s,N=completions,U=remaining,P=pending,E=numeric errors. Order M,W,C,V,N,U,P,E.']
    profiles=[]
    for row in data['six_condition_full_rollouts']:
        for k,v in row.items():
            if k!='case' and v[2:] not in profiles:profiles.append(v[2:])
    lines.append('Cost profiles k(index)=C,V,N,U,P,E: '+';'.join('k'+str(i)+'='+','.join(str(v) for v in values) for i,values in enumerate(profiles)))
    lines.append('Cohort entries method=M,W,cost_profile:')
    for row in data['six_condition_full_rollouts']:
        lines.append(row['case']+' '+ ' '.join(k+'='+str(val[0])+','+('-' if val[1] is None else str(val[1]))+',k'+str(profiles.index(val[2:])) for k,val in row.items() if k!='case'))
    lines.append('Component names n(index):'+','.join(f'{i}={s}' for i,s in enumerate(data['component_names'])))
    lines.append('Source names s(index):'+','.join(f'{i}={s}' for i,s in enumerate(data['origin_source_names'])))
    needed={k:set() for k in data['evidence_frames']}
    for card in data['paired_cards']:
        if not card.get('no_root'):
            needed[card['evidence']].update(t for t,delta,_ in card['planned_shifts_task_delta_s_target_round'] if delta!=0)
    used={origin for name,frame in data['evidence_frames'].items() for row in frame if row[0] in needed[name] for _,_,origin in row[-1]}
    display_origins=[];origin_alias={}
    for i,(group,stamp,source,contributors) in enumerate(data['origins_group_time_source_contributors']):
        if i not in used:continue
        origin=[group,stamp,source]
        if origin not in display_origins:display_origins.append(origin)
        origin_alias[i]=display_origins.index(origin)
    lines.append('Origin o=group,time_s,source. Component age=case time-origin time. Cross/pod-power refer to task pod below; cross time is oldest max contributor. Individual rack-member details are in raw audit, not this prompt. ?=unknown.')
    for i,(group,stamp,source) in enumerate(display_origins):lines.append(f'o{i} {data["origin_group_names"][group]},{stamp if stamp is not None else "?"},s{source}')
    lines.append('Evidence rows: task profession pod old_public_risk direct_readout_age estimate_output_time n:value@origin. ?=unknown, never normal. All tasks with nonzero planned shifts included. Unchanged tasks have zero gain contribution for any weights, not assumed normal; their IDs/shifts remain listed. Full snapshots preserved outside prompt.')
    for name,frame in data['evidence_frames'].items():
        lines.append(name+':')
        for task,profession,pod,risk,direct_age,outtime,components in frame:
            if task not in needed[name]:continue
            parts=' '.join(f'n{n}:{value if value is not None else "?"}@o{origin_alias[origin]}' for n,value,origin in components)
            lines.append(f'{task} {profession} {pod} {risk} {direct_age if direct_age is not None else "?"} {outtime if outtime is not None else "?"} '+parts)
    lines.append('Paired cases: A=actual T above (verified action/measurement equality). B-A vector is actual complete-episode difference, calculated before display rounding. Planned shifts positive=delay, include other tasks, task:seconds:target_round.')
    for card in data['paired_cards']:
        if card.get('no_root'):lines.append(card['case']+' no legal root');continue
        groups={}
        for task,seconds,r in card['planned_shifts_task_delta_s_target_round']:groups.setdefault(r,[]).append(f'{task}:{seconds}')
        shifts=' '.join('round'+str(r)+'='+','.join(items) for r,items in groups.items())
        lines.append(f'{card["case"]} time={card["time_s"]} {card["evidence"]} u0 round={card["round"]} '+
            'A='+','.join(card['original'])+' B='+','.join(card['alternative'])+' shifts '+shifts+
            ' B-A='+','.join('-' if x is None else str(x) for x in card['actual_B_minus_A'])+
            ' '+card['category']+' R_prefers_B='+str(card['R_prefers_B']))
    if data.get('Q1_actual_result') is not None:lines.append('Q1 actual result and retained parent:'+dumps(data['Q1_actual_result']))
    if 'Q1_first_actual_numeric_failure' in data:lines.append('Q1 first numerical error:'+dumps(data['Q1_first_actual_numeric_failure']))
    if 'Q1_behavior_feedback' in data:lines.append('Q1 actual behavior changes:'+dumps(data['Q1_behavior_feedback']))
    if data.get('structural_failures'):lines.append('Previous billed invalid/duplicate outputs:'+dumps(data['structural_failures']))
    return re.sub(r'(?<![\w.])(-?\d+)\.0(?![\w.])',r'\1','\n'.join(lines))


def main():
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM
    from patrol_rsi.m12 import verify_open_model
    from run_baseline_correction import (STAGE,verify,read,write,sha,need,validate,record,reserve)
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--round',type=int,choices=(1,2),required=True);p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
    need('SLURM_JOB_ID' in os.environ and not torch.cuda.is_available(),'Frozen CPU Slurm proposer')
    root=a.root.resolve();source=Path(__file__).resolve().parents[1];sig=verify(source);cases=read(source/STAGE/'protocol.json')['development'];index=a.round
    baselines=read(root/'baselines-complete.json');h=validate(read(root/'H-complete.json'),sig,cases)
    for r in baselines.values():validate(r,sig,cases)
    pairs=read(root/'pairs-complete.json');need(pairs['frozen_roots_sha256']==sha(root/'roots-frozen.json'),'Paired root freeze binding')
    labels=read(root/'pair-classification.json');need(labels['raw_pairs_sha256']==sha(root/'pairs-complete.json'),'Explicit derived labels binding')
    for item in pairs['pairs']:
        if item['root'] is not None:item['category']=labels['labels'][item['case_id']]
    first=read(root/'Q1-complete.json') if index==2 else None
    if first is not None:
        for key in ('parent','selected'):validate(first[key],sig,cases)
        if first['candidate'] is not None:validate(first['candidate'],sig,cases)
    prompt,mapping=prompt_data(baselines,h,pairs,first);prompt=compact_tables(prompt);parent=h if index==1 else first['selected']
    if first is not None and first['candidate'] is not None:
        prompt['Q1_first_actual_numeric_failure']=next((failure for row in first['candidate']['rows'] for failure in record(row)['numeric_failures']),None)
        behavior=[];first_plan=None
        peers={r['case_id']:r for r in first['parent']['rows']}
        for n,row in enumerate(first['candidate']['rows']):
            own=record(row);old=record(peers[row['case_id']])
            behavior.append(['c'+str(n),own['action_sha256']!=old['action_sha256'],own['metrics']['reordered_plans'],old['metrics']['reordered_plans']])
            if first_plan is not None:continue
            prior={(d['time_s'],d['agent']):d for d in old['local_decisions']}
            for d in sorted(own['local_decisions'],key=lambda v:(v['time_s'],v['agent'])):
                previous=prior.get((d['time_s'],d['agent']))
                if previous is None or previous['selected_order']!=d['selected_order']:
                    ids={p['task']:'q1_t'+str(k) for k,p in enumerate(d['public_tasks'])}
                    first_plan={'case':'c'+str(n),'time_s':d['time_s'],'actor':'q1_u0','namespace':'q1_ labels are a separate view, not paired-card t/u labels',
                        'original':[ids[j] for j in d['window']],
                        'child':[ids[j] for j in d['selected_order']],
                        'parent_observed':[ids.get(j,'other') for j in previous['selected_order']] if previous else None,
                        'risk_and_component_sources':[[ids[p['task']],short(p['risk']),[[c['group'],short(c['value']),c['time_s']] for c in p['evidence_components']]] for p in d['public_tasks'] if p['task'] in d['window']],
                        'planned_shifts':[[ids[v['task']],v['delta_completion_s'],v['target_round']] for v in d['completion_deltas_vs_original']],
                        'scope':'Actual first recorded plan difference; full-episode metrics above include downstream harms.'}
                    break
        prompt['Q1_behavior_feedback']={'case_changed_child_reordered_parent_reordered':behavior,'first_plan':first_plan}
    simple=read(root/'S-complete.json');seen={Rule().identity}
    for step in simple['rounds']:seen.add(rule_from_dict(step['candidate']['policy']['rule']).identity)
    if first is not None and first['candidate'] is not None:seen.add(rule_from_dict(first['candidate']['policy']['rule']).identity)
    prompt['already_evaluated_rules_no_resubmission']=[h['policy']['rule']]+[s['candidate']['policy']['rule'] for s in simple['rounds']]+([first['candidate']['policy']['rule']] if first and first['candidate'] else [])
    prompt['structural_failures']=[]
    parse_model_response(json.dumps(response_example()))
    prompt['numeric_representation']='All equivalent JSON number spellings share identity; -0.0 and0.0 are the same parameter, never a new edit.'
    callfile=root/'model-calls.jsonl';prior=[json.loads(v) for v in callfile.read_text().splitlines()] if callfile.exists() else []
    need(not any(v['round']==index for v in prior),'No restart/resampling of a billed round')
    need(not(root/f'Q{index}-proposal.json').exists(),'First legal proposal already exists')
    allowed=min(2,4-len(prior)) if index==1 else 4-len(prior);need(allowed>0,'Four-call cap')
    torch.set_num_threads(int(os.environ['SLURM_CPUS_PER_TASK']))
    tokenizer=AutoTokenizer.from_pretrained(MODEL,local_files_only=True,trust_remote_code=False)
    if a.prepare_only:
        rendered=tokenizer.apply_chat_template([{'role':'system','content':'Output exactly the complete registered JSON object; source_weights is an OBJECT and mechanism is a short STRING. Do not copy previously evaluated rules.'},
            {'role':'user','content':render_user(prompt)}],tokenize=False,add_generation_prompt=True,enable_thinking=False)
        tokens=len(tokenizer.encode(rendered))
        write(root/f'prompt-preflight-round{index}-{sha(Path(__file__))[:10]}-{os.environ["SLURM_JOB_ID"]}.json',{'prompt':prompt,'rendered_user':render_user(prompt),'input_tokens':tokens,'within_4096':tokens<=4096,'real_model_generations':0,'anonymous_mapping':mapping})
        print('PROMPT_PREFLIGHT_TOKENS',index,tokens,flush=True);return
    area=root/f'model-round-{index}';area.mkdir(exist_ok=False);write(area/'anonymous-mapping.json',mapping)
    verification=verify_open_model(MODEL)
    model=AutoModelForCausalLM.from_pretrained(MODEL,torch_dtype=torch.float32,attn_implementation='eager',local_files_only=True,trust_remote_code=False).eval()
    need(all(p.dtype==torch.float32 and p.device.type=='cpu' for p in model.parameters()),'CPU float32 unchanged')
    versions=tuple(p._version for p in model.parameters())
    write(area/'startup.json',{'job_id':os.environ['SLURM_JOB_ID'],'execution_signature':sig,'model_verified':verification,
        'script_sha256':sha(Path(__file__)),'source_manifest_sha256':sha(source/'snapshot-manifest.json'),
        'feedback_Q1_receipt_sha256':sha(root/'Q1-complete.json') if first is not None else None,
        'paired_feedback_receipt_sha256':sha(root/'pairs-complete.json'),'dtype':'float32','training':False})
    for _ in range(allowed):
        rendered=tokenizer.apply_chat_template([{'role':'system','content':'Output exactly the complete registered JSON object; source_weights is an OBJECT and mechanism is a short STRING. Do not copy previously evaluated rules.'},
            {'role':'user','content':render_user(prompt)}],tokenize=False,add_generation_prompt=True,enable_thinking=False)
        inputs=tokenizer(rendered,return_tensors='pt');count=int(inputs['input_ids'].numel())
        need(count<=4096,'4096-token pre-generation bound; compact tables without dropping any conditions')
        receipt=reserve(root,'model-calls',4,{'round':index,'parent_policy_id':parent['policy_id'],'execution_signature':sig})
        call=area/f"call-{receipt['number']:02d}";call.mkdir()
        write(call/'start.json',{'receipt':receipt,'prompt':prompt,'rendered_prompt':rendered,'input_tokens':count,'output_max':256,'greedy':True,'thinking':False})
        start=time.perf_counter();response=None;phase='generation'
        def timeout(signum,frame):raise TimeoutError('240s generation limit, charged')
        previous=signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,240)
        try:
            with torch.inference_mode():generated=model.generate(**inputs,max_new_tokens=256,do_sample=False)
            response=tokenizer.decode(generated[0,count:],skip_special_tokens=True)
            write(call/'response.json',{'raw_response':response,'output_tokens':int(generated.shape[1]-count),'seconds':time.perf_counter()-start})
            phase='parse'
            rule,mechanism=parse_model_response(response);require_mutation(rule,rule_from_dict(parent['policy']['rule']),seen)
            phase='persist'
            need(tuple(p._version for p in model.parameters())==versions,'No model update')
            value={'rule':rule.to_dict(),'mechanism':mechanism,'round':index,'parent_policy_id':parent['policy_id'],
                'execution_signature':sig,'response_path':str(call/'response.json'),'response_sha256':sha(call/'response.json'),
                'raw_repaired':False,'numeric_representation_canonicalized':True,'copied_contract_example':rule.identity==Rule().identity}
            write(call/'accepted-interface.json',value);write(root/f'Q{index}-proposal.json',value)
            print('LEGAL_CORRECTION_CHILD',index,receipt['number'],rule.to_dict(),flush=True);return
        except Exception as exc:
            write(call/'failed.json',{'type':type(exc).__name__,'error':str(exc),'phase':phase,'raw_response':response,'charged':True,'seconds':time.perf_counter()-start})
            prompt['structural_failures'].append({'error':str(exc),'raw_response':response})
            if phase=='persist' or phase=='generation' and not isinstance(exc,TimeoutError):
                write(area/'operational-stop.json',{'phase':phase,'error':str(exc)});return
        finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
    write(area/'no-legal-child.json',{'calls':allowed,'failures':prompt['structural_failures']})


if __name__=='__main__':main()
