import hashlib,io,json,pathlib,re,subprocess,time,urllib.request,zipfile
root=pathlib.Path.cwd();run_id=42548898914;expected='4f2977bb29ecb563601ae9aed5439729e6093477'
credential=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\n\n',capture_output=True,text=True,check=True)
secret=dict(line.split('=',1) for line in credential.stdout.splitlines() if '=' in line)['password']
opener=urllib.request.build_opener(urllib.request.ProxyHandler({'https':'http://127.0.0.1:7897'}))
def request(path):
 return opener.open(urllib.request.Request('https://api.github.com/repos/DonsonHH/AegisDC'+path,headers={'User-Agent':'AegisDC-checkpoint-readback','Authorization':'Bearer '+secret,'Accept':'application/vnd.github+json','Cache-Control':'no-cache'}),timeout=30)
with request('/actions/runs/'+str(run_id)+'?_='+str(time.time_ns())) as response:run=json.load(response)
if run['head_sha']!=expected or run['run_attempt']!=1:raise SystemExit('CI source or attempt differs')
with request('/actions/runs/'+str(run_id)+'/jobs?_='+str(time.time_ns())) as response:jobs=json.load(response)
print(json.dumps({'source':expected,'status':run['status'],'conclusion':run['conclusion'],'created_at':run['created_at'],'updated_at':run['updated_at'],'jobs':[{'name':job['name'],'status':job['status'],'started_at':job['started_at'],'steps':[{'name':step['name'],'status':step['status'],'conclusion':step['conclusion']} for step in job['steps']]} for job in jobs['jobs']]}))
if run['status']!='completed':raise SystemExit(0)
with request('/actions/runs/'+str(run_id)+'/logs') as response:raw=response.read()
out=root/'.work/39c-ci-evidence-02';out.mkdir(exist_ok=False)
(out/'logs.zip').write_bytes(raw)
record={'source_commit':expected,'run_id':run_id,'run_attempt':1,'status':run['status'],'conclusion':run['conclusion'],'zip_sha256':hashlib.sha256(raw).hexdigest(),'members':{},'suite_reports':[]}
with zipfile.ZipFile(io.BytesIO(raw)) as archive:
 for index,name in enumerate(archive.namelist()):
  if name.endswith('/'):continue
  data=archive.read(name);target=f'{index:02d}-'+pathlib.PurePosixPath(name).name
  (out/target).write_bytes(data);record['members'][name]={'local_file':target,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
  text=data.decode('utf-8','replace')
  for match in re.finditer(r'Ran (\d+) tests in ([0-9.]+)s',text):record['suite_reports'].append({'member':name,'discovered':int(match[1]),'wall_s':float(match[2]),'tail':text[match.start():match.start()+300]})
(out/'ci-record.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'saved':str(out),'suite_reports':record['suite_reports']}))
