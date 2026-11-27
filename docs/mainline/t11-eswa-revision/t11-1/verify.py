"""Verify release, return receipts, denominators and frozen Git bytes without running a method."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
REL=HERE.relative_to(ROOT).as_posix()
BASE="e3484fd1967164bfb3fe7b5d9c0309e513e95444"
FIRST="c41ab91096c25399b24193f652dbb8b0b9d39ebd"
LOCK="8dfc03a7c1df9c254f246e1d40add424a0c04218ffdd345acc2b05ade6dc7284"
PARENT="docs/mainline/t11-eswa-revision/"

def require(test,message):
    if not test:raise ValueError(message)

def git(*args):
    return subprocess.check_output(["git",*args],cwd=ROOT)

def blob(rev,path):
    return git("cat-file","blob",rev+":"+path)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def obj(path):
    return json.loads(path.read_bytes())

def packed(v):
    return json.dumps(v,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(",",":")).encode()

def tsv(path):
    with path.open(encoding="utf8",newline="") as f:return list(csv.DictReader(f,delimiter="\t"))

def check_source():
    require(sha(blob(BASE,PARENT+"protocol-freeze.json"))==LOCK,"T11-0 protocol")
    desc=obj(HERE/"source-manifest.json")
    require(desc["accepted_parent"]==BASE and desc["interpretation_commit"]==FIRST and desc["protocol_sha256"]==LOCK,
            "source release provenance")
    require(set(desc["files"])==set(desc["file_origins"]),"complete source map")
    for name,digest in desc["files"].items():
        rev,path=desc["file_origins"][name]
        require(sha(blob(rev,path))==digest,"source member "+name)
        if path.startswith(REL+"/"):
            require(sha((ROOT/path).read_bytes())==digest,"released file differs from its freeze: "+path)
    require((HERE/"interpretation-before-run.md").read_bytes()==blob(FIRST,REL+"/interpretation-before-run.md"),"pre-run interpretation")
    design=json.loads(blob(BASE,PARENT+"design.json"))
    panel=design["panel"]; native=panel["input_revision"]
    archive=blob(native,panel["archive"]); manifest=blob(native,panel["manifest"])
    require(sha(archive)==panel["archive_sha256"] and sha(manifest)==panel["manifest_sha256"],"input archive and order")
    inputs=json.loads(manifest);hashes={}
    for line in gzip.decompress(archive).splitlines():
        key,case=json.loads(line);require(key not in hashes,"duplicate registered condition")
        hashes[key]=sha(packed(case)+b"\n")
    require(list(hashes)==inputs["order"] and hashes==inputs["files"] and len(hashes)==72,"original per-condition bytes")
    raw=blob(panel["score_revision"],panel["scores"])
    require(sha(raw)==panel["scores_sha256"],"archived public score file")
    pairs={u["key"]:[u["input"],u["score"],u["raw"],u["IPC"],u["job"],u["attempt"]]
           for u in json.loads(gzip.decompress(raw))["units"] if u["role"]=="V_COST"}
    checking=obj(HERE/"stage0-identity.json")["matched_remote_development_archive"]
    require(len(pairs)==72 and sha(packed(pairs))==checking["stable_center_ledger"] and
            all(row[0]==hashes[k] for k,row in pairs.items()),"historical center matches remote identity receipt")
    reg=obj(HERE/"registration.json"); groups=reg["groups"]
    require(len(groups)==len(reg["order"])==63 and sum(g["seconds"] for g in groups.values())==229800,"job caps")
    got=[(g["role"],key) for g in groups.values() if g["kind"]=="science" for key in g["keys"]]
    require(len(got)==720 and set(got)=={(role,k) for role in reg["roles"] for k in hashes},"registered position membership")
    return desc,reg,hashes

def verify_sums(folder,name):
    record=folder/name
    lines=record.read_text(encoding="utf8").splitlines();names=[]
    for line in lines:
        digest,relative=line.split("  ",1)
        path=(folder/relative).resolve()
        require(path.is_relative_to(folder.resolve()) and not path.is_symlink() and re.fullmatch(r"[0-9a-f]{64}",digest),"digest entry")
        require(sha(path.read_bytes())==digest,"published digest "+relative)
        names.append(relative)
    require(len(names)==len(set(names)),"duplicate digest entries")
    return set(names)

def verify_results(release,reg,hashes):
    root=HERE/"results";account=obj(root/"accounting.json")
    ret=verify_sums(root,"RETURN-SHA256SUMS.txt")
    actual={p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    require(actual==ret|{"RETURN-SHA256SUMS.txt"},"complete remote return")
    require(account["source_manifest_sha256"]==sha((HERE/"source-manifest.json").read_bytes()) and
            account["center_native_runs"]==account["center_scores_created"]==account["scientific_retries"]==0 and
            account["sealed_H2_generate_read_derive"]==account["sealed_H3_generate_read_derive"]==[0,0,0],"fixed scientific boundary")
    jobs=tsv(root/"jobs.tsv"); by_role=tsv(root/"per-role-ledger.tsv")
    require(len(jobs)==len({j["job"] for j in jobs})==account["jobs"]<=63 and
            sum(int(j["reserved_cpu_s"]) for j in jobs)==account["reserved_cpu_s"]<=229800,"allocated CPU and job caps")
    for j in jobs:
        require(j["group"] in reg["groups"] and int(j["reserved_cpu_s"])==reg["groups"][j["group"]]["seconds"],"job allocation")
    require(abs(sum(float(j["reported_used_cpu_s"]) for j in jobs if j["reported_used_cpu_s"])-account["reported_used_cpu_s"])<1e-4,"actual CPU accounting")
    require({r["role"] for r in by_role}==set(reg["roles"]) and len(by_role)==10 and
            sum(int(r["planned"]) for r in by_role)==720,"full planned denominator")
    require(sum(int(r["native_entries"]) for r in by_role)==account["charged_native_calls"]<=720 and
            sum(int(r["complete_scores"]) for r in by_role)==account["complete_new_scores"],"charged and returned units")
    qualpath=root/"qualification/acceptance.json"
    qual=obj(qualpath) if qualpath.exists() else {}
    released=qual.get("pass") is True
    if not released:
        require(account["charged_native_calls"]==account["complete_new_scores"]==0 and
                not any(j["kind"]=="science" for j in jobs),"no science before qualification")
        require((root/"STOP.json").exists(),"documented engineering stop")
        print("PASS phase-0 stop preserved; all 720 positions unexecuted; no scientific result inferred")
        return account
    w=obj(root/"qualification/public-witness.json")
    require(qual["native_calls"]==w["facility_calls"]==w["native_runs"]==0 and w["status"]=="PASS" and
            w["passed"] is True and len(w["checks"])==10 and all(v["passed"] for v in w["checks"].values()) and
            sha((root/"qualification/public-witness.json").read_bytes())==qual["witness_sha256"],"public engineering outcome")
    initial=qual["initial_implementation_manifest"];final=qual["implementation_manifest"]
    previous=obj(HERE/"source-manifest-failed-qualification.json")
    require(initial==sha((HERE/"source-manifest-failed-qualification.json").read_bytes()) and
            final==account["source_manifest_sha256"] and
            {n for n,v in release["files"].items() if previous["files"].get(n)!=v}=={"source/worker.py"},
            "single-member engineering repair")
    attempts=root/"qualification"/"attempts"
    old=obj(attempts/initial/"public-witness.json"); accepted=obj(attempts/final/"receipt.json")
    require(old["failed"]==["oat_single_change"] and old["native_runs"]==old["facility_calls"]==0 and
            old["qualification_sha256"]==w["qualification_sha256"] and accepted["pass"] and
            accepted["job"]==obj(attempts/initial/"receipt.json")["job"]==qual["job"],"retained original fixture and failure")
    scan=obj(root/"qualification/historical-fields.json")
    require(scan["eligible_rows"]==72 and scan["frames"]==61*scan["native_original_hashes_verified"]<=4392 and
            (scan["frames"]==4392 or scan["status"]=="TIMING_FRAMES_UNAVAILABLE" and scan["unavailable_frames"]),
            "old development timing inspection")
    if account.get("statistical_readback")=="UNRESOLVED":
        adjudicated=[j for j in jobs if j["group"]=="analysis"]
        require(len(adjudicated)==1 and (root/"science-settled.json").is_file() and
                not (root/"analysis"/"analysis.json").exists(),"failed readback may not publish estimates")
        print("PASS terminal readback failure retained; no statistical panel certified")
        return account
    ap=root/"analysis";small=verify_sums(ap,"SHA256SUMS.txt")
    require({"panel.md","analysis.json","positions.tsv","scope-contrasts.tsv","timing.tsv"}<=small,"paired analysis artifacts")
    evidence=tsv(ap/"native-evidence-index.tsv"); raw=obj(ap/"native-readback-receipt.json")
    require(len(evidence)==720 and {(v["role"],v["key"]) for v in evidence}=={(r,k) for r in reg["roles"] for k in hashes} and
            all(v["input_sha256"]==hashes[v["key"]] for v in evidence),"all planned evidence slots")
    require(raw["index_sha256"]==sha((ap/"native-evidence-index.tsv").read_bytes()) and
            raw["native_calls"]==account["charged_native_calls"] and raw["committed_scores"]==account["complete_new_scores"] and
            raw["metadata_and_clocks_checked"]==raw["committed_scores"]+raw["as_run_diagnostics_checked"]==
            account["complete_as_run_scores"],"private readback accounting")
    analysis=obj(ap/"analysis.json")
    require(analysis["label"]=="事后补充、非确认" and analysis["sample"]["planned_conditions"]==72 and
            analysis["sample"]["planned_new_positions"]==720 and set(analysis["interpretation"])=={"MYOPIC","POMCP"},"scope and interpretive status")
    require(analysis["program_sha256"]==release["files"]["source/analysis.py"],"published analysis program")
    source_design=json.loads(blob(BASE,"docs/mainline/t11-eswa-revision/design.json"))
    expected_scopes={"overall":72,**{"family/"+f:12 for f in source_design["panel"]["families"]},
                     **{"duration/"+str(d):24 for d in (0,600,1200)}}
    require(set(analysis["scopes"])==set(expected_scopes),"registered scope set")
    for name,size in expected_scopes.items():
        scope=analysis["scopes"][name]
        require(scope["n"]==size and set(scope["pairs"])==set(reg["roles"]),"registered scope denominator: "+name)
        for role,pair in scope["pairs"].items():
            direction=("V_COST",role) if role in ("MYOPIC","POMCP") else (role,"V_COST")
            require((pair["left"],pair["right"])==direction and pair["planned"]==size,
                    "paired direction or denominator: "+name+"/"+role)
            estimates=pair["compliant_full_scope"]
            require((estimates is None)==(pair["pairable"]<size),"missing/invalid pair estimate suppression")
            if estimates is not None:
                require(all(k in estimates and estimates[k]["lo"]<=estimates[k]["hi"] for k in
                            ("L","U","person","tool","fee","refusals","NA_3600","PV_3600")),
                        "uncertainty and required outcome coverage")
    complete_rows=tsv(ap/"positions.tsv")
    require(len(complete_rows)==720 and {(r["role"],r["key"],r["input_sha256"]) for r in complete_rows}==
            {(r["role"],r["key"],r["input_sha256"]) for r in evidence},"per-position publication identity")
    timer=analysis["timing"]
    require(set(reg["roles"])|{"V_COST"}==set(timer),"timing role membership")
    for role in [*reg["roles"],"V_COST"]:
        group=timer[role]["groups"]["ALL"]
        ipc=group["timing_ns"]["ipc_wall_ns"]
        if ipc["n"]:
            require(0<=ipc["median"]<=ipc["p95"]<=ipc["max"],"timing distribution: "+role)
    t=timer["POMCP"]["groups"]["ALL"]["tree_counts"]
    require((t["tree_steps"]["total"] or 0)<=2248704 and (t["leaf_evaluations"]["total"] or 0)<=562176,
            "tree and leaf counters")
    if timer["V_COST"]["validated_full_series"]:
        require(timer["V_COST"]["groups"]["ALL"]["timing_ns"]["ipc_wall_ns"]["n"]==4392 and
                timer["V_COST"]["source"] in ("archived_online","isolated_worker_replay"),"validated original timing scope")
    for role,pair in analysis["scopes"]["overall"]["pairs"].items():
        if role not in reg["roles"]:continue
        if pair["compliant_full_scope"] is not None:
            require(pair["planned"]==72 and all(v["status"]=="COMPLETE_COMPLIANT" for v in evidence if v["role"]==role),
                    "incomplete or hard-violating pair cannot yield a main interval")
    if account["complete_new_scores"]==720:
        projection=obj(root/"pilot-projection.json")
        require(projection["continue"] is True and account["returned_public_decisions"]==account["actual_decision_calls"]==43920,
                "complete position/call denominator and pilot release")
    print("PASS 10 public witnesses, historical timing inspection, native receipts, tagged contrasts and full planned suffix")
    return account

def main(checkout,write):
    release,reg,hashes=check_source()
    account=verify_results(release,reg,hashes)
    if checkout:
        names={p[len(REL)+1:] for p in git("ls-tree","-r","--name-only","HEAD","--",REL+"/").decode().splitlines()}
    else:
        names={p.relative_to(HERE).as_posix() for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
        names.add("SHA256SUMS.txt")
    require({"README.md","SHA256SUMS.txt","source-manifest.json","results/accounting.json","manuscript-panel-en.md"}<=names,"full delivery set")
    if write:
        (HERE/"SHA256SUMS.txt").write_bytes("".join(sha((HERE/f).read_bytes())+"  "+f+"\n" for f in sorted(names-{"SHA256SUMS.txt"})).encode())
    require(verify_sums(HERE,"SHA256SUMS.txt")==names-{"SHA256SUMS.txt"},"complete file index")
    if checkout:
        for f in names:require((HERE/f).read_bytes()==blob("HEAD",REL+"/"+f),"fresh Git bytes "+f)
        require(not git("diff","--name-only",BASE,"HEAD","--",":(top,exclude)"+REL+"/**"),"changed accepted package")
        print("PASS",len(names),"files match Git HEAD byte-for-byte; prior packages unchanged")
    print("PASS 72 input identities, original V_COST scores preserved; native entries",account["charged_native_calls"],
          "jobs",account["jobs"],"reserved CPU s",account["reserved_cpu_s"])
    print("SHA-256 file index:",sha((HERE/"SHA256SUMS.txt").read_bytes()))

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    g=p.add_mutually_exclusive_group()
    g.add_argument("--check",action="store_true")
    g.add_argument("--write-manifest",action="store_true")
    p.add_argument("--checkout-bytes",action="store_true")
    a=p.parse_args();main(a.checkout_bytes,a.write_manifest)
