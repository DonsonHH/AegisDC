"""Inspect frozen comparison inputs without loading the simulator or a policy."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

METHODS = ('one_observation_lookahead', 'evidence_consistent_contingent')
POLICY_FIELD = 'dispatch_program.policy_program.policy'
FACILITY = 'zhengzhou-inspired-synthetic-full-facility-reserve-v6'
DOMAINS = {'power', 'backup', 'facility_cooling', 'equipment_environment',
           'it_service', 'control_monitoring', 'space_access', 'people_tools_work'}
RELATIONS = {'physical', 'functional', 'control_information', 'access'}


def read(path):
    def unique(pairs):
        values = {}
        for key,value in pairs:
            if key in values:
                raise ValueError(f'Duplicate JSON key: {key}')
            values[key] = value
        return values

    return json.loads(path.read_bytes(),object_pairs_hook=unique)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def audit_pair(paths):
    shared = []
    for path,name in zip(paths,METHODS,strict=True):
        document = read(path)
        dispatch = document['dispatch_program']
        policy = dispatch['policy_program']
        model = document['model']
        if (dispatch['schema'] != 'aegisdc-policy-run-program-v3'
                or policy['schema'] != 'aegisdc-dispatch-policy-program-v4'
                or policy.pop('policy') != name):
            raise ValueError(f'Expected paired V4 method: {name}')
        if (model['id'] != FACILITY or len(model['domains']) != len(DOMAINS)
                or {row['id'] for row in model['domains']} != DOMAINS or set(model['graphs']) != RELATIONS):
            raise ValueError('The pair must use the complete eight-domain V6 facility')
        shared.append(canonical(document))
    if shared[0] != shared[1]:
        raise ValueError('Another pair input differs')
    return dict(status='PASS_EXACT_INPUT_PARITY',allowed_difference=POLICY_FIELD,
        shared_input_sha256=sha256(shared[0]).hexdigest(),facility_calls=0,selector_calls=0,
        registered_research_trials=0)


PHASES = ('development','confirmation','ablation','robustness')
REFERENCE_ARMS = ('no_human','periodic','fifo','risk_condition_priority_adapted')
ABLATION_ARMS = ('full','without_nonfixed_context','without_dependency_context','without_joint_crew_planning')
CASE_FAMILIES = {'network-restorable','cooling-masked','misleading-report','protection-or-access'}
ROBUSTNESS_AXES = {'load-level','sensor-coverage','reserve-path','model-error'}
BUDGET_ITEMS = ('attempts','simulated_charge_s','scheduled_decisions')


def require(condition,message):
    if not condition:
        raise ValueError(message)


def audit_plan(path):
    plan = read(path)
    canonical(plan)
    require(plan['schema']=='aegisdc-registered-comparison-v1'
            and plan['facility_id']==FACILITY
            and plan['status'] in {'DESIGN_OPEN_NO_EXECUTION','FROZEN_NO_EXECUTION_UNTIL_TICKET_30_ACCEPTED'},
            'Unknown registered comparison or improper execution status')
    ticks = plan['decision_times_s']
    require(ticks==list(range(10)) and all(type(t) is int for t in ticks)
            and plan['maximum_step_s']==.01, 'Fixed physical and decision clocks differ')
    require(plan['comparison']['primary']==list(METHODS)
            and plan['comparison']['only_primary_input_difference']==POLICY_FIELD,
            'Primary comparison identity differs')
    phases = plan['phases']
    require(set(phases)==set(PHASES), 'Phase registration differs')
    ids, counts = set(), {}
    totals = dict.fromkeys(BUDGET_ITEMS,0)
    for name,arms,number in zip(PHASES,(REFERENCE_ARMS+METHODS,REFERENCE_ARMS+METHODS,ABLATION_ARMS,METHODS),
                                (6,16,8,8),strict=True):
        phase=phases[name]
        require(set(phase)=={'ticket','arms','worlds','budget','release'}, 'Unknown phase role')
        require(phase['arms']==list(arms), f'Phase arms differ: {name}')
        worlds=phase['worlds']
        counts[name]=len(worlds)
        require(len(worlds)==number, f'World denominator differs: {name}')
        fields={'id','family','slot','duration_s'}|({'level','comparison'} if name=='robustness' else set())
        for i,world in enumerate(worlds,1):
            require(set(world)==fields, f'Unknown public world field: {name}')
            require(world['id'] not in ids, 'World IDs overlap across planned units')
            ids.add(world['id'])
            require(world['id']==f'{name}-{i:02}' and type(world['slot']) is int and world['slot']==i
                    and type(world['duration_s']) is int and world['duration_s']==10,
                    f'World index or physical window differs: {name}')
        families=[row['family'] for row in worlds]
        expected=ROBUSTNESS_AXES if name=='robustness' else CASE_FAMILIES
        require(set(families)==expected, f'Coverage differs: {name}')
        if name=='confirmation':
            require(all(families.count(family)==4 for family in expected), 'Unequal primary stratum weights')
        if name=='robustness':
            for i in range(0,len(worlds),2):
                reference,perturbed=worlds[i:i+2]
                require(reference['family']==perturbed['family']
                        and reference['comparison']==perturbed['comparison']==f'R{i//2+1}'
                        and (reference['level'],perturbed['level'])==('reference','perturbed'),
                        'Robustness requires matched reference and perturbation')
        calculated=dict(attempts=len(arms)*len(worlds),
            simulated_charge_s=len(arms)*sum(row['duration_s'] for row in worlds),
            scheduled_decisions=len(arms)*len(worlds)*len(ticks))
        require(phase['budget']==calculated and all(type(value) is int for value in phase['budget'].values()),
                f'Phase budget differs: {name}')
        for item,value in calculated.items():
            totals[item]+=value
    namespaces=plan['seed_policy']['namespaces']
    require(set(namespaces)==set(PHASES) and all(type(n) is str and n.strip() for n in namespaces.values())
            and len(set(namespaces.values()))==len(PHASES), 'Seed namespaces overlap')
    require(plan['global_budget']==dict(totals,llm_calls=0,training_calls=0,automatic_retries=0)
            and all(type(n) is int for n in plan['global_budget'].values())
            and plan['attempt_policy']['zero_effect_before_acceptance'] is True, 'Global budget differs')
    return dict(status='PASS_STATIC_PLAN_AUDIT',worlds=counts,**totals,
        scope='Protocol structure only; no executable worlds or release are inferred.',
        facility_calls=0,selector_calls=0,research_trials=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_subparsers(dest='command',required=True)
    pair = command.add_parser('audit-pair', help='Check the exact primary paired input boundary')
    pair.add_argument('baseline',type=Path)
    pair.add_argument('candidate',type=Path)
    plan = command.add_parser('audit-plan', help='Check the finite roster and attempt budget')
    plan.add_argument('protocol',type=Path)
    args = parser.parse_args()
    try:
        receipt = (audit_pair((args.baseline,args.candidate)) if args.command=='audit-pair'
                   else audit_plan(args.protocol))
    except (OSError,ValueError,KeyError,TypeError) as error:
        parser.exit(2,f'{error}\n')
    print(json.dumps(receipt,allow_nan=False))


if __name__ == '__main__':
    main()
