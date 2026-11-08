"""Local text/Git/integrity metadata only. No scientific metric calculations."""
from pathlib import Path
import hashlib,json,re,subprocess
ROOT=Path(r"C:\Users\Donson\Documents\ChatGPT\Renly")
OUT=Path(__file__).resolve().parent
BASE='8e32a8075fb86de0818f8149d4e47cdae3170ad9'
SOURCE='f73c57f8806dcc6e23d510e83391b0f46677b6cc'
REVIEWED_SCIENCE='2f3fb67f6847b94c24f8d50b95298dd4b057dd6c'
checks=[]
def ck(ok,label):checks.append({'label':label,'passed':bool(ok)});assert ok,label
def git(*a):return subprocess.check_output(['git','-C',str(ROOT),*a])
def blob(p,rev=SOURCE):return git('cat-file','blob',rev+':'+p)
def text(p,rev=SOURCE):return blob(p,rev).decode('utf-8-sig')
def doc(p,rev=SOURCE):return json.loads(blob(p,rev))
def line(raw,needle):return next(i for i,v in enumerate(raw.splitlines(),1) if needle in v)
sha=lambda raw:hashlib.sha256(raw).hexdigest()
observed_head=git('rev-parse','HEAD').decode().strip()
progress=doc('docs/mainline/progress.json');response=text('docs/reviews/20261109-user-review/response.md')
ck(progress['current_ticket']=='39a' and progress['status']=='active','39a current and overall objective active')
ck(progress['agent_stage']=='structured_AI_factor_eligible_coverage_preparation_first','AI eligibility distinct from coverage preparation priority')
ck(progress['research_trials']['attempts']==180 and progress['research_trials']['remaining_registered_attempts']==0,'old registered counts read as unchanged metadata, not recomputed')
ck('32次草案不是已获执行额度' in response and '原180次结果' in response and '不重跑' in response,'future budget not inherited from old estimate or old outcomes')
ck(not git('diff','--name-only',REVIEWED_SCIENCE,SOURCE,'--','src/aegis_dc','configs').strip(),'scientific runtime/config bytes unchanged after user-review scientific cutoff')
ck(git('diff','--name-only','2dfe5537e4f95fa605f325b060ef32223dafb4f6',SOURCE,'--','src/aegis_dc','configs').decode().splitlines()==['src/aegis_dc/verified_closure.py'],'pre36 audit reused with its one explicitly accepted closure correction')
ck(git('rev-parse','pre-meeting-20261103^{}').decode().strip()=='076d9aa15c5bc99a5b7985f296e15543b7b0f3d7','premeeting original identity retained')
ck(blob('docs/mainline/30-comparison-protocol-v1.json')==blob('docs/mainline/30-comparison-protocol-v1.json',REVIEWED_SCIENCE),'original protocol source bytes preserved')
issue_dir='.scratch/full-facility-mainline/issues/'
issue_files=git('ls-tree','-r','--name-only',SOURCE,'--',issue_dir).decode().splitlines()
tickets={}
for p in issue_files:
    match=re.match(re.escape(issue_dir)+r'([0-9]+[a-d]?)-',p)
    if not match:continue
    body=text(p);status=re.search(r'\*\*Status:\*\*\s*([^\n]+)',body).group(1).strip();blocked=re.search(r'\*\*Blocked by:\*\*\s*([^\n]+)',body).group(1).strip()
    tickets[match.group(1)]={'path':p,'status':status,'blocked_by':blocked,'sha256':sha(blob(p))}
for key,dependencies in [('39a','38'),('39b','39a'),('39c','39a'),('39d','39b, 39c'),('39','38, 39b, 39c, 39d')]:ck(tickets[key]['blocked_by']==dependencies,'real source dependency '+key)
ck(tickets['39a']['status']=='claimed' and all(tickets[k]['status']=='ready-for-agent' for k in ['39b','39c','39d','39','40','41','42']),'only39a active; future work not accepted or falsely deferred')
ck(all(tickets[f'{i:02}']['status']=='resolved' for i in range(1,39)),'1–38 resolved only within their recorded historical acceptance scopes')
map_text=text('.scratch/full-facility-mainline/map.md')
ck(all('|'+k+'|' in map_text for k in ['39a','39b','39c','39d']),'new prerequisites represented in real task graph')
scope39c=text(issue_dir+'39c-business-endpoints-and-closure.md');scope39d=text(issue_dir+'39d-timescales-parameter-and-numeric-scope.md')
ck('不重标原180次的未测端点' in scope39c and '提前量' in scope39c and '删失规则' in scope39c,'business endpoint definitions prospective, missing/censoring explicit')
ck('有限数值资格不升级为普适误差界' in scope39d and '只通过Slurm执行' in scope39d,'new time/numerical scope remote and finite')
oldreadme=text('README.md');oldstate=doc('docs/current-research.json');cli=text('src/aegis_dc/__main__.py')
ck(oldstate['current_primary_ticket']=='32' and 'docs/current-research.json' in cli,'fixed-source stale current-state finding anchored to actualCLI consumer')
findings=[
 {'id':'S39A-01','priority':'P2','origin':'Inherited current-state drift, present at fixed f73','path':'docs/current-research.json','line':line(text('docs/current-research.json'),'"current_primary_ticket"'),'related':'src/aegis_dc/__main__.py:51','issue':'CLI status reads obsolete32/no materialized confirmation/old AI-stage metadata while authoritative progress is39a with180 completed.','rule':'AGENTS current-ticket/live-source rule; docs/agents/issue-tracker.md current lifecycle truth.'},
 {'id':'S39A-02','priority':'P2','origin':'Old README instructions conflicting with newly applicable remote policy','path':'README.md','line':line(oldreadme,'python -m aegis_dc simulate'),'issue':'Operational install/simulate/risk/verify examples lacked remote placement, and broad no-model wording conflated noLLM with finite numeric computation.','rule':'AGENTS Compute and storage; docs/agents/compute-storage.md Execution2–6.'},
 {'id':'S39A-03','priority':'P2','origin':'Old source link became misleading after accepted website update','path':'README.md','line':line(oldreadme,'线上快照'),'issue':'v11 online snapshot link points at the current180-run report route.','rule':'AGENTS preserve source/epoch distinctions; GLOSSARY engineering/reference and research-layer definitions.'}
]
working={p:(ROOT/p).read_bytes() for p in ['README.md','docs/current-research.json']}
newreadme=working['README.md'].decode('utf-8-sig');newstate=json.loads(working['docs/current-research.json'])
ck(newstate['current_primary_ticket']=='39a' and newstate['current_primary_ticket_assigned'] is True and newstate['active_tickets']==['39a'] and newstate['next_ready_unassigned']==[],'working current-state correction matches actual frontier and owner')
ck(newstate['agent_stage']==progress['agent_stage'] and newstate['rsi_gain']=='NOT_MEASURED' and newstate['original_registered_runs']==180 and newstate['new_research_trials_after_user_review']==0,'working metadata preserves eligibility/unmeasured effects and old-run source count')
ck('/liquid-cooling/history/20261103/report.bin' in newreadme and 'v11历史HTML下载' in newreadme,'working v11 source link correction')
ck('远端计算与存储规则' in newreadme and '不能自动改在本机运行' in newreadme and '没有训练或LLM调用' in newreadme and '仍进行数值计算' in newreadme,'working remote/LLM/numerical-computation distinction')
ck('历史验收范围' in newreadme and '39a跨阶段复核' in newreadme,'old M2 entry explicitly historical, current39a visible')
for p,raw in working.items():ck((ROOT/p).read_bytes()==raw,'small working metadata stable during read '+p)
policy_note=None
if '以下运行、安装及校验示例均在现有服务器执行；集群上须进入Slurm作业' in newreadme:
    policy_note='Narrow wording pending: distinguish login-node downloads/isolated setup/light inspection from Slurm computation; compute nodes are offline per compute-storage.'
nav=ROOT/'.work/user-review-20261109/commit-list.txt'
standards=['AGENTS.md','docs/agents/compute-storage.md','docs/agents/issue-tracker.md','docs/agents/domain.md','docs/MAINLINE.md','GLOSSARY.md','docs/adr/0003-complete-facility-mainline.md','.scratch/full-facility-mainline/spec.md','docs/reviews/20261109-user-review/response.md']
result={'status':'PREPARATION_STANDARDS_FINDINGS_CORRECTED_IN_WORKING_METADATA_PENDING_FINAL_PIN','source':SOURCE,'requested_base':BASE,'observed_head':observed_head,'checks':checks,'check_count':len(checks),'initial_findings':findings,'working_metadata':[{'path':p,'sha256':sha(raw),'bytes':len(raw),'identity_scope':'CURRENT_WORKING_BYTES; pending committed final pin'} for p,raw in working.items()],'working_findings_disposition':'Three fixed-source entry/source problems corrected in inspected working metadata. No scientific acceptance of39a or future tickets implied.','wording_note':policy_note,'standards_sources':[{'path':p,'sha256':sha(blob(p))} for p in standards],'commit_navigation_sha256':sha(nav.read_bytes()),'metadata_commit_count':git('rev-list','--count',BASE+'..'+SOURCE).decode().strip(),'future_ticket_metadata':{k:tickets[k] for k in ['39a','39b','39c','39d','39','40','41','42']},'awaited':'Root final pin for38-row coverage/requirements tables and remote saved-data readout. No local numerical calculation or wholesale source export performed.','reviewer_activity':{'project_runs':0,'tests':0,'models':0,'physical_runs':0,'numeric_metric_recomputations':0,'browser':0,'dependencies_installed':0,'full_source_exports':0,'clones':0,'worktrees_created':0,'source_edits':0}}
(OUT/'metadata-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:result[k] for k in ['status','source','check_count','working_findings_disposition','wording_note','metadata_commit_count','awaited','reviewer_activity']}))
