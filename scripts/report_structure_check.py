"""Check the requested method/result separation on the rendered HTML tree."""
from html.parser import HTMLParser
import re

SECTIONS=['overview','model','hotspots','fifo','comparison','roadmap','appendix']
METHOD_FIGURES={'model':'model','pid-visual-sample':'hotspots','visual-interface':'hotspots',
                'supplement-unet':'hotspots','inspection-architecture':'fifo','supplement-crossed-design':'fifo'}
RESULT_FIGURES=['supplement-estimator-training','supplement-ppo-training','supplement-estimation',
                'supplement-heatmaps','supplement-process','supplement-methods','supplement-professions',
                'supplement-contrasts','supplement-latency','supplement-scale']
APPENDIX_FIGURES=['estimated-temperature','offline-temperature','public-risk','confirmations','outcome-costs',
                  'paired-net','fifo-cycle','fifo-actions','registered-rules','rule-diagnosis','execution-chain',
                  'task-17','task-21','original-paper-scores','supplement-seed-blocks']


class Structure(HTMLParser):
    def __init__(self):
        super().__init__();self.section=None;self.sections=[];self.svg=0;self.optional=0
        self.heading=None;self.headings=[];self.figures={};self.tables={};self.nav=False;self.link=None;self.links=[]
        self.text={section:[] for section in SECTIONS}
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='svg':self.svg+=1;return
        if self.svg:return
        if tag=='section':self.section=attrs['id'];self.sections.append(self.section)
        elif tag=='details':self.optional+=1
        elif tag=='figure':self.figures[attrs['id'].removeprefix('figure-')]={'section':self.section,'optional':bool(self.optional)}
        elif tag=='table' and 'data-table' in attrs:self.tables[attrs['data-table']]=self.section
        elif tag in ('h2','h3','h4'):self.heading=[int(tag[1]),self.section,[]]
        elif tag=='nav' and 'contents' in attrs.get('class','').split():self.nav=True
        elif tag=='a' and self.nav:self.link=[attrs.get('href'),[]]
    def handle_data(self,text):
        if self.svg:return
        if self.heading is not None:self.heading[2].append(text)
        if self.link is not None:self.link[1].append(text)
        if self.section in self.text:self.text[self.section].append(text)
    def handle_endtag(self,tag):
        if tag=='svg':self.svg-=1;return
        if self.svg:return
        if tag=='section':self.section=None
        elif tag=='details':self.optional-=1
        elif tag in ('h2','h3','h4') and self.heading is not None:
            level,section,text=self.heading;self.headings.append((level,section,''.join(text).strip()));self.heading=None
        elif tag=='a' and self.link is not None:
            self.links.append((self.link[0],''.join(self.link[1]).strip()));self.link=None
        elif tag=='nav':self.nav=False


def verify_structure(html):
    parsed=Structure();parsed.feed(html)
    assert parsed.sections==SECTIONS
    h2=[(section,text) for level,section,text in parsed.headings if level==2]
    assert len(h2)==7
    for number,(section,text) in enumerate(h2):assert section==SECTIONS[number] and text.startswith(f'{number}. '),(section,text)
    assert len(parsed.links)==7
    for number,(href,text) in enumerate(parsed.links):assert href=='#'+SECTIONS[number] and text.startswith(f'{number}. ')
    parent={};numbers=set();appendices=[]
    for level,section,text in parsed.headings:
        assert '?' not in text and '？' not in text,(level,text)
        if level==2:continue
        chapter=SECTIONS.index(section)
        if level==4 and section=='appendix':
            found=re.match(r'附录 ([A-H])\.',text);assert found,text;appendices.append(found[1]);continue
        found=re.match(r'(\d+(?:\.\d+)+)\s',text);assert found,(level,text)
        parts=tuple(map(int,found[1].split('.')))
        assert len(parts)==level-1 and parts[0]==chapter and parts not in numbers,(level,text)
        numbers.add(parts)
        if level==3:parent[section]=parts
        else:assert parts[:2]==parent[section],(level,text)
    assert appendices==list('ABCDEFGH')
    assert len(parsed.figures)==31
    for name,section in METHOD_FIGURES.items():assert parsed.figures[name]=={'section':section,'optional':False},name
    for name in RESULT_FIGURES:assert parsed.figures[name]=={'section':'comparison','optional':False},name
    for name in APPENDIX_FIGURES:assert parsed.figures[name]=={'section':'appendix','optional':True},name
    for section in ('overview','model','hotspots','fifo'):
        assert '/89' not in ''.join(parsed.text[section]),section
    for name in ['supplement-errors','supplement-tasks','supplement-fixed-stream','supplement-contrasts',
                 'supplement-healthy','supplement-latency','supplement-scale','supplement-scale-cycles','supplement-training']:
        assert parsed.tables[name]=='comparison',name
    assert parsed.tables['task-contract']=='fifo' and parsed.tables['fifo-queue']=='appendix'
    return {'chapter_order_verified':SECTIONS,'numbered_headings_verified':len(parsed.headings),
            'method_figures':len(METHOD_FIGURES),'result_figures_in_chapter4':len(RESULT_FIGURES),
            'historical_and_detail_figures_in_appendix':len(APPENDIX_FIGURES),'figure_locations':parsed.figures,
            'numbered_navigation_entries':len(parsed.links)}
