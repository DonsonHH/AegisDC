"""Offline certificate for the two registered cold, unit-demand task families.

This module has no dispatch entry point. A bound is certified only when a
separately observed, legal production trajectory attains the capacity bound.
"""
from fractions import Fraction

TOL = Fraction(1, 10**8)


def q(value):
    return Fraction(str(value))


def require(ok, detail):
    if not ok:
        raise ValueError(detail)


def parameters(scenario):
    return {row['id']: q(row['value']) for row in scenario['parameters']}


def max_delivery(p, network, storage):
    """Relax pump draw, thermal trip and grid shortage; never relax the rectifier."""
    require(p['service_demand'] == p['compute_service_capacity'] == 1, 'unit demand/compute')
    capacity = [Fraction(1), network, storage]
    names = ['compute', 'network', 'storage']
    requested = [p[n + '_demand_power'] * min(Fraction(1), cap)
                 for n, cap in zip(names, capacity, strict=True)]
    share = min(Fraction(1), p['rectifier_capacity'] * p['rectifier_efficiency'] / sum(requested))
    return min(Fraction(1), *(min(cap, draw * share / p[n + '_nominal_power'])
                              for n, cap, draw in zip(names, capacity, requested, strict=True)))


def segments_loss(segments):
    return sum(((end - start) * (1 - service) for start, end, service in segments), Fraction(0))


def show_segments(rows):
    return [[str(x) for x in row] for row in rows if row[0] < row[1]]


def first_slice(item, events, horizon):
    p = parameters(item)
    state = {'network_service_capacity': p['network_service_capacity'],
             'storage_service_capacity': p['storage_service_capacity']}
    knots = {q(e['time_s']) for e in events} | {Fraction(0), q(horizon)}
    points = sorted(knots)
    profile = []
    for start, end in zip(points, points[1:]):
        for event in events:
            if q(event['time_s']) == start:
                require(event['parameter_id'] in state, 'unregistered fixed boundary')
                state[event['parameter_id']] = q(event['value'])
        y = max_delivery(p, state['network_service_capacity'], state['storage_service_capacity'])
        profile.append((start, end, y))
    return segments_loss(profile), show_segments(profile)


def cold(item):
    p = parameters(item['scenario'])
    program = item['dispatch_program']
    cfg = program['policy_program']
    n = cfg['types']['N']
    require({op['kind'] for op in program['intervention_program']['profile']['operations']}
            == {'clean_filter', 'restore_network_capacity'}, 'physical action support')
    require(n['setting'] == 1 and cfg['pose'][n['worker']] == cfg['pose'][n['tool']] == n['location']
            and n['qualification'] in cfg['qualification'][n['worker']], 'N reach/qualification')
    require(cfg['horizon'] == cfg['deadline'] == 12 and not item['boundary_events'], 'cold scope')
    require(cfg['clock'] == [k / 4 for k in range(49)], 'public clock')
    opens = [q(r['arrived']) for r in program['order_channel'] if r['desk'] == n['desk']]
    require(len(opens) == 1, 'one network work order')
    opening = opens[0]
    clock = list(map(q, cfg['clock']))
    H, latency, ttl = q(cfg['deadline']), q(cfg['latency']), q(cfg['paid_ttl'])
    work = q(n['work_s']) + q(cfg['gate'])
    g, s = p['network_service_capacity'], p['storage_service_capacity']
    before = max_delivery(p, g, s)
    after = max_delivery(p, Fraction(1), s)
    options = [(H * (1 - before), None, [], [(Fraction(0), H, before)])]
    feasible = 0
    # Dropping all C work relaxes contention and heat but cannot accelerate any N
    # task: the dedicated worker/tool already start on site. Only N.A can write g.
    # Enumerate every possible delay, including waiting to reduce the R envelope.
    phases = ('I', 'A', 'R') if n['require_probe'] else ('A', 'R')
    # For these frozen deterministic, zero-error inputs compute-permitted gives
    # the best possible service. Positive evidence is still necessary. With g=1
    # repair cannot raise capacity. Mixed low g and e is a legal measured positive.
    for ai in clock:
        effect = ai + work
        if not (opening <= ai and q(n['write'][0]) <= ai and effect < q(n['write'][1])):
            continue
        if after <= before:
            continue
        probes = [None]
        if n['require_probe']:
            if g >= 1:
                continue
            probes = [t for t in clock if opening <= t and t + work + latency <= ai < t + work + ttl
                      and all(v is not None and q(v[0]) <= t and t + work < q(v[1])
                              for v in n['read'].values())]
        release_r = effect + latency
        for probe in probes:
            # R is a mandatory own review. Choosing the earliest available R
            # suffices for existence given no further N work, but examine all ticks.
            for rt in clock:
                if rt < release_r or rt + work + latency > H:
                    continue
                if not all(v is not None and q(v[0]) <= rt and rt + work < q(v[1]) for v in n['read'].values()):
                    continue
                if not (q(cfg['shift'][n['worker']][0]) <= (ai if probe is None else probe)
                        and rt + work <= q(cfg['shift'][n['worker']][1])):
                    continue
                debit = (len(phases)-1) * (H-opening) + H-release_r
                if any(debit > q(v) for v in cfg['caps'][:2]) or q(cfg['fee'])*len(phases)>q(cfg['caps'][2]):
                    continue
                feasible += 1
                steps = [v for v in (probe, ai, rt) if v is not None]
                profile = [(Fraction(0), effect, before), (effect, H, after)]
                options.append((segments_loss(profile), effect, steps, profile))
    loss, effect, issue, curve = min(options, key=lambda o: o[0])
    return dict(minimum_lower_bound=str(loss), capacity_profile=show_segments(curve),
                relaxed_N_effect=None if effect is None else str(effect),
                projected_chain=[] if effect is None else list(zip(phases, map(str, issue))),
                feasible_projected_schedules=feasible, before=str(before), after=str(after))
