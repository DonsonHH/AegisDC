"""Finite predeclared engineering jobs, with physical resource enforcement.

No risk selection, automatic patrol, diagnosis, repair or inspection evidence is
created. Those later behaviors must use these same occupation/access rules.
"""
from copy import deepcopy
import heapq
import math

from .thermodynamics import finite_number


class Workforce:
    """Stateful facility work executor used only by the private plant interface."""

    def __init__(self, scenario, parameters, requests, duration_s):
        self.entities = {row['id']: row for row in scenario['entities']}
        self.interfaces = {row['id']: row for domain in scenario['domains'] for row in domain['work_interfaces']}
        self.p = parameters
        self.workers = {row['id']: {'location_id': row['location_id'], 'status': 'idle', 'request_id': None}
                        for row in scenario['entities'] if row['kind'] == 'worker'}
        self.tools = {row['id']: {'location_id': row['location_id'], 'reserved_by': None, 'carried_by': None}
                      for row in scenario['entities'] if row['kind'] == 'tool'}
        self.routes = {}
        for edge in scenario['graphs']['access']:
            duration = self.p[edge['duration_parameter']]
            qualifications = set(edge['requires_qualification_ids'])
            self.routes.setdefault(edge['from'], []).append((edge['to'], duration, qualifications))
            if edge['bidirectional']:
                self.routes.setdefault(edge['to'], []).append((edge['from'], duration, qualifications))
        self.requests = self._validate(requests, duration_s)
        self.index = 0
        self.records, self.active = [], {}

    def _validate(self, rows, duration):
        if not isinstance(rows, (tuple, list)):
            raise ValueError('Engineering work requests must be a declared list')
        result, identifiers = [], set()
        fields = {'id', 'time_s', 'worker_id', 'work_interface_id', 'target_id', 'source_note'}
        for row in rows:
            if not isinstance(row, dict) or set(row) != fields:
                raise ValueError('Engineering request fields do not match the declared contract')
            for name in fields - {'time_s'}:
                if not isinstance(row[name], str) or not row[name].strip():
                    raise ValueError('Engineering request requires text ' + name)
            time_s = finite_number(row['time_s'], 'Engineering request time')
            if not 0 <= time_s <= duration or row['id'] in identifiers:
                raise ValueError('Engineering work time outside run or duplicate request ID')
            if row['worker_id'] not in self.workers or row['work_interface_id'] not in self.interfaces:
                raise ValueError('Unknown work executor or interface')
            if row['target_id'] not in self.interfaces[row['work_interface_id']]['target_ids']:
                raise ValueError('Work target not covered by the declared interface')
            identifiers.add(row['id'])
            result.append(dict(row, time_s=time_s))
        return sorted(result, key=lambda row: row['time_s'])

    def _path(self, start, target, qualifications, blocked):
        if start in blocked or target in blocked:
            return None
        queue, best = [(0.0, start, [])], {start: 0.0}
        while queue:
            cost, location, path = heapq.heappop(queue)
            if location == target:
                return path
            if cost != best[location]:
                continue
            for destination, duration, required in self.routes.get(location, []):
                value = cost + duration
                if destination not in blocked and required <= qualifications \
                        and value < best.get(destination, math.inf):
                    best[destination] = value
                    heapq.heappush(queue, (value, destination, path + [(location, destination, duration)]))
        return None

    def _release(self, job, time_s, status, reason=None):
        record = job['record']
        worker = self.workers[record['worker_id']]
        for tool_id in job['tools']:
            tool = self.tools[tool_id]
            if tool['carried_by'] == record['worker_id']:
                tool['location_id'] = worker['location_id']
            tool.update(reserved_by=None, carried_by=None)
        worker.update(status='idle', request_id=None)
        record.update(status=status, finished_at_s=time_s)
        if status == 'completed':
            record['completed_at_s'] = time_s
        if reason:
            record['reason'] = reason
        del self.active[record['id']]

    def _pickup(self, job):
        worker_id = job['record']['worker_id']
        location = self.workers[worker_id]['location_id']
        for identifier in job['tools']:
            tool = self.tools[identifier]
            if tool['location_id'] == location:
                tool['carried_by'] = worker_id

    def _advance(self, time_s, blocked):
        for identifier, job in list(self.active.items()):
            record = job['record']
            worker = self.workers[record['worker_id']]
            moves = job['moves']
            while job['next_move'] < len(moves) and moves[job['next_move']]['arrives_at_s'] <= time_s:
                move = moves[job['next_move']]
                if move['to_id'] in blocked:
                    self._release(job, time_s, 'aborted', 'access_changed')
                    break
                worker['location_id'] = move['to_id']
                for tool in self.tools.values():
                    if tool['carried_by'] == record['worker_id']:
                        tool['location_id'] = move['to_id']
                self._pickup(job)
                job['next_move'] += 1
            if identifier not in self.active:
                continue
            if job['next_move'] == len(moves):
                worker['status'] = 'working'
                record['status'] = 'working'
                record.setdefault('arrived_at_s', record['scheduled_arrival_at_s'])
                if job['target_location'] in blocked:
                    self._release(job, time_s, 'aborted', 'access_changed')
                elif time_s >= record['scheduled_completion_at_s']:
                    self._release(job, time_s, 'completed')

    def _request(self, request, time_s, blocked):
        worker_id = request['worker_id']
        entity, worker = self.entities[worker_id], self.workers[worker_id]
        interface = self.interfaces[request['work_interface_id']]
        target = self.entities[request['target_id']]
        target_location = target['id'] if target['kind'] == 'location' else target['location_id']
        qualifications = set(entity['qualification_ids'])
        reason = None
        if interface['qualification_id'] not in qualifications:
            reason = 'qualification_mismatch'
        elif worker['status'] != 'idle':
            reason = 'worker_busy'
        elif not set(interface['tool_ids']) <= set(entity['tool_ids']):
            reason = 'incompatible_tool'
        elif any(self.tools[identifier]['reserved_by'] for identifier in interface['tool_ids']):
            reason = 'tool_busy'
        path, location, planned_time = [], worker['location_id'], time_s
        if reason is None:
            for destination in [self.tools[identifier]['location_id'] for identifier in interface['tool_ids']] + [target_location]:
                segment = self._path(location, destination, qualifications, blocked)
                if segment is None:
                    reason = 'access_unreachable'
                    break
                for start, end, duration in segment:
                    path.append({'from_id': start, 'to_id': end, 'departs_at_s': planned_time,
                                 'arrives_at_s': planned_time + duration})
                    planned_time += duration
                location = destination
        work_duration = self.p[interface['duration_parameter']]
        if reason is None and planned_time + work_duration > self.p['shift_end_time']:
            reason = 'shift_unavailable'
        record = dict(request, requested_at_s=time_s, accepted=reason is None,
                      effect='ENGINEERING_WORK_RECORD_ONLY_NO_REPAIR_OR_EVIDENCE')
        self.records.append(record)
        if reason:
            record.update(status='rejected', reason=reason)
            return
        record.update(started_at_s=time_s, scheduled_arrival_at_s=planned_time,
                      scheduled_completion_at_s=planned_time + work_duration,
                      travel_duration_s=planned_time - time_s, work_duration_s=work_duration,
                      status='travelling' if path else 'working', path=deepcopy(path))
        if not path:
            record['arrived_at_s'] = time_s
        job = {'record': record, 'moves': path, 'next_move': 0,
               'target_location': target_location, 'tools': interface['tool_ids']}
        self.active[request['id']] = job
        worker.update(status=record['status'], request_id=request['id'])
        for identifier in interface['tool_ids']:
            self.tools[identifier]['reserved_by'] = request['id']
        self._pickup(job)

    def process(self, time_s, blocked_locations):
        """Complete existing work first, then process equal-time requests in order."""
        self._advance(time_s, blocked_locations)
        while self.index < len(self.requests) and self.requests[self.index]['time_s'] <= time_s:
            self._request(self.requests[self.index], time_s, blocked_locations)
            self.index += 1

    def next_event(self, time_s):
        events = []
        if self.index < len(self.requests):
            events.append(self.requests[self.index]['time_s'])
        for job in self.active.values():
            if job['next_move'] < len(job['moves']):
                events.append(job['moves'][job['next_move']]['arrives_at_s'])
            else:
                events.append(job['record']['scheduled_completion_at_s'])
        return min((value for value in events if value > time_s), default=math.inf)

    def snapshot(self):
        workers = deepcopy(self.workers)
        tools = deepcopy(self.tools)
        for job in self.active.values():
            if job['next_move'] < len(job['moves']):
                row = workers[job['record']['worker_id']]
                row['last_location_id'] = row['location_id']
                row['location_id'] = None
                row['travel'] = deepcopy(job['moves'][job['next_move']])
        for tool in tools.values():
            if tool['carried_by'] and workers[tool['carried_by']]['status'] == 'travelling':
                tool['last_location_id'] = tool['location_id']
                tool['location_id'] = None
                tool['travel'] = deepcopy(workers[tool['carried_by']]['travel'])
        return {'workers': workers, 'tools': tools, 'active_requests': sorted(self.active)}

    def occupation_rates(self):
        return {'worker_travel_person_s': sum(worker['status'] == 'travelling' for worker in self.workers.values()),
                'worker_work_person_s': sum(worker['status'] == 'working' for worker in self.workers.values()),
                'tool_occupation_tool_s': sum(tool['reserved_by'] is not None for tool in self.tools.values())}
