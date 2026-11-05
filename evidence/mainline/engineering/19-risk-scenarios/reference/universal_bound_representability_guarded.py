from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
import json,sys,copy,math,subprocess
out=Path('.work/19-spec-final-01').resolve();root=out.parents[1];pin='1939cb2ff375f7a0632a0a05ada68ae98afbdc1a';sys.path.insert(0,str(out/'final-export/src'))
paths=subprocess.check_output(['git','ls-tree','-r','--name-only',pin,'src','configs'],cwd=root,text=True).splitlines()
def guard():
 hashes={}
 for name in paths:
  raw=(out/'final-export'/name).read_bytes();assert raw==subprocess.check_output(['git','show',pin+':'+name],cwd=root);hashes[name]=sha256(raw).hexdigest()
 return hashes
before=guard()
from aegis_dc.risk_scenarios import assess_risks
f=json.loads((out/'public-frame.json').read_bytes());m=json.loads((out/'final-export/configs/full-facility-belief-model-v1.json').read_bytes());base=json.loads((out/'final-export/configs/full-facility-risk-scenarios-v1.json').read_bytes());rows=[]
for upper in [.3,math.nextafter(.3,math.inf)]:
 c=copy.deepcopy(base);c['demand'][0]['rate']=.1;c['demand'][1]['rate']=.2
 for q in c['questions']:q['consequence_bounds']['unserved_service_unit_s']['interval']=[0,upper]
 try:assess_risks(f,m,c);result=dict(status='ACCEPTED')
 except ValueError as e:result=dict(status='REJECTED',reason=str(e))
 rows.append(dict(upper=upper,**result))
after=guard();assert before==after;total=F(.1)+F(.2)
packet=dict(source=pin,exact_offered=str(total),exact_total_numerator_significant_bits=total.numerator.bit_length(),rows=rows,source_before=before,source_after=after,source_unchanged=True)
(out/'universal-bound-representability-guarded.json').write_text(json.dumps(packet,indent=2)+chr(10),encoding='utf-8');print(json.dumps({k:v for k,v in packet.items() if k not in ['source_before','source_after']}))
