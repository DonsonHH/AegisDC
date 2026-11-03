"""Offline estimators and professional task metrics for the supplementary study."""
import math
from statistics import mean

import numpy as np


def temperature_metrics(prediction,truth,weights,fresh):
    prediction=np.asarray(prediction,dtype=float);truth=np.asarray(truth,dtype=float)
    weights=np.asarray(weights,dtype=float);fresh=np.asarray(fresh,dtype=bool)
    if prediction.shape!=truth.shape or prediction.ndim!=2 or prediction.shape[1]!=len(weights) or fresh.shape!=truth.shape:
        raise ValueError('Prediction, physical labels, weights and mask must align')
    if not np.isfinite(prediction).all() or not np.isfinite(truth).all() or not (weights>0).all():raise ValueError('Invalid estimation inputs')
    errors=(prediction-truth)**2
    def subset(mask):
        count=int(mask.sum())
        if not count:return {'count':0,'rmse_c':None,'weighted_rmse_c':None,'r2':None}
        squared=errors[mask];target=truth[mask]
        w=np.broadcast_to(weights,truth.shape)[mask]
        sst=float(((target-target.mean())**2).sum())
        return {'count':count,'rmse_c':float(np.sqrt(squared.mean())),
                'weighted_rmse_c':float(np.sqrt(np.dot(squared,w)/w.sum())),
                'r2':float(1-squared.sum()/sst) if sst>1e-12 else None}
    return {'all':subset(np.ones(truth.shape,dtype=bool)),'not_fresh':subset(~fresh)}


def weighted_age(record):
    weights=record['asset_weights'];deadlines=record['deadlines_s'];area=0.
    for row in record['exact_task_gaps']:
        task=row['task'];limit=deadlines[task];times=[0.,*row['completion_times_s'],1800.]
        for before,after in zip(times,times[1:]):
            gap=after-before
            if gap<0:raise ValueError('Unordered completion times')
            area+=weights[task]*(gap*gap/(2*limit) if gap<=limit else gap-limit/2)
    return area/(1800*sum(weights))


def latency_metrics(record):
    result={}
    for key in ['estimator_total_ms','public_packet_ms','nominal_update_ms','neural_input_ms','logger_context_ms',
                'neural_predict_ms','fresh_correction_ms','instrumented_update_ms','policy_total_ms','instrumented_execution_step_ms','online_control_cycle_ms']:
        values=[r[key] for r in record['timing'] if r.get(key) is not None]
        result[key]={'n':len(values),'mean':mean(values) if values else None,
                     'p50':float(np.percentile(values,50)) if values else None,
                     'p95':float(np.percentile(values,95)) if values else None}
    return result


def episode_summary(record,arrays):
    result=dict(record['metrics'])
    result['weighted_normalized_age']=weighted_age(record)
    result['temperature']=temperature_metrics(arrays['predicted_temperature_c'],arrays['true_temperature_c'],arrays['rack_weights'],arrays['fresh_measurement_mask'])
    result['latency']=latency_metrics(record)
    denominator=result['anomaly_segments'];result['confirmation_ratio']=result['confirmed_segments']/denominator if denominator else None
    result['event_status_counts']={key:sum(e['status']==key for e in record['public_events']) for key in ['pending','expired','measured','measured_late']}
    return result
