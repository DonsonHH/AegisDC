"""Immutable data, code, review identity, and the two disjoint launch domains."""
from dataclasses import dataclass
import getpass
import gzip
import os
from pathlib import Path
import re
import socket
import sys

from cold3_runner import digest, sha
from v6_research.binding import BRANCH, REPO, SHARED, PYTHON, GateError, GitHubReview, check, load_json, raw_sha

PACK='docs/mainline/v6-stage-three-cold-launch-v1'
COLD='docs/mainline/v6-stage-three-cold-v2'
FINAL=PACK+'/launch-manifest.json'
DATA=COLD+'/study-manifest.json'
ACCEPT=COLD+'/acceptance-20261121.json'
GRANT='docs/mainline/authorizations/v6-stage-three-cold-study-v2.json'
DATA_SHA='cccb296c64264092200cbb763a9c697cbf572557055f9747838ceb399d465fd4'
ACCEPT_SHA='295f14043ff3b90cc44605c44717b63206d8a9ab6b095a2bdf86fcef489498a9'
CORE='0e5afde1a5e734a04489f1bf27804db6a3325497'
PUBLICATION='4fa886c0ccf75a7e61fd219ad85b0abd269faacc'
STUDY='V6-cold-study-v2-once'
DEPLOY=SHARED/'V6-cold-launch-release-v1/source'
QUAL=SHARED/'V6-cold-launch-qualification-20261121'
REAL='NATIVE_COLD_RESEARCH'
SURROGATE='PUBLIC_COLD_LAUNCH_SURROGATE'
CLI='scripts/cold3_study_launch.py'
MODULES=('__init__','binding','control','ledger','native','transport')
ADAPTER=tuple('scripts/cold3_launch/'+s+'.py' for s in MODULES)+(CLI,PACK+'/study.sbatch')
REUSED=tuple('scripts/v6_research/'+s+'.py' for s in ('__init__','binding','control','native','slurm'))


@dataclass(frozen=True)
class Release:
    root: Path
    manifest: dict
    sha: str
    data: dict
    inputs: dict

    def keys(self,case):
        return [p['input_key'] for p in self.group(case)['positions']]

    def group(self,case):
        group=next((g for g in self.data['groups'] if g['row']==case),None)
        check(group is not None,'WORKER_ORDER')
        return group

    @property
    def cases(self):
        return [g['row'] for g in self.data['groups']]

    @property
    def slots(self):
        return [p['input_key'] for g in self.data['groups'] for p in g['positions']]


@dataclass(frozen=True)
class Site:
    shared: Path
    purpose: str
    @property
    def activity(self):return self.shared/STUDY
    @property
    def claim(self):return self.shared/'.native-research-approvals'/STUDY

    def validate(self):
        if self.purpose==REAL:
            check(self.shared==SHARED and self.activity==SHARED/STUDY,'PURPOSE')
        else:
            check(self.purpose==SURROGATE and self.shared.is_absolute() and self.shared.resolve().is_relative_to(QUAL)
                  and self.shared.resolve()!=QUAL,'PURPOSE')
        for path in (self.shared,self.activity,self.claim.parent,self.claim):
            check(path.resolve()==path,'DEPLOYMENT_IDENTITY')


def load_release(root,expected):
    root=Path(root).resolve()
    raw=(root/FINAL).read_bytes()
    check(raw_sha(raw)==expected,'MANIFEST_IDENTITY')
    m=load_json(raw)
    check(m['schema']=='aegisdc-cold-single-use-launch-v1' and m['purpose']==REAL and m['one_time_review_required'] is True
          and m['embedded_grant'] is None and m['retries']==0,'MANIFEST_BINDING')
    check(m['data_sha256']==DATA_SHA==sha(root/DATA) and m['acceptance_sha256']==ACCEPT_SHA==sha(root/ACCEPT),'DATA_OR_ACCEPTANCE_IDENTITY')
    d=load_json((root/DATA).read_bytes());a=load_json((root/ACCEPT).read_bytes())
    check(a['publication']==PUBLICATION and a['execution_revision']==CORE==d['release_revision'] and
          a['input_freeze']==m['input_freeze_revision'] and m['core_revision']==CORE and
          m['accepted_publication']==PUBLICATION,'ACCEPTANCE_IDENTITY')
    check(d['state']=='STOP_AT_RESEARCH_LAUNCH_REVIEW' and d['authority'] is None and d['study_starts']==0 and
          d['retries']==0 and m['groups']==d['groups'] and m['limits']==d['limits'],'SCHEDULE_IDENTITY')
    check(m['root']==str(SHARED/STUDY) and m['claim']==str(Site(SHARED,REAL).claim) and m['release_root']==str(DEPLOY)
          and m['authority']==dict(repository=REPO,branch=BRANCH,path=GRANT),'DEPLOYMENT_IDENTITY')
    check(m['python']['path']==PYTHON and Path(sys.executable).resolve()==Path(PYTHON).resolve() and
          sha(Path(sys.executable))==d['python_sha256']==m['python']['sha256'] and
          sys.version.split()[0]==m['python']['version'],'PYTHON_IDENTITY')
    check(m['core_files']==d['execution_file_sha256'] and set(m['launch_files'])==set(ADAPTER+REUSED)
          and digest(m['launch_files'])==m['launch_tree'],'SOURCE_IDENTITY')
    from .transport import commands
    check(m['commands']==commands(),'COMMAND_IDENTITY')
    files=m['core_files']|m['launch_files']
    for folder in ('src/aegis_dc','src/patrol_rsi','scripts/v6_research','scripts/cold3_launch'):
        deployed={p.relative_to(root).as_posix() for p in (root/folder).rglob('*.py')}
        check(deployed=={k for k in files if k.startswith(folder+'/') and k.endswith('.py')},'SOURCE_IDENTITY',folder)
    for path,h in files.items():
        check((root/path).resolve().is_relative_to(root) and (root/path).is_file() and sha(root/path)==h,'SOURCE_IDENTITY',path)
    for field,path in [('protocol_sha256','protocol.md'),('matrix_sha256','conditions.json'),('input_freeze_sha256','input-freeze.json'),
                       ('earlier_disclosure_sha256','disclosure.json.gz'),('new_observed_prefix_sha256','engineering-prefix-overlap.json.gz')]:
        check(sha(root/COLD/path)==d[field],'DATA_IDENTITY',path)
    check(m['input_archive']==COLD+'/study-inputs.json.gz' and sha(root/m['input_archive'])==d['data_sha256']==m['input_sha256'],'INPUT_ARCHIVE_IDENTITY')
    with gzip.open(root/m['input_archive'],'rb') as f:items=load_json(f.read())
    rel=Release(root,m,expected,d,items);slots=rel.slots
    check(len(rel.cases)==len(set(rel.cases))==24 and len(slots)==len(set(slots))==len(items)==66 and set(slots)==set(items),'SCHEDULE_IDENTITY')
    check(m['denominators']=={'J/B':24,'J_OPEN':4,'J_NO_PROBE':10,'J_ORDER':4},'SCHEDULE_IDENTITY')
    c=0
    for g in d['groups']:
        keys=rel.keys(g['row'])
        check(keys[:2]==[g['row']+'-J',g['row']+'-B'] and g['primary']==keys[:2]
              and g['mechanism_pairs']==[[keys[0],k] for k in keys[2:]],'SCHEDULE_IDENTITY')
        for p in g['positions']:
            check(p['position']==c and p['public_decisions']==49 and p['H']==12 and p['step']==.01,'SCHEDULE_IDENTITY')
            verify_item(rel,g['row'],p['input_key'],items[p['input_key']]);c+=1
    return rel


def verify_item(rel,case,slot,item):
    p=next((x for x in rel.group(case)['positions'] if x['input_key']==slot),None)
    check(p is not None and digest(item)==p['complete_call_sha256'],'INPUT_IDENTITY',slot)
    cfg=item['dispatch_program']['policy_program']
    check(cfg['method']==p['arm'] and cfg['clock']==[i/4 for i in range(49)] and
          item['duration_s']==12 and item['step_s']==.01 and item['private_physical_audit'] is True and
          item['business_program'] is None and item['boundary_events']==item['action_commands']==item['work_requests']==[] and
          digest(item['scenario'])==p['scenario_sha256'] and digest(item['dispatch_program'])==p['dispatch_sha256'],'INPUT_IDENTITY',slot)


def bind_grant(rel,site,grant):
    m=rel.manifest
    check(isinstance(grant,dict),'GRANT_BINDING')
    ref=grant.get('user_decision_reference')
    check(isinstance(ref,str) and 0<len(ref.strip())<=500,'GRANT_BINDING')
    fields=dict(schema='cold-single-use-reviewed-grant-v1',purpose=site.purpose,decision='APPROVE_ONE_LAUNCH',uses=1,
        study=STUDY,launch_sha256=rel.sha,data_sha256=DATA_SHA,input_sha256=m['input_sha256'],acceptance_sha256=ACCEPT_SHA,
        adapter_revision=m['adapter_revision'],launch_tree=m['launch_tree'],core_revision=CORE,core_tree=m['core_tree'],
        order_sha256=digest(m['groups']),limits_sha256=digest(m['limits']),activity_root=str(site.activity),user_decision_reference=ref)
    check(digest(grant)==digest(fields),'GRANT_BINDING')
    return grant


class Review(GitHubReview):
    def authorize(self,rel,revision,site):
        check(revision is not None,'AUTHORIZATION_REQUIRED');check(re.fullmatch('[a-f0-9]{40}',revision or ''),'REVIEW_IDENTITY')
        def current():
            ref=self.obtain('/git/ref/heads/'+BRANCH)
            check(ref.get('ref')=='refs/heads/'+BRANCH and ref.get('object',{}).get('type')=='commit' and ref['object'].get('sha')==revision,'REVIEW_IDENTITY')
        current()
        grant=bind_grant(rel,site,load_json(self.reviewed_file(GRANT,revision)))
        for path,h,code in [(FINAL,rel.sha,'MANIFEST_IDENTITY'),(DATA,DATA_SHA,'DATA_IDENTITY'),(ACCEPT,ACCEPT_SHA,'ACCEPTANCE_IDENTITY')]:
            check(raw_sha(self.reviewed_file(path,revision))==h,code)
        current()
        return dict(review_revision=revision,grant=grant,grant_digest=digest(grant),launch_sha256=rel.sha)


def host(root,login):
    check(root.resolve()==DEPLOY and getpass.getuser()=='renly' and Path.home()==Path('/share/home/renly'),'DEPLOYMENT_IDENTITY')
    if login:check(socket.gethostname().split('.')[0]=='mu01' and not os.environ.get('SLURM_JOB_ID'),'DEPLOYMENT_IDENTITY')
