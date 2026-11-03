"""Post-hoc read-only diagnosis of estimator error versus effective confirmation.

Uses the completed held-out records; no environment replay, model call or tuning.
"""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/supplement-benchmark-20261103'
DEST=ROOT/'paper/source-data/estimation-confirmation-gap.json'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def load_record(identifier,sources,originals):
    path=RUN/'test'/identifier/'record.json.gz'
    relative=path.relative_to(RUN).as_posix();identity=sha(path)
    assert identity==originals[relative]['sha256']
    sources[relative]=identity
    with gzip.open(path,'rt',encoding='utf-8') as stream:return json.load(stream)


def interval_key(row):return row['task'],row['kind'],row['onset_s'],row['end_s']


def task_detail(record,key):
    task,kind,start,end=key
    interval=next(row for row in record['anomaly_intervals'] if interval_key(row)==key)
    cues=[{name:event[name] for name in ['event_id','visible_s','expires_s','status','measurement_s','measured_alarm']}
          for event in record['public_events'] if event['task']==task and start-180<=event['visible_s']<=end+180]
    measurements=[{'time_s':event['time_s'],'alarm':event['alarm'],'extra_event_visit':event['extra_event_visit']}
                  for event in record['inspection_events'] if event['task']==task and start-120<=event['time_s']<=end+180]
    return {'interval':interval,'cues':cues,'nearby_measurements':measurements}


def first_divergence(nominal,neural,nominal_id,neural_id,sources,originals):
    pair=next(((left,right) for left,right in zip(nominal['action_log'],neural['action_log']) if left!=right),None)
    if pair is None:return None
    left,right=pair;clock=left['time_s'];assert clock==right['time_s']
    agents=sorted(int(a) for a in set(left['choices'])|set(right['choices']) if left['choices'].get(a)!=right['choices'].get(a))
    rows=[]
    for label,record,identifier in [('nominal',nominal,nominal_id),('cvae',neural,neural_id)]:
        path=RUN/'test'/identifier/'arrays.npz';relative=path.relative_to(RUN).as_posix()
        assert sha(path)==originals[relative]['sha256'];sources[relative]=sha(path)
        with np.load(path) as arrays:
            prediction=arrays['predicted_temperature_c'][int(clock/5)-1]
            truth=arrays['true_temperature_c'][int(clock/5)-1]
        for agent in agents:
            decision=next(d for d in record['decisions'] if d['agent']==agent and d['time_s']==clock)
            candidates=[]
            for row in decision['candidates']:
                task=row['task'];cert=row['certificate']
                item={'task':task,'public_risk':row['public_risk'],'visible_s':row['visible_s'],
                      'certificate_ok':cert['ok'],'budget_allowed':row['budget_allowed']}
                if cert['ok']:item.update(finish_s=cert['candidate_finish_s'],minimum_slack_s=cert['minimum_projected_slack_s'])
                if task<128:
                    item.update(temperature_c=float(prediction[task]),physical_temperature_c=float(truth[task]),
                                temperature_component=float(max(prediction[task]-65,0)/20))
                    item['other_risk_component']=float(row['public_risk']-item['temperature_component'])
                candidates.append(item)
            rows.append({'estimator':label,'agent':agent,'routine_head':decision['routine_head'],'selected':decision['selected'],'candidates':candidates})
    return {'time_s':clock,'decisions':rows}


def main():
    protocol=json.loads((RUN/'protocol.json').read_text(encoding='utf-8'))
    registered=json.loads((ROOT/'evidence/supplement-study/local-artifacts.json').read_text(encoding='utf-8'))['files']
    sources={};changes=[];counts=Counter();per_seed={str(seed):Counter() for seed in protocol['model_seeds']}
    primary=set(protocol['analysis']['primary_families'])
    for case in protocol['case_sets']['test']:
        if case['family'] not in primary:continue
        nominal_id=case['id']+'-nominal-fifo';nominal=load_record(nominal_id,sources,registered)
        base={interval_key(row) for row in nominal['anomaly_intervals'] if row['detected']}
        for seed in protocol['model_seeds']:
            neural_id=f"{case['id']}-cvae-fifo-{seed}";neural=load_record(neural_id,sources,registered)
            assert nominal['process_sha256']==neural['process_sha256']
            assert {interval_key(row) for row in nominal['anomaly_intervals']}=={interval_key(row) for row in neural['anomaly_intervals']}
            chosen={interval_key(row) for row in neural['anomaly_intervals'] if row['detected']}
            lost,gained=sorted(base-chosen),sorted(chosen-base)
            counts.update(comparisons=1,lost=len(lost),gained=len(gained),changed=int(base!=chosen))
            per_seed[str(seed)].update(lost=len(lost),gained=len(gained))
            if lost or gained:
                changes.append({'case':case,'model_seed':seed,'nominal_id':nominal_id,'cvae_id':neural_id,
                    'lost':[{'key':list(key),'nominal':task_detail(nominal,key),'cvae':task_detail(neural,key)} for key in lost],
                    'gained':[{'key':list(key),'nominal':task_detail(nominal,key),'cvae':task_detail(neural,key)} for key in gained],
                    'first_action_divergence':first_divergence(nominal,neural,nominal_id,neural_id,sources,registered)})
    summary=json.loads((ROOT/'paper/source-data/supplement-study.json').read_text(encoding='utf-8'))
    net=(counts['gained']-counts['lost'])/3
    assert abs(net-(summary['primary_aggregates']['cvae_fifo']['total_confirmed_model_mean']-summary['primary_aggregates']['nominal_fifo']['total_confirmed_model_mean']))<1e-10
    result={'scope':'Post-hoc explanation using retained records, not a new registered test or proof of a general estimator bias.',
            'new_environment_runs':0,'new_model_calls':0,'new_training':0,'counts':dict(counts),'per_model_seed':{k:dict(v) for k,v in per_seed.items()},
            'model_mean_net_confirmation_difference':net,'changes':changes,'source_hashes':sources,'script_sha256':sha(Path(__file__))}
    DEST.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:result[k] for k in ['counts','per_model_seed','model_mean_net_confirmation_difference']},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
