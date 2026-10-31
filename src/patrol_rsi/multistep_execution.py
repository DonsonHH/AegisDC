"""New two-step adapter over unchanged physics, qualified sensing and ReturnPlan.

The controller receives public dictionaries only. Environment truth is used by
the inherited measurement interface and by the end-of-episode evaluator.
"""
from copy import deepcopy

import numpy as np

from .causal_observation import ObservedTask, capture_public, task_signal
from .coverage_plan import InfeasibleCoverage, exact_task_gaps
from .facility_workflow import public_outcome
from .improver_task import PatrolProgram
from .inspection_metrics import evaluate_episode
from .multistep_safety import certify_dispatch
from .multistep_workflow import Workflow, digest, followup_order, select_follow_up
from .timing_skill import TimingSkill
from .timing_skill_control import TimingSkillSelector

MEASUREMENT_FIELDS = {'thermal': 'temperature_c', 'cooling': 'pod_flow_kg_s',
                      'electrical': 'contact_temperature_c', 'control': 'controller_sensor_error_c'}


def measurement_information(before, event, packet):
    """Sensor redundancy is reported separately from a new qualified timestamp."""
    kind = before['kind']
    pod = before['pod']
    if kind == 'thermal':
        remote = dict(zip(packet['temperature_indices'], packet['temperature_c']))
        concurrent = event['index'] in remote
        remote_value = float(remote[event['index']]) if concurrent else None
        prior = before['temperature_measurement']
    elif kind == 'cooling':
        remote = dict(zip(packet['flow_pod_indices'], packet['flow_pod_kg_s']))
        concurrent = pod in remote
        remote_value = float(remote[pod]) if concurrent else None
        prior = before['flow']
    else:
        concurrent, remote_value = False, None
        prior = before['contact' if kind == 'electrical' else 'sensor_error']
    return {'quantity': MEASUREMENT_FIELDS[kind], 'first_qualified_for_task': not before['qualified']['available'],
            'prior_same_quantity': deepcopy(prior), 'prior_qualified': deepcopy(before['qualified']),
            'contemporaneous_remote_same_quantity': bool(concurrent),
            'remote_time_s': float(packet['time_s']) if concurrent else None,
            'remote_value': remote_value,
            'meaning': 'New qualified reference and time; novelty of physical information is a separate question'}


class MultistepTask(ObservedTask):
    """Fixed ownership, sequential optional work, explicit global K=1 or K=2."""
    def __init__(self, spec, predictor, max_checks):
        if type(max_checks) is not int or max_checks not in (1, 2):
            raise ValueError('Only K=1 or K=2 in this prototype')
        self.max_checks = max_checks
        self.issued = 0
        self.pending_optional = None
        self.optional_chain = []
        self.dispatch_safety = []
        super().__init__(spec, PatrolProgram(), predictor)
        owned = [j for p in self.plans for j in p.tour]
        if sorted(owned) != list(range(len(self.tasks))):
            raise ValueError('Original task owners must form a partition')

    @property
    def remaining(self):
        return self.max_checks - self.issued

    def options(self, agent_index, reserved, guard=False):
        ids, features, mask = super().options(agent_index, reserved, guard)
        if self.remaining == 0 or self.pending_optional is not None:
            baseline = self.plans[agent_index].tour[self.protected_cursor[agent_index]]
            keep = ids == baseline
            return ids[keep], features[keep], mask[keep]
        return ids, features, mask

    def step(self, choices):
        optional = [(i, int(j)) for i, j in choices.items() if j is not None
                    and j != self.plans[i].tour[self.protected_cursor[i]]]
        if len(optional) > 1 or len(optional) > self.remaining:
            raise InfeasibleCoverage('One sequential dispatch and remaining global budget required')
        if optional and self.pending_optional is not None:
            raise InfeasibleCoverage('Wait for the real first measurement before another extra check')
        # Recompute all dispatch certificates, even if options cached an earlier one.
        reserved = self.reserved()
        fresh = []
        for i, j in choices.items():
            if j is None:
                continue
            cursor = int(self.protected_cursor[i])
            certificate = certify_dispatch(self.plans[i], self.agents[i], int(j), self.clock,
                                           self.last_inspection, cursor, reserved, self.remaining)
            fresh.append({'time_s': float(self.clock), 'agent': i, 'task': int(j),
                          'remaining_before': self.remaining, 'last_stamps_sha256': digest(self.last_inspection.tolist()),
                          'position': list(self.agents[i]['position']), 'cursor': cursor, 'certificate': certificate})
            reserved.add(int(j))
        pending = None
        if optional:
            i, j = optional[0]
            public = capture_public(self)
            certificate = next(r['certificate'] for r in fresh if r['agent'] == i)
            pending = {'dispatch_time_s': float(self.clock), 'agent': i, 'task': j,
                       'expected_finish_s': certificate['candidate_finish_s'],
                       'before_task': deepcopy(public['tasks'][j]), 'before_shared': public}
        # Only successful atomic physical validation consumes budget or changes state.
        old_count = len(self.events)
        for r in fresh:
            self.certificate_cache[(r['agent'], r['task'], r['cursor'])] = r['certificate']
        reward = super().step(choices)
        self.dispatch_safety.extend(fresh)
        self.issued += len(optional)
        if pending is not None:
            self.pending_optional = pending
        for event in self.events[old_count:]:
            pending = self.pending_optional
            if pending is not None and event['agent'] == pending['agent'] and event['task'] == pending['task']:
                if event['time_s'] != pending['expected_finish_s']:
                    raise RuntimeError('Reference completion must match the actual certified assignment')
                after = capture_public(self)
                self.optional_chain.append(dict(pending, completed=deepcopy(event),
                    information=measurement_information(pending['before_task'], event, self.current_packet),
                    after_task=deepcopy(after['tasks'][event['task']]), after_shared=after))
                self.pending_optional = None
        return reward


def candidate_rows(env, public, estimator):
    """Known schedules and causal observations, with no physical-array access."""
    choices, rows = {}, []
    reserved = env.reserved()
    for raw_i in np.roll(np.arange(len(env.agents)), -(env.tick % len(env.agents))):
        i = int(raw_i)
        if env.agents[i]['task'] is not None:
            continue
        ids, features, _ = env.options(i, reserved)
        cursor = int(env.protected_cursor[i])
        base = int(env.plans[i].tour[cursor])
        choices[i] = base if len(ids) else None
        if not len(ids):
            continue
        schedule = env.plans[i].check(env.clock, env.agents[i]['position'], env.last_inspection, cursor)
        if not schedule['ok']:
            raise InfeasibleCoverage('Current protected fallback is infeasible')
        arrivals = dict(zip(schedule['fallback_order'], schedule['fallback_completion_s']))
        for k, raw_j in enumerate(ids):
            j = int(raw_j)
            if j == base:
                continue
            task = deepcopy(public['tasks'][j])
            if estimator == 'nominal':
                task['history_assimilated']['available'] = False
            signal, source = task_signal(task)
            cert = env.candidate_certificate(i, j)
            rows.append({'agent': i, 'task': j, 'pod': task['pod'], 'kind': task['kind'],
                'baseline_next': base, 'rank_signal': float(signal) if signal is not None else 0.,
                'signal_available': signal is not None, 'signal_source': source,
                'weight': float(features[k, 6]), 'age_ratio': float(features[k, 0]),
                'eta_ratio': float(features[k, 1]), 'finish_s': float(cert['candidate_finish_s']),
                'lead_s': max(0., min(1800., arrivals[j]) - cert['candidate_finish_s']),
                'already_alarm': bool(task['already_alarm']), 'qualified': deepcopy(task['qualified']),
                'temperature_measurement': deepcopy(task['temperature_measurement']),
                'flow': deepcopy(task['flow']), 'minimum_return_slack_s': cert['minimum_projected_slack_s']})
    return choices, rows


def frozen_priority(public, anchor, workflow):
    """Commit task preference once, including currently busy owners; not a safety plan."""
    rows = []
    now = public['time_s']
    for agent in public['agents']:
        tour, cursor = agent['tour'], agent['cursor']
        start, costs = now, agent['first_costs_s']
        if agent['busy_target'] is not None:
            busy = agent['busy_target']
            start, costs = agent['busy_finish_s'], agent['costs_s'][str(busy)]
            if busy == tour[cursor]:
                cursor = (cursor + 1) % len(tour)
        arrivals, at, previous = {}, start, None
        for j in tour[cursor:] + tour[:cursor]:
            at += costs[str(j)] if previous is None else agent['costs_s'][str(previous)][str(j)]
            arrivals[j], previous = at, j
        for j in tour:
            row = deepcopy(public['tasks'][j])
            if workflow.estimator == 'nominal':
                row['history_assimilated']['available'] = False
            signal, _ = task_signal(row)
            finish = start + costs[str(j)]
            rows.append({'task': j, 'pod': row['pod'], 'kind': row['kind'],
                'rank_signal': float(signal) if signal is not None else 0., 'weight': row['weight_scaled'],
                'lead_s': max(0., min(1800., arrivals[j]) - finish),
                'age_ratio': min((now - max(0., row['last_check_s'])) / row['deadline_s'], 6),
                'eta_ratio': (finish - now) / row['deadline_s'], 'already_alarm': row['already_alarm']})
    # First dispatch already requires a positive public cue. C commits the
    # positive-cue hypothesis now; this is explicitly NOT a measured alarm.
    ordered = followup_order(workflow, rows, anchor, workflow.after_alarm, True)
    return [r['task'] for r in ordered]


class WorkflowRuntime:
    """White-list interpreter: READ/ESTIMATE, CHECK, WAIT, branch, or TOUR."""
    def __init__(self, workflow, fixed=False):
        self.workflow, self.fixed = workflow, fixed
        self.first_request = None
        self.frozen_order = []
        self.frames = []

    def choose(self, public, candidates, baseline, completed, remaining, pending):
        now = public['time_s']
        selected = None
        branch = 'continue_tour'
        frozen_choice = None
        if remaining and not pending:
            if self.first_request is None:
                # Same first-check logic in C/D; no hidden labels or future scores.
                eligible = [r for r in candidates if r['signal_available'] and r['rank_signal'] >= .05
                            and not r['already_alarm'] and r['lead_s'] > 0]
                selected = max(eligible, key=lambda r: (r['age_ratio'] + r['eta_ratio'], -r['task']), default=None)
                if selected is not None:
                    self.first_request = deepcopy(selected)
                    self.frozen_order = frozen_priority(public, selected, self.workflow)
                    branch = 'first_public_evidence'
            elif completed:
                event = completed[0]['completed']
                first = dict(event, pod=completed[0]['before_task']['pod'])
                positions = {task: i for i, task in enumerate(self.frozen_order)}
                frozen_choice = min((r for r in candidates if r['task'] in positions),
                                    key=lambda r: positions[r['task']], default=None)
                if self.fixed:
                    selected, branch = frozen_choice, 'precommitted_second_order'
                else:
                    selected = select_follow_up(self.workflow, candidates, first, now)
                    branch = 'after_alarm' if first['alarm'] else 'after_normal'
        elif pending:
            branch = 'wait_real_completion_and_continue_other_tours'
        choices = dict(baseline)
        if selected is not None:
            choices[selected['agent']] = selected['task']
        frame = {'time_s': now, 'state': branch, 'tool': self.workflow.estimator,
                 'remaining_before': remaining, 'waiting_for_measurement': bool(pending),
                 'safe_optional_candidates': len(candidates), 'selected': deepcopy(selected),
                 'frozen_second_if_currently_legal': deepcopy(frozen_choice),
                 'frozen_plan_basis': 'Before first result, same tool/ranker/positive-cue branch; not a qualified measurement',
                 'first_request': {'agent': self.first_request['agent'], 'task': self.first_request['task']} if self.first_request else None,
                 'public_sha256': digest(public)}
        self.frames.append(frame)
        return choices


class DeniedOnlineTrace:
    def __getattr__(self, name):
        raise RuntimeError('Online controller cannot access physical trace: ' + name)


def run_workflow_episode(spec, workflow, predictor, max_checks, arm):
    """Trace substitution belongs to the caller; this function never chooses data."""
    if arm not in ('A', 'B', 'C', 'D', 'child'):
        raise ValueError('Only preregistered arms')
    env = MultistepTask(spec, predictor, max_checks)
    runtime = WorkflowRuntime(workflow, fixed=arm == 'C')
    legacy = TimingSkillSelector(TimingSkill.initial_e1()) if arm == 'B' else None
    decisions = []
    while not env.done:
        trace = env.trace
        env.trace = DeniedOnlineTrace()
        try:
            public = capture_public(env)
            baseline, candidates = candidate_rows(env, public, workflow.estimator)
            if arm == 'A':
                choices, logs = baseline, []
            elif legacy is not None:
                choices, logs = legacy(env, lambda f: np.zeros(len(f)))
            else:
                choices = runtime.choose(public, candidates, baseline, env.optional_chain, env.remaining, env.pending_optional)
                logs = []
        finally:
            env.trace = trace
        if arm != 'B':
            for i, j in choices.items():
                if j is not None:
                    base = int(env.plans[i].tour[env.protected_cursor[i]])
                    logs.append({'time_s': env.clock, 'agent': i, 'task': j, 'baseline_next': base,
                        'actor_task': j, 'tool': 'workflow_check' if j != base else 'return_tour',
                        'rule_index': 0 if j != base else None, 'legal_candidates': 0,
                        'detours_used_before': int(env.detours_used[i]), 'baseline_completed_before': int(env.baseline_completed[i])})
        decisions.append({'time_s': env.clock, 'choices': {str(i): j for i, j in choices.items()}})
        env.step(choices)
        env.workflow_decisions.extend(logs)
    metrics, by_role, intervals = evaluate_episode(env)
    maxima, gaps = exact_task_gaps(env.tasks, env.events)
    metrics.update(tasks_violating_exact_gap=int((maxima > env.deadlines + 1e-9).sum()),
        maximum_exact_gap_s=float(maxima.max()), maximum_exact_gap_ratio=float((maxima / env.deadlines).max()),
        selected_detours=env.issued, estimator_calls=env.estimator_calls)
    if metrics['tasks_violating_exact_gap'] or env.issued > max_checks or env.pending_optional is not None:
        raise InfeasibleCoverage('Full episode must preserve cumulative coverage and completed optional work')
    record = {'specification': dict(spec), 'arm': arm, 'workflow': env.workflow.to_dict(),
        'multistep_workflow': workflow.to_dict(), 'workflow_sha256': workflow.sha256,
        'online_trace_access_denied_all_359_decisions': True,
        'workflow_contract': {'global_optional_budget': max_checks, 'extra_checks_per_owned_round': 2,
            'task_weights': env.asset_weights.tolist(), 'deadlines_s': env.deadlines.tolist()},
        'metrics': metrics, 'by_role': by_role, 'anomaly_intervals': intervals,
        'exact_task_gaps': gaps, 'action_log': decisions, 'assignments': env.assignments,
        'inspection_events': env.events, 'initial_certificates': env.initial_certificates,
        'selected_certificates': env.selected_certificates, 'dispatch_safety': env.dispatch_safety,
        'workflow_decisions': env.workflow_decisions, 'workflow_frames': runtime.frames,
        'optional_chain': env.optional_chain, 'scalar_trace': env.scalar_trace,
        'service_evidence_events': env.supply_monitor.events, 'process': env.trace.metadata,
        'team': {'count': len(env.agents), 'per_agent': [{k: a[k] for k in
            ('id', 'role', 'zone', 'travel_m', 'service_s', 'idle_s', 'completed')} for a in env.agents]}}
    record['public_selection'] = public_outcome(record, env.asset_weights)
    record['public_selection']['different_from_actor'] = None
    record['public_selection']['actor_counterfactual_observed'] = False
    record['PPO_scoring_calls'] = 0
    record['action_sha256'] = digest(decisions)
    return record, env
