"""New isolated public roles. The unchanged V* and T4a PA/B run their original executable."""
import sys
import json
from pathlib import Path


def main():
    root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root))
    import public_work
    from aegis_risk_dispatch import knowledge,policy
    from aegis_dc.joint_resources import transit
    from aegis_action_cost import planning
    from aegis_action_cost.permit import Gate
    settings=json.loads((root/'aegis_risk_dispatch/settings.json').read_bytes())
    limits=json.loads((root/'aegis_action_cost/rules.json').read_bytes())
    role=sys.argv[1]
    if role not in ('V_COST','V_COST_NOPROBE','VSTAR_NOPROBE','BPLUS','PERIODIC','ALARM','P'):
        raise ValueError('Unknown public role')
    updated=role.startswith('V_COST')
    gate=Gate(limits['exclusive_recovery_s']) if updated or role=='BPLUS' else public_work
    if updated:
        settings['maintenance_capacity']=limits['bypass_capacity']
        policy.choose_first=planning.choose_first
    if role.endswith('_NOPROBE'):
        underlying=gate
        class WithoutInitial:
            def __getattr__(self,name):return getattr(underlying,name)
            def admit(self,pub,view,sub,phase,slot=None):
                if phase=='I':return None,'INITIAL_READ_DISABLED'
                return underlying.admit(pub,view,sub,phase,slot)
        gate=WithoutInitial()
    for k in ('ordinary','power_board','cooling_board'):knowledge.catalogue(k)
    for name in ('public_work','common','aegis_action_cost.planning','aegis_risk_dispatch.policy','aegis_dc.joint_resources'):
        if not Path(sys.modules[name].__file__).resolve().is_relative_to(root):raise RuntimeError(name)
    if any(k in sys.modules for k in ('native_v3','plant_cost','inputs_v3','bounds','score_saved','aegis_dc.plant')):
        raise RuntimeError('Private module in public interpreter')
    def deny(event,args):
        if event.startswith(('open','os.','socket.','subprocess.','ctypes.','sys._getframe','sys.settrace','sys.setprofile')) or event in ('import','compile','exec','marshal.loads','sys.addaudithook','gc.get_objects','gc.get_referrers'):
            raise PermissionError('Closed decision interface: '+event)
    sys.addaudithook(deny)
    pub=None
    for line in sys.stdin:
        msg=json.loads(line)
        if set(msg)=={'public'} and pub is None:
            pub=msg['public'];answer={'ready':True,'role':role}
        elif set(msg)=={'view'} and pub is not None:
            view=msg['view'];policy.validate(pub,view)
            if role in ('P','PERIODIC','ALARM'):
                answer=public_work.choose(pub,view,role,{})
            elif role=='BPLUS':
                due,renew=policy.priorities(pub,view,public_work)
                issued={r['task'] for r in view['issued']}
                all_writes=[(sid,'A',None) for sid in pub['routes'] if sid+'::A' not in issued]
                req,denied=policy.first_legal(due+all_writes+renew,pub,view,gate)
                answer=dict(request=req,refusals=denied,certificates={z['id']:public_work.certificate(z,view) for z in pub['subjects']})
            else:answer=policy.decide('V3',pub,view,settings,gate)
        elif set(msg)=={'close'}:break
        else:raise ValueError('Unregistered public payload')
        print(json.dumps(answer,sort_keys=True,separators=(',',':'),allow_nan=False),flush=True)

if __name__=='__main__':main()
