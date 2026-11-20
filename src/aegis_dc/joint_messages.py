"""Task-bound public receipts for the joint opt-in interface."""
from math import isfinite

TERMINALS = frozenset({'completed', 'aborted', 'rejected'})
PROCESS = 'safety_stop_observed'


def _time(value):
    try:
        return type(value) in (int, float) and isfinite(value)
    except OverflowError:
        return False


def _binding(cfg, issued, task):
    if not isinstance(task, str):
        return None
    parts = task.split('/')
    if len(parts) != 3 or not parts[1] or parts[0] not in cfg['types'] or parts[2] not in ('I', 'A', 'R'):
        return None
    entries = [row for row in issued if row['task'] == task]
    if len(entries) != 1 or not _time(entries[0]['at']):
        return None
    return cfg['types'][parts[0]], entries[0]['at']


def _arrived(row, start, now):
    observed, arrived = row.get('at'), row.get('arrived')
    return _time(observed) and _time(arrived) and _time(now) and start <= observed <= arrived <= now


def _work_matches(row, task, typ, start, now):
    status = row.get('status')
    if not isinstance(status, str) or (status not in TERMINALS and status != PROCESS):
        return False
    location = typ['location'] if status == 'completed' else None
    return (row.get('task') == task and row.get('origin') == 'workforce:' + task
            and row.get('worker') == typ['worker'] and row.get('tool') == typ['tool']
            and 'location' in row and row['location'] == location and _arrived(row, start, now))


def _write_matches(row, task, typ, start, now):
    return (task.endswith('/A') and row.get('task') == task and row.get('origin') == 'intervention:' + task
            and row.get('operation') == typ['operation'] and row.get('outcome') in ('APPLIED', 'NO_EFFECT')
            and _arrived(row, start, now))


def _unique_arrival(rows, fields):
    identities = {tuple(r[k] for k in fields) for r in rows}
    if len(identities) != 1:
        return None
    return min(rows, key=lambda r: r['arrived'])


def own_ack(cfg, view, task):
    binding = _binding(cfg, view['issued'], task)
    if binding is None:
        return None
    typ, start = binding
    terminals = [r for r in view['work'] if isinstance(r.get('status'), str) and r['status'] in TERMINALS
                 and _work_matches(r, task, typ, start, view['time'])]
    return _unique_arrival(terminals, ('status', 'at', 'location'))


def _write_candidates(cfg, view, task):
    binding = _binding(cfg, view['issued'], task)
    if binding is None:
        return []
    typ, start = binding
    return [r for r in view['writes'] if _write_matches(r, task, typ, start, view['time'])]


def action_feedback(cfg, view, task):
    ack = own_ack(cfg, view, task)
    if ack is None:
        return None
    candidates = [r for r in _write_candidates(cfg, view, task) if r['at'] == ack['at']
                  and (r['outcome'] == 'NO_EFFECT' or ack['status'] == 'completed')]
    return _unique_arrival(candidates, ('at', 'outcome'))


def provisional_review_release(cfg, view, issue, ack):
    """An early possible APPLIED may increase escrow. It cannot certify the write."""
    candidates = [r['arrived'] for r in _write_candidates(cfg, view, issue['task'])
                  if r['outcome'] == 'APPLIED' and (ack is None or ack['at'] == r['at'])]
    return min([issue['planned_ack'], *candidates])


def native_message(cfg, issued, raw, channel, now):
    task = raw.get('task_id')
    binding = _binding(cfg, issued, task)
    if binding is None:
        return None
    typ, start = binding
    if raw.get('worker_id',typ['worker']) != typ['worker'] or raw.get('tool_id',typ['tool']) != typ['tool']:
        return None
    row = dict(task=task, at=raw.get('observed_at_s'), arrived=raw.get('arrived_at_s'), origin=raw.get('origin_id'))
    if channel == 'work':
        if (raw.get('source_id') != 'workforce-execution-report' or raw.get('coverage') != 'THIS_ISSUED_TASK_ONLY'
                or 'location_id' not in raw):
            return None
        row.update(status=raw.get('status'), location=raw['location_id'], worker=typ['worker'], tool=typ['tool'])
        return row if _work_matches(row, task, typ, start, now) else None
    if channel == 'write':
        if raw.get('source_id') != 'intervention-execution-report' or raw.get('coverage') != 'THIS_AUTHORIZED_TASK_ONLY':
            return None
        row.update(outcome=raw.get('outcome'), operation=raw.get('operation_id'))
        return row if _write_matches(row, task, typ, start, now) else None
    raise ValueError('Unknown joint receipt channel')
