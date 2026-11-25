"""Reconcile a written registration and its analytic planning grid. No facility imports."""

import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, stdev
import subprocess
import sys

import numpy as np
from scipy.stats import nct, t


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REL = HERE.relative_to(ROOT).as_posix()
PRIOR = "41709979b277812c1b7af8af5d7d3128293cb790"
STAGE1 = "docs/mainline/t7-incident-counterfactual/stage1/"
BASE = "3487276af9e9759357771d16eb45feceaa3c948a"
METHOD = "docs/mainline/t4c-action-cost-v3/"
REFERENCE_PATHS = {STAGE1 + x for x in ("comparison.json", "pilot-accounting.psv", "batch-accounting.psv")}
REFERENCE_PATHS.update({
    METHOD + "v-double-star-freeze.json", METHOD + "inputs_v3.py", "src/aegis_action_cost/rules.json",
    "docs/mainline/t3-prior-information-v2/generator_v2.py", "docs/mainline/t3-prior-information-v2/score_saved.py",
    "docs/mainline/t3-prior-information-v2/settings.json",
})
MEMBERS = ("README.md", "registration.json", "panel-law.json", "design.json",
           "round-ledger.schema.json", "seed-registration.json", "power.json", "planning.py")


def require(ok, label):
    if not ok:
        raise ValueError(label)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def unique(pairs):
    result = {}
    for name, value in pairs:
        require(name not in result, "duplicate JSON member: " + name)
        result[name] = value
    return result


def reject_constant(value):
    raise ValueError("nonfinite JSON number: " + value)


def load(raw):
    return json.loads(raw, object_pairs_hook=unique, parse_constant=reject_constant)


def data(name):
    return load((HERE / name).read_bytes())


def pinned(rev, path, expected):
    require(path in REFERENCE_PATHS and rev in (PRIOR, BASE), "outside the public planning source allowlist")
    raw = git("cat-file", "blob", rev + ":" + path)
    require(sha(raw) == expected, "published source digest: " + path)
    return raw


def duration_in_seconds(text):
    return sum(Fraction(v) * 60**i for i, v in enumerate(reversed(text.split(":"))))


def old_development(spec):
    require(spec["source_revision"] == PRIOR, "planning baseline")
    rows = load(pinned(PRIOR, spec["public_development_source"], spec["public_development_source_sha256"]))["rows"]
    dutch = [r["arms"] for r in rows if r["family"] == "NETHERLANDS"]
    require(len(rows) == 24 and len(dutch) == 12, "original development denominators")
    loss = lambda arm, key: Fraction(str(arm[key]["L"]))
    old_gain = [loss(v, "P") - loss(v, "V_COST") for v in dutch]
    opportunity = [max(Fraction(0), loss(v, "V_COST")-loss(v, "PERIODIC")) for v in dutch]
    opportunities = [v for v,x in zip(dutch,opportunity) if x>0]
    oracle = [loss(v, "V_COST")-loss(v, "ORACLE") for v in dutch]
    cpu = Fraction(0)
    for prefix in ("pilot", "batch"):
        raw = pinned(PRIOR, spec[prefix+"_cpu_source"], spec[prefix+"_cpu_sha256"])
        parts = [line.split("|") for line in raw.decode("ascii").splitlines()]
        records = [dict(zip(parts[0], r, strict=True)) for r in parts[1:]]
        allocation = [r for r in records if "." not in r["JobID"]]
        require(len(allocation) == 1 and allocation[0]["State"] == "COMPLETED", "historical allocation")
        cpu += duration_in_seconds(allocation[0]["TotalCPU"])
    return {
        "historical_dutch_rows": len(dutch), "V_mean_L_s": float(mean(loss(v,"V_COST") for v in dutch)),
        "P_mean_L_s": float(mean(loss(v,"P") for v in dutch)), "mean_P_minus_V_s": float(mean(old_gain)),
        "mean_positive_part_V_minus_periodic_s": float(mean(opportunity)), "positive_rows": sum(o>0 for o in opportunity),
        "mean_person_in_positive_rows": {role:float(mean(Fraction(str(v[role]["person"])) for v in opportunities))
                                        for role in ("V_COST","PERIODIC","ORACLE")},
        "positive_part_row_sd_s": round(stdev(opportunity), 8), "mean_V_minus_legal_oracle_s": float(mean(oracle)),
        "mean_V_minus_periodic_s": float(mean(loss(v,"V_COST")-loss(v,"PERIODIC") for v in dutch)),
        "reference_V_positions": len(rows), "reference_TotalCPU_s": float(cpu),
        "reference_CPU_s_per_V_position": float(cpu/len(rows)),
    }


def round8(x):
    return round(float(x), 8)


def first_ge(g, values, threshold):
    matches = g[values >= threshold]
    return int(matches[0]) if len(matches) else None


def development_grid(r, historical):
    plan, endpoint = r["planning"], r["estimands"]
    block = r["randomization"]["conditions_per_block"]
    g = np.arange(plan["blocks_grid_min"], plan["blocks_grid_max"]+1)
    df = g - 1
    critical = t.isf(1-endpoint["q1"]["level"], df)
    multiplier = plan["effect_fraction"]
    proxy = historical["mean_P_minus_V_s"]*multiplier
    small = historical["mean_positive_part_V_minus_periodic_s"]
    chosen = small*multiplier
    # Each tuple fixes the Dutch reduction, SD factor, and a true extra staff cost in EACH family.
    settings = [
        ("requested_prior_times_0.75", proxy, 1., 0.), ("opportunity_times_1.00", small, 1., 0.),
        ("design_opportunity_times_0.75", chosen, 1., 0.), ("opportunity_times_0.50", small*.5, 1., 0.),
        ("half_design_effect", chosen*.5, 1., 0.), ("all_block_sds_doubled", chosen, 2., 0.),
        ("half_person_margin_consumed", chosen, 1., endpoint["q3"]["margin_person_s"]/2),
        ("whole_person_margin_consumed", chosen, 1., endpoint["q3"]["margin_person_s"]),
    ]
    bounds = {}
    marginal = {}
    base_sd = plan["block_sd"]
    for name, gain, noise, staff_shift in settings:
        z = np.array([
            (gain+endpoint["q1"]["margin_s"])/base_sd["dutch_L"],
            (endpoint["q2"]["margin_s"]-plan["true_noninferiority_gaps"]["london_L"])/base_sd["london_L"],
            (endpoint["q3"]["margin_person_s"]-plan["true_noninferiority_gaps"]["each_family_person"]-staff_shift)/base_sd["each_family_person"],
        ]) / noise
        powers = nct.sf(critical, df, z[:, None]*np.sqrt(g))
        require(np.all(np.isfinite(powers)), "unknown marginal planning power")
        # Q3 contains two separately assessed personnel conditions; no independence assumption here.
        raw_joint = 1 - ((1-powers[0]) + (1-powers[1]) + 2*(1-powers[2]))
        bounds[name] = np.maximum(0, raw_joint-plan["planning_whole_panel_failure_allowance"])
        marginal[name] = powers, raw_joint
    thresh = plan["required_joint_lower_bound"]
    joint = np.minimum(bounds["requested_prior_times_0.75"], bounds["design_opportunity_times_0.75"])
    selected = first_ge(g, joint, thresh)
    require(selected is not None, "planned joint target not attained")
    idx = int(np.nonzero(g == selected)[0][0])
    powers, raw_joint = marginal["design_opportunity_times_0.75"]
    return {
        "requested_proxy_gain_s": proxy, "selected_planning_gain_s": chosen,
        "scenario_inputs": [{"id":name,"gain_s":gain,"block_sd_multiplier":noise,
                              "extra_true_person_s_per_family":shift} for name,gain,noise,shift in settings],
        "grid_columns": ["g","n_per_family","df"] + list(bounds),
        "joint_grid": [[int(k),int(k)*block,int(k)-1] + [round8(curve[i]) for curve in bounds.values()]
                       for i,k in enumerate(g)],
        "first_qualifying_blocks": {key:first_ge(g,vals,thresh) for key,vals in bounds.items()},
        "selected_blocks_per_family": selected, "selected_conditions_per_family": selected*block,
        "selected_marginals_Q1_Q2_staff_London_staff_Netherlands": [round8(powers[j,idx]) for j in (0,1,2,2)],
        "selected_joint_before_hard_risk": round8(max(0,raw_joint[idx])),
        "selected_joint_lower_bound": round8(joint[idx]),
        "meaning": "All curves are planning-model lower bounds. A zero lower bound carries no positive joint guarantee. Selection uses values before rounding.",
    }


def prospective_h2(r):
    q = r["h2"]
    g = np.arange(2, q["max_planning_blocks_per_family"]+1)
    crit = t.isf(0.05/2, g-1)
    floor = q["block_sd_floor_s"]
    sec = nct.sf(crit,g-1,q["planned_effect_cap_s"]*np.sqrt(g)/floor)
    out = []
    for gain in (5., 7.5, 10., 15.):
        primary=nct.sf(crit,g-1,gain*np.sqrt(g)/floor)
        joint=np.maximum(0,primary+sec-1-r["planning"]["planning_whole_panel_failure_allowance"])
        out.append({"hypothetical_primary_gain_s":gain,"secondary_gain_s":q["planned_effect_cap_s"],
                    "block_sd_both_s":floor,"first_blocks":first_ge(g,joint,r["planning"]["required_joint_lower_bound"]),
                    "bound_at_max_blocks":round8(joint[-1])})
    return out


def workload(r, unit_cpu):
    b, p = r["budget"], r["randomization"]
    per_arm = b["rounds"] * b["proposals_per_round_per_improver"] * p["fit_conditions_total"]
    overhead = b["rounds"]*b["optimizer_cpu_cap_s_per_round_per_arm"]
    fit = 2*per_arm + p["fit_conditions_total"]
    dev = p["dev_conditions_total"] * len(r["arms"]["dev_order"])
    cap = b["native_cpu_cap_s_per_position"]
    low, high = b["cpu_estimate_factors"]
    quantities = {
        "FIT_shared_parent": (p["fit_conditions_total"],0),
        "FIT_O": (per_arm,overhead), "FIT_R": (per_arm,overhead),
        "FIT_total_including_author": (fit,2*overhead+b["input_author_cpu_cap_s_per_split"]),
        "DEV_all_seven_including_author_and_final_check": (dev,b["input_author_cpu_cap_s_per_split"]+b["terminal_account_replay_cpu_cap_s"]),
        "entire_stage_if_authorized": (fit+dev,2*overhead+2*b["input_author_cpu_cap_s_per_split"]+b["terminal_account_replay_cpu_cap_s"]),
    }
    return {name:{"native_positions":num,"at_reference_unit_cpu_s":round(num*unit_cpu,3),
                  "estimated_cpu_s_interval":[math.floor(num*unit_cpu*low),math.ceil(num*unit_cpu*high+fixed)],
                  "cpu_cap_s":num*cap+fixed} for name,(num,fixed) in quantities.items()}


def make(r):
    historical = old_development(r["planning"])
    return {"schema":"AegisDC.T8.r0.power-ledger.v1","inputs":historical,
            "DEV":development_grid(r,historical),"resources":workload(r,historical["reference_CPU_s_per_V_position"]),
            "H2_precision_examples_no_seed_or_observations":prospective_h2(r)}


def json_bytes(obj):
    return (json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+"\n").encode()


def payload_digest(registration):
    unsigned = dict(registration)
    unsigned["integrity"] = {k:v for k,v in registration["integrity"].items() if k != "payload_sha256"}
    return sha(json.dumps(unsigned,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode())


def verify_schema(schema):
    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                ptr = node["$ref"]
                require(ptr.startswith("#/"), "external schema reference")
                target = schema
                for part in ptr[2:].split("/"):
                    target = target[part.replace("~1","/").replace("~0","~")]
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)
    walk(schema)
    require({"arm","round","before","slots","feedback","selection","rewrite","after","next_witness","accounting","audit"}
            <= set(schema["required"]), "round evidence schema")


def check(r, out, checkout):
    p,b,e=r["randomization"],r["budget"],r["estimands"]
    require(json_bytes(out)==(HERE/"power.json").read_bytes(), "published grid differs")
    require(out["DEV"]["selected_blocks_per_family"]==p["dev_blocks_per_family"]==38 and
            out["DEV"]["selected_conditions_per_family"]==p["dev_conditions_per_family"]==456, "DEV sizing")
    for split in ("fit","dev"):
        require(p[split+"_conditions_per_family"]==12*p[split+"_blocks_per_family"] and
                p[split+"_conditions_total"]==2*p[split+"_conditions_per_family"], "split sizes")
    require((e["q1"]["family"],e["q1"]["pair"],e["q1"]["metric"],e["q1"]["margin_s"],e["q1"]["comparison"]) ==
            ("NETHERLANDS",["R","V_COST"],"L",0,"<"), "Dutch developer gate")
    require((e["q2"]["family"],e["q2"]["pair"],e["q2"]["metric"],e["q2"]["margin_s"],e["q2"]["comparison"]) ==
            ("LONDON",["R","V_COST"],"L",5,"<="), "London noninferiority gate")
    require(e["q3"]["families_separately"]==["LONDON","NETHERLANDS"] and e["q3"]["pair"]==["R","V_COST"] and
            e["q3"]["margin_person_s"]==5 and e["q3"]["max_hard_violations"]==0 and e["q3"]["comparison"]=="<="
            and e["q4"]["pair"]==["R","O"] and e["q4"]["use"]=="DESCRIPTIVE_ONLY", "resource gates and descriptive Q4")
    require(all(e[k]["level"]==0.95 and e[k]["sided"]=="upper" for k in ("q1","q2","q3","q4")), "sidedness")
    require(r["h2"]["primary"]=="R−O Dutch mean L" and r["h2"]["key_secondary"]=="R−V_COST Dutch mean L" and
            r["h2"]["status"]=="WITHHELD_NO_AUTHORIZATION", "attribution and H2 closure")
    cost=out["resources"]
    require(b["rounds"]*b["proposals_per_round_per_improver"]==b["proposals_per_improver"] and
            b["fit_rows_per_proposal"]==b["shared_fit_parent_positions"]==p["fit_conditions_total"] and
            b["dev_arms"]==len(r["arms"]["dev_order"])==7 and cost["FIT_R"]==cost["FIT_O"], "matched search budgets")
    require(cost["FIT_O"]["native_positions"]==b["fit_evaluations_per_improver"] and
            cost["FIT_O"]["cpu_cap_s"]==b["cpu_cap_s_per_improver"] and
            cost["FIT_total_including_author"]["native_positions"]==b["total_fit_positions"] and
            cost["DEV_all_seven_including_author_and_final_check"]["native_positions"]==b["total_dev_positions"] and
            cost["entire_stage_if_authorized"]["native_positions"]==b["total_native_positions"] and
            cost["entire_stage_if_authorized"]["cpu_cap_s"]==b["study_cpu_cap_s"], "workload denominators")
    plan=r["baseline"]
    for path_field, hash_field in (("method_freeze","method_freeze_sha256"),("generator_path","generator_sha256"),
                                  ("incident_generator_path","incident_generator_sha256"),("scorer_path","scorer_sha256")):
        raw=pinned(BASE,plan[path_field],plan[hash_field])
        if path_field=="method_freeze":
            require(load(raw)["public_bundle_sha256"]==plan["parent_bundle_sha256"],"original V_COST")
    seed=data(p["seeds"])
    root=bytes.fromhex(seed["fresh_public_development_root_hex"])
    require(len(root)==32 and sha(root)==seed["root_sha256"] and
            sha(b"AegisDC/T8/r0/FIT/v1\0"+root)==seed["fit_seed_hex"],"public FIT identity")
    beacon=seed["dev"]
    require(beacon["scheme"]=="bls-unchained-g1-rfc9380" and len(bytes.fromhex(beacon["public_key_hex"]))==96 and
            (beacon["period_s"],beacon["genesis_unix_utc_s"],beacon["publication_lead_s"])==(3,1692803367,120)
            and beacon["chain_hash"]=="52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971",
            "fixed future DEV entropy rule")
    law=data(p["panel_law"])
    ranges=law["operative_variations"]
    count=math.prod((hi-lo+1)**2 for lo,hi in (ranges["start_ticks_inclusive"],ranges["end_ticks_inclusive"]))
    require(count==ranges["catalogue_size_per_family"] and count>11*(p["dev_blocks_per_family"]+p["fit_blocks_per_family"]),
            "schedule-profile capacity before any identity audit")
    seeds=r["at_freeze"]
    require(seeds["new_public_development_root_draws"]==1 and all(type(v) is int and v==0
            for k,v in seeds.items() if k!="new_public_development_root_draws"), "zero execution boundary")
    design = data(r["arms"]["initial_programs"])
    require(design["arms"]["parent"]["public_bundle_sha256"]==plan["parent_bundle_sha256"] and
            4**len(design["policy_language"]["cells"])==design["policy_language"]["catalogue_size"],"registered finite design")
    require([a["id"] for a in design["arms"]["descriptive"]]==r["arms"]["descriptive"] and
            r["arms"]["dev_order"]==["V_COST","O","R","P","ALARM","B","PERIODIC"], "frozen seven DEV arms")
    paths={name for item in law["historical_catalogue"]["entries"] for name in item["paths"]}
    families=("t3-prior-information-v2","t4b-holdout-confirmation-v2","t4c-action-cost-v3",
              "t5-ordinary-improvement-development-v1","t5-ordinary-improvement-development-v2",
              "t5-landscape-diagnostic-v3a","t5-block-recombination-v3b","t5-observable-selector-v3c",
              "t7-incident-counterfactual/stage1")
    require(all(any(path.startswith("docs/mainline/"+name+"/") for path in paths) for name in families), "historic coverage declarations")
    h3_index=[item for item in law["historical_catalogue"]["entries"] if "allowed_input" in item]
    require(len(h3_index)==1 and h3_index[0]["counts"]==[120] and h3_index[0]["revision"]=="0a74506cd10cf7d45d038a0bd027619d62852ede"
            and h3_index[0]["paths"]==["docs/mainline/t7-incident-counterfactual/stage2/pre-score/input-manifest.json"],
            "sealed index pointer only")
    access=design["access_control"]
    require(set(access["dispatch_worker_allow"]["frame"])=={"time","records","work","paid","writes","fixed","issued"}
            and set(access["other_principals"])=={"new_panel_curator","fit_evaluator","dev_evaluator","overlap_custodian","auditor"},
            "registered public frame and separate role declarations")
    require(len(design["overlap_gate"]["two_axes"])==3 and {"full","operative","compatibility"} <=
            set(design["overlap_gate"]["identities"]), "input-only comparison specification")
    verify_schema(data(r["arms"]["round_ledger_schema"]))
    require(r["integrity"]["payload_sha256"]==payload_digest(r),"embedded registration payload digest")
    companions=r["integrity"]["bound_spec_sha256"]
    require(set(companions)=={"design.json","round-ledger.schema.json","seed-registration.json","panel-law.json",
                               "planning.py","power.json"}, "normative attachment set")
    for name,digest in companions.items():
        require(sha((HERE/name).read_bytes())==digest, "registration-bound component: "+name)
    seal=data("delivery.json")
    require(set(seal["files_sha256"])==set(MEMBERS),"delivery set")
    for name,h in seal["files_sha256"].items():
        require(sha((HERE/name).read_bytes())==h, "registered artifact: "+name)
    require(seal["registration_sha256"]==sha((HERE/"registration.json").read_bytes()),"registration hash")
    text=(HERE/"README.md").read_text("utf-8").replace("**","")
    grid={row[0]:row for row in out["DEV"]["joint_grid"]}
    for k in (30,37,38):
        row=grid[k]
        line=f"| {k} | {row[1]} | {row[3]:.4f} | {row[5]:.4f} | {row[7]:.4f} |"
        require(line in text,"summary power row: "+str(k))
    for key in ("FIT_total_including_author","DEV_all_seven_including_author_and_final_check","entire_stage_if_authorized"):
        cost=out["resources"][key]
        lo,hi=cost["estimated_cpu_s_interval"]
        line=f"| {cost['native_positions']:,} | {lo:,}–{hi:,} | {cost['cpu_cap_s']:,} |"
        require(line in text,"summary budget: "+key)
    print("PASS original parent / generator / scorer pins; new public FIT identity and prospective DEV derivation")
    print("PASS development-only inputs; paired power grid [2..144]; 38 blocks, 456 conditions/family; joint bound %.8f"
          % out["DEV"]["selected_joint_lower_bound"])
    print("PASS O/R: 16 proposals, 768 FIT evaluations and 138480 CPU seconds each; 7968 total planned native positions")
    print("PASS written round schema, role allowlist, historical catalogue, overlap rules and Q1-Q4 / H2 hierarchy; live isolation untested")
    print("PASS registration-only: no panel generation, overlap queries, optimizer/plant/Slurm calls or H2/H3 seed access")
    if checkout:
        digest=sha((HERE/"delivery.json").read_bytes());reg_sha=seal["registration_sha256"]
        anchor=git("log","-1","--format=%H","HEAD","--",REL+"/delivery.json").decode().strip()
        require(anchor,"r0 not committed")
        expected={REL+"/"+f for f in (*MEMBERS,"delivery.json")}
        for rev in (anchor,"HEAD"):
            names=git("ls-tree","-r","--name-only",rev,"--",REL).decode().splitlines()
            require(set(names)==expected,"release tree inventory")
            for name in sorted(expected):
                require((ROOT/name).read_bytes()==git("cat-file","blob",rev+":"+name),"checkout bytes: "+name)
        trailers=git("show","-s","--format=%B",anchor).decode().splitlines()
        require("Registration-SHA256: "+reg_sha in trailers and "Delivery-SHA256: "+digest in trailers,"release trailers")
        print(f"PASS checkout bytes for {len(expected)} files and both release trailers")
    print("Registration-SHA256:",seal["registration_sha256"])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    modes=p.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check",action="store_true")
    modes.add_argument("--power",action="store_true",help="emit the design grid, no condition draws")
    p.add_argument("--checkout-bytes",action="store_true")
    args=p.parse_args()
    require(not args.checkout_bytes or args.check,"--checkout-bytes requires --check")
    r=data("registration.json");out=make(r)
    if args.power:
        sys.stdout.buffer.write(json_bytes(out))
    else:
        check(r,out,args.checkout_bytes)


if __name__=="__main__":
    main()
