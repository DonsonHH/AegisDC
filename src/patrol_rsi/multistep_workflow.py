"""Small executable workflow grammar. No environment, truth, or code execution."""
from dataclasses import asdict, dataclass, replace
import hashlib
import json

from .meta_schema import strict_json

SCOPES = ('same_pod_other_profession', 'same_pod', 'different_pod', 'global', 'return_tour')
RANKERS = ('risk_lead', 'urgency', 'risk_per_cost')
TOOLS = ('history_and_nominal', 'nominal')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class Workflow:
    after_alarm: str = 'same_pod_other_profession'
    after_normal: str = 'different_pod'
    ranker: str = 'risk_lead'
    estimator: str = 'history_and_nominal'

    def __post_init__(self):
        if self.after_alarm not in SCOPES or self.after_normal not in SCOPES:
            raise ValueError('Unregistered measurement branch')
        if self.ranker not in RANKERS or self.estimator not in TOOLS:
            raise ValueError('Unregistered ranking/estimation tool')

    def to_dict(self):
        return dict(schema='multistep-workflow-v1', **asdict(self))

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) != {'schema', 'after_alarm', 'after_normal', 'ranker', 'estimator'}:
            raise ValueError('Closed workflow schema')
        if value['schema'] != 'multistep-workflow-v1':
            raise ValueError('Workflow version')
        return cls(**{k: v for k, v in value.items() if k != 'schema'})

    @property
    def sha256(self):
        return digest(self.to_dict())


def compile_edit(parent, edit):
    """One bounded child; budgets and interpreter code are never editable."""
    if isinstance(edit, str):
        edit = strict_json(edit)
    if not isinstance(edit, dict) or set(edit) != {'schema', 'parent_sha256', 'changes', 'mechanism'}:
        raise ValueError('Closed edit envelope')
    if edit['schema'] != 'workflow-edit-v1' or edit['parent_sha256'] != parent.sha256:
        raise ValueError('Exact current parent required')
    changes = edit['changes']
    if not isinstance(changes, dict) or not 1 <= len(changes) <= 2 or not set(changes) <= set(asdict(parent)):
        raise ValueError('One or two registered workflow fields')
    if type(edit['mechanism']) is not str or not 1 <= len(edit['mechanism']) <= 700:
        raise ValueError('Explain a bounded mechanism')
    child = replace(parent, **changes)
    if child == parent:
        raise ValueError('A literal duplicate is not a modification')
    return child


def rank_value(candidate, ranker):
    if ranker == 'urgency':
        return candidate['age_ratio'] + candidate['eta_ratio']
    if ranker == 'risk_per_cost':
        return (.01 + candidate['rank_signal']) * candidate['weight'] / (.03 + candidate['eta_ratio'])
    if ranker == 'risk_lead':
        return candidate['rank_signal'] * candidate['weight'] * candidate['lead_s'] / 300.
    raise ValueError('Unknown ranking tool')


def select_follow_up(workflow, candidates, first_measurement, now):
    """Candidate pool is already certified; relatedness is a public topology cue.

    A positive first reference can support checking another profession in its
    pod. It does not assert a diagnosed failure or a calibrated probability.
    Unrelated work requires its own positive public cue.
    """
    if first_measurement['time_s'] > now:
        raise ValueError('Only an actually completed reference can branch')
    scope = workflow.after_alarm if first_measurement['alarm'] else workflow.after_normal
    if scope == 'return_tour':
        return None
    pool = [r for r in candidates if r['task'] != first_measurement['task'] and not r['already_alarm']
            and (r['rank_signal'] >= .05 or first_measurement['alarm'] and r['pod'] == first_measurement['pod'])]
    if scope == 'same_pod_other_profession':
        preferred = [r for r in pool if r['pod'] == first_measurement['pod'] and r['kind'] != first_measurement['kind']]
    elif scope == 'same_pod':
        preferred = [r for r in pool if r['pod'] == first_measurement['pod']]
    elif scope == 'different_pod':
        preferred = [r for r in pool if r['pod'] != first_measurement['pod']]
    else:
        preferred = pool
    pool = preferred or pool
    return max(pool, key=lambda r: (rank_value(r, workflow.ranker), -r['task']), default=None)
