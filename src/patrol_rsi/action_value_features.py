"""Frozen36 public state/action features. No labels, process IDs or environment input."""
import math
import numpy as np

ROLES=('thermal','electrical','cooling','control')
Z_NAMES=('one','direct_value','raw_cvae','nominal','cvae_minus_nominal','direct_missing','cvae_missing',
    'direct_age','cvae_age','public_risk','qualified_direct','inspection_age',*ROLES)
FEATURE_NAMES=tuple('advance_'+s for s in Z_NAMES)+tuple('delay_'+s for s in Z_NAMES)+(
    'delta_bridge_travel','delta_mean_square_pressure','delta_peak_pressure','timing_change_times_horizon')
ROW_KEYS={'kind','observed_value','direct_available','direct_time_s','source','raw_cvae_temperature_c',
    'raw_cvae_time_s','nominal_temperature_c','risk','weight','last_check_s','deadline_s'}


def task_vector(row,now):
    if set(row)!=ROW_KEYS:raise ValueError('Closed public feature schema only')
    kind=row['kind'];direct=row['direct_available'];cv=row['raw_cvae_temperature_c'] is not None
    for flag,stamp in ((direct,row['direct_time_s']),(cv,row['raw_cvae_time_s'])):
        if flag and (stamp is None or not 0<=stamp<=now):raise ValueError('Causal valid observation time required')
    offsets={'thermal':(50.,20.),'electrical':(38.,30.),'cooling':(33.6,33.6),'control':(0.,18.)}
    offset,scale=offsets[kind]
    raw=(row['observed_value']-offset)/scale if direct else 0.
    c=(row['raw_cvae_temperature_c']-50.)/20. if cv else 0.
    nominal=(row['nominal_temperature_c']-50.)/20.
    values=[1.,raw,c,nominal,c-nominal if cv else 0.,float(not direct),float(not cv),
        min((now-row['direct_time_s'])/1800.,1.) if direct else 1.,
        min((now-row['raw_cvae_time_s'])/1800.,1.) if cv else 1.,row['risk']/4.,
        float(direct and row['source'].startswith('qualified')),
        (now-max(0.,row['last_check_s']))/row['deadline_s'],*[float(kind==role) for role in ROLES]]
    if not all(math.isfinite(v) for v in values):raise ValueError('Finite public values')
    return np.asarray(values,dtype=np.float64)


def finish(c,j):
    values=c['first_completion_s'];return values[j] if j in values else values[str(j)]


def features(rows,original,candidate,now):
    if not 0<=now<=1800 or not rows:raise ValueError('Known mission clock and owned tasks')
    advance=np.zeros(16);delay=np.zeros(16);pressure0=[];pressure=[];magnitude=0.
    for j,row in rows.items():
        f0,f=finish(original,j),finish(candidate,j);d=row['deadline_s'];e=(f0-f)/d
        z=task_vector(row,now);advance+=z*max(e,0.);delay+=z*max(-e,0.);magnitude+=abs(e)
        last=max(0.,row['last_check_s']);pressure0.append((f0-last)/d);pressure.append((f-last)/d)
    n=len(rows)
    tail=[(candidate['segment_and_bridge_travel_s']-original['segment_and_bridge_travel_s'])/300.,
        np.mean(np.square(pressure))-np.mean(np.square(pressure0)),max(pressure)-max(pressure0),magnitude/n*(1800.-now)/1800.]
    output=np.r_[advance/n,delay/n,tail]
    if output.shape!=(36,) or not np.isfinite(output).all():raise ValueError('Frozen finite36 features')
    return output


def public_discrimination(rows,original,candidates):
    scores=[]
    for c in candidates:
        score=0.
        for j,row in rows.items():
            cv=row['raw_cvae_temperature_c'];u=min(abs(cv-row['nominal_temperature_c'])/20.,1.) if cv is not None else 0.
            q=row['risk']/4.+u
            score+=row['weight']*q*(finish(original,j)-finish(c['certificate'],j))/row['deadline_s']
        scores.append(float(score/len(rows)))
    return max(scores)-min(scores)
