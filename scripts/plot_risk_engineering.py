"""SVGs derived only from saved risk engineering output."""
from hashlib import sha256
from html import escape
import json


def text(x,y,value,size=15,color='#24405c',bold=False):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{"bold" if bold else "normal"}">{escape(str(value))}</text>'


def base(raw,title,subtitle,width,height):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        f'<title>{escape(title)}</title><metadata>Saved data SHA256 {sha256(raw).hexdigest()}</metadata>',
        '<rect width="100%" height="100%" fill="#f7f9fc"/><g font-family="Arial,sans-serif">',
        text(34,40,title,25,bold=True),text(34,68,subtitle)]


def encode(rows):return ('\n'.join(rows+['</g></svg>'])+'\n').encode('utf-8')


def render(directory):
    raw=(directory/'check-results.json').read_bytes();data=json.loads(raw);last=data['results'][-1]
    rows=base(raw,'Joint service accounting | declared 2 s law',
        'Public two-report belief at 12 s; normalized service is not FLOP/s or site-calibrated capacity',1100,515)
    series=[('Offered work','offered_service_unit_s','#617991'),('Delivered work','delivered_service_unit_s','#007b9c'),
        ('Unserved work','unserved_service_unit_s','#b45319'),('Fractional deficit time','service_deficit_time_s','#8448a4')]
    for index,(label,key,color) in enumerate(series):
        y=120+index*78;value=last['full_horizon_service'][key]['value']
        rows+=[text(34,y+22,label,17,bold=True),f'<rect x="280" y="{y}" width="{value/2.5*620:.3f}" height="29" fill="{color}"/>',
            text(920,y+21,f"{value:.6f} "+('s' if key=='service_deficit_time_s' else 'service-unit s'))]
    rows += [text(34,455,'The first three rows share work units. Deficit time has a different denominator and stays separate.'),
        text(34,484,'Known joint outcomes are counted once per time window; unmodeled domain risks remain unknown.') ]
    accounting=encode(rows)
    rows=base(raw,'Eight-domain risk questions | knowledge and action boundary',
        'Two finite conditional questions; six unmodeled probabilities with conditional impacts and professional referrals',1200,680)
    labels={'cooling':'Cooling / immersion','power':'Power support','backup-support':'Backup / common supply',
        'it-dependence':'Compute + network + storage','control-uncertainty':'Control / sparse evidence','access-and-leak':'Leakage / safe access',
        'people-and-tools':'People / tools / timing','room-boundary':'Room / thermal boundary'}
    for index,q in enumerate(last['questions']):
        y=105+index*60;finite=q['quantification']=='FINITE_CONDITIONAL_LAW'
        rows += [f'<rect x="34" y="{y}" width="1132" height="48" rx="5" fill="{"#e0eef2" if finite else "#e9edf2"}"/>',
            text(48,y+20,labels[q['id']],17,bold=True),
            text(435,y+20,('P = %.6f'%q['probability']['value']) if finite else 'P unknown; conservative impact bounds',16),
            text(48,y+39,q['immediate_service_effect'].replace('_',' ').lower(),13),
            text(840,y+29,'Defer / professional referral',15)]
    rows += [text(34,624,'Planning capability and current reports are checked. Dynamic execution and operation effects require later gates.'),
        text(34,653,'Public frame + declared assumptions → belief → joint consequences. No private state or physical action is consumed.') ]
    return {'consequence-accounting.svg':accounting,'domain-risk-map.svg':encode(rows)}
