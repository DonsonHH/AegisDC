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


RELEASES = {
    'development':('31','ONLY_DEVELOPMENT_INPUTS'),
    'confirmation':('33','PREPARE_AT_32_AFTER_31_EXECUTE_AT_33_AFTER_32'),
    'ablation':('35','AFTER_TICKET_34_AND_ABLATION_INPUT_AUDIT'),
    'robustness':('36','AFTER_TICKET_34_AND_ROBUSTNESS_INPUT_AUDIT'),
}
STOPS = {'mismatched execution identity','invalid shared pair','unexpected truth leak',
         'hard safety or resource breach','output or budget collision'}
CONSTRAINTS = {'no_unqualified_work','no_work_under_blocked_access','no_tool_or_worker_double_booking',
               'no_unauthorized_effect','no_override_of_local_protection','no_future_or_private_input',
               'no_admission_budget_overrun'}
OUTCOMES = ['UNSAFE_OR_INVALID','INCOMPLETE','NOT_IDENTIFIED','PRACTICAL_HARM',
            'COST_LIMIT_EXCEEDED','PRACTICAL_GAIN','STRATUM_SENSITIVE','NO_PRACTICAL_GAIN']


def _semantics(plan):
    def check(ok,message):
        require(ok,'Protocol semantic mismatch: '+message)

    expected={'schema','status','id','facility_id','baseline_acceptance','maximum_step_s','decision_times_s',
              'phases','global_budget','comparison','seed_policy','attempt_policy','scope',
              'development_recipes','held_blueprints','registration_limits'}
    check(set(plan)==expected,'root field roles')
    check(plan['id']=='V6-M5-evidence-consistent-comparison-v1'
          and plan['baseline_acceptance']=='docs/mainline/evidence/29-root.json'
          and plan['development_recipes']=='configs/full-facility-comparison-development-v1.json'
          and plan['held_blueprints']=='configs/full-facility-comparison-held-blueprints-v1.json','identity and source roles')
    for name,(ticket,release) in RELEASES.items():
        check(plan['phases'][name]['ticket']==ticket and plan['phases'][name]['release']==release,'phase preparation/execution gate')
    c=plan['comparison']
    expected_c={'primary','only_primary_input_difference','estimand','independence_unit','minimum_worthwhile_gain_s',
        'cost_bounds','common_admission_budget','identification','partial_outcomes','sensitivity','outcome_order',
        'rule','required_actual_constraints','zero_baseline_rule','report_separately','metric_definition',
        'partial_outcome_details','outcome_rules','contribution_claims'}
    check(set(c)==expected_c,'comparison field roles')
    check(type(c['minimum_worthwhile_gain_s']) in (int,float) and c['minimum_worthwhile_gain_s']==.25,
          'minimum worthwhile gain')
    check(c['cost_bounds']=={'extra_mean_paid_person_s':.5,'extra_mean_travel_person_s':.25,
          'extra_mean_tool_occupation_s':.5},'signed cost thresholds')
    check(c['common_admission_budget']=={'person_s':24,'tool_s':20,'cost':2,'cost_unit':'research_cost_unit'},
          'common resource envelope')
    identification=c['identification']
    check(set(identification)=={'minimum_shared_frame_different_first_actions','minimum_distinct_strata',
         'minimum_common_eligible_paid_candidates','unit','shared_frame','common_eligibility','intent',
         'terminal_handling','criterion','post_divergence'},'identification fields')
    for k,value in (('minimum_shared_frame_different_first_actions',4),('minimum_distinct_strata',2),
                    ('minimum_common_eligible_paid_candidates',2)):
        check(type(identification[k]) is int and identification[k]==value,'identification denominator')
    check(c['outcome_order']==OUTCOMES
          and type(c['outcome_rules']) is list and len(c['outcome_rules'])==len(OUTCOMES)
          and all(type(row) is dict and set(row)=={'label','when'} and row['label']==label
                  and type(row['when']) is str and bool(row['when'].strip())
                  for row,label in zip(c['outcome_rules'],OUTCOMES,strict=True)),'outcome order/rules')
    check(type(c['required_actual_constraints']) is list and len(c['required_actual_constraints'])==len(CONSTRAINTS)
          and set(c['required_actual_constraints'])==CONSTRAINTS,'hard constraints')
    metrics=c['metric_definition']
    check(set(metrics)=={'service_deficit_s','delta_service','paid_person_s','delta_cost','cost_quantities',
                         'sum_rule','numerical_tolerances','threshold_rule'},'metric field roles')
    check(metrics['cost_quantities']=={'paid_person_s':['worker_travel_person_s','worker_work_person_s','worker_wait_person_s'],
          'travel_person_s':['worker_travel_person_s'],'tool_occupation_s':['tool_occupation_tool_s']}
          and metrics['numerical_tolerances']=={'s':1e-8,'person_s':1e-8,'tool_s':1e-8,'W':1e-6},'metric units/tolerances')
    check(set(c['partial_outcome_details'])=={'per_arm','per_pair','aggregate','costs','uncertainty'},
          'missing-outcome accounting')
    check(set(c['contribution_claims'])=={'existing','candidate_increment','facility_extension','comparison_limits','unestablished'},
          'contribution boundary')
    attempts=plan['attempt_policy']
    check(set(attempts)=={'ids','terminal_states','repeated_attempts','stop_conditions','successful_cache_only',
                         'zero_effect_before_acceptance'},'attempt lifecycle roles')
    check(attempts['terminal_states']==['COMPLETED','FAILED','INTERRUPTED','UNRUN']
          and len(attempts['stop_conditions'])==len(STOPS) and set(attempts['stop_conditions'])==STOPS
          and attempts['zero_effect_before_acceptance'] is True
          and attempts['repeated_attempts'].startswith('No automatic retries or resampling.'),'stop/retry rules')
    check(set(plan['registration_limits'])=={'development','confirmatory','information_budget','temporal_scope','source_pins','release'},
          'registration boundary')
    check(set(plan['seed_policy'])=={'namespaces','development_rule','sealed_rule','common_observation_rule','release_rules'},
          'seed roles')
    check(plan['seed_policy']['namespaces']==dict(zip(PHASES,('V6-M5-dev-v1','V6-M5-confirm-v1','V6-M5-ablate-v1','V6-M5-robust-v1'),strict=True)),
          'seed namespaces')
    for section in (c['partial_outcome_details'],plan['registration_limits']):
        check(all(type(v) is str and bool(v.strip()) for v in section.values()),'empty semantic rule')


def audit_plan(path):
    plan = read(path)
    canonical(plan)
    _semantics(plan)
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


RECIPE_FIELDS = {'kernel','network_cap','filter_multiplier','context_valid_until_s','background','crew','events'}
BLUEPRINT_FIELDS = RECIPE_FIELDS | {'variant'}


def _recipe(recipe):
    require(type(recipe) is dict and set(recipe)==BLUEPRINT_FIELDS, 'Unknown held recipe fields')
    require(type(recipe['variant']) is str and recipe['variant'].strip(), 'Unnamed held blueprint')
    require(recipe['kernel'] in ('network-fallback','masked-cooling')
            and recipe['background'] in ('late','early')
            and recipe['crew'] in ('solo','it-with-cooling'), 'Unknown held mode')
    for field,low,high in (('network_cap',0,2),('filter_multiplier',.25,100),('context_valid_until_s',0,10)):
        value=recipe[field]
        require(type(value) in (int,float) and low<=value<=high, f'Invalid recipe coordinate: {field}')
    require(type(recipe['events']) is list, 'Declare the held exogenous events')
    seen=set()
    for event in recipe['events']:
        require(type(event) is dict and set(event)=={'time_s','parameter_id','value','source_note'}
                and type(event['time_s']) in (int,float) and 0<=event['time_s']<=10,
                'Invalid held event fields or time')
        key=(event['time_s'],event['parameter_id'])
        require(key not in seen and type(event['source_note']) is str and bool(event['source_note'].strip()),
                'Repeated or unattributed held event')
        seen.add(key)
        limits={'shared_distribution_available':(0,1),'it_access_permit':(0,1),'grid_capacity':(0,10_000_000)}
        require(event['parameter_id'] in limits, 'Held event is not an allowed exogenous parameter')
        low,high=limits[event['parameter_id']]
        require(type(event['value']) in (int,float) and low<=event['value']<=high
                and (event['parameter_id']=='grid_capacity' or event['value'] in (0,1)), 'Invalid held event value')


def audit_blueprints(protocol_path,blueprint_path):
    audit_plan(protocol_path)
    plan,held=read(protocol_path),read(blueprint_path)
    canonical(held)
    require(type(held) is dict and set(held)=={'schema','status','scope','confirmation','ablation','masks','robustness','sealing'}
            and held['schema']=='aegisdc-held-comparison-blueprints-v1'
            and held['status']=='DESIGN_BLUEPRINTS_NO_RELEASE','Unknown blueprint catalog')
    count={}
    seen=set()
    for phase,per_family in (('confirmation',4),('ablation',2)):
        require(set(held[phase])==CASE_FAMILIES, f'Blueprint family coverage differs: {phase}')
        count[phase]=0
        for family,recipes in held[phase].items():
            require(type(recipes) is list and len(recipes)==per_family, f'Family denominator differs: {phase}/{family}')
            for recipe in recipes:
                _recipe(recipe)
                require(recipe['variant'] not in seen,'Reused blueprint identifier')
                seen.add(recipe['variant'])
                count[phase]+=1
        require(count[phase]==len(plan['phases'][phase]['worlds']), 'Held world denominator differs')
    require(set(held['masks'])==set(ABLATION_ARMS)-{'full'}, 'Ablation transform coverage differs')
    mask_fields={
      'without_nonfixed_context':{'field','keep_registry','remove_source_ids','remove_copied_descendants','unchanged'},
      'without_dependency_context':{'scope','remove_edge_ids','nominal','capacity_transform','invariants','interpretation'},
      'without_joint_crew_planning':{'scope','candidate_transform','value_transform','risk_transform','binding_scope','invariants','interpretation'},
    }
    for key,fields in mask_fields.items():
        mask=held['masks'][key]
        require(type(mask) is dict and set(mask)==fields and bool(mask), 'Missing ablation transform semantics')
    mask=held['masks']['without_nonfixed_context']
    require(mask['keep_registry'] is True and mask['remove_copied_descendants'] is True
            and mask['remove_source_ids']==['operator-report']
            and held['masks']['without_dependency_context']['remove_edge_ids']==['f12','f13','f14'],
            'Ablation transform scope differs')
    require(set(held['robustness'])==ROBUSTNESS_AXES, 'Robustness axes differ')
    for i,axis in enumerate(('load-level','sensor-coverage','reserve-path','model-error'),1):
        block=held['robustness'][axis]
        require(set(block)=={'shared','role','reference','perturbed','allowed_deltas','key'}
                and block['key']==f'R{i}' and block['reference']!=block['perturbed']
                and len(block['allowed_deltas'])==len(set(block['allowed_deltas']))
                and type(block['role']) is str and bool(block['role'].strip()),
                'Unknown or vacuous robustness contrast')
        _recipe(block['shared'])
        parameter,expected_values={
          'load-level':('offered_demand',(.75,1.25)),
          'sensor-coverage':('rectifier_meter_enabled',(True,False)),
          'reserve-path':('ups_in_service',(1,0)),
          'model-error':('declared_fallback_capacity',(.75,1)),
        }[axis]
        require(set(block['reference'])==set(block['perturbed'])=={parameter}
                and (block['reference'][parameter],block['perturbed'][parameter])==expected_values,
                'Robustness coordinate differs from its registered limits')
        require(block['shared']['variant'] not in seen,'Reused blueprint identifier')
        seen.add(block['shared']['variant'])
    require(type(held['sealing']) is dict and all(type(v) is str and bool(v.strip()) for v in held['sealing'].values()),
            'Incomplete sealing recipe')
    return dict(status='PASS_PUBLIC_BLUEPRINT_AUDIT',confirmation_blueprints=count['confirmation'],
        ablation_blueprints=count['ablation'],robustness_blocks=len(held['robustness']),
        held_inputs_materialized=0,secret_material_reads=0,facility_calls=0,selector_calls=0,research_trials=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_subparsers(dest='command',required=True)
    pair = command.add_parser('audit-pair', help='Check the exact primary paired input boundary')
    pair.add_argument('baseline',type=Path)
    pair.add_argument('candidate',type=Path)
    plan = command.add_parser('audit-plan', help='Check the finite roster and attempt budget')
    plan.add_argument('protocol',type=Path)
    blueprints = command.add_parser('audit-blueprints', help='Check public held rules without creating a held input')
    blueprints.add_argument('protocol',type=Path)
    blueprints.add_argument('blueprints',type=Path)
    args = parser.parse_args()
    try:
        if args.command=='audit-pair':
            receipt=audit_pair((args.baseline,args.candidate))
        elif args.command=='audit-plan':
            receipt=audit_plan(args.protocol)
        else:
            receipt=audit_blueprints(args.protocol,args.blueprints)
    except (OSError,ValueError,KeyError,TypeError) as error:
        parser.exit(2,f'{error}\n')
    print(json.dumps(receipt,allow_nan=False))


if __name__ == '__main__':
    main()
