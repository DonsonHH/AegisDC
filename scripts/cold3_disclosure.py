"""Hash existing frozen documents and public snapshots only. No policy, facility or forecast imports."""
from collections import defaultdict
from copy import deepcopy
import gzip,hashlib,json
from pathlib import Path

P=Path('docs/mainline/v6-stage-three-cold-v2')
def read(p):
    b=p.read_bytes()
    return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)
def h(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
from cold3_identity import binding_keys as keys, public_keys
def rootcfg(cfg,orders,t):
    return dict(time=t,orders=[r for r in orders if r['arrived']<=t],issued=[],work=[],writes=[],paid=[],fixed=[])
def prefix(cfg,v,t):
    v=deepcopy(v);v['time']=t
    for k in ('orders','work','writes','paid','fixed'):
        v[k]=[r for r in v[k] if r['at']<=r['arrived']<=t]
    v['issued']=[r for r in v['issued'] if r['at']<=t]
    for row in v['orders']:
        if row['revoked_at'] is not None and row['revoked_at']>t:row['revoked_at']=None
    return public_keys(cfg,v)
def roots(x):
    prog=x['dispatch_program'];cfg=prog['policy_program'];orders=prog['order_channel']
    times=sorted({0.,float(min(r['arrived'] for r in orders))})
    # Use the native public clock's numeric representation (short ticks are binary64).
    return {f'{t:g}':prefix(cfg,rootcfg(cfg,orders,t),t) for t in times}

E=read(P/'engineering-inputs.json.gz');S=read(P/'study-inputs.json.gz');direct=read(P/'direct.json')
Q=Path('docs/mainline/v6-joint-engineering-v1/inputs.json.gz');prior=read(Q)
T=Path('docs/mainline/v6-joint-terminal-v1/fixtures.json');terminal=read(T)
H10=Path('docs/mainline/v6-native-method-comparison-v1/conditions.json');old=read(H10)
index={name:defaultdict(list) for name in ('full','physics','scenario','design','method_context','semantic')}
prefixes=[defaultdict(list),defaultdict(list)]
def add_prefix(tag,hashes):
    for idx,key in zip(prefixes,hashes):idx[key].append(tag)
def add(tag,item):
    for k,v in keys(item).items():index[k][v].append(tag)
    if item['dispatch_program'].get('schema')=='aegisdc-policy-run-program-v6':
        for t,pair in roots(item).items():add_prefix(tag+'@'+t,pair)
for key,x in E.items():add('engineering/'+key,x)
for key,x in prior.items():
    if 'scenario' in x:add('joint-v1/'+key,x)
    elif 'view' in x:
        times=x.get('args',{}).get('times',[x['view']['time']])
        for t in times:add_prefix(f'joint-v1/{key}@{t:g}',prefix(x['program'],x['view'],t))
for key,x in direct.items():add_prefix('cold-direct/'+key,prefix(x['config'],x['view'],x['view']['time']))
for key,unit in terminal['units'].items():
    if 'source_key' in unit:
        src=prior[unit['source_key']];cfg=src['program'];v=src['view'];t=unit['args'].get('time',v['time'])
    elif unit.get('view'):
        cfg=terminal['programs'][unit['program']];v=unit['view'];t=v['time']
    else:continue
    add_prefix('terminal/'+key,prefix(cfg,v,t))
for row in old['conditions']:
    for arm,ref in row['arms'].items():
        tag='historical-H10/'+row['id']+'-'+arm
        index['full'][ref['complete_call']].append(tag);index['scenario'][ref['scenario']].append(tag)
out={}
for key,x in S.items():
    sig=keys(x);matches={k:index[k].get(v,[]) for k,v in sig.items()};rootmap=roots(x)
    out[key]=dict(hashes=sig,overlaps=matches,known_roots={t:dict(view_sha=v[0],configured_view_sha=v[1],
        view_only=prefixes[0].get(v[0],[]),same_public_configuration=prefixes[1].get(v[1],[])) for t,v in rootmap.items()})
duplicates=defaultdict(list)
for k,r in out.items():duplicates[r['hashes']['semantic']].append(k)
result=dict(schema='cold-before-output-input-disclosure-v1',counts=dict(engineering=len(E),study=len(S),prior_joint_units=len(prior),
    prior_H10=85,terminal_green=len(terminal['green']),terminal_red_repeats=len(terminal['red']),new_direct=len(direct)),
    rule='Full documents, physical horizon/step and exogenous input, scenario-only, entire public design excluding method, method-specific program and complete semantic call. For semantic comparison normalize JSON numeric representations by exact rational value, retain boolean/string type, sort equivalent evidence lists and world/order registries, and exclude private instrumentation. H10 v5 has a different ABI and horizon; compare registered full-call and underlying scenario identities, separately. Work order origins/times, grants and operative fields retained.',
    prefix_rule='Separate exact detached view and same view plus full common decision configuration. Initial and first-opening study frames only. No post-choice study prefix is generated or inspected. Case/arm indices are external. Red repeats carry their old green key in the terminal register.',
    historical_bytes={p.as_posix():sha(p) for p in (Q,T,H10)},study=out,study_duplicates=[v for v in duplicates.values() if len(v)>1],
    complete_engineering_study_matches=[[k,m] for k,v in out.items() for m in v['overlaps']['semantic'] if m.startswith('engineering/')],
    research_executions=0)
(P/'disclosure.json.gz').write_bytes(gzip.compress((json.dumps(result,sort_keys=True,separators=(',',':'))+'\n').encode(),mtime=0))
print('full eng/study',len(result['complete_engineering_study_matches']),'within-study semantic duplicates',result['study_duplicates'])
for kind in index:
 print(kind,sum(any(x.startswith('engineering/') for x in v['overlaps'][kind]) for v in out.values()))
