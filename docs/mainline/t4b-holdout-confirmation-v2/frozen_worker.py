"""Reuse the accepted public IPC with the three registered, byte-verified bundles."""
from pathlib import Path
import subprocess
import sys

from context_t4b import T4D
from public_adapter import Worker


class FrozenWorker(Worker):
    def __init__(self, role, binding, stderr):
        self.role = role
        self.identity, folder, _ = binding
        self.static = None
        self.events = []
        self.ipc = []
        if role in ("B", "PA"):
            entry = folder/"aegis_risk_dispatch/worker.py"
        elif role == "B_COST":
            entry = folder/"aegis_cost_baseline/worker.py"
        else:
            entry = folder/"aegis_action_cost/worker.py"
        self.stderr = Path(stderr).open("x")
        self.child = subprocess.Popen(
            [sys.executable, "-I", "-S", "-B", str(entry), role],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr, cwd=folder,
            env={"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
                 "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"},
        )
