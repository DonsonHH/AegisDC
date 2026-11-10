"""Private dimensional cost records; actual use, admission and computation stay separate."""
from collections import Counter
from copy import deepcopy
import math

from .evidence_ledger import _fields, _finite, _plain_json, _require, _text

PROGRAM_FIELDS = {'schema', 'id', 'facility_id', 'basis', 'time_unit', 'source_note'}
PERSON_FIELDS = ('worker_travel_person_s', 'worker_work_person_s', 'worker_wait_person_s',
                 'access_check_person_s', 'rendezvous_wait_person_s', 'queue_wait_person_s')
TOOL_FIELDS = ('tool_occupation_tool_s', 'tool_work_tool_s')
PERSON_TOTAL_FIELDS = ('worker_travel_person_s', 'worker_work_person_s', 'worker_wait_person_s')


def validate_cost_program(program, facility_id):
    _plain_json(program)
    _fields(program, PROGRAM_FIELDS, 'Private cost evaluation program')
    _require(program['schema'] == 'aegisdc-business-cost-evaluation-v1'
             and program['facility_id'] == facility_id and program['basis'] == 'synthetic_assumption'
             and program['time_unit'] == 's', 'Cost evaluation identity,basis or time unit differs')
    for name in ('id', 'source_note'):
        _text(program[name], 'Cost evaluation ' + name)
    return deepcopy(program)


def _measurement(value, unit, source):
    if value is not None:
        _finite(value, 'Recorded cost quantity')
    return dict(value=value, unit=unit, status='RECORDED' if value is not None else 'NOT_RECORDED', source=source)


def _counter(value):
    _require(type(value) is int and value >= 0, 'Recorded computational counter must be a nonnegative integer')
    return value


def _audit_timing(audits, key):
    values = [_counter(row[key]) for row in audits if key in row]
    result = _measurement(sum(values) if audits and len(values) == len(audits) else None,
                          'ns', 'POLICY_COMPUTATION_AUDIT_ONLY_NOT_PHYSICAL_TIME')
    result.update(records_with_timing=len(values), audit_records=len(audits),
                  scope='SELECTOR_OR_CONDITION_CALL_ONLY_NOT_FULL_PROGRAM_WALL_TIME')
    return result


def _audit_counter(audits, key):
    values = [_counter(row[key]) for row in audits if key in row]
    return dict(count=sum(values) if values else None, records_with_count=len(values), audit_records=len(audits),
                coverage='ALL_AUDIT_RECORDS' if audits and len(values) == len(audits)
                else 'PARTIAL_AUDIT_RECORDS' if values else 'NOT_RECORDED')


def _computation(result):
    audits = result.get('policy_computation_audit', [])
    kinds = sorted({kind for row in audits for kind in row['model_evaluations']})
    models = {}
    for kind in kinds:
        values = [_counter(row['model_evaluations'][kind]) for row in audits if kind in row['model_evaluations']]
        models[kind] = dict(count=sum(values), records_with_count=len(values), audit_records=len(audits),
                            coverage='ALL_AUDIT_RECORDS' if len(values) == len(audits) else 'PARTIAL_AUDIT_RECORDS')
    condition = [_counter(row['condition_assessment_evaluations']) for row in audits
                 if 'condition_assessment_evaluations' in row]
    return dict(observed_selector_invocations=len(audits) if 'policy_computation_audit' in result else None,
        observed_condition_assessment_invocations=sum(condition) if condition else None,
        condition_count_records=len(condition), audit_records=len(audits), audit_record_details=deepcopy(audits),
        model_evaluations=models, instance_closure_evaluations=_audit_counter(audits, 'instance_closure_evaluations'),
        selector_elapsed_ns=_audit_timing(audits, 'elapsed_ns'),
        condition_assessment_elapsed_ns=_audit_timing(audits, 'condition_assessment_elapsed_ns'),
        llm_calls=_measurement(_counter(result['model_calls']) if 'model_calls' in result else None,
                               'call', 'FACILITY_DECLARED_LLM_COUNTER_NOT_MATHEMATICAL_ESTIMATIONS'),
        training_calls=_measurement(_counter(result['training_calls']) if 'training_calls' in result else None,
                                    'call', 'FACILITY_DECLARED_TRAINING_COUNTER'),
        internal_nested_calls=_measurement(None, 'call', 'NOT_INSTRUMENTED'),
        llm_tokens=_measurement(None, 'token', 'NO_TOKEN_ACCOUNT'),
        computation_energy_J=_measurement(None, 'J', 'NO_COMPUTE_ENERGY_ACCOUNT'))


def evaluate_actual_costs(result, program):
    summary = result['summary']
    actual = {name: _measurement(summary.get(name), 'person_s' if name in PERSON_FIELDS else 'tool_s',
                                 'PLANT_INTEGRATED_OCCUPATION_COUNTS') for name in PERSON_FIELDS + TOOL_FIELDS}
    complete_person = all(actual[name]['value'] is not None for name in PERSON_TOTAL_FIELDS)
    personnel = _measurement(math.fsum(actual[name]['value'] for name in PERSON_TOTAL_FIELDS) if complete_person else None,
                             'person_s', 'TRAVEL_PLUS_WORK_PLUS_WAIT_EXCLUDING_WAIT_SUBCOMPONENTS')
    wait = [actual[name]['value'] for name in ('worker_wait_person_s', 'access_check_person_s',
                                               'rendezvous_wait_person_s', 'queue_wait_person_s')]
    occupation, work = (actual[name]['value'] for name in TOOL_FIELDS)
    consistency = dict(
        wait_components_partition_total=math.isclose(wait[0], math.fsum(wait[1:]), rel_tol=1e-9, abs_tol=1e-9)
            if all(v is not None for v in wait) else None,
        tool_work_within_occupation=work <= occupation + 1e-9 if work is not None and occupation is not None else None,
        all_recorded_quantities_nonnegative=all(row['value'] >= 0 for row in actual.values() if row['value'] is not None),
        absolute_roundoff_tolerance=1e-9, relative_roundoff_tolerance=1e-9)
    admission = deepcopy(result.get('policy_public_resource_ledger'))
    fees = _measurement(admission['spent_or_reserved']['cost'] if admission is not None else None,
                         admission['cost_unit'] if admission is not None else None,
                         'DECLARED_ISSUE_FEES_NOT_ACTUAL_CURRENCY_PAYMENT')
    if admission is None:
        fees.update(status='NOT_APPLICABLE', unavailable_reason='NO_ADMISSION_LEDGER')
    tasks = result['work_records']
    records = [{key: deepcopy(row[key]) for key in ('id', 'status', 'accepted', 'reason', 'issued_at_s',
                'finished_at_s', 'completed_at_s') if key in row} for row in tasks]
    return dict(schema='aegisdc-business-cost-result-v1', program_id=program['id'], facility_id=result['facility_id'],
        visibility='PRIVATE_EVALUATOR_ONLY', basis=program['basis'], time_unit='s', window_end_s=summary['duration_s'],
        execution_code_identity=deepcopy(result['code_identity']), actual=actual, personnel_total=personnel,
        consistency=consistency, admission=admission, issue_fees=fees,
        distance_m=_measurement(None, 'm', 'NO_METRIC_ROUTE_LENGTH_ACCOUNT'),
        currency_payment=_measurement(None, None, 'NO_CURRENCY_RATE_OR_PAYMENT_RECORD'),
        task_outcomes=dict(total=len(tasks), counts=dict(sorted(Counter(row['status'] for row in tasks).items())), records=records),
        failure_attribution=dict(status='NOT_IMPLEMENTED_FOR_THIS_VERSION',
            failure_task_ids=[row['id'] for row in tasks if row['status'] in ('aborted', 'rejected')],
            scope='GLOBAL_TOTALS_INCLUDE_ALL_TASK_STATUSES;PER_TASK_OUTCOME_COSTS_PENDING'),
        computation=_computation(result),
        scope='ACTUAL_OCCUPATION_DECLARED_FEES_AND_RECORDED_COMPUTATION_NOT_FIELD_MONETARY_COST',
        field_calibration='PENDING', new_research_trials=0, research_gain_claim='NOT_ESTABLISHED')
