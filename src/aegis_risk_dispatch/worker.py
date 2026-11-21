"""Persistent isolated Python child, one new process per arm. Only an explicitly assembled public bundle is importable."""
import sys
import json
from pathlib import Path


def main():
    root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root))
    from aegis_risk_dispatch.policy import decide
    from aegis_risk_dispatch import knowledge
    import public_work
    from aegis_dc.joint_resources import transit
    with (root/'aegis_risk_dispatch'/'settings.json').open(encoding='utf8') as stream:settings=json.load(stream)
    role=sys.argv[1]
    if role not in (*settings['versions'],'PA','B'):raise ValueError('unknown public role')
    # Preload the public prior only. No generator, plant, score, artifact loader, private path, seed or native objects.
    for architecture in ('ordinary','power_board','cooling_board'):knowledge.catalogue(architecture)
    if any(n in sys.modules for n in ('native','bounds','execute','aegis_dc.plant','incident_facility','generator_v2','score_saved')):
        raise RuntimeError('private module in dispatch interpreter')
    def deny(event,args):
        if (event.startswith(('open','os.','socket.','subprocess.','ctypes.','sys._getframe','sys.settrace','sys.setprofile'))
            or event in ('import','compile','exec','marshal.loads','sys.addaudithook','gc.get_objects','gc.get_referrers')):
            raise PermissionError('closed public decision interpreter: '+event)
    sys.addaudithook(deny)
    pub=None
    for line in sys.stdin:
        msg=json.loads(line)
        if set(msg)=={'public'} and pub is None:
            pub=msg['public'];answer={'ready':True,'role':role}
        elif set(msg)=={'view'} and pub is not None:answer=decide(role,pub,msg['view'],settings,public_work)
        elif set(msg)=={'close'}:break
        else:raise ValueError('forbidden IPC fields')
        print(json.dumps(answer,sort_keys=True,separators=(',',':'),allow_nan=False),flush=True)


if __name__=='__main__':main()
