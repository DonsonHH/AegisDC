"""Verification jobs V0/V1 only. The native plant and policy are unavailable in this process."""
from copy import deepcopy
from pathlib import Path
import base64
import hashlib
import json
import os
import shutil
import socket
import sys
import traceback

HERE=Path(__file__).resolve().parent
DEPLOY=Path('/share/home/renly/renly-patrol-rsi/mainline/V6-cold-launch-release-v1/source')
sys.path[:0]=[str(DEPLOY/'scripts'),str(DEPLOY/'src')]
for denied in ('aegis_dc.plant','aegis_dc.joint_policy','aegis_dc.joint_session'):sys.modules[denied]=None
from cold3_runner import read,sha,digest
from cold3_evaluation import compare_pair,panel
from cold3_launch import binding as B
from cold3_launch.control import admit,admitted,start,worker,verify_worker_identity,reservation
from cold3_launch.native import disposition
from cold3_launch.ledger import summary,slot_state
from cold3_launch.transport import allocation,ColdSlurm
from v6_research.control import once,doc


def insist(ok,what):
    if not ok:raise AssertionError(what)


def expect_error(fn,wanted):
    try:fn()
    except B.GateError as exc:
        insist(exc.code==wanted,f'{exc.code} != {wanted}');return exc.code
    raise AssertionError('unexpected success: '+wanted)


def literal(actual,expected):
    if isinstance(expected,bool):return type(actual) is bool and actual==expected
    if type(expected) in (int,float):return type(actual) in (int,float) and actual==expected
    if isinstance(expected,dict):return isinstance(actual,dict) and set(actual)==set(expected) and all(literal(actual[k],v) for k,v in expected.items())
    if isinstance(expected,list):return isinstance(actual,list) and len(actual)==len(expected) and all(literal(a,b) for a,b in zip(actual,expected))
    return type(actual) is type(expected) and actual==expected


class FixtureReview(B.Review):
    """Only the embedded GitHub transport is replaced; use real current-ref and blob checks."""
    def __init__(self,bench,site,mode='ok'):
        self.b=bench;self.site=site;self.mode=mode
    def obtain(self,path):
        revision=self.b.f['fixture_bindings']['review_revision']
        if path=='/git/ref/heads/'+B.BRANCH:
            return dict(ref='refs/heads/'+B.BRANCH,object=dict(type='commit',sha=(self.b.f['fixture_bindings']['stale_revision'] if self.mode=='stale-ref' else revision)))
        name=path.removeprefix('/contents/').split('?ref=')[0]
        insist(path=='/contents/'+name+'?ref='+revision,'review revision/path mismatch')
        if name==B.GRANT:
            if self.mode=='absent-grant':raise B.GateError('GRANT_ABSENT')
            m=self.b.rel.manifest
            grant=dict(schema='cold-single-use-reviewed-grant-v1',purpose='PUBLIC_COLD_LAUNCH_SURROGATE',
                decision='APPROVE_ONE_LAUNCH',uses=1,study='V6-cold-study-v2-once',launch_sha256=self.b.rel.sha,
                data_sha256=self.b.f['data_manifest_sha256'],input_sha256=self.b.f['data_inputs_sha256'],
                acceptance_sha256=B.ACCEPT_SHA,adapter_revision=m['adapter_revision'],launch_tree=m['launch_tree'],
                core_revision='0e5afde1a5e734a04489f1bf27804db6a3325497',core_tree='67db74467194edf547cc7994a702019fa4040b8aa1cebf1eaa33574327b7b735',
                activity_root=str(self.site.activity),order_sha256=digest(self.b.rel.data['groups']),limits_sha256=digest(self.b.rel.data['limits']),
                user_decision_reference='PUBLIC SYNTHETIC REVIEW ONLY')
            for mode,key,val in [('wrong-purpose','purpose','UNRELATED'),('wrong-hash','launch_sha256',self.b.f['data_manifest_sha256']),
                                 ('wrong-budget','limits_sha256','0'*64),('wrong-root','activity_root',str(self.site.activity)+'-other'),
                                 ('wrong-schedule','order_sha256','0'*64)]:
                if self.mode==mode:grant[key]=val
            raw=json.dumps(grant,sort_keys=True).encode()
        else:
            insist(name in (B.FINAL,B.DATA,B.ACCEPT),'unknown public reviewed file')
            raw=(DEPLOY/name).read_bytes()
            if (self.mode,name) in [('wrong-published-manifest',B.FINAL),('wrong-published-acceptance',B.ACCEPT)]:raw+=b' '
        oid=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        return dict(path=name,type='file',encoding='base64',size=len(raw),sha=oid,content=base64.b64encode(raw).decode())


class Replay:
    def __init__(self,bench,scenario):
        self.b=bench;self.scenario=scenario
    def evidence(self,key):
        donor=self.b.donors[key];return self.b.engineering[donor]
    def command(self,rel,site,case,key,unit,job,native):
        insist(site.purpose==B.SURROGATE and site.activity in unit.parents,'surrogate containment')
        literal_command=[B.PYTHON,'-I','-B',str(DEPLOY/B.CLI),'arm','--manifest-sha',rel.sha,'--case',case,'--slot',key]
        insist(native==literal_command,'incorrect actual production arm command')
        return [sys.executable,'-I','-B',str(HERE/'replay_child.py'),self.b.phase,self.scenario,rel.sha,self.b.pin_hash,key,job]


class Scheduler(ColdSlurm):
    def __init__(self,b,site,scenario,mode):
        self.b=b;self.site=site;self.scenario=scenario;self.mode=mode;self.jobs={};self.duplicate=None;self.misses=0
        self.sub=Replay(b,scenario)
        super().__init__(self.handle,lambda seconds:None)
    def alloc(self,job):
        return allocation(self.handle,dict(SLURM_JOB_ID=job,SLURM_CPUS_PER_TASK='1',SLURM_MEM_PER_NODE='4096'))
    def handle(self,*a):
        node=socket.gethostname().split('.')[0]
        if a[0]=='sbatch':
            i=len(self.jobs);case=self.b.f['rows'][i]['row'];folder=self.site.activity/'jobs'/case
            expected=['sbatch','--parsable','--hold','--no-requeue','--partition=cu','--nodes=1','--ntasks=1','--cpus-per-task=1',
                '--mem=4G','--time=00:05:00','--job-name=cold3-study-'+case,'--chdir='+str(DEPLOY),
                '--output='+str(folder/'slurm-%j.out'),'--error='+str(folder/'slurm-%j.err'),str(DEPLOY/B.PACK/'study.sbatch'),
                str(DEPLOY),self.b.rel.sha,case]
            insist(list(a)==expected and not any(j['state'] in ('HELD','RUNNING','UNKNOWN') for j in self.jobs.values()),'held serial command')
            job=str(900001+i);self.jobs[job]=dict(row=case,state='HELD')
            if self.mode=='HELD_ID_LOST':raise OSError('frozen lost held submission response')
            return job
        if a[:2]==('scontrol','release'):
            job=a[-1];j=self.jobs[job];insist(j['state']=='HELD','duplicate release');j['state']='RUNNING'
            if self.mode=='RELEASE_ACK_LOST':raise OSError('frozen release acknowledgement missing')
            receipt=worker(self.site,self.b.rel,j['row'],self.alloc(job),self.sub)
            if self.scenario=='full' and j['row']=='A01':
                self.duplicate=expect_error(lambda:worker(self.site,self.b.rel,'A01',self.alloc(job),self.sub),'WORKER_REPLAY')
            j['state']='UNKNOWN' if self.mode=='TERMINAL_UNOBSERVED' else 'COMPLETED' if receipt['passed'] else 'FAILED'
            return ''
        if a[:4]==('scontrol','show','job','-o'):
            job=a[-1];j=self.jobs[job]
            return (f"JobId={job} JobName=cold3-study-{j['row']} JobState=RUNNING NumCPUs=1 NumNodes=1 MinMemoryNode=4G "
                    f"NodeList={node} BatchHost={node} AllocTRES=cpu=1,mem=4G,node=1 TimeLimit=00:05:00 UserId=renly(1) Requeue=0 Restarts=0 Partition=cu")
        if a[:2]==('scontrol','listpids'):return f"PID JOBID STEPID\n{os.getpid()} {a[2]} batch"
        if a[0]=='sacct':
            job=a[a.index('-j')+1];state=self.jobs[job]['state']
            if state=='UNKNOWN':self.misses+=1;return ''
            return f"{job}|{state}|"+('0:0' if state=='COMPLETED' else '1:0')+'|1'
        if a[0]=='squeue':return ''
        raise ValueError('Unregistered scheduler operation '+str(a))


class Bench:
    def __init__(self,phase,launch,pin_hash):
        self.phase=phase;self.pin_hash=pin_hash;self.out=B.QUAL/phase;self.rel=B.load_release(DEPLOY,launch)
        pin=read(HERE/'verification-pin.json')
        insist(set(pin['files'])=={'verify.py','replay_child.py','validation-freeze.json'} and pin['purpose']=='ZERO_FACILITY_COLD_LAUNCH_VERIFICATION' and
               sha(HERE/'verification-pin.json')==pin_hash and pin['launch_sha256']==launch and
               all(sha(HERE/k)==h for k,h in pin['files'].items()),'qualification source binding')
        self.f=read(HERE/'validation-freeze.json')
        accepted=read(DEPLOY/B.ACCEPT)
        insist(sha(DEPLOY/B.COLD/'engineering-inputs.json.gz')==self.f['engineering_inputs_sha256'] and
               sha(DEPLOY/B.COLD/'expected.json')==accepted['binding']['expected.json'],'complete historical inputs and independent oracle')
        self.engineering=read(DEPLOY/B.COLD/'engineering-inputs.json.gz')
        self.donors={c['slot']:c['donor'] for r in self.f['rows'] for c in r['order']}
        self.donor_scores={};self.results=[];self.revision=self.f['fixture_bindings']['review_revision']
        for name,d in self.f['donor_sources'].items():
            source=Path(self.f['source_activity'])
            insist(sha(source/d['retained_run'])==d['raw_sha256'] and sha(source/d['score_path'])==d['score_sha256']
                   and digest(self.engineering[name])==d['source_input'],'original engineering source '+name)
            self.donor_scores[name]=digest(read(source/d['score_path']))
    def site(self,name):return B.Site(self.out/name/'sandbox',B.SURROGATE)
    def check(self,name,actual,wanted):
        self.results.append(dict(check=name,ok=literal(actual,wanted),actual=actual,expected=wanted))
    def entries(self):
        p=self.out/'surrogate-entries.jsonl'
        return [json.loads(l) for l in p.read_text().splitlines()] if p.is_file() else []

    def guards(self):
        wanted=self.f['zero_entry_guards']
        for name in ('absent-revision','absent-grant','wrong-purpose','wrong-hash','wrong-budget','wrong-root','wrong-schedule',
                     'stale-ref','wrong-published-manifest','wrong-published-acceptance','existing-output','already-consumed'):
            site=self.site('guard-'+name);review=FixtureReview(self,site,name)
            if name=='existing-output':site.activity.mkdir(parents=True);once(site.activity/'previous.json',{'keep':'prior'})
            if name=='already-consumed':admit(site,self.rel,review,self.revision)
            code=expect_error(lambda:admit(site,self.rel,review,None if name=='absent-revision' else self.revision),wanted[name])
            self.check(name,[code,site.claim.exists()],[wanted[name],name=='already-consumed'])
        for name,file in [('source-drift','src/aegis_dc/joint_policy.py'),('packed-input-drift',self.rel.manifest['input_archive'])]:
            dest=self.out/name/'export';shutil.copytree(DEPLOY,dest)
            with (dest/file).open('ab') as s:s.write(b'public negative fixture')
            self.check(name,expect_error(lambda:B.load_release(dest,self.rel.sha),wanted[name]),wanted[name])
        altered=deepcopy(self.rel.inputs['A01-J']);altered['step_s']=.02
        self.check('individual-input-drift',expect_error(lambda:B.verify_item(self.rel,'A01','A01-J',altered),wanted['individual-input-drift']),wanted['individual-input-drift'])
        self.check('manifest-drift',expect_error(lambda:B.load_release(DEPLOY,'0'*64),wanted['manifest-drift']),wanted['manifest-drift'])
        site=self.site('guard-allocation');admit(site,self.rel,FixtureReview(self,site),self.revision)
        folder=site.activity/'jobs/A01';folder.mkdir()
        once(folder/'reserved.json',reservation(site,self.rel,'A01'))
        once(folder/'submitted.json',dict(row='A01',job='900001'));once(folder/'release-requested.json',dict(row='A01',job='900001'))
        scheduler=Scheduler(self,site,'guard-allocation','');scheduler.jobs['900001']=dict(row='A01',state='HELD')
        a=scheduler.alloc('900001')
        for name,row,alloc in [('bad-allocation','A01',dict(a,requeue=1)),('wrong-worker-row','A02',a),('bad-job','A01',dict(a,job='900002'))]:
            self.check(name,expect_error(lambda:verify_worker_identity(site,self.rel,row,alloc),wanted[name]),wanted[name])
        self.check('failed claims leave worker unclaimed',(folder/'worker-claim.json').exists(),False)
        path=self.out/'intent-only';unit=path/'arms/A01-J';unit.mkdir(parents=True);once(unit/'prelaunch.json',{'surrogate':True})
        row=slot_state(path,'A01-J',self.rel)
        self.check('prelaunch without process acknowledgement',[row['known'],row['potential'],row['state']],[False,True,'ENTRY_UNKNOWN'])
        # Test the unchanged numerical evaluator on previously frozen score fixtures, then the stop classifier.
        fixture=read(DEPLOY/B.COLD/'expected.json')['evaluators']['conflicting-directions']
        baseline=read(Path(self.f['source_activity'])/self.f['donor_sources']['O-J']['score_path'])
        l=dict(baseline,service=fixture['left']);r=dict(baseline,service=fixture['right']);result=compare_pair(l,r)
        self.check('ordinary numerical ambiguity',[result['category'],disposition(result)],['NUMERIC_UNRESOLVED','CONTINUE'])
        self.check('all pre-entry guards',len(self.entries()),0)

    def scenario(self,name,mode,expected):
        site=self.site(name);scheduler=Scheduler(self,site,name,mode)
        completed=start(site,self.rel,FixtureReview(self,site),self.revision,scheduler)
        state=summary(site,self.rel,deep=True)
        once(self.out/name/'readback.json',state)
        known={k:state[k] for k in expected if k not in ('expected_halt','material_pairs')}
        known['expected_halt']=doc(site.activity/'halt.json')['code'] if (site.activity/'halt.json').is_file() else None
        known['material_pairs']=state['paired']
        self.check(name+' core projection',known,expected)
        self.check(name+' sealed qualification namespace',[completed,state['real_research_entries'],site.claim.is_dir()],
                   [name=='full',0,True])
        self.check(name+' all slot identities',[r['slot'] for r in state['rows']],self.f['position_order'])
        self.check(name+' paired denominators',state['panel']['denominators'],self.f['denominators'])
        categories={k:v for k,v in state['panel']['counts'].items()}
        for typ,n in self.f['denominators'].items():
            records={k:0 for k in ('SAME','BETTER','WORSE','NUMERIC_UNRESOLVED','NONCOMPLIANT','NO_PAIR')}
            for slot,cat in expected['material_pairs'].items():
                method=slot.split('-',1)[1]
                if ('J/B' if method=='B' else method)==typ:records[cat]+=1
            records['NO_PAIR']=n-sum(records.values())
            self.check(name+' all outcomes '+typ,categories[typ],records)
        actual=[r['slot'] for r in self.entries() if r['case']==name]
        self.check(name+' actual substitute order',actual,self.f['position_order'][:expected['known_starts']])
        self.check(name+' unchanged/known progress',state['accounting_errors'],[])
        for k in actual:
            case=k.split('-')[0];unit=site.activity/'jobs'/case/'arms'/k
            if not (unit/'scored.json').exists():continue
            donor=self.donors[k];mode_here=doc(unit/'donor.json')['mode']
            if mode_here=='COPY':
                self.check(name+' old score identity '+k,digest(read(unit/'score.json.gz')),self.donor_scores[donor])
            else:
                score=read(unit/'score.json.gz')
                if mode_here=='BAD_CERTIFICATE':self.check(name+' hard reason','NAMED_CLOSURE' in score['violations'],True)
                if mode_here=='MISSING_LEFT':self.check(name+' true missing face',score['numerical_evidence']['face_faults'],[dict(reason='MISSING_FACE',time=2,face='left')])
        if name=='archive':
            self.check('archive sentinel',(site.activity/'jobs/A01/arms/A01-J/score.json.gz').read_text(),self.f['fixture_bindings']['sentinel'])
        if name=='scheduler-unknown':
            self.check('same ID observed three times',scheduler.misses,3)
            mirror=self.site('missing-evidence-mirror');target=mirror.activity/'jobs/A01';target.mkdir(parents=True)
            source=site.activity/'jobs/A01'
            for n in ('reserved.json','submitted.json','release-requested.json','worker-result.json','scheduler-terminal.json'):
                shutil.copyfile(source/n,target/n)
            shutil.copytree(source/'pairs',target/'pairs')
            unavailable=summary(mirror,self.rel,deep=True)
            self.check('sealed subtotal, missing files',[unavailable['known_starts'],unavailable['validated_returns'],unavailable['known_internal'],
                unavailable['raw_present'],unavailable['rows'][0]['state'],unavailable['panel']['counts']['J/B']['NO_PAIR']],
                [3,3,147,0,'SAVED_EVIDENCE_UNAVAILABLE',24])
        if name=='full':
            self.check('worker replay',scheduler.duplicate,self.f['full']['duplicate_worker'])
            self.check('consumed full launch',expect_error(lambda:admit(site,self.rel,FixtureReview(self,site),self.revision),'GRANT_CONSUMED'),'GRANT_CONSUMED')
            self.check('manual archive subtotal',state['manual_exact'],self.f['full']['independent_manual_issues'])
            self.check('final panel seal',sha(site.activity/'panel.json'),doc(site.activity/'finished.json')['panel_sha256'])
        return dict(id=name,observed=known,counts=state['panel']['counts'],readback_sha256=sha(self.out/name/'readback.json'),
                    grant_namespace=site.purpose,real_research_entries=state['real_research_entries'])


def main():
    phase,h,pin_hash=sys.argv[1:]
    if phase not in ('V0','V1') or HERE!=B.QUAL/'tools' or os.environ.get('SLURM_CPUS_PER_TASK')!='1':raise PermissionError('qualification only')
    out=B.QUAL/phase
    once(out/'started.json',dict(phase=phase,job=os.environ['SLURM_JOB_ID'],launch=h,verification_pin=pin_hash))
    real_allocation=allocation()
    insist(real_allocation['name']=='cold-launch-'+phase and real_allocation['cpus']==real_allocation['nodes']==1 and
           real_allocation['mem_mib']==4096 and real_allocation['seconds']==300 and real_allocation['partition']=='cu' and
           real_allocation['gpus']==real_allocation['restarts']==real_allocation['requeue']==0 and
           real_allocation['state']=='RUNNING' and real_allocation['process_membership'],'live verification allocation')
    once(out/'allocation.json',real_allocation)
    b=Bench(phase,h,pin_hash)
    if phase=='V1':
        from v6_research.slurm import run as slurm_read
        prior=doc(B.QUAL/'V0/result.json');jid=str(prior['job'])
        insist(jid.isdecimal() and (B.QUAL/'V0/job.id').read_text().strip()==jid and prior['phase']=='V0' and
               prior['status']=='PASS' and prior['launch_sha256']==h and prior['verifier_sha256']==pin_hash and
               prior['checks_sha256']==sha(B.QUAL/'V0/checks.json') and prior['actual_surrogate_entries']==14,'V0 not qualified')
        rows=[x.split('|') for x in slurm_read('sacct','-X','-nP','-j',jid,'-o','JobIDRaw,State,ExitCode').splitlines() if x.split('|')[0]==jid]
        insist(len(rows)==1 and rows[0][:3]==[jid,'COMPLETED','0:0'],'no verified V0 terminal')
    def boundary(event,args):
        if event.startswith('socket.connect'):raise PermissionError('External review transport disabled in fixture')
        if event=='subprocess.Popen':
            command=args[1]
            if not isinstance(command,list) or command[:4]!=[sys.executable,'-I','-B',str(HERE/'replay_child.py')]:
                raise PermissionError('Live submission or facility child is not a qualification command')
    sys.addaudithook(boundary)
    cases=[];failure=None
    try:
        if phase=='V0':
            b.guards()
            for spec in b.f['faults']:cases.append(b.scenario(spec['id'],spec['mode'],spec['expected']))
        else:cases.append(b.scenario('full','COPY',b.f['full']['expected']))
    except Exception as exc:
        failure=repr(exc);(out/'exception.txt').write_text(traceback.format_exc(),encoding='utf8')
    entered=b.entries();expected=b.f['resource'][phase]['surrogate_cap']
    b.check('actual surrogate calls including repeats',len(entered),expected)
    b.check('exclusive actual process entries',len({(r['case'],r['slot']) for r in entered}),len(entered))
    b.check('no native modules loaded',all(sys.modules.get(n) is None for n in ('aegis_dc.plant','aegis_dc.joint_policy','aegis_dc.joint_session')),True)
    order=([['full',k] for k in b.f['position_order']] if phase=='V1' else
           [[s['id'],k] for s in b.f['faults'] for k in s['ordered_substitute_entries']])
    actual_order=[[r['case'],r['slot']] for r in entered]
    b.check('full frozen ordered entry ledger',actual_order,order)
    unstarted=[r for r in order if r not in actual_order]
    missing=[r['check'] for r in b.results if not r['ok']]
    once(out/'checks.json',b.results)
    once(out/'result.json',dict(status='PASS' if not missing and not failure else 'FAILED',phase=phase,job=os.environ['SLURM_JOB_ID'],launch_sha256=h,
        verifier_sha256=pin_hash,actual_surrogate_entries=len(entered),real_facility=0,real_policy=0,real_research=0,real_grants_created=0,
        real_grants_consumed=0,planned_entries=order,actual_entries=actual_order,unstarted=unstarted,actual_assertions=len(b.results),failures=missing,exception=failure,cases=cases,checks_sha256=sha(out/'checks.json')))
    print(phase,len(entered),len(b.results),missing,failure,flush=True)
    return int(bool(missing or failure))


if __name__=='__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        # Distinguish a consumed failed allocation from unstarted verification phases.
        name=sys.argv[1] if len(sys.argv)>1 else ''
        if name in ('V0','V1'):
            folder=B.QUAL/name
            if ((folder/'started.json').is_file() and doc(folder/'started.json').get('job')==os.environ.get('SLURM_JOB_ID')
                    and not (folder/'result.json').exists()):
                journal=folder/'surrogate-entries.jsonl'
                entries=[json.loads(l) for l in journal.read_text().splitlines()] if journal.exists() else []
                once(folder/'result.json',dict(phase=name,job=os.environ.get('SLURM_JOB_ID'),status='FAILED_BEFORE_COMPLETION',
                    error=repr(exc),actual_surrogate_entries=len(entries),observed_entries=entries,real_facility=0,real_policy=0,
                    real_research=0,retry=False))
        raise
