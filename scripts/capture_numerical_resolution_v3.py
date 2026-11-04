"""Run only the registered .00125 s reference additions; no repeated full suite."""
import argparse,json,subprocess,sys,tempfile,traceback,zipfile
from pathlib import Path
from aegis_dc.plant import simulate_scenario,save_run
from aegis_dc.scenario import load_scenario
from reanalyze_numerical_all_v3 import configured
from numerical_alignment_v3 import assess
from numerical_engineering_checks import read_archive,member_identities
from numerical_refinement_checks import inspect_refinement_run,compact
from numerical_resolution_helpers import check_extension
from verify_reserve_delivery import file_sha,git_blob_sha,is_runtime_cache,safe_path

ROOT=Path(__file__).resolve().parents[1]
PROTOCOL='docs/mainline/12-numerical-resolution-v3.json'


def write(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to(ROOT):raise ValueError('Use a fresh worktree output')
    execution=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=ROOT,text=True).strip():raise ValueError('Freeze v3 tools/inputs before capture')
    book=json.loads((ROOT/PROTOCOL).read_text(encoding='utf-8'));v1=ROOT/'evidence/mainline/engineering/12-numerical/capture-04';v2=ROOT/'evidence/mainline/engineering/12-numerical/refinement-01'
    old=json.loads((v1/'runs-index.json').read_text(encoding='utf-8'));prior=json.loads((v2/'runs-index.json').read_text(encoding='utf-8'));common=json.loads((v1/'receipt.json').read_text(encoding='utf-8'))['runtime_sources']
    tools=['scripts/'+name for name in ('capture_numerical_resolution_v3.py','prepare_numerical_resolution_v3.py','verify_numerical_resolution_v3.py','numerical_resolution_helpers.py','reanalyze_numerical_all_v3.py','numerical_alignment_v3.py','numerical_refinement_checks.py','numerical_engineering_checks.py','coupled_engineering_checks.py','verify_reserve_delivery.py')]
    inputs=[PROTOCOL,book['profile'],'configs/materials/reference-r134a-saturation.json',book['prior_reanalysis']+'/assessment.json',book['prior_reanalysis']+'/receipt.json']
    for item in book['cases']:
        inputs += [(v1/old[item['id']]['0.01']['archive']).relative_to(ROOT).as_posix(),(v2/prior[item['id']]['0.0025']['archive']).relative_to(ROOT).as_posix()]
    pinned={name:file_sha(ROOT/name) for name in tools+inputs}
    for name,identity in {**pinned,**common}.items():
        if git_blob_sha(ROOT,execution,name)!=identity or (name in common and file_sha(ROOT/name)!=identity):raise ValueError('Frozen source/input mismatch: '+name)
    planned=['declaration.json','protocol-copy.json','engineering-attempts.jsonl','runs-index.json','assessment.json','capture-status.json']+[f"runs/{item['id']}/h-0.00125.zip" for item in book['cases']]
    output.mkdir(parents=True,exist_ok=False);(output/'runs').mkdir()
    write(output/'declaration.json',dict(declared_artifacts=planned,declared_tools=tools,declared_inputs=inputs,runtime_cache_policy='Exclude __pycache__/.pyc/.pyo by type BEFORE hashing',classification=book['classification'],full_regression_runs=0))
    write(output/'protocol-copy.json',book);index={};analyses={};stage=None;staging=ROOT/'.work/numerical-staging';staging.mkdir(parents=True,exist_ok=True)
    with (output/'engineering-attempts.jsonl').open('x',encoding='utf-8',newline='\n') as ledger:
        def record(row):ledger.write(json.dumps(dict(row,analysis_execution_commit=execution),allow_nan=False)+'\n');ledger.flush()
        try:
            for item in book['cases']:
                name=item['id'];index[name]={};analyses[name]={}
                for h,folder,original in [(.01,v1,old[name]['0.01']),(.0025,v2,prior[name]['0.0025'])]:
                    path=safe_path(folder,original['archive']);m,s,t,b=read_archive(path);analysis=inspect_refinement_run(item,m,s,t,b)
                    analyses[name][str(h)]=analysis;index[name][str(h)]=dict(original_path=path.relative_to(ROOT).as_posix(),archive_sha256=file_sha(path),original_members=member_identities(path),runtime_execution_commit=m['code_identity']['git_commit'],analysis=compact(analysis),new_physics=False)
                stage=name+'/0.00125';base=configured(load_scenario(ROOT/book['profile']),item);scenario=json.loads(json.dumps(base));numeric=next(row for row in scenario['parameters'] if row['id']=='step_time');numeric.update(valid_range=[.00125,numeric['valid_range'][1]],basis='synthetic_assumption',source_note='Explicit engineering resolution protocol v3; numeric range only, all canonical physical values unchanged.')
                check_extension(base,scenario);result=simulate_scenario(scenario,duration_s=item['duration_s'],step_s=.00125,boundary_events=item['events'],work_requests=item['work_requests'])
                if result['code_identity']['git_commit']!=execution or result['code_identity']['files']!=common or result['code_identity']['implementation_has_changes']:raise ValueError('Actual physical runtime source changed')
                folder=output/'runs'/name;folder.mkdir();path=folder/'h-0.00125.zip'
                with tempfile.TemporaryDirectory(dir=staging,prefix='resolution-') as temporary:
                    target=Path(temporary).resolve()
                    if not target.is_relative_to(staging.resolve()):raise ValueError('Temporary cleanup escaped staging')
                    save_run(result,target/'run')
                    with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
                        for saved in sorted((target/'run').iterdir()):archive.writestr(saved.name,saved.read_bytes())
                del result
                m,s,t,b=read_archive(path);check_extension(base,s);analysis=inspect_refinement_run(item,m,s,t,b)
                analyses[name]['0.00125']=analysis;index[name]['0.00125']=dict(original_path=path.relative_to(ROOT).as_posix(),archive_sha256=file_sha(path),original_members=member_identities(path),runtime_execution_commit=m['code_identity']['git_commit'],analysis=compact(analysis),new_physics=True)
                record(dict(case=name,maximum_step_s=.00125,outcome='ENGINEERING_COMPLETED',archive_sha256=file_sha(path),runtime_execution_commit=execution));print('captured v3 '+stage,flush=True)
            write(output/'runs-index.json',index);checked=assess(book,analyses);write(output/'assessment.json',checked);write(output/'capture-status.json',dict(status='PASS',numerical_gate=checked['all_declared_fixtures_qualified'],new_physical_runs=len(book['cases']),full_regression_runs=0))
        except Exception as error:
            record(dict(stage=stage,outcome='UNEXPECTED_FAILURE',error=repr(error)));write(output/'capture-status.json',dict(status='FAIL',stage=stage,error=repr(error),traceback=traceback.format_exc()));raise
    actual={path.relative_to(output).as_posix() for path in output.rglob('*') if path.is_file() and not is_runtime_cache(path)}
    if actual!=set(planned):raise ValueError('V3 durable set differs from declaration')
    write(output/'receipt.json',dict(schema='aegisdc-resolution-capture-receipt-v3',engineering_capture='PASS',delivery_gate='PENDING_COMMIT_AND_FRESH_CHECKOUT',execution_commit=execution,runtime_sources=common,pinned_tools={name:pinned[name] for name in tools},execution_inputs={name:pinned[name] for name in inputs},artifacts={name:file_sha(output/name) for name in planned},new_physical_runs=len(book['cases']),full_regression_runs=0,numerical_gate=checked['all_declared_fixtures_qualified'],runtime_caches_required=0,python_executable=sys.executable,python_executable_sha256=file_sha(Path(sys.executable)),python_version=sys.version,research_trials=0,model_calls=0,training_calls=0))
    print(json.dumps(dict(capture='PASS',numerical_gate=checked['all_declared_fixtures_qualified'],new_physical_runs=len(book['cases']))))


if __name__=='__main__':main()
