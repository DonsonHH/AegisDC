"""Versioned amplitude guard for bounded numerical-epoch diagnostics."""
from numerical_refinement_checks import causal_sample, epoch_compare as _v2_compare


def epoch_compare(actual, reference, limits, *, factor=1):
    result = _v2_compare(actual, reference, limits, factor=factor)
    baseline = dict(result['maximum_absolute_series_error'])
    saved_time_sets = {'actual':set(actual['times']), 'reference':set(reference['times'])}
    checks = []
    for window in result['alignment']['windows']:
        pair = next(row for row in result['alignment']['paired_side_limits']
                    if row['actual_time_s'] == window['actual_time_s']
                    and row['reference_time_s'] == window['reference_time_s'])
        # Recheck the CLOSED interval at every union breakpoint for BOTH
        # trajectories, including the other trajectory's event/high endpoint.
        # States are linearly completed and fluxes are causally left-held.
        # Each value keeps its side relative to its OWN actual event time.
        for label, data, event_time, opposite in (
                ('actual', actual, window['actual_time_s'], 'reference'),
                ('reference', reference, window['reference_time_s'], 'actual')):
            for when in window['excluded_union_times_s']:
                side = 'left' if when < event_time else 'right'
                values, targets, errors = {}, {}, {}
                for key, series in data['series'].items():
                    value = causal_sample(data['times'], series, when, hold=key.endswith('_W'))
                    target = pair['side_values'][side][opposite][key]
                    values[key], targets[key], errors[key] = value, target, abs(value-target)
                    result['maximum_absolute_series_error'][key] = max(result['maximum_absolute_series_error'][key], errors[key])
                checks.append(dict(trajectory=label, time_s=when, own_event_time_s=event_time,
                    side_of_own_event=side, is_own_event_row=when == event_time,
                    is_original_saved_breakpoint=when in saved_time_sets[label],
                    values=values, paired_limit_targets=targets, absolute_errors=errors))
    if any(result['maximum_absolute_series_error'][key] < value for key, value in baseline.items()):
        raise ValueError('Amplitude correction must preserve every old lower bound')
    result['within_predeclared_limits'] = bool(result['within_predeclared_limits'] and all(
        value <= factor * limits['temperature_K' if key.endswith('_K') else 'pressure_Pa' if key.endswith('_Pa') else 'heat_W']
        for key,value in result['maximum_absolute_series_error'].items()))
    result['comparison_method'] = 'FIXED_PAIRED_EPOCH_WITH_CLOSED_INTERVAL_AMPLITUDE_GUARD_V3'
    result['amplitude_guard'] = dict(previous_epoch_error_lower_bound=baseline,
        closed_interval_checks=checks, checked_value_points=len(checks),
        no_window_value_omitted=True,
        scope='Finite piecewise-linear state / left-held flux diagnostic only; not a general retiming metric theorem.')
    return result


def assess(book, runs):
    cases = {}
    for item in book['cases']:
        rows = runs[item['id']]
        reference = rows[str(book['fine_reference_s'])]
        comparisons = {h:epoch_compare(row,reference,book['limits']) for h,row in rows.items()}
        checked = epoch_compare(rows[str(book['reference_refinement_s'])],reference,book['limits'],
                                factor=book['fine_reference_fraction_of_limits'])
        candidate = comparisons[str(book['proposed_qualified_maximum_step_s'])]
        analytic = item['id'] != 'isolated-room' or rows[str(book['proposed_qualified_maximum_step_s'])]['metrics']['analytic_max_temperature_error_K'] <= item['qualified_analytic_absolute_error_K']
        cases[item['id']] = dict(comparisons=comparisons, fine_reference_refinement=checked,
            analytic_gate=analytic,proposed_step_gate=candidate['within_predeclared_limits'] and analytic,
            qualified_for_declared_fixture=candidate['within_predeclared_limits'] and analytic and checked['within_predeclared_limits'])
    return dict(schema='aegisdc-amplitude-preserving-numerical-assessment-v3',cases=cases,
        all_declared_fixtures_qualified=all(row['qualified_for_declared_fixture'] for row in cases.values()),
        qualification_scope='Explicit full-facility fixture conditions only; causal raw, actual timing and every closed-window value retained.')
