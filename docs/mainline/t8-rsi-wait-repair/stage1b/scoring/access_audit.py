"""Read only the OS observer's traces and return a bounded verdict inside the auditor mount."""

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys


def audit(root, role):
    files = sorted(Path(root).glob("os.*"))
    allowed = ["/runtime/", "/lib64/", "/dev/", "/proc/self/", "/proc/sys/vm/overcommit_memory"]
    if role in ("parent","child"):
        allowed.append("/public/")
    if role in ("child","search-O","search-R","audit","probe"):
        allowed.append("/t8/")
    if role == "eval":
        allowed += ["/t8/", "/native/", "/out/", "/input.json",
                    "/share/home/renly/renly-patrol-rsi/mainline/V6-cold-launch-release-v1/source/"]
    if role == "audit": allowed += ["/evidence/","/audit-crypto/","/signer"]
    if role in ("search-O","search-R"): allowed.append("/audit-crypto/")
    opens, reads, denials = 0, 0, 0
    digests, traces, work = {}, {}, []
    for path in files:
        data = path.read_bytes()
        digests[path.name] = hashlib.sha256(data).hexdigest()
        pid=int(path.suffix[1:])
        traces[pid]=data.decode("utf-8","replace").splitlines()
        for i,line in enumerate(traces[pid]):
            if line.startswith('execve("/runtime/bin/python3.13"') and re.search(r"=\s*0$",line):
                work.append((pid,i+1))
    found=len(work)
    visited=set()
    while work:
        pid,start=work.pop()
        if pid in visited:continue
        visited.add(pid)
        for line in traces[pid][start:]:
            if line.startswith(("read(","readv(")): reads += 1
            if " = -1 " in line:
                denials += 1
                continue
            if line.startswith(("socket(","connect(","socketpair(","setns(","unshare(","ptrace(","mount(","execve(")):
                raise ValueError("unexpected successful socket, process or namespace operation")
            if line.startswith(("clone(","clone3(","fork(","vfork(")):
                child=re.search(r"=\s*([1-9][0-9]*)$",line)
                if child:
                    if role!="eval":raise ValueError("unexpected public child")
                    work.append((int(child[1]),0))
            if not line.startswith(("open(","openat(","openat2(")): continue
            m = re.search(r'=\s*[0-9]+<([^>]+)>$',line)
            if m:
                name = m.group(1)
            else:
                m = re.search(r'"(/[^"]+)"',line)
                if not m: raise ValueError("unattributable open")
                name = m.group(1)
            # The observed descriptor resolves the role's /proc/self inside its own PID namespace.
            own_proc = (re.search(r'"/proc/self/(status|uid_map)"', line) and
                        re.fullmatch(r"/proc/[1-9][0-9]*/(status|uid_map)", name))
            if not own_proc and (".." in PurePosixPath(name).parts or not any(
                    name == key.rstrip("/") or name.startswith(key if key.endswith("/") else key+"/") for key in allowed)):
                raise ValueError("open outside declared mounts")
            opens += 1
    if not (found==1 and opens>0 and reads>0): raise ValueError("missing OS access coverage")
    return {"interpreter":found,"successful_opens":opens,"reads":reads,"denied_or_missing":denials,
            "trace_objects":digests}


if __name__=="__main__":
    report=audit("/evidence",sys.argv[1])
    if len(sys.argv)==3 and sys.argv[2]=="signed":
        sys.path.insert(0,"/audit-crypto")
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        key=Ed25519PrivateKey.from_private_bytes(Path("/signer").read_bytes())
        payload={"role":sys.argv[1],"os_access":report}
        message=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
        report={"payload":payload,"signer":key.public_key().public_bytes_raw().hex(),
                "signature":key.sign(message).hex()}
    print(json.dumps(report,sort_keys=True,separators=(",",":")),flush=True)
