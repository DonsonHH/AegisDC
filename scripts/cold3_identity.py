"""Canonical metadata commitments; no simulator, selector or evaluator dependencies."""
import hashlib
import json
from copy import deepcopy
from fractions import Fraction


def raw_hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _typed(value):
    if isinstance(value,bool) or value is None or isinstance(value,str):return value
    if isinstance(value,(int,float)):
        number=Fraction(value);return ['number',number.numerator,number.denominator]
    if isinstance(value,list):return ['array',[_typed(item) for item in value]]
    if isinstance(value,dict):return ['object',[[k,_typed(value[k])] for k in sorted(value)]]
    raise TypeError('Unsupported frozen data')


def semantic_hash(value):
    return raw_hash(_typed(value))


def public_config(cfg):
    cfg=deepcopy(cfg);cfg.pop('method',None)
    if 'worlds' in cfg:cfg['worlds'].sort(key=lambda w:w['origin'])
    return cfg


def public_keys(cfg,view):
    v=deepcopy(view)
    for channel in ('orders','work','writes','paid','fixed'):
        v[channel].sort(key=semantic_hash)
    state=semantic_hash(v)
    return [state,semantic_hash([public_config(cfg),state])]


def binding_keys(item):
    dispatch=deepcopy(item['dispatch_program'])
    cfg=dispatch['policy_program'];method=cfg.get('method',cfg.get('policy'))
    dispatch['policy_program']=public_config(cfg)
    if 'order_channel' in dispatch:dispatch['order_channel'].sort(key=semantic_hash)
    if 'task_catalog' in dispatch:dispatch['task_catalog'].sort(key=lambda r:r['id'])
    physics=semantic_hash([item['scenario'],item['boundary_events'],item['duration_s'],item['step_s'],item.get('action_commands',[]),item.get('work_requests',[])])
    design=semantic_hash(dispatch)
    return dict(full=raw_hash(item),physics=physics,scenario=raw_hash(item['scenario']),design=design,
                method_context=semantic_hash([design,method]),semantic=semantic_hash([physics,design,method,item.get('business_program')]))
