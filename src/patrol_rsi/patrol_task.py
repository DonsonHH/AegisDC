"""Fixed-owner protected task used by the single active workflow.

This removes the historical four-class inheritance chain while preserving the
same initialization, public observations, refresh times and measured evidence.
"""
from dataclasses import dataclass
import time
import numpy as np

from .active_inspection import ActiveInspection, graph_for
from .aisles import DEADLINES, build_agents
from .coverage_plan import InfeasibleCoverage, ReturnPlan
from .estimation import ObservationState
from .inspection_contracts import ServiceEvidence
from .process import phased_trace


@dataclass(frozen=True)
class RefreshSchedule:
    refresh_s: int = 30

    def __post_init__(self):
        if type(self.refresh_s) is not int or self.refresh_s not in (30, 60, 120):
            raise ValueError('Frozen refresh interval must be 30, 60 or 120 seconds')


class FixedPatrolTask(ActiveInspection):
    """Original protected mission contract, independent of old stage drivers."""
    def __init__(self, spec, predictor=None, refresh_s=30):
        self.spec, self.workflow = dict(spec), RefreshSchedule(refresh_s)
        if spec.get('control', 'feedback') != 'feedback' or spec.get('resources', 'provisioned') != 'provisioned':
            raise ValueError('This study fixes plant control and staffing')
        if spec['noise_c'] not in (.2, 1.):
            raise ValueError('Frozen observation noise required')
        self.selector, self.protected = 'risk_certified', True
        self.graph = graph_for(128, 'open')
        self.tasks = self.graph.tasks
        self.public_risk_pulses = spec.get('public_risk_pulses', [])
        for pulse in self.public_risk_pulses:
            if (type(pulse['task']) is not int or not 0 <= pulse['task'] < len(self.tasks)
                    or not 0 <= pulse['start_s'] < pulse['end_s'] <= 1800
                    or not 0 < pulse['risk'] <= 4):
                raise ValueError('Invalid synthetic public risk pulse')
        self.agents = build_agents(self.graph, 'provisioned')
        self.deadlines = np.asarray([DEADLINES[t.kind] for t in self.tasks])
        for agent in self.agents:
            agent['allowed'] = list(agent['tour'])
        self.plans = [ReturnPlan(self.graph, self.tasks, a['tour'], self.deadlines) for a in self.agents]
        self.protected_cursor = np.zeros(len(self.agents), dtype=int)
        self.pending_cursor, self.selected_certificates, self.certificate_cache = {}, [], {}
        self.last_inspection = np.full(len(self.tasks), -1.)
        self.ever = np.zeros(len(self.tasks), dtype=bool)
        self.initial_certificates = [p.check(5., a['position'], self.last_inspection, 0) for p, a in zip(self.plans, self.agents)]
        if not all(c['ok'] for c in self.initial_certificates):
            raise InfeasibleCoverage('Initial backlog cannot satisfy protected tour')
        self.trace = phased_trace(spec['seed'], spec['scenario'], spec['duration_s'], spec['fault_start_s'], spec.get('fault_rack'))
        self.config = self.trace.config
        self.mode, self.predictor = spec['estimator'], predictor
        if self.mode not in ('nominal', 'history') or self.mode == 'history' and predictor is None:
            raise ValueError('Frozen observation-only estimator required')
        asset = self.trace.arrays['asset_weights']
        self.asset_weights = np.asarray([asset[t.index] if t.kind == 'thermal'
            else asset.reshape(16, 8)[t.index].mean() for t in self.tasks])
        self.state = ObservationState(self.config)
        self.events, self.assignments, self.frames, self.scalar_trace = [], [], [], []
        self.tick, self.clock = 0, 5.
        self.current_history = np.full(128, 50.)
        self.inference_seconds, self.estimator_calls = 0., 0
        self.workflow_decisions = []
        self.measured_alert = {}
        self.supply_monitor = ServiceEvidence(16, calibrated=True)
        self._update([])
        self.supply_monitor.update(self.current_packet)
        self.scalar_trace.append(self.public_metrics())
        self.certificate_evaluations, self.certificate_rejections = 0, 0
        self.detours_used = np.zeros(len(self.agents), dtype=int)
        self.baseline_completed = np.zeros(len(self.agents), dtype=int)

    def public_risk(self):
        risk, disagreement = super().public_risk()
        if not self.public_risk_pulses:
            return risk, disagreement
        risk = risk.copy()
        for pulse in self.public_risk_pulses:
            if pulse['start_s'] <= self.clock < pulse['end_s']:
                risk[pulse['task']] = max(risk[pulse['task']], pulse['risk'])
        return risk, disagreement

    def packet(self):
        original = self.trace.packets[self.tick]
        result = {k: v.copy() if isinstance(v, np.ndarray) else v for k, v in original.items()}
        rng = np.random.default_rng(4000000 + self.spec['seed'] * 1000 + self.tick)
        result['temperature_c'] += rng.normal(0, self.spec['noise_c'], len(result['temperature_c']))
        return result

    def _update(self, completed):
        self._risk_cache = None
        self.current_packet = self.packet()
        self.observation = self.state.update(self.current_packet, completed)
        if round(self.clock) % 30 == 0:
            self.frames.append(self.state.features(self.current_packet))
            self.frames = self.frames[-4:]
            if self.mode == 'history' and round(self.clock) % self.workflow.refresh_s == 0:
                frames = [self.frames[0]] * (4 - len(self.frames)) + self.frames
                start = time.perf_counter()
                self.current_history = np.asarray(self.predictor(np.concatenate(frames, axis=-1)), dtype=float)
                self.inference_seconds += time.perf_counter() - start
                self.estimator_calls += 1
                if self.current_history.shape != (128,) or not np.isfinite(self.current_history).all():
                    raise ValueError('Invalid observation-only history estimate')
        fresh = self.state.observer.temperature_stamp == self.clock
        self.current_history[fresh] = self.state.observer.last_temperature[fresh]
