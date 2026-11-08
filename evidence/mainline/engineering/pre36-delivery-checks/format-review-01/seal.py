"""Seal the narrow saved-byte review; perform no project work."""
from pathlib import Path
import hashlib
import json

OUT=Path(__file__).resolve().parent
sha=lambda raw:hashlib.sha256(raw).hexdigest()
assert not (OUT/'manifest.json').exists()
result=json.loads((OUT/'result.json').read_bytes())
assert result['status']=='PASS_NARROW_FORMAT_BYTE_PRESERVATION' and result['check_count']==123
assert result['review_members']==84 and len(result['archives'])==5
assert 'AssertionError: original failed terminal not relabelled pass' in (OUT/'review-01.log').read_text(encoding='utf-8-sig')
correction={'classification':'REVIEWER_ASSERTION_LABEL_CORRECTION_ONLY','original_script':'review-01.py','original_log':'review-01.log','correction':'Original refusal is REFUSED_DELIVERY with source9b14 and exit1, rather than a generic FAIL string; verify exact original fields.','passing_script':'review.py','passing_log':'review-02.log','new_project_calls':0,'root_refusal_record_unchanged':True}
(OUT/'reviewer-correction.json').write_text(json.dumps(correction,indent=2)+'\n',encoding='utf-8')
files=[]
for path in sorted(OUT.iterdir()):
    if path.is_file() and path.name not in {'manifest.json','seal-verification.json'}:
        raw=path.read_bytes();files.append({'path':path.name,'sha256':sha(raw),'bytes':len(raw)})
manifest={'schema':'aegisdc-independent-format-review-manifest-v1','source':result['source'],'refused_source':result['refused_source'],'files':files,'excluded':['manifest.json (self)','seal-verification.json (post-seal proof)','runtime caches (none declared)']}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
for row in json.loads((OUT/'manifest.json').read_bytes())['files']:
    raw=(OUT/row['path']).read_bytes();assert sha(raw)==row['sha256'] and len(raw)==row['bytes']
proof={'status':'PASS','artifacts':len(files),'manifest_sha256':sha((OUT/'manifest.json').read_bytes()),'project_calls':0}
(OUT/'seal-verification.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
print(json.dumps(proof))
