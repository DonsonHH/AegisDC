"""Bind the final research document to the accepted science and the exact launch source."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PACK='docs/mainline/v6-native-research-launch-v1'
ENG='docs/mainline/v6-native-comparison-qualification-v1'
BASE='984071352142239201e3b69a449207ec35cd7cfa'
FREEZE='4daac1bcd467dc1ac7cb785946025f76a8da888e'

def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def blob(commit,path):return git('cat-file','blob',commit+':'+path)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(obj):return sha(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
def main():
    code=git('rev-parse',sys.argv[1]).decode().strip()
    prior_raw=blob(BASE,ENG+'/research-manifest.json')
    prior=json.loads(prior_raw)
    source=['scripts/v6_research_launch.py','scripts/v6_research/__init__.py','scripts/v6_research/binding.py',
        'scripts/v6_research/control.py','scripts/v6_research/native.py','scripts/v6_research/slurm.py',PACK+'/study.sbatch']
    pins={p:sha(blob(code,p)) for p in source}
    acceptance=ENG+'/acceptance-20261120.json'
    fs=json.loads(blob(FREEZE,PACK+'/freeze.json'))
    assert sha(blob(FREEZE,acceptance))==fs['acceptance_sha256']
    assert sha(prior_raw)==fs['accepted_prior_manifest_sha256']
    assert not git('diff','--name-only',BASE,code,'--','src','configs','docs/mainline/v6-native-method-comparison-v1')
    shared='/share/home/renly/renly-patrol-rsi/mainline'
    doc=dict(schema='aegisdc-native-study-launch-manifest-v1',purpose='NATIVE_V6_RESEARCH',
       state='FINAL_CONTENT_AWAITING_SEPARATE_ONE_USE_DECISION',one_time_grant_required=True,embedded_authorization=False,
       protocol_revision=prior['protocol_revision'],finite_publication=BASE,acceptance_file=acceptance,
       acceptance_sha256=fs['acceptance_sha256'],prior_manifest_sha256=sha(prior_raw),
       protocol_sha256=prior['protocol_sha256'],launch_source_revision=code,launcher_sha256=pins,launcher_tree=canonical(pins),
       native_source_tree=prior['actual_runtime_source_tree'],runtime_and_material_sha256=prior['runtime_and_material_sha256'],
       python=prior['python'],groups=prior['groups'],budget=prior['planned'],
       study_group_order='C01 through C17; in each V,D,K,H,P in five separate processes, including the identical V/H calls',
       activity_root=shared+'/V6-native-method-study-v1',
       release_root=shared+'/V6-research-launch-verification-20261120/attempt01/source',
       consumption_root=shared+'/.native-research-approvals/V6-native-method-study-v1',
       review_authority=dict(repository='DonsonHH/AegisDC',branch='donson/mainline-39c-endpoints',
                            path='docs/mainline/authorizations/v6-native-method-study-v1.json'),
       controller=dict(host='mu01',account='renly',entry='scripts/v6_research_launch.py start',
          required_arguments=['--manifest-sha SHA256_OF_THIS_FILE','--approval-revision PUBLISHED_REVIEW_COMMIT'],
          claim='One exclusive, persistent study-wide receipt outside output root, no refund or rerun',
          scheduler='sbatch --hold --no-requeue, record job id then scontrol release, await same job terminal and verified return before next',
          resources={'partition':'cu','jobs':17,'nodes':1,'ntasks':1,'cpus':1,'MiB':1024,'seconds':120,'gpus':0,'concurrent':1,'retries':0}),
       arm=dict(command=prior['normal_native_command'],H=10,maximum_step_s=0.01,exogenous_work_requests=[],action_commands=[],
         admission='Strict source list and tree, materialized components, interpreter, native requested H10 and dt, original inputs and empty external action commands',
         scorer='aegis_dc.native_compare_score.score_arm on the same verified saved snapshot',
         incomplete='Preserve raw, validated, known, unknown and unresolved separately, no implied retry allowance',
         consistency='V/H require identical full input and saved semantic identity before P may start'),
       lock='A complete panel can be sealed only inside the final approved Slurm allocation, after all 85 saved raw artifact identities and case results are rechecked.',
       actual_study_starts_at_publication=0)
    with (HERE/'research-manifest.json').open('x',encoding='utf-8',newline='\n') as out:
        json.dump(doc,out,indent=2,ensure_ascii=False,allow_nan=False);out.write('\n')
    print(sha((HERE/'research-manifest.json').read_bytes()))

if __name__=='__main__':main()
