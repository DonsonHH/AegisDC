"""Trusted host connects a fresh restricted interpreter to the native public decision interface."""
import subprocess
from workpackage import *
import bridge
import public_work as work
from aegis_cost_baseline.rule import operative_view


class Worker(bridge.PublicProcess):
    def __init__(self,mode,role,inventory,stderr):
        self.role=role;self.static=None;self.events=[];self.ipc=[]
        self.identity=inventory['role_bundles'][mode][role]
        root=B_OLD if role=='B' else ACT/'bundles'/self.identity
        verify_bundle(root,inventory['bundle_members'][self.identity])
        script=('aegis_cost_baseline/worker.py' if role=='B_COST' else 'aegis_risk_dispatch/worker.py'
                if role=='B' else 'aegis_action_cost/worker.py')
        self.stderr=Path(stderr).open('x')
        self.child=subprocess.Popen([sys.executable,'-I','-S','-B',str(root/script),role],
              stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.stderr,cwd=root,
              env={'LANG':'C.UTF-8','LC_ALL':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1'})

    def start(self,pub):
        must(self.message({'public':pub})=={'ready':True,'role':self.role},'worker ready')
        self.static=digest(pub)

    def choose(self,pub,view,role,plan):
        must(role==self.role and not plan and self.static==digest(pub),'closed decision entry')
        frame=operative_view(view) if role=='B_COST' else view
        result=self.message({'view':frame})
        self.ipc.append([view['time'],digest(frame),digest(result)])
        if role=='B_COST':
            result['certificates']={s['id']:work.certificate(s,view) for s in pub['subjects']}
        self.events.append([view['time'],digest(view),digest(result)])
        return result
