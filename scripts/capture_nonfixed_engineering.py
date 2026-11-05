"""Freeze ticket17 producer outputs and run exactly one author full regression."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from aegis_dc.nonfixed_evidence import NonfixedSession, SavedRunSignals
from acceptance import verify as full_check
from build_nonfixed_fixture import build, encoded, PROFILE, PLAN, RUNBOOK, PRIVATE_RUN, PAIRED_RUNS
from nonfixed_engineering_checks import check_package
from plot_nonfixed_evidence import render


def file_sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def git_blob_sha(root, revision, name):
    result=subprocess.run(['git','show',revision+':'+name],cwd=root,capture_output=True)
    if result.returncode:
        raise ValueError('Missing committed blob: '+name)
    return sha256(result.stdout).hexdigest()


def write(path,value):
    with path.open('xb') as stream:
        stream.write(encoded(value))


def is_cache(path):
    return '__pycache__' in {part.lower() for part in Path(path).parts} or Path(path).suffix.lower() in {'.pyc','.pyo'}


def declared_pins(root):
    sources=[p.relative_to(root).as_posix() for p in sorted((root/'src').rglob('*.py'))]
    tools=[p.relative_to(root).as_posix() for folder in ['scripts','tests']
           for p in sorted((root/folder).rglob('*')) if p.is_file() and not is_cache(p)]
    inputs=[PROFILE,PLAN,RUNBOOK,'pyproject.toml','.gitattributes','AGENTS.md','GLOSSARY.md',
        'docs/adr/0002-sparse-evidence-not-sensor-free.md','docs/adr/0003-complete-facility-mainline.md',
        '.scratch/full-facility-mainline/spec.md','docs/mainline/information-boundary.md',
        'docs/mainline/14-evidence-contract.md','docs/mainline/17-nonfixed-evidence.md',
        'configs/full-facility-evidence-v1.json','configs/full-facility-mainline-reserve-v6.json',
        'configs/materials/reference-r134a-saturation.json','evidence/mainline/engineering/17-nonfixed/.gitattributes',
        'evidence/mainline/engineering/17-nonfixed/README.md']
    inputs.extend(p.relative_to(root).as_posix() for p in sorted((root/'evidence/mainline/engineering/17-nonfixed/development').rglob('*'))
                  if p.is_file() and not is_cache(p))
    for directory in [PRIVATE_RUN,*PAIRED_RUNS]:
        inputs.extend(directory+'/'+name for name in ['run.json','scenario.json','private-state.jsonl','balances.jsonl'])
    return dict(runtime_sources=sorted(sources),authoring_verification_tools=sorted(tools),frozen_inputs=sorted(inputs))


def capture(directory):
    directory=directory.resolve();directory.relative_to(ROOT)
    execution=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip():
        raise ValueError('Commit runtime, tests, authoring/verification tools and declared inputs before capture')
    pin_paths=declared_pins(ROOT)
    pins={group:{name:file_sha(ROOT/name) for name in names} for group,names in pin_paths.items()}
    for entries in pins.values():
        for name,expected in entries.items():
            if git_blob_sha(ROOT,execution,name)!=expected:
                raise ValueError('Executed input differs from frozen Git blob: '+name)
    book=json.loads((ROOT/RUNBOOK).read_text(encoding='utf-8'))
    declared=['declaration.json','profile-copy.json','private-plan-copy.json','runbook-copy.json',
        'profile-rebuilt.json','private-plan-rebuilt.json','runbook-rebuilt.json','snapshots.json','public-models.json',
        'private-audit.json','private-source-witness.json','private-noninterference.json','commands.json',
        'independent-checks.json','figure-checks.json','capture-failure.txt',
        'negative-inputs/no-fixed-profile.json','negative-inputs/no-fixed-plan.json','negative-inputs/ungated-plan.json',
        'cli/overwrite-preservation.json','figures/observation-timing.svg','figures/source-authority.svg',
        'full-check/summary.json','full-check/tests.log','full-check/evidence.json']
    for case in book['CLI']:
        declared.extend('cli/'+case['id']+'.'+channel+('.json' if channel=='stdout' and case['expected_exit']==0 else '.raw')
                        for channel in ['stdout','stderr'])
        if case['expected_exit']==0:
            declared.extend('cli/'+case['id']+'/'+name for name in ['declaration.json','public-snapshot.json','public-models.json','private-audit.json','receipt.json'])
        elif case['id']=='ungated-handheld':
            declared.extend('cli/'+case['id']+'/'+name for name in ['declaration.json','receipt.json'])
    directory.mkdir(parents=True,exist_ok=False)
    write(directory/'declaration.json',dict(schema='aegisdc-nonfixed-delivery-declaration-v1',
        classification='ENGINEERING_NOT_RESEARCH',declared_artifacts=sorted(declared),terminal_receipt='receipt.json',
        runtime_caches='NOT_DELIVERABLE',pinned_paths=pin_paths,
        public_files=['snapshots.json','public-models.json'],
        private_audit_files=['private-plan-copy.json','private-audit.json','private-source-witness.json','private-noninterference.json']))
    receipt=dict(schema='aegisdc-nonfixed-engineering-receipt-v1',engineering_capture='FAIL',execution_commit=execution,
        execution_started_utc=datetime.now(timezone.utc).isoformat(),delivery_gate='PENDING_COMMIT_AND_FRESH_CHECKOUT',**pins,
        python=dict(version=sys.version,implementation=sys.implementation.name,executable_sha256=file_sha(sys.executable)),
        numpy_version=importlib.metadata.version('numpy'),registered_research_trials=0,model_calls=0,training_calls=0,
        new_physics_execution=False,professional_execution_connected=False,physical_source=book['saved_run_interpretation'],
        field_calibration='PENDING',research_gain_claim='NOT_ESTABLISHED',full_regression_executions=0)
    failure=''
    try:
        for source,copy in [(PROFILE,'profile'),(PLAN,'private-plan'),(RUNBOOK,'runbook')]:
            (directory/(copy+'-copy.json')).write_bytes((ROOT/source).read_bytes())
            rebuilt=encoded(build()[source]);(directory/(copy+'-rebuilt.json')).write_bytes(rebuilt)
            if rebuilt!=(ROOT/source).read_bytes():
                raise ValueError('Authoring tool does not rebuild exact frozen bytes: '+source)
        profile=json.loads((directory/'profile-copy.json').read_text(encoding='utf-8'))
        plan=json.loads((directory/'private-plan-copy.json').read_text(encoding='utf-8'))
        session=NonfixedSession(profile,plan,private_signals=SavedRunSignals(ROOT/PRIVATE_RUN))
        snapshots={case['id']:session.snapshot(case['as_of_s']) for case in book['snapshots']}
        write(directory/'snapshots.json',snapshots);write(directory/'public-models.json',session.public_models())
        write(directory/'private-audit.json',session.private_audit())
        private_manifest=json.loads((ROOT/PRIVATE_RUN/'run.json').read_text(encoding='utf-8'))
        signals=SavedRunSignals(ROOT/PRIVATE_RUN)
        samples=[dict(time_s=time,temperature_K=signals.sample_at(time,signal_id='immersion.coolant_temperature',
            target_id='immersion',facility_id=profile['registry']['facility_id'])['value']) for time in [65.5,97.5,98]]
        write(directory/'private-source-witness.json',dict(classification='PRIVATE_ENGINEERING_AUDIT_NOT_DISPATCH',
            original_directory=PRIVATE_RUN,original_run_sha256=file_sha(ROOT/PRIVATE_RUN/'run.json'),
            physical_code_identity=private_manifest['code_identity'],
            historical_maximum_step_s=private_manifest['inputs']['maximum_step_s'],
            historical_duration_s=private_manifest['inputs']['duration_s'],new_physics_execution=False,
            exact_point_sampling='EXACT_SAVED_POINT_AT_EFFECTIVE_COMPLETION',actual_samples=samples))
        pair_plan=deepcopy(plan)
        pair_plan['completion_requests']=pair_plan['completion_requests'][:1]
        token=pair_plan['completion_requests'][0]['completion']
        token.update(planned_started_at_s=120,planned_completed_at_s=121,started_at_s=120,completed_at_s=121,valid_until_s=130)
        paired=[NonfixedSession(profile,pair_plan,private_signals=SavedRunSignals(ROOT/path)) for path in PAIRED_RUNS]
        before=[item.snapshot(121) for item in paired];after=[item.snapshot(121.5) for item in paired]
        pair_audits=[item.private_audit() for item in paired]
        write(directory/'private-noninterference.json',dict(classification='PRIVATE_ENGINEERING_AUDIT_NOT_DISPATCH',
            paired_original_directories=PAIRED_RUNS,before=before,after=after,private_audits=pair_audits,
            same_public_before_and_after_authorized_observation=before[0]==before[1] and after[0]==after[1],
            scope='Different hidden access states, equal authorized measured signal. No dispatch feasibility or actual executor21/22.'))
        (directory/'negative-inputs').mkdir();(directory/'cli').mkdir()
        no_fixed=deepcopy(profile);no_fixed['registry']['sources']=[s for s in no_fixed['registry']['sources'] if s['kind'] not in {'fixed_sensor','control_record'}]
        no_fixed_plan=deepcopy(plan);no_fixed_plan['external_records']=[]
        write(directory/'negative-inputs/no-fixed-profile.json',no_fixed);write(directory/'negative-inputs/no-fixed-plan.json',no_fixed_plan)
        ungated=deepcopy(plan);untrusted=deepcopy(plan['external_records'][0])
        untrusted.update(id='ungated-handheld',source_id='handheld-thermometer',observed_at_s=0,arrived_at_s=0,value=300)
        ungated['external_records'].append(untrusted);write(directory/'negative-inputs/ungated-plan.json',ungated)
        commands=[]
        def cli(identifier,profile_path,plan_path,time,output):
            command=[sys.executable,'-B','-X','utf8','-m','aegis_dc.nonfixed_evidence','--profile',str(profile_path),
                '--plan',str(plan_path),'--private-run',str(ROOT/PRIVATE_RUN),'--as-of',str(time),'--output',str(output)]
            result=subprocess.run(command,cwd=ROOT,env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),capture_output=True)
            expected=next(row['expected_exit'] for row in book['CLI'] if row['id']==identifier)
            (directory/('cli/'+identifier+'.stdout'+('.json' if expected==0 else '.raw'))).write_bytes(result.stdout)
            (directory/('cli/'+identifier+'.stderr.raw')).write_bytes(result.stderr)
            commands.append(dict(id=identifier,argv=command,returncode=result.returncode))
        cli('arrived',ROOT/PROFILE,ROOT/PLAN,98,directory/'cli/arrived')
        cli('before-arrival',ROOT/PROFILE,ROOT/PLAN,97.99999999999999,directory/'cli/before-arrival')
        cli('no-fixed',directory/'negative-inputs/no-fixed-profile.json',directory/'negative-inputs/no-fixed-plan.json',98,directory/'cli/no-fixed')
        cli('ungated-handheld',ROOT/PROFILE,directory/'negative-inputs/ungated-plan.json',98,directory/'cli/ungated-handheld')
        before_files={p.relative_to(directory/'cli/arrived').as_posix():file_sha(p) for p in (directory/'cli/arrived').rglob('*') if p.is_file()}
        cli('overwrite',ROOT/PROFILE,ROOT/PLAN,98,directory/'cli/arrived')
        after_files={p.relative_to(directory/'cli/arrived').as_posix():file_sha(p) for p in (directory/'cli/arrived').rglob('*') if p.is_file()}
        write(directory/'cli/overwrite-preservation.json',dict(unchanged=before_files==after_files,before=before_files,after=after_files))
        write(directory/'commands.json',commands)
        render(directory,directory/'figures')
        figures={}
        for path in sorted((directory/'figures').glob('*.svg')):
            element=ET.fromstring(path.read_bytes())
            if element.tag!='{http://www.w3.org/2000/svg}svg':
                raise ValueError('Figure is not SVG')
            figures[path.name]=dict(sha256=file_sha(path),width=element.attrib['width'],height=element.attrib['height'],elements=len(list(element.iter())))
        write(directory/'figure-checks.json',dict(status='PASS',classification='DATA_DERIVED_ENGINEERING_DIAGRAMS',
            author='scripts/plot_nonfixed_evidence.py',figures=figures,visual_QA='SEPARATE_RENDER_REVIEW'))
        checks=check_package(directory);write(directory/'independent-checks.json',checks)
        receipt['full_regression_executions']=1
        regression=full_check(ROOT,directory/'full-check')
        receipt.update(independent_checks=checks,full_tests=regression['tests'],verified_historical_originals=regression['verified_original_files'])
        if regression['overall']!='PASS':
            raise ValueError('Author full regression failed; retain original log')
        if execution!=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip():
            raise ValueError('HEAD changed during capture')
        if any(file_sha(ROOT/name)!=expected for group in pins.values() for name,expected in group.items()):
            raise ValueError('Pinned source/tool/input changed during capture')
        receipt['engineering_capture']='PASS'
    except Exception as error:
        failure=traceback.format_exc();receipt['failure']=dict(type=type(error).__name__,message=str(error))
    finally:
        (directory/'capture-failure.txt').write_text(failure,encoding='utf-8',newline='\n')
        actual={p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file() and not is_cache(p)}
        receipt['missing_declared_artifacts']=sorted(set(declared)-actual)
        receipt['unexpected_durable_artifacts']=sorted(actual-set(declared))
        receipt['artifacts']={name:file_sha(directory/name) for name in sorted(actual)}
        receipt['runtime_caches_required']=0;receipt['execution_ended_utc']=datetime.now(timezone.utc).isoformat()
        if receipt['missing_declared_artifacts'] or receipt['unexpected_durable_artifacts']:
            receipt['engineering_capture']='FAIL'
        write(directory/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=capture(args.output)
    print(json.dumps({key:result[key] for key in ['engineering_capture','execution_commit','delivery_gate','full_regression_executions']}))
    if 'failure' in result:print(json.dumps(result['failure']),file=sys.stderr)
    raise SystemExit(0 if result['engineering_capture']=='PASS' else 1)
