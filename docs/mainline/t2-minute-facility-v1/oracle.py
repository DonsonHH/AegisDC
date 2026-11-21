"""Evaluation-side analytic bounds. Public baselines never import this module."""
import math
from fractions import Fraction

from facility_inputs import H


def schedule_certificate(item):
    native=item['native'];pr=native['dispatch_program']['policy_program'];ev=item['evaluation']
    family=ev['family'];group=ev['group'];target=ev['target'];typ=pr['types'][target]
    duration=typ['work_s']+pr['gate']+(120 if target=='C' else 0)
    legal=[t for t in pr['clock'] if t>=pr['shift'][typ['worker']][0] and typ['write'][0]<=t and t+duration<typ['write'][1]
           and math.ceil((t+duration+pr['latency'])/60)*60+pr['gate']+typ['work_s']+pr['latency']<=H]
    if group in ('reference','mask'):
        if family in ('WATER_HEAT','COOLING_ACCESS') and group=='mask':
            proof='STORAGE_ZERO_THROUGHOUT'
            lower=H
        elif family=='NETWORK_POWER' and group=='mask':
            p={v['id']:v['value'] for v in native['scenario']['parameters']}
            t=ev['latent']['demand_start']; ratio=Fraction(str(p['rectifier_capacity']))*Fraction(str(p['rectifier_efficiency']))/2200000
            lower=float((H-t)*(1-min(1,ratio)));proof='FIXED_RECTIFIER_NO_EFFECTIVE_WRITABLE_CAPACITY'
        elif family=='RESERVE_TRANSFER' and group=='mask':
            lower=ev['latent']['return']-ev['latent']['onset'];proof='GRID_OUT_NO_GENERATOR_OR_IT_UPS'
        else:
            lower=0;proof='NONNEGATIVE_LOSS_WITH_NATIVE_HOLD_ATTAINMENT'
        return dict(plan={},lower=lower,proof=proof,last_start=None)
    if not legal:raise ValueError('Registered actionable branch absent')
    if family in ('WATER_HEAT','COOLING_ACCESS'):
        # Prove the last possible issue by producing a zero-loss native trajectory at this exact tick.
        feasible=[t for t in legal if t+duration>=ev['latent']['onset']]
        last=max(feasible);t=last;lower=0;proof='ZERO_AT_LAST_LEGAL_FILTER_START'
    elif family=='NETWORK_POWER':
        last=max(t for t in legal if t+duration<=ev['latent']['demand_start'])
        t=last;lower=0;proof='ZERO_AT_LAST_LEGAL_NETWORK_START_BEFORE_LOAD'
    else:
        t=min(legal);last=None
        p={q['id']:q['value'] for q in native['scenario']['parameters']}
        early=(1-p['network_service_capacity'])*(t+duration)
        lower=early+ev['latent']['return']-ev['latent']['onset']
        proof='EARLIEST_NETWORK_WRITE_PLUS_UNSUPPLIED_GRID_INTERVAL'
    return dict(plan={t:item['public']['own_instance'][target]+'/A'},lower=lower,proof=proof,last_start=last)
