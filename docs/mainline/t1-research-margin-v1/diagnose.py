"""T1 Slurm-only, evaluator-side batch. No optimizer is imported into the facility."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from copy import deepcopy
from fractions import Fraction

from bounds import TOL, cold, first_slice, q, require

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MAIN = Path('/share/home/renly/renly-patrol-rsi/mainline')
CORE = MAIN / 'V6-cold-launch-release-v1/source'
DATA = ROOT / 'docs/mainline'
FIRST = MAIN / 'V6-native-method-study-v1/jobs'
DEV = MAIN / 'R4-public-development-20261116/attempt-01/result'
HIST = DATA / 'review-gated/R4'


def read(path):
    with (gzip.open(path, 'rt') if path.suffix == '.gz' else path.open(encoding='utf-8')) as f:
        return json.load(f)


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def logical(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        f.write('\n')


def record(out, event):
    with (out / 'events.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(event, separators=(',', ':')) + '\n')


def common_inputs():
    return read(DATA / 'v6-stage-three-cold-v2/study-inputs.json.gz')


def check_bundle():
    require(os.environ.get('SLURM_JOB_ID') and os.environ.get('SLURM_CPUS_PER_TASK') == '1', 'allocation required')
    pin = read(HERE / 'freeze.json')
    for name, wanted in pin['files'].items():
        require(sha(ROOT / name) == wanted, 'frozen input/solver ' + name)
    launch = read(DATA / 'v6-stage-three-cold-launch-v1/launch-manifest.json')
    for name, wanted in launch['core_files'].items():
        require(sha(CORE / name) == wanted, 'historical runtime ' + name)
    require(sha(Path(sys.executable)) == launch['python']['sha256'], 'interpreter')
    return pin, launch


def native_child(row, kind, out):
    pin, launch = check_bundle()
    require(kind in ('HOLD','N_DIRECT','N_PROBE'), 'registered native witness')
    item = common_inputs()[row+'-J']
    base = logical(item)
    spec = next(x for group in launch['groups'] for x in group['positions'] if x['input_key']==row+'-J')
    require(base == spec['complete_call_sha256'], 'original input binding')
    cfg = item['dispatch_program']['policy_program']
    cfg['method'] = kind
    actual_input = logical(item)
    require(actual_input == pin['cold_inputs'][row]['registered_derivatives'][kind], 'precommitted diagnostic input')
    sys.path[:0] = [str(CORE/'src'), str(CORE/'scripts')]
    from aegis_dc.plant import simulate_scenario
    from cold3_evaluation import score_arm
    unit = out / (row+'-'+kind)
    unit.mkdir()
    save(unit/'entry.json', dict(purpose='T1_DIAGNOSTIC_ONLY', job=os.environ['SLURM_JOB_ID'],
                                pid=os.getpid(), original=base, chosen=actual_input, method=kind))
    run = simulate_scenario(item['scenario'], duration_s=item['duration_s'], step_s=item['step_s'],
                            boundary_events=item['boundary_events'], work_requests=item['work_requests'],
                            action_commands=item['action_commands'], dispatch_program=item['dispatch_program'],
                            business_program=item['business_program'], private_physical_audit=item['private_physical_audit'])
    raw = unit / 'run.json.gz'
    with gzip.open(raw,'xt',encoding='utf-8',compresslevel=1) as f:
        json.dump(run,f,separators=(',',':'),allow_nan=False)
    score = score_arm(item, run)
    require(run['code_identity']['source_tree_sha256']==launch['core_tree'] and score['private_inputs_digest']==actual_input,
            'native output identity')
    require(score['status']=='OK' and not score['violations'] and len(score['decisions'])==49,'native score/clock')
    if kind=='HOLD':
        require(not score['stages'] and not score['all_writes'] and not any(score['resources']), 'P had manual work')
    keep=('status','service','stages','all_writes','resources','admission','paid_fields','work_outcomes','effects',
          'states','violations','private_inputs_digest','runtime')
    summary={k:score[k] for k in keep}
    summary.update(raw_sha256=sha(raw),score_sha256=logical(score),clock=len(score['decisions']),method=kind,
                   pid=os.getpid(),job=os.environ['SLURM_JOB_ID'])
    with gzip.open(unit/'score.json.gz','xt',encoding='utf-8',compresslevel=1) as f:
        json.dump(score,f,separators=(',',':'),allow_nan=False)
    save(unit/'return.json',summary)


def run_child(row, kind, out):
    record(out,dict(event='before_native',row=row,method=kind))
    subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'native',row,kind,str(out)],check=True)
    result=read(out/(row+'-'+kind)/'return.json')
    record(out,dict(event='after_native',row=row,method=kind,raw=result['raw_sha256'],calls=result['clock']))
    return result


def close_to_bound(s, minimum):
    return s['status']=='OK' and not s['violations'] and all(
        abs(Fraction(value)-minimum) <= TOL for typ in ('balance','rate') for value in s['service'][typ])


def diagnostic_cold(row, inputs, old, out):
    item=inputs[row+'-J']
    bound=cold(item)
    minimum=Fraction(bound['minimum_lower_bound'])
    p=run_child(row,'HOLD',out)
    original=next(x for x in old['rows'] if x['row']==row)['positions']
    pool=[('T1-P',p)] + [(k,v['actual']) for k,v in original.items()]
    witnesses=[(k,s) for k,s in pool if close_to_bound(s,minimum)]
    extra=[]
    if not witnesses:
        mode='N_PROBE' if item['dispatch_program']['policy_program']['types']['N']['require_probe'] else 'N_DIRECT'
        s=run_child(row,mode,out)
        extra.append(mode)
        pool.append(('T1-'+mode,s))
        if close_to_bound(s,minimum):
            witnesses.append(('T1-'+mode,s))
    observed={'P':p, 'B':original[row+'-B']['actual'], 'J':original[row+'-J']['actual']}
    result=dict(row=row,bound=bound,certified=bool(witnesses),baseline='T1 diagnostic P only',
                historical_P=False,extra_native=extra,
                comparisons={arm:{'service':s['service'],'gap':str(Fraction(s['service']['rate'][0])-minimum)
                                  if witnesses else None} for arm,s in observed.items()},
                witness=[dict(identity=k,stages=s['stages'],effects=s['effects'],resources=s['resources'],
                              admission=s['admission'],paid_fields=s['paid_fields'],service=s['service'],
                              violations=s['violations']) for k,s in witnesses[:1]],
                frozen_scope_sensitivity=None,P_native={k:p[k] for k in ('raw_sha256','score_sha256','private_inputs_digest','clock','pid','job')})
    if row=='C03':
        result['frozen_scope_sensitivity']=dict(scope='Also retaining J/B zero-support elective abstention after legal mixed read',
                min_L=original[row+'-J']['actual']['service']['rate'][0],
                reason='A concrete positive measurement can permit N.A physically; J/B abstain after zero support. Without N.A the same rectifier/network cap binds.')
    save(out/(row+'.json'),result)
    return result


def best_row(arms, valid):
    levels={k:dict(L=str(q(v['L'])),U=str(q(v['U'])),eligible=bool(valid[k])) for k,v in arms.items()}
    def best(keys):
        if not keys:return None
        loss=min(Fraction(levels[k]['L']) for k in keys)
        tied=[k for k in keys if abs(Fraction(levels[k]['L'])-loss)<=TOL]
        return dict(arms=tied,L=str(loss),P_minus_best=str(Fraction(levels['P']['L'])-loss))
    return dict(arms=levels,raw_best=best(list(arms)),eligible_best=best([k for k in arms if valid[k]]))


def read_london():
    records=[]
    dev=read(HIST/'public-development-v1/terminal.json')
    indexed={a['condition_id']:a for a in dev['records']}
    for r in dev['rows']:
        row=r['condition_id']
        path=DEV/indexed[row]['file'];require(sha(path)==indexed[row]['sha256'],'dev original '+row)
        raw=read(path);arms=r['arms'];aa=raw['actual']['arms']['P']['final_audit']
        state=[dict(start=s['start'],end=s['end'],state=[s['source'],s['power'],s['demand'],s['service'],s['device'],s['isolated']])
               for s in aa['segments']]
        valid={k:v['hard_constraints_ok'] and v['trace_status']=='COMPLETE' for k,v in arms.items()}
        records.append(london_row('dev19',row,arms,valid,r['valid_comparison'],state,raw['condition']['common']))
    ext=read(HIST/'finite-extension-study-v1/paired-results.json')
    for r in ext['rows']:
        arms=r['arms']
        valid={k:not v['violated_constraints'] and v['L'] is not None for k,v in arms.items()}
        records.append(london_row('ext35',r['slot'],arms,valid,r['eligible'],arms['P']['service_states'],r['preclassified']))
    return records


def london_row(batch,row,arms,valid,pair_eligible,states,common):
    spells=[]
    supply=[]
    loss=unserved=Fraction(0)
    for s in states:
        a,b=q(s['start']),q(s['end'])
        source,_,d,y,device,isolated=s['state']
        if not supply or supply[-1][2]!=source:supply.append([float(a),float(b),source])
        else:supply[-1][1]=float(b)
        if q(d)<=q(y):continue
        reason='BOOT_AFTER_POWER_RETURN' if device=='BOOTING' else 'NO_POWER_AFTER_RESERVE' if source is None else device
        gap=q(d)-q(y)
        loss+=(b-a)*gap/q(d);unserved+=(b-a)*gap
        if spells and spells[-1][1]==float(a) and spells[-1][2:]==[reason,d,y]:
            spells[-1][1]=float(b)
        else:spells.append([float(a),float(b),reason,d,y])
    require((loss,unserved)==(q(arms['P']['L']),q(arms['P']['U'])),'historical P intervals '+row)
    return dict(batch=batch,row=row,**best_row(arms,valid),original_pair_eligible=pair_eligible,
                P_loss_spells=spells,P_supply=supply,
                P_cause_inputs={k:common[k] for k in ('tF','tR','family','ready','permit','exec_fault','cB','vB') if k in common})


def read_first():
    archive=read(DATA/'v6-native-method-study-v1/result.json')
    manifest=read(DATA/'v6-native-research-launch-v1/research-manifest.json')
    rows=[]
    for group in manifest['groups']:
        name=group['condition'];values={};valid={}
        saved={v['arm']:v for v in archive['arms'] if v['condition']==name}
        for k,v in saved.items():
            s=v['score'];values[k]=dict(zip(('L','U'),s['service']['rate']))
            valid[k]=v['state']=='COMPLETED' and not s['violations']
        path=FIRST/name/'arms'/(name+'-P')
        model=read(path/'model.json');events=read(path/'inputs.json')['boundary_events']
        grant=read(path/'dispatch-program.json')['intervention_program']['profile']['operations']
        require(all(op['kind']=='clean_filter' for op in grant),'first-slice operation')
        ids=group['arm_inputs']['P']
        require(logical(model)==ids['scenario'] and logical(events)==ids['events']
                and logical(read(path/'dispatch-program.json'))==ids['dispatch'],'first input identities')
        scr=read(path/'score.json');raw=path/'run/run.json'
        require(scr['native_sha256']==sha(raw)==saved['P']['process_account']['native_sha256'] and
                scr['service']['rate']==saved['P']['score']['service']['rate'],'first P return')
        minimum,curve=first_slice(model,events,10)
        certified=all(abs(Fraction(v)-minimum)<=TOL for u in ('balance','rate') for v in scr['service'][u])
        p=parameters_for_evidence(model)
        rows.append(dict(batch='V6-17',row=name,**best_row(values,valid),P_profile=scr['service']['profile'],
                         frozen_events=events,rectifier=p['rectifier_capacity'],efficiency=p['rectifier_efficiency'],
                         bound=str(minimum),capacity_profile=curve,certified=certified,witness='archived native P, zero manual work',
                         gaps={k:str(q(values[k]['L'])-minimum) if certified else None for k in ('P','D','V')},
                         P_source_sha256=sha(raw)))
    return rows


def parameters_for_evidence(model):
    return {p['id']:p['value'] for p in model['parameters']}


def main():
    if sys.argv[1]=='native':
        native_child(sys.argv[2],sys.argv[3],Path(sys.argv[4]))
        return
    pin,_=check_bundle()
    group=sys.argv[1]; out=Path(sys.argv[2]);out.mkdir(exist_ok=False)
    save(out/'start.json',dict(group=group,job=os.environ['SLURM_JOB_ID'],source=sha(Path(__file__)),purpose='T1_DIAGNOSTIC'))
    if group=='saved':
        result=dict(london=read_london(),first=read_first())
    else:
        spec=pin['batches'][group]
        inputs=common_inputs();old=read(DATA/'v6-stage-three-cold-study-v2/result.json')
        result={'cold':[diagnostic_cold(row,inputs,old,out) for row in spec]}
    save(out/'results.json',result)
    print(group,os.environ['SLURM_JOB_ID'],sha(out/'results.json'),flush=True)


if __name__=='__main__':
    main()
