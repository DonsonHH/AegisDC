"""Read-only reconciliation of T1 allocations. Does not import the plant or a policy."""
from collections import Counter
from fractions import Fraction
from pathlib import Path
import gzip
import hashlib
import json
import os

BASE = Path('/share/home/renly/renly-patrol-rsi/mainline/T1-margin-20261121-v1')
DOC = BASE/'source/docs/mainline'
PK = DOC/'t1-research-margin-v1'
TOL = Fraction(1,10**8)


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    with path.open('rb') as fp:
        return hashlib.file_digest(fp,'sha256').hexdigest()


def q(value):
    return Fraction(str(value))


def insist(ok,detail):
    if not ok:
        raise ValueError(detail)


def curve_error(actual, bound):
    a=[(q(t),q(u),q(y)) for t,u,d,y in actual if q(d)==1]
    b=[tuple(map(q,row)) for row in bound]
    for profile in (a,b):
        insist(profile and profile[0][0]==0 and all(x<y for x,y,_ in profile)
               and all(p[1]==n[0] for p,n in zip(profile,profile[1:])), 'curve coverage')
    insist(a[-1][1]==b[-1][1],'curve H')
    return sum((min(t2,u2)-max(t1,u1))*abs(y-z)
               for t1,t2,y in a for u1,u2,z in b if min(t2,u2)>max(t1,u1))


def summarize(rows):
    positive=Counter()
    for x in rows:
        positive['P_positive']+=q(x['arms']['P']['L'])>TOL
        positive['Pminus_best_all_positive']+=q(x['raw_best']['P_minus_best'])>TOL
        positive['Pminus_best_eligible_positive']+=q(x['eligible_best']['P_minus_best'])>TOL
    return dict(rows=len(rows),**positive)


def make():
    insist(os.environ.get('SLURM_JOB_ID'),'in allocation')
    inputs=read(PK/'freeze.json')
    saved=read(BASE/'attempts/saved-01/results.json')
    hist=read(DOC/'v6-stage-three-cold-study-v2/result.json')
    maps={x['row']:x['positions'] for x in hist['rows']}
    result=dict(schema='t1-diagnostic-results-v1',input_freeze='3d2b4dd21da897d4e6b66a450bd0f2a4b4dff84c',
                freeze_sha256=sha(PK/'freeze.json'),london=saved['london'],first=saved['first'],cold=[],
                prior_cold_P=False,prior_H10_B_name='D',claims='finite evaluation-only bounds, no policy or method results')
    total=Counter()
    deltas={k:[] for k in ('P','B','J')}
    first_archive=read(DOC/'v6-native-method-study-v1/result.json')
    first_P={arm['condition']:arm for arm in first_archive['arms'] if arm['arm']=='P'}
    for x in result['first']:
        slot=x['row']+'-P'
        score_path=BASE.parent/'V6-native-method-study-v1/jobs'/x['row']/'arms'/slot/'score.json'
        score=read(score_path)
        insist(sha(score_path)==first_P[x['row']]['score_sha256'] and score['service']['profile']==x['P_profile'],
               'original H10 complete P score/profile '+slot)
        x['P_score_sha256']=sha(score_path)
        e=curve_error(x['P_profile'],x['capacity_profile'])
        insist(x['certified'] and e<=TOL,'H10 unresolved '+x['row'])
        x['attainment_curve_L1_error']=str(e)
    for group,order in inputs['batches'].items():
        folder=BASE/'attempts'/(group+'-01')
        batch=read(folder/'results.json')['cold']
        insist([x['row'] for x in batch]==order,'cold order')
        for item in batch:
            row=item['row']
            archived_JB={}
            for k in ('J','B'):
                slot=maps[row][row+'-'+k]
                s=slot['actual']
                archived_JB[k]=dict(service=s['service'],raw_sha256=slot['raw_sha256'],score_sha256=slot['score_sha256'])
            item['historical_JB']=archived_JB
            frames=[]
            for key in ['HOLD',*item['extra_native']]:
                unit=folder/(row+'-'+key)
                en=read(unit/'entry.json');ret=read(unit/'return.json')
                insist(en['purpose']=='T1_DIAGNOSTIC_ONLY' and en['chosen']==inputs['cold_inputs'][row]['registered_derivatives'][key]
                       and en['pid']==ret['pid'] and en['job']==ret['job'] and ret['clock']==49,'native entry/return')
                insist(sha(unit/'run.json.gz')==ret['raw_sha256'] and not ret['violations'],'native original '+row+key)
                with gzip.open(unit/'score.json.gz','rt') as fp:
                    score=json.load(fp)
                canonical=json.dumps(score,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
                insist(hashlib.sha256(canonical).hexdigest()==ret['score_sha256'] and score['service']==ret['service']
                       and score['stages']==ret['stages'] and score['all_writes']==ret['all_writes']
                       and score['private_inputs_digest']==en['chosen'],'T1 score projection '+row+key)
                if key=='HOLD':
                    insist(ret['stages']==ret['effects']==ret['all_writes']==[] and ret['resources']==[0,0,0],'P work')
                frames.append(dict(method=key,job=en['job'],pid=en['pid'],purpose=en['purpose'],
                                   input_sha256=en['chosen'],run_sha256=ret['raw_sha256'],clock=49,
                                   score_file_sha256=sha(unit/'score.json.gz'),dir=str(unit)))
                total[key]+=1
            item['native_records']=frames
            if item['certified']:
                w=item['witness'][0];key=w['identity']
                if key.startswith('T1-'):
                    method='HOLD' if key=='T1-P' else key[3:]
                    item['attainer_original']=next(a for a in frames if a['method']==method)
                else:
                    src=maps[row][key]
                    item['attainer_original']=dict(identity=key,raw_sha256=src['raw_sha256'],score_sha256=src['score_sha256'])
                err=curve_error(w['service']['curve'],item['bound']['capacity_profile'])
                item['attainment_curve_L1_error']=str(err)
                insist(err<=TOL,'integrated absolute discrepancy '+row)
                for arm in deltas:
                    gap=q(item['comparisons'][arm]['gap'])
                    insist(gap>=-TOL,'lower bound exceeded '+row)
                    if gap>TOL:deltas[arm].append(row)
            result['cold'].append(item)
    insist(len(result['cold'])==24 and total['HOLD']==24,'P coverage')
    for historical_row in result['london'] + result['first']:
        for k in ('raw_best','eligible_best'):
            entry=historical_row[k]
            entry['U_at_best_L']={a:historical_row['arms'][a]['U'] for a in entry['arms']}
            entry['P_minus_U_at_best_L']={a:str(q(historical_row['arms']['P']['U'])-q(u)) for a,u in entry['U_at_best_L'].items()}
    result['summary']={b:summarize([x for x in result['london'] if x['batch']==b]) for b in ('dev19','ext35')}
    result['summary']['V6-17']=summarize(result['first'])
    cold=result['cold']
    result['summary']['cold']=dict(rows=len(cold),certified=sum(x['certified'] for x in cold),
        P_positive=sum(q(x['comparisons']['P']['service']['rate'][0])>TOL for x in cold),
        positive_gaps=deltas,new_native=dict(total),new_public_ticks=49*sum(total.values()))
    result['summary']['cold']['P_minus_best_stored_JB_positive']=[x['row'] for x in cold if
        q(x['comparisons']['P']['service']['rate'][0])-min(q(x['comparisons'][k]['service']['rate'][0]) for k in ('J','B'))>TOL]
    return result


if __name__=='__main__':
    result=make()
    out=BASE/'attempts'/('readback-'+os.environ['SLURM_JOB_ID'])
    out.mkdir()
    encoded=(json.dumps(result,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode()
    with (out/'diagnostic-data.json.gz').open('xb') as fp:
        fp.write(gzip.compress(encoded,compresslevel=6,mtime=0))
    print(json.dumps(result['summary'],ensure_ascii=False),flush=True)
    print(sha(out/'diagnostic-data.json.gz'),flush=True)
