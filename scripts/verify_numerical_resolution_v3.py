"""Verify the exact v3 delivery and independent saved-byte analysis only."""
import argparse,json,subprocess
from pathlib import Path
from reanalyze_numerical_all_v3 import configured
from numerical_alignment_v3 import assess
from numerical_engineering_checks import read_archive,member_identities
from numerical_refinement_checks import inspect_refinement_run,compact,check_numeric_range_extension
from numerical_resolution_helpers import check_extension
from verify_reserve_delivery import file_sha,git_blob_sha,is_runtime_cache,safe_path


def verify(root,folder,delivery_commit):
    root=root.resolve();folder=(folder if folder.is_absolute() else root/folder).resolve();relative=folder.relative_to(root).as_posix()
    delivery=subprocess.check_output(['git','rev-parse',delivery_commit+'^{commit}'],cwd=root,text=True).strip();receipt=json.loads((folder/'receipt.json').read_text(encoding='utf-8'));declaration=json.loads((folder/'declaration.json').read_text(encoding='utf-8'))
    if receipt['delivery_gate']!='PENDING_COMMIT_AND_FRESH_CHECKOUT' or receipt['full_regression_runs']!=0:raise ValueError('Initial receipt/source policy changed')
    actual={path.relative_to(folder).as_posix() for path in folder.rglob('*') if path.is_file() and not is_runtime_cache(path)}
    if actual!=set(declaration['declared_artifacts'])|{'receipt.json'} or set(receipt['artifacts'])!=set(declaration['declared_artifacts']):raise ValueError('V3 durable declaration differs')
    for name in actual:
        identity=file_sha(folder/name)
        if git_blob_sha(root,delivery,relative+'/'+name)!=identity or (name!='receipt.json' and receipt['artifacts'][name]!=identity):raise ValueError('V3 raw delivery artifact differs')
    execution=receipt['execution_commit']
    for group,declared in [('pinned_tools','declared_tools'),('execution_inputs','declared_inputs')]:
        if set(receipt[group])!=set(declaration[declared]):raise ValueError('V3 provenance declaration differs')
    for group in ('pinned_tools','execution_inputs','runtime_sources'):
        for name,identity in receipt[group].items():
            if file_sha(safe_path(root,name))!=identity or git_blob_sha(root,execution,name)!=identity or git_blob_sha(root,delivery,name)!=identity:raise ValueError('V3 execution/delivery provenance differs: '+name)
    book=json.loads((folder/'protocol-copy.json').read_text(encoding='utf-8'))
    if book!=json.loads((root/'docs/mainline/12-numerical-resolution-v3.json').read_text(encoding='utf-8')):raise ValueError('V3 protocol copy differs')
    index=json.loads((folder/'runs-index.json').read_text(encoding='utf-8'));base=json.loads((root/book['profile']).read_text(encoding='utf-8'));analyses={};new_count=0;points=0;commits=set()
    for item in book['cases']:
        name=item['id'];analyses[name]={}
        if set(index[name])!={str(h) for h in book['maximum_steps_s']}:raise ValueError('V3 levels differ')
        for h,record in index[name].items():
            path=safe_path(root,record['original_path'])
            if file_sha(path)!=record['archive_sha256'] or member_identities(path)!=record['original_members']:raise ValueError('V3 original member/hash differs')
            m,s,t,b=read_archive(path);source=m['code_identity']['git_commit']
            if source!=record['runtime_execution_commit'] or m['code_identity']['files']!=receipt['runtime_sources'] or m['code_identity']['implementation_has_changes']:raise ValueError('V3 actual runtime identity differs')
            if source not in commits:
                for p,identity in receipt['runtime_sources'].items():
                    if git_blob_sha(root,source,p)!=identity:raise ValueError('Historical actual runtime source differs')
                commits.add(source)
            expected=configured(base,item)
            if record['new_physics']:
                if source!=execution or float(h)!=.00125:raise ValueError('Unexpected new v3 execution')
                check_extension(expected,s);new_count+=1;points+=len(t)
            elif float(h)==.0025:check_numeric_range_extension(expected,s)
            elif s!=expected:raise ValueError('Inherited physical inputs differ')
            if m['inputs']['maximum_step_s']!=float(h):raise ValueError('V3 maximum-step metadata differs')
            analysis=inspect_refinement_run(item,m,s,t,b)
            if compact(analysis)!=record['analysis']:raise ValueError('V3 saved analysis differs')
            analyses[name][h]=analysis
    result=assess(book,analyses)
    if result!=json.loads((folder/'assessment.json').read_text(encoding='utf-8')):raise ValueError('V3 final gates do not reproduce')
    return dict(status='PASS',execution_commit=execution,delivery_commit=delivery,new_original_archives=new_count,
        inherited_original_archives=len(book['cases'])*2,new_state_points=points,numerical_gate=result['all_declared_fixtures_qualified'],
        declared_artifacts=len(receipt['artifacts']),initial_pending_receipt_preserved=True,runtime_caches_required=0,
        physics_rerun=False,full_suite_rerun=False,research_trials=0,model_calls=0,training_calls=0)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);parser.add_argument('--directory',type=Path,required=True);parser.add_argument('--delivery-commit',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();result=verify(args.root,args.directory,args.delivery_commit)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result))
