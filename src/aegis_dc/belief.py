"""Finite belief updates over a validated public decision frame."""
import argparse
from fractions import Fraction
import json
from pathlib import Path

from patrol_rsi.contracts import strict_json

from .decision_view import validate_current_frame
from .evidence_ledger import _fields, _plain_json, _registry, _require, _strings, _text


MODEL_FIELDS = {'schema', 'id', 'basis', 'facility_id', 'scope', 'probability_unit',
                'hypotheses', 'channels', 'independent_pairs', 'independence_basis',
                'unidentified', 'variants'}
SCOPE_FIELDS = {'id', 'ledger_id', 'nominal_knowledge_id', 'starts_at_s',
                'epoch_s', 'epoch_count', 'time_unit'}
CHANNEL_FIELDS = {'id', 'source_id', 'target_id', 'observable_id', 'unit',
                  'positive_when', 'threshold'}


def _masses(values, size, label, *, normalized=False):
    _require(type(values) is list and len(values) == size,
             label + ' must align with the declared hypotheses')
    _require(all(type(value) in (int, float) and 0 <= value <= 1 for value in values),
             label + ' requires dimensionless probabilities in [0, 1]')
    masses = tuple(Fraction(str(value)) for value in values)
    _require(not normalized or sum(masses) == 1, label + ' must sum to one')
    return masses


def _model_for_frame(model, frame):
    _plain_json(model)
    _fields(model, MODEL_FIELDS, 'Belief model')
    _require(model['schema'] == 'aegisdc-belief-model-v1' and model['basis'] == 'synthetic_assumption'
             and model['probability_unit'] == '1', 'Declare a dimensionless synthetic belief model')
    _require(model['facility_id'] == frame['facility_id'], 'Belief facility differs from the decision frame')
    _text(model['id'], 'Belief model id')
    _text(model['independence_basis'], 'Conditional independence basis')
    _strings(model['unidentified'], 'Unidentified item')
    scope = model['scope']
    _fields(scope, SCOPE_FIELDS, 'Belief scope')
    _text(scope['id'], 'Belief scope id')
    _require(scope['time_unit'] == 's' and type(scope['starts_at_s']) in (int, float)
             and type(scope['epoch_s']) in (int, float) and scope['epoch_s'] > 0
             and type(scope['epoch_count']) is int and 1 <= scope['epoch_count'] <= 128,
             'Declare 1–128 finite positive-length belief epochs in SI seconds')
    knowledge, evidence = frame['nominal_knowledge'], frame['evidence']
    _require(scope['ledger_id'] == evidence['ledger_id'] and scope['nominal_knowledge_id'] == knowledge['id'],
             'Belief scope differs from the public ledger or nominal knowledge identity')
    entities = {row['id'] for row in knowledge['entities']}
    hypotheses = _registry(model['hypotheses'], 'belief hypothesis')
    _require(2 <= len(hypotheses) <= 8 and 'other' in hypotheses,
             'Declare two to eight hypotheses including other')
    for hypothesis in hypotheses.values():
        _fields(hypothesis, {'id', 'entity_ids', 'meaning'}, 'Belief hypothesis')
        _text(hypothesis['meaning'], 'Hypothesis meaning')
        _strings(hypothesis['entity_ids'], 'Hypothesis entity id')
        _require(set(hypothesis['entity_ids']) <= entities, 'Unknown nominal hypothesis entity')
    channels = _registry(model['channels'], 'belief channel')
    _require(1 <= len(channels) <= 16, 'Declare one to sixteen modeled observation channels')
    static = evidence['static_knowledge']
    sources = {row['id']: row for row in static['sources']}
    observables = {row['id']: row for row in static['observables']}
    bindings = set()
    for channel in channels.values():
        _fields(channel, CHANNEL_FIELDS, 'Belief channel')
        for key in ('source_id', 'target_id', 'observable_id', 'unit', 'positive_when'):
            _text(channel[key], 'Belief channel ' + key)
        source_id, target_id, observable_id = (channel[key] for key in ('source_id', 'target_id', 'observable_id'))
        binding = (source_id, target_id, observable_id)
        _require(target_id in entities and binding not in bindings, 'Unknown entity or duplicate belief channel binding')
        bindings.add(binding)
        positive_when, threshold = channel['positive_when'], channel['threshold']
        if positive_when == 'true':
            _require(threshold is None and channel['unit'] == '1', 'Boolean channels require unit 1 and no threshold')
            value_type = 'boolean'
        else:
            _require(positive_when in {'below', 'at_or_above'} and type(threshold) in (int, float),
                     'Numeric channels require a declared threshold and polarity')
            value_type = 'number'
        _require(source_id in sources and observable_id in observables,
                 'Belief channel requires a registered public source and observable')
        source, observable = sources[source_id], observables[observable_id]
        _require(target_id in source['target_ids'] and observable_id in source['observable_ids'],
                 'Belief channel exceeds public source coverage')
        _require(observable['value_type'] == value_type and observable['unit'] == channel['unit'],
                 'Belief channel type or units differ from the public observable')
    independent = set()
    _require(type(model['independent_pairs']) is list and len(model['independent_pairs']) <= 1,
             'Declare at most one conditionally independent channel pair in this model')
    for pair in model['independent_pairs']:
        _strings(pair, 'Conditional independence channel id')
        _require(len(pair) == 2 and set(pair) <= set(channels), 'Unknown conditional independence channel pair')
        left, right = pair
        _require(channels[left]['source_id'] != channels[right]['source_id'],
                 'A shared source cannot declare independence from itself')
        independent.add(frozenset(pair))
    variants = _registry(model['variants'], 'belief model variant')
    _require(2 <= len(variants) <= 8, 'Declare a reference variant and at least one sensitivity variant')
    parameters = {}
    size = len(hypotheses)
    other = list(hypotheses).index('other')
    for variant_id, variant in variants.items():
        _fields(variant, {'id', 'prior', 'transition', 'positive_likelihood', 'basis'}, 'Belief variant')
        _text(variant['basis'], 'Belief variant basis')
        prior = _masses(variant['prior'], size, 'Prior', normalized=True)
        matrix = variant['transition']
        _require(type(matrix) is list and len(matrix) == size, 'Declare one transition row per hypothesis')
        transition = tuple(_masses(row, size, 'Transition row', normalized=True) for row in matrix)
        _require(prior[other] > 0 and all(row[other] > 0 for row in transition),
                 'Keep the other hypothesis viable in the prior and evolution')
        _fields(variant['positive_likelihood'], set(channels), 'Positive likelihood')
        likelihood = {key: _masses(values, size, 'Positive likelihood')
                      for key, values in variant['positive_likelihood'].items()}
        parameters[variant_id] = prior, transition, likelihood
    return hypotheses, channels, independent, parameters


def _epoch(time, scope):
    elapsed = Fraction(time) - Fraction(scope['starts_at_s'])
    return elapsed // Fraction(scope['epoch_s'])


def _predict(masses, transition):
    return tuple(sum(mass * weight for mass, weight in zip(masses, column))
                 for column in zip(*transition))


def _binding(row):
    return row['source_id'], row['target_id'], row['observable_id']


def _components(evidence):
    parent = {row['id']: row['id'] for row in evidence['records']}

    def root(record_id):
        while parent[record_id] != record_id:
            parent[record_id] = parent[parent[record_id]]
            record_id = parent[record_id]
        return record_id

    for group in evidence['correlation_groups']:
        first, *others = group['record_ids']
        for other in others:
            parent[root(other)] = root(first)
    return {record_id: root(record_id) for record_id in parent}


def _copy_disposition(row, visible):
    parent = row['provenance']['copied_from_record_id']
    seen = {row['id']}
    while parent is not None:
        if parent in seen:
            return 'copy_provenance_unresolved'
        if parent not in visible:
            return 'copy_root_unavailable'
        seen.add(parent)
        if visible[parent]['provenance']['origin_id'] != row['provenance']['origin_id']:
            return 'copy_provenance_unresolved'
        parent = visible[parent]['provenance']['copied_from_record_id']
    return 'copy_not_a_factor'


def _choose_records(evidence, candidates, channels, independent):
    components = _components(evidence)
    ambiguous = {components[record_id] for issue in evidence['provenance_issues']
                 for record_id in issue['record_ids']}
    eligible = {row['id'] for row, _, _ in candidates}
    disputed = {record_id for conflict in evidence['conflicts']
                if set(conflict['record_ids']) <= eligible for record_id in conflict['record_ids']}
    priority = {channel_id: index for index, channel_id in enumerate(channels)}
    selected, represented = [], set()
    candidates.sort(key=lambda candidate: (candidate[0]['availability'] != 'current',
                    priority[candidate[2]['id']], -candidate[0]['observed_at_s'], candidate[0]['id']))
    for row, item, channel in candidates:
        record_id, channel_id = row['id'], channel['id']
        if components[record_id] in ambiguous:
            item['disposition'] = 'provenance_ambiguous'
        elif record_id in disputed:
            item['disposition'] = 'conflicting_reports'
        elif channel_id in represented:
            item['disposition'] = 'channel_representative_already_used'
        elif any(components[record_id] == components[other['id']] for other, _, _ in selected):
            item['disposition'] = 'shared_provenance'
        elif any(frozenset((channel_id, other['id'])) not in independent for _, _, other in selected):
            item['disposition'] = 'dependence_not_modeled'
        else:
            selected.append((row, item, channel))
            represented.add(channel_id)
    return selected


def _binary_outcome(row, channel):
    if channel['positive_when'] == 'true':
        return row['value']
    value, bound = Fraction(row['value']), Fraction(row['quality']['error_bound'])
    threshold = Fraction(channel['threshold'])
    if value - bound >= threshold:
        return channel['positive_when'] == 'at_or_above'
    if value + bound < threshold:
        return channel['positive_when'] == 'below'
    return None


def _eligible_records(frame, channels, scope):
    lookup = {_binding(channel): channel for channel in channels.values()}
    audit, candidates = {}, []
    visible = {row['id']: row for row in frame['evidence']['records']}
    for row in visible.values():
        channel = lookup.get(_binding(row))
        epoch = _epoch(row['observed_at_s'], scope)
        item = dict(record_id=row['id'], source_id=row['source_id'],
                    origin_id=row['provenance']['origin_id'],
                    copied_from_record_id=row['provenance']['copied_from_record_id'],
                    observed_at_s=row['observed_at_s'], arrived_at_s=row['arrived_at_s'],
                    valid_until_s=row['valid_until_s'], availability=row['availability'],
                    observation_epoch=epoch, channel_id=channel['id'] if channel is not None else None)
        audit[row['id']] = item
        if row['provenance']['copied_from_record_id'] is not None:
            item['disposition'] = _copy_disposition(row, visible)
        elif channel is None:
            item['disposition'] = 'unsupported_channel'
        elif row['availability'] == 'missing':
            item['disposition'] = 'missing'
        elif row['quality']['status'] == 'unknown':
            item['disposition'] = 'unknown_quality'
        elif epoch < 0:
            item['disposition'] = 'before_scope'
        elif row['valid_until_s'] is not None and row['arrived_at_s'] >= row['valid_until_s']:
            item['disposition'] = 'expired_before_arrival'
        else:
            positive = _binary_outcome(row, channel)
            if positive is None:
                item['disposition'] = 'threshold_straddled'
            else:
                item['positive'] = positive
                candidates.append((row, item, channel))
    return audit, candidates


def _filter(prior, transition, likelihood, epoch, factors):
    masses = prior
    for step in range(epoch + 1):
        if step:
            masses = _predict(masses, transition)
        for channel_id, positive in factors.get(step, ()):
            weights = likelihood[channel_id]
            if not positive:
                weights = tuple(1 - weight for weight in weights)
            masses = tuple(mass * weight for mass, weight in zip(masses, weights))
        if step in factors:
            total = sum(masses)
            if total == 0:
                return None, step
            masses = tuple(mass / total for mass in masses)
    return masses, None


def infer_belief(frame, model):
    """Return detached probabilities and an information audit, using only public inputs."""
    frame = validate_current_frame(frame)
    hypotheses, channels, independent, variants = _model_for_frame(model, frame)
    scope = model['scope']
    epoch = _epoch(frame['as_of_s'], scope)
    _require(0 <= epoch < scope['epoch_count'], 'Decision time is outside the declared belief scope')
    audit, candidates = _eligible_records(frame, channels, scope)
    factors, updates = {}, []
    for row, item, channel in _choose_records(frame['evidence'], candidates, channels, independent):
        factors.setdefault(item['observation_epoch'], []).append((channel['id'], item['positive']))
        item['disposition'] = 'used'
        updates.append(row['id'])
    posterior_by_variant, support, impossible, exact_posteriors = {}, {}, {}, []
    for variant_id, (prior, transition, likelihood) in variants.items():
        masses, impossible_epoch = _filter(prior, transition, likelihood, epoch, factors)
        if masses is None:
            impossible[variant_id] = impossible_epoch
            posterior_by_variant[variant_id] = None
            support[variant_id] = []
        else:
            exact_posteriors.append(masses)
            posterior_by_variant[variant_id] = dict(zip(hypotheses, map(float, masses)))
            support[variant_id] = [name for name, mass in zip(hypotheses, masses) if mass > 0]
    envelope = None
    if impossible:
        status = 'PARTIAL_MODEL_CONFLICT' if exact_posteriors else 'MODEL_CONFLICT'
    else:
        status = 'UPDATED' if updates else 'PRIOR_PREDICTION'
        envelope = {name: [float(min(column)), float(max(column))]
                    for name, column in zip(hypotheses, zip(*exact_posteriors))}
    reference = next(iter(variants))
    return dict(schema='aegisdc-belief-result-v1', model_id=model['id'], scope_id=scope['id'],
                facility_id=frame['facility_id'], domain_ids=frame['nominal_knowledge']['domain_ids'],
                as_of_s=frame['as_of_s'], epoch=epoch, time_unit='s', probability_unit='1',
                status=status, posterior=posterior_by_variant[reference],
                reference_variant_id=reference, posterior_by_variant=posterior_by_variant,
                positive_support_by_variant=support, impossible_observation_epoch_by_variant=impossible,
                assumption_envelope=envelope, envelope_basis='MIN_MAX_ACROSS_DECLARED_MODEL_VARIANTS',
                information_updates=updates, record_audit=[audit[key] for key in sorted(audit)],
                reported_conflicts=frame['evidence']['conflicts'], provenance_issues=frame['evidence']['provenance_issues'],
                physical_actions=[], unidentified=list(model['unidentified']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frame', type=Path, required=True, help='One validated ticket-15 decision frame')
    parser.add_argument('--model', type=Path, required=True, help='Declared synthetic belief model')
    arguments = parser.parse_args()
    try:
        frame = strict_json(arguments.frame.read_text(encoding='utf-8'))
        model = strict_json(arguments.model.read_text(encoding='utf-8'))
        result = infer_belief(frame, model)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, allow_nan=False, ensure_ascii=False))


if __name__ == '__main__':
    main()
