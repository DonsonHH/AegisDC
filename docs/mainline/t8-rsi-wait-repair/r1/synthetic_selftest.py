"""Execute the stage-B controller on stand-in tokens only, or verify its saved evidence."""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from time import process_time_ns

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from jsonschema import Draft202012Validator

from fit_broker import Broker, SlotFailure, microseconds
from fit_evidence import Journal, Objects, exclusive, public_hex, signed
from fit_loop import run_fit
from fit_program import BASE, ZERO, canonical, fingerprint, macro, require, roster
from public_fixture import checks as public_checks
from read_fit import read_case

HERE=Path(__file__).resolve().parent
R0=HERE.parent/"r0"


def read(path): return json.loads(path.read_bytes())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


class SyntheticService:
    """Explicit public fabrication. No panel lookup or worker dispatch is available."""

    def __init__(self, case):
        self.case=case
        self.calls=0

    def __call__(self, binding, levels, ordinal):
        self.calls+=1
        start=process_time_ns()
        arm=binding["arm"];r=binding["round"];s=binding["slot"]
        if self.case=="baseline-stop" and arm=="PARENT" and ordinal==1:
            raise SlotFailure("FAILED","injected missing parent cost",None)
        if self.case=="partial" and (arm,r,s,ordinal)==("R",2,2,7):
            raise SlotFailure("PARTIAL","injected incomplete row",max(1,(process_time_ns()-start)//1000))
        weight=sum(x*y for x,y in zip(levels,(40,5,4,30,2,1)))
        loss=1000 if self.case=="plateau" else 1000-weight
        invalid=self.case=="hard" and levels==(1,0,0,0,0,0)
        if invalid:loss=0
        result={"L":str(loss)+".0000005","person":str(10+sum(levels))+".0000015",
                "hard_violations":int(invalid and ordinal==1)}
        actual=max(1,(process_time_ns()-start)//1000)
        # Inject an over-limit METER value only. The Slurm job never consumes this time.
        result["cpu_us"]=180_000_001 if self.case=="cap" and (arm,r,s,ordinal)==("O",1,1,3) else actual
        return result


class FixtureBroker(Broker):
    def __init__(self,store,signer,service):
        super().__init__(store,signer,service)
        self.case=service.case

    def evaluate(self,binding,levels):
        meter,packet=super().evaluate(binding,levels)
        if (binding["arm"],binding["round"],binding["slot"])!=("O",1,1):return meter,packet
        if self.case=="missing":return meter,None
        if self.case=="bad-signature":packet["signature"]="00"*64
        if self.case=="foreign-binding":
            p=deepcopy(packet["payload"]);p["binding"]["arm"]="R"
            packet=signed(self.signer,p)
        if self.case=="extra-field":
            p=deepcopy(packet["payload"]);p["data"]["unregistered_field"]=1
            packet=signed(self.signer,p)
        return meter,packet


def check_expectations(case, result, summary):
    o,r=result["arms"]["O"],result["arms"]["R"]
    if case in ("gain","plateau","hard"):
        require(all(a["statuses"]==["CLOSED"]*4 and a["emitted"]==16 and a["started"]==a["completed"]==768
                    for a in (o,r)) and summary["service_calls"]==1584, "balanced complete fixture")
        require(len(set(o["program_sha256"]))==1 and o["program_sha256"][0]==fingerprint(BASE),"O program invariant")
    if case=="gain":
        require(r["selected_slots"][:2]==[1,1] and r["next_effects"][0]=="CHANGED_MEMBERSHIP" and
                [2,1] in r["selected_changed_slots"],"R: changed grammar -> actual paid slot -> selected lineage")
    elif case=="plateau":
        require(all(a["selected_slots"]==[None]*4 and a["actually_paid_changed_slots"]==[] for a in (o,r)),
                "tied scores must retain the baseline")
    elif case=="hard":
        require(all(a["selected_slots"][0]!=1 for a in (o,r)),"tempting violated candidate promoted")
    elif case=="partial":
        require(o["statuses"]==r["statuses"]==["CLOSED","INCOMPLETE","UNRUN","UNRUN"] and
                (o["started"],o["completed"],r["started"],r["completed"])==(384,384,247,246)
                and summary["service_calls"]==679,"partial must preserve both totals and suffix")
    else:
        require(o["statuses"]==r["statuses"]==["INCOMPLETE","UNRUN","UNRUN","UNRUN"],"paired stop")
        expected={"cap":(3,3,51),"bad-signature":(48,48,96),"extra-field":(48,48,96),
                  "foreign-binding":(48,48,96),"missing":(48,48,96),"baseline-stop":(0,0,1)}[case]
        require((o["started"],o["completed"],summary["service_calls"])==expected and r["started"]==0,
                "retained partial or failed attempts")
    if case not in ("gain","plateau","hard"):
        require(summary["result"]["dual_lock"] is None and summary["result"]["stop"],"failed run produced lock")


def run_or_read(args):
    freeze=read(HERE/"b-freeze.json")
    for name,expect in freeze["sources"].items():require(sha(HERE/name)==expect,"pinned B source "+name)
    for name,expect in freeze["r0"].items():require(sha(R0/name)==expect,"pinned r0 "+name)
    registration=read(R0/"registration.json")
    schema=read(R0/"round-ledger.schema.json")
    Draft202012Validator.check_schema(schema)
    validate=Draft202012Validator(schema).validate
    freeze_sha=sha(HERE/"b-freeze.json")
    expected_keys=("rounds","proposals_per_round_per_improver","fit_rows_per_proposal",
                   "native_cpu_cap_s_per_position","optimizer_cpu_cap_s_per_round_per_arm","cpu_cap_s_per_improver")
    require([registration["budget"][k] for k in expected_keys]==[4,4,48,180,60,138480],"registered caps")
    frozen={"parent_bundle":registration["baseline"]["parent_bundle_sha256"],"policy_compiler":sha(HERE/"fit_program.py"),
            "search_interpreter":sha(HERE/"fit_program.py"),"selector":sha(HERE/"fit_program.py"),
            "facility_metrics":sha(HERE/"synthetic_selftest.py"),"score_adapter":sha(HERE/"fit_broker.py"),
            "sandbox":fingerprint(freeze["standin_access"]),"resource_envelope":fingerprint(registration["budget"]),
            "fit_commitment":fingerprint(freeze["fabricated_tokens"])}
    if not args.check:
        args.root.mkdir(exist_ok=False)
        require(microseconds("0.0000005")==0 and microseconds("0.0000015")==2,"decimal round-half-even")
        for cell in ("DIRECT_NEAR","ALARM_FAR"):
            for step,x in [(-1,ZERO),(1,(3,)*6)]:
                _,audit=roster(macro(cell,step),x,{x},2,4)
                require(all(item["result"]=="OUT_OF_RANGE" for item in audit["macro"]),"macro must skip without clipping")
        interface=public_checks()
    else:interface=read(args.root/"selftest.json")["standin_public_interface"]
    reports={}
    for case in freeze["cases"]:
        case_root=args.root/case
        context=fingerprint({"engineering":"stage1a","case":case,"freeze_sha256":freeze_sha})
        if not args.check:
            store=Objects(case_root)
            key=Ed25519PrivateKey.generate();score_key=Ed25519PrivateKey.generate()
            journal=Journal(store,key,context)
            access=journal.seal("engineering-role-scope",freeze["standin_access"])
            service=SyntheticService(case);broker=FixtureBroker(store,score_key,service)
            outcome=run_fit(journal,broker,freeze["r0"]["registration.json"],freeze["r0"]["design.json"],
                            frozen,validate,access)
            summary={"fixture_case":case,"context":context,"freeze_sha256":freeze_sha,
                     "registration_sha256":freeze["r0"]["registration.json"],"design_sha256":freeze["r0"]["design.json"],
                     "journal_key":public_hex(key),"score_key":public_hex(score_key),"frozen":frozen,"result":outcome,
                     "service_calls":service.calls}
            exclusive(case_root/"case.json",summary)
        else:summary=read(case_root/"case.json")
        require(summary["context"]==context and summary["frozen"]==frozen and summary["freeze_sha256"]==freeze_sha,
                "wrong engineering execution version")
        evidence=read_case(case_root,summary,validate)
        check_expectations(case,evidence,summary)
        reports[case]={"service_tokens":summary["service_calls"],"stopped":summary["result"]["stop"],
                       "dual_lock":summary["result"]["dual_lock"] is not None,"round_heads":summary["result"]["round_heads"],
                       "checked":evidence}
    report={"type":"T8 stage 1a synthetic controller selftest","freeze_sha256":freeze_sha,
            "cases":reports,"standin_public_interface":interface,"standin_round_records":8*len(reports),
            "standin_position_tokens":sum(v["service_tokens"] for v in reports.values()),
            "formal_FIT_rows_created":0,"formal_DEV_rows_created":0,"facility_calls":0,"real_child_score_calls":0,
            "official_overlap_queries":0,"H2_access":0,"H3_access":0}
    if args.check:
        require(report==read(args.root/"selftest.json"),"saved report does not match immutable evidence")
    else:exclusive(args.root/"selftest.json",report)
    print("PASS",len(reports),"engineering scenarios;",report["standin_round_records"],"schema-valid signed rounds;",
          report["standin_position_tokens"],"fabricated position tokens")
    print("PASS O fixed byte-for-byte; R paid next-round divergence, selected ancestry, terminal lock; tie and hard constraints")
    print("PASS partial, ceiling, signature, binding, extra key, missing packet and invalid parent preserve stops and suffixes")
    print("PASS zero facility, real child scoring, FIT/DEV panel creation, official overlap queries and H2/H3 access")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--check",action="store_true",help="Read original records only; no synthetic or research evaluation")
    run_or_read(p.parse_args())
