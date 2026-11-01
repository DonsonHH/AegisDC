"""Tour-preserving public-evidence advantage with structurally nonnegative costs."""
from dataclasses import dataclass
import math

from .contracts import strict_json, digest

SOURCES=('direct','model','power','cross')
WEIGHTS=(0,.5,1,2)
PENALTIES=(0,.05,.2,1)
MARGINS=(0,.001,.01)
CONTRACT={'source_weights':{'type':'object','keys':list(SOURCES),'values':list(WEIGHTS)},
    'freshness':{'type':'string','values':['flat','linear300']},
    'travel_penalty':{'type':'number','values':list(PENALTIES)},
    'deadline_penalty':{'type':'number','values':list(PENALTIES)},
    'margin':{'type':'number','values':list(MARGINS)},
    'mechanism':{'type':'string','max_length':500}}


@dataclass(frozen=True)
class Rule:
    source_weights:tuple=(1,1,1,1)
    freshness:str='flat'
    travel_penalty:float=.05
    deadline_penalty:float=.2
    margin:float=0

    def __post_init__(self):
        def member(value,values):return type(value) in (int,float) and math.isfinite(value) and value in values
        if type(self.source_weights) is not tuple or len(self.source_weights)!=4 or not all(member(v,WEIGHTS) for v in self.source_weights) or not any(self.source_weights):raise ValueError('Four bounded nonnegative source weights, not all zero')
        if self.freshness not in ('flat','linear300'):raise ValueError('Freshness enum')
        if not all(member(v,PENALTIES) for v in (self.travel_penalty,self.deadline_penalty)):raise ValueError('Nonnegative penalty enum')
        if not member(self.margin,MARGINS):raise ValueError('Margin enum')

    def to_dict(self):
        return {'source_weights':dict(zip(SOURCES,map(float,self.source_weights))),'freshness':self.freshness,
            'travel_penalty':float(self.travel_penalty),'deadline_penalty':float(self.deadline_penalty),'margin':float(self.margin)}

    @property
    def identity(self):return digest(self.to_dict())


def response_example():return {**Rule().to_dict(),'mechanism':'Use public evidence and retain Tour unless net advantage is positive.'}


def response_contract():return {'fields':CONTRACT,'required':list(CONTRACT),'additional_fields':False,'example':response_example()}


def rule_from_dict(value):
    if type(value) is not dict or set(value)!=set(CONTRACT)-{'mechanism'}:raise ValueError('Exact registered rule fields')
    weights=value['source_weights']
    if type(weights) is not dict or set(weights)!=set(SOURCES):raise ValueError('Exact source weight object, never list')
    return Rule(tuple(weights[k] for k in SOURCES),value['freshness'],value['travel_penalty'],value['deadline_penalty'],value['margin'])


def parse_response(raw):
    value=strict_json(raw)
    if type(value) is not dict or set(value)!=set(CONTRACT):raise ValueError('Exactly six rule fields including mechanism')
    mechanism=value['mechanism']
    if type(mechanism) is not str or not 1<=len(mechanism)<=500:raise ValueError('Nonempty mechanism string <=500characters')
    return rule_from_dict({k:v for k,v in value.items() if k!='mechanism'}),mechanism


def require_mutation(child,parent,seen=()):
    if child.identity==parent.identity or child.identity in seen:raise ValueError('Empty or duplicate canonical rule')
    return child


def advantage(features,rule):
    if set(features)!={'gain_plus','gain_minus','delta_travel','delta_pressure'} or not all(type(v) in (int,float) and math.isfinite(v) and abs(v)<=1e6 for v in features.values()):raise ValueError('Finite closed correction features')
    g=features['gain_plus']-features['gain_minus']
    a=g-rule.travel_penalty*max(features['delta_travel'],0)-rule.deadline_penalty*max(features['delta_pressure'],0)
    if not math.isfinite(a) or abs(a)>1e6:raise ValueError('Advantage numeric bound')
    return g,a


def choose_advantage(options,rule):
    original=next(c for c in options if c['original']);selected=original;best=0.
    for candidate in sorted(options,key=lambda c:(not c['original'],c['order'])):
        g,a=advantage(candidate['correction'],rule)
        if candidate['original']:
            if abs(g)>1e-12 or abs(a)>1e-12:raise ValueError('Original advantage must be zero')
        elif g>1e-9 and a>rule.margin+1e-9 and a>best+1e-9:selected,best=candidate,a
    return selected


def risk_value(row,rule,now):
    total=0.;weights=dict(zip(SOURCES,rule.source_weights))
    for c in row['evidence_components']:
        if c['group']=='unknown':continue
        stamp=c['time_s'];value=c['value']
        if stamp is None or value is None or stamp>now or stamp<0:raise ValueError('Valid causal component time required')
        if not math.isfinite(value) or value<0:raise ValueError('Nonnegative public risk component')
        freshness=1. if rule.freshness=='flat' else max(0.,1-(now-stamp)/300.)
        total+=weights[c['group']]*freshness*value
    return min(total,4.)


def relative_features(original,candidate,snapshot,tour,now,rule):
    plus=minus=pressure=0.
    for j in tour:
        row=snapshot[j];f0=original['first_completion_s'][j];f=candidate['first_completion_s'][j]
        r=risk_value(row,rule,now);coefficient=row['weight']*r/row['deadline_s']
        plus+=coefficient*max(f0-f,0.);minus+=coefficient*max(f-f0,0.)
        last=max(0.,row['last_check_s']);d=row['deadline_s']
        pressure+=((f-last)/d)**2-((f0-last)/d)**2
    n=len(tour)
    return {'gain_plus':plus/n,'gain_minus':minus/n,
        'delta_travel':(candidate['segment_and_bridge_travel_s']-original['segment_and_bridge_travel_s'])/300.,
        'delta_pressure':pressure/n}
