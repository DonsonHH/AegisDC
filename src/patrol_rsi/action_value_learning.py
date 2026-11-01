"""One fixed36-dimensional,lambda1,no-intercept ridge method; no hyperparameter search."""
from pathlib import Path
import json
import numpy as np

from .action_value_features import FEATURE_NAMES

HEADS=('missed','wait_s','travel_m','completed')


def weights(rows):
    groups={r['group_id'] for r in rows};out=[]
    for r in rows:
        own=[v for v in rows if v['group_id']==r['group_id']];roots={v['root_id'] for v in own}
        actions=sum(v['root_id']==r['root_id'] for v in own)
        out.append(1./len(groups)/len(roots)/actions)
    return np.asarray(out,dtype=np.float64)


def fit_fold(rows,heldout):
    train=[r for r in rows if r['group_id']!=heldout]
    if not train:raise ValueError('No training groups')
    x=np.asarray([r['x'] for r in train],dtype=np.float64)
    if x.shape[1:]!=(36,) or not np.isfinite(x).all():raise ValueError('Frozen36 finite input columns')
    w=weights(train);mean=np.sum(w[:,None]*x,axis=0)
    scale=np.sqrt(np.sum(w[:,None]*(x-mean)**2,axis=0));scale[scale<=1e-12]=1.
    normalized=x/scale;heads=[]
    for h,name in enumerate(HEADS):
        mask=np.asarray([r['y'][h] is not None for r in train]);valid=[r for r,yes in zip(train,mask) if yes]
        y=np.asarray([r['y'][h] for r in valid],dtype=np.float64)
        head={'name':name,'valid_rows':len(valid),'valid_groups':len({r['group_id'] for r in valid}),
            'valid_roots':len({r['root_id'] for r in valid}),'coefficient':[0.]*36}
        if head['valid_groups']<2 or head['valid_roots']<4:head['status']='constant_zero_insufficient'
        elif np.ptp(y)<=1e-9:head['status']='constant_zero_no_variation'
        else:
            vw=weights(valid);z=normalized[mask];matrix=z.T@(vw[:,None]*z)+np.eye(36)
            beta=np.linalg.solve(matrix,z.T@(vw*y))
            if not np.isfinite(beta).all():raise ValueError('Finite fitted coefficients')
            head.update(status='ridge_fitted',coefficient=beta.tolist(),condition_number=float(np.linalg.cond(matrix)))
        heads.append(head)
    return {'feature_names':list(FEATURE_NAMES),'lambda':1.,'fit_intercept':False,'centering':False,
        'mean':mean.tolist(),'scale':scale.tolist(),'heads':heads,'heldout_group':heldout,
        'training_groups':sorted({r['group_id'] for r in train}),'training_roots':sorted({r['root_id'] for r in train}),
        'train_row_count':len(train),'inference_input':'Only numeric36 public features; no valid-label masks or grouping IDs'}


def predict(model,x):
    if model['feature_names']!=list(FEATURE_NAMES):raise ValueError('Feature order identity')
    x=np.asarray(x,dtype=np.float64)
    if x.ndim==1:x=x[None,:]
    if x.shape[1:]!=(36,) or not np.isfinite(x).all():raise ValueError('Finite public36 input required')
    coef=np.asarray([h['coefficient'] for h in model['heads']],dtype=np.float64).T
    values=(x/np.asarray(model['scale']))@coef
    if not np.isfinite(values).all():raise ValueError('Finite head outputs')
    return values


def load(path):
    model=json.loads(Path(path).read_bytes())
    if model['feature_names']!=list(FEATURE_NAMES) or model['lambda']!=1. or model['fit_intercept'] is not False:raise ValueError('Frozen learned tool contract')
    return model
