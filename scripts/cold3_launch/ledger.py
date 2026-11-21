"""Reconcile admission, process, arm and internal-call facts without inferring absent returns."""
from pathlib import Path
from cold3_evaluation import panel
from cold3_runner import sha
from v6_research.binding import load_json
from v6_research.control import doc
from .binding import SURROGATE, check


def safe_file(path,errors):
    if not path.is_file():return None
    try:return doc(path)
    except (OSError,ValueError) as exc:
        errors.append(path.name+': '+str(exc));return None


def fingerprint(path):
    x=path.stat()
    return [x.st_size,x.st_mtime_ns,x.st_ctime_ns,x.st_ino]


def retained(unit,hashes,stats,deep=False):
    faults=[]
    for name,h in hashes.items():
        p=unit/name
        try:
            if not p.is_file() or ((deep or stats.get(name)!=fingerprint(p)) and sha(p)!=h):
                faults.append('missing/changed '+name)
        except OSError as exc:faults.append(name+': '+str(exc))
    return faults


def clock_count(path,slot,launch,errors):
    journal=path/'decisions.jsonl';n=0
    if journal.is_file():
        try:
            for line in journal.read_bytes().splitlines():
                e=load_json(line)
                check(type(e.get('n')) is int and type(e.get('at')) in (int,float) and e=={'slot':slot,'n':n+1,'at':n/4} and n<49,'INTERNAL_LEDGER')
                n+=1
        except (KeyError,TypeError,OSError,ValueError) as exc:errors.append('decisions: '+str(exc))
    end=safe_file(path/'clock-end.json',errors)
    exact=None
    if end is not None:
        if (end.get('slot')==slot and end.get('launch')==launch and type(end.get('calls')) is int and
            end['calls']==n and journal.is_file() and end.get('journal_sha256')==sha(journal)):
            exact=n
        else:errors.append('clock-end binding')
    return n,exact


def slot_state(folder,slot,rel):
    errors=[];path=folder/'arms'/slot
    entry=safe_file(path/'entry.json',errors);pre=(path/'prelaunch.json').is_file()
    spawned=safe_file(path/'spawn.json',errors);raw=(path/'run.json.gz').is_file()
    returned=safe_file(path/'validated.json',errors);score=safe_file(path/'scored.json',errors)
    known=bool(entry and entry.get('slot')==slot and entry.get('launch')==rel.sha)
    if entry is not None and not known:errors.append('invalid entry binding')
    uncertain=not known and (pre or spawned is not None)
    lower,exact=clock_count(path,slot,rel.sha,errors) if path.exists() else (0,None)
    valid=bool(returned and returned.get('slot')==slot and returned.get('launch')==rel.sha and known)
    scored=bool(score and score.get('slot')==slot and score.get('launch')==rel.sha and valid)
    if scored and not (path/'score.json.gz').is_file():errors.append('missing score archive')
    if valid and not raw:errors.append('missing native archive')
    if returned and not valid:errors.append('invalid return receipt')
    if score and not scored:errors.append('invalid score receipt')
    if valid and returned.get('calls')!=exact:errors.append('return and clock disagree')
    state=('RETURNED' if scored and not errors else 'SAVED_EVIDENCE_UNAVAILABLE' if errors else 'RETURNED_NOT_SCORED' if valid
           else 'RAW_UNVALIDATED' if known and raw else 'STARTED_UNRETURNED' if known else
           'ENTRY_UNKNOWN' if uncertain else 'FAILED_BEFORE_LAUNCH' if (path/'failure.txt').exists() else 'UNEXECUTED')
    return dict(slot=slot,state=state,known=known,spawned=spawned is not None,pid=entry.get('pid') if known else None,
        potential=uncertain,raw=raw,validated=valid,scored=scored,internal_lower=lower,internal_exact=exact,
        manual=returned.get('issues') if valid else None,errors=errors)


def summary(site,rel,deep=False):
    positions=[];jobs=[];pairs={};potential=[];unknown_submit=[];unknown_terminal=[];errors=[]
    for g in rel.data['groups']:
        case=g['row'];keys=rel.keys(case);folder=site.activity/'jobs'/case
        reserved=(folder/'reserved.json').is_file()
        submitted=safe_file(folder/'submitted.json',errors);terminal=safe_file(folder/'scheduler-terminal.json',errors)
        requested=(folder/'release-requested.json').exists();committed=(folder/'committed.json').is_file()
        wr=safe_file(folder/'worker-result.json',errors)
        water={};sealed=False
        if wr:
            sealed=(wr.get('row')==case and wr.get('launch')==rel.sha and submitted and wr.get('job')==submitted.get('job')
                    and [r['slot'] for r in wr.get('rows',[])]==keys)
            if sealed:water={r['slot']:r for r in wr['rows']}
            else:errors.append(case+' worker binding')
        if committed:
            commit=safe_file(folder/'committed.json',errors)
            if not commit or not wr or commit.get('worker_sha256')!=sha(folder/'worker-result.json') or not terminal or commit.get('terminal_sha256')!=sha(folder/'scheduler-terminal.json'):
                errors.append(case+' commit changed')
        for slot in keys:
            if sealed:
                r=dict(water[slot]);unit=folder/'arms'/slot
                faults=retained(unit,wr['arm_hashes'][slot],wr.get('file_stats',{}).get(slot,{}),deep)
                if faults:
                    r.update(state='SAVED_EVIDENCE_UNAVAILABLE',raw=(unit/'run.json.gz').is_file(),
                             errors=[*r['errors'],*faults,'sealed start, return and clock subtotals retained'])
            else:r=slot_state(folder,slot,rel)
            if requested and not sealed and r['state']=='UNEXECUTED' and not (terminal and terminal.get('state') in ('FAILED','TIMEOUT','OUT_OF_MEMORY','CANCELLED')):
                r.update(state='JOB_UNRESOLVED',potential=True)
            if r['potential']:potential.append(slot)
            if r['errors']:errors.extend(slot+':'+str(err) for err in r['errors'])
            positions.append(r)
        for name in keys[1:]:
            fp=folder/'pairs'/(name+'.json')
            value=safe_file(fp,errors)
            if value and value.get('launch')==rel.sha and value.get('left')==keys[0] and value.get('right')==name:
                if sealed and wr['pair_hashes'].get(name)!=sha(fp):errors.append(name+' pair seal')
                else:pairs[name]=value['result']
            elif value:errors.append(name+' pair identity')
            elif sealed and name in wr['pair_hashes']:errors.append(name+' missing pair')
        if reserved:
            if submitted is None:unknown_submit.append(case)
            if requested and (not terminal or terminal.get('state')=='UNRESOLVED'):unknown_terminal.append(case)
            jobs.append(dict(row=case,id=submitted.get('job') if submitted else None,released=requested,
                worker_sealed=bool(sealed),committed=committed,terminal=terminal))
    started=sum(r['known'] for r in positions);lower=sum(r['internal_lower'] for r in positions)
    unknown=[r['slot'] for r in positions if r['known'] and r['internal_exact'] is None]
    unknown_manual=[r['slot'] for r in positions if r['known'] and r['manual'] is None]
    mapped={r['slot']:r['state'] for r in positions}
    plan=[dict(id=g['row'],arms=[s['arm'] for s in g['positions']]) for g in rel.data['groups']]
    classified=panel(plan,pairs,mapped)
    return dict(launch_sha256=rel.sha,purpose=site.purpose,rows=positions,jobs=jobs,panel=classified,archived_pairs={k:v['category'] for k,v in pairs.items()},
        paired={k:v['category'] for k,v in pairs.items() if mapped[k]=='RETURNED' and mapped[k.split('-')[0]+'-J']=='RETURNED'},
        reservations=len(jobs),submitted=sum(j['id'] is not None for j in jobs),submissions_exact=None if unknown_submit else len(jobs),
        unknown_submission_ids=unknown_submit,unresolved_scheduler=unknown_terminal,committed_jobs=sum(j['committed'] for j in jobs),
        reserved_cpu_s=300*len(jobs),known_starts=started,starts_exact=None if potential or errors else started,
        raw_present=sum(r['raw'] for r in positions),validated_returns=sum(r['validated'] for r in positions),scored=sum(r['scored'] for r in positions),
        known_internal=lower,internal_exact=None if potential or unknown or errors else lower,unknown_internal=unknown,
        validated_without_raw=[r['slot'] for r in positions if r['validated'] and not r['raw']],
        known_manual=sum(r['manual'] for r in positions if type(r['manual']) is int),unknown_manual=unknown_manual,
        manual_exact=None if unknown_manual or potential or errors else sum(r['manual'] or 0 for r in positions),
        potential_slots=potential,known_unstarted=[r['slot'] for r in positions if not r['known'] and not r['potential']],
        accounting_errors=errors,real_research_entries=0 if site.purpose==SURROGATE else None if potential or errors else started)
