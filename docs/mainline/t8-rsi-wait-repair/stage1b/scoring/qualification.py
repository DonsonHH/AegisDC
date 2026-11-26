"""Check the deployed FIT interfaces on public engineering frames, before any physical entry."""

from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import sys

from access_audit import audit
import sandbox
from positions import online, receive, terminate, transmit
from prepare_runtime import PK, STUDY, compact, read, require, save


def checked_trace(image,role,trace,dest):
    external=sandbox.audit_role(image,role,trace,dest)
    return {"signed":external,"observer_readback":audit(dest,"audit")}


def qualify(image, scratch, evidence):
    root=scratch/"engineering"
    root.mkdir()
    marker=root/"outside-engineering-marker"
    marker.write_bytes(b"public interface check\n")
    require(marker.read_bytes()==b"public interface check\n","positive outside marker")
    procs={}; observations={}; traces={}
    try:
        for role in sandbox.UID:
            procs[role]=sandbox.spawn(image,role,"/t8/public_roles.py",["probe",str(marker),"hold"],
                                      root/("probe-"+role),probe=True)
        for role,p in procs.items():
            q=receive(p)
            require(q["uid"]==q["gid"]==sandbox.UID[role] and int(q["caps"],16)==0 and
                    q["hidden_engineering_marker"] and q["socket_denied"],"real file/network/UID isolation")
            observations[role]=q
        require(len({q["uid"] for q in observations.values()})==5,"five different role IDs")
        for key in ("mnt","net","pid"):
            require(len({q["ns"][key] for q in observations.values()})==len(procs),"distinct "+key+" namespaces")
        for role,p in procs.items():
            transmit(p,{"close":True});p.stdin.close()
            require(p.wait(timeout=10)==0,"probe exit")
            traces[role]=checked_trace(image,"probe",root/("probe-"+role),root/("audit-"+role))
    finally:
        for p in procs.values():terminate(p)
    p=sandbox.spawn(image,"eval","/t8/native_role.py",["--imports"],root/"native-imports")
    out,_=p.communicate(timeout=20)
    require(p.returncode==0 and json.loads(out)["native_tree"]["source_tree_sha256"]==
            read(PK/"source-lock.json")["native_tree"] and json.loads(out)["facility_calls"]==0,
            "pinned native evaluator imports and runtime identity")
    traces["native-imports"]=checked_trace(image,"eval",root/"native-imports",root/"native-imports-audit")
    item=read(PK/"engineering-example.json")
    outputs=[]
    for label,levels in (("parent",None),("zero",[0]*6)):
        name,p=online(image,levels,root/label)
        try:
            transmit(p,{"public":item["public"]});require(receive(p)=={"ready":True,"role":"V_COST"},"parent hello")
            transmit(p,{"view":item["view"]});outputs.append(receive(p))
            transmit(p,{"close":True});p.stdin.close();require(p.wait(timeout=20)==0,"public example exit")
            traces[label+"-example"]=checked_trace(image,name,root/label,root/(label+"-example-audit"))
        finally:terminate(p)
    require(compact(outputs[0])==compact(outputs[1]),"zero child parity with original V_COST")
    for reason in ("field","future"):
        name,p=online(image,[0]*6,root/reason)
        try:
            transmit(p,{"public":item["public"]});receive(p)
            v=deepcopy(item["view"])
            if reason=="field":v["unknown_engineering_key"]=1
            else:v["records"][0]["arrived"]=v["time"]+60
            transmit(p,{"view":v});p.stdin.close()
            require(not p.stdout.readline() and p.wait(timeout=15)!=0,"invalid public frame accepted")
            traces[reason]=checked_trace(image,name,root/reason,root/(reason+"-audit"))
        finally:terminate(p)
    result={"scope":"engineering public interfaces","native_entries":0,"role_uids":observations,
            "uid_map":sandbox.require_rootless(),"zero_equals_parent":True,"bad_field_denied":True,
            "future_arrival_denied":True,"source":read(PK/"source-lock.json")["engineering_example"],
            "accepted_six_bin_fixtures":"91c6468d226c7ea08583527de34b63709ce228b7","access":traces}
    save(root/"qualification.json",result)
    shutil.copytree(root,evidence)
    return result
