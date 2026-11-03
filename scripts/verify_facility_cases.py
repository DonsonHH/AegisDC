"""Check source/diagram/export identity and evidence boundaries, not site physics.

Uses the standard library; suitable for the repository's minimal CI job.
"""
from __future__ import annotations
import csv
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
PACK=ROOT/'docs/research/20261104/facility-cases'
EVIDENCE=ROOT/'evidence/facility-case-models-20261104'
SVG='{http://www.w3.org/2000/svg}'

class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=[];self.resources=[];self.anchors=[];self.math=0;self.parameters=0
    def handle_starttag(self,tag,attributes):
        attributes=dict(attributes)
        if 'id' in attributes:self.ids.append(attributes['id'])
        if tag in {'img','script','iframe','source','link'}:
            self.resources.extend(attributes[k] for k in ('src','href') if k in attributes)
        if tag=='a':self.anchors.append(attributes.get('href',''))
        if tag=='math':self.math+=1
        if tag=='tr' and 'data-availability' in attributes:self.parameters+=1

def require(value,message):
    if not value:raise ValueError(message)

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def verify():
    book=json.loads((PACK/'casebook.json').read_text(encoding='utf-8'))
    manifest=json.loads((EVIDENCE/'build-manifest.json').read_text(encoding='utf-8'))
    require(book['schema']=='aegisdc-facility-casebook-v1','Unexpected schema')
    require([c['id'] for c in book['cases']]==['frontier','el-capitan','zhengzhou'],'Three independent cases required')
    require(book['no_new_training'] and book['no_new_registered_experiments'],'Research scope changed')
    for group in ['sources','generated']:
        for name,expected in manifest[group].items():require(sha(ROOT/name)==expected,'Build identity mismatch: '+name)
    count=0;diagrams=[];missing=0;conflicting=0
    for case in book['cases']:
        require(sha(PACK/case['source_note'])==case['source_note_sha256'],'Source-note identity mismatch: '+case['id'])
        require(case['transient_model_status']=='UNRESOLVED_CLOSURE' and case['can_run_calibrated_transient'] is False,'Do not claim calibrated dynamics')
        require(len(case['parameters'])>=15,'Insufficient parameter coverage')
        identifiers=[p['id'] for p in case['parameters']]
        require(len(identifiers)==len(set(identifiers)),'Duplicate parameter')
        for p in case['parameters']:
            count+=1
            require(p['unit'] and p['evidence'] and p['model_use_or_gap'],'Missing units/evidence/use boundary: '+p['id'])
            require(p['availability'] in {'documented','partial','missing','conflicting'},'Unknown availability')
            if p['availability'] in {'missing','partial','conflicting'}:require(p['value'] is None,'Unresolved value must remain null: '+p['id'])
            else:require(p['value'] is not None and p['source_refs'],'Published value needs provenance: '+p['id'])
            require(all(ref in case['sources'] for ref in p['source_refs']),'Cross-case or absent source ref: '+p['id'])
            missing+=p['availability']=='missing';conflicting+=p['availability']=='conflicting'
        exported=list(csv.DictReader(io.StringIO((PACK/'parameters'/f'{case["id"]}.csv').read_text(encoding='utf-8-sig'))))
        require(len(exported)==len(case['parameters']),'CSV count mismatch')
        for p,row in zip(case['parameters'],exported):
            for key,value in row.items():require(value==p[key],'CSV changes parameter: '+p['id']+'/'+key)
        require(len(case['diagrams'])>=2,'Two diagrams per case required')
        for d in case['diagrams']:
            for item in d['nodes']+d['edges']:
                require(all(ref in case['sources'] for ref in item['source_refs']),'Foreign/absent diagram source')
                if item['status'] in {'published','design','model','vendor'}:require(item['source_refs'],'Source-backed graphical element lacks ref')
        diagrams+=case['diagrams']
    diagrams+=book['shared_diagrams']
    require(len(diagrams)>=8,'Eight diagrams required')
    for d in diagrams:
        node_ids=[n['id'] for n in d['nodes']]
        require(len(node_ids)==len(set(node_ids)),'Duplicate diagram node')
        for e in d['edges']:require(e['from'] in node_ids and e['to'] in node_ids,'Dangling edge')
        parsed=ET.fromstring((PACK/'figures'/f'{d["id"]}.svg').read_text(encoding='utf-8'))
        require(parsed.find(SVG+'title').text==d['title'],'Figure title mismatch')
        groups=[e for e in parsed.iter() if 'data-node' in e.attrib]
        paths=[e for e in parsed.iter() if 'data-edge' in e.attrib]
        require(len(groups)==len(d['nodes']) and len(paths)==len(d['edges']),'Graph/ledger count mismatch')
        for n,element in zip(d['nodes'],groups):
            require(element.attrib['data-node']==n['id'] and element.attrib['data-status']==n['status'],'Figure node status mismatch')
            require([x.text for x in element.findall(SVG+'text')][1:]==n['label'],'Figure node content mismatch')
        for e,path in zip(d['edges'],paths):
            require(path.attrib['data-from']==e['from'] and path.attrib['data-to']==e['to'] and path.attrib['data-status']==e['status'],'Figure edge identity mismatch')
    page=Page();text=(PACK/'report.html').read_text(encoding='utf-8');page.feed(text)
    require(len(page.ids)==len(set(page.ids)),'Duplicate HTML/SVG ID')
    require(page.math==manifest['mathml_formulas'] and page.math>=20,'Formula rendering mismatch')
    require(page.parameters==count==manifest['parameter_records'],'HTML parameter count mismatch')
    require(not page.resources,'Reading HTML requires external/adjacent resources')
    for target in page.anchors:
        if target.startswith('#'):require(target[1:] in page.ids,'Broken internal anchor: '+target)
        else:require(target.startswith(('https://','data:')),'Standalone link has a local dependency')
    require('$$' not in text,'Raw display LaTeX left in HTML')
    for path in PACK.glob('*.md'):
        for target in re.findall(r'!?\[[^]]*\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
            if '://' not in target and not target.startswith('#'):
                require((path.parent/target.split('#',1)[0]).exists(),'Broken Markdown link: '+str(path.name)+': '+target)
    return {'status':'PASS','scope':'source identity, provenance boundaries and consistent exports; not dynamic/field validation',
            'cases':len(book['cases']),'parameter_records':count,'missing_records':missing,'conflicting_records':conflicting,
            'diagrams':len(diagrams),'mathml_formulas':page.math,'external_runtime_resources':len(page.resources)}

if __name__=='__main__':
    try:print(json.dumps(verify(),ensure_ascii=False,indent=2))
    except (ValueError,AssertionError) as error:print('FAIL: '+str(error),file=sys.stderr);raise SystemExit(1)
