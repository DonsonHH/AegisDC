"""Render ticket17 timing and source diagrams from declared/captured data."""
from hashlib import sha256
from html import escape
import json
from pathlib import Path


def render(directory, output):
    directory, output = Path(directory), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    book=json.loads((directory/'runbook-copy.json').read_text(encoding='utf-8'))
    profile=json.loads((directory/'profile-copy.json').read_text(encoding='utf-8'))
    plan=json.loads((directory/'private-plan-copy.json').read_text(encoding='utf-8'))
    saved=json.loads((directory/'snapshots.json').read_text(encoding='utf-8'))
    fingerprint=sha256((directory/'profile-copy.json').read_bytes()).hexdigest()

    def start(title, height):
        return [f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}">',
            '<rect width="1200" height="100%" fill="#f7f9fc"/>',
            '<style>text{font-family:Arial,sans-serif;fill:#14243b} .muted{fill:#52647d} .small{font-size:14px} .label{font-size:16px} .title{font-size:25px;font-weight:700}</style>',
            f'<metadata>ENGINEERING_NOT_RESEARCH; public profile SHA256 {fingerprint}</metadata>',
            f'<text x="40" y="45" class="title">{escape(title)}</text>']

    def text(svg,x,y,value,css='label',color=None):
        fill=f' style="fill:{color}"' if color else ''
        svg.append(f'<text x="{x}" y="{y}" class="{css}"{fill}>{escape(str(value))}</text>')

    svg=start('Nonfixed evidence: observation, arrival and expiry',640)
    text(svg,40,74,'Same V6 synthetic facility | declared producer fixtures | seconds | no professional executor21/22','small')
    left,right=300,1150
    x=lambda t:left+(t+100)/220*(right-left)
    for t in [-100,-50,0,30,65.5,98,120]:
        svg.append(f'<line x1="{x(t)}" x2="{x(t)}" y1="105" y2="447" stroke="#d7dfeb"/>')
        text(svg,round(x(t)-12,2),100,t,'small')
    rows=plan['reported_records']+[r['completion'] for r in plan['completion_requests'][:2]]
    for index,row in enumerate(rows):
        y=137+index*44
        is_token='completed_at_s' in row
        observed=row['completed_at_s'] if is_token else row['observed_at_s']
        arrived=observed+row['arrival_latency_s'] if is_token else row['arrived_at_s']
        expiry=row['valid_until_s']
        text(svg,40,y+5,row['id'],'label')
        svg.append(f'<line x1="{x(observed)}" x2="{x(expiry if expiry is not None else 120)}" y1="{y}" y2="{y}" stroke="#b7c9de" stroke-width="4"/>')
        svg.append(f'<circle cx="{x(observed)}" cy="{y}" r="5" fill="#1879ad"/>')
        svg.append(f'<path d="M{x(arrived)-6},{y-6} l12,0 l0,12 l-12,0 Z" fill="#d18a19"/>')
        if expiry is not None:
            svg.append(f'<line x1="{x(expiry)}" x2="{x(expiry)}" y1="{y-9}" y2="{y+9}" stroke="#bd4258" stroke-width="3"/>')
    text(svg,40,475,'Blue: observed   Gold: arrived   Red bar: exclusive validity end. Late history arrives already expired.','small')
    literal=book['literal_checks']
    text(svg,40,517,f"Saved signal at start65.5s: {literal['start_temperature_K']:.6f}K",'label')
    text(svg,40,548,f"Effective completion97.5s: {literal['completion_temperature_K']:.6f}K; first record at98s",'label')
    text(svg,40,579,f"Saved signal at delivery98s: {literal['arrival_temperature_K']:.6f}K; never substituted for completion",'label')
    text(svg,40,615,'Historical private physical source max step1s; exact saved-point adapter. No new numerical qualification or gain.','small')
    svg.append('</svg>');(output/'observation-timing.svg').write_text('\n'.join(svg)+'\n',encoding='utf-8',newline='\n')

    svg=start('Nonfixed evidence: authority and carried provenance',690)
    text(svg,40,75,f"{len(profile['registry']['entity_ids'])} shared entities | {sum(s['kind']=='fixed_sensor' for s in profile['registry']['sources'])} sparse fixed sources | {len(profile['models'])} declared instrument models",'small')
    svg.append('<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#657e9b"/></marker></defs>')
    def box(x,y,w,h,lines,fill='#fff'):
        svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="#b7c7dc"/>')
        for n,line in enumerate(lines):text(svg,x+17,y+28+n*23,line,'label' if n==0 else 'small')
    def arrow(x1,y1,x2,y2,dash=False):
        style=' stroke-dasharray="7 5"' if dash else ''
        svg.append(f'<path d="M{x1},{y1} L{x2},{y2}" stroke="#657e9b" stroke-width="2" fill="none" marker-end="url(#arrow)"{style}/>')
    box(40,120,300,116,['Declared asset/history/manual claims','Original observed/arrival/expiry','Unknown and negative remain claims','No private-world input'])
    box(40,270,300,105,['Typed fixture completion','Status + qualification + coverage','Positive actual interval + latency','Not M1 work or verified22 execution'])
    box(40,410,300,105,['PRIVATE saved plant source','Signal whitelist; exact completion point','Bias/noise/seed and source SHA audit','Historical1s physical execution'], '#fff1e9')
    box(420,150,310,105,['Report/completion producer17','Declared public quality/provenance','Private realization is kept separate','Inspection changes information only'])
    box(420,375,310,128,['PRIVATE operator/audit files','Raw planned / effective / sample time','Signal + draw + physical source IDs','CLI receipt / input SHA / execution ID','Never dispatcher snapshot'], '#fff1e9')
    box(820,150,335,105,['Evidence ledger14 / snapshot(t)','Only observed AND arrived records','Exclusive expiry; original age','Correlation is not independence'])
    box(820,315,335,105,['Decision-side plain data','Static registry + received records','Public models are declared assumptions','Risk18 and action23 are deferred'])
    box(820,475,335,105,['Copy arrives before alarm root','copy-first at30s; alarm-later at80s','Carried origin retained before parent','No future chain lookup'])
    arrow(340,170,420,190);arrow(340,318,420,225);arrow(340,450,420,245,True)
    arrow(730,195,820,195);arrow(575,255,575,375,True);arrow(990,255,990,315);arrow(990,475,990,420)
    text(svg,40,560,f"At98s: {len(saved['arrived']['records'])} received records; {len(saved['arrived']['current_record_ids'])} current, no independent-sample count.",'small')
    text(svg,40,601,'Solid: declared/public path. Dashed: private production/audit path; authorization precedes private I/O.','small')
    text(svg,40,638,'Engineering fixture only. Zero registered trials, model calls or training calls. No repair, field calibration or policy benefit.','small')
    svg.append('</svg>');(output/'source-authority.svg').write_text('\n'.join(svg)+'\n',encoding='utf-8',newline='\n')
