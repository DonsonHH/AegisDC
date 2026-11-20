"""One-use launch, serial job reservations and full-panel accounting on shared storage."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
import traceback

from aegis_dc.native_compare_inputs import file_hash
from aegis_dc.native_compare_run import checkpoint
from aegis_dc.native_compare_score import panel
from patrol_rsi.contracts import digest
from .binding import ARMS, CASES, REAL, SURROGATE, STUDY, SHARED, GateError, check, check_grant, load_json
from .native import execute_case


def doc(path):
    return load_json(path.read_bytes())


def once(path, value):
    """Publish one complete receipt without replacing an earlier record."""
    data=(json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode()
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.writing-')
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.link(tmp,path)
        parent=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(parent)
        finally:os.close(parent)
    finally:
        os.unlink(tmp)


@dataclass(frozen=True)
class Site:
    shared: Path
    purpose: str
    @property
    def activity(self):return self.shared/STUDY
    @property
    def claim(self):return self.shared/'.native-research-approvals'/STUDY

    def validate(self):
        check((self.purpose==REAL and self.shared.resolve()==SHARED.resolve()) or
              (self.purpose==SURROGATE and self.shared.resolve()!=SHARED.resolve()),'PURPOSE')
        check(not self.activity.is_symlink() and not self.claim.parent.is_symlink() and not self.claim.is_symlink(),'DEPLOYMENT_IDENTITY')


def admit(site,release,authority,revision):
    check(revision is not None,'AUTHORIZATION_REQUIRED')
    site.validate()
    approval=authority.authorize(release,revision,site.purpose)
    check_grant(release,approval['grant'],site.purpose)
    check(approval['review_revision']==revision and approval['manifest_sha256']==release.sha
          and approval['grant_digest']==digest(approval['grant']),'GRANT_BINDING')
    check(not os.path.lexists(site.claim),'GRANT_CONSUMED')
    if os.path.lexists(site.activity):
        raise GateError('GRANT_CONSUMED' if site.claim.exists() else 'OUTPUT_EXISTS')
    site.claim.parent.mkdir(mode=0o700,exist_ok=True)
    try:site.claim.mkdir(mode=0o700)
    except FileExistsError as exc:raise GateError('GRANT_CONSUMED') from exc
    proof=dict(approval=approval,manifest_sha256=release.sha,physical_activity=str(site.activity),
               purpose=site.purpose,grant_id=STUDY)
    once(site.claim/'consumption.json',proof)
    try:site.activity.mkdir(mode=0o700)
    except FileExistsError as exc:raise GateError('OUTPUT_EXISTS','consumption retained') from exc
    once(site.activity/'admission.json',proof)
    once(site.activity/'manifest-binding.json',dict(sha256=release.sha,acceptance=release.manifest['acceptance_sha256'],
         consumption_sha256=file_hash(site.claim/'consumption.json')))
    (site.activity/'jobs').mkdir(mode=0o700)
    checkpoint(site.activity/'progress.json',snapshot(site,release))
    return proof


def admitted(site,release):
    site.validate()
    bound=doc(site.activity/'manifest-binding.json')
    proof=doc(site.claim/'consumption.json')
    check(bound['sha256']==release.sha and bound['acceptance']==release.manifest['acceptance_sha256']
          and bound['consumption_sha256']==file_hash(site.claim/'consumption.json')
          and (site.activity/'admission.json').read_bytes()==(site.claim/'consumption.json').read_bytes(),'CONSUMPTION_IDENTITY')
    check(proof['manifest_sha256']==release.sha and proof['purpose']==site.purpose
          and proof['physical_activity']==str(site.activity) and proof['approval']['grant_digest']==digest(proof['approval']['grant']),'CONSUMPTION_IDENTITY')
    check_grant(release,proof['approval']['grant'],site.purpose)
    return proof


def sum_jobs(history):
    return [len(history),sum(r['started'] for r in history),sum(r['known_decisions'] for r in history),
            sum(r['manual_issues'] for r in history),sum(r['reserved_cpu_s'] for r in history)]


def next_position(history, case):
    for index,job in enumerate(history):
        check(index<len(CASES) and job['case']==CASES[index],'JOB_ORDER')
        check(job['status']=='COMMITTED' and not job['unknown'] and not job['unknown_issues'] and not job['uncertain_starts'] and not job.get('accounting_errors'),'PRIOR_UNRESOLVED')
        limit=24 if job['case']=='C17' else 12
        check(job['started']==job['returned']==5 and job['known_decisions']==100 and
              type(job['manual_issues']) is int and 0<=job['manual_issues']<=limit and job['reserved_cpu_s']==120,'BUDGET_EXCEEDED')
    check(len(history)<len(CASES),'SCHEDULE_COMPLETE')
    check(case==CASES[len(history)],'JOB_ORDER')
    jobs,starts,calls,issues,cpu=sum_jobs(history)
    check(jobs+1<=17 and starts+5<=85 and calls+100<=1700 and issues+(24 if case=='C17' else 12)<=216 and cpu+120<=2040,
          'BUDGET_EXCEEDED')
    return dict(case=case,index=len(history)+1,reserved_cpu_s=120,arm_cap=5,decision_cap=100,
                manual_cap=24 if case=='C17' else 12,previous_totals=[jobs,starts,calls,issues,cpu])


def case_rows(jobdir,case):
    names=[case+'-'+a for a in ARMS]
    result={k:dict(unit=k,state='NOT_EXECUTED',known_start=False,validated_return=False,raw_return=False,
                   decisions=None,issues=None,ambiguous_start=False) for k in names}
    errors=[]
    ledger=jobdir/'arms/ledger.json'
    if ledger.exists():
        try:
            rows=doc(ledger)['rows']
            check([r['unit'] for r in rows]==names and all(set(('state','started','complete_return','internal_policy_calls','pid','start_ns','returned_ns'))<=r.keys() for r in rows),'LEDGER_IDENTITY')
        except (OSError,ValueError,TypeError,KeyError) as exc:
            errors.append('ledger: '+str(exc));rows=[]
        for x in rows:
            r=result[x['unit']]
            r.update(state=x['state'],known_start=x['started'],validated_return=x['complete_return'],
                     decisions=x['internal_policy_calls'],pid=x['pid'],start_ns=x['start_ns'],return_ns=x['returned_ns'])
            if x.get('error'):r['error']=x['error']
    events=jobdir/'arms/events.jsonl'
    if events.exists():
        for line in events.read_bytes().splitlines():
            e=load_json(line);r=result[e['unit']]
            if e['event']=='BEFORE_LAUNCH':r['before_launch']=True
            elif e['event']=='STARTED':r.update(known_start=True,pid=e['pid'],start_ns=e['ns'])
            elif e['event']=='EXIT':r['exit_code']=e['rc']
            elif e['event']=='COMPLETE_RETURN':r.update(validated_return=True,decisions=e.get('decisions'),return_ns=e['ns'])
            elif e['event']=='FAILED':r['state']='FAILED'
    for key,r in result.items():
        path=jobdir/'arms'/key
        r['raw_return']=(path/'run/run.json').is_file()
        if (path/'native-return.json').is_file():
            try:
                receipt=doc(path/'native-return.json')
                r.update(validated_return=True,decisions=receipt['internal_policy_calls'],issues=receipt['manual_issues'],
                         native_sha256=receipt['native_sha256'])
            except (ValueError,TypeError,KeyError,OSError) as exc:
                errors.append(key+' native receipt: '+str(exc))
        if (r.get('before_launch') or (errors and (path/'call.json').exists())) and not r['known_start']:
            r.update(ambiguous_start=True,state='START_UNRESOLVED')
        elif r['known_start'] and r['state'] not in ('COMPLETED','FAILED'):r['state']='UNRESOLVED'
        if (path/'score.json').is_file():r['score_present']=True
    if errors:result[names[0]]['case_accounting_errors']=errors
    return list(result.values())


def case_summary(rows):
    known=lambda v:type(v) is int and v>=0
    return dict(accounting_errors={r['unit']:r['case_accounting_errors'] for r in rows if r.get('case_accounting_errors')},
        started=sum(r['known_start'] for r in rows),returned=sum(r['validated_return'] for r in rows),
        raw_returns=sum(r['raw_return'] for r in rows),unreturned=sum(r['known_start'] and not r['validated_return'] for r in rows),
        missing_raw_returns=[r['unit'] for r in rows if r['known_start'] and not r['raw_return']],
        raw_present_unvalidated=[r['unit'] for r in rows if r['raw_return'] and not r['validated_return']],
        known_decisions=sum(r['decisions'] for r in rows if known(r['decisions'])),
        manual_issues=sum(r['issues'] for r in rows if known(r['issues'])),
        unknown=[r['unit'] for r in rows if r['known_start'] and not known(r['decisions'])],
        unknown_issues=[r['unit'] for r in rows if r['known_start'] and not known(r['issues'])],
        uncertain_starts=[r['unit'] for r in rows if r['ambiguous_start']])


def committed(site,release,case):
    jobdir=site.activity/'jobs'/case
    seal=doc(jobdir/'committed.json')
    for name,h in seal['files'].items():
        check(file_hash(jobdir/name)==h,'LEDGER_IDENTITY',case+'/'+name)
    need_files={'reserved.json','submitted.json','worker-claim.json','worker-result.json','scheduler-terminal.json','arms/ledger.json','arms/events.jsonl'}
    check(set(seal['files'])==need_files,'LEDGER_IDENTITY')
    worker=doc(jobdir/'worker-result.json');terminal=doc(jobdir/'scheduler-terminal.json')
    reservation=doc(jobdir/'reserved.json')
    check(seal['manifest']==release.sha==reservation['manifest'] and worker['manifest']==release.sha
          and terminal['state']=='COMPLETED' and terminal['exit']=='0:0' and worker['passed'] and
          worker['case']==case and worker['job']==doc(jobdir/'submitted.json')['job']==terminal['job'],'LEDGER_IDENTITY')
    return dict(case=case,status='COMMITTED',reserved_cpu_s=reservation['reserved_cpu_s'],**worker['counts'])


def previous(site,release,case):
    return [committed(site,release,c) for c in CASES[:CASES.index(case)]]


def snapshot(site,release):
    all_rows=[];jobs=[];potential=[];submit_unknown=[];scheduler_pending=[]
    for case in CASES:
        jobdir=site.activity/'jobs'/case
        rows=case_rows(jobdir,case)
        if (jobdir/'reserved.json').exists():
            job=dict(case=case,reserved_cpu_s=120)
            for file,key in [('submitted.json','submitted'),('scheduler-terminal.json','terminal'),('worker-result.json','worker')]:
                if (jobdir/file).exists():
                    try:
                        entry=doc(jobdir/file)
                        job[key]=entry.get('state',entry.get('job')) if key!='worker' else entry['passed']
                    except (OSError,KeyError,TypeError,ValueError) as exc:
                        rows[0].setdefault('case_accounting_errors',[]).append(file+': '+str(exc))
            job['committed']=(jobdir/'committed.json').exists()
            if 'submitted' not in job:submit_unknown.append(case)
            if 'submitted' in job and job.get('terminal') in (None,'UNKNOWN','UNRESOLVED'):scheduler_pending.append(case)
            if (jobdir/'release-requested.json').exists() and 'worker' not in job:
                potential.append(case)
                for r in rows:
                    if r['state']=='NOT_EXECUTED':r['state']='JOB_UNRESOLVED'
            jobs.append(job)
        all_rows.extend(rows)
    counts=case_summary(all_rows)
    return dict(schema='aegisdc-v6-research-global-account-v1',manifest_sha256=release.sha,purpose=site.purpose,
        denominator=85,rows=all_rows,jobs=jobs,job_reservations=len(jobs),confirmed_job_ids=sum('submitted' in j for j in jobs),
        reserved_cpu_s=120*len(jobs),unresolved_jobs=potential,unknown_submission_ids=submit_unknown,
        unresolved_scheduler_outcomes=scheduler_pending,confirmed_submissions_exact=None if submit_unknown else len(jobs),counts=counts,
        not_executed=[r['unit'] for r in all_rows if r['state']=='NOT_EXECUTED'],
        total_starts_exact=None if potential or counts['uncertain_starts'] or counts['accounting_errors'] else counts['started'],
        total_decisions_exact=None if potential or counts['unknown'] or counts['uncertain_starts'] or counts['accounting_errors'] else counts['known_decisions'],
        research_arms_executed=counts['started'] if site.purpose==REAL else 0)


def claim_worker(site,release,case,allocation):
    admitted(site,release)
    check(case in CASES,'JOB_ORDER')
    jobdir=site.activity/'jobs'/case
    check((jobdir/'reserved.json').is_file() and (jobdir/'release-requested.json').is_file(),'JOB_ORDER')
    check(not (jobdir/'worker-claim.json').exists(),'WORKER_REPLAY')
    check(not (site.activity/'halt.json').exists(),'PRIOR_UNRESOLVED')
    plan=next_position(previous(site,release,case),case)
    reservation=doc(jobdir/'reserved.json')
    check(reservation==dict(plan,manifest=release.sha),'JOB_ORDER')
    submitted=doc(jobdir/'submitted.json')
    check(allocation['job']==submitted['job']==doc(jobdir/'release-requested.json')['job'] and submitted['case']==case
          and allocation['name']=='v6-study-'+case,'JOB_IDENTITY')
    check(allocation['cpus']==1 and allocation['mem_MiB']==1024 and allocation['seconds']==120 and allocation['nodes']==1
          and allocation['gpus']==0 and allocation['partition']=='cu' and allocation['restart']==0 and allocation['requeue']==0
          and allocation['state']=='RUNNING' and allocation['user']=='renly','ALLOCATION')
    try:once(jobdir/'worker-claim.json',dict(manifest=release.sha,case=case,allocation=allocation))
    except FileExistsError as exc:raise GateError('WORKER_REPLAY') from exc
    return jobdir


def worker(site,release,case,allocation,substitute=None):
    jobdir=claim_worker(site,release,case,allocation)
    receipt=dict(manifest=release.sha,case=case,job=allocation['job'],passed=False)
    try:
        ledger=execute_case(release,case,jobdir,site.purpose,substitute)
        rows=case_rows(jobdir,case);counts=case_summary(rows)
        receipt['counts']=counts
        ok=all(r['state']=='COMPLETED' for r in ledger['rows'])
        if not ok:
            receipt['failure']=next((r.get('error') for r in ledger['rows'] if r['state']=='FAILED'),'INCOMPLETE_CASE')
        else:
            check(counts['started']==counts['returned']==5 and counts['known_decisions']==100 and not counts['unknown']
                  and not counts['unknown_issues'] and not counts['accounting_errors'] and not counts['missing_raw_returns'] and counts['manual_issues']<=(24 if case=='C17' else 12),'BUDGET_EXCEEDED')
            receipt['scores']={arm:file_hash(jobdir/'arms'/(case+'-'+arm)/'score.json') for arm in ARMS}
            receipt['raw_bindings']={}
            for arm in ARMS:
                path=jobdir/'arms'/(case+'-'+arm)
                ret=doc(path/'native-return.json')
                check(file_hash(path/'run/run.json')==ret['native_sha256'],'RETURN_CHANGED')
                receipt['raw_bindings'][arm]=dict(native=ret['native_sha256'],receipt=file_hash(path/'native-return.json'),
                                                  call=file_hash(path/'call.json'),execution=file_hash(path/'execution-binding.json'))
            if case==CASES[-1]:
                scores={}
                for c in CASES:
                    where=site.activity/'jobs'/c
                    evidence=receipt if c==case else doc(where/'worker-result.json')
                    hashes=evidence['scores']
                    scores[c]={}
                    for arm in ARMS:
                        path=where/'arms'/(c+'-'+arm)/'score.json'
                        check(file_hash(path)==hashes[arm],'SCORE_IDENTITY')
                        arm_dir=path.parent
                        raw=evidence['raw_bindings'][arm]
                        for name,key in [('run/run.json','native'),('native-return.json','receipt'),('call.json','call'),('execution-binding.json','execution')]:
                            check(file_hash(arm_dir/name)==raw[key],'RETURN_CHANGED')
                        native=doc(arm_dir/'run/run.json')
                        for name in ('scenario.json','balances.jsonl','private-state.jsonl'):
                            check(file_hash(arm_dir/'run'/name)==native['artifacts'][name]['sha256'],'RETURN_CHANGED',name)
                        scores[c][arm]=doc(path)
                once(jobdir/'panel.json',panel(scores,list(CASES)))
                receipt['panel_sha256']=file_hash(jobdir/'panel.json')
            receipt['passed']=True
    except Exception:
        receipt['failure']=traceback.format_exc()
    finally:
        # A journal or score failure never converts actual native calls into zero.
        try:receipt['counts']=case_summary(case_rows(jobdir,case))
        except Exception:receipt.update(counts=None,passed=False,accounting_unresolved=True)
        once(jobdir/'worker-result.json',receipt)
    return receipt


def drive(site,release,scheduler):
    admitted(site,release)
    check(not (site.activity/'halt.json').exists(),'PRIOR_UNRESOLVED')
    try:once(site.activity/'controller.json',dict(manifest=release.sha))
    except FileExistsError as exc:raise GateError('CONTROLLER_REPLAY') from exc
    case=None
    try:
        for case in CASES:
            plan=next_position(previous(site,release,case),case)
            jobdir=site.activity/'jobs'/case
            jobdir.mkdir(mode=0o700)
            once(jobdir/'reserved.json',dict(plan,manifest=release.sha))
            job=scheduler.submit_held(case,jobdir,release)
            check(isinstance(job,str) and job.isdecimal() and int(job)>0,'JOB_IDENTITY')
            prior_ids=[doc(site.activity/'jobs'/c/'submitted.json')['job'] for c in CASES[:CASES.index(case)]]
            check(job not in prior_ids,'JOB_IDENTITY')
            once(jobdir/'submitted.json',dict(job=job,case=case))
            once(jobdir/'release-requested.json',dict(job=job))
            scheduler.release(job,case,jobdir)
            terminal=scheduler.terminal(job)
            check(terminal['job']==job,'JOB_IDENTITY')
            once(jobdir/'scheduler-terminal.json',terminal)
            check(terminal['state']=='COMPLETED' and terminal['exit']=='0:0','JOB_TERMINAL',terminal['state'])
            wr=doc(jobdir/'worker-result.json')
            check(wr['passed'] and wr['job']==job and wr['manifest']==release.sha,'WORKER_FAILED')
            files=['reserved.json','submitted.json','worker-claim.json','worker-result.json','scheduler-terminal.json','arms/ledger.json','arms/events.jsonl']
            once(jobdir/'committed.json',dict(manifest=release.sha,files={f:file_hash(jobdir/f) for f in files}))
            checkpoint(site.activity/'progress.json',snapshot(site,release))
        state=snapshot(site,release)
        check(file_hash(site.activity/'jobs/C17/panel.json')==doc(site.activity/'jobs/C17/worker-result.json')['panel_sha256'],'SCORE_IDENTITY')
        check(state['counts']['returned']==85 and state['total_decisions_exact']==1700 and state['reserved_cpu_s']==2040 and not state['counts']['unknown_issues'] and not state['counts']['missing_raw_returns']
              and not state['counts']['accounting_errors'] and state['counts']['raw_returns']==85,'BUDGET_EXCEEDED')
        once(site.activity/'finished.json',dict(manifest=release.sha,panel_sha256=doc(site.activity/'jobs/C17/worker-result.json')['panel_sha256']))
        return True
    except Exception as error:
        once(site.activity/'halt.json',dict(case=case,code=getattr(error,'code','OPERATION_UNRESOLVED'),detail=str(error),retry=False))
        try:checkpoint(site.activity/'progress.json',snapshot(site,release))
        except Exception as exc:
            once(site.activity/'accounting-unresolved.json',dict(detail=repr(exc),total_starts=None,total_decisions=None,denominator=85))
        return False


def start(site,release,authority,revision,scheduler):
    admit(site,release,authority,revision)
    return drive(site,release,scheduler)
