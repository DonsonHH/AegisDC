"""Read a fitted fold tool and predict public feature36 only; never schedule actions."""
import argparse
import json
from pathlib import Path
from patrol_rsi.action_value_learning import load,predict,HEADS


def main():
    p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--features-json',type=Path,required=True);a=p.parse_args()
    payload=json.loads(a.features_json.read_bytes())
    if type(payload) is not dict or set(payload)!={'x'}:raise ValueError('Input must contain only x:public36; no audit IDs, labels or validity masks')
    model=load(a.model);values=predict(model,payload['x'])
    print(json.dumps({'predictions':[dict(zip(HEADS,map(float,v))) for v in values],
        'head_statuses':{h['name']:h['status'] for h in model['heads']},
        'meaning':'Predicted relative outcomes for one frozen intervention then Tour; not deployment performance or calibrated probability.'},allow_nan=False))


if __name__=='__main__':main()
