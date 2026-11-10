"""Private sampled event references; physical onset, service loss and plan clocks stay distinct."""
from copy import deepcopy

from .evidence_ledger import _fields, _finite, _plain_json, _registry, _require, _text

TIMING_FIELDS = {'sample_times_s', 'service_reference', 'intervention_deadline', 'source_note'}
DEADLINE_FIELDS = {'status', 'at_s', 'source_note'}


def _base_program(program):
    from .diagnostic_endpoints import PROGRAM_FIELDS, EVENT_FIELDS
    _plain_json(program)
    _fields(program, PROGRAM_FIELDS, 'Temporal diagnostic program')
    events = _registry(program['events'], 'Temporal event')
    for event in events.values():
        _fields(event, EVENT_FIELDS | {'timing'}, 'Temporal diagnostic event')
    base = deepcopy(program)
    base['schema'] = 'aegisdc-business-diagnostic-evaluation-v2'
    for event in base['events']:
        del event['timing']
    return base


def validate_temporal_diagnostic(program, facility_id, duration_s, dispatch, scenario, boundary_events):
    from .diagnostic_endpoints import validate_diagnostic_evaluation
    base = _base_program(program)
    validate_diagnostic_evaluation(base, facility_id, duration_s, dispatch, scenario, boundary_events)
    points = {0, duration_s, *dispatch['decision_times_s']}
    points.update(row['time_s'] for row in boundary_events if type(row) is dict and 'time_s' in row)
    for event in program['events']:
        timing = event['timing']
        _fields(timing, TIMING_FIELDS, 'Temporal reference profile')
        _text(timing['source_note'], 'Temporal reference source')
        _require(timing['service_reference'] == 'WHOLE_FACILITY_UNSERVED_POSITIVE',
                 'Declare the whole-facility service reference without cause attribution')
        times = timing['sample_times_s']
        _require(type(times) is list and 2 <= len(times) <= 1024, 'Declare two to1024 private temporal samples')
        for time in times:
            _finite(time, 'Temporal sample')
            _require(event['opened_at_s'] <= time <= duration_s and time in points,
                     'Temporal samples need exact declared run instants')
        _require(times[0] == event['opened_at_s'] and times[-1] == duration_s
                 and all(a < b for a, b in zip(times, times[1:])),
                 'Temporal samples must increase from event opening through the actual horizon')
        deadline = timing['intervention_deadline']
        _fields(deadline, DEADLINE_FIELDS, 'Planned intervention deadline')
        _text(deadline['source_note'], 'Planned intervention deadline source')
        if deadline['status'] == 'UNMODELED':
            _require(deadline['at_s'] is None, 'Unmodeled intervention deadline must remain null')
        else:
            _require(deadline['status'] == 'DECLARED_PLANNED_DEADLINE', 'Unknown intervention deadline status')
            _finite(deadline['at_s'], 'Planned intervention deadline')
            _require(deadline['at_s'] >= event['opened_at_s'], 'Planned deadline precedes this event')
    return deepcopy(program)


def _sample_reference(times, is_event, confirmation):
    common = dict(sample_at_s=None, previous_non_event_sample_at_s=None,
                  lead_s=None, transition_lead_interval_s=None, interval_lower_exclusive=None,
                  right_censored=False, left_censored=False, censor_at_s=None,
                  lead_lower_bound_if_later_event_s=None, sampling_scope='DECLARED_PRIVATE_SAMPLES_ONLY')
    if is_event is None:
        return dict(common, status='UNMODELED', lead_unavailable_reason='UNMODELED_REFERENCE')
    first = next((i for i, flag in enumerate(is_event) if flag), None)
    if first == 0:
        return dict(common, status='PRESENT_AT_FIRST_SAMPLE', sample_at_s=times[0],
                    left_censored=True, censor_at_s=times[0], lead_unavailable_reason='ONSET_NOT_OBSERVED')
    if first is None:
        return dict(common, status='NOT_OBSERVED_BY_LAST_SAMPLE', right_censored=True,
                    censor_at_s=times[-1], lead_unavailable_reason='REFERENCE_RIGHT_CENSORED',
                    lead_lower_bound_if_later_event_s=times[-1]-confirmation if confirmation is not None else None)
    at, previous = times[first], times[first-1]
    return dict(common, status='FIRST_TRANSITION_SAMPLE', sample_at_s=at,
                previous_non_event_sample_at_s=previous, interval_lower_exclusive=True,
                lead_s=at-confirmation if confirmation is not None else None,
                transition_lead_interval_s=[previous-confirmation, at-confirmation] if confirmation is not None else None,
                lead_unavailable_reason=None if confirmation is not None else 'NO_PUBLIC_CONFIRMATION')


def evaluate_temporal_diagnostic(result, program):
    from .diagnostic_endpoints import evaluate_diagnostic_events, _truth_at
    base = _base_program(program)
    evaluation = evaluate_diagnostic_events(result, base)
    evaluation['schema'] = 'aegisdc-business-diagnostic-result-v3'
    for declaration, event in zip(program['events'], evaluation['events']):
        timing = declaration['timing']
        times = timing['sample_times_s']
        confirmation = event['first_corroborated_fault_report_at_s']
        fault = None if declaration['truth']['kind'] == 'UNMODELED' else [
            _truth_at(result, declaration['truth'], time)[0] == 'FAULT' for time in times]
        service = []
        for time in times:
            selected = [row for row in result['trace'] if row['time_s'] == time]
            _require(len(selected) == 1, 'No exact private service snapshot; interpolation is forbidden')
            unserved = selected[0]['domains']['it_service']['unserved']
            _finite(unserved, 'Actual unserved service')
            service.append(unserved > 0)
        deadline = deepcopy(timing['intervention_deadline'])
        deadline.update(lead_s=deadline['at_s']-confirmation
                        if deadline['at_s'] is not None and confirmation is not None else None,
                        lead_unavailable_reason='UNMODELED_REFERENCE' if deadline['at_s'] is None
                        else 'NO_PUBLIC_CONFIRMATION' if confirmation is None else None,
                        scope='PROSPECTIVE_PLAN_NOT_OBSERVED_FAILURE_OR_OPTIMAL_RESCUE_TIME')
        service_reference = _sample_reference(times, service, confirmation)
        service_reference['attribution'] = 'WHOLE_FACILITY_NOT_CAUSE_ATTRIBUTED'
        event['temporal_endpoints'] = dict(
            first_public_confirmation_at_s=confirmation,
            confirmation_status='OBSERVED' if confirmation is not None else 'NOT_OBSERVED_BY_WINDOW_END',
            sample_times_s=deepcopy(times), fault_reference=_sample_reference(times, fault, confirmation),
            service_loss_reference=service_reference, intervention_deadline_reference=deadline,
            sign_convention='REFERENCE_MINUS_PUBLIC_CONFIRMATION_AVAILABILITY',
            prevention_effect='NOT_IDENTIFIED_NO_PAIRED_COUNTERFACTUAL')
    return evaluation
