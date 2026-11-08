"""Verify exact saved report artifacts and source bindings without research calls."""
import argparse
import base64
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess

parser=argparse.ArgumentParser()
parser.add_argument('--checkout',type=Path,required=True)
parser.add_argument('--revision',required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
root=args.checkout;prefix='paper/mentor-review-20261108/'
sha=lambda b:hashlib.sha256(b).hexdigest()
git=lambda *v:subprocess.check_output(['git',*v],cwd=root)
assert git('rev-parse','HEAD').decode().strip()==args.revision
assert not git('status','--porcelain','--untracked-files=no').strip()
def current(path):
    data=(root/path).read_bytes()
    assert data==git('show',args.revision+':'+path),path+' differs from exact Git delivery'
    return data
manifest=json.loads(current(prefix+'report-manifest.json'))
source=manifest['source_commit']
assert source=='435727e7b517f86077aca97ba143d9752c7385f0'
for path,spec in manifest['source_files'].items():
    data=git('show',source+':'+path)
    assert len(data)==spec['bytes'] and sha(data)==spec['sha256'],path
assert manifest['registered_runs_before']==manifest['registered_runs_after']==164
assert manifest['new_physical_calls']==manifest['new_selector_calls']==manifest['new_inference_calls']==manifest['new_research_trials']==0
assert sha(current('scripts/build_mentor_report.py'))==manifest['authoring_sha256']
assert sha(current('scripts/render_mentor_report_figures.py'))==manifest['figure_authoring_sha256']
raw=current(prefix+'AegisDC-导师研究报告.html');assert sha(raw)==manifest['html_sha256']
class Content(HTMLParser):
    def __init__(self):
        super().__init__();self.images=[];self.downloads=[];self.formulas=0;self.parameters=0;self.external=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='img' and a.get('src'):self.images.append(a['src'])
        if tag=='a' and 'download' in a:self.downloads.append((a['download'],a['href']))
        if tag=='math':self.formulas+=1
        if 'data-param' in a:self.parameters+=1
        if tag in ['script','link','iframe'] and a.get('src',a.get('href','')).startswith(('http:','https:')):self.external.append(a)
c=Content();c.feed(raw.decode('utf-8'))
assert len(c.images)==len(manifest['figures'])==15
for uri,fig in zip(c.images,manifest['figures']):
    assert sha(base64.b64decode(uri.split(',',1)[1]))==fig['sha256']
    assert sha(current(prefix+fig['path']))==fig['sha256']
    assert sha(current(prefix+str(Path(fig['path']).with_suffix('.svg')).replace('\\','/')))==fig['svg_sha256']
assert len(c.downloads)==len(manifest['downloads'])==23
for (name,uri),spec in zip(c.downloads,manifest['downloads']):
    data=base64.b64decode(uri.split(',',1)[1]);assert name==spec['name'] and len(data)==spec['bytes'] and sha(data)==spec['sha256']
assert c.formulas==8 and c.parameters==113 and not c.external
qa=json.loads(current(prefix+'qa/responsive-qa.json'))
assert qa['status']=='PASS_MENTOR_REPORT_THREE_VIEWPORTS' and not qa['javascript_errors']
assert sorted(r['viewport'] for r in qa['results'])==[412,1440,1920]
for r in qa['results']:assert r['pageWidth']==r['clientWidth'] and r['parameters']==r['restored']==113
visual=json.loads(current(prefix+'qa/visual-review.json'))
for path,digest in visual['screenshots'].items():assert sha(current(prefix+'qa/'+path))==digest
progress=json.loads(git('show',source+':docs/mainline/progress.json'))
assert progress['research_trials']['attempts']==164 and progress['research_trials']['robustness']['attempts']==0
assert current('docs/mainline/progress.json')==git('show',source+':docs/mainline/progress.json')
assert git('rev-parse','pre-meeting-20261103^{}').decode().strip()=='076d9aa15c5bc99a5b7985f296e15543b7b0f3d7'
receipt=dict(status='PASS_EXACT_FRESH_MENTOR_REPORT',commit=args.revision,source_commit=source,source_files=len(manifest['source_files']),figures=15,formulas=8,parameters=113,downloads=23,registered_runs=164,new_research_trials=0,new_physical_calls=0,new_selector_calls=0,new_inference_calls=0,premeeting_tag_preserved=True)
with args.output.open('x',encoding='utf-8',newline='\n') as f:f.write(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
