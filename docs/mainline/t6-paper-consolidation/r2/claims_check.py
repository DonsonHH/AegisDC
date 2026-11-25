"""Additive C1.B correction. No old file, research process or seed is changed."""
import sys
sys.dont_write_bytecode = True

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
T6 = HERE.parent
ROOT = T6.parents[2]
PREFIX = T6.relative_to(ROOT).as_posix()+"/"
ACCEPTED = "0ca350d1cb54ecc20fd99db5d69167d886cdef34"
T4B = "3487276af9e9759357771d16eb45feceaa3c948a"
RESULT = "docs/mainline/t4b-holdout-confirmation-v2/results.json.gz"


def insist(ok, message):
    if not ok:
        raise ValueError("claims r2: "+message)


def sealed(rev,path):
    return subprocess.check_output(["git","-C",str(ROOT),"show",rev+":"+path])


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(obj):
    return (json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+"\n").encode("utf8")


def expected():
    raw=sealed(ACCEPTED,PREFIX+"claims.json")
    old=json.loads(raw);new=json.loads(raw)
    c1=new["claims"][0];sub=c1["subclaims"][0]
    insist(c1["id"]=="C1" and c1["status"]=="部分成立" and sub["id"]=="C1.B"
           and sub["level"]=="确认" and sub["scope"]=="T4b" and sub["status"]=="部分成立","accepted claim identities")
    data=sealed(T4B,RESULT);results=json.loads(gzip.decompress(data))
    hidx=[i for i,h in enumerate(results["hypotheses"]) if h["id"]=="H1"]
    insist(hidx==[0],"prespecified H1")
    h=results["hypotheses"][hidx[0]]
    n=h["comparison"]["available"];ci=h["comparison"]["metrics"]["L"]
    insist(h["comparator"]=="B" and h["decision"]=="MET" and n==h["comparison"]["planned"]==len(results["rows"])
           and ci["hi"]<0 and h["comparison"]["directions"]==[54,76,14],"actual published H1 decision and complete panel")
    bad=[r for r in results["rows"] if r["arms"]["V_COST"]["L"]>r["arms"]["B"]["L"]]
    ids=lambda rows:{"C1.T4b.B."+r["key"] for r in rows}
    dutch=[r for r in bad if r["family"]=="NETHERLANDS"]
    insist(len(bad)==14 and len(dutch)==10 and set(sub["counterexamples"])==ids(bad) and
           set(sub["failure_conditions"][0]["counterexamples"])==ids(dutch),"retained 14 losses and Dutch subset")
    sub["scope"]="仅 T4b 整板的等权平均服务缺额 L（预注册 H1：V_COST−B）。"
    sub["status"]="成立" if h["decision"]=="MET" else "不成立"
    prior=old["claims"][0]["subclaims"][0]
    insist(prior["failure_conditions"]==sub["failure_conditions"] and prior["counterexamples"]==sub["counterexamples"]
           and old["claims"][0]["failure_conditions"]==c1["failure_conditions"],"original limits are immutable")
    frozen=encode(new)
    a=raw.decode().splitlines();b=frozen.decode().splitlines()
    insist(len(a)==len(b),"line layout unchanged")
    line_diff=[dict(line=i,pointer="/claims/0/subclaims/0/"+left.lstrip().split('"')[1],old_line=left,new_line=right)
               for i,(left,right) in enumerate(zip(a,b),1) if left!=right]
    insist([z["pointer"] for z in line_diff]==["/claims/0/subclaims/0/scope","/claims/0/subclaims/0/status"],"only two authorized JSON lines")
    metrics=sum(len(c["numbers"]) for c in new["claims"])
    log="\n".join([
        "Accepted stage-2 claims.json and delivery members: byte-identical to 0ca350d1.",
        f"H1: {h['decision']}, V_COST-B, {n}/{len(results['rows'])} valid; mean {ci['mean']:.2f} s, two-sided CI [{ci['lo']:.2f}, {ci['hi']:.2f}] s.",
        "C1.B: 成立, level=确认, scope=T4b whole-board mean only; consistent with sealed H1 decision.",
        "C1: 部分成立. Original 14 loss rows, including 10 Dutch losses, and original failure conditions preserved.",
        f"Revision: exactly 2 logical JSON fields; {metrics} numeric entries and all other fields unchanged. Facility=0; Slurm=0; H2=0."
    ])+"\n"
    manifest=dict(schema="aegisdc-t6-claims-amendment-r2",baseline=ACCEPTED,accepted_path=PREFIX+"claims.json",
        corrected_path=PREFIX+"r2/claims.json",original_sha256=digest(raw),corrected_sha256=digest(frozen),changed_lines=line_diff,
        unchanged_level={"pointer":"/claims/0/subclaims/0/level","value":"确认"},
        unchanged_limits=["/claims/0/status","/claims/0/failure_conditions","/claims/0/subclaims/0/failure_conditions","/claims/0/subclaims/0/counterexamples"],
        H1_source=dict(commit=T4B,path=RESULT,sha256=digest(data),fields=["/hypotheses/0/id","/hypotheses/0/comparator","/hypotheses/0/decision",
            "/hypotheses/0/comparison/available","/hypotheses/0/comparison/planned","/hypotheses/0/comparison/metrics/L","/hypotheses/0/comparison/directions"]),
        files={"claims.json":digest(frozen),"claims_check.py":digest(Path(__file__).read_bytes()),"verification.txt":digest(log.encode()),
               "README.md":digest((HERE/"README.md").read_bytes())},
        scope="This additive ledger supersedes only C1.B scope and status. All accepted scientific values and prior files are retained.")
    return frozen,encode(manifest),log.encode("utf8")


def check_accepted_files():
    manifest=sealed(ACCEPTED,PREFIX+"claims-delivery.json");m=json.loads(manifest)
    for fn,h in m["files"].items():
        data=sealed(ACCEPTED,PREFIX+fn)
        insist((T6/fn).read_bytes()==data and digest(data)==h,"stage-2 member "+fn)
    insist((T6/"claims-delivery.json").read_bytes()==manifest,"accepted manifest")


def run(check=True):
    check_accepted_files()
    payload,manifest,out=expected()
    for name,data in {"claims.json":payload,"delivery.json":manifest,"verification.txt":out}.items():
        if check:insist((HERE/name).read_bytes()==data,"not the authorized r2 "+name)
        else:(HERE/name).write_bytes(data)
    return out.decode()


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check",action="store_true",help="read-only H1/status, scope and preservation checks")
    mode.add_argument("--write",action="store_true",help="materialize the amendment in this new directory only")
    args=parser.parse_args()
    print(run(args.check),end="")
