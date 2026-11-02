"""One fixed priority comparison; confirmation starts only after selection."""
import csv
import gzip
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path

from .risk_response import run_response
from .reorder_execution import run_reorder


def run_priority_study(args):
    from .cli import ROOT,write_json
    path=Path(args.protocol) if args.protocol else ROOT/'configs/event-priority.json'
    protocol=json.loads(path.read_text(encoding='utf-8'))
    output=Path(args.output);output.mkdir(parents=True,exist_ok=False)
    if {c['spec']['seed'] for c in protocol['confirmation']} & set(protocol['seen_seeds']):
        raise ValueError('Confirmation seeds already seen')
    write_json(output/'protocol.json',protocol)
    write_json(output/'seal.json',{'at':datetime.now(timezone.utc).isoformat(),
        'protocol_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}})
    rows=[];attempts=[];cache={}
    def evaluate(case,method,phase,label):
        key=(case['id'],method,phase)
        if key not in cache:
            if len(attempts)>=protocol['max_actual_evaluations']:raise RuntimeError('Budget exhausted')
            a={'case':case['id'],'method':method,'phase':phase,'status':'started','at':datetime.now(timezone.utc).isoformat()}
            attempts.append(a);write_json(output/'attempts.json',attempts)
            try:
                if method=='tour':
                    record,env=run_reorder(case['spec'],None,{'method':'T'})
                    record={k:record[k] for k in ('metrics','inspection_events','anomaly_intervals','action_log','action_sha256')}
                    record['process_sha256']=env.trace.fingerprint
                else:record,_=run_response(case['spec'],True,120.,method)
                filename=f'{phase}-{case["id"]}-{method}.json.gz'
                with gzip.open(output/filename,'wt',encoding='utf-8') as f:json.dump(record,f,allow_nan=False)
                cache[key]=(record,filename);a['status']='completed'
                print(phase,case['id'],method,record['metrics']['missed_segments'],flush=True)
            except Exception as error:a.update(status='failed',error=str(error));raise
            finally:write_json(output/'attempts.json',attempts)
        record,filename=cache[key];m=record['metrics']
        rows.append({'phase':phase,'case':case['id'],'label':label,'actual_method':method,'record':filename,
            **{k:m.get(k,0) for k in ('anomaly_segments','confirmed_segments','missed_segments',
               'consequence_weighted_censored_delay_s','travel_m','service_s','completed_inspections',
               'extra_event_visits','tasks_violating_exact_gap','invalid_assignments','duplicate_reservations')}})
        return record
    for case in protocol['development']:
        for method in ['tour',*protocol['priorities']]:evaluate(case,method,'development',method)
    def score(method):
        subset=[r for r in rows if r['phase']=='development' and r['actual_method']==method]
        waits=[r['consequence_weighted_censored_delay_s'] for r in subset if r['consequence_weighted_censored_delay_s'] is not None]
        return (sum(r['missed_segments'] for r in subset),sum(waits)/len(waits) if waits else 0,
                sum(r['travel_m'] for r in subset))
    chosen=min(protocol['priorities'],key=score)
    write_json(output/'selected.json',{'at':datetime.now(timezone.utc).isoformat(),'selected':chosen,
                                     'scores':{m:score(m) for m in protocol['priorities']}})
    for case in protocol['confirmation']:
        results=[evaluate(case,m,'confirmation',label) for label,m in [('tour','tour'),('fifo','fifo'),('selected',chosen)]]
        assert len({r['process_sha256'] for r in results})==1
    with (output/'results.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary={'selected':chosen,'actual_evaluations':len(attempts),'model_calls':0,'training':0,'confirmation':{}}
    for label in ['tour','fifo','selected']:
        subset=[r for r in rows if r['phase']=='confirmation' and r['label']==label]
        waits=[r['consequence_weighted_censored_delay_s'] for r in subset if r['consequence_weighted_censored_delay_s'] is not None]
        summary['confirmation'][label]={k:sum(r[k] for r in subset) for k in ('anomaly_segments','confirmed_segments','missed_segments','extra_event_visits','tasks_violating_exact_gap','invalid_assignments','duplicate_reservations')}
        summary['confirmation'][label].update(mean_wait_s=sum(waits)/len(waits) if waits else None,
            **{'mean_'+k:sum(r[k] for r in subset)/len(subset) for k in ('travel_m','service_s','completed_inspections')})
    write_json(output/'summary.json',summary)
    return summary
