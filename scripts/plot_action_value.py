"""Draw data-bound figures from saved public action-value results."""
from hashlib import sha256
from html import escape
import json

def render(directory):
    raw=(directory/'check-results.json').read_bytes();data=json.loads(raw);identity=sha256(raw).hexdigest()
    out=['<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="650" viewBox="0 0 1120 650"><metadata>Saved data SHA256 '+identity+'</metadata>',
        '<rect width="1120" height="650" fill="#f7f9fc"/><style>text{font-family:Arial,sans-serif;fill:#162b42}.h{font-size:23px;font-weight:bold}.s{font-size:15px}</style>',
        '<text x="30" y="38" class="h">Information and intervention | independent finite action tree</text>',
        '<text x="30" y="66" class="s">100 s declared horizon · inspection 10 s · intervention 20 s · sensitivity 0.8 / specificity 0.9</text>']
    colors=['#657992','#007b9c','#8448a4'];labels=['Defer','Direct intervention','Inspect then act if positive']
    panels=[('service_deficit_time_s','Expected service-deficit time',100,'s'),('person_s','Expected personnel occupation',30,'person-s')]
    for panel,(quantity,title,maximum,unit) in enumerate(panels):
        top=115+panel*250;out.append(f'<text x="30" y="{top}" class="h">{escape(title)}</text>')
        for group,row in enumerate(data['independent_cases']):
            left=45+group*365;prior=row['prior_fault']
            out.append(f'<text x="{left}" y="{top+28}" class="s">Prior impairment P = {prior}</text>')
            for j,result in enumerate(row['result']['question_values'][0]['alternatives']):
                value=result['expected'][quantity]['value'];y=top+48+j*42
                out.append(f'<rect x="{left}" y="{y}" width="{value/maximum*225:.3f}" height="24" fill="{colors[j]}"/>')
                out.append(f'<text x="{left+233}" y="{y+18}" class="s">{value:.2f} {unit}</text>')
    for i,(label,color) in enumerate(zip(labels,colors)):
        x=30+i*350;out.append(f'<rect x="{x}" y="602" width="18" height="18" fill="{color}"/><text x="{x+28}" y="617" class="s">{label}</text>')
    out.append('<text x="30" y="644" class="s">Separate units and axes. This validates a stated law, not facility method gain or field calibration.</text></svg>')
    architecture=['<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="390" viewBox="0 0 1120 390"><metadata>Saved data SHA256 '+identity+'</metadata>',
        '<rect width="1120" height="390" fill="#f7f9fc"/><style>text{font-family:Arial,sans-serif;fill:#162b42}.h{font-size:23px;font-weight:bold}.b{font-size:15px}</style>',
        '<text x="30" y="40" class="h">Current evidence → branch law → separate value accounts</text>']
    boxes=[(30,'Public current inputs',['18 belief / 19 joint outcomes','Common exogenous service demand','Nominal qualifications and reports','Declared availability and budgets']),
        (400,'Finite alternatives',['Defer / direct / inspect then act','Loss continues during travel / test','Report latency before branch action','Action and residual capacities']),
        (770,'Predicted values and limits',['Service / person / tool / cost','All supported branches fit budget','Unknowns and conflicts retained','No physical action or verified gain'])]
    for x,title,lines in boxes:
        architecture.append(f'<rect x="{x}" y="95" width="320" height="205" fill="white" stroke="#aabbce"/><text x="{x+14}" y="125" class="b" font-weight="bold">{title}</text>')
        architecture += [f'<text x="{x+14}" y="{161+i*30}" class="b">{line}</text>' for i,line in enumerate(lines)]
    architecture += ['<path d="M350 195H400M720 195H770" stroke="#007b9c" stroke-width="3"/>',
        '<text x="30" y="338" class="b">Eight-domain synthetic V6 context persists. Six unmodeled domain probabilities stay unknown.</text>',
        '<text x="30" y="370" class="b">Actual workforce, inspection results and intervention are separate21/22/23 execution gates.</text></svg>']
    return {'value-comparison.svg':('\n'.join(out)+'\n').encode(),'decision-boundary.svg':('\n'.join(architecture)+'\n').encode()}
