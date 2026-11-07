"""Audit exact actual inputs first, then the separately declared public planner view."""
from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from inspection_delivery import read,require,digest,write,durable
from development_run_evidence import check_run as original_check
from ablation_planner import audit_document,planner_view,fingerprint
from registered_development import NATIVE

def check_ablation_run(document,run,trace,balances):
    actual=document['dispatch_program'];mask=document['ablation_mask'];planning=planner_view(actual,mask)
    require(run['inputs']['dispatch_program']==actual,'Native actual execution input differs from its frozen full declaration')
    marker=run['ablation_execution_audit']
    require(marker['mask']==mask and marker['actual_program_sha256']==fingerprint(actual)
        and marker['planner_program_sha256']==fingerprint(planning)
        and marker['actual_plant_sha256']==fingerprint(document['model']),
        'Actual/planning view identities differ')
    require(marker['adapter_source']=='scripts/ablation_planner.py'
        and marker['adapter_sha256']==digest((Path(__file__).parent/'ablation_planner.py').read_bytes()),
        'Adapter source identity differs')
    require(marker['actual_catalog_task_ids']==sorted(c['task']['id'] for c in actual['policy_program']['candidates'])
        and marker['actual_binding_task_ids']==sorted(b['task_id'] for b in actual['intervention_program']['bindings'])
        and marker['planner_candidate_ids']==sorted(c['id'] for c in planning['policy_program']['candidates'])
        and marker['planner_binding_task_ids']==sorted(b['task_id'] for b in planning['intervention_program']['bindings']),
        'Actual executor capability or masked planning availability differs')
    count=marker['schema_component_identity_validations']
    require(type(count) is int and (count>0 if mask=='without_dependency_context' else count==0),
        'Unexpected dependency shape-validation lifecycle')
    actual_tasks={c['task']['id']:c['task'] for c in actual['policy_program']['candidates']}
    for row in run['policy_public_decisions']:
        task=row['choice']['work_intention']
        if task is not None:require(task==actual_tasks[task['id']],'A mask changed an actual task definition')
        require(row['frame']['nominal_knowledge']==planning['nominal_knowledge'],'A removed static dependency reached a decision frame')
    # Native bytes remain untouched. Only this local evaluator copy binds the
    # existing public-choice checker to the planner declaration. Physical inputs
    # above were checked against the full actual declaration, without a waiver.
    projected=deepcopy(run);projected['inputs']['dispatch_program']=deepcopy(planning)
    audit=original_check(audit_document(document),projected,trace,balances)
    audit['ablation_view_verification']=dict(status='PASS_EXACT_ACTUAL_AND_PLANNER_VIEWS',
        mask=mask,actual_program_sha256=marker['actual_program_sha256'],
        planner_program_sha256=marker['planner_program_sha256'],
        scope='Planning-field evaluator projection only, after exact original actual input validation; native bytes unchanged.')
    return audit

def save_native(native,folder,program,result,source):
    from aegis_dc.plant import save_run
    run=save_run(result,native)
    require(set(durable(native))==set(NATIVE),'Native returned members differ from declaration')
    originals=folder/'originals.zip'
    with ZipFile(originals,'x',compression=ZIP_DEFLATED,compresslevel=4) as archive:
        members={}
        for name in NATIVE:
            raw=(native/name).read_bytes();members[name]=digest(raw);archive.writestr(name,raw)
    write(folder/'originals.json',dict(archive_sha256=digest(originals.read_bytes()),members=members))
    require(run['code_identity']['git_commit']==source and run['code_identity']['implementation_has_changes'] is False,
        'Physical runtime identity differs from registered source')
    require(read(native/'scenario.json')==program['model'],'Returned actual scenario differs')
    for name,item in run['artifacts'].items():require(members[name]==item['sha256'],'Native artifact manifest differs')
    audit=check_ablation_run(program,run,result['trace'],result['balances']);write(folder/'audit.json',audit)
    return len(result['policy_public_decisions'])
