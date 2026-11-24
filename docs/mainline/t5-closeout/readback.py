"""Reconcile sealed T5 results from Git objects. No facility, policy, random or seed interface."""
import argparse
from collections import Counter
from datetime import datetime
import gzip
import hashlib
import json
from math import isclose
from pathlib import Path
from statistics import mean
import subprocess

BASE = "25f86d8c7de5cad37e6b47d01a4991f161db0539"
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
V1 = "t5-ordinary-improvement-development-v1"
V2 = "t5-ordinary-improvement-development-v2"
V3A = "t5-landscape-diagnostic-v3a"
V3B = "t5-block-recombination-v3b"
V3C = "t5-observable-selector-v3c"


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def require(ok, message):
    if not ok:
        raise ValueError(message)


def close(a, b):
    return isclose(a, b, rel_tol=1e-12, abs_tol=1e-9)


def signs(values):
    return {"better":sum(v < 0 for v in values), "equal":sum(v == 0 for v in values), "worse":sum(v > 0 for v in values)}


def build():
    sources = {}
    def load(label, pkg, file):
        name = f"docs/mainline/{pkg}/{file}"
        data = git("show", BASE+":"+name)
        sources[label] = {"path":name,"sha256":hashlib.sha256(data).hexdigest(),
                          "git_blob":git("rev-parse", BASE+":"+name).decode().strip()}
        return (json.loads(gzip.decompress(data)) if file.endswith(".gz")
                else json.loads(data) if file.endswith(".json") else data.decode())

    old = load("dev", V3C, "development.json")
    new = load("new", V3C, "confirmation-result.json")
    reg = load("lock", V3C, "locked-selector.json")
    panel = load("panel", V3C, "new-panel.json")
    receipt = load("receipt", V3C, "confirmation-receipt.json")
    r0 = load("dev_receipt", V3C, "development-receipt.json")
    require(r0["result_sha256"] == sources["dev"]["sha256"] and receipt["result_sha256"] == sources["new"]["sha256"], "published result bytes")
    require(receipt["lock"]["sha256"] == sources["lock"]["sha256"] and receipt["panel"]["sha256"] == sources["panel"]["sha256"], "published lock/panel")
    a = old["rows"]; b = new["conditions"]
    require(len({r["key"] for r in a}) == len(a) == 36 and [r["key"] for r in b] == panel["order"]
            and len(set(panel["order"])) == len(b) == 36, "complete paired panels")
    for field, lane in (("S_gap","S_L"),("W_gap","W_L"),("F_gap","F_L")):
        require(all(close(r[field], r[lane]-r["lower"]) for r in a), "old gap "+lane)
        require(close(mean(r[field] for r in a),old["means"][field]), "old mean "+lane)
    da = [r["S_L"]-r["W_L"] for r in a]
    require(all(close(v,r["delta"]) for r,v in zip(a,da)) and close(mean(da),old["primary"]["mean"]), "old paired delta")
    db=[]; failures=[]; reserve=[]; fallback=[]; matched=[]; unchecked=[]
    for i,r in enumerate(b):
        s, w = (r["arms"][lane]["L"] for lane in ("S","W"))
        y=r["lower"]["certified_min"]
        require(r["arms"]["W"]["entry"]["actual"] == reg["fit"]["winner"], "locked W at "+r["key"])
        if r["lower"]["status"] == "ATTAINED" and close(w,y): matched.append(r["key"])
        select = r["arms"]["S"]["selection"]; cell="|".join(select["cell"]); definition=new["cells"][cell]
        require(r["key"] in definition["keys"] and select["selected"] == definition["selected"] == reg["fit"]["cells"].get(cell,reg["fit"]["winner"]), "cell selection")
        delta=s-w; db.append(delta)
        record={"key":r["key"],"family":r["family"],"source":f"new#/conditions/{i}","cell":cell,"selected":select["selected"],
                "S_L":s,"W_L":w,"certified_min":y,"S_minus_W":delta,"S_gap":s-y}
        if delta>0: failures.append(record)
        if r["family"]=="RESERVE_TRANSFER": reserve.append(record)
        if definition["fallback"]: fallback.append(record)
        if not r["lower"]["actual_chain"]:unchecked.append(r["key"])
    all_co = {}
    for role, obj in new["comparisons"].items():
        scores=[r["arms"]["S"]["L"]-r["arms"][role]["L"] for r in b]
        require(obj["pairs"] == obj["planned"] == len(scores) and close(mean(scores),obj["ci"]["mean"]), "contrast "+role)
        all_co[role] = {"source":f"new#/comparisons/{role}","pairs":obj["pairs"],**obj["ci"]}
    require(close(mean(db),all_co["W"]["mean"]) and (new["primary_verdict"]=="PASS") == (all_co["W"]["upper"]<0), "new verdict")
    require(all(r["selected"]==reg["fit"]["winner"] and r["S_minus_W"]==0 for r in fallback), "no losses due to fallback")
    require(close(mean(r["S_gap"] for r in reserve),new["families"]["RESERVE_TRANSFER"]["S"]["gap"]), "reserve family mean")
    require(panel["overlap"]==new["overlap"]==receipt["overlap"] and len(new["overlap"])==4, "both overlap audits")
    require(new["scored"]==sum(len(r["arms"]) for r in b)==receipt["originals_compared"]==receipt["native_markers"], "actual native scores")
    v1=load("v1",V1,"results.json.gz");classification=load("v1_attribution",V2,"manual-references.json")
    v2=load("v2",V2,"results.json.gz");v3a=load("v3a",V3A,"results.json.gz")
    v3b=load("v3b",V3B,"result.json")
    earlier = {
        "v1":{"source":"v1#/overall/pairs/MAIN","original_gate":v1["development_gate"],
              "relative_to_V_COST":v1["overall"]["pairs"]["MAIN"]["V_COST"]["metrics"]["L"],
              "attribution_source":"v1_attribution#/interpretation","attribution":classification["interpretation"]},
        "v2":{"source":"v2#/comparisons/MAIN/estimates/U","gate":v2["development_gate"],
              "U_minus_R":v2["comparisons"]["MAIN"]["estimates"]["U"]["R"],"U_minus_B_cost":v2["comparisons"]["MAIN"]["estimates"]["U"]["B_COST"]},
        "v3a":{"source":"v3a#/landscape/curves/{k}/pooled/recovered","decision":v3a["landscape"]["decision"],
               "k6":v3a["landscape"]["curves"]["6"]["pooled"]["recovered"],"k24":v3a["landscape"]["curves"]["24"]["pooled"]["recovered"]},
        "v3b":{"source":"v3b#/contrasts","gate":v3b["status"],"winner":v3b["control"],"n":v3b["scored"],"comparisons":v3b["contrasts"]},
    }
    times=[]
    for rev,label,file,jid in (("ab6a8ad5","stage0_account","sacct.psv","135468"),("f3027bd7","stage1_account","confirm-sacct.psv","135471")):
        raw=load(label,V3C,file)
        rows=[l.split("|") for l in raw.splitlines() if l.split("|")[0]==jid]
        require(len(rows)==1,"allocation not .batch")
        ct=datetime.fromisoformat(git("show","-s","--format=%cI",rev).decode().strip())
        st=datetime.fromisoformat(rows[0][9]).replace(tzinfo=ct.tzinfo)
        require(ct<st,"source precedes job")
        times.append({"git_commit":git("rev-parse",rev).decode().strip(),"committer_time":ct.isoformat(),"slurm_start":st.isoformat(),"job":jid,
                      "source":label+": allocation record column 10 (Start); Git committer timestamp %cI"})
    return {
        "schema":"t5-stop-loss-evidence-v1","frozen_revision":BASE,"sources":sources,"prior_stages":earlier,
        "development":{"source":"dev#/rows; dev#/means; dev#/primary","n":len(a),"row_comparison":signs(da),"means":old["means"],"ci":old["primary"],
            "gate0":old["gate0"],"gate1":old["gate1"],"ties_reference_source":"lock#/historic_reference_diagnostics","tie_orders":reg["historic_reference_diagnostics"]},
        "confirmation":{"source":"new#/conditions; new#/roles; new#/comparisons","n":len(b),"verdict":new["primary_verdict"],"W":reg["fit"]["winner"],
            "row_comparison":signs(db),"roles":new["roles"],"W_attained_keys":matched,"oracle_states":dict(Counter(r["lower"]["status"] for r in b)),
            "oracle_actual_chain_false":unchecked,"worse_rows":failures,"worse_by_cell":dict(Counter(r["cell"] for r in failures)),
            "reserve_rows":reserve,"reserve_mean_gap":mean(r["S_gap"] for r in reserve),"fallback_rows":fallback,
            "contrasts":all_co,"signed_and_L_mirrors":{r["key"]:r["passed"] for r in new["mirrors"]}},
        "audit":{"source":"new#/errors; new#/overlap; receipt#/combined","positions_planned":new["positions_planned"],"positions_scored":new["scored"],
            "errors":new["errors"],"retries":receipt["retries"],"overlap":new["overlap"],"panel_duplicates":new["internal_duplicates"],
            "new_panel_redraws":len(panel["rejected"]),"source_rosters":panel["old_counts"],"combined_original_compute":receipt["combined"],
            "readback_recovery":receipt["readback_recovery"],"source_before_its_job":times,
            "sealed_H2":{k:new[k] for k in ("H2_generated","H2_accessed","H2_derived")}},
    }


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check",action="store_true",help="compare with the saved closeout ledger; write nothing")
    args=parser.parse_args()
    data=build()
    payload=(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+"\n").encode("utf8")
    dest=OUT/"evidence.json"
    if args.check:require(dest.read_bytes()==payload,"closeout ledger differs from Git-backed readback")
    else:
        with dest.open("xb") as stream:stream.write(payload)
    print("Verified paired development and new panels, recorded intervals, four previous stages, and two release timestamps.")
