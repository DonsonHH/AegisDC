"""Preregistered Pareto exploration and conservative adoption, no business exchange rate."""
import statistics


def vector(result):
    rows=result['rows'];metrics=[v['metrics'] for v in rows]
    if len(rows)!=6 or any(not v['audit']['passed'] or v['metrics']['numeric_scoring_failures'] for v in rows):return None
    waits=[v['consequence_weighted_censored_delay_s'] for v in metrics if v['consequence_weighted_censored_delay_s'] is not None]
    return [statistics.mean(v['missed_segments'] for v in metrics),statistics.mean(waits) if waits else 0.,statistics.mean(v['travel_m'] for v in metrics)]


def dominates(a,b):
    return a is not None and b is not None and all(x<=y+1e-9 for x,y in zip(a,b)) and any(x<y-1e-9 for x,y in zip(a,b))


def retain(parent,candidate,references):
    a,b=vector(parent),vector(candidate)
    blocked=[name for name,result in references.items() if dominates(vector(result),b)]
    accepted=dominates(b,a) and not blocked
    return (candidate if accepted else parent),{'accepted':accepted,'parent_vector':a,'candidate_vector':b,
        'dominated_by':blocked,'reason':'Child must Pareto-dominate parent and not be dominated by T/R; otherwise archive and keep parent.'}


def adopt(tour,archive):
    eligible=[]
    def count(r):return sum(v['metrics']['completed_inspections'] for v in r['rows'])
    for name,result in archive.items():
        if name not in ('H','S1','S2','Q1','Q2'):continue
        if dominates(vector(result),vector(tour)) and count(result)>=count(tour) and not any(dominates(vector(other),vector(result)) for other in archive.values()):eligible.append(name)
    return {'selected':eligible[0] if eligible else 'T','eligible_in_fixed_order':eligible,
        'rule':'Pareto-dominate T, no other archive dominance, complete>=T; earliest H,S1,S2,Q1,Q2. No qualified candidate=>T.'}
