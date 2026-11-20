"""Fresh detached checkout and finished-study identity checks; no project code or model imports."""
import hashlib
import json
from pathlib import Path
import posixpath
import re
import subprocess
import sys

PK='docs/mainline/v6-native-method-study-v1'
LP='docs/mainline/v6-native-research-launch-v1'
G='docs/mainline/authorizations/v6-native-method-study-v1.json'
BASE='69bc0a52677d541e5726db1a919b743287887ca5'
AUTH='288c325fcba196c0eab3426a0e10730d13d77bd0'
MH='59080339a1846f242e0b8664e80a59b91ac623c768010ad1652e7d648c3b3301'
def need(test,reason):
    if not test:raise ValueError(reason)
def sha(data):return hashlib.sha256(data).hexdigest()
def read(path):return json.loads(path.read_bytes())
def digest(value):return sha(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode())


def main(tree, received, output):
    def git(*args):return subprocess.check_output(['git','-C',str(tree),*args])
    def blob(rev,path):return git('cat-file','blob',rev+':'+path)
    rev=git('rev-parse','HEAD').decode().strip()
    need(not git('status','--porcelain','--untracked-files=no'),'Dirty verification checkout')
    changed=git('diff','--name-only',BASE,rev).decode().splitlines()
    allowed={'README.md','docs/WORKSPACE.md','docs/MAINLINE.md','docs/current-research.json','docs/mainline/progress.json',
             'docs/mainline/master-roadmap.md',LP+'/acceptance-20261120.json',G}
    need(all(n in allowed or n.startswith(PK+'/') for n in changed),'Unapproved science/protocol/history edits')
    files={};targets=set()
    for n in changed:
        data=(tree/n).read_bytes()
        need(data==blob(rev,n),'Fresh file differs: '+n)
        files[n]=dict(sha256=sha(data),bytes=len(data),git_blob=git('rev-parse',rev+':'+n).decode().strip())
        if n.endswith('.md') and (n.startswith(PK+'/') or n=='docs/mainline/master-roadmap.md'):
            for url in re.findall(r'\[[^\]]*\]\(([^)]+)\)',data.decode()):
                path=url.split('#')[0]
                if path and not re.match(r'[a-z]+:',path):
                    target=posixpath.normpath(posixpath.join(posixpath.dirname(n),path));git('cat-file','-e',rev+':'+target);targets.add(target)
    doc=PK+'/result.json';r=read(tree/doc);m=read(tree/LP/'research-manifest.json');g=read(tree/G)
    need(sha(blob(BASE,LP+'/research-manifest.json'))==sha(blob(rev,LP+'/research-manifest.json'))==r['manifest_sha256']==MH,'Manifest drift')
    need(blob(rev,G)==blob(AUTH,G) and git('diff-tree','--no-commit-id','--name-only','-r',AUTH).decode().splitlines()==[G],'Authorization was not isolated')
    need(g['schedule_sha256']==digest(m['groups']) and g['budget_sha256']==digest(m['budget']) and g['uses']==1 and g['decision']=='APPROVE_ONE_LAUNCH'
        and g['purpose']==m['purpose'] and g['launcher_tree']==m['launcher_tree'] and g['native_source_tree']==m['native_source_tree']
        and g['python_sha256']==m['python']['sha256'] and g['activity_root']==m['activity_root'] and g['manifest_sha256']==MH
        and g['acceptance_sha256']==m['acceptance_sha256'] and r['control']['grant_digest']==digest(g),'Grant binding differs')
    need((received/'study/admission.json').read_bytes()==(received/'consume/consumption.json').read_bytes() and
         r['control']['accepted_proof']==read(received/'study/admission.json'),'Consumption proof differs')
    x=read(received/'retrieval.json')
    for folder,key in [('study','study_files_sha256'),('study','per_job_files_sha256'),('consume','consumption_sha256'),('control','controller_files_sha256')]:
        for n,h in x[key].items():need(sha((received/folder/n).read_bytes())==h,'Fetched file differs: '+n)
    need(r['preserved']['official_status_sha256']==sha((received/'official-status.json').read_bytes()) and r['preserved']['retrieval_sha256']==sha((received/'retrieval.json').read_bytes()),'Receipt drift')
    projected=[json.loads(line) for line in (received/'actual-stages.jsonl').read_bytes().splitlines()]
    need(len(projected)==len(r['arms'])==85,'Stage denominator drift')
    slots=[(group['condition'],arm,group['arm_inputs'][arm]) for group in m['groups'] for arm in group['fixed_order']]
    summary=read(received/'official-status.json');count=summary['counts']
    need(r['account']['counts']==count and r['account']['retries']==0 and r['account']['not_executed']==summary['not_executed'],'Public status accounting differs')
    need(r['frozen_budget']==m['budget'] and r['account']['job_reservations']<=17 and r['account']['reserved_cpu_s']<=2040
         and count['started']<=85 and count['known_decisions']<=1700 and count['manual_issues']<=216,'Budget overrun')
    native_count=0;scored=0;processes=set()
    for (c,a,ids),u,stage in zip(slots,r['arms'],projected,strict=True):
        key=c+'-'+a
        need(key==u['unit']==stage['unit'] and u['expected_input_sha256']==ids['complete_call'],'Scheduled identity differs')
        if u.get('native_return'):
            ret=u['native_return'];need(ret['full_input']==ids['complete_call'] and ret['source_tree']==m['native_source_tree'] and
                 ret['native_sha256']==stage['native_sha256']==u['native_sha256'],'Returned native identity differs')
            work=u['actual_stages']['work_records']
            need(len(work)==ret['manual_issues'] and len(stage['decisions'])==ret['internal_policy_calls'] and
                [[d[2],d[0]] for d in stage['decisions'] if d[2] is not None]==[[t['id'],t['issued_at_s']] for t in work],
                'Saved actual stages and returns differ: '+key)
            native_count+=1
        if u['process_account']['known_start']:
            proc=(u['process_account'].get('pid'),u['process_account'].get('start_ns'))
            need(proc not in processes and all(value is not None for value in proc),'Repeated process identity')
            processes.add(proc)
        if u['score']:
            path=received/'study/jobs'/c/'arms'/key/'score.json'
            raw=read(path);need(sha(path.read_bytes())==u['score_sha256'] and u['score']['questions']==raw['questions'] and
                u['score']['service']=={k:raw['service'][k] for k in ('balance','rate')} and
                u['score']['resources']=={k:raw['resources'][k] for k in ('balance','rate','admission','actual_components')} and
                u['semantic_sha256']==raw['semantic_sha256'],'Published score differs from sealed score: '+key)
            scored+=1
    need(native_count==count['returned'] and len(processes)==count['started'],'Actual run counts differ')
    jobs=r['jobs'];job_ids=[j['job_id'] for j in jobs if j['job_id']]
    need(len(job_ids)==len(set(job_ids)),'Reused scheduler identity')
    previous_end=None
    for job in jobs:
        if not job.get('committed'):continue
        d=job['scheduler_accounting']
        need(d[0]==job['job_id']==job['terminal']['job'] and d[3:5]==['COMPLETED','0:0'] and d[6]=='1' and d[7]=='1G'
                and d[12]=='00:02:00','Terminal allocation differs')
        need(previous_end is None or previous_end<=d[10],'Jobs overlap')
        previous_end=d[11]
        claim=job['allocation_claim']['allocation']
        need(claim['gpus']==0 and claim['cpus']==1 and claim['seconds']==120 and claim['requeue']==claim['restart']==0,'Allocation drift')
    if r['status']=='SEALED_FULL_PANEL':
        need(len(jobs)==17 and all(j['committed'] for j in jobs) and native_count==scored==85 and count['known_decisions']==1700 and
             all(q['consistency'] for q in r['official_panel']['rows']) and not count['unknown'] and not count['unknown_issues']
             and not r['account']['not_executed'] and not r['halt'],'Sealed status contradicts evidence')
        panel=received/'study/jobs/C17/panel.json';need(read(panel)==r['official_panel'] and sha(panel.read_bytes())==read(received/'study/finished.json')['panel_sha256'],'Official panel identity differs')
        need(all(v['planned']==17 for v in r['official_panel']['claims'].values()),'Contrast denominators')
    else:need(r['halt'] is not None and r['official_panel'] is None,'Missing stopped-suffix identity')
    pg=read(tree/'docs/mainline/progress.json')
    need(pg['current_milestone']=='STOP_AT_NATIVE_STUDY_CONSOLIDATED_REVIEW' and not pg['active_implementations']
         and pg['v6_native_study_v1']['grant_consumed'] and pg['v6_native_study_v1']['user_acceptance_pending'],'Final review gate differs')
    preserved={n:sha(blob(rev,n)) for n in ['tests/fixtures/39c-business-record-replay-57.json','docs/mainline/39c-business-record-replay-contract-57.md','evidence/mainline/engineering/39c-development/slice-57/result.json']}
    for n,h in preserved.items():need(sha(blob(BASE,n))==h,n)
    proof=dict(schema='aegisdc-native-study-static-integrity-v1',content_revision=rev,baseline=BASE,approval_revision=AUTH,
        final_manifest_sha256=MH,files=files,links=sorted(targets),arm_identities_checked=85,verified_distinct_subprocesses=len(processes),
        validated_native_returns=native_count,saved_scores=scored,serial_jobs=len(job_ids),source_receipt_sha256=sha((received/'retrieval.json').read_bytes()),
        current_panel_sha256=r['preserved']['sealed_panel_sha256'],slice57_sha256=preserved,
        archived_results_protocols_models_and_gates_preserved=True,new_scientific_calls_in_integrity_checks=0)
    with output.open('x',encoding='utf-8',newline='\n') as stream:json.dump(proof,stream,indent=2,ensure_ascii=False);stream.write('\n')
    print('Fresh files',len(files),'links',len(targets),'arm identities',len(slots),'native returns',native_count,'scores',scored,'jobs',len(job_ids))


if __name__=='__main__':main(*map(Path,sys.argv[1:4]))
