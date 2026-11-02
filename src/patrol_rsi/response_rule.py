"""Bounded numeric response/defer rules; no environment or executable input."""
from dataclasses import dataclass
import math

from .contracts import strict_json

FEATURES = ('risk', 'age', 'extra_time', 'slack_difference')
FEATURE_LIMITS = ((0., 1.), (0., 1.), (-6., 6.), (-1., 1.))


def bounded_number(value, lower, upper):
    if type(value) not in (int, float) or not lower <= value <= upper or not math.isfinite(value):
        raise ValueError('Expected finite numeric value within rule contract')
    return float(value)


@dataclass(frozen=True)
class ResponseRule:
    bias: float = 0.
    weights: tuple = (0., 0., 0., 0.)

    def __post_init__(self):
        object.__setattr__(self, 'bias', bounded_number(self.bias, -2., 2.))
        if type(self.weights) is not tuple or len(self.weights) != len(FEATURES):
            raise ValueError('Exactly four immutable weights required')
        object.__setattr__(self, 'weights', tuple(bounded_number(v, -4., 4.) for v in self.weights))

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) != {'version', 'bias', 'weights'}:
            raise ValueError('Only version, bias and four weights are allowed')
        if type(value['version']) is not int or value['version'] != 1:
            raise ValueError('Unknown response rule version')
        if type(value['weights']) is not dict or set(value['weights']) != set(FEATURES):
            raise ValueError('Exactly the declared public features are allowed')
        return cls(value['bias'], tuple(value['weights'][key] for key in FEATURES))

    @classmethod
    def from_json(cls, raw):
        return cls.from_dict(strict_json(raw))

    def to_dict(self):
        return {'version': 1, 'bias': self.bias, 'weights': dict(zip(FEATURES, self.weights))}

    def score(self, features):
        if type(features) is not dict or set(features) != set(FEATURES):
            raise ValueError('Rule accepts only four public scalar features')
        values = [bounded_number(features[key], *limits) for key, limits in zip(FEATURES, FEATURE_LIMITS)]
        return self.bias + sum(w*x for w, x in zip(self.weights, values))

    def respond(self, features):
        return self.score(features) >= 0.


def select_response(rule, event, routine, now, visible_s=None):
    """Choose between certified public candidates without access to an environment.

    Missing candidates denote masked actions. A rule may only change a genuine
    two-choice state; it cannot idle or replace the certified fallback.
    """
    if type(rule) is not ResponseRule:
        raise ValueError('Only a validated bounded rule may select responses')
    for row in (event, routine):
        if row is not None and (not row['certificate']['ok'] or not row.get('budget_allowed', True)):
            raise ValueError('Response selector accepts certified, budget-allowed candidates only')
    features, score = None, None
    selected = event if event is not None else routine
    choice = 'respond' if event is not None else 'routine'
    reason = 'routine_only' if event is None else 'same_task' if routine is not None and event['task'] == routine['task'] else 'forced_event'
    if event is not None and routine is not None and event['task'] != routine['task']:
        features = {
            'risk': event['public_risk']/4.,
            'age': (now-visible_s)/120.,
            'extra_time': (event['certificate']['candidate_finish_s']-routine['certificate']['candidate_finish_s'])/300.,
            'slack_difference': (event['certificate']['minimum_projected_slack_s']-routine['certificate']['minimum_projected_slack_s'])/600.,
        }
        score = rule.score(features)
        choice = 'respond' if score >= 0 else 'defer'
        selected = event if choice == 'respond' else routine
        reason = 'rule'
    if selected is None:
        reason, choice = 'terminal_no_action', 'none'
    return {'selected':selected,'reason':reason,'choice':choice,'features':features,'score':score}
