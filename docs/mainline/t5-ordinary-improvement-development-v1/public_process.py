"""Dedicated public processes implementing the inherited decision-envelope contract."""
from pathlib import Path
import subprocess
import sys

from context_t5 import ACT, PUBLIC, digest, read, require
from public_adapter import Worker


class Process(Worker):
    def __init__(self, role, stderr, reference=None, descriptor=None):
        self.role=role
        self.static=None
        self.events=[]
        self.ipc=[]
        self.descriptor=descriptor
        self.stderr=Path(stderr).open("x")
        if descriptor is not None:
            self.identity=read(ACT/"worker-bundle.json")["bundle"]
            self.wire="T5"
            root=PUBLIC
            entry="aegis_improvement/worker.py"
        else:
            self.identity,root=reference
            self.wire=role
            entry={"B":"aegis_risk_dispatch/worker.py","B_COST":"aegis_cost_baseline/worker.py"}.get(
                role,"aegis_action_cost/worker.py"
            )
        self.child=subprocess.Popen([sys.executable,"-I","-S","-B",str(root/entry),self.wire],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.stderr,cwd=root,
            env={"LANG":"C.UTF-8","LC_ALL":"C.UTF-8","PYTHONDONTWRITEBYTECODE":"1","OMP_NUM_THREADS":"1","OPENBLAS_NUM_THREADS":"1"})

    def start(self,pub):
        if self.descriptor is not None:
            require(self.message({"policy":self.descriptor})=={"configured":True},"descriptor installed")
        require(self.message({"public":pub})=={"ready":True,"role":self.wire},"public handshake")
        self.static=digest(pub)
