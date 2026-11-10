"""Actual private activity intervals,with ambiguous queue costs retained jointly."""
from collections import defaultdict
import math

from .evidence_ledger import _finite, _require

PERSON_STATUS_FIELDS = {'travelling': 'worker_travel_person_s', 'working': 'worker_work_person_s',
                        'waiting': 'worker_wait_person_s'}


def attribute_task_costs(result, global_actual, global_fees):
    tasks = {row['id']: row for row in result['work_records']}
    _require(len(tasks) == len(result['work_records']), 'Cost attribution needs unique actual task identities')
    trace = result['trace']
    _require(len(trace) >= 2 and trace[0]['time_s'] == 0
             and trace[-1]['time_s'] == result['summary']['duration_s'], 'Cost attribution needs the complete actual time window')
    empty = lambda: {key: [] for key in global_actual}
    assigned = {key: empty() for key in tasks}
    shared = {}
    shared_workers = defaultdict(set)
    shifts = result['inputs'].get('work_program', {}).get('profile', {}).get('shifts', {})
    for left, right in zip(trace, trace[1:]):
        dt = right['time_s'] - left['time_s']
        _finite(dt, 'Actual activity interval')
        _require(dt > 0, 'Actual activity intervals must be increasing')
        people = left['domains']['people_tools_work']
        working = set()
        for worker in people['workers'].values():
            field = PERSON_STATUS_FIELDS.get(worker['status'])
            if field is None:
                continue
            owner = worker.get('request_id')
            _require(owner in assigned, 'Active private worker has no actual task cost owner')
            assigned[owner][field].append(dt)
            if worker['status'] == 'working':
                working.add(owner)
            elif worker['status'] == 'waiting':
                subtype = 'access_check_person_s' if worker.get('stage') == 'gate_check' else 'rendezvous_wait_person_s'
                assigned[owner][subtype].append(dt)
        queued = defaultdict(list)
        for identifier in people.get('queued_requests', []):
            _require(identifier in tasks, 'Private queue contains an unknown task')
            for role in tasks[identifier]['crew']:
                worker_id = role['worker_id']
                state = people['workers'][worker_id]
                _require(worker_id in shifts, 'Queued cost attribution needs the declared worker shift')
                if state['status'] == 'idle' and shifts[worker_id][0] <= left['time_s'] < shifts[worker_id][1]:
                    queued[worker_id].append(identifier)
        for worker_id, members in queued.items():
            members = tuple(sorted(set(members)))
            if len(members) == 1:
                target = assigned[members[0]]
            else:
                target = shared.setdefault(members, empty())
                shared_workers[members].add(worker_id)
            target['worker_wait_person_s'].append(dt)
            target['queue_wait_person_s'].append(dt)
        for tool in people['tools'].values():
            owner = tool.get('reserved_by')
            if owner is None:
                continue
            _require(owner in assigned, 'Reserved private tool has no actual task cost owner')
            assigned[owner]['tool_occupation_tool_s'].append(dt)
            if owner in working:
                assigned[owner]['tool_work_tool_s'].append(dt)

    def measures(bucket):
        return {key: dict(value=math.fsum(parts) if global_actual[key]['value'] is not None else None,
                          unit=global_actual[key]['unit'],
                          status='ACTUAL_TRACE_RECORDED' if global_actual[key]['value'] is not None else 'NOT_RECORDED',
                          source='POST_EVENT_ACTUAL_STATE_UNTIL_NEXT_TRACE_TIME') for key, parts in bucket.items()}

    fees = {}
    for decision in result.get('policy_public_decisions', []):
        choice = decision['choice']
        selected = choice['chosen_candidate_id']
        if selected is None:
            continue
        audit = next(row for row in choice['candidates'] if row['candidate_id'] == selected)
        reservation = audit.get('declared_resource_reservation')
        if reservation is not None:
            fees[choice['work_intention']['id']] = reservation['cost']
    per_task = []
    for identifier, task in tasks.items():
        value = fees.get(identifier)
        per_task.append(dict(task_id=identifier, status_at_horizon=task['status'], actual=measures(assigned[identifier]),
            issue_fee=dict(value=value, unit=global_fees['unit'], source='ACTUAL_SELECTED_CANDIDATE_DECLARED_FEE',
                status='RECORDED' if value is not None else 'NOT_APPLICABLE' if global_fees['unit'] is None else 'NOT_RECORDED')))
    shared_rows = [dict(task_ids=list(members), worker_ids=sorted(shared_workers[members]), actual=measures(bucket),
                        basis='SHARED_IDLE_WORKER_QUEUE_COST_NOT_DUPLICATED_OR_EQUALLY_SPLIT')
                   for members, bucket in sorted(shared.items())]
    reconciliation = {}
    for key, original in global_actual.items():
        values = [row['actual'][key]['value'] for row in per_task + shared_rows]
        reconciliation[key] = (math.isclose(math.fsum(values), original['value'], rel_tol=1e-9, abs_tol=1e-9)
            if original['value'] is not None and all(v is not None for v in values) else None)
    values = [row['issue_fee']['value'] for row in per_task]
    fee_check = (math.isclose(math.fsum(values), global_fees['value'], rel_tol=1e-9, abs_tol=1e-9)
        if global_fees['value'] is not None and all(v is not None for v in values) else None)
    return dict(status='ACTUAL_TRACE_WITH_SHARED_QUEUE_COSTS', per_task=per_task, shared_queue_costs=shared_rows,
        failure_task_ids=[identifier for identifier, row in tasks.items() if row['status'] in ('aborted', 'rejected')],
        unfinished_task_ids=[identifier for identifier, row in tasks.items() if row['status'] not in ('completed', 'aborted', 'rejected')],
        reconciliation=reconciliation, issue_fee_reconciled=fee_check,
        scope='OBSERVED_ACTIVITY_AND_ISSUED_FEES_INCLUDING_FAILURES_AND_UNFINISHED;SHARED_QUEUE_REMAINS_JOINT')
