from pathlib import Path
import hashlib,json,subprocess
root=Path('.')
dest=root/'evidence/mainline/audits/39a-review-20261109/format-01'
dest.mkdir(exist_ok=False)
record=subprocess.run(['git','diff','HEAD^','HEAD','--check','--','evidence/mainline/audits/39a-review-20261109'],capture_output=True)
(dest/'original-check.log').write_bytes(record.stdout+record.stderr)
classified=[]
for path in sorted((root/'evidence/mainline/audits/39a-review-20261109').rglob('*')):
 if not path.is_file() or dest in path.parents:continue
 data=path.read_bytes()
 if b'\r\n' not in data:continue
 for line in data.splitlines():
  if line.endswith((b' ',b'\t')):raise ValueError('True trailing whitespace needs separate classification: '+str(path))
 classified.append({'path':path.as_posix(),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'classification':'EXACT_ORIGINAL_CRLF_ONLY_NO_TRAILING_SPACES'})
attrs=root/'.gitattributes'
with attrs.open('a',encoding='utf-8',newline='\n') as f:
 f.write('\n# Ticket39a original reviewer CRLF records; exact bytes retained\n')
 for row in classified:f.write(row['path']+' -text whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol\n')
summary={'classification':'ORIGINAL_RECORD_FORMAT_CORRECTION_NOT_A_SCIENTIFIC_FAILURE','original_delivery':'1a224179','first_check_returncode':record.returncode,'failure_log':'original-check.log','members':classified,'explanation':'Original reviewer Windows CRLF bytes already preserved by evidence/** -text. Classify only these exact CRLF originals; no source bytes changed and no arbitrary hash failure waived.'}
(dest/'classification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'original_check_exit':record.returncode,'exact_CRLF_members':len(classified),'original_bytes_unchanged':True}))
