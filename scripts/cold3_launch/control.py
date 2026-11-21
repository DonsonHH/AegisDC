"""Manifest-shaped one-use admission and held, serial cold study dispatch."""
import os
from pathlib import Path
import traceback

from aegis_dc.native_compare_run import checkpoint
from cold3_runner import execute_group, sha, digest
from v6_research.control import once, doc
from .binding import REAL, SURROGATE, ACCEPT_SHA, Review, GateError, bind_grant, check, host
from .ledger import slot_state, summary
from .native import archived_score, run_slot
from .transport import ColdSlurm


def admit(site,rel,authority,revision):
    check(revision is not None,'AUTHORIZATION_REQUIRED')
    site.validate()
    if site.purpose==REAL:
        host(rel.root,True);check(type(authority) is Review,'PURPOSE')
    proof=authority.authorize(rel,revision,site)
    grant=bind_grant(rel,site,proof['grant'])
    check(proof['review_revision']==revision and proof['grant_digest']==digest(grant) and proof['launch_sha256']==rel.sha,'GRANT_BINDING')
    check(not os.path.lexists(site.claim),'GRANT_CONSUMED')
    check(not os.path.lexists(site.activity),'OUTPUT_EXISTS')
    site.claim.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    try:site.claim.mkdir(mode=0o700)
    except FileExistsError as e:raise GateError('GRANT_CONSUMED') from e
    receipt=dict(study=site.activity.name,activity=str(site.activity),purpose=site.purpose,approval=proof,
                 launch=rel.sha,acceptance_sha256=ACCEPT_SHA)
    once(site.claim/'consumption.json',receipt)
    try:site.activity.mkdir(mode=0o700)
    except FileExistsError as e:raise GateError('OUTPUT_EXISTS','consumption retained') from e
    once(site.activity/'admission.json',receipt);(site.activity/'jobs').mkdir(mode=0o700)
    once(site.activity/'binding.json',dict(launch=rel.sha,consumption_sha256=sha(site.claim/'consumption.json')))
    return receipt


def admitted(site,rel):
    site.validate()
    check((site.claim/'consumption.json').is_file() and (site.activity/'binding.json').is_file(),'NO_CONSUMPTION')
    binding=doc(site.activity/'binding.json');proof=doc(site.claim/'consumption.json')
    check(binding['launch']==proof['launch']==rel.sha and binding['consumption_sha256']==sha(site.claim/'consumption.json')
          and (site.claim/'consumption.json').read_bytes()==(site.activity/'admission.json').read_bytes(),'CONSUMPTION_IDENTITY')
    check(proof['activity']==str(site.activity) and proof['purpose']==site.purpose and proof['acceptance_sha256']==ACCEPT_SHA and
          proof['approval']['launch_sha256']==rel.sha and proof['approval']['grant_digest']==digest(proof['approval']['grant']),'CONSUMPTION_IDENTITY')
    bind_grant(rel,site,proof['approval']['grant'])


def reservation(site,rel,case):
    index=rel.cases.index(case);starts=calls=0
    for prev in rel.cases[:index]:
        folder=site.activity/'jobs'/prev
        check((folder/'committed.json').is_file(),'PRIOR_UNRESOLVED')
        seal=doc(folder/'committed.json')
        for name in ('worker-result','scheduler-terminal','reserved','submitted','release-requested','worker-claim'):
            check(sha(folder/(name+'.json'))==seal[name.replace('worker-result','worker').replace('scheduler-terminal','terminal')+'_sha256'],'ARCHIVE_IDENTITY',prev)
        w=doc(folder/'worker-result.json');term=doc(folder/'scheduler-terminal.json');keys=rel.keys(prev)
        check(seal['launch']==w['launch']==rel.sha and w['row']==prev and w['passed'] and
              term['job']==w['job'] and term['state']=='COMPLETED' and term['exit']=='0:0','PRIOR_UNRESOLVED')
        check([r['slot'] for r in w['rows']]==keys and all(r['known'] and r['validated'] and r['scored'] and
            r['internal_exact']==49 and not r['errors'] for r in w['rows']),'PRIOR_UNRESOLVED')
        starts+=len(keys);calls+=sum(r['internal_exact'] for r in w['rows'])
    slots=rel.keys(case);lim=rel.data['limits']
    check(index+1<=lim['jobs'] and starts+len(slots)<=lim['facility_arms'] and calls+49*len(slots)<=lim['internal_policy_calls']
          and (index+1)*300<=lim['total_reserved_CPU_s'],'BUDGET_EXCEEDED')
    return dict(index=index,row=case,slots=slots,arm_cap=len(slots),decision_cap=49*len(slots),reserved_cpu_s=300,
                predecessor_starts=starts,predecessor_calls=calls,launch=rel.sha)


def verify_worker_identity(site,rel,case,alloc,claimed=False):
    admitted(site,rel);check(case in rel.cases,'WORKER_ORDER')
    folder=site.activity/'jobs'/case
    check((folder/'reserved.json').is_file() and (folder/'release-requested.json').is_file(),'WORKER_ORDER')
    if not claimed:check(not (folder/'worker-claim.json').exists(),'WORKER_REPLAY')
    check(not (site.activity/'halt.json').exists() and not (site.activity/'finished.json').exists(),'PRIOR_UNRESOLVED')
    check(doc(folder/'reserved.json')==reservation(site,rel,case),'WORKER_ORDER')
    submission=doc(folder/'submitted.json')
    check(alloc['job']==submission['job']==doc(folder/'release-requested.json')['job'] and submission['row']==case
          and alloc['name']=='cold3-study-'+case,'JOB_IDENTITY')
    check(alloc['partition']=='cu' and alloc['cpus']==alloc['nodes']==1 and alloc['seconds']==300 and alloc['mem_mib']==4096
          and alloc['gpus']==alloc['requeue']==alloc['restarts']==0 and alloc['state']=='RUNNING' and alloc['user']=='renly','ALLOCATION')
    claim=dict(launch=rel.sha,row=case,allocation=alloc)
    if claimed:check(doc(folder/'worker-claim.json')==claim,'WORKER_CLAIM')
    else:
        try:once(folder/'worker-claim.json',claim)
        except FileExistsError as e:raise GateError('WORKER_REPLAY') from e
    return folder


def worker(site,rel,case,alloc,substitute=None):
    if site.purpose==REAL:
        host(rel.root,False);check(substitute is None,'PURPOSE')
    else:check(site.purpose==SURROGATE and substitute is not None,'PURPOSE')
    folder=verify_worker_identity(site,rel,case,alloc)
    arms=folder/'arms';arms.mkdir();(folder/'pairs').mkdir()
    order=rel.keys(case);errors=[];code=None
    def start(key,unit):
        nonlocal code
        try:return run_slot(rel,site,case,key,unit,alloc['job'],substitute)
        except Exception as exc:
            code=getattr(exc,'code','ARCHIVE_IO' if isinstance(exc,OSError) else 'OPERATION_UNRESOLVED')
            once(unit/'arm-error.json',dict(code=code,detail=str(exc),retry=False))
            raise
    try:
        group=execute_group(arms,order,start)
        check(group['status']=='ALL_RETURNED',code or 'WORKER_FAILED')
        for key in order:
            checked=archived_score(folder,key,rel)
            check(checked['status']=='OK' and not checked['violations'],'HARD_NONCOMPLIANT')
    except Exception as exc:
        code=code or getattr(exc,'code','OPERATION_UNRESOLVED');errors.append(traceback.format_exc())
    slots=[slot_state(folder,k,rel) for k in order]
    pair_hashes={k:sha(folder/'pairs'/(k+'.json')) for k in order[1:] if (folder/'pairs'/(k+'.json')).is_file()}
    if not code and (len(pair_hashes)!=len(order)-1 or any(r['state']!='RETURNED' or r['internal_exact']!=49 for r in slots)):
        code='WORKER_ACCOUNTING'
    arm_hashes={}
    for key in order:
        unit=arms/key
        arm_hashes[key]={name:sha(unit/name) for name in
            ('input.json','prelaunch.json','entry.json','spawn.json','exit.json','clock-end.json','return.json','validated.json','scored.json')
            if (unit/name).is_file()}
        if (unit/'validated.json').is_file():arm_hashes[key]['run.json.gz']=doc(unit/'validated.json')['raw_sha256']
        if (unit/'scored.json').is_file():arm_hashes[key]['score.json.gz']=doc(unit/'scored.json')['score_sha256']
    panel_hash=None
    if code is None and case==rel.cases[-1]:
        try:
            for prior in rel.cases:
                where=site.activity/'jobs'/prior
                seals=arm_hashes if prior==case else doc(where/'worker-result.json')['arm_hashes']
                for key in rel.keys(prior):
                    unit=where/'arms'/key
                    for name,h in seals[key].items():check(sha(unit/name)==h,'ARCHIVE_IDENTITY',key+'/'+name)
            state=summary(site,rel,deep=True)
            check(state['scored']==66 and state['validated_returns']==66 and len(state['paired'])==42 and not state['accounting_errors'],'FINAL_ACCOUNT')
            once(folder/'panel.json',state['panel']);panel_hash=sha(folder/'panel.json')
        except Exception as exc:
            code=getattr(exc,'code','ARCHIVE_IO');errors.append(traceback.format_exc())
    result=dict(launch=rel.sha,row=case,job=alloc['job'],passed=code is None,code=code,rows=slots,pair_hashes=pair_hashes,
        arm_hashes=arm_hashes,panel_sha256=panel_hash,errors=errors)
    once(folder/'worker-result.json',result)
    return result


def persist_progress(site,rel):
    state=summary(site,rel)
    checkpoint(site.activity/'progress.json',state)
    return state


def drive(site,rel,scheduler):
    admitted(site,rel)
    if site.purpose==REAL:host(rel.root,True);check(type(scheduler) is ColdSlurm,'PURPOSE')
    try:once(site.activity/'controller.json',dict(launch=rel.sha))
    except FileExistsError as e:raise GateError('CONTROLLER_REPLAY') from e
    case=None
    try:
        for case in rel.cases:
            plan=reservation(site,rel,case);folder=site.activity/'jobs'/case;folder.mkdir()
            once(folder/'reserved.json',plan)
            try:job=scheduler.submit_held(case,folder,rel)
            except Exception as exc:raise GateError('SUBMIT_UNKNOWN',str(exc)) from exc
            existing=[doc(site.activity/'jobs'/key/'submitted.json')['job'] for key in rel.cases[:plan['index']]]
            check(isinstance(job,str) and job.isdecimal() and int(job)>0 and job not in existing,'SUBMIT_UNKNOWN')
            once(folder/'submitted.json',dict(row=case,job=job))
            once(folder/'release-requested.json',dict(row=case,job=job))
            try:scheduler.release(job,case,folder)
            except Exception as exc:raise GateError('RELEASE_UNKNOWN',str(exc)) from exc
            terminal=scheduler.terminal(job);check(terminal['job']==job,'JOB_IDENTITY')
            once(folder/'scheduler-terminal.json',terminal)
            check(terminal['state']!='UNRESOLVED' and not terminal.get('live',False),'SCHEDULER_UNKNOWN')
            check((folder/'worker-result.json').is_file(),'WORKER_UNRETURNED')
            wr=doc(folder/'worker-result.json')
            check(wr['launch']==rel.sha and wr['job']==job and wr['row']==case,'WORKER_IDENTITY')
            check(wr['passed'],wr.get('code') or 'WORKER_FAILED')
            check(terminal['state']=='COMPLETED' and terminal['exit']=='0:0','JOB_TERMINAL')
            files={'worker':'worker-result','terminal':'scheduler-terminal','reserved':'reserved','submitted':'submitted',
                   'release-requested':'release-requested','worker-claim':'worker-claim'}
            once(folder/'committed.json',dict(launch=rel.sha,**{k+'_sha256':sha(folder/(v+'.json')) for k,v in files.items()}))
            persist_progress(site,rel)
        state=summary(site,rel,deep=True)
        check(state['committed_jobs']==24 and state['starts_exact']==state['validated_returns']==state['scored']==66 and
              state['internal_exact']==3234 and state['reserved_cpu_s']==7200 and state['panel']['denominators']==rel.manifest['denominators']
              and len(state['paired'])==42 and not state['accounting_errors'],'FINAL_ACCOUNT')
        last=site.activity/'jobs'/rel.cases[-1]
        check(doc(last/'worker-result.json')['panel_sha256']==sha(last/'panel.json') and doc(last/'panel.json')==state['panel'],'PANEL_IDENTITY')
        once(site.activity/'panel.json',state['panel'])
        once(site.activity/'finished.json',dict(launch=rel.sha,purpose=site.purpose,panel_sha256=sha(site.activity/'panel.json'),counts=[24,66,3234,7200]))
        persist_progress(site,rel)
        return True
    except Exception as exc:
        once(site.activity/'halt.json',dict(row=case,code=getattr(exc,'code','SCHEDULER_UNKNOWN' if case and
            not (site.activity/'jobs'/case/'scheduler-terminal.json').exists() else 'OPERATION_UNRESOLVED'),detail=str(exc),retry=False))
        try:persist_progress(site,rel)
        except Exception as err:once(site.activity/'account-unresolved.json',dict(error=repr(err),starts_exact=None,internal_exact=None,slots=rel.slots))
        return False


def start(site,rel,review,revision,scheduler):
    admit(site,rel,review,revision)
    return drive(site,rel,scheduler)
