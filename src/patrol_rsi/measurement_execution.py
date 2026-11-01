"""Independent policy observers over the existing two-check physical executor."""
from copy import deepcopy
import numpy as np

from .coverage_plan import InfeasibleCoverage, exact_task_gaps
from .facility_workflow import public_outcome
from .inspection_metrics import evaluate_episode
from .measurement_state import MeasurementState, event_key
from .measurement_workflow import MeasurementWorkflow, rank_candidates, choose_first, choose_followup
from .multistep_execution import MultistepTask, DeniedOnlineTrace
from .multistep_workflow import digest


class MeasurementTask(MultistepTask):
    def __init__(self, spec, predictor):
        self.policy_states = None
        self.policy_cursor = 0
        self.first_key = None
        self.focus_event = None
        super().__init__(spec, predictor, 2)
        self.policy_states = {name: MeasurementState(self.config, self.tasks, predictor) for name in ('masked', 'visible')}
        for state in self.policy_states.values():
            state.advance(self.current_packet, [])

    def _update(self, completed):
        super()._update(completed)
        if self.policy_states is None:
            return
        events = self.events[self.policy_cursor:]
        pending = self.pending_optional
        if self.first_key is None and pending is not None and self.issued == 1:
            for e in events:
                if e['agent'] == pending['agent'] and e['task'] == pending['task'] and e['time_s'] == pending['expected_finish_s']:
                    self.first_key = event_key(e)
                    self.focus_event = deepcopy(e)
        # Both streams are computed at the same times in every arm. Only the
        # selected stream is passed to the controller; the other is audit-only.
        self.policy_states['masked'].advance(self.current_packet, events, blocked=self.first_key)
        self.policy_states['visible'].advance(self.current_packet, events)
        self.policy_cursor = len(self.events)


def safe_geometry(env, *, all_owned=False):
    """Export schedule/weights only, never true-observer risk feature vectors."""
    baseline, rows = {}, []
    reserved = env.reserved()
    for i, agent in enumerate(env.agents):
        plan = env.plans[i]
        cursor = int(env.protected_cursor[i])
        base = int(plan.tour[cursor])
        if agent['task'] is not None:
            if not all_owned:
                continue
            busy = agent['task']
            remaining = agent['remaining_travel_s'] + agent['remaining_service_s']
            start = float(env.clock + np.ceil(remaining / 5. - 1e-10) * 5.)
            position = env.tasks[busy].position_m
            cursor = (cursor + 1) % len(plan.tour) if busy == base else cursor
            base = int(plan.tour[cursor])
            ids = np.asarray(plan.tour)
        else:
            start, position = float(env.clock), agent['position']
            ids, _, _ = env.options(i, reserved)  # Ignore ALL returned value features.
            baseline[i] = base if len(ids) else None
            if all_owned:
                ids = np.asarray(plan.tour)
        fallback = plan.check(start, position, env.last_inspection, cursor)
        if not fallback['ok']:
            if all_owned:
                continue
            raise InfeasibleCoverage('Current fallback must be feasible')
        arrivals = dict(zip(fallback['fallback_order'], fallback['fallback_completion_s']))
        for raw_j in ids:
            j = int(raw_j)
            if j == base and not all_owned:
                continue
            task = env.tasks[j]
            finish = start + plan.travel_service(position, j)
            shift = max(0., finish + plan.cost[j, base] - (start + plan.travel_service(position, base)))
            rows.append({'agent': i, 'task': j, 'kind': task.kind,
                'pod': task.index // 8 if task.kind == 'thermal' else task.index,
                'baseline_next': base, 'weight': float(env.asset_weights[j] / 2),
                'finish_s': float(finish), 'completion_cost_s': float(finish-env.clock),
                'lead_s': max(0., min(1800., arrivals[j])-finish), 'shift_s': float(shift),
                'deadline_s': float(env.deadlines[j]), 'last_check_s': float(env.last_inspection[j]),
                'age_ratio': float((env.clock-max(0., env.last_inspection[j]))/env.deadlines[j])})
    return baseline, rows


def physical_context(env, geometry):
    return {'time_s': float(env.clock), 'remaining': env.remaining,
        'position': [list(a['position']) for a in env.agents],
        'busy_tasks': [a['task'] for a in env.agents],
        'remaining_travel_s': [float(a['remaining_travel_s']) for a in env.agents],
        'remaining_service_s': [float(a['remaining_service_s']) for a in env.agents],
        'last_inspection_s': env.last_inspection.tolist(), 'cursor': env.protected_cursor.tolist(),
        'detours_used': env.detours_used.tolist(), 'safe_geometry': geometry,
        'public_packet': {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in env.current_packet.items()}}


def run_measurement_episode(spec, workflow, predictor, arm):
    if arm not in ('A', 'B', 'C', 'child'):
        raise ValueError('Only measurement-experiment arms')
    env = MeasurementTask(spec, predictor)
    first_request, frozen_order, first_context = None, [], None
    action_log, decisions, comparisons = [], [], []
    old_workflow = env.workflow.to_dict()
    for _ in range(359):
        trace = env.trace
        env.trace = DeniedOnlineTrace()
        try:
            baseline, geometry = safe_geometry(env)
            state = env.policy_states['masked' if arm == 'B' else 'visible']
            # The first rule is immutable and shared even for a model child.
            effective = MeasurementWorkflow() if first_request is None else workflow
            ranked = rank_candidates(state, geometry, effective)
            selected, branch = None, 'Tour'
            if env.remaining and env.pending_optional is None:
                if first_request is None:
                    selected = choose_first(ranked)
                    if selected is not None:
                        first_request = deepcopy(selected)
                        _, whole = safe_geometry(env, all_owned=True)
                        fixed = rank_candidates(state, whole, MeasurementWorkflow())
                        frozen_order = [r['task'] for r in fixed if r['task'] != selected['task'] and r['value'] > 0 and not r['already_alarm']]
                        branch = 'diagnostic_first'
                elif env.first_key is not None:
                    candidates = [r for r in ranked if r['task'] != first_request['task']]
                    if arm == 'A':
                        positions = {j: k for k, j in enumerate(frozen_order)}
                        selected = min((r for r in candidates if r['task'] in positions), key=lambda r: positions[r['task']], default=None)
                        branch = 'fixed_second'
                    else:
                        reference = state.qualified.get(first_request['task'])
                        alarm = reference['alarm'] if reference and tuple(reference['event_id']) == env.first_key else None
                        selected = choose_followup(candidates, workflow, alarm)
                        branch = 'replan_masked' if arm == 'B' else 'replan_visible'
            elif env.pending_optional is not None:
                branch = 'wait_real_completion'
            choices = dict(baseline)
            if selected is not None:
                choices[selected['agent']] = selected['task']
            if env.first_key is not None and env.remaining and env.pending_optional is None:
                before = rank_candidates(env.policy_states['masked'], geometry, effective)
                after = rank_candidates(env.policy_states['visible'], geometry, effective)
                comparisons.append({'time_s': float(env.clock), 'scope': 'same_actual_state_masked_vs_visible_candidates_not_two_world_outcomes',
                    'masked': before, 'visible': after, 'selected_pair': [selected['agent'], selected['task']] if selected else None})
                if first_context is None:
                    first_context = {'physical': physical_context(env, geometry), 'first_actual_event': deepcopy(env.focus_event),
                        'masked_state': env.policy_states['masked'].view(), 'visible_state': env.policy_states['visible'].view(),
                        'masked_ranking': before, 'visible_ranking': after,
                        'actual_selected': [selected['agent'], selected['task']] if selected else None}
            frame = {'time_s': float(env.clock), 'branch': branch, 'safe_optional_count': len(geometry),
                'selected': deepcopy(selected), 'remaining': env.remaining}
            decisions.append(frame)
            action_log.append({'time_s': float(env.clock), 'choices': {str(i): j for i, j in choices.items()}})
        finally:
            env.trace = trace
        logs = []
        for i, j in choices.items():
            if j is not None:
                base = int(env.plans[i].tour[env.protected_cursor[i]])
                logs.append({'time_s': float(env.clock), 'agent': i, 'task': j, 'baseline_next': base,
                    'actor_task': j, 'tool': 'measurement_value' if j != base else 'return_tour',
                    'rule_index': 0 if j != base else None, 'legal_candidates': 0,
                    'detours_used_before': int(env.detours_used[i]), 'baseline_completed_before': int(env.baseline_completed[i])})
        env.step(choices)
        env.workflow_decisions.extend(logs)
    metrics, by_role, intervals = evaluate_episode(env)
    maxima, gaps = exact_task_gaps(env.tasks, env.events)
    metrics.update(tasks_violating_exact_gap=int((maxima > env.deadlines+1e-9).sum()),
        maximum_exact_gap_s=float(maxima.max()), maximum_exact_gap_ratio=float((maxima/env.deadlines).max()),
        selected_detours=env.issued, estimator_calls=env.estimator_calls)
    if metrics['tasks_violating_exact_gap'] or env.issued > 2 or env.pending_optional is not None:
        raise InfeasibleCoverage('Cumulative physical coverage and K=2')
    assert env.policy_states['masked'].tool_times == env.policy_states['visible'].tool_times
    record = {'experiment': 'measurement-effect-v1', 'specification': dict(spec), 'arm': arm,
        'workflow': old_workflow, 'measurement_workflow': workflow.to_dict(), 'workflow_sha256': workflow.sha256,
        'workflow_contract': {'global_optional_budget': 2, 'extra_checks_per_owned_round': 2,
            'task_weights': env.asset_weights.tolist(), 'deadlines_s': env.deadlines.tolist()},
        'metrics': metrics, 'by_role': by_role, 'anomaly_intervals': intervals, 'exact_task_gaps': gaps,
        'action_log': action_log, 'assignments': env.assignments, 'inspection_events': env.events,
        'initial_certificates': env.initial_certificates, 'selected_certificates': env.selected_certificates,
        'dispatch_safety': env.dispatch_safety, 'workflow_decisions': env.workflow_decisions,
        'measurement_decisions': decisions, 'candidate_comparisons': comparisons, 'first_post_measurement_context': first_context,
        'first_request': first_request, 'frozen_second_preference': frozen_order,
        'optional_chain': env.optional_chain, 'scalar_trace': env.scalar_trace,
        'service_evidence_events': env.supply_monitor.events, 'process': env.trace.metadata,
        'tool_calls': {'true_observer': env.estimator_calls, 'policy_masked_times': env.policy_states['masked'].tool_times,
            'policy_visible_times': env.policy_states['visible'].tool_times, 'off_grid_CVAE': 0},
        'policy_state_final_SHA256': {k: digest(v.view()) for k, v in env.policy_states.items()},
        'online_trace_access_denied': True, 'PPO_scoring_calls': 0,
        'team': {'count': len(env.agents), 'per_agent': [{k: a[k] for k in
            ('id', 'role', 'zone', 'travel_m', 'service_s', 'idle_s', 'completed')} for a in env.agents]}}
    record['public_selection'] = public_outcome(record, env.asset_weights)
    record['public_selection'].update(different_from_actor=None, actor_counterfactual_observed=False)
    record['action_sha256'] = digest(action_log)
    return record, env
