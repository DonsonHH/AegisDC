"""Read only the OS observer's traces and return a bounded verdict inside the auditor mount."""

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys


def audit(root, role):
    files = sorted(Path(root).glob("os.*"))
    allowed = ["/runtime/", "/lib64/", "/dev/", "/proc/self/"]
    if role in ("parent","child"):
        allowed.append("/public/")
    if role in ("child","search-O","search-R","audit","probe"):
        allowed.append("/t8/")
    if role == "eval":
        allowed += ["/t8/", "/native/", "/out/", "/input.json",
                    "/share/home/renly/renly-patrol-rsi/mainline/V6-cold-launch-release-v1/source/"]
    if role == "audit": allowed.append("/evidence/")
    found, opens, reads, denials = 0, 0, 0, 0
    digests = {}
    for path in files:
        data = path.read_bytes()
        digests[path.name] = hashlib.sha256(data).hexdigest()
        live = False
        for line in data.decode("utf-8","replace").splitlines():
            if line.startswith('execve("/runtime/bin/python3.13"') and re.search(r"=\s*0$",line):
                if live: raise ValueError("unexpected repeated interpreter")
                live = True
                found += 1
                continue
            if not live: continue
            if line.startswith(("read(","readv(")): reads += 1
            if " = -1 " in line:
                denials += 1
                continue
            if line.startswith(("socket(","connect(","socketpair(","setns(","unshare(","ptrace(","mount(","execve(")):
                raise ValueError("unexpected successful socket, process or namespace operation")
            if line.startswith(("clone(","clone3(","fork(","vfork(")) and role != "eval":
                raise ValueError("unexpected public child")
            if not line.startswith(("open(","openat(","openat2(")): continue
            m = re.search(r'=\s*[0-9]+<([^>]+)>$',line)
            if m:
                name = m.group(1)
            else:
                m = re.search(r'"(/[^"]+)"',line)
                if not m: raise ValueError("unattributable open")
                name = m.group(1)
            if ".." in PurePosixPath(name).parts or not any(
                    name == key.rstrip("/") or name.startswith(key if key.endswith("/") else key+"/") for key in allowed):
                raise ValueError("open outside declared mounts")
            opens += 1
    if not (found==1 and opens>0 and reads>0): raise ValueError("missing OS access coverage")
    return {"interpreter":found,"successful_opens":opens,"reads":reads,"denied_or_missing":denials,
            "trace_objects":digests}


if __name__=="__main__":
    print(json.dumps(audit("/evidence",sys.argv[1]),sort_keys=True,separators=(",",":")),flush=True)
