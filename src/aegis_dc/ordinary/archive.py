"""Append-only evidence and exact, content-addressed identities."""
import hashlib
import json
import os
import tempfile
from pathlib import Path


def wire(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(wire(value)).hexdigest()


def save(path, value):
    """Publish once, even if two writers race. Keep a partial on I/O failure."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".partial-", delete=False) as tmp:
        tmp.write(wire(value) + b"\n")
        tmp.flush()
        os.fsync(tmp.fileno())
    os.link(tmp.name, path)
    os.unlink(tmp.name)


def load(path):
    return json.loads(Path(path).read_bytes())


class Journal:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("xb")
        self.sequence = 0

    def event(self, kind, **fields):
        self.sequence += 1
        self.stream.write(wire(dict(sequence=self.sequence, event=kind, **fields)) + b"\n")
        self.stream.flush()
        os.fsync(self.stream.fileno())
        return self.sequence

    def close(self):
        self.stream.close()
