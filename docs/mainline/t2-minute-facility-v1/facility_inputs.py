"""Construct the minute facility from immutable V6 templates, without importing the plant."""
import gzip
import hashlib
import json
from copy import deepcopy
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
TEMPLATES = ROOT / 'docs/mainline/v6-joint-engineering-v1/inputs.json.gz'
H = 3600
CLOCK = list(range(0, H + 1, 60))
KINDS = ('C', 'N')


def read(path):
    return json.loads(Path(path).read_bytes())


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def write(path, value):
    with Path(path).open('x', encoding='utf8') as output:
        json.dump(value, output, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        output.write('\n')


def templates():
    raw = TEMPLATES.read_bytes()
    if hashlib.sha256(raw).hexdigest() != 'd7f3a8e1bd681427e05ea5072cf10b94df9ddc88ffed49a9f5fbc268385e5ea9':
        raise ValueError('Original joint input package changed')
    return json.loads(gzip.decompress(raw))


def message(kind, origin, topic, at=0, arrival=0, until=H+1, copy=None, label=None):
    desk, target = ('cooling-service-desk', 'intake_pump') if kind == 'C' else ('network-service-desk', 'network')
    return dict(id=label or f'{topic}/{origin}', origin=origin, desk=desk, target=target, observable=topic,
                value=True, at=at, arrived=arrival, until=until, copied_from=copy, revoked_at=None)


def epoch_event(t, field, value):
    return dict(time_s=t, parameter_id=field, value=value, source_note='T2 synthetic facility boundary')


def materialize(source, design):
    """Only the public program is delivered to dispatch. Events and parameters stay with the plant."""
    timing = read(PACKAGE/'timing.json')
    donor = source['S12']['dispatch_program']
    base = source[design['initial']]
    scenario = deepcopy(base['scenario'])
    updates = timing['scenario_parameters'] | design['physical']
    by_name = {p['id']:p for p in scenario['parameters']}
    for name, value in updates.items():
        row = by_name[name]
        if not row['valid_range'][0] <= value <= row['valid_range'][1]:
            raise ValueError('Outside V6 parameter range: '+name)
        row['value'] = value
    prog = deepcopy(donor)
    cfg, crew = prog['policy_program'], prog['workforce_profile']
    crew.update(id='t2-minute-professionals', access_check_s=timing['gate'], feedback_latency_s=timing['latency'])
    crew['walk_times_s'] = {k:(timing['long_walk'] if k=='a3' else timing['short_walk']) for k in crew['walk_times_s']}
    crew['work_times_s'] = {k:timing['work_s'] for k in crew['work_times_s']}
    crew['shifts'] = {k:[0,H] for k in crew['shifts']}
    cfg.update(method='HOLD', horizon=H, deadline=H, clock=list(CLOCK), gate=timing['gate'],
               latency=timing['latency'], paid_ttl=timing['paid_ttl'], fixed_ttl=timing['fixed_ttl'],
               fixed_epochs=list(design['fixed_epochs']), fixed_on=['lake','network','service'],
               fee=1, caps=[timing['occupation_limit'],timing['occupation_limit'],timing['fee_limit']])
    cfg['shift']={k:[0,H] for k in cfg['shift']}
    for a,b in zip(cfg['routes'],prog['nominal_knowledge']['graphs']['access'],strict=True):
        if (a['a'],a['b'])!=(b['from'],b['to']):
            raise ValueError('Native public route order drift')
        a['travel']=crew['walk_times_s'][b['id']]
    for kind,typ in cfg['types'].items():
        typ['write'] = list(design['grants'][kind])
        typ['read']={k:[0,H] for k in typ['read']}
        typ.update(work_s=timing['work_s'], max_origins=4, require_probe=False)
    intervention=prog['intervention_program']
    intervention['profile']['feedback_latency_s']=timing['latency']
    for grant in intervention['profile']['authorizations']:
        grant['starts_at_s'],grant['expires_at_s']=design['grants'][grant['id'][-1]]
    for op in intervention['profile']['operations']:
        op['minimum_work_s']=timing['work_s']
    proto_tasks={t['id']:t for t in donor['task_catalog']}
    proto_see={b['task']:b for b in donor['inspection_program']['bindings']}
    proto_write={b['task_id']:b for b in donor['intervention_program']['bindings']}
    prog['task_catalog']=[]; prog['inspection_program']['bindings']=[];intervention['bindings']=[]
    prog['order_channel']=deepcopy(design['records'])
    for k, origin, phases in design['catalog']:
        for phase in phases:
            parent=f'{k}/{k.lower()}0/{phase}'; key=f'{k}/{origin}/{phase}'
            task=deepcopy(proto_tasks[parent]);task.update(id=key,deadline_s=H)
            prog['task_catalog'].append(task)
            if phase=='A':
                entry=deepcopy(proto_write[parent]);entry['task_id']=key;intervention['bindings'].append(entry)
            else:
                obs=deepcopy(proto_see[parent]);obs.update(task=key,fields=deepcopy(cfg['types'][k]['read']),
                    ttl=timing['paid_ttl'],latency=timing['latency'],minimum_work_s=timing['work_s'])
                prog['inspection_program']['bindings'].append(obs)
    return dict(scenario=scenario,duration_s=H,step_s=design['step'],boundary_events=deepcopy(design['events']),
                action_commands=[],work_requests=[],dispatch_program=prog,business_program=None)


def qualification_design(step):
    records=[message('C','c0','problem_reported'),message('C','c1','problem_reported'),
             message('N','n0','problem_reported'),message('C','notice','alarm',10,25,95),
             message('C','notice','alarm',10,45,95,copy='alarm/notice',label='relay/notice'),
             message('N','stale','alarm',25,125,110)]
    return dict(initial='T03',physical={},step=step,
                events=[epoch_event(0,'filter_resistance_multiplier',100)],
                records=records, fixed_epochs=list(range(0,H+1,300)),
                grants={k:[0,H] for k in KINDS},
                catalog=[['C','c0','IAR'],['C','c1','IAR'],['N','n0','IAR']])
