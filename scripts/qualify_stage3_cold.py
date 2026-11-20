"""Bounded Slurm engineering qualification; the separate study archive is never used for native launches."""
from collections import Counter
from fractions import Fraction
from pathlib import Path
import os
import sys
import traceback

from cold3_runner import ROOT,PK,digest,read,save,sha,journal,release,engineering_admit,native_parent,execute_group,phase_units
from cold3_evaluation import score_arm,compare_pair,panel,service_direction,TYPES

DIMS=('facility','internal','direct','component')


class Meter:
    def __init__(self,out,limits):
        self.out=out;self.limits=limits;self.counts=Counter()
    def enter(self,key,kind):
        if self.counts[kind]>=self.limits.get(kind,0):raise PermissionError('PHASE_CAP '+kind)
        journal(self.out,key,kind);self.counts[kind]+=1


def same(a,b):
    if isinstance(b,bool) or isinstance(a,bool):return type(a)==type(b) and a==b
    if isinstance(b,dict):return isinstance(a,dict) and all(k in a and same(a[k],v) for k,v in b.items())
    if isinstance(b,list):return isinstance(a,(list,tuple)) and len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
    if a==b:return True
    try:return abs(Fraction(str(a))-Fraction(str(b)))<=Fraction('1e-8')
    except (ValueError,TypeError,ZeroDivisionError):return False


def record(out,key,actual,wanted,raw=None):
    folder=out/key;folder.mkdir(exist_ok=False)
    diffs=[dict(field=k,actual=actual.get(k),expected=v) for k,v in wanted.items() if k not in actual or not same(actual[k],v)]
    if raw is not None:save(folder/'saved.json.gz',raw)
    row=dict(key=key,status='FAIL' if diffs else 'PASS',actual=actual,expected=wanted,differences=diffs,assertions=len(wanted))
    if raw is not None:row['saved_sha256']=sha(folder/'saved.json.gz')
    save(folder/'result.json',row);return row


def direct_check(case,field,actual):
    root=actual['prefix'];out=dict(first=actual['choice'],instances=sorted(actual['certificates']),reviews=root['obligations'],
        original_support=root['support'],probe_in_menu=any(any(k.endswith('/I') for k in r['sequence']) for r in actual['alternatives']))
    by_seq={tuple(r['sequence']):r for r in actual['alternatives']}
    out['C_elective_exists']=('C/c0/A',) in by_seq
    direct=by_seq.get(('N/n0/A',))
    out['own_positive_before_N']=direct is not None and not direct['admitted'] and direct['reason']=='OWN_POSITIVE_REQUIRED'
    which=case.get('checked_single')
    if which:
        r=by_seq[(which,)];out.update(admitted=r['admitted'],single_reason=r['reason'],
            single_stages=[[step['task'].split('/')[0]+'.'+step['task'][-1],step['at'],step['planned_end']] for step in r['steps']])
    if 'feasible_pair_order' in case:
        viable=[list(seq) for seq,r in by_seq.items() if len(seq)==2 and r['admitted']]
        out['feasible_pair_order']=viable[0] if len(viable)==1 else viable
        out['reverse_feasible']=by_seq[('C/c0/A','N/n0/A')]['admitted']
    return out


def public_phase(out,plan,expected,manifest,meter):
    from aegis_dc.joint_policy import choose,order_exclusions
    snapshots=read(PK/'direct.json');rows=[]
    for case in expected['direct']:
        key=case['id'];item=snapshots[key]
        if digest(item)!=manifest['direct'][key]:raise ValueError('Snapshot identity')
        meter.enter(key,'direct');actual=choose(item['config'],item['view'])
        want={k:v for k,v in case.items() if k not in ('id','row','method','setup','time','checked_single') and not(k=='admitted' and v is None)}
        rows.append(record(out,key,direct_check(case,item,actual),want,actual))
    for case in expected['order_cases']:
        options=[(tuple(r['seq']),r['plan']) for r in case['options']];key=case['id']
        meter.enter(key,'component');excluded=order_exclusions(case['config'],options)
        kept=['/'.join(x.split('/')[0] for x in seq) for seq,p in options if p['admitted'] and seq not in excluded]
        rows.append(record(out,key,dict(kept=kept),dict(kept=[case['wanted']])))
    stub=expected['mock_runner'];fake=out/'fake-work';fake.mkdir()
    for key,purpose,kind,expected_error in [('reject-study-purpose','COLD_STUDY','study','STUDY_UNAUTHORIZED'),
                                           ('reject-wrong-input','PUBLIC_ENGINEERING','engineering','INPUT_HASH')]:
        meter.enter(key,'component')
        try:engineering_admit(purpose,kind,'r1',{'slot':'r1'},{'engineering':{'r1':'wrong'}})
        except PermissionError as e:code=str(e)
        else:code='ACCEPTED'
        rows.append(record(out,key,dict(error=code),dict(error=expected_error)))
    seen=[]
    def failing(key,unit):
        meter.enter('fake-'+('success' if key=='r1' else 'failure'),'component');seen.append(key)
        if key=='r2':raise RuntimeError('frozen substitute failure')
        return dict(slot=key,status='RETURNED')
    meter.enter('fake-driver','component')
    result=execute_group(fake,stub['order'],failing)
    rows.append(record(out,'fake-driver',dict(started=seen,missing=result['unexecuted'],state=result['status']),
                       dict(started=stub['started'],missing=stub['missing'],state='FAILED'),result))
    meter.enter('reject-consumed','component')
    try:execute_group(fake,stub['order'],failing)
    except FileExistsError:answer='REFUSED'
    else:answer='ACCEPTED'
    rows.append(record(out,'reject-consumed',dict(reuse=answer),dict(reuse='REFUSED')))
    return rows


def named(summary):
    def tag(k,typ):return k.split('/')[0]+'.'+typ
    def at(t):return sorted(tag(k,TYPES[s]) for k,s in summary['states'][t].items() if s in TYPES)
    return dict(first={tag(k,typ):time for k,seen in summary['first'].items() for typ,time in seen.items()},
                at_5=at('5'),at_7_5=at('7.5'),at_12=at('12'))


def actual_arm(summary):
    return dict(chain=summary['stages'],L=summary['service']['rate'][0],U=summary['service']['rate'][1],
        L_balance=summary['service']['balance'][0],U_balance=summary['service']['balance'][1],person=summary['resources'][0],
        tool=summary['resources'][1],fee=summary['resources'][2],admission=summary['admission'],
        effects=summary['effects'],instances=sorted(summary['opened']),status=summary['status'],**named(summary))


def planned_arm(exp,chains):
    return dict(chain=chains[exp['chain']],L=exp['L'],U=exp['U'],L_balance=exp['L'],U_balance=exp['U'],person=exp['person'],
        tool=exp['tool'],fee=exp['fee'],admission=[exp['person_tool_envelope']]*2+[exp['fee']],
        effects=exp['effects'],instances=exp['instances'],status='OK',**{k:exp[k] for k in ('first','at_5','at_7_5','at_12')})


def public_arm(s):
    return {k:v for k,v in s.items() if k not in ('audit','resource_history','decisions')}


def saved_phase(root,out,pin,plan,expected,manifest,meter):
    items=read(PK/'engineering-inputs.json.gz');rows=[];states={};compact={};public_results={}
    for phase,_,assigned in plan['jobs']:
        if not isinstance(assigned,list):continue
        folder=root/phase
        if not (folder/'group.json').exists():continue
        group=read(folder/'group.json');parent=read(folder/'result.json');order=phase_units(phase,plan)
        if group!=parent.get('group') or parent['source_revision']!=pin['revision']:
            raise ValueError('Native group receipt binding '+phase)
        if group['scheduled']!=order or [r['slot'] for r in group['rows']]+group['unexecuted']!=order:raise ValueError('Group denominator')
        states.update({key:'UNEXECUTED' for key in group['unexecuted']})
        for row in group['rows']:
            key=row['slot'];states[key]=row['state']
            if row['state']!='RETURNED':continue
            unit=folder/key;path=unit/'run.json.gz';receipt=row['receipt']
            if (sha(path)!=receipt['raw_sha256'] or receipt['input_sha256']!=manifest['engineering'][key]
                or digest(read(unit/'input.json'))!=manifest['engineering'][key]):raise ValueError('Archive identity '+key)
            run=read(path);meter.enter('score:'+key,'component');s=score_arm(items[key],run)
            del run
            if s['runtime']!=receipt['runtime_tree']:raise ValueError('Runtime tree mismatch')
            e=expected['arms'][key];rows.append(record(out,'arm-'+key,actual_arm(s),planned_arm(e,expected['chains']),s))
            compact[key]=public_arm(s);compact[key]['pid']=receipt['pid'];compact[key]['raw_sha256']=receipt['raw_sha256']
            # Store only fingerprints in this public exposure ledger. Full alternatives/frames remain in private files.
            public_results[key]=[dict(time=r['time'],evidence=r['evidence'],public=r['public'],signature=r['signature'],task=r['task']) for r in s['decisions']]
    pairs={};evaluated=[]
    for exp in expected['pairs']:
        a,b=exp['left'],exp['right']
        inputs=[read(out/('arm-'+k)/'saved.json.gz') if states.get(k)=='RETURNED' else None for k in (a,b)]
        key='pair-'+a+'__'+b;meter.enter(key,'component');answer=compare_pair(*inputs);pairs[b]=answer
        want={k:exp[k] for k in ('category','resources','t_star','t_delta','closures_preserved')}
        rows.append(record(out,key,answer,want));evaluated.append(dict(candidate=a,comparator=b,**answer))
    for key in plan['component_ids']['saved_pairs']:
        case=expected['evaluators'][key];meter.enter(key,'component')
        answer=compare_pair(case['left'],case['right']) if case['op']=='pair' else dict(category=service_direction(case['left'],case['right']))
        rows.append(record(out,key,answer,case['expected']))
    mock=expected['panel_fixture'];matrix=read(PK/'conditions.json')['core_rows']
    stubpairs={k+'-B':dict(category=v,resources='WORSE',closures_preserved=False) for k,v in mock['primary'].items()}
    stubpairs.update({k:dict(category=v,resources='SAME',closures_preserved=True) for k,v in mock['mechanism'].items()})
    slots={slot:'RETURNED' for slot in stubpairs}
    slots.update({s.split('-')[0]+'-J':'RETURNED' for s in stubpairs})
    meter.enter('mock-denominators','component');mocked=panel(matrix,stubpairs,slots)
    rows.append(record(out,'mock-denominators',dict(counts=mocked['counts']['J/B'],planned=mocked['planned'],denominators=mocked['denominators'],dominance=mocked['service_dominance']),
                       {k:mock[k] for k in ('counts','planned','denominators','dominance')},mocked))
    meter.enter('engineering-panel','component')
    full=panel(plan['groups'],pairs,states)
    rows.append(record(out,'engineering-panel',dict(planned=full['planned'],comparisons=len(full['comparisons']),
                       primary_count=full['denominators']['J/B'],unexecuted=sum(v!='RETURNED' for v in full['position_states'].values())),
                       dict(planned=16,comparisons=9,primary_count=3,unexecuted=0),full))
    save(out/'summary.json',dict(positions=states,arms=compact,pairs=evaluated,panel=full))
    save(out/'public-roots.json.gz',public_results)
    return rows


def phase_totals(out):
    path=out/'calls.jsonl'
    rows=[__import__('json').loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    return {k:sum(r[1]==k for r in rows) for k in DIMS}


def main():
    phase,h=sys.argv[1:];pin=release(h);root=Path(pin['activity']);out=root/phase
    plan=read(PK/'engineering-plan.json');manifest=read(PK/'input-freeze.json');expected=read(PK/'expected.json')
    if (sha(PK/'engineering-inputs.json.gz')!=manifest['files']['engineering-inputs.json.gz'] or
        sha(PK/'direct.json')!=manifest['files']['direct.json'] or sha(PK/'expected.json')!=manifest['files']['expected.json']):
        raise PermissionError('Freeze mismatch')
    if phase not in [j[0] for j in plan['jobs']][1:]:raise PermissionError('Unknown phase')
    import fcntl
    owner=(root/'serial.lock').open('a')
    fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
    before=[j[0] for j in plan['jobs']];prior=before[:before.index(phase)]
    for prev in prior:
        folder=root/prev;receipt=folder/'result.json'
        if phase in ('A','M') and not folder.exists():continue
        if not receipt.exists():raise PermissionError('Previous allocation unresolved '+prev)
        if phase not in ('A','M') and read(receipt)['status'] not in ('PASS','EXPECTED_PRIOR_REJECTIONS'):
            raise PermissionError('Previous engineering gate did not pass '+prev)
    with (out/'started.lock').open('x') as fp:fp.write(os.environ['SLURM_JOB_ID'])
    rows=[];failed=[];extra={};error=None
    try:
        if phase=='Q':
            meter=Meter(out,dict(direct=9,component=9))
            rows=public_phase(out,plan,expected,manifest,meter)
        elif phase.startswith('N'):
            group=native_parent(phase,pin,h,out,plan,manifest)
            extra=dict(group=group,unexecuted=group['unexecuted'])
            failed=[r['slot'] for r in group['rows'] if r['state']!='RETURNED']
        elif phase=='A':
            meter=Meter(out,dict(component=41))
            rows=saved_phase(root,out,pin,plan,expected,manifest,meter)
        else:
            from cold3_manifest import assemble_manifest
            meter=Meter(out,dict(component=1));meter.enter('manifest-binding','component')
            extra=assemble_manifest(root,out,pin,plan,manifest,h)
    except Exception as exc:
        error=repr(exc);(out/'exception.txt').write_text(traceback.format_exc(),encoding='utf8')
    failed+= [r['key'] for r in rows if r['status']!='PASS']
    counts=phase_totals(out)
    report=dict(phase=phase,job=os.environ['SLURM_JOB_ID'],source_revision=pin['revision'],release=h,counts=counts,
        status='FAILED' if failed or error else 'PASS',failed=failed,error=error,rows=rows,**extra)
    save(out/'result.json',report)
    print(phase,report['status'],counts,failed,error or '',flush=True)
    owner.close()
    return int(report['status']=='FAILED')


if __name__=='__main__':raise SystemExit(main())
