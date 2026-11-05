"""Frozen value capture and saved-only committed delivery verification."""
import argparse
from fractions import Fraction
from hashlib import sha256
import json,os,subprocess,sys
from pathlib import Path
from plot_action_value import render
ROOT=Path(__file__).resolve().parents[1]
PROTOCOL='docs/mainline/20-action-value-engineering-protocol.json'
PACKAGE='evidence/mainline/engineering/20-action-value'
INPUTS=('frame','belief_model','risk_catalog','value_model','witness_frame','witness_belief','witness_catalog','witness_value','independent_witness')
def require(ok,msg):
    if not ok:raise ValueError(msg)
def read(p):return json.loads(p.read_bytes())
def digest(raw):return sha256(raw).hexdigest()
def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT)
def blob(rev,n):return digest(git('cat-file','blob',rev+':'+n))
def write(p,v):
    raw=v if isinstance(v,bytes) else (json.dumps(v,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False)+chr(10)).encode()
    with p.open('xb') as f:f.write(raw)
def durable(d):return {p.relative_to(d).as_posix() for p in d.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.pyc','.pyo'}}
def paths(p,s):
    names=git('ls-tree','-rz','--name-only',s,'src',PACKAGE+'/development').decode().strip(chr(0)).split(chr(0))
    return dict(runtime_sources=sorted(n for n in names if n.startswith('src/') and n.endswith('.py')),authoring_tools=p['tools'],frozen_inputs=sorted([PROTOCOL,*[p[k] for k in INPUTS],*p['frozen_documents'],PACKAGE+'/.gitattributes',*[n for n in names if n.endswith('.log')]]))
def unchanged(s,pins):return git('rev-parse','HEAD').decode().strip()==s and all(digest((ROOT/n).read_bytes())==h for rows in pins.values() for n,h in rows.items())
def capture(d,p):
    require(not git('status','--porcelain'),'Capture checkout must be clean')
    require(Path(os.environ.get('PYTHONPATH','')).resolve()==ROOT/'src','Set explicit PYTHONPATH')
    s=git('rev-parse','HEAD').decode().strip();pins={g:{n:blob(s,n) for n in names} for g,names in paths(p,s).items()};require(unchanged(s,pins),'Initial source differs');d.mkdir()
    write(d/'attempt.json',dict(classification='ENGINEERING_ONLY',execution_commit=s,argv=sys.argv,python=sys.version,executable=sys.executable,executable_sha256=digest(Path(sys.executable).read_bytes()),pythonpath=os.environ['PYTHONPATH'],new_physical_runs=0,registered_research_trials=0,llm_calls=0,training_calls=0))
    r=dict(schema='aegisdc-action-value-receipt-v1',execution_commit=s,**pins,global_regression_gate='PENDING_ROOT_INTEGRATED_FULL',field_calibration='PENDING',new_physical_runs=0,registered_research_trials=0,llm_calls=0,training_calls=0)
    try:
        from action_value_engineering_checks import exercise
        data=exercise(ROOT,p);write(d/'check-results.json',data)
        args=['-B','-X','utf8','-m','aegis_dc.action_value','--frame',p['frame'],'--belief-model',p['belief_model'],'--catalog',p['risk_catalog'],'--value-model',p['value_model']]
        cli=subprocess.run([sys.executable,*args],cwd=ROOT,capture_output=True);write(d/'cli-stdout.raw',cli.stdout);write(d/'cli-stderr.raw',cli.stderr)
        require(cli.returncode==0 and not cli.stderr,'Value CLI failed');require(json.loads(cli.stdout)==data['default_result'],'CLI differs from public result');r.update(cli_argv=args,cli_exit_code=cli.returncode)
        for n,raw in render(d).items():write(d/n,raw)
        require(durable(d)==set(p['durable_outputs']),'Durable set differs');r['status']='PASS'
    except Exception as e:r.update(status='FAIL',error_type=type(e).__name__,error=str(e));raise
    finally:
        r['source_head_and_bytes_unchanged']=unchanged(s,pins)
        if not r['source_head_and_bytes_unchanged']:r['status']='FAIL'
        r['artifacts']={n:digest((d/n).read_bytes()) for n in sorted(durable(d))};write(d/p['terminal_receipt'],r)
    require(r['source_head_and_bytes_unchanged'],'Source changed during capture')
    return dict(status='PASS',execution_commit=s,artifacts=len(r['artifacts']),independent_cases=3,boundary_cases=5,maximum_absolute_error=data['maximum_absolute_error'])
def saved(d,p):
    data=read(d/'check-results.json');w=read(ROOT/p['independent_witness']);errors=[]
    require(len(data['independent_cases'])==len(w['cases'])==3,'Independent count differs')
    names={'defer':'defer','direct_intervention':'direct_intervention','inspect_then_intervene_if_positive':'inspect_then_act'}
    for row,literal in zip(data['independent_cases'],w['cases']):
        require(row['prior_fault']==literal['prior_fault'] and row['expected']==literal,'Witness identity differs');a={x['kind']:x for x in row['result']['question_values'][0]['alternatives']}
        for key,name in names.items():
            for q,expect in [('service_deficit_time_s','expected_deficit_time_s'),('person_s','expected_worker_person_s')]:
                e=abs(a[name]['expected'][q]['value']-float(Fraction(literal[expect][key])));errors.append(e);require(e<=p['absolute_numeric_tolerance'],'Independent value differs')
        require(abs(a['inspect_then_act']['branches'][0]['probability']-float(Fraction(literal['positive_probability'])))<=p['absolute_numeric_tolerance'],'Report probability differs')
    require(data['maximum_absolute_error']==max(errors),'Max error differs');require([r['case'] for r in data['boundary_cases']]==p['boundary_cases'],'Boundary set differs')
    for result in [r['result'] for r in data['independent_cases']]+[r['result'] for r in data['boundary_cases']]+[data['default_result']]:
        require(result['physical_actions']==[] and not result['execution_permission'] and len(result['risk']['domain_ids'])==8,'Scope differs')
        require(len(result['unmodeled_questions'])==6 and all(r['value'] is None for r in result['unmodeled_questions']),'Unknowns became numeric')
        for q in result['question_values']:
            for a in q['alternatives']:
                require(not a['execution_permission'] and not a['information_updates_physical_state'],'Physical permission changed')
                require(abs(sum(b['probability'] for b in a['branches'])-1)<=1e-14,'Probability mass differs')
    require((d/'cli-stderr.raw').read_bytes()==b'' and read(d/'cli-stdout.raw')==data['default_result'],'Saved CLI differs')
    for n,raw in render(d).items():require((d/n).read_bytes()==raw,'Saved figure differs')
    return dict(independent_cases=3,boundary_cases=5,maximum_absolute_error=max(errors),svg_figures=2)
def verify(d,p,delivery):
    require(git('rev-parse','HEAD').decode().strip()==delivery and not git('status','--porcelain'),'Use clean requested checkout');r=read(d/p['terminal_receipt']);s=r['execution_commit']
    require(r['status']=='PASS' and r['source_head_and_bytes_unchanged'] and r['cli_exit_code']==0,'Original failed');require(r['global_regression_gate']=='PENDING_ROOT_INTEGRATED_FULL','Original gate changed')
    require(durable(d)==set(p['durable_outputs'])|{p['terminal_receipt']} and set(r['artifacts'])==set(p['durable_outputs']),'Declared set differs');relative=d.relative_to(ROOT).as_posix()
    for n in durable(d):
        h=digest((d/n).read_bytes());require(h==blob(delivery,relative+'/'+n),'Git artifact differs:'+n)
        if n in r['artifacts']:require(h==r['artifacts'][n],'Original artifact differs:'+n)
    for g,names in paths(p,s).items():
        require(set(names)==set(r[g]),'Pinned roles differ')
        for n,h in r[g].items():require(h==blob(s,n)==blob(delivery,n)==digest((ROOT/n).read_bytes()),'Execution/delivery pin differs:'+n)
    return dict(schema='aegisdc-action-value-fresh-proof-v1',status='PASS',execution_commit=s,delivery_commit=delivery,durable_artifacts=6,terminal_receipts=1,pinned_paths={g:len(r[g]) for g in paths(p,s)},**saved(d,p),inference_rerun=False,physical_rerun=False,full_regression_rerun=False,runtime_caches_required=0,global_regression_gate='PENDING_ROOT_INTEGRATED_FULL',field_calibration='PENDING',registered_research_trials=0,llm_calls=0,training_calls=0)
if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('mode',choices=['capture','verify']);a.add_argument('--capture',type=Path,required=True);a.add_argument('--delivery');args=a.parse_args();p=read(ROOT/PROTOCOL);d=(ROOT/args.capture).resolve();require(d.parent==ROOT/PACKAGE,'Use unique ticket20 directory');print(json.dumps(capture(d,p) if args.mode=='capture' else verify(d,p,args.delivery),ensure_ascii=False,allow_nan=False))
