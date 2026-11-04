"""Fresh-checkout final-entry proof; no simulation, rendering or full rerun."""
import argparse,json,subprocess
from pathlib import Path
from summarize_numerical_qualification import summary
from verify_reserve_delivery import file_sha,git_blob_sha,is_runtime_cache,safe_path


def verify(root,folder,delivery_commit):
    root=root.resolve();folder=(folder if folder.is_absolute() else root/folder).resolve();relative=folder.relative_to(root).as_posix()
    delivery=subprocess.check_output(['git','rev-parse',delivery_commit+'^{commit}'],cwd=root,text=True).strip();receipt=json.loads((folder/'receipt.json').read_text(encoding='utf-8'));declaration=json.loads((folder/'declaration.json').read_text(encoding='utf-8'))
    declared=set(declaration['declared_artifacts']);actual={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file() and not is_runtime_cache(p)}
    if actual!=declared|{'receipt.json'} or declared!=set(receipt['artifacts']) or receipt['delivery_gate']!='PENDING_COMMIT_AND_FRESH_CHECKOUT':raise ValueError('Final-entry durable declaration/initial receipt differs')
    for name in actual:
        identity=file_sha(folder/name)
        if git_blob_sha(root,delivery,relative+'/'+name)!=identity or (name!='receipt.json' and receipt['artifacts'][name]!=identity):raise ValueError('Final-entry original differs from delivery Git')
    execution=receipt['authoring_commit']
    for group,declared_name in [('pinned_tools','declared_tools'),('execution_inputs','declared_inputs')]:
        if set(receipt[group])!=set(declaration[declared_name]):raise ValueError('Final-entry provenance declaration differs')
        for name,identity in receipt[group].items():
            if file_sha(safe_path(root,name))!=identity or git_blob_sha(root,execution,name)!=identity or git_blob_sha(root,delivery,name)!=identity:raise ValueError('Final-entry input/tool execution identity differs')
    expected=json.loads((folder/'summary.json').read_text(encoding='utf-8'));computed=summary(root);computed['authoring_commit']=execution
    if computed!=expected or expected['authoring_commit']!=execution:raise ValueError('All-eleven independent readback does not reproduce')
    if expected['all_original_archives']!=102 or expected['full_case_count']!=11:raise ValueError('Full-facility case/original coverage changed')
    for name,identity in receipt['runtime_sources'].items():
        if git_blob_sha(root,execution,name)!=identity:raise ValueError('Recorded numerical implementation differs from execution Git')
    figure=json.loads((folder/'figure-receipt.json').read_text(encoding='utf-8'))
    if figure['input_sha256']!=file_sha(folder/'summary.json') or figure['author_sha256']!=file_sha(root/'scripts/plot_numerical_qualification_final.py'):raise ValueError('Final figure source/input differs')
    for name,identity in figure['outputs'].items():
        if file_sha(folder/name)!=identity:raise ValueError('Final figure bytes differ')
    return dict(status='PASS',analysis_execution_commit=execution,delivery_commit=delivery,cases=11,original_archives=102,
        all_eleven_declared_fixtures_qualified=expected['all_eleven_declared_fixtures_qualified'],
        original_v1_NO_GO_preserved=not expected['original_v1_numeric_gate_preserved'],
        original_v2_NO_GO_preserved=not expected['additive_six_case_gate'],
        actual_runtime_execution_commits=expected['actual_runtime_execution_commits'],
        durable_artifacts=len(declared),initial_pending_receipt_preserved=True,runtime_caches_required=0,
        physics_rerun=False,full_suite_rerun=False,research_trials=0,model_calls=0,training_calls=0)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);parser.add_argument('--directory',type=Path,required=True);parser.add_argument('--delivery-commit',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();result=verify(args.root,args.directory,args.delivery_commit)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result))
