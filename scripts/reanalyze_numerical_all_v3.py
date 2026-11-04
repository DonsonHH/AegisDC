"""Versioned, read-only reanalysis of ALL 88+12 original trajectories."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import subprocess

from numerical_alignment_v3 import assess
from numerical_engineering_checks import read_archive,member_identities
from numerical_refinement_checks import compact,inspect_refinement_run,check_numeric_range_extension
from verify_reserve_delivery import file_sha,git_blob_sha,is_runtime_cache,safe_path

ROOT=Path(__file__).resolve().parents[1]


def configured(base,item):
    result=deepcopy(base)
    for row in result['parameters']:
        if row['id'] in item['overrides']:
            row.update(value=item['overrides'][row['id']],basis='synthetic_assumption',
                source_note='Frozen ticket 12 numerical engineering case: '+item['id'])
    return result


def compute(root):
    v1=root/'evidence/mainline/engineering/12-numerical/capture-04'
    v2=root/'evidence/mainline/engineering/12-numerical/refinement-01'
    book=json.loads((v1/'runbook-copy.json').read_text(encoding='utf-8'))
    extra=json.loads((v2/'protocol-copy.json').read_text(encoding='utf-8'))
    first=json.loads((v1/'runs-index.json').read_text(encoding='utf-8'))
    second=json.loads((v2/'runs-index.json').read_text(encoding='utf-8'))
    receipt=json.loads((v1/'receipt.json').read_text(encoding='utf-8'))
    if receipt['runtime_sources']!=json.loads((v2/'receipt.json').read_text(encoding='utf-8'))['runtime_sources']:
        raise ValueError('Original physical runtime fingerprints differ')
    base=json.loads((root/book['profile']).read_text(encoding='utf-8'))
    new_names={item['id'] for item in extra['cases']}
    inputs={};runs={};analyses={};seen_commits=set();points=0;count=0
    for item in book['cases']:
        name=item['id'];runs[name]={};analyses[name]={}
        for h in book['maximum_steps_s']+(extra['newly_run_steps_s'] if name in new_names else []):
            added=h in extra['newly_run_steps_s']
            record=second[name][str(h)] if added else first[name][str(h)]
            folder=v2 if added else v1
            path=safe_path(folder,record['archive'])
            if file_sha(path)!=record['archive_sha256'] or member_identities(path)!=record['original_members']:
                raise ValueError('An original artifact changed')
            manifest,scenario,trace,balances=read_archive(path)
            source=manifest['code_identity']['git_commit']
            if manifest['code_identity']['files']!=receipt['runtime_sources'] or manifest['code_identity']['implementation_has_changes']:
                raise ValueError('Actual physical source fingerprint differs')
            if source not in seen_commits:
                for relative,identity in receipt['runtime_sources'].items():
                    if git_blob_sha(root,source,relative)!=identity:raise ValueError('Original execution source differs from Git')
                seen_commits.add(source)
            expected=configured(base,item)
            if added:check_numeric_range_extension(expected,scenario)
            elif expected!=scenario:raise ValueError('Frozen original physical input differs')
            if manifest['inputs']['maximum_step_s']!=h or manifest['inputs']['duration_s']!=item['duration_s']:
                raise ValueError('Original numeric/time input differs')
            analysis=inspect_refinement_run(item,manifest,scenario,trace,balances)
            analyses[name][str(h)]=analysis
            relative=path.relative_to(root).as_posix();inputs[relative]=file_sha(path)
            runs[name][str(h)]=dict(original_path=relative,sha256=inputs[relative],original_members=record['original_members'],
                actual_runtime_commit=source,analysis=compact(analysis))
            points+=len(trace);count+=1
            del manifest,scenario,trace,balances
        print('read all original levels '+name,flush=True)
    results={}
    for item in book['cases']:
        name=item['id'];selected=dict(extra if name in new_names else book,cases=[item])
        row=assess(selected,{name:analyses[name]})['cases'][name]
        row.update(candidate_maximum_step_s=selected['proposed_qualified_maximum_step_s'],
            fine_reference_s=selected['fine_reference_s'],reference_refinement_s=selected['reference_refinement_s'])
        results[name]=row
    needed=[name for name,row in results.items() if not row['fine_reference_refinement']['within_predeclared_limits']]
    assessment=dict(schema='aegisdc-all-100-readonly-reanalysis-v3',cases=results,original_archives=count,
        state_points=points,all_eleven_declared_fixtures_qualified=all(row['qualified_for_declared_fixture'] for row in results.values()),
        cases_requiring_additional_reference_resolution=needed,
        candidate_failures=[name for name,row in results.items() if not row['proposed_step_gate']],
        runtime_sources=receipt['runtime_sources'],actual_runtime_commits=sorted(seen_commits),
        all_originals_read_without_result_selection=True,physics_rerun=False,full_suite_rerun=False,
        legacy_v1_and_v2_outputs_unmodified=True,research_trials=0,model_calls=0,training_calls=0)
    for folder in (v1,v2):
        for name in ('receipt.json','runs-index.json','runbook-copy.json' if folder==v1 else 'protocol-copy.json'):
            path=folder/name;inputs[path.relative_to(root).as_posix()]=file_sha(path)
    return runs,assessment,inputs


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--verify',type=Path)
    args=parser.parse_args();root=args.root.resolve()
    runs,assessment,inputs=compute(root)
    if args.verify:
        if runs!=json.loads((args.verify/'runs-index.json').read_text(encoding='utf-8')) or assessment!=json.loads((args.verify/'assessment.json').read_text(encoding='utf-8')):
            raise ValueError('All-original reanalysis does not reproduce')
        receipt=json.loads((args.verify/'receipt.json').read_text(encoding='utf-8'))
        if receipt['original_inputs']!=inputs:raise ValueError('Reanalysis input set differs')
        with args.output.open('x',encoding='utf-8',newline='\n') as stream:
            json.dump(dict(status='PASS',original_archives=assessment['original_archives'],state_points=assessment['state_points'],physics_rerun=False,full_suite_rerun=False),stream,indent=2);stream.write('\n')
        return
    execution=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    tools=['scripts/reanalyze_numerical_all_v3.py','scripts/numerical_alignment_v3.py','scripts/numerical_refinement_checks.py','scripts/numerical_engineering_checks.py','scripts/coupled_engineering_checks.py','scripts/verify_reserve_delivery.py']
    pinned={path:file_sha(root/path) for path in tools}
    for name,identity in {**pinned,**inputs}.items():
        if is_runtime_cache(name) or git_blob_sha(root,execution,name)!=identity:raise ValueError('Freeze analysis tool/original first: '+name)
    args.output.mkdir(parents=True,exist_ok=False)
    for filename,value in [('runs-index.json',runs),('assessment.json',assessment)]:
        with (args.output/filename).open('x',encoding='utf-8',newline='\n') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    receipt=dict(schema='aegisdc-readonly-all-originals-receipt-v3',analysis_execution_commit=execution,
        original_inputs=inputs,pinned_tools=pinned,physics_rerun=False,full_suite_rerun=False,
        declared_artifacts=['runs-index.json','assessment.json'],artifacts={name:file_sha(args.output/name) for name in ('runs-index.json','assessment.json')},
        runtime_cache_policy='__pycache__, .pyc and .pyo excluded by type before hashing',initial_delivery='PENDING_COMMIT_AND_FRESH_CHECKOUT',
        research_trials=0,model_calls=0,training_calls=0)
    with (args.output/'receipt.json').open('x',encoding='utf-8',newline='\n') as stream:json.dump(receipt,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(originals=assessment['original_archives'],necessary_reference_cases=assessment['cases_requiring_additional_reference_resolution'],candidate_failures=assessment['candidate_failures'],physics_rerun=False)))


if __name__=='__main__':main()
