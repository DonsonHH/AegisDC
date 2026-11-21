"""Final read-only attempt inventory. Bind every observed entry to its original registration and job."""
from collections import Counter
from pathlib import Path
import gzip
import hashlib
import json
import os
import sys

ROOT=Path('/share/home/renly/renly-patrol-rsi/mainline/T2-minute-facility-20261121-v1')
def load(p):return json.loads(p.read_bytes())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def need(v,name):
    if not v:raise ValueError(name)


def main():
    need(os.environ.get('SLURM_JOB_ID'),'Slurm only')
    mh=sys.argv[1];ip=ROOT/'study-inputs'
    need(sha(ip/'manifest.json')==mh,'published input manifest')
    m=load(ip/'manifest.json');full=m['files'];audit=load(ROOT/'observation-scope-audit.json')
    retired={tuple(pair) for pair in audit['affected']}
    with gzip.open(ROOT/'study-results.json.gz','rt') as f:scores=json.load(f)
    final={(r['key'],k):r[k] for r in scores['rows'] for k in ('P','PERIODIC','ALARM','ORACLE')}
    group_members={}
    batch_index={}
    for d in sorted((ROOT/'batches').iterdir()):
        start=load(d/'started.json');end=load(d/'terminal.json')
        need(start['manifest']==mh and start['job']==end['job'] and
             [p[:2] for p in end['entries']]==start['ordered'],'job slots '+d.name)
        batch_index[d.name]=dict(job=start['job'],count=len(end['entries']),terminal_sha256=sha(d/'terminal.json'))
        for k,role,status in end['entries']:group_members[(start['job'],k,role)]=status
    group_members[(load(ROOT/'pilot-account.json')['repair_job'],'4-01','ORACLE')]=0
    attempts=[];seen=set()
    for f in sorted((ROOT/'positions').rglob('start.json')):
        entry=load(f);d=f.parent;k,role=entry['key'],entry['mode']
        need(entry['manifest']==mh and entry['input']==full[k],'entry request')
        need((entry['job'],k,role) in group_members and (entry['job'],entry['pid']) not in seen,'registered process')
        seen.add((entry['job'],entry['pid']))
        source=final[k,role]
        kept=(source['pid'],source['job'])==(entry['pid'],entry['job'])
        raw=d/'original.jsonl.gz';score=d/'result.json';meta_clock=None
        if raw.is_file():
            with gzip.open(raw,'rt') as stream:meta=json.loads(next(stream))['metadata']
            historical=load(ip/(k+'.json'))['native']
            need(meta['inputs']['boundary_events']==sorted(historical['boundary_events'],key=lambda e:e['time_s'])
                 and meta['inputs']['dispatch_program']==historical['dispatch_program'] and
                 meta['source_config']==historical['scenario'] and meta['inputs']['maximum_step_s']==.25
                 and [x['view']['time'] for x in meta['policy_public_decisions']]==list(range(0,3601,60)),
                 'archived original binding '+k+' '+role)
            meta_clock=61
        if kept:
            need(raw.is_file() and score.is_file() and sha(score)==source['score_sha256'] and
                 group_members[(entry['job'],k,role)]==0,'final position')
            state='FINAL'
        elif (k,role) in retired:
            need(raw.is_file() and d==ROOT/'positions'/(k+'-'+role),'preserve superseded acquisition')
            state='SUPERSEDED_REPEATED_PAID_MEASUREMENT'
        else:
            need(k=='4-01' and role=='ORACLE' and entry['job']=='134753' and not raw.exists()
                 and not score.exists(),'unexpected unarchived return')
            state='FAILED_BEFORE_NATIVE_ARCHIVE'
        attempts.append(dict(key=k,role=role,job=entry['job'],pid=entry['pid'],state=state,
            path=d.relative_to(ROOT).as_posix(),start_sha256=sha(f),saved_score=score.is_file(),archived_clock=meta_clock))
    count=Counter(x['state'] for x in attempts)
    need(count=={'FINAL':192,'SUPERSEDED_REPEATED_PAID_MEASUREMENT':7,'FAILED_BEFORE_NATIVE_ARCHIVE':1},'attempt counts')
    panel=load(ROOT/'panel-identity.json')
    visits=panel['route_visits_per_position']
    # Four paid routes of two stations must each fit its own quarter-hour interval.
    need(sum(visits.values())==48,'route denominator')
    short_routes=[]
    for (key,role),one in final.items():
        if role!='PERIODIC':continue
        actual=[v[2] for v in one['issues'] if v[2] is not None]
        if len(actual)<8:
            planned=load(ROOT/'study-inputs'/(key+'.json'))['public']['duty_route']
            short_routes.append(dict(key=key,visited=actual,missing=planned[len(actual):],recorded_denials=one['denials']))
    amendments={}
    pk=ROOT/'C-source/docs/mainline/t2-minute-facility-v1/production'
    for n in ('execution-amendment.json','observation-amendment.json'):
        a=load(pk/n);files=a.get('checksums',a.get('source_sha256'))
        for path,want in files.items():need(sha(pk/path)==want,'repair tool identity '+path)
        amendments[n]=sha(pk/n)
    out=dict(roles=dict(Counter(x['role'] for x in attempts if x['state']=='FINAL')),
        states=dict(count),all_native_starts=len(attempts),raw_originals_with_clock=sum(x['archived_clock'] is not None for x in attempts),
        validated_clock_count=192*61,additional_archived_clock_count=7*61,unknown_clock_for_unarchived_pilot=1,
        scientific_inputs_unchanged=48,short_routes=short_routes,attempts=attempts,batches=batch_index,amendments=amendments)
    with (ROOT/'attempt-inventory.json').open('x') as stream:json.dump(out,stream,separators=(',',':'))
    print('attempt ledger',dict(count),'complete routes',visits,flush=True)


if __name__=='__main__':main()
