"""Replay only recorded policy observations to annotate CVAE input provenance.

No plant generation, inspector scheduling, policy action or score evaluation.
Replayed first/final policy hashes must match the closed actual record. This is
instrumentation reconstruction, not another independent world experiment.
"""
import argparse
import json
from collections import defaultdict
import numpy as np
import torch

from patrol_rsi.measurement_state import MeasurementState
from patrol_rsi.active_inspection import graph_for
from patrol_rsi.m11 import frozen_predictor
from patrol_rsi.multistep_workflow import digest
from run_measurement import (STAGE,CVAE,read,write,verify,rows,record,get_trace)


def main():
    from pathlib import Path
    import os
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--root',type=Path,required=True);a=p.parse_args()
    if 'SLURM_JOB_ID' not in os.environ:raise RuntimeError('Slurm instrumentation only')
    torch.set_num_threads(1);signature=verify(a.source)
    predictor=frozen_predictor(CVAE,a.source/'research/2026-10-28-m111-coverage/frozen_estimator.json')
    completed=rows(a.root,signature);cases=read(a.source/STAGE/'protocol.json')['cases'];result=[]
    tasks=graph_for(128,'open').tasks
    for case in cases:
        row=next(v for v in completed if v['case_id']==case['case_id'] and v['arm']=='C')
        actual=record(row);context=actual['first_post_measurement_context']
        first_key=tuple(context['visible_state']['qualified'][str(actual['first_request']['task'])]['event_id']) if context else None
        if case['group']=='new_development':
            assert (a.root/'processes'/case['case_id']/'complete.json').exists(), 'Read closed sources only, do not generate'
        trace=get_trace(a.root,a.source,case)
        by_time=defaultdict(list)
        for event in actual['inspection_events']:by_time[event['time_s']].append(event)
        captures={'masked':[],'visible':[]}
        states={}
        for name in captures:
            def tracked(x,name=name):
                state=states[name]
                output=predictor(x)
                target=actual['first_request']['task'] if actual['first_request'] else None
                rack=tasks[target].index if target is not None and tasks[target].kind=='thermal' else None
                captures[name].append({'time_s':state.now,'frame_times_s':list(state.frame_times),
                    'input_sha256':digest(x.tolist()),'output_sha256':digest(output.tolist()),
                    'target_last_temperature_feature_by_frame':[float(f[rack,0]) for f in state.frames] if rack is not None else None,
                    'target_measurement_age_feature_by_frame':[float(f[rack,1]) for f in state.frames] if rack is not None else None})
                return output
            states[name]=MeasurementState(trace.config,tasks,tracked)
        first_hashes_checked=False
        for tick,original in enumerate(trace.packets):
            packet={k:v.copy() if isinstance(v,np.ndarray) else v for k,v in original.items()}
            rng=np.random.default_rng(4000000+case['specification']['seed']*1000+tick)
            packet['temperature_c']+=rng.normal(0,case['specification']['noise_c'],len(packet['temperature_c']))
            t=float(packet['time_s']);events=by_time[t]
            states['masked'].advance(packet,events,blocked=first_key)
            states['visible'].advance(packet,events)
            if context is not None and t==context['physical']['time_s']:
                for name in states:
                    # JSON object keys are strings after record loading. Match
                    # the persisted representation before canonical sorting.
                    persisted=json.loads(json.dumps(states[name].view(),allow_nan=False))
                    assert digest(persisted)==digest(context[name+'_state']),(case['case_id'],name,'first')
                plain={k:v.tolist() if isinstance(v,np.ndarray) else v for k,v in packet.items()}
                assert digest(plain)==digest(context['physical']['public_packet'])
                first_hashes_checked=True
        for name in states:
            assert digest(states[name].view())==actual['policy_state_final_SHA256'][name],(case['case_id'],name,'final')
        differences=[]
        for b,c in zip(captures['masked'],captures['visible']):
            assert b['time_s']==c['time_s'] and b['frame_times_s']==c['frame_times_s']
            if b['input_sha256']!=c['input_sha256']:
                differences.append({'time_s':b['time_s'],'frame_times_s':b['frame_times_s'],
                    'masked_target_feature':b['target_last_temperature_feature_by_frame'],
                    'visible_target_feature':c['target_last_temperature_feature_by_frame'],
                    'output_changed':b['output_sha256']!=c['output_sha256']})
        result.append({'case_id':case['case_id'],'first_context_hashes_match_actual':first_hashes_checked,
            'final_state_hashes_match_actual':True,'frozen_CVAE_calls_replayed':sum(len(v) for v in captures.values()),
            'input_differences':differences,'calls':captures})
        print('ANNOTATED',case['case_id'],len(differences),flush=True)
    write(a.root/'policy-input-annotations.json',{'scope':'Deterministic instrumentation replay against closed first/final policy hashes, no environment or task-score evaluation',
        'actual_extra_environment_evaluations':0,'actual_extra_language_model_calls':0,'execution_signature':signature,
        'frozen_estimator_forward_calls':sum(v['frozen_CVAE_calls_replayed'] for v in result),'cases':result})


if __name__=='__main__':main()
