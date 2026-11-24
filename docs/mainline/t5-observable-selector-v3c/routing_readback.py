"""Reopen each saved S prefix, reconstruct public cells, and audit trigger/response identity."""
import gzip
import json
from pathlib import Path

from development import ROLES,previous
from control_v3c import OUT
from landscape import digest,read,sha,write
from selector import catalogue,features,select,signals


def need(ok,why):
    if not ok:raise ValueError(why)


def audit():
    panel=read(OUT/"panel.json");lock=read(OUT/"locked-selector.json")["fit"]
    report={}
    for key in panel["order"]:
        folder=OUT/"positions"/key/"S"
        if not (folder/"row.json").exists():
            report[key]=dict(state="NO_S_ROW");continue
        q=read(folder/"row.json")
        if q["status"]!="SCORED":
            report[key]=dict(state=q["status"],error=q.get("error"));continue
        z=read(folder/"selector.json")
        need(sha(folder/"selector.json")==q["selector_log"] and {k:z[k] for k in ("cell","at","selected")}==q["selection"],"selector log vs row")
        with gzip.open(folder/"original.jsonl.gz","rt") as fd:meta=json.loads(next(fd))["metadata"]
        static=catalogue(meta["inputs"]["dispatch_program"]["public"])
        ds=meta["policy_public_decisions"];ps=meta["v3_proposals"]
        need(len(ds)==len(ps)==61 and digest([[p["at"],p["view"],p["proposal"]] for p in ps])==q["proposal_index"],"complete actual response chain")
        history=[];found=None;at=None;cell=None;prefix=[];origin=""
        for i,probe in enumerate(z["probe_log"]):
            d,p=ds[i],ps[i];view=d["view"]
            need(probe["t"]==view["time"]==p["at"]==i*60 and probe["public"]==p["view"]==digest(view),"raw online public frame")
            history.append(signals(view));names=[a for a,b in probe["probes"]]; hashes=dict(probe["probes"])
            need(names==list(ROLES[:len(names)]) and len(set(names))==len(names),"ordered unique probes")
            prefix.append(p["view"]);first=probe["first_nonempty"]
            if first is None:
                need(len(names)==58 and probe["answer"]==dict(cell=None,selected=None) and p["requested"] is None and
                     p["proposal"]==hashes[ROLES[0]],"complete no-trigger and actual wait")
            else:
                need(i==len(z["probe_log"])-1 and names[-1]==first,"first trigger short circuit")
                cell=features(static,history);found=select(lock,cell);at=view["time"]
                need(probe["answer"]==dict(cell=list(cell),selected=found) and list(cell)==z["cell"] and found==z["selected"] and at==z["at"],"reconstruct exact cell and trigger independently")
                if found in hashes:
                    need(hashes[found]==p["proposal"],"selected already-probed response identity")
                    origin="MATCHED_PROBED_AND_NATIVE_RESPONSE"
                else:
                    need(found in z["pids"] and z["pids"][found]!=q["entry"]["pid"],"selected-on-demand original worker")
                    origin="NATIVE_CHAIN_AND_ON_DEMAND_WORKER; NO_SECOND_RESPONSE_HASH"
        if found is None:
            need(len(history)==61 and all(p["requested"] is None for p in ps) and all(z[k] is None for k in ("at","cell","selected")),"explicit no-trigger through horizon")
        report[key]=dict(state="TRIGGERED" if found is not None else "NEVER_TRIGGERED",selected=found,at=at,cell=cell,
                         response_identity=origin,prefix_hashes=prefix,actual_L=q["L"],actual_U=q["U"],actual_signed_count=len(q["issued"]),
                         issued_identity=digest(q["issued"]),selector_sha256=q["selector_log"],native_sha256=q["raw"],full_response_index=q["proposal_index"])
    write(OUT/"routing-readback.json",dict(rows=report,facilities_called=0))
