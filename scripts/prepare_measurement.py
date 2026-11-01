"""Freeze this one mechanism experiment before any environment evaluation."""
import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / 'research/2026-11-01-measurement-effect'


def main():
    old = json.loads((ROOT/'research/2026-11-01-multistep-workflow/protocol-v1.json').read_bytes())
    occupied = set(old['registry']['excluded_seed_groups']) | {v['specification']['seed'] for v in old['cases']}
    seeds = (42000,42001)
    if occupied & set(seeds):
        raise ValueError('Global registration collision')
    history = json.loads((ROOT/'research/2026-11-01-multistep-workflow/historical-identities.json').read_bytes())
    prior_rows = json.loads((ROOT/'research/2026-11-01-multistep-workflow/evidence/baselines-complete.json').read_bytes())['rows']
    history['seed_groups'] = sorted(occupied)
    history['numeric_fingerprints'] = sorted(set(history['numeric_fingerprints']) | {v['process_fingerprint'] for v in prior_rows})
    cases = []
    for k, case in enumerate(old['cases']):
        row = next(v for v in prior_rows if v['case_id'] == case['case_id'] and v['arm'] == 'D')
        cases.append({'case_id': f'old-{k:02d}', 'group': 'already_seen_development',
            'specification': case['specification'], 'trace_folder': f'/share/home/renly/renly-patrol-rsi/runs/20261101-multistep/processes/{case["case_id"]}',
            'expected_fingerprint': row['process_fingerprint']})
    for seed in seeds:
        for family, duration in [('healthy',900),('coldplate_fouling',180),('aux_feeder_loss+cdu_fouling',180)]:
            cases.append({'case_id': f'new-{len(cases)-6:02d}', 'group': 'new_development',
                'specification': dict(phase='development',seed=seed,scenario=family,duration_s=duration,
                    fault_start_s=335,noise_c=.2,estimator='history',control='feedback',resources='provisioned',variant='open')})
    protocol = {'experiment': 'measurement-effect-v1', 'execution_base': '81992020ab583ce6dec402d1e9279726f6a7a350',
        'research_baseline': '41a2857d7f26d588639ede88514d0ff77185170e',
        'plan': 'research/2026-11-01-measurement-effect-plan/执行计划.md', 'cases': cases,
        'new_seed_registration': {'seeds': list(seeds), 'excluded': sorted(occupied),
            'authority': 'Previous global232-metadata registration + completed six-development seed/physical identities; no old final raw opened'},
        'limits': {'conditions':12,'environment_attempts':60,'model_calls':2,'training':0,
            'CPU_allocated_core_minutes':240,'GPU_seconds':0,'new_storage_bytes':2000000000,'parallel_allocations':1},
        'evaluation_allocation': {'old_ABC':18,'new_ABC':18,'old_positive_reference_R':6,'one_legal_child_all_cases':12,'repair_reserve':6},
        'arms': {'A':'Frozen preferences before first measurement, live safety',
            'B':'Current-time replanning with first new reference and all derivatives masked',
            'C':'Current-time replanning using first reference', 'R':'Original positive-first two-step flow, old six only'},
        'primary_contrast':'C minus B; all actual episodes independent',
        'first_rule': {'name':'fixed_diagnostic_v1','score':'I*E*w*min(lead/300,1)/(1+cost/60)',
            'require':'I>0,E>0,lead>0,at_least_one_equation_related_current_safe_followup,not_known_alarm',
            'I':'missing1 else min(direct_age/300,1)', 'E':'min(max(model_difference,public_cross_cue),1)',
            'thermal_difference':'abs(raw_CVAE-nominal)/20;0 before predictor exists',
            'relations':['cooling_flow_to_same_branch_thermal_projection','rack_heat_balance_residual_to_its_cooling_verification'],
            'no_result_based_rule_changes':True},
        'followup_value':'w*max(own_signal,supported_diagnostic_signal)*lead/300 - .05*shift/300; only positive values; tie Tour',
        'state_update':'Independent policy observers from time5; exact30s CVAE frames, direct priority and nominal future projection; no off-grid CVAE or backfill',
        'observer_tool_schedule':'Both masked and visible audit streams computed in every arm; controller only receives its selected stream. Same-time shadow comparison is not a world outcome.',
        'model':{'id':'Qwen/Qwen3-8B','directory':'/share/home/renly/renly-patrol-rsi/models/Qwen3-8B-b968826d',
            'device':'cpu','dtype':'float32','decoder':'greedy','input_tokens_max':4096,'output_tokens_max':256,
            'call_timeout_seconds':240,'call_cap':2,'stop':'first legal nonduplicate child; second call only structural failure or duplicate, no score-driven resampling',
            'fields':['estimate_tool','dependency_evidence','normal_followup'],'raw_format':'changes + mechanism; same existing compact compiler',
            'no_positive_human_gate':True},
        'report_layers':['data_written','state_used_new_reference','priority_changed','actual_action_changed','same_budget_task_improvement']}
    STAGE.mkdir(parents=True,exist_ok=False)
    for name, value in [('protocol.json',protocol),('historical-identities.json',history)]:
        (STAGE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print('FROZEN',len(cases),seeds,hashlib.sha256((STAGE/'protocol.json').read_bytes()).hexdigest())


if __name__ == '__main__':main()
