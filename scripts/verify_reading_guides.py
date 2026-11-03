"""Check guide coverage, association and preserved evidence independently of rendering."""
from collections import Counter
from html.parser import HTMLParser
import hashlib
import json
import re


class Guides(HTMLParser):
    def __init__(self):
        super().__init__();self.svg=0;self.figure=None;self.table_guide=None;self.depth=0;self.pending=None
        self.figures={};self.tables={};self.figure_keys=[];self.table_keys=[];self.labels=[];self.label=None;self.table_count=0;self.plain=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='svg':self.svg+=1;return
        if self.svg:return
        if tag=='figure':
            self.figure=a['id'].removeprefix('figure-');assert self.figure not in self.figures;self.figures[self.figure]=[]
        if tag=='div':
            if 'table-guide' in a.get('class','').split():
                assert not self.table_guide and not self.pending
                self.table_guide=a['id'].removeprefix('table-');self.pending=self.table_guide;self.depth=1;self.tables[self.table_guide]=[]
            elif self.table_guide:self.depth+=1
        if 'data-guide-figure' in a:
            key=a['data-guide-figure'];self.figure_keys.append(key)
            if self.figure:assert key==self.figure
        if 'data-guide-table' in a:
            key=a['data-guide-table'];self.table_keys.append(key);assert key==self.table_guide
        if tag=='table':
            assert self.pending,'Table has no adjacent reading guide'
            if 'data-table' in a:assert a['data-table']==self.pending
            self.table_count+=1;self.pending=None
        if tag=='span' and 'exhibit-number' in a.get('class','').split():self.label=[]
    def handle_data(self,text):
        if self.svg:return
        self.plain.append(text)
        if self.figure:self.figures[self.figure].append(text)
        if self.table_guide:self.tables[self.table_guide].append(text)
        if self.label is not None:self.label.append(text)
    def handle_endtag(self,tag):
        if tag=='svg':self.svg-=1;return
        if self.svg:return
        if tag=='figure':self.figure=None
        if tag=='div' and self.table_guide:
            self.depth-=1
            if not self.depth:self.table_guide=None
        if tag=='span' and self.label is not None:self.labels.append(''.join(self.label).strip());self.label=None


def verify(root,html,manifest):
    read=lambda p:json.loads((root/p).read_text(encoding='utf-8'))
    sha=lambda p:hashlib.sha256((root/p).read_bytes()).hexdigest()
    guides=read('paper/source-data/report-reading-guides.json');parsed=Guides();parsed.feed(html)
    norm=lambda value:''.join(value.split())
    for kind,collection in [('figures',parsed.figures),('tables',parsed.tables)]:
        assert set(collection)==set(guides[kind])
        for key,record in guides[kind].items():
            text=norm(''.join(collection[key]))
            for field in ['title','purpose','read','takeaway']:assert norm(record[field]) in text,(kind,key,field)
    assert parsed.figure_keys==manifest['reading_guides']['figures'] and parsed.table_keys==manifest['reading_guides']['tables']
    assert [v for v in parsed.labels if v.startswith('图')]==[f'图 {i}' for i in range(1,32)]
    assert [v for v in parsed.labels if v.startswith('表')]==[f'表 {i}' for i in range(1,28)]
    assert parsed.table_count==27
    from markdown_it import MarkdownIt
    exported=manifest['text_export'];full=Guides();full.feed(MarkdownIt('commonmark',{'html':True}).enable('table').render((root/exported['full']['path']).read_text(encoding='utf-8')))
    for field,expected in [('figure_keys',parsed.figure_keys),('table_keys',parsed.table_keys)]:assert getattr(full,field)==expected
    for key,record in guides['figures'].items():
        for field in ['title','purpose','read','takeaway']:assert norm(record[field]) in norm(''.join(full.plain)),(key,field)
    fragment_keys={'figure_keys':[],'table_keys':[]}
    for row in exported['sections']:
        part=Guides();part.feed(MarkdownIt('commonmark',{'html':True}).enable('table').render((root/'paper/text-review'/row['path']).read_text(encoding='utf-8')))
        for field in fragment_keys:fragment_keys[field].extend(getattr(part,field))
    assert all(Counter(fragment_keys[field])==Counter(getattr(parsed,field)) for field in fragment_keys)
    for row in guides['symbols']:assert norm(row['meaning']) in norm(''.join(parsed.plain))
    baseline=read('paper/briefing-history/29bb834f/baseline.json')
    for row in baseline['files'].values():assert sha(row['archived_as'])==row['sha256']
    for path,identity in baseline['protected_inputs'].items():assert sha(path)==identity,path
    old=read('paper/briefing-history/29bb834f/briefing-manifest.json')
    assert manifest['figure_sha256']==old['figure_sha256']
    assert manifest['data_sha256']==old['data_sha256']
    previous=(root/'paper/briefing-history/29bb834f/supervisor-briefing.html').read_text(encoding='utf-8')
    assert re.findall(r'<table\b[^>]*>.*?</table>',html,re.S)==re.findall(r'<table\b[^>]*>.*?</table>',previous,re.S)
    return {'figure_guides_verified':31,'table_guides_verified':27,'symbol_explanations_verified':len(guides['symbols']),
            'guide_numbering_and_table_association':True,'unchanged_v10_figures':31,'unchanged_v10_tables':27,
            'unchanged_v10_report_files':len(baseline['files']),'review_chapters':len(exported['chapters']),'review_parts':len(exported['sections'])}
