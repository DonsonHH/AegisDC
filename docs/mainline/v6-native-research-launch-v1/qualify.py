"""Frozen, zero-facility verification. No live scheduler transport or real grant in the fixture domain."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
sys.modules['aegis_dc.plant']=None
from aegis_dc.native_compare_inputs import file_hash, read
from aegis_dc.native_compare_score import read_native, service
from patrol_rsi.contracts import digest
from v6_research import binding as B
from v6_research import control as C
from v6_research.native import verify_return
from v6_research.slurm import Slurm, current_allocation

REV='ab'*20
PREFIX='/git/ref/heads/donson/mainline-39c-endpoints'


def ensure(ok,message):
    if not ok:raise ValueError(message)


def literal_equal(actual, expected):
    if type(expected) is bool:return type(actual) is bool and actual==expected
    if type(expected) in (int,float):return type(actual) in (int,float) and actual==expected
    if type(expected) is list:return type(actual) is list and len(actual)==len(expected) and all(literal_equal(a,b) for a,b in zip(actual,expected))
    if type(expected) is dict:return type(actual) is dict and actual.keys()==expected.keys() and all(literal_equal(actual[k],v) for k,v in expected.items())
    return type(actual) is type(expected) and actual==expected


def rejection(fn):
    try:fn()
    except B.GateError as exc:return exc.code
    return 'UNEXPECTED_ALLOW'


def grant(rel):
    m=rel.manifest
    # Transcribed from the public authorization contract, not derived from a gate verdict.
    return dict(schema='aegisdc-single-use-reviewed-study-grant-v1',purpose='PUBLIC_LAUNCH_SURROGATE',
        decision='APPROVE_ONE_LAUNCH',grant_id='V6-native-method-study-v1',manifest_sha256=rel.sha,
        acceptance_sha256=m['acceptance_sha256'],protocol_revision=m['protocol_revision'],finite_publication=m['finite_publication'],
        published_launcher_revision=m['launch_source_revision'],launcher_tree=m['launcher_tree'],native_source_tree=m['native_source_tree'],
        python_sha256=m['python']['sha256'],schedule_sha256=digest(m['groups']),budget_sha256=digest(m['budget']),
        activity_root=m['activity_root'],uses=1,user_decision_reference='FROZEN_PUBLIC_REVIEW_FIXTURE_ONLY')


class Review(B.GitHubReview):
    def __init__(self,release,mutation=''):
        self.release=release;self.mutation=mutation;self.requests=[]
    def obtain(self,path):
        self.requests.append(path)
        if path==PREFIX:
            return dict(ref='refs/heads/donson/mainline-39c-endpoints',object=dict(type='commit',sha='bc'*20 if self.mutation=='head' else REV))
        name=path.removeprefix('/contents/').split('?')[0]
        ensure(path=='/contents/'+name+'?ref='+REV,'Unexpected review source request')
        if name==B.GRANT_PATH:
            if self.mutation=='absent':raise B.GateError('GRANT_ABSENT')
            g=grant(self.release)
            if self.mutation in ('manifest_sha256','activity_root','budget_sha256'):g[self.mutation]='wrong'
            if self.mutation=='purpose':g['purpose']=B.REAL
            raw=json.dumps(g,sort_keys=True).encode()
        else:
            ensure(name in (B.MANIFEST,B.ACCEPTANCE),'Unexpected source file')
            raw=(ROOT/name).read_bytes()
            if self.mutation=='acceptance' and name==B.ACCEPTANCE:raw+=b' '
        return dict(type='file',path=name,encoding='base64',content=base64.b64encode(raw).decode(),size=len(raw),
                    sha=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest())


def allocation(job,case):
    return dict(job=job,name='v6-study-'+case,cpus=1,mem_MiB=1024,seconds=120,nodes=1,partition='cu',
                restart=0,requeue=0,state='RUNNING',user='renly',gpus=0)


class Scheduler(Slurm):
    """Replace only Slurm and the final arm executable; run the actual gate, worker, reader and scorer."""
    def __init__(self,harness,site,mode):
        self.h=harness;self.site=site;self.mode=mode;self.jobs={};self.calls=[];self.extra={}
        self.command=self.transport
        self.pause=lambda _:None
    def transport(self,*argv):
        self.calls.append(list(argv))
        if argv[0]=='sbatch':
            case=argv[-1];jobdir=self.site.activity/'jobs'/case
            expected=['sbatch','--parsable','--hold','--no-requeue','--partition=cu','--nodes=1','--ntasks=1','--cpus-per-task=1',
                '--mem=1G','--time=00:02:00','--job-name=v6-study-'+case,'--chdir='+str(ROOT),
                '--output='+str(jobdir/'slurm-%j.out'),'--error='+str(jobdir/'slurm-%j.err'),str(HERE/'study.sbatch'),str(ROOT),self.h.release.sha,case]
            ensure(list(argv)==expected,'Unexpected Slurm submission arguments')
            ensure(not any(j['state'] in ('HELD','RELEASED') for j in self.jobs.values()),'Overlapping simulated jobs')
            job=str(910000+len(self.jobs)+1)
            self.jobs[job]={'case':case,'directory':str(jobdir),'state':'HELD','manifest':self.h.release.sha}
            return job
        if argv[:2]==('scontrol','release'):
            job=argv[-1];j=self.jobs[job]
            self.dispatch(job,j['case'],Path(j['directory']))
            return ''
        if argv[:4]==('scontrol','show','job','-o'):
            job=argv[-1];case=self.jobs[job]['case']
            return f'JobId={job} JobName=v6-study-{case} JobState=RUNNING NumCPUs=1 NumNodes=1 MinMemoryNode=1G AllocTRES=cpu=1,mem=1G,node=1 TimeLimit=00:02:00 UserId=renly(1) Requeue=0 Restarts=0 Partition=cu'
        if argv[0]=='sacct':
            job=argv[argv.index('-j')+1];j=self.jobs[job]
            return '' if j['state']=='RELEASED' else job+'|'+j['state']+'|'+('0:0' if j['state']=='COMPLETED' else '1:0')+'|1'
        if argv[0]=='squeue':
            ensure(argv[argv.index('-j')+1] in self.jobs,'Wrong lookup ID')
            return ''
        raise ValueError('Unregistered substitute transport')
    def replacement_child(self,case,arm,path,native):
        ensure(self.site.purpose==B.SURROGATE and self.h.parent in path.parents,'Unsafe surrogate workspace')
        ensure(native[0]==sys.executable and native[1:5]==['-B','-m','aegis_dc','simulate'],'Unexpected proposed native invocation')
        mode='copy'
        if self.mode=='J1' and case=='C02':mode='no-return'
        if self.mode=='J2':mode='missing-count'
        if self.mode=='J3' and arm=='H':mode='divergent-H'
        if self.mode=='H1':mode='cut-H5'
        ensure(case=='C01' or (case=='C02' and arm=='V' and mode=='no-return'),'Unplanned surrogate')
        self.h.starts.append([self.mode,case,arm,mode])
        ensure(len(self.h.starts)<=12,'Verification process budget')
        spec=self.h.freeze['saved_C01'][arm]
        original=self.h.original(arm) if mode!='no-return' else Path(self.h.freeze['old_private_output'])/spec['relative']
        return [sys.executable,'-I','-B',str(HERE/'replay_child.py'),str(original),str(path/'run'),mode,spec['run_sha256']]
    def dispatch(self,job,case,jobdir):
        ensure(self.jobs[job]['state']=='HELD' and self.jobs[job]['case']==case,'Surrogate double release')
        ensure((jobdir/'submitted.json').is_file() and not (jobdir/'worker-claim.json').exists(),'Release preceded job binding')
        self.jobs[job]['state']='RELEASED';self.calls.append(['release',case,job])
        rel=B.load_release(ROOT,self.h.release.sha)
        facts=current_allocation(self.transport,dict(SLURM_JOB_ID=job,SLURM_CPUS_PER_TASK="1",SLURM_MEM_PER_NODE="1024"))
        ensure(facts==allocation(job,case),"Scheduler allocation parse differs")
        if self.mode=='J4':
            live=C.snapshot(self.site,rel)
            self.extra['pre_halt']=dict(exact_starts=live['total_starts_exact'],possible_case=live['unresolved_jobs'][0],definite_suffix=len(live['not_executed']))
            def claim(c=case,a=facts):return C.claim_worker(self.site,rel,c,a)
            self.extra['rejections']=[rejection(lambda:claim(a=dict(facts,job='111'))),rejection(lambda:claim(a=dict(facts,cpus=2))),
                                    rejection(lambda:claim(c='C02'))]
            self.extra['gpu']=rejection(lambda:claim(a=dict(facts,gpus=1)))
            claim()
            self.extra['rejections'].append(rejection(claim))
            return
        record=C.worker(self.site,rel,case,facts,self.replacement_child)
        self.jobs[job]['state']='COMPLETED' if record['passed'] else 'FAILED'


class Harness:
    def __init__(self,parent,release,freeze):
        self.parent=parent;self.release=release;self.freeze=freeze;self.starts=[];self.originals={}
    def site(self,name):
        path=self.parent/'sites'/name
        path.mkdir(parents=True)
        return C.Site(path,B.SURROGATE)
    def journey(self,name):
        site=self.site(name);schedule=Scheduler(self,site,name);authority=Review(self.release)
        completed=C.start(site,self.release,authority,REV,schedule)
        ensure(not completed and (site.activity/'halt.json').exists(),'Expected one bounded non-success scenario')
        state=C.snapshot(site,self.release)
        ensure(len(state['rows'])==85 and state['research_arms_executed']==0,'Wrong denominator or purpose')
        C.once(site.shared/'surrogate-transport.json',dict(jobs=schedule.jobs,events=schedule.calls,review_requests=authority.requests))
        return site,schedule,state
    def original(self,arm):
        spec=self.freeze['saved_C01'][arm]
        path=Path(self.freeze['old_private_output'])/spec['relative']
        ensure(file_hash(path/'run.json')==spec['run_sha256'],'Retained original changed')
        saved_score=path.parent/'score.json'
        ensure(file_hash(saved_score)==spec['score_sha256'],'Historical score identity changed')
        score=read(saved_score)
        ensure(score['input_sha256']==spec['input_sha256'] and score['native_source']==spec['source_tree']
               and score['native_sha256']==spec['run_sha256'],'Historical saved identities differ')
        self.originals[arm]=dict(path=str(path),sha256=spec['run_sha256'],score_sha256=spec['score_sha256'],
                                 input_sha256=spec['input_sha256'],native_source_tree=spec['source_tree'])
        return path
    def A1(self):
        site=C.Site(B.SHARED,B.REAL)
        before=(os.path.lexists(site.activity),os.path.lexists(site.claim))
        ensure(before==(False,False),'Actual research or authority storage already exists')
        proc=subprocess.run([sys.executable,'-I','-B',str(ROOT/'scripts/v6_research_launch.py'),'start','--manifest-sha',self.release.sha],capture_output=True,text=True)
        ensure(proc.returncode==2 and before==(os.path.lexists(site.activity),os.path.lexists(site.claim)),'Unexpected CLI refusal side effect')
        return dict(error=json.loads(proc.stderr)['code'],real_submissions=0,production_consumptions=0)
    def A2(self):
        site=self.site('A2')
        errors=[rejection(lambda m=m:C.admit(site,self.release,Review(self.release,m),REV)) for m in
                ('absent','head','manifest_sha256','purpose','activity_root','budget_sha256','acceptance')]
        errors.append(rejection(lambda:B.load_release(ROOT,'0'*64)))
        clone=site.shared/'source-derivative'
        shutil.copytree(ROOT,clone)
        native=clone/'scripts/v6_research/native.py'
        with native.open('ab') as f:f.write(b'\n# fixture byte drift\n')
        errors.append(rejection(lambda:B.load_release(clone,self.release.sha)))
        m=deepcopy(self.release.manifest);m['python']['sha256']='0'*64
        raw=(json.dumps(m)+'\n').encode();(clone/B.MANIFEST).write_bytes(raw)
        errors.append(rejection(lambda:B.load_release(clone,B.raw_sha(raw))))
        ensure(not site.activity.exists() and not site.claim.exists(),'Failed authorization created state')
        return dict(errors=errors,submitted=0,consumed=0)
    def A3(self):
        existing=self.site('A3-existing');existing.activity.mkdir();sentinel=existing.activity/'keep';sentinel.write_bytes(b'original')
        refused=rejection(lambda:C.admit(existing,self.release,Review(self.release),REV))
        ensure(sentinel.read_bytes()==b'original','Overwrote earlier output')
        site=self.site('A3-race')
        def attempt(_):
            try:C.admit(site,self.release,Review(self.release),REV);return 'ok'
            except B.GateError as exc:return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,range(2)))
        ensure(all(x in ('ok','GRANT_CONSUMED') for x in results),'Unexpected race result '+str(results))
        state=C.snapshot(site,self.release)
        return dict(existing=refused,existing_consumed=int(existing.claim.exists()),concurrent_accepted=results.count('ok'),
            concurrent_refused=results.count('GRANT_CONSUMED'),replay=rejection(lambda:C.admit(site,self.release,Review(self.release),REV)),
            reservations=state['job_reservations'],rows=len(state['rows']))
    def J1(self):
        site,schedule,s=self.journey('J1');c=s['counts'];job=site.activity/'jobs/C01/arms'
        vh=[read(job/('C01-'+a)/'score.json') for a in ('V','H')]
        ensure(len({row['pid'] for row in s['rows'][:5]})==5 and s['total_decisions_exact'] is None,'Process isolation or unknown count lost')
        return dict(submissions=len(schedule.jobs),ordered=[x['case'] for x in schedule.jobs.values()],reserved_cpu_s=s['reserved_cpu_s'],
              started=c['started'],complete_returns=c['returned'],unreturned=c['unreturned'],known_decisions=c['known_decisions'],
              known_issues=c['manual_issues'],unknown_decisions=c['unknown'],unexecuted=len(s['not_executed']),
              vh_equal=vh[0]['semantic_sha256']==vh[1]['semantic_sha256'],retry=read(site.activity/'halt.json')['retry'])
    def J2(self):
        site,schedule,s=self.journey('J2');c=s['counts']
        ensure(s['total_decisions_exact'] is None and not c['missing_raw_returns'],'Malformed native count lost')
        return dict(submissions=len(schedule.jobs),started=c['started'],raw_returns=c['raw_returns'],complete_returns=c['returned'],
            known_decisions=c['known_decisions'],unknown_decisions=c['unknown'],unexecuted=len(s['not_executed']),
            score_called=(site.activity/'jobs/C01/arms/C01-V/score.json').exists())
    def J3(self):
        site,schedule,s=self.journey('J3');c=s['counts']
        h=next(row for row in s['rows'] if row['unit']=='C01-H')
        ensure('VH_MISMATCH' in h.get('error','') and h['score_present'],'Unexpected mismatch cause')
        return dict(submissions=len(schedule.jobs),started=c['started'],complete_returns=c['returned'],known_decisions=c['known_decisions'],
              known_issues=c['manual_issues'],unknown_decisions=c['unknown'],unexecuted=len(s['not_executed']),error='VH_MISMATCH')
    def J4(self):
        site,schedule,s=self.journey('J4')
        # Isolated read-only reconstruction of a prelaunch journal with no reliable start/return.
        separate=self.site('J4-journal');C.admit(separate,self.release,Review(self.release),REV)
        folder=separate.activity/'jobs/C01';folder.mkdir()
        C.once(folder/'reserved.json',dict(case='C01'))
        lost=C.snapshot(separate,self.release)
        job=folder/'arms';job.mkdir()
        (job/'events.jsonl').write_text(json.dumps(dict(unit='C01-V',event='BEFORE_LAUNCH',ns=1))+'\n')
        ambiguous=C.case_summary(C.case_rows(folder,'C01'))['uncertain_starts']
        traces=[dict(unit='C01-V',event='BEFORE_LAUNCH',ns=1),dict(unit='C01-V',event='STARTED',ns=2,pid=1),
                dict(unit='C01-V',event='COMPLETE_RETURN',ns=3,decisions=20),dict(unit='C01-D',event='BEFORE_LAUNCH',ns=4)]
        (job/'events.jsonl').write_bytes(('\n'.join(json.dumps(t) for t in traces)+'\n{"partial":').encode())
        damaged=C.snapshot(separate,self.release)
        supplementary=dict(pre_halt=schedule.extra['pre_halt'],gpu=schedule.extra['gpu'],
            unknown_submission_ids=lost['unknown_submission_ids'],lost_reserved_cpu_s=lost['reserved_cpu_s'],
            lost_confirmed_starts=lost['counts']['started'],torn_known=damaged['counts']['known_decisions'],
            torn_ambiguous=damaged['counts']['uncertain_starts'],torn_slots=len(damaged['rows']),torn_errors=bool(damaged['counts']['accounting_errors']))
        C.once(site.shared/'review-addendum-results.json',supplementary)
        ensure(supplementary==dict(pre_halt=dict(exact_starts=None,possible_case='C01',definite_suffix=80),gpu='ALLOCATION',
            unknown_submission_ids=['C01'],lost_reserved_cpu_s=120,lost_confirmed_starts=0,torn_known=20,torn_ambiguous=['C01-D'],
            torn_slots=85,torn_errors=True),'Unresolved accounting failed: '+str(supplementary))
        return dict(submissions=len(schedule.jobs),reserved_cpu_s=s['reserved_cpu_s'],confirmed_starts=s['counts']['started'],
            unresolved_job=s['unresolved_jobs'][0],suffix=len(s['not_executed']),ambiguous_marker=ambiguous[0],errors=schedule.extra['rejections'])
    def B1(self):
        rows=[dict(case=case,status='COMMITTED',started=5,returned=5,known_decisions=100,manual_issues=11,
            unknown=[],unknown_issues=[],uncertain_starts=[],reserved_cpu_s=120) for case in B.CASES]
        for i,c in enumerate(B.CASES):C.next_position(rows[:i],c)
        def changed(**fields):return rows[:15]+[dict(rows[15],**fields)]
        errors=[rejection(lambda:C.next_position(rows[:16],'C16')),rejection(lambda:C.next_position(changed(known_decisions=101),'C17')),
                rejection(lambda:C.next_position(changed(unknown=['C16-V']),'C17')),rejection(lambda:C.next_position(rows,'C18'))]
        ensure(rejection(lambda:C.next_position(changed(unknown_issues=['C16-V']),'C17'))=='PRIOR_UNRESOLVED','Unknown manual count admitted')
        return dict(first16=C.sum_jobs(rows[:16]),final17=C.sum_jobs(rows),errors=errors)
    def I1(self):
        folder=self.original('V');run,_,_=read_native(folder);scenario=read(folder/'scenario.json')
        def verify(r):return verify_return(self.release,'C01','V',r,scenario)
        verify(run)
        edits=[(['code_identity','files'],{}),(['code_identity','source_tree_sha256'],'0'*64),(['scenario_sha256'],'0'*64),
             (['inputs','dispatch_program','id'],'wrong'),(['inputs','business_program','id'],'wrong'),(['inputs','boundary_events'],[]),
             (['inputs','duration_s'],9),(['inputs','maximum_step_s'],0.02),(['inputs','action_commands'],['fixture']),
             (['inputs','work_requests'],['fixture'])]
        errors=[]
        for keys,value in edits:
            obj=deepcopy(run);ref=obj
            for k in keys[:-1]:ref=ref[k]
            ref[keys[-1]]=value
            errors.append(rejection(lambda:verify(obj)))
        return dict(valid=True,errors=errors)
    def H1(self):
        site,schedule,s=self.journey('H1')
        path=site.activity/'jobs/C01/arms/C01-V'
        raw,trace,balances=read_native(path/'run')
        source=self.original('V');original=read(source/'run.json')
        need=[r for r in s['rows'] if r['unit']=='C01-V'][0]
        ensure(need['validated_return'] and 'Incomplete physical trajectory' in need['error'],'Wrong score rejection: '+need.get('error',''))
        ensure(raw['inputs']==original['inputs'] and raw['code_identity']==original['code_identity'] and len(raw['policy_public_decisions'])==20,
               'Derived copy must preserve declared H10, runtime and public decisions')
        rows=[]
        for t,b in zip(trace[:-1],balances,strict=True):
            it=t['domains']['it_service']
            rows.append([b['start_s'],b['end_s'],it['demand'],it['delivered'],b['service_deficit_time_s'],b['demand_service_unit_s'],b['delivered_service_unit_s']])
        ensure(all(r[1]>r[0] for r in rows) and all(a[1]==b[0] for a,b in zip(rows,rows[1:])), 'Prefix not contiguous')
        try:service(rows);reason='UNEXPECTED_ACCEPT'
        except ValueError as exc:reason=str(exc)
        proof=dict(origin_path=str(source),origin_sha256=file_hash(source/'run.json'),derivative_sha256=file_hash(path/'run/run.json'),
                   prior_artifacts=original['artifacts'],derived_artifacts=raw['artifacts'],physical_records=len(trace),balance_records=len(balances),
                   declared_H10=raw['inputs']['duration_s'],actual_elapsed=[trace[0]['time_s'],trace[-1]['time_s']],
                   received=read(path/'native-return.json'),score_error=need['error'].splitlines()[-1],service_error=reason)
        C.once(site.shared/'truncation-proof.json',proof)
        c=s['counts']
        return dict(start_s=trace[0]['time_s'],last_s=trace[-1]['time_s'],nonempty=bool(rows),rows_align=len(trace)==len(balances)+1,
            inputs_verified=raw['inputs']==original['inputs'],source_verified=raw['code_identity']==original['code_identity'],
            raw_returns=c['raw_returns'],complete_returns=c['returned'],known_decisions=c['known_decisions'],unknown_decisions=c['unknown'],
            unexecuted=len(s['not_executed']),scorer_reason=need['error'].splitlines()[-1].removeprefix('ValueError: '),
            integrator_reason=reason,first_error_is_file_hash=False)



def durable_records(out,unit_ids):
    roles={}
    def include(path,role):
        if path.is_file():
            roles[path.relative_to(out).as_posix()]=dict(role=role,sha256=file_hash(path),bytes=path.stat().st_size)
    for unit in unit_ids:
        for name,role in [('observed.json','observed versus literal'),('error.txt','unexpected error')]:
            include(out/'units'/unit/name,role)
    for site_dir in sorted((out/'sites').glob('*')):
        if not site_dir.is_dir():continue
        site=C.Site(site_dir,B.SURROGATE)
        for name in ('surrogate-transport.json','truncation-proof.json','review-addendum-results.json'):
            include(site_dir/name,'fixture receipt')
        include(site.claim/'consumption.json','test grant consumption')
        for name in ('admission.json','manifest-binding.json','controller.json','halt.json','progress.json','finished.json','accounting-unresolved.json'):
            include(site.activity/name,'control ledger')
        for case in B.CASES:
            directory=site.activity/'jobs'/case
            if not directory.is_dir():continue
            for name in ('reserved.json','scheduler-command.json','submitted.json','release-requested.json','worker-claim.json',
                         'worker-result.json','scheduler-terminal.json','committed.json','panel.json','arms/ledger.json','arms/events.jsonl'):
                include(directory/name,'case journal or outcome')
            for arm in B.ARMS:
                arm_dir=directory/'arms'/(case+'-'+arm)
                if not arm_dir.is_dir():continue
                for name in ('execution-binding.json','call.json','native-return.json','score.json','stdout','stderr',
                        'inputs.json','model.json','dispatch-program.json','business-program.json','run/run.json','run/scenario.json',
                        'run/private-state.jsonl','run/balances.jsonl'):
                    include(arm_dir/name,'surrogate invocation / saved evidence')
    return roles


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--launch',type=Path,required=True);parser.add_argument('--sha',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    ensure(os.environ.get('SLURM_JOB_ID') and file_hash(args.launch)==args.sha,'Wrong qualification allocation or launch')
    launch=read(args.launch);out=args.output.resolve()
    ensure(launch['output']==str(out) and os.environ.get('SLURM_CPUS_PER_TASK')=='1' and os.environ.get('SLURM_MEM_PER_NODE')=='1024','Wrong allocation')
    out.mkdir(mode=0o700);(out/'units').mkdir()
    freeze=read(HERE/'freeze.json')
    report=dict(schema='aegisdc-native-research-launch-zero-facility-attempt-v1',job=os.environ['SLURM_JOB_ID'],
        launch_sha256=args.sha,source_revision=launch['source_revision'],manifest_sha256=launch['manifest_sha256'],results={},
        actual_facility_calls=0,actual_public_policy_calls=0,real_research_authorizations_consumed=0,research_jobs_submitted=0)
    h=None
    try:
        for k,v in launch['files'].items():ensure(file_hash(ROOT/k)==v,'Staged source differs: '+k)
        ensure(file_hash(Path(sys.executable).resolve())==launch['python_sha256'],'Unpinned interpreter')
        ensure(file_hash(HERE/'freeze.json')==launch['freeze_sha256'] and file_hash(HERE/'review-addendum.json')==launch['review_addendum_sha256'],
               'Witness freeze drift')
        rel=B.load_release(ROOT,launch['manifest_sha256'])
        ensure(ROOT==B.RELEASE and not (B.SHARED/B.STUDY).exists() and not C.Site(B.SHARED,B.REAL).claim.exists(),
               'Wrong verification deployment or an actual research state exists')
        h=Harness(out,rel,freeze)
        for spec in freeze['tests']:
            key=spec['id'];directory=out/'units'/key;directory.mkdir()
            try:
                actual=getattr(h,key)()
                expected=spec['expected']
                ensure(actual.keys()==expected.keys(),'Mismatched comparison fields')
                differences={k:dict(expected=v,actual=actual[k]) for k,v in expected.items() if not literal_equal(actual[k],v)}
                row=dict(passed=not differences,actual=actual,expected=expected,differences=differences)
                C.once(directory/'observed.json',row)
            except Exception:
                error=traceback.format_exc();(directory/'error.txt').write_text(error,encoding='utf-8')
                row=dict(passed=False,error=error)
            report['results'][key]=row
        ensure(sys.modules['aegis_dc.plant'] is None,'Unexpected facility module import')
        ensure(not (B.SHARED/B.STUDY).exists() and not C.Site(B.SHARED,B.REAL).claim.exists(),'Real study state created')
        report['passed']=all(x['passed'] for x in report['results'].values())
    except Exception:
        report.update(passed=False,fatal=traceback.format_exc())
    finally:
        ids=[s['id'] for s in freeze['tests']]
        report['unexecuted']=[k for k in ids if k not in report['results']]
        if h is not None:
            report['surrogate_arm_requests']=h.starts;report['originals']=h.originals
        inventory=durable_records(out,ids)
        C.once(out/'durable-files.json',inventory)
        report['durable_manifest_sha256']=file_hash(out/'durable-files.json')
        C.once(out/'report.json',report)
    return 0 if report['passed'] else 1


if __name__=='__main__':sys.exit(main())
