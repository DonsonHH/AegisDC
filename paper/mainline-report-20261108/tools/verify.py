"""Saved-only report/source/embedded asset checks; no browser or project model."""
import argparse,base64,csv,hashlib,io,json,re,subprocess,sys,zipfile
from html.parser import HTMLParser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'paper/mainline-report-20261108'
git=lambda *a:subprocess.check_output(['git',*a],cwd=ROOT)
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda p:json.loads(p.read_bytes())

def write(p,d):
    with p.open('x',encoding='utf-8',newline='\n') as f:f.write(json.dumps(d,ensure_ascii=False,indent=2)+'\n')

class Page(HTMLParser):
    def __init__(self):super().__init__();self.images=[];self.downloads=[];self.links=[];self.ids=[];self.h1=0;self.h2=0;self.script=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='h1':self.h1+=1
        if tag=='h2':self.h2+=1
        if tag=='script':self.script+=1
        if tag=='img':self.images.append(a)
        if tag=='a':
            self.links.append(a.get('href',''))
            if 'download' in a:self.downloads.append(a)

def validate():
    source=git('rev-parse','HEAD').decode().strip();m=read(OUT/'source-manifest.json')
    for name,entry in m['inputs'].items():
        raw=(ROOT/name).read_bytes();assert sha(raw)==entry['sha256'] and len(raw)==entry['bytes'],name
        assert git('cat-file','blob',m['scientific_cutoff']+':'+name)==raw
    for name,h in m['tools'].items():
        assert sha((ROOT/name).read_bytes())==h and sha(git('cat-file','blob',m['authoring_source']+':'+name))==h
    facts=read(OUT/'facts.json');primary=read(OUT/'data/primary.json');ablation=read(OUT/'data/ablation.json');robust=read(OUT/'data/robustness.json')
    assert facts['total_runs']==sum(p['completed'] for p in facts['phases'])==180
    assert facts['total_simulated_s']==sum(p['charged_simulated_s'] for p in facts['phases'])==1800
    assert facts['primary']['status']==primary['status']=='NO_PRACTICAL_GAIN'
    assert facts['primary']['mean_service_delta_s']==primary['mean_service_delta_s']==.03515625
    assert facts['ablation_summary']==ablation['summary'] and facts['robustness_paired']==robust['paired']
    assert abs(facts['robustness_mean']+.084375)<1e-12 and robust['contrast_blocks']==4
    assert len(list(csv.DictReader(io.StringIO((OUT/'data/model-parameters.csv').read_bytes().decode('utf-8-sig')))))==113
    assert len(read(OUT/'data/metric-coverage.json'))==18
    assert (facts['domain_count'],facts['entity_count'],facts['parameter_count'])==(8,45,113)
    assert facts['formal_closure']=='NOT_EVALUATED' and facts['AI_RSI']=='NOT_MEASURED'
    text=(OUT/'AegisDC-会后研究报告.html').read_text(encoding='utf-8');md=(OUT/'report.md').read_text(encoding='utf-8')
    assert '{{' not in text and '{{' not in md
    parser=Page();parser.feed(text)
    assert parser.h1==1 and parser.h2==6 and parser.script==0 and len(parser.images)==8 and len(parser.downloads)==22
    assert len(parser.ids)==len(set(parser.ids))
    for href in parser.links:
        if href.startswith('#'):assert href[1:] in parser.ids
        elif not href.startswith('data:'):assert (OUT/href.split('#')[0]).exists(),href
    figures=read(OUT/'figure-sources.json');pngs={r['png_sha256'] for r in figures};expected={p.name:sha(p.read_bytes()) for folder in ['figures','data'] for p in (OUT/folder).iterdir()}
    for image in parser.images:
        assert image.get('alt') and image['src'].startswith('data:image/png;base64,')
        raw=base64.b64decode(image['src'].split(',',1)[1],validate=True);assert sha(raw) in pngs
    for link in parser.downloads:
        raw=base64.b64decode(link['href'].split(',',1)[1],validate=True);assert sha(raw)==expected[link['download']]
    for row in figures:
        stem=f"{row['number']:02}-{row['id']}"
        assert sha((OUT/'figures'/(stem+'.png')).read_bytes())==row['png_sha256']
        assert sha((OUT/'figures'/(stem+'.svg')).read_bytes())==row['svg_sha256']
    assert '@media(max-width:640px)' in text and '@media(min-width:1600px)' in text and '.figure-scroll{overflow-x:auto' in text
    assert '0.03515625' in md and '−0.084375' in md and '0.25' in md
    assert '`closure_program=None`' in md and '没有测量证据验证关闭' in md
    assert '未测' in md and '4秒' in md and '8.5秒' in md and '100秒' in md
    terminal=sorted((OUT/'builds').glob('build-*.terminal.json'))[-1];b=read(terminal)
    assert b['status']=='PASS_SAVED_REPORT_BUILD' and b['html_sha256']==sha(text.encode()) and b['markdown_sha256']==sha(md.encode())
    assert not any(n.startswith('aegis_dc') for n in sys.modules)
    return dict(status='PASS_SAVED_REPORT_SOURCE_AND_STRUCTURE',source=source,source_inputs=len(m['inputs']),figures=8,downloads=22,
        parameter_rows=113,registered_runs=180,actual_browser_QA=False,QA_scope='Source arithmetic, embedded original bytes, links and static responsive CSS; no new browser run',
        new_physical_calls=0,new_selectors=0,new_inference=0,new_trials=0)

def declaration():return {p.relative_to(OUT).as_posix() for p in OUT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.pyc','.pyo'} and p.name!='delivery-manifest.json'}

def seal():
    names=declaration();source=git('rev-parse','HEAD').decode().strip();files={n:sha((OUT/n).read_bytes()) for n in sorted(names)}
    for n,h in files.items():assert sha(git('cat-file','blob',source+':paper/mainline-report-20261108/'+n))==h
    write(OUT/'delivery-manifest.json',dict(schema='aegisdc-37-report-delivery-v1',authoring_source=source,files=files,scope='Report, source data/figures, tools, all builds and reviews; caches excluded.'))
    return dict(status='SEALED_REPORT_DELIVERY',files=len(files))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['validate','seal','fresh']);p.add_argument('--output',type=Path);a=p.parse_args()
    try:
        if a.mode=='seal':result=seal()
        else:
            result=validate()
            if a.mode=='fresh':
                m=read(OUT/'delivery-manifest.json');assert declaration()==set(m['files'])
                for n,h in m['files'].items():
                    assert sha((OUT/n).read_bytes())==h and sha(git('cat-file','blob','HEAD:paper/mainline-report-20261108/'+n))==h,n
                result.update(status='PASS_FRESH_REPORT_DELIVERY',declared_files=len(m['files']))
            if a.output:write(a.output,result)
        print(json.dumps(result,ensure_ascii=False))
    except BaseException as exc:
        if a.output and not a.output.exists():write(a.output,dict(status='FAILED_REPORT_CHECK',error_type=type(exc).__name__,error=str(exc),new_trials=0))
        raise
