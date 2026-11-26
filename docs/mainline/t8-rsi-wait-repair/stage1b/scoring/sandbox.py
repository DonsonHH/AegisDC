"""Rootless, network-denied study roles, launched inside the allocated Podman subordinate-ID map."""

import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

UID = {"eval":1101,"parent":1102,"child":1102,"search-O":1103,"search-R":1104,"audit":1105}
CORE = "/share/home/renly/renly-patrol-rsi/mainline/V6-cold-launch-release-v1/source"


def filehash(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""):h.update(chunk)
    return h.hexdigest()


def filter_bytes():
    so=ctypes.CDLL("libseccomp.so.2")
    so.seccomp_init.argtypes=[ctypes.c_uint32];so.seccomp_init.restype=ctypes.c_void_p
    so.seccomp_syscall_resolve_name.argtypes=[ctypes.c_char_p]
    so.seccomp_rule_add.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_uint]
    so.seccomp_export_bpf.argtypes=[ctypes.c_void_p,ctypes.c_int]
    so.seccomp_release.argtypes=[ctypes.c_void_p]
    ctx=so.seccomp_init(0x7fff0000)  # libseccomp SCMP_ACT_ALLOW
    if not ctx:raise RuntimeError("seccomp initialization")
    try:
        for name in ("socket","socketpair","connect","ptrace","mount","umount2","setns","unshare"):
            nr=so.seccomp_syscall_resolve_name(name.encode())
            if nr<0 or so.seccomp_rule_add(ctx,0x00050000|errno.EPERM,nr,0)!=0:raise RuntimeError("seccomp rule")
        with tempfile.TemporaryFile() as f:
            if so.seccomp_export_bpf(ctx,f.fileno())!=0:raise RuntimeError("seccomp export")
            f.seek(0)
            return f.read()
    finally:
        so.seccomp_release(ctx)


def require_rootless():
    maps=[list(map(int,line.split())) for line in Path("/proc/self/uid_map").read_text().splitlines()]
    if os.geteuid()!=0 or not any(i==0 and host!=0 and n==1 for i,host,n in maps):
        raise RuntimeError("require allocated unprivileged rootless user namespace")
    if not all(any(i<=uid<i+n and host+uid-i!=0 for i,host,n in maps) for uid in set(UID.values())):
        raise RuntimeError("missing delegated subordinate role identities")
    return maps


def spawn(image, role, program, args, log, mounts=(), probe=False):
    """Only explicit immutable mounts and optional one-position output enter a role."""
    require_rootless()
    log=Path(log);log.mkdir(parents=True,exist_ok=False)
    runtime=image/"runtime"
    command=["strace","-ff","-qq","-y","-s","256","-e",
             "trace=%file,read,readv,socket,socketpair,connect,clone,clone3,fork,vfork,ptrace,setns,unshare,mount",
             "-e","raw=read,readv","-o",str(log/"os"),"bwrap","--unshare-pid","--unshare-net","--unshare-ipc",
             "--unshare-uts","--new-session","--die-with-parent","--cap-add","CAP_SETUID","--cap-add","CAP_SETGID",
             "--cap-add","CAP_SETPCAP","--proc","/proc","--dev","/dev","--ro-bind",str(runtime/"py"),"/runtime",
             "--ro-bind",str(runtime/"syslib"),"/lib64","--setenv","LANG","C",
             "--setenv","LC_ALL","C","--setenv","PATH","/no-executables","--setenv","LD_LIBRARY_PATH","/runtime/lib"]
    if role in ("parent","child"):
        command+=["--ro-bind",str(image/"parent"),"/public"]
    if role=="eval":
        command+=["--ro-bind",str(image/"native"),"/native","--ro-bind",str(image/"core"),CORE,
                  "--ro-bind",str(image/"code/native_role.py"),"/t8/native_role.py"]
    if role in ("child","search-O","search-R") or probe:
        command+=["--ro-bind",str(image/"code/public_roles.py"),"/t8/public_roles.py",
                  "--ro-bind",str(image/"code/fit_program.py"),"/t8/fit_program.py"]
    if role=="audit":
        command+=["--ro-bind",str(image/"code/access_audit.py"),"/t8/access_audit.py"]
    for flag,src,dst in mounts:
        command.extend([flag,str(src),dst])
    with (image/"policy.bpf").open("rb") as rules:
        command+=["--seccomp",str(rules.fileno()),"--chdir","/","/runtime/bin/setpriv",f"--reuid={UID[role]}",
                  f"--regid={UID[role]}","--clear-groups","--no-new-privs","--bounding-set=-all","--inh-caps=-all",
                  "--ambient-caps=-all","/runtime/bin/python3.13","-I","-S","-B",program,*args]
        with (log/"stderr").open("xb") as err:
            proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,
                    pass_fds=(rules.fileno(),),close_fds=True,env={"PATH":"/usr/bin:/bin","LANG":"C","LC_ALL":"C"})
    return proc


def audit_role(image, role, traces, path):
    """Auditor gets only traces. Its signed summary is retained by the external journal."""
    # A subordinate identity can traverse this bind mount but cannot write its read-only contents.
    for entry in traces.glob("os.*"):entry.chmod(0o444)
    traces.chmod(0o755)
    p=spawn(image,"audit","/t8/access_audit.py",[role],path,
            mounts=[("--ro-bind",traces,"/evidence")])
    out,_=p.communicate(timeout=20)
    if p.returncode:raise RuntimeError("independent OS trace check failed")
    return json.loads(out)
