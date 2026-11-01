"""Freeze development rules only; confirmation seeds are registered after selection."""
import json
from pathlib import Path
import sys


def main():
    root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'src'))
    from patrol_rsi.local_score import response_contract,BASE_EXPRESSION,parse_response
    previous=json.loads((root/'research/2026-11-01-measurement-effect/protocol.json').read_bytes())
    legacy=json.loads((root/'research/2026-11-01-multistep-workflow/evidence/baselines-complete.json').read_bytes())['rows']
    history=json.loads((root/'research/2026-11-01-measurement-effect/historical-identities.json').read_bytes())
    history['seed_groups']=sorted(set(history['seed_groups'])|{c['specification']['seed'] for c in previous['cases']})
    pairs=json.loads((root/'research/2026-11-01-measurement-effect/evidence/new-complete.json').read_bytes())['rows']
    history['numeric_fingerprints']=sorted(set(history['numeric_fingerprints'])|{v['process_fingerprint'] for v in pairs})
    cases=[]
    for i,c in enumerate(previous['cases'][:6]):
        old=next(v for v in legacy if v['case_id']==f'dev-{i:02d}' and v['arm']=='A')
        cases.append({'case_id':f'dev-{i:02d}','partition':'development','specification':c['specification'],
            'trace_folder':c['trace_folder'],'expected_fingerprint':c['expected_fingerprint'],
            'legacy_tour_record':{k:old[k] for k in ('record_path','record_sha256','action_sha256','process_fingerprint')}})
    contract=response_contract();parse_response(json.dumps(contract['example']))
    protocol={'experiment':'local-reorder-v1','execution_base':'109a6c398d31ea09e1c84fa40a63271c319c8f3f',
        'research_baseline':'4903ed682c4fdbbde391a81829c0774963705c72',
        'plan':'research/2026-11-01-local-reorder-plan/执行计划.md','development':cases,
        'window':3,'extra_checks':0,'duration_s':1800,'staff':18,'racks':128,
        'R_expression':BASE_EXPRESSION,'D_rule':['deadline_peak','deadline_pressure','travel_cost'],
        'S_changes':['risk_delay + deadline_pressure + 0.05*travel_cost','(retained_parent_expression) + 0.2*travel_cost'],
        'selection':['mean_missed','mean_censored_wait_over_event_conditions','mean_travel_m','negative_total_completions'],
        'tolerance':1e-9,'model_contract':contract,
        'model':{'id':'Qwen/Qwen3-8B','device':'cpu','dtype':'float32','decoder':'greedy',
            'max_new_tokens':256,'input_tokens_hard_max':4096,'input_target':3072,'call_timeout_s':240,
            'round1_call_max':2,'total_call_max':4,'actual_candidate_rounds_max':2},
        'confirmation_rule':{'register_after_selection':True,'seed_rule':'first unused two seed groups from43000, global metadata rechecked at freeze',
            'phase_s':520,'noise_c':.2,'families':[['healthy',900],['coldplate_fouling',180],['aux_feeder_loss+cdu_fouling',180]],
            'methods':['T','D','R','selected_S','selected_Q'],'no_confirmation_feedback':True},
        'limits':{'environment_attempts':90,'real_Qwen_calls':4,'training':0,'conditions_dev':6,'conditions_confirmation':6,
            'allocated_CPU_core_minutes':360,'GPU_seconds':0,'new_storage_bytes':2000000000,'parallel_allocations':1},
        'main_evaluation_budget':{'development':42,'confirmation':30,'repairs_and_regression':18},
        'feedback_case_selection':'First case/time in each observed gain-or-unchanged and degradation category; absent categories explicitly unobserved',
        'safety':'Independent current-round+restored-full-cycle proof, then original-period bound; live dispatch and actual gap audits',
        'tail':'Commit segment may extend beyond1800; dispatch only completable next head, never skip, preserve incomplete ledger',
        'cache':'Execution kernel/models/canonical policy/condition+process+observations+initial ledger; method labels not new independent samples'}
    stage=root/'research/2026-11-01-local-reorder';stage.mkdir(exist_ok=False)
    for name,value in [('protocol.json',protocol),('historical-identities.json',history)]:
        (stage/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    (stage/'新旧任务区别.md').write_text('# 本轮任务：重排已有义务\n\n旧方法把非下一站视为补查，游标不推进；本轮维护独立round账本，完成一项即移除本轮义务，下一轮重新产生。额外补查关闭，三项窗口仅改变顺序。\n\n资格、测量、工时、物理、观测权限与重访期限沿用。新检查器覆盖局部段、余下本轮及恢复基础巡回，独立核对受延误任务。T/D/R/S/Q共用合法排列空间；模型只提供受限评分表达式。\n\n同义务集合不意味着同路程或相同回合完成数，尾部剩余清单也不自动等于超期。旧K结果仅保留历史，旧Tour只用于工程等价回归。科研结论来自本轮重新运行的共同设定。\n',encoding='utf8',newline='\n')
    print('FROZEN DEVELOPMENT',len(cases),'CONFIRMATION NOT GENERATED')


if __name__=='__main__':main()
