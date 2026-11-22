"""Use the exact inherited public response protocol for old and new decision makers."""
from pathlib import Path
import subprocess
import sys

from context_v2 import ACT, digest, need, read, references
from public_adapter import Worker


class Process(Worker):
    def __init__(self, role, log, descriptor=None, manual=False):
        self.role=role
        self.events=[]
        self.ipc=[]
        self.static=None
        self.descriptor=descriptor
        self.stderr=Path(log).open("x")
        if descriptor is None:
            self.identity,base,_=references()[role]
            entry={"B":"aegis_risk_dispatch/worker.py","B_COST":"aegis_cost_baseline/worker.py"}.get(role,"aegis_action_cost/worker.py")
            self.wire=role
        else:
            scope="manual" if manual else "learned"
            base=ACT/"public"/scope
            self.identity=read(ACT/"bundle-index.json")[scope]["sha256"]
            entry="aegis_improvement/worker.py" if manual else "aegis_improvement_v2/worker.py"
            self.wire="T5"
        self.child=subprocess.Popen([sys.executable,"-I","-S","-B",str(base/entry),self.wire],stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=self.stderr,cwd=base,
            env={"LANG":"C.UTF-8","LC_ALL":"C.UTF-8","PYTHONDONTWRITEBYTECODE":"1","OMP_NUM_THREADS":"1","OPENBLAS_NUM_THREADS":"1"})

    def start(self,pub):
        if self.descriptor is not None:
            need(self.message({"policy":self.descriptor})=={"configured":True},"one static strategy")
        need(self.message({"public":pub})=={"ready":True,"role":self.wire},"public worker startup")
        self.static=digest(pub)
