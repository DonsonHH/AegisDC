"""Public sampled scalar conditions; no plant state or event truth is accepted."""
from fractions import Fraction

from .decision_view import validate_current_frame
from .evidence_ledger import _fields, _finite, _plain_json, _registry, _require, _strings, _text

PROFILE_FIELDS = {'schema', 'id', 'facility_id', 'nominal_knowledge_id', 'basis', 'time_unit', 'source_note', 'rules'}
RULE_FIELDS = {'id', 'target_id', 'observable_id', 'unit', 'source_ids', 'comparison', 'threshold', 'source_note'}


def validate_condition_profile(frame, profile):
    frame = validate_current_frame(frame)
    _plain_json(profile);_fields(profile, PROFILE_FIELDS, 'Public condition profile')
    _require(profile['schema']=='aegisdc-public-condition-profile-v1' and profile['basis']=='synthetic_assumption'
             and profile['time_unit']=='s', 'Declare synthetic sampled scalar conditions in SI seconds')
    _require(profile['facility_id']==frame['facility_id']
             and profile['nominal_knowledge_id']==frame['nominal_knowledge']['id'], 'Condition facility or nominal identity differs')
    for name in ('id','source_note'):_text(profile[name], 'Condition '+name)
    static=frame['evidence']['static_knowledge']
    sources={row['id']:row for row in static['sources']}
    observables={row['id']:row for row in static['observables']}
    rules=_registry(profile['rules'],'Condition rule')
    _require(0<len(rules)<=32,'Declare one to32 condition rules')
    for rule in rules.values():
        _fields(rule,RULE_FIELDS,'Condition rule')
        _text(rule['source_note'],'Condition rule basis');_finite(rule['threshold'],'Condition threshold')
        observable=observables.get(rule['observable_id'])
        _require(observable is not None and observable['value_type']=='number'
                 and observable['unit']==rule['unit'] and rule['comparison']=='below', 'Condition observable/unit/comparison differs')
        _strings(rule['source_ids'],'Condition measurement sources')
        _require(bool(rule['source_ids']),'Declare actual condition measurement coverage')
        for identifier in rule['source_ids']:
            source=sources.get(identifier)
            _require(source is not None and source['kind'] in {'fixed_sensor','handheld'}
                     and rule['target_id'] in source['target_ids'] and rule['observable_id'] in source['observable_ids'],
                     'Condition rule exceeds the declared numeric measurement coverage')
    return frame,rules,sources


def assess_conditions(frame, profile):
    frame,rules,sources=validate_condition_profile(frame,profile)
    evidence=frame['evidence'];current=set(evidence['current_record_ids']);conditions=[]
    conflict_ids={identifier for issue in evidence['conflicts'] if set(issue['record_ids'])<=current for identifier in issue['record_ids']}
    provenance_ids={identifier for issue in evidence['provenance_issues'] for identifier in issue['record_ids']}
    for rule in rules.values():
        contexts=sorted(row['id'] for row in evidence['records'] if row['id'] in current
            and row['target_id']==rule['target_id'] and sources[row['source_id']]['kind'] in {'human_report','work_order'})
        candidates=[row for row in evidence['records'] if row['id'] in current and row['source_id'] in rule['source_ids']
                    and row['target_id']==rule['target_id'] and row['observable_id']==rule['observable_id'] and row['unit']==rule['unit']]
        latest=max((row['observed_at_s'] for row in candidates),default=None)
        selected=[row for row in candidates if row['observed_at_s']==latest]
        blocked=sorted(row['id'] for row in selected if row['id'] in conflict_ids|provenance_ids
                       or row['provenance']['copied_from_record_id'] is not None or row['quality']['status']!='bounded')
        states=[]
        if not blocked:
            for row in selected:
                value,error,threshold=Fraction(row['value']),Fraction(row['quality']['error_bound']),Fraction(rule['threshold'])
                states.append('ABNORMAL' if value+error<threshold else 'NORMAL' if value-error>=threshold else 'UNKNOWN')
        status=states[0] if states and len(set(states))==1 else 'UNKNOWN'
        conditions.append(dict(condition_id=rule['id'],target_id=rule['target_id'],observable_id=rule['observable_id'],unit=rule['unit'],
            status=status,reason='BOUNDED_SCALAR_CONDITION' if status!='UNKNOWN' else
                'NO_CURRENT_MEASUREMENT' if not selected else 'BLOCKED_OR_AMBIGUOUS_MEASUREMENT',
            available_at_s=frame['as_of_s'],observed_at_s=latest,
            latest_source_arrival_at_s=max((row['arrived_at_s'] for row in selected),default=None),
            supporting_record_ids=sorted(row['id'] for row in selected) if not blocked else [],
            blocking_record_ids=blocked,external_context_record_ids=contexts,
            scope='SAMPLED_SCALAR_CONDITION_NOT_ROOT_CAUSE_OR_CONTINUOUS_CURRENT_STATE'))
    return dict(schema='aegisdc-public-condition-assessment-v1',facility_id=frame['facility_id'],profile_id=profile['id'],
                as_of_s=frame['as_of_s'],conditions=conditions,private_truth_used=False)
