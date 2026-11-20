"""Immutable source, manifest and independently published one-use decision bindings."""
import base64
from dataclasses import dataclass
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sys
import urllib.error
import urllib.request

from aegis_dc.native_compare_inputs import Conditions, file_hash
from patrol_rsi.contracts import digest

PACK='docs/mainline/v6-native-research-launch-v1'
MANIFEST=PACK+'/research-manifest.json'
ENGINEERING='docs/mainline/v6-native-comparison-qualification-v1'
ACCEPTANCE=ENGINEERING+'/acceptance-20261120.json'
PRIOR=ENGINEERING+'/research-manifest.json'
PROTOCOL='53cc32b93dd62c8ce5ffd725eed9afba167557e5'
FINITE='984071352142239201e3b69a449207ec35cd7cfa'
ACCEPTANCE_SHA='c12a18f1e279c5a07067c366b050e82b9ec6a199b1050dc81fbcb6fd101ac938'
ACCEPTED_PRIOR_SHA='6e04fe74e64ac0cccd91b959003c3267e5a23e9d0cb24784acdcb75b25bb8282'
BRANCH='donson/mainline-39c-endpoints'
REPO='DonsonHH/AegisDC'
GRANT_PATH='docs/mainline/authorizations/v6-native-method-study-v1.json'
SHARED=Path('/share/home/renly/renly-patrol-rsi/mainline')
RELEASE=SHARED/'V6-research-launch-verification-20261120/attempt01/source'
STUDY='V6-native-method-study-v1'
PYTHON='/share/home/renly/miniconda3/bin/python'
REAL='NATIVE_V6_RESEARCH'
SURROGATE='PUBLIC_LAUNCH_SURROGATE'
CASES=tuple(f'C{i:02}' for i in range(1,18))
ARMS=('V','D','K','H','P')
LAUNCH_FILES=('scripts/v6_research_launch.py','scripts/v6_research/__init__.py','scripts/v6_research/binding.py',
              'scripts/v6_research/control.py','scripts/v6_research/native.py','scripts/v6_research/slurm.py',PACK+'/study.sbatch')


class GateError(ValueError):
    def __init__(self, code, detail=''):
        self.code=code
        super().__init__(code+(': '+str(detail) if detail else ''))


def check(test, code, detail=''):
    if not test:
        raise GateError(code,detail)


def load_json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            check(key not in result,'MALFORMED_JSON','duplicate '+key)
            result[key]=value
        return result
    def invalid(value):
        raise GateError('MALFORMED_JSON',value)
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid)


def raw_sha(raw):
    return hashlib.sha256(raw).hexdigest()


@dataclass
class Release:
    root: Path
    manifest: dict
    sha: str
    conditions: Conditions


def load_release(root, expected_sha):
    root=Path(root).resolve()
    raw=(root/MANIFEST).read_bytes()
    check(raw_sha(raw)==expected_sha,'MANIFEST_IDENTITY')
    m=load_json(raw)
    check(m['schema']=='aegisdc-native-study-launch-manifest-v1' and m['purpose']==REAL and
          m['protocol_revision']==PROTOCOL and m['finite_publication']==FINITE and m['one_time_grant_required'] is True,'MANIFEST_BINDING')
    check(m['activity_root']==str(SHARED/STUDY) and m['release_root']==str(RELEASE) and
          m['review_authority']=={'repository':REPO,'branch':BRANCH,'path':GRANT_PATH},'MANIFEST_BINDING')
    check(Path(sys.executable).resolve()==Path(PYTHON).resolve() and m['python']['path']==PYTHON
          and file_hash(Path(sys.executable).resolve())==m['python']['sha256']
          and sys.version.split()[0]==m['python']['version'],'PYTHON_IDENTITY')
    check(file_hash(root/PRIOR)==ACCEPTANCE_SHA='c12a18f1e279c5a07067c366b050e82b9ec6a199b1050dc81fbcb6fd101ac938'
ACCEPTED_PRIOR_SHA==m['prior_manifest_sha256'],'PROTOCOL_IDENTITY')
    prior=load_json((root/PRIOR).read_bytes())
    check(file_hash(root/ACCEPTANCE)==m['acceptance_sha256']==ACCEPTANCE_SHA and load_json((root/ACCEPTANCE).read_bytes())['publication']==FINITE,'ACCEPTANCE_IDENTITY')
    check(digest(m['groups'])==digest(prior['groups']) and digest(m['budget'])==digest(prior['planned'])
          and [r['condition'] for r in m['groups']]==list(CASES) and all(r['fixed_order']==list(ARMS) for r in m['groups']),
          'SCHEDULE_IDENTITY')
    check(m['runtime_and_material_sha256']==prior['runtime_and_material_sha256'] and m['python']==prior['python']
          and m['native_source_tree']==prior['actual_runtime_source_tree'],'SOURCE_IDENTITY')
    check(set(m['launcher_sha256'])==set(LAUNCH_FILES) and m['launcher_tree']==digest(m['launcher_sha256']),'SOURCE_IDENTITY')
    runtime=m['runtime_and_material_sha256']
    actual_python={p.relative_to(root).as_posix() for p in (root/'src/aegis_dc').rglob('*.py')}
    check(actual_python=={k for k in runtime if k.startswith('src/aegis_dc/') and k.endswith('.py')},'SOURCE_IDENTITY','module set')
    check({p.relative_to(root).as_posix() for p in (root/'scripts/v6_research').glob('*.py')}
          =={k for k in LAUNCH_FILES if k.startswith('scripts/v6_research/')},'SOURCE_IDENTITY','launch module set')
    for path,h in (runtime|m['launcher_sha256']).items():
        check((root/path).is_file() and file_hash(root/path)==h,'SOURCE_IDENTITY',path)
    native={k:v for k,v in runtime.items() if (k.startswith('src/aegis_dc/') and k.count('/')==2 and k.endswith('.py')) or k=='src/patrol_rsi/contracts.py'}
    check(digest(native)==m['native_source_tree'],'SOURCE_IDENTITY','native tree')
    conditions=Conditions(root)
    check(m['protocol_sha256']==prior['protocol_sha256'],'PROTOCOL_IDENTITY')
    for name,h in m['protocol_sha256'].items():
        check(file_hash(root/'docs/mainline/v6-native-method-comparison-v1'/name)==h,'PROTOCOL_IDENTITY',name)
    return Release(root,m,expected_sha,conditions)


def grant_fields(release, purpose):
    m=release.manifest
    return dict(schema='aegisdc-single-use-reviewed-study-grant-v1',purpose=purpose,decision='APPROVE_ONE_LAUNCH',
        grant_id=STUDY,manifest_sha256=release.sha,acceptance_sha256=m['acceptance_sha256'],
        protocol_revision=PROTOCOL,finite_publication=FINITE,published_launcher_revision=m['launch_source_revision'],
        launcher_tree=m['launcher_tree'],native_source_tree=m['native_source_tree'],python_sha256=m['python']['sha256'],
        schedule_sha256=digest(m['groups']),budget_sha256=digest(m['budget']),activity_root=m['activity_root'],uses=1)


def check_grant(release, grant, purpose):
    check(isinstance(grant,dict),'GRANT_BINDING')
    fields=grant_fields(release,purpose)
    reference=grant.get('user_decision_reference')
    check(isinstance(reference,str) and 0<len(reference.strip())<=500,'GRANT_BINDING')
    check(digest(grant)==digest(dict(fields,user_decision_reference=reference)),'GRANT_BINDING')
    return grant


class GitHubReview:
    """Only the canonical reviewed branch can supply authority to the production CLI."""
    base='https://api.github.com/repos/'+REPO

    def obtain(self, path):
        url=self.base+path
        request=urllib.request.Request(url,headers={'Accept':'application/vnd.github+json','User-Agent':'AegisDC-native-study-review'})
        try:
            with urllib.request.urlopen(request,timeout=15) as response:
                check(response.geturl()==url,'REVIEW_IDENTITY')
                data=response.read(2_000_001)
                check(len(data)<=2_000_000,'REVIEW_IDENTITY')
                return load_json(data)
        except urllib.error.HTTPError as exc:
            if exc.code==404:
                raise GateError('GRANT_ABSENT',path) from exc
            raise GateError('REVIEW_UNAVAILABLE',exc.code) from exc
        except OSError as exc:
            raise GateError('REVIEW_UNAVAILABLE',str(exc)) from exc

    def reviewed_file(self, path, revision):
        info=self.obtain('/contents/'+path+'?ref='+revision)
        check(info.get('type')=='file' and info.get('path')==path and info.get('encoding')=='base64','REVIEW_IDENTITY')
        raw=base64.b64decode(''.join(info['content'].split()),validate=True)
        git_sha=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        check(info.get('sha')==git_sha and info.get('size')==len(raw),'REVIEW_IDENTITY')
        return raw

    def authorize(self, release, revision, purpose):
        check(revision is not None,'AUTHORIZATION_REQUIRED')
        check(re.fullmatch('[0-9a-f]{40}',revision or ''),'REVIEW_IDENTITY')
        def current():
            row=self.obtain('/git/ref/heads/'+BRANCH)
            check(row['ref']=='refs/heads/'+BRANCH and row['object'].get('type')=='commit' and row['object'].get('sha')==revision,'REVIEW_IDENTITY')
        current()
        grant=check_grant(release,load_json(self.reviewed_file(GRANT_PATH,revision)),purpose)
        check(raw_sha(self.reviewed_file(MANIFEST,revision))==release.sha,'MANIFEST_IDENTITY')
        check(raw_sha(self.reviewed_file(ACCEPTANCE,revision))==release.manifest['acceptance_sha256'],'ACCEPTANCE_IDENTITY')
        current()
        return dict(review_revision=revision,grant=grant,grant_digest=digest(grant),manifest_sha256=release.sha)


def production_host(root, login):
    check(Path(root).resolve()==RELEASE and getpass.getuser()=='renly' and Path.home()==Path('/share/home/renly'),'DEPLOYMENT_IDENTITY')
    if login:check(socket.gethostname().split('.')[0]=='mu01' and 'SLURM_JOB_ID' not in os.environ,'DEPLOYMENT_IDENTITY')
