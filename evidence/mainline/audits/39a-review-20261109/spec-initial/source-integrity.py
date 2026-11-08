"""Text/Git integrity only. Does not import project code or calculate study metrics."""
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import re,subprocess

ROOT=Path('C:/Users/Donson/Documents/ChatGPT/Renly')
OUT=Path(__file__).resolve().parent
SOURCE='f73c57f8806dcc6e23d510e83391b0f46677b6cc'
BASE='8e32a8075fb86de0818f8149d4e47cdae3170ad9'
git=lambda *args:subprocess.check_output(['git',*args],cwd=ROOT)
sha=lambda raw:hashlib.sha256(raw).hexdigest()

def save(name,value):
    with (OUT/name).open('x',encoding='utf-8',newline='\n') as stream:stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

reference=git('rev-parse','2f3fb67f').decode().strip()
unchanged=git('diff','--name-only',reference,SOURCE,'--','src/aegis_dc','configs','scripts').decode()
assert not unchanged.strip(),'Scientific runtime/config changed after user scientific review reference'
matrix=(OUT/'coverage-01-38.md').read_text(encoding='utf-8')
rows=re.findall(r'^\|(\d\d) ',matrix,flags=re.M)
assert rows==['01','02','03','04','05','06','07','08','09','10','11','12','13','14','15','16','17','18','19','20','21','22','23','24','25','26','27','28','29','30','31','32','33','34','35','36','37','38']
paths=set()
for token in re.findall(r'`([^`]+)`',matrix):
    path=token.split(':',1)[0]
    if path.startswith(('src/','configs/','scripts/','docs/','evidence/','paper/','.scratch/')):
        paths.add(path)
objects={}
for path in sorted(paths):
    objects[path]=git('rev-parse',SOURCE+':'+path).decode().strip()
selected=[
    'docs/meetings/2026-11-03-research-reset.md','docs/MAINLINE.md','.scratch/full-facility-mainline/spec.md',
    'docs/reviews/20261109-user-review/response.md','docs/mainline/audits/20261108-pre36/ticket-matrix.md',
    '.scratch/full-facility-mainline/issues/39a-integrated-scope-review.md',
    '.scratch/full-facility-mainline/issues/39b-multisystem-questions-and-tasks.md',
    '.scratch/full-facility-mainline/issues/39c-business-endpoints-and-closure.md',
    '.scratch/full-facility-mainline/issues/39d-timescales-parameter-and-numeric-scope.md',
    'src/aegis_dc/risk_scenarios.py','src/aegis_dc/action_value.py','src/aegis_dc/dispatch_policy.py',
    'src/aegis_dc/lookahead_policy.py','scripts/prepare_comparison_worlds.py',
    'configs/full-facility-risk-scenarios-v1.json','configs/full-facility-action-value-v1.json',
    'configs/full-facility-comparison-development-v1.json','docs/mainline/20-action-value-contract.md',
    'docs/mainline/29-public-evidence-scope.md','evidence/mainline/research/34-paired-analysis/README.md',
    'docs/mainline/evidence/38-root.json','README.md','docs/NEXT.md']
hashes={path:sha(git('show',SOURCE+':'+path)) for path in selected}
navigation=ROOT/'.work/user-review-20261109/commit-list.txt'
save('source-integrity.json',dict(source=SOURCE,feature_base=BASE,scientific_reference=reference,
    requested_diff_command='git diff 8e32a807...f73c57f8 -- src/aegis_dc configs docs .scratch/full-facility-mainline README.md',
    method='Pinned targeted text/Git reads plus reused01–35 substantive audit and accepted36–38 evidence; no full source export or all-history data diff.',
    matrix_ticket_ids=rows,referenced_git_objects=objects,selected_text_sha256=hashes,
    navigation=dict(path='.work/user-review-20261109/commit-list.txt',sha256=sha(navigation.read_bytes()),use='Commit navigation only; not expanded into data/code export.'),
    runtime_config_diff_from_scientific_reference=unchanged,
    local_research_metric_recomputation=False,raw_180_samples_reaudited=False,
    project_calls=0,tests=0,model_calls=0,physical_calls=0,metric_recomputations=0,
    browser_calls=0,dependency_installs=0,full_source_exports=0,clones=0,new_worktrees=0))
save('findings.json',dict(source=SOURCE,
    empirical_or_implementation_regression_newly_established=False,
    classification='Existing finite accepted conclusions preserved; business/formal coverage partial. Known coverage gaps are not recast as old implementation bugs.',
    findings=[
      dict(id='39A-SPEC-DOC-01',severity='P2',path='README.md',line=56,
           finding='The v11 historical online-snapshot label points to the now-current180-run report route, mixing historical navigation with the new task definition.',
           correction='Point to the preserved v11 historicalHTML download or immutable oldGit source; keep latest report separate.',
           status_at_source='OPEN',root_reported_fix='Await fixed revision before closing.'),
      dict(id='39A-SPEC-DOC-02',severity='P3',path='README.md',lines=[65,70,71,80,90,94],
           finding='Old currentM2 wording and unqualified executable CLI examples are not explicitly separated from the new remote/Slurm-only, local-read-only research policy.',
           correction='Label historical entry scope and remote execution; use current39a→39b/c→39d→39 priority. Do not execute any example locally.',
           status_at_source='OPEN',root_reported_fix='Await fixed revision before closing.')],
    acceptance_limit='This packet supplies38-ticket andR1–R7 notes for the final two tables. It does not accept unwritten final tables, the pending remote saved-only readout, or39b–39d implementation.'))
save('receipt.json',dict(status='CROSSSTAGE_SPEC_REVIEW_COMPLETED_WITH_DOC_FINDINGS',source=SOURCE,
    matrix='coverage-01-38.md',meeting_notes='meeting-coverage-notes.md',
    substantive_conclusion='Finite1–38 acceptances supported within scope; formal multisystem risk/task/business/time coverage remains partial and needs user-approved39b–39d.',
    eligible38_preserved=True,old180_primary_unchanged=True,
    new_concentration_and_timescale_numbers='Not computed locally; rootSlurm saved-readout required where new arithmetic is needed.',
    final39a_tables_accepted=False,project_calls=0,tests=0,model_calls=0,physical_calls=0,
    metric_recomputations=0,browser_calls=0,installs=0,full_source_exports=0,clones=0,new_worktrees=0))
print(json.dumps(dict(status='TEXT_AND_INTEGRITY_REVIEW_SAVED',source=SOURCE,
    matrix='coverage-01-38.md',scientific_runtime_unchanged=True,local_metric_recomputation=False,project_calls=0)))
