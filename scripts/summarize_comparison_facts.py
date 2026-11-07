"""Apply preregistered arithmetic to facts; source verification is a separate gate."""

import argparse
import json
from math import fsum, isfinite
from pathlib import Path

from registered_comparison import audit_plan, read, require

METRICS = ('service_deficit_time_s','worker_travel_person_s','worker_work_person_s',
           'worker_wait_person_s','tool_occupation_tool_s')
EXTRAS = {
    'paid_person_s':('worker_travel_person_s','worker_work_person_s','worker_wait_person_s'),
    'travel_person_s':('worker_travel_person_s',),
    'tool_occupation_s':('tool_occupation_tool_s',),
}


def _arm(row, duration):
    if row is None:
        return (0,duration)
    require(type(row) is dict and set(METRICS)<=set(row), 'Missing actual metric')
    for name in METRICS:
        value=row[name]
        require(type(value) in (int,float) and isfinite(value) and value>=0, 'Invalid actual metric')
    value=row['service_deficit_time_s']
    require(value<=duration, 'Service deficit exceeds the registered horizon')
    return (value,value)


def summarize(protocol, facts):
    phase=protocol['phases']['confirmation']
    worlds={row['id']:row for row in phase['worlds']}
    require(type(facts) is dict and set(facts)=={'schema','pairs'}
            and facts['schema']=='aegisdc-comparison-analysis-facts-v1'
            and type(facts['pairs']) is list and len(facts['pairs'])==len(worlds),
            'Facts must retain every planned primary pair')
    seen=set()
    pairs,complete,identified=[],[],[]
    family_deltas={family:[] for family in {row['family'] for row in worlds.values()}}
    hard=[]
    costs={name:[] for name in EXTRAS}
    lower,upper=[],[]
    for row in facts['pairs']:
        require(type(row) is dict and set(row)=={'world_id','baseline','candidate',
                'identified_first_difference','hard_violations'},'Unknown paired fact field')
        name=row['world_id']
        require(name in worlds and name not in seen, 'Unknown or repeated paired fact')
        seen.add(name)
        world=worlds[name]
        duration=world['duration_s']
        require(type(row['identified_first_difference']) is bool
                and type(row['hard_violations']) is list
                and len(set(row['hard_violations']))==len(row['hard_violations'])
                and all(type(v) is str and v in protocol['comparison']['required_actual_constraints']
                        for v in row['hard_violations']), 'Invalid opportunity or hard-constraint fact')
        hard.extend({'world_id':name,'violated_contract':v} for v in row['hard_violations'])
        base,candidate=row['baseline'],row['candidate']
        b,c=_arm(base,duration),_arm(candidate,duration)
        bounds=[b[0]-c[1],b[1]-c[0]]
        lower.append(bounds[0]);upper.append(bounds[1])
        returned=base is not None and candidate is not None
        delta=None
        extra={}
        if returned:
            complete.append(name)
            delta=b[0]-c[0]
            family_deltas[world['family']].append(delta)
            for metric,keys in EXTRAS.items():
                extra[metric]=fsum(candidate[k] for k in keys)-fsum(base[k] for k in keys)
                costs[metric].append(extra[metric])
            if row['identified_first_difference']:
                identified.append(name)
        pairs.append(dict(world_id=name,family=world['family'],service_delta_bounds_s=bounds,
            service_delta_s=delta,extra_costs=extra or None))
    count=len(worlds)
    all_complete=len(complete)==count
    averages={name:(fsum(values)/count if all_complete else None) for name,values in costs.items()}
    gain=fsum(lower)/count if all_complete else None
    strata={family:dict(completed_pairs=len(values),planned_pairs=sum(w['family']==family for w in worlds.values()),
        mean_delta_s=fsum(values)/len(values) if values and all_complete else None)
        for family,values in sorted(family_deltas.items())}
    leave_out={family:(fsum(p['service_delta_s'] for p in pairs if p['family']!=family) /
                     sum(p['family']!=family for p in pairs)) for family in strata} if all_complete else {}
    comparison=protocol['comparison']
    diag=comparison['identification']
    tol=comparison['metric_definition']['numerical_tolerances']['s']
    enough=len(identified)>=diag['minimum_shared_frame_different_first_actions'] and \
           len({worlds[name]['family'] for name in identified})>=diag['minimum_distinct_strata']
    over=all_complete and any(averages[name] > comparison['cost_bounds']['extra_mean_'+name] + tol
                            for name in costs)
    threshold=comparison['minimum_worthwhile_gain_s']
    flags=dict(unsafe_or_invalid=bool(hard),incomplete=not all_complete,not_identified=not enough,
        practical_harm=all_complete and gain<=-threshold+tol,cost_limit_exceeded=bool(over),
        potential_gain=all_complete and gain>=threshold-tol,
        stratum_sensitive=all_complete and gain>=threshold-tol and min(leave_out.values()) < -tol)
    if hard:
        status='UNSAFE_OR_INVALID'
    elif not all_complete:
        status='INCOMPLETE'
    elif not enough:
        status='NOT_IDENTIFIED'
    elif flags['practical_harm']:
        status='PRACTICAL_HARM'
    elif over:
        status='COST_LIMIT_EXCEEDED'
    elif flags['potential_gain']:
        status='STRATUM_SENSITIVE' if flags['stratum_sensitive'] else 'PRACTICAL_GAIN'
    else:
        status='NO_PRACTICAL_GAIN'
    return dict(status=status,source_verification='REQUIRED_SEPARATELY',planned_denominator=count,
        completed_primary_pairs=len(complete),mean_service_delta_bounds_s=[fsum(lower)/count,fsum(upper)/count],
        mean_service_delta_s=gain,**{'mean_extra_'+name:value for name,value in averages.items()},
        identified_world_ids=identified,strata=strata,leave_one_family_out_mean_delta_s=leave_out,
        diagnostic_flags=flags,hard_violations=hard,pairs=pairs,
        scope='Arithmetic of supplied facts. Actual source, safety, opportunity and lifecycle verification are required upstream.',
        facility_calls=0,selector_calls=0,registered_research_trials=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('protocol',type=Path)
    parser.add_argument('facts',type=Path)
    args=parser.parse_args()
    try:
        audit_plan(args.protocol)
        result=summarize(read(args.protocol),read(args.facts))
    except (OSError,KeyError,TypeError,ValueError) as exc:
        parser.exit(2,f'{exc}\n')
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))


if __name__=='__main__':
    main()
