"""Separate research-only child boundary; engineering allowlists stay immutable."""
from pathlib import Path
import os
import subprocess
import sys
import time
from unittest.mock import patch

from cold3_evaluation import score_arm, compare_pair
from cold3_runner import digest, read, save, sha
from aegis_dc.native_compare_run import note
from v6_research.control import once, doc
from .binding import REAL, SURROGATE, GateError, check, verify_item
from .ledger import clock_count
from .transport import argv


def runtime_files(rel):
    return {p:h for p,h in rel.manifest['core_files'].items() if p.startswith('src/aegis_dc/') or p=='src/patrol_rsi/contracts.py'}


def count_end(unit,key,rel,n):
    once(unit/'clock-end.json',dict(slot=key,launch=rel.sha,calls=n,journal_sha256=sha(unit/'decisions.jsonl')))


def entry_record(rel,site,key,job,input_id):
    return dict(slot=key,launch=rel.sha,purpose=site.purpose,job=job,input_sha256=input_id,pid=os.getpid(),parent=os.getppid())


def envelope(rel,site,key,job,request_hash,evidence_hash,raw_hash,count):
    return dict(schema='cold-isolated-return-v1',slot=key,job=job,purpose=site.purpose,launch=rel.sha,
        pid=os.getpid(),parent=os.getppid(),request_sha256=request_hash,evidence_sha256=evidence_hash,
        raw_sha256=raw_hash,internal=count)


def child_admission(rel,site,case,key,allocation):
    from .control import admitted, verify_worker_identity
    admitted(site,rel)
    folder=verify_worker_identity(site,rel,case,allocation,claimed=True)
    order=rel.keys(case);check(key in order,'SLOT_ORDER')
    for prior in order[:order.index(key)]:
        p=folder/'arms'/prior
        check((p/'scored.json').is_file() and doc(p/'scored.json')['status']=='OK' and
              sha(p/'score.json.gz')==doc(p/'scored.json')['score_sha256'],'PRIOR_UNRESOLVED')
    unit=folder/'arms'/key;item=read(unit/'input.json');verify_item(rel,case,key,item)
    binding=doc(unit/'prelaunch.json')
    check(binding==dict(slot=key,launch=rel.sha,purpose=site.purpose,job=allocation['job'],request_sha256=digest(item),
        command=argv(rel,'arm',row=case,slot=key)),'PRELAUNCH_IDENTITY')
    check(not (unit/'entry.json').exists(),'ARM_REPLAY')
    deadline=time.monotonic()+10
    while not (unit/'spawn.json').is_file() and time.monotonic()<deadline:
        time.sleep(.01)
    check((unit/'spawn.json').is_file(),'SPAWN_IDENTITY')
    spawn=doc(unit/'spawn.json')
    check(spawn==dict(slot=key,launch=rel.sha,pid=os.getpid(),parent=os.getppid()),'SPAWN_IDENTITY')
    return unit,item


def real_child(rel,site,case,key,allocation):
    from .binding import host
    check(site.purpose==REAL,'PURPOSE');host(rel.root,False)
    unit,item=child_admission(rel,site,case,key,allocation)
    # No native or policy function is imported by the surrogate transport.
    from aegis_dc import joint_session
    from aegis_dc.plant import simulate_scenario
    cfg=item['dispatch_program']['policy_program'];original=joint_session.choose;n=0
    def counted(program,view):
        nonlocal n
        check(n<49 and view['time']==cfg['clock'][n] and program==cfg,'INTERNAL_CLOCK')
        n+=1;note(unit/'decisions.jsonl',dict(slot=key,n=n,at=view['time']))
        check(set(view)=={'time','orders','issued','work','writes','paid','fixed'} and
              all(r['arrived']<=view['time'] for channel in ('orders','work','writes','paid','fixed') for r in view[channel]),'PUBLIC_BOUNDARY')
        choice=original(program,view)
        req=choice['request']
        if req:check(choice['selected']['admitted'] and req['at']==view['time'] and
                     (cfg['method']!='J_NO_PROBE' or not req['task'].endswith('/I')),'NATIVE_ADMISSION')
        return choice
    with patch.object(joint_session,'choose',counted):
        once(unit/'entry.json',entry_record(rel,site,key,allocation['job'],digest(item)))
        run=simulate_scenario(item['scenario'],duration_s=12,step_s=.01,dispatch_program=item['dispatch_program'],private_physical_audit=True)
    count_end(unit,key,rel,n)
    save(unit/'run.json.gz',run)
    once(unit/'return.json',envelope(rel,site,key,allocation['job'],digest(item),digest(item),sha(unit/'run.json.gz'),n))


def validate_native(rel,site,case,key,unit,item,evidence,job,child_pid):
    verify_item(rel,case,key,item)
    try:ret=doc(unit/'return.json')
    except (ValueError,TypeError,FileNotFoundError) as e:raise GateError('MALFORMED_RETURN') from e
    check(type(ret) is dict and ret.get('schema')=='cold-isolated-return-v1','MALFORMED_RETURN')
    entry=doc(unit/'entry.json');binding=digest(item)
    check(ret.get('slot')==key and ret.get('purpose')==site.purpose and ret.get('job')==job and ret.get('launch')==rel.sha and
          ret.get('pid')==child_pid==entry['pid'] and ret.get('parent')==os.getpid()==entry['parent'] and
          entry['slot']==key and entry['input_sha256']==binding and entry['purpose']==site.purpose and
          entry['launch']==rel.sha and entry['job']==job,'RETURN_BINDING')
    check(ret.get('request_sha256')==binding and ret.get('evidence_sha256')==digest(evidence),'RETURN_INPUT')
    check(site.purpose!=REAL or binding==digest(evidence),'RETURN_INPUT')
    raw=unit/'run.json.gz';check(raw.is_file() and sha(raw)==ret.get('raw_sha256'),'RAW_IDENTITY')
    try:run=read(raw)
    except (OSError,EOFError,ValueError) as exc:raise GateError('MALFORMED_RETURN','raw body') from exc
    check(isinstance(run,dict) and run.get('schema')=='aegisdc-engineering-facility-run-v1','MALFORMED_RETURN')
    src=run.get('code_identity',{});files=runtime_files(rel)
    check(src.get('files')==files and src.get('source_tree_sha256')==digest(files)==rel.manifest['core_tree'],'RETURN_SOURCE')
    inp=run.get('inputs',{})
    check(digest(run.get('source_config'))==digest(evidence['scenario'])==run.get('scenario_sha256') and
          digest(inp.get('dispatch_program'))==digest(evidence['dispatch_program']) and
          inp.get('boundary_events')==evidence['boundary_events']==[] and inp.get('action_commands',[])==evidence['action_commands']==[] and
          inp.get('work_requests',[])==evidence['work_requests']==[] and inp.get('business_program') is None and
          'business_evaluation' not in run and inp.get('private_physical_audit') is True and
          inp.get('duration_s')==run.get('summary',{}).get('duration_s')==12 and inp.get('maximum_step_s')==.01,'RETURN_INPUT')
    decisions=run.get('policy_public_decisions');errors=[]
    lower,exact=clock_count(unit,key,rel.sha,errors)
    check(not errors and type(ret.get('internal')) is int and ret['internal']==exact==lower==49 and
          isinstance(decisions,list) and len(decisions)==49 and all(isinstance(d,dict) and isinstance(d.get('decision'),dict)
          and type(d.get('view',{}).get('time')) in (int,float) and d['view']['time']==i/4 for i,d in enumerate(decisions)),'INTERNAL_COUNT_UNKNOWN')
    work=run.get('work_records')
    check(isinstance(work,list) and all(isinstance(w,dict) and isinstance(w.get('id'),str) for w in work)
          and isinstance(run.get('trace'),list) and isinstance(run.get('balances'),list) and len(run['trace'])==1+len(run['balances'])
          and len(run['balances'])>0 and run['trace'][0]['time_s']==0 and run['trace'][-1]['time_s']==12,'MALFORMED_RETURN')
    return run,dict(slot=key,launch=rel.sha,request_sha256=binding,evidence_sha256=digest(evidence),raw_sha256=ret['raw_sha256'],
                    return_sha256=sha(unit/'return.json'),calls=exact,issues=len(work),pid=child_pid,clock_sha256=sha(unit/'decisions.jsonl'))


def disposition(result):
    cat=result['category']
    if cat=='NONCOMPLIANT':return 'HARD_NONCOMPLIANT'
    if cat=='NO_PAIR':return 'MISSING_PAIR'
    if cat=='NUMERIC_UNRESOLVED' and result.get('reason'):return 'QUALIFICATION_UNRESOLVED'
    check(cat in ('SAME','BETTER','WORSE','NUMERIC_UNRESOLVED'),'PAIR_SHAPE')
    return 'CONTINUE'


def archived_score(folder,key,rel):
    unit=folder/'arms'/key;s=doc(unit/'scored.json');v=doc(unit/'validated.json')
    check(s['slot']==v['slot']==key and s['launch']==v['launch']==rel.sha and s['validated_sha256']==sha(unit/'validated.json') and
          sha(unit/'score.json.gz')==s['score_sha256'] and sha(unit/'run.json.gz')==v['raw_sha256'] and
          sha(unit/'return.json')==v['return_sha256'] and digest(read(unit/'input.json'))==v['request_sha256'],'ARCHIVE_IDENTITY',key)
    return read(unit/'score.json.gz')


def run_slot(rel,site,case,key,unit,job,substitute):
    """Both modes use the same intent -> process -> raw -> score -> pair interface."""
    item=rel.inputs[key];verify_item(rel,case,key,item)
    if site.purpose==REAL:check(substitute is None,'PURPOSE')
    else:check(site.purpose==SURROGATE and substitute is not None,'PURPOSE')
    request=digest(item);evidence=item if substitute is None else substitute.evidence(key)
    save(unit/'input.json',item)
    command=argv(rel,'arm',row=case,slot=key)
    actual=command if substitute is None else substitute.command(rel,site,case,key,unit,job,command)
    once(unit/'command.json',dict(proposed=command,executed=actual))
    once(unit/'prelaunch.json',dict(slot=key,launch=rel.sha,purpose=site.purpose,job=job,request_sha256=request,command=command))
    note(unit.parent/'events.jsonl',dict(slot=key,event='BEFORE_LAUNCH',input_sha256=request))
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1',OPENBLAS_NUM_THREADS='1',
             OMP_NUM_THREADS='1',GIT_CEILING_DIRECTORIES=str(rel.root.parent))
    with (unit/'stdout.log').open('xb') as so,(unit/'stderr.log').open('xb') as se:
        with subprocess.Popen(actual,cwd=rel.root,env=env,stdout=so,stderr=se) as child:
            once(unit/'spawn.json',dict(slot=key,launch=rel.sha,pid=child.pid,parent=os.getpid()))
            code=child.wait()
    once(unit/'exit.json',dict(pid=child.pid,code=code))
    check(code==0,'CHILD_EXIT',code)
    run,validated=validate_native(rel,site,case,key,unit,item,evidence,job,child.pid)
    once(unit/'validated.json',validated)
    score=score_arm(evidence,run)
    check(sha(unit/'run.json.gz')==validated['raw_sha256'],'RAW_IDENTITY')
    try:save(unit/'score.json.gz',score)
    except FileExistsError as e:raise GateError('ARCHIVE_EXISTS','score') from e
    once(unit/'scored.json',dict(slot=key,launch=rel.sha,status=score['status'],score_sha256=sha(unit/'score.json.gz'),
                               validated_sha256=sha(unit/'validated.json')))
    folder=unit.parent.parent;keys=rel.keys(case);reason=None
    if key!=keys[0]:
        pair=compare_pair(archived_score(folder,keys[0],rel),score)
        once(folder/'pairs'/(key+'.json'),dict(left=keys[0],right=key,launch=rel.sha,result=pair))
        policy=disposition(pair)
        if policy!='CONTINUE':reason=policy
    if score['violations'] or score['status']=='NONCOMPLIANT':reason='HARD_NONCOMPLIANT'
    elif score['status']!='OK':reason=reason or 'QUALIFICATION_UNRESOLVED'
    if reason:raise GateError(reason,key)
    return dict(slot=key,status='RETURNED',pid=child.pid,raw_sha256=validated['raw_sha256'])
