"""Read-only additive-protocol helpers; no plant or property imports."""
from copy import deepcopy
from bisect import bisect_left, bisect_right
import math


def causal_sample(times, values, when, *, hold):
    index = bisect_right(times, when) - 1
    if hold or index == len(times) - 1 or times[index] == when:
        return values[index]
    fraction = (when - times[index]) / (times[index + 1] - times[index])
    return values[index] + fraction * (values[index + 1] - values[index])


def inspect_refinement_run(item, manifest, scenario, trace, balances):
    from numerical_engineering_checks import inspect_run
    result = inspect_run(item, manifest, scenario, trace, balances)
    # Include declared boundary jumps, not just reserve/PLC changes. Values
    # remain part of the identity; a different command is never aligned away.
    result['events'] += [dict(identity=[row['kind'], row['parameter_id'], row['value']],
                             time_s=row.get('applied_at_s', row['time_s']))
                         for row in manifest['events'] if row['kind'] == 'exogenous_boundary_input']
    return result


def epoch_compare(actual, reference, limits, *, factor=1):
    """Causal raw envelope and a fixed, identity-paired numerical-epoch view.

    Only the CLOSED interval between two <=8-ULP matched event times is replaced
    by explicit paired left/right limits. No surrounding tolerance window,
    rolling merge, independent forward peek, or binary interpolation is used.
    An intervening distinct event blocks alignment of that group entirely.
    """
    first = sorted(enumerate(actual['events']), key=lambda pair: (pair[1]['time_s'], pair[0]))
    second = sorted(enumerate(reference['events']), key=lambda pair: (pair[1]['time_s'], pair[0]))
    sequence = [row['identity'] for _, row in first] == [row['identity'] for _, row in second]
    switch_error = max((abs(a['time_s'] - b['time_s']) for (_, a), (_, b) in zip(first, second)), default=0.) if sequence else None
    groups = {}
    if sequence:
        for (_, a), (_, b) in zip(first, second):
            groups.setdefault((a['time_s'], b['time_s']), []).append(a['identity'])
    windows, pair_limits, blocked = [], [], []
    for (ta, tb), identities in groups.items():
        low, high = min(ta, tb), max(ta, tb)
        close = abs(ta - tb) <= 8 * max(math.ulp(ta), math.ulp(tb))
        intervening = [other for other in groups if other != (ta, tb)
                       and any(low <= time <= high for time in other)]
        allowed = close and not intervening
        if allowed and ta != tb:
            windows.append(dict(actual_time_s=ta, reference_time_s=tb, common_anchor_s=low,
                                start_s=low, end_s=high, width_s=high-low, identities=identities))
        elif not allowed and ta != tb:
            blocked.append(dict(actual_time_s=ta, reference_time_s=tb, identities=identities,
                reason='INTERVENING_DISTINCT_EVENT' if intervening else 'MORE_THAN_EIGHT_ULP'))
        ia, ib = bisect_left(actual['times'], ta), bisect_left(reference['times'], tb)
        if ia == len(actual['times']) or ib == len(reference['times']) or actual['times'][ia] != ta or reference['times'][ib] != tb:
            raise ValueError('Matched event has no exact saved right-limit row')
        errors = {'left': {}, 'right': {}}
        side_values = {side: {'actual': {}, 'reference': {}} for side in errors}
        for key in actual['series']:
            for side in errors:
                a_index = ia - 1 if side == 'left' and key.endswith('_W') and ia else ia
                b_index = ib - 1 if side == 'left' and key.endswith('_W') and ib else ib
                errors[side][key] = abs(actual['series'][key][a_index] - reference['series'][key][b_index])
                side_values[side]['actual'][key] = actual['series'][key][a_index]
                side_values[side]['reference'][key] = reference['series'][key][b_index]
        pair_limits.append(dict(actual_time_s=ta, reference_time_s=tb, identities=identities,
                                epoch_alignment_allowed=allowed, maximum_absolute_side_errors=errors, side_values=side_values))
    all_times = sorted(set(actual['times'] + reference['times']))
    for window in windows:
        window['excluded_union_times_s'] = [time for time in all_times if window['start_s'] <= time <= window['end_s']]
        window['excluded_union_points'] = len(window['excluded_union_times_s'])
    excluded = {time for time in all_times if any(row['start_s'] <= time <= row['end_s'] for row in windows)}
    outside = [time for time in all_times if time not in excluded]

    def maxima(times):
        return {key: max((abs(causal_sample(actual['times'], values, time, hold=key.endswith('_W'))
                              - causal_sample(reference['times'], reference['series'][key], time, hold=key.endswith('_W')))
                         for time in times), default=0.) for key, values in actual['series'].items()}

    raw, epoch = maxima(all_times), maxima(outside)
    for row in pair_limits:
        if row['epoch_alignment_allowed']:
            for errors in row['maximum_absolute_side_errors'].values():
                for key, value in errors.items():
                    epoch[key] = max(epoch[key], value)
    metric_errors = {key: abs(value - reference['metrics'][key]) for key, value in actual['metrics'].items()
                     if not key.startswith('analytic_')}

    def passed(errors):
        return bool(sequence and actual['literal_checks_pass'] and reference['literal_checks_pass']
            and switch_error <= factor * limits['switch_time_s']
            and all(value <= factor * limits['temperature_K' if key.endswith('_K') else 'pressure_Pa' if key.endswith('_Pa') else 'heat_W']
                    for key, value in errors.items())
            and all(value <= factor * limits.get(key, limits['resource_time_s']) for key, value in metric_errors.items()))

    return dict(maximum_absolute_series_error=epoch, absolute_integral_error=metric_errors,
        event_sequence_match=sequence, maximum_switch_time_error_s=switch_error,
        within_predeclared_limits=passed(epoch),
        comparison_method='FIXED_IDENTITY_PAIRED_EPOCH_WITH_CAUSAL_LEFT_HELD_RAW_V2',
        raw_causal=dict(maximum_absolute_series_error=raw, within_predeclared_limits=passed(raw),
                        method='UNION_GRID_NO_LOOKAHEAD_CONTINUOUS_LINEAR_FLUX_LEFT_HELD'),
        alignment=dict(changed_epoch_groups=len(windows), total_window_duration_s=math.fsum(row['width_s'] for row in windows),
                       excluded_union_points=len(excluded), excluded_union_times_s=sorted(excluded), windows=windows, paired_side_limits=pair_limits,
                       blocked_groups=blocked, sequence_mismatch_disables_all_alignment=not sequence))


def assess_refinement(book, runs):
    results = {}
    for item in book['cases']:
        by_step = runs[item['id']]
        reference = by_step[str(book['fine_reference_s'])]
        comparisons = {h: epoch_compare(value, reference, book['limits']) for h, value in by_step.items()}
        fine = epoch_compare(by_step[str(book['reference_refinement_s'])], reference, book['limits'],
                             factor=book['fine_reference_fraction_of_limits'])
        selected = comparisons[str(book['proposed_qualified_maximum_step_s'])]
        analytic = item['id'] != 'isolated-room' or by_step[str(book['proposed_qualified_maximum_step_s'])]['metrics']['analytic_max_temperature_error_K'] <= item['qualified_analytic_absolute_error_K']
        results[item['id']] = dict(comparisons=comparisons, fine_reference_refinement=fine,
            analytic_gate=analytic, proposed_step_gate=selected['within_predeclared_limits'] and analytic,
            qualified_for_declared_fixture=selected['within_predeclared_limits'] and analytic and fine['within_predeclared_limits'])
    return dict(schema='aegisdc-epoch-consistent-numerical-assessment-v2', cases=results,
        all_declared_fixtures_qualified=all(row['qualified_for_declared_fixture'] for row in results.values()),
        qualification_metric='Epoch-consistent maximum with fixed <=8-ULP event pairing, explicit two-sided limits, independently reported actual event-time error; causal raw maximum is retained, legacy v1 forward-peek is not a strict raw envelope.',
        qualification_scope='Finite full-facility engineering conditions only; not empirical validation or a continuous parameter-box proof.')


def compact(analysis):
    return {key: value for key, value in analysis.items() if key not in ('times', 'series')}


def check_numeric_range_extension(original, updated):
    left, right = deepcopy(original), deepcopy(updated)
    a = next(row for row in left['parameters'] if row['id'] == 'step_time')
    b = next(row for row in right['parameters'] if row['id'] == 'step_time')
    if a['valid_range'][0] != .01 or b['valid_range'][0] != .0025 or a['valid_range'][1] != b['valid_range'][1]:
        raise ValueError('Numeric range differs from the explicit v2 extension')
    for record in (a, b):
        for key in ('valid_range', 'basis', 'source_note'):
            del record[key]
    if left != right:
        raise ValueError('Scenario changed beyond the declared numeric-range/provenance record')
