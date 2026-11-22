"""Restricted public JSON entry; the facility attaches reporting certificates outside the selector."""
import json
from pathlib import Path
import sys


def main():
    root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root))
    from aegis_cost_baseline.rule import decide,operative_view
    from aegis_risk_dispatch.policy import validate
    from aegis_dc.joint_resources import transit
    rule=json.loads((root/'cost-permit.json').read_bytes())
    if set(rule)!={'exclusive_recovery_s'} or rule['exclusive_recovery_s'] not in (0,180):
        raise ValueError('Unexpected static scheduling parameter')
    for name in ('public_work','common','aegis_cost_baseline.rule','aegis_action_cost.permit'):
        if not Path(sys.modules[name].__file__).resolve().is_relative_to(root):raise ValueError(name)
    def deny(event,args):
        if event.startswith(('open','os.','socket.','subprocess.','ctypes.','sys._getframe','sys.settrace','sys.setprofile')) or event in ('import','compile','exec','marshal.loads','sys.addaudithook','gc.get_objects','gc.get_referrers'):
            raise PermissionError('Closed public decision interface')
    sys.addaudithook(deny)
    pub=None
    for line in sys.stdin:
        m=json.loads(line)
        if set(m)=={'public'} and pub is None:
            pub=m['public'];out={'ready':True,'role':'B_COST'}
        elif set(m)=={'view'} and pub is not None:
            v=m['view'];validate(pub,v)
            if v!=operative_view(v):raise ValueError('Unregistered baseline channel')
            out=decide(pub,v,rule['exclusive_recovery_s'])
        elif set(m)=={'close'}:break
        else:raise ValueError('Unexpected decision payload')
        print(json.dumps(out,sort_keys=True,separators=(',',':'),allow_nan=False),flush=True)


if __name__=='__main__':main()
