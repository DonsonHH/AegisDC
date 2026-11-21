"""One-hour qualification only. Run inside a single-CPU Slurm allocation."""
import gzip
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from unittest.mock import patch

from facility_inputs import CLOCK, PACKAGE, ROOT, fingerprint, materialize, qualification_design, read, templates, write

ACTIVITY=Path('/share/home/renly/renly-patrol-rsi/mainline/T2-minute-facility-20261121-v1')
CORE=Path('/share/home/renly/renly-patrol-rsi/mainline/V6-cold-launch-release-v1/source')


def file_hash(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def identity():
    if os.environ.get('SLURM_CPUS_PER_TASK')!='1' or not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Remote single-CPU allocation required')
    pin=read(ROOT/'docs/mainline/v6-stage-three-cold-launch-v1/launch-manifest.json')
    for name,h in pin['core_files'].items():
        if h!=file_hash(CORE/name):
            raise ValueError('Frozen V6 file changed: '+name)
    if file_hash(Path(sys.executable))!=pin['python']['sha256']:
        raise ValueError('Python freeze mismatch')
    return pin


def prepare():
    identity()
    folder=ACTIVITY/'A-inputs';folder.mkdir()
    base=templates();checks={}
    for name,step in [('coarse',.25),('fine',.125)]:
        item=materialize(base,qualification_design(step))
        write(folder/(name+'.json'),item)
        checks[name]=dict(input_sha256=file_hash(folder/(name+'.json')),canonical=fingerprint(item))
    write(folder/'manifest.json',dict(purpose='T2_A_ONLY',inputs=checks,
          independent_expected=file_hash(PACKAGE/'qualification-expected.json'),
          timing=file_hash(PACKAGE/'timing.json'),job=os.environ['SLURM_JOB_ID']))
    print(json.dumps(checks),flush=True)


def extract(run):
    from audit_v6_joint import physiology
    account=physiology(run)
    decisions=run['policy_public_decisions']; trace=run['trace']
    work=run['work_records'];feedback=run['workforce_public_feedback']
    arrivals={a['task_id']:a['arrived_at_s'] for a in feedback if a['status']=='completed'}
    minute={str(int(x['view']['time'])):dict(
        open=x['decision']['opened'],adm=x['decision']['admissions'],
        alarms=x['decision']['active_alarms'],paid=x['decision']['paid_state'],
        raw_notices=[r['id'] for r in x['view']['orders'] if r['observable']=='alarm'])
        for x in decisions}
    overlaps=[]
    for snap in trace:
        state=snap['domains']['people_tools_work']
        if snap['time_s'] in (0,60,75,95,120,155,180,215):
            overlaps.append(dict(t=snap['time_s'],
                workers={k:v['request_id'] for k,v in state['workers'].items() if v['request_id']},
                tools={k:v['reserved_by'] for k,v in state['tools'].items() if v['reserved_by']}))
    first=next((s['time_s'] for s in trace if s['domains']['control_monitoring']['protection_latched']),None)
    sm=run['summary']
    return dict(clock=[d['view']['time'] for d in decisions],minute=minute,overlaps=overlaps,work=[
        [r['id'],r['issued_at_s'],r.get('finished_at_s'),arrivals.get(r['id'])] for r in work],
        statuses=[r['status'] for r in work],paid=run['inspection_public_feedback'],
        writes=run['intervention_private_audit']['events'],account=account,first_trip=first,
        continuous_steps=sm['integration_steps'],max_energy_residual_J=sm['max_energy_residual_J'],
        max_mass_residual_kg=sm['max_mass_residual_kg'],whole_run_energy_residual_J=sm['whole_run_energy_residual_J'],
        physics_step=run['inputs']['maximum_step_s'],runtime=run['code_identity']['source_tree_sha256'])


def check_one(actual,expected):
    audit={}
    def check(name,ok):audit[name]=bool(ok)
    check('61_native_wakes',actual['clock']==CLOCK)
    check('three_named_completed',actual['work']==expected['work'] and actual['statuses']==['completed']*3)
    check('no_physical_writes',not actual['writes'])
    check('two_or_more_open',actual['minute']['0']['open']==['C/c0','C/c1','N/n0'])
    at75=next((r for r in actual['overlaps'] if r['t']==75),{})
    expected_workers={'worker_cooling':'C/c0/I','worker_it':'N/n0/I'}
    check('real_overlap_and_identity', at75.get('workers')==expected_workers and
          at75.get('tools')=={'tool_flow_meter':'C/c0/I','tool_it_diagnostic':'N/n0/I'})
    m=actual['minute']
    for t in expected['shared_worker_tool_deny_at']:
        check('held_same_resources_'+str(t),['C/c1/I','RESOURCE_HELD'] in m[str(t)]['adm'])
    check('copy_same_origin_one',set(m['60']['raw_notices'])=={'alarm/notice','relay/notice'} and m['60']['alarms']==['notice'])
    check('expires_between_ticks',m['0']['alarms']==[] and m['120']['alarms']==[])
    check('late_arrival_cannot_revive_expired','alarm/stale' not in m['120']['raw_notices'] and
          'alarm/stale' in m['180']['raw_notices'] and not m['180']['alarms'])
    for task,data in expected['paid_records'].items():
        check(task+'-not-yet',m[str(data['before'])]['paid'][task]=='PENDING')
        wanted='LOW_FLOW' if task.startswith('C') else 'LOCAL_ADEQUATE'
        check(task+'-live',all(m[str(t)]['paid'][task]==wanted for t in data['live']))
        check(task+'-expired',m[str(data['expired'])]['paid'][task]=='EXPIRED')
    a=actual['account'];check('whole_coverage',a['continuous'])
    check('per_inventory_and_whole_balances',a['conserved'])
    check('physical_and_native_occupations',a['physical_work']==a['native_work']==[225,225])
    check('independent_L_U',all(abs(l-r)<=1e-8 for l,r in zip(a['balance'],a['rate'])))
    lim=expected['coarse_and_fine_each']; tr=actual['first_trip']
    check('real_first_trip',tr is not None and lim['first_trip_range_s'][0]<=tr<=lim['first_trip_range_s'][1])
    check('nontrivial_full_L',lim['L_range_s'][0]<=a['rate'][0]<=lim['L_range_s'][1])
    return audit


def run_one(name,manifest_pin):
    pin=identity();sys.path[:0]=[str(CORE/'src'),str(CORE/'scripts')]
    from aegis_dc import joint_session
    from aegis_dc.plant import simulate_scenario
    from public_gate import engineering_choice
    folder=ACTIVITY/'A-inputs'
    assert file_hash(folder/'manifest.json')==manifest_pin
    manifest=read(folder/'manifest.json');case=folder/(name+'.json')
    assert file_hash(case)==manifest['inputs'][name]['input_sha256']
    item=read(case);assert fingerprint(item)==manifest['inputs'][name]['canonical']
    expected=read(PACKAGE/'qualification-expected.json')
    assert file_hash(PACKAGE/'qualification-expected.json')==manifest['independent_expected']
    out=ACTIVITY/('A-'+name);out.mkdir()
    write(out/'started.json',dict(job=os.environ['SLURM_JOB_ID'],purpose='T2_ENGINEERING',input=file_hash(case)))
    with patch.object(joint_session,'choose',engineering_choice):
        run=simulate_scenario(**item)
    actual=extract(run)
    # Lossless step-ordered raw output remains private. Encode individual rows to keep memory bounded.
    with gzip.open(out/'original.jsonl.gz','wt',encoding='utf8',compresslevel=1) as stream:
        meta={k:v for k,v in run.items() if k not in ('trace','balances')}
        stream.write(json.dumps({'metadata':meta},separators=(',',':'),allow_nan=False)+'\n')
        for row in run['trace']:stream.write(json.dumps({'sample':row},separators=(',',':'),allow_nan=False)+'\n')
        for row in run['balances']:stream.write(json.dumps({'balance':row},separators=(',',':'),allow_nan=False)+'\n')
    checks=check_one(actual,expected);checks['frozen_core']=actual['runtime']==pin['core_tree']
    write(out/'result.json',dict(grid=name,job=os.environ['SLURM_JOB_ID'],input_sha256=file_hash(case),
        manifest=manifest_pin,raw_sha256=file_hash(out/'original.jsonl.gz'),actual=actual,checks=checks,passed=all(checks.values())))
    print(name,actual['first_trip'],actual['account'],[k for k,v in checks.items() if not v],flush=True)
    return all(checks.values())


def compare():
    identity()
    coarse,fine=(read(ACTIVITY/('A-'+k)/'result.json') for k in ('coarse','fine'))
    expected=read(PACKAGE/'qualification-expected.json')['grid_agreement']
    a,b=coarse['actual'],fine['actual']
    diff={'first_trip_absolute_s':abs(a['first_trip']-b['first_trip']),
          'L_absolute_s':abs(a['account']['rate'][0]-b['account']['rate'][0]),
          'U_absolute_unit_s':abs(a['account']['rate'][1]-b['account']['rate'][1])}
    ok=coarse['passed'] and fine['passed'] and all(n<=expected[k] for k,n in diff.items())
    write(ACTIVITY/'A-final.json',dict(passed=ok,delta=diff,limits=expected,
          receipts={k:file_hash(ACTIVITY/('A-'+k)/'result.json') for k in ('coarse','fine')},
          checks_failed={x['grid']:[k for k,v in x['checks'].items() if not v] for x in (coarse,fine)}))
    print('A',ok,diff,flush=True)
    return ok


if __name__=='__main__':
    op=sys.argv[1]
    if op=='prepare':prepare()
    elif op in ('coarse','fine'):
        if not run_one(op,sys.argv[2]):raise SystemExit(2)
    elif op=='compare':
        if not compare():raise SystemExit(3)
    else:raise ValueError(op)
