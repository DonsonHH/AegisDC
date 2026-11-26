"""Public-only verification of FIT rounds, detached signatures, displayed numbers and resource accounts."""

import argparse
from copy import deepcopy
import csv
from decimal import Decimal
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/"r1"))
from fit_evidence import authenticated
from fit_program import canonical, fingerprint, policy_id
from read_fit import independent_list
from read_native_fit import cpu_seconds, public_score
from write_fit_report import write as render


def read(p):return json.loads(p.read_bytes())
def check(t,why):
    if not t:raise ValueError(why)


def schemas(folder):
    schema=HERE.parent/"r0/round-ledger.schema.json"
    paths=sorted((folder/"rounds").glob("*.json"));check(len(paths)==8,"round files")
    try:from jsonschema import Draft202012Validator
    except ImportError:
        pwsh=shutil.which("pwsh");check(pwsh,"JSON Schema validator required")
        script=('$ErrorActionPreference="Stop"; $a=[Console]::In.ReadToEnd() | ConvertFrom-Json; '
                'foreach($p in $a){if (-not (Test-Json -LiteralPath $p -SchemaFile $env:T8_PUBLIC_SCHEMA)){throw $p}}')
        subprocess.run([pwsh,"-NoProfile","-NonInteractive","-Command",script],check=True,text=True,
                       input=json.dumps([str(p) for p in paths]),env=dict(os.environ,T8_PUBLIC_SCHEMA=str(schema)))
    else:
        validator=Draft202012Validator(read(schema))
        for p in paths:validator.validate(read(p))


def verify(folder):
    result=read(folder/"results.json");proof=read(folder/"public-proof.json")
    envelope=read(HERE/"scoring/execution-envelope-recovery.json")
    check(sha_key(proof["journal_public"])==envelope["signer_fingerprints"]["journal"] and
          sha_key(proof["score_public"])==envelope["signer_fingerprints"]["evaluator"],"registered technical signers")
    check(result["execution_envelope_sha256"]==proof["context"]==fingerprint(envelope) and
          result["fit_batch_root"]==envelope["frozen"]["fit_commitment"],"prior published execution identity")
    for h,obj in proof["objects"].items():check(fingerprint(obj)==h,"sidecar SHA-256")
    def obj(ref):
        value=proof["objects"][ref["sha256"]]
        check(ref["locator"]=="objects/"+ref["sha256"] and len(canonical(value))==ref["bytes"],"reference bytes")
        return value
    def event(ref,purpose):
        payload=authenticated(obj(ref),proof["journal_public"])
        check(payload["context"]==proof["context"] and payload["purpose"]==purpose,"signed event")
        return payload["body"]
    def paid(ref):return authenticated(obj(ref),proof["score_public"])
    schemas(folder)
    parent=event(proof["shared"],"shared-parent-return")["slot"]
    check(public_score(parent["fit_return"])==result["baseline"]["score"],"shared baseline public result")
    if parent["fit_return"]:
        p=paid(parent["fit_return"]["receipt"])
        check(p["binding"]["arm"]=="PARENT" and p["binding"]["policy_id"]==parent["policy"]["id"] and
              all(p["data"][k]==parent["fit_return"][k] for k in ("L_sum_us","person_sum_us","hard_violations")),
              "shared baseline signed aggregate")
    heads={};rounds=0
    for a in ("O","R"):
        prior=None;seen={(0,)*6};score=parent["fit_return"]
        for n,reported in enumerate(result["arms"][a]["rounds"],1):
            rec=read(folder/"rounds"/f"{a}-{n}.json");rounds+=1
            check(rec["arm"]==a and rec["round"]==n and rec["frozen"]==envelope["frozen"] and
                  rec["registration_sha256"]==envelope["registration_sha256"] and rec["design_sha256"]==envelope["design_sha256"],
                  "versioned round")
            body=deepcopy(rec);seal=event(body["audit"].pop("record_seal"),"round")
            check(seal["payload_sha256"]==fingerprint(body) and fingerprint(rec)==reported["record_sha256"] and
                  rec["previous_record_sha256"]==(fingerprint(prior) if prior else None),"round signatures and ancestry")
            check(rec["status"]==reported["status"] and len(rec["slots"])==len(reported["slots"])==4,"slot denominator")
            before=rec["before"]
            if before and rec["accounting"]["emitted_proposals"]:
                current=tuple(before["incumbent"]["levels"])
                predicted=independent_list(before["ast"],current,seen,n)
                check(predicted==[tuple(s["policy"]["levels"]) for s in rec["slots"]],"independent prepaid roster replay")
            order=[s["policy"] for s in rec["slots"]]
            for s,t in zip(rec["slots"],reported["slots"]):
                check(s["slot"]==t["slot"] and s["started_fit_n"]==t["started"] and s["complete_fit_n"]==t["completed"] and
                      public_score(s["fit_return"])==t["score"],"per-slot public accounting")
                if s["policy"]:
                    p=s["policy"];check(obj(p["bytes"])==p["levels"]==t["levels"] and p["id"]==t["id"]==
                        policy_id(p["levels"],rec["design_sha256"],rec["frozen"]["parent_bundle"]),"public descriptor")
                if s["fit_return"]:
                    packet=paid(s["fit_return"]["receipt"])
                    check(packet["binding"]=={"context":proof["context"],"arm":a,"round":n,"slot":s["slot"],
                          "policy_id":s["policy"]["id"],"roster_sha256":fingerprint(order)} and
                          packet["data"]["scheduled"]==packet["data"]["completed"]==48 and
                          all(packet["data"][k]==s["fit_return"][k] for k in ("L_sum_us","person_sum_us","hard_violations")),
                          "signed own-arm aggregate")
            if rec["status"]=="CLOSED":
                if prior:check(before==prior["after"],"before/after continuity")
                ranked=sorted([s for s in rec["slots"] if s["fit_return"]["hard_violations"]==0],
                    key=lambda s:(s["fit_return"]["L_sum_us"],s["fit_return"]["person_sum_us"],s["policy"]["levels"]))
                winner=ranked[0] if ranked and ranked[0]["fit_return"]["L_sum_us"]<score["L_sum_us"] else None
                check(rec["selection"]["accepted_slot"]==reported["selected_slot"]==(winner["slot"] if winner else None),
                      "strict L gain and tie rules")
                if winner:score=winner["fit_return"]
                check(rec["after"]["paid_score_receipt"]==score["receipt"],"selected paid slot")
                if a=="O":check(before["ast"]==rec["after"]["ast"]=={"op":"base"},"O unchanged program")
                check(fingerprint(before["ast"])==reported["program_before_sha256"] and
                      fingerprint(rec["after"]["ast"])==reported["program_after_sha256"],"program bytes")
                seen.update(tuple(s["policy"]["levels"]) for s in rec["slots"])
                if n<4:
                    w=rec["next_witness"];center=tuple(rec["after"]["incumbent"]["levels"])
                    for k,ast in (("before_roster",before["ast"]),("after_roster",rec["after"]["ast"])):
                        check([tuple(p["levels"]) for p in obj(w[k])]==independent_list(ast,center,seen,n+1),
                              "counterfactual programme roster")
                if prior:
                    new=[s["slot"] for s in rec["slots"] if s["policy"]["id"] not in prior["next_witness"]["before_policy_ids"]]
                    check(new==reported["new_paid_slots"]==rec["incoming_witness"]["actually_paid_new_slots"],"actual paid change")
            prior=rec
        heads[a]=fingerprint(prior)
        if proof["dual_lock"]:
            final=result["arms"][a]["locked"]
            check(final["id"]==prior["after"]["incumbent"]["id"] and final["score"]==public_score(score),"final FIT lock")
    check(heads==result["private_round_record_heads"],"two terminal round heads")
    if proof["dual_lock"]:
        check(event(proof["dual_lock"],"dual-fixture-or-study-lock")["round_heads"]==heads and
              result["status"]=="DUAL_LOCKED_PENDING_REVIEW" and result["native_starts"]==result["scored_positions"]==1584,
              "dual lock and complete native denominator")
    with (folder/"sacct.psv").open(encoding="utf8",newline="") as f:
        acc={row["JobID"]:row for row in csv.DictReader(f,delimiter="|")}
    total=Decimal(0)
    for j in result["jobs"]:
        raw=acc[j["job"]]
        check(raw["State"]==j["state"] and raw["ExitCode"]==j["exit"] and
              cpu_seconds(raw["TotalCPU"])==Decimal(j["actual_cpu_s"]) and
              j["reserved_cpu_s"]==60*int(raw["TimelimitRaw"])*int(raw["AllocCPUS"]),"job accounting")
        total+=Decimal(j["actual_cpu_s"])
    check(total==Decimal(result["total_slurm_cpu_s"]) and len(result["jobs"])<=10 and
          sum(j["reserved_cpu_s"] for j in result["jobs"])==result["total_reserved_cpu_s"]<=285900,"reservation cap")
    check(total+Decimal(result["local_intake_comparison_cpu_s"])<=285900 and
          result["dev_positions"]==result["h2_access"]==result["h3_originals_access"]==0 and
          all(j["stage"] in ("input","parent","parent-a2","pilot","r2O","r2R","r3O","r3R","r4O","r4R")
              for j in result["jobs"]),"actual CPU ceiling and FIT-only stages")
    if proof["dual_lock"]:
        check(result["max_charged_position_cpu_us"]<=180_000_000 and result["observed_native_hard_violations"]==0 and
              all(v["charged_arm_cpu_us"]<=138480*1_000_000 for v in result["arms"].values()),"hard and per-arm constraints")
    if "pilot_projection" in result:
        pp=result["pilot_projection"]
        check(Decimal(pp["planned_reserved_cpu_s"])<=6*Decimal(pp["pilot_total_cpu_s"]) and
              pp["planned_reserved_cpu_s"]==sum(j["reserved_cpu_s"] for j in result["jobs"] if j["stage"].startswith("r")),
              "measured pilot extrapolation")
    check((folder/"report.md").read_bytes()==render(result).encode(),"reported numbers, tables and labels")
    print(f"PASS {rounds} signed, schema-valid rounds; all 32 scheduled candidate slots and the shared baseline")
    print("PASS paid ordinal counts, signed aggregates, programme replay, selected ancestry and reported locks/stop")
    print("PASS Slurm original summary, measured reservation caps, manuscript tables and closed DEV boundary")


def sha_key(k):return hashlib.sha256(bytes.fromhex(k)).hexdigest()


class ReviewCells(HTMLParser):
    """Read rendered table cells without accepting the embedded Markdown as evidence."""

    def __init__(self):
        super().__init__()
        self.cells = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "td":
            self.current = []

    def handle_data(self, value):
        if self.current is not None:
            self.current.append(value)

    def handle_endtag(self, tag):
        if tag == "td" and self.current is not None:
            self.cells.append("".join(self.current).strip())
            self.current = None


def verify_review(folder):
    result = read(folder / "results.json")
    if result["status"] != "DUAL_LOCKED_PENDING_REVIEW":
        return
    timing = read(folder / "cpu-scope.json")
    denominators = {"PARENT": result["baseline"]["completed"],
                    **{a: result["arms"][a]["completed"] for a in ("O", "R")}}
    check(timing["unit"] == "nanoseconds" and timing["per_position_cap_ns"] == 180_000_000_000 and
          {a: v["positions"] for a, v in timing["arms"].items()} == denominators, "timing coverage")
    for row in timing["arms"].values():
        check(row["positions"] == 48 * row["slots"] and 0 < row["max_recorded_launch_to_terminal_ns"]
              <= row["max_position_cpu_upper_bound_ns"] <= timing["per_position_cap_ns"], "timing upper bound")
    page = ReviewCells()
    page.feed((folder / "review.html").read_text(encoding="utf8"))
    for i, slot in enumerate([result["baseline"], *(result["arms"][a]["locked"] for a in ("O", "R"))]):
        score = slot["score"]
        check(page.cells[3*i+1:3*i+3] == [f"{score['L_mean_s']:.6f}", f"{score['person_mean_s']:.6f}"],
              "visible review table FIT scores")
    print("PASS published timing summary covers 1,584 positions within cap and three rendered FIT score rows match")


def checkout_bytes(folder):
    """Compare the declared public release to the actual checkout and its immutable Git objects."""
    root=HERE.parents[3]
    manifest=read(folder/"delivery.json")
    def blob(revision,path):
        return subprocess.check_output(["git","cat-file","blob",revision+":"+path],cwd=root)
    prefix=folder.relative_to(root).as_posix()+"/"
    committed=set(subprocess.check_output(["git","ls-tree","-r","--name-only","HEAD","--",prefix],cwd=root).decode().splitlines())
    check(committed=={prefix+x for x in [*manifest["public_files"],"delivery.json"]},"complete declared public result set")
    for name,entry in manifest["public_files"].items():
        data=(folder/name).read_bytes()
        check(len(data)==entry["bytes"] and hashlib.sha256(data).hexdigest()==entry["sha256"] and
              data==blob("HEAD",prefix+name),"published original bytes: "+name)
    check((folder/"delivery.json").read_bytes()==blob("HEAD",prefix+"delivery.json"),"published manifest")
    r=read(folder/"results.json")
    for p,entry in manifest["versioned_dependencies"].items():
        original=blob(entry["revision"],p)
        check(hashlib.sha256(original).hexdigest()==entry["sha256"],"execution revision bytes: "+p)
    check(manifest["versions"]["native_fit"]==r["execution_revision"] and
          manifest["versions"]["input_job"]=="6fe60fde8ad51003918989051245f9de6bfbc315" and
          manifest["versions"]["request"]=="ec5a3846457ef8f8435de1e6b641318b87ed229b" and
          manifest["versions"]["signed_receipt"]=="7518bc3f66a03eb56b68640aa8fd5e0a6d169a01","execution publication mapping")
    print(f"PASS {len(committed)} public delivery files byte-for-byte against Git; "
          f"{len(manifest['versioned_dependencies'])} versioned source/evidence dependencies")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--check",required=True,action="store_true")
    parser.add_argument("--checkout-bytes",action="store_true")
    parser.add_argument("--folder",type=Path,default=HERE/"results");args=parser.parse_args()
    verify(args.folder.resolve())
    verify_review(args.folder.resolve())
    if args.checkout_bytes:checkout_bytes(args.folder.resolve())
