"""Read the saved events and native scores without calling any simulator or online policy."""
from collections import Counter
import gzip
import hashlib
import json
import math
from statistics import mean
import os

import numpy as np

from context_t4b import (
    ACT, EPS, PROTOCOL, SOURCES, TICKS, bundle_inventory, check_runtime, check_sources,
    digest, groups, load_case, read, read_inputs, require, sha, slurm_id, write, write_gz,
)
from aegis_action_cost.permit import Gate
from aegis_cost_baseline.rule import operative_view
from bounds import information
from schedule import batch_path, ledger, slurm_rows, state, terminal

METRICS = ("L", "U", "person", "tool", "fee")


def verified_return(folder, record, key, role, case, info, bundle, source_sha):
    marker = folder/"native-entry.json"
    score = folder/"score.json"
    metadata = None
    entry = read(marker) if marker.is_file() else None
    audit = dict(job=record["job"], group=record["group"], attempt=record["attempt"], key=key, role=role,
                 native_entry=entry is not None, score_sha256=None, raw_sha256=None, calls_accounted=0)
    raw = folder/"original.jsonl.gz"
    if raw.is_file():
        audit["raw_sha256"] = sha(raw)
        try:
            with gzip.open(raw, "rt", encoding="utf8") as stream:
                metadata = json.loads(next(stream))["metadata"]
            audit["calls_accounted"] = len(metadata["policy_public_decisions"])
        except (OSError, EOFError, ValueError, KeyError, StopIteration):
            metadata = None
    if not score.is_file():
        return None, dict(audit, status="ENTERED_NO_SCORE" if entry else "NO_FACILITY_ENTRY"), None
    audit["score_sha256"] = sha(score)
    try:
        s = read(score)
        require(entry is not None and s["entry"] == entry and entry["job"] == record["job"] and entry["role"] == role
                and entry["key"] == key and entry["group"] == record["group"] and entry["attempt"] == record["attempt"]
                and entry["input"] == info["sha256"] and entry["source"] == source_sha
                and entry["input_manifest"] == os.environ["T4B_CONDITION_SHA"], "score identity")
        require(metadata is not None and audit["raw_sha256"] == s["raw_sha256"], "original trace identity")
        native = case["native"]
        require(metadata["source_config"] == native["scenario"]
                and metadata["inputs"]["dispatch_program"] == native["dispatch_program"]
                and metadata["inputs"]["boundary_events"] == sorted(native["boundary_events"], key=lambda x: x["time_s"])
                and metadata["v3_received_maintenance"] == case["maintenance"]
                and metadata["t3_received_attachment_sha256"] == digest(case["attachment"]), "native arguments")
        decisions = metadata["policy_public_decisions"]
        proposals = metadata["v3_proposals"]
        require([q["view"]["time"] for q in decisions] == list(range(0, 3601, 60))
                and len(proposals) == 61 and all(digest(d["view"]) == p["view"] for d, p in zip(decisions, proposals, strict=True)),
                "public decision identity")
        require(all(abs(a-b) <= EPS for a,b in zip((s["L"],s["U"]), s["integral_balances"], strict=True)), "independent service integral")
        require(all(math.isfinite(s[k]) and s[k] >= 0 for k in METRICS), "valid saved metrics")
        if bundle:
            require(entry["bundle"] == bundle and entry["worker_pid"] != entry["pid"]
                    and digest([[p["at"],p["view"],p["proposal"]] for p in proposals]) == s["public_proposal"], "verified worker return")
        if role == "B_COST":
            messages = []
            for p,d in zip(proposals, decisions, strict=True):
                require(p["external_refusal"] is None, "cost baseline admission")
                reply = {k:v for k,v in d["decision"].items() if k != "certificates"}
                messages.append([p["at"],digest(operative_view(d["view"])),digest(reply)])
            require(digest(messages) == s["public_ipc"], "filtered worker input and reply")
        require(set(s["checkpoints"]) == set(TICKS), "each closure checkpoint")
    except (ValueError, KeyError, TypeError, OSError) as error:
        return None, dict(audit, status="INVALID_SAVED_RECORD", error=str(error)), None
    return s, dict(audit, status="SCORED", isolated_worker=entry["worker_pid"], bundle=bundle), metadata


def series_loss(score, left, right):
    return math.fsum(max(0, min(right, b)-max(left, a)) * max(0, d-y)/d
                     for a,b,d,y in score["curve"] if d > 0)


def event_time(score, task, outcomes=("APPLIED",)):
    return next((w["at"] for w in score["writes"] if w["task"] == task and w["outcome"] in outcomes), None)


def failure_counts(case, arms, v_meta):
    v = arms.get("V_COST")
    b = arms.get("B")
    no = arms.get("V_COST_NOPROBE")
    p = arms.get("P")
    dutch = case["evaluation"]["family"] == "NETHERLANDS"
    reported = dict(missed_preventive_window=None if dutch else "NOT_APPLICABLE", measurement_vs_action_need=None,
                    measurement_delayed_necessary_action=None, zero_P_in_measurement_case=None,
                    missed_preventive_evidence=None, binding_writes=[], delayed_writes=[])
    if v is not None:
        bought = {q["subject"]:q for q in v["paid"] if q["phase"] == "I" and q["fields"] is not None}
        actual_a = {task:t for t,task in v["requests"] if task.endswith("::A")}
        binding = [e for e in v["maintenance"] if e["lost_L_at_cap"] > EPS
                   and (q := bought.get(e["task"][:-3])) is not None and q["arrived"] <= actual_a[e["task"]]]
        reported["measurement_vs_action_need"] = bool(binding)
        reported["binding_writes"] = binding
        if p is not None:
            reported["zero_P_in_measurement_case"] = bool(binding) and p["L"] <= EPS
        if no is not None:
            a_no = {task:t for t,task in no["requests"] if task.endswith("::A")}
            delayed = []
            for task, issued in actual_a.items():
                initial = bought.get(task[:-3])
                direct_issue = a_no.get(task)
                if not initial or initial["arrived"] > issued or direct_issue is None or issued-direct_issue < 60:
                    continue
                late, early = event_time(v, task), event_time(no, task)
                if late is None or early is None or late <= early:
                    continue
                maintenance = v_meta["v3_maintenance_events"] if v_meta else []
                if not any(q["task"] == task and q["at"] == late and q["indicated"] for q in maintenance):
                    continue
                extra = series_loss(v, early, late)-series_loss(no, early, late)
                if extra > EPS:
                    delayed.append(dict(task=task, initial_arrival=initial["arrived"], issue_delay=issued-direct_issue,
                                        interval=[early,late], paired_extra_L=extra))
            reported["measurement_delayed_necessary_action"] = bool(delayed)
            reported["delayed_writes"] = delayed
    if dutch and v is not None and b is not None and v_meta is not None:
        a = case["attachment"]
        fault, restored = a["fault_at"], a["restore_at"]
        reported["missed_preventive_window"] = False
        if fault is not None:
            vwhen, bwhen = event_time(v, "NR::A"), event_time(b, "NR::A")
            pub = case["native"]["dispatch_program"]["public"]
            sub = next(x for x in pub["subjects"] if x["id"] == "NR")
            permit = Gate(case["maintenance"]["recovery"])
            legal = []
            for d in v_meta["policy_public_decisions"]:
                frame = d["view"]
                if frame["time"] >= fault:
                    break
                req, _ = permit.admit(pub, frame, sub, "A")
                if req and req["planned_end"] < fault:
                    legal.append(frame["time"])
            tripping = any(e["t"] == fault and e.get("tripped") is True for e in v["terminal_power_events"])
            b_tripping = any(e["t"] == fault and e.get("tripped") is True for e in b["terminal_power_events"])
            additional = series_loss(v, fault, restored) - series_loss(b, fault, restored)
            missed = bool(legal and bwhen is not None and bwhen < fault
                          and (vwhen is None or vwhen >= fault) and tripping and not b_tripping and additional > EPS)
            reported["missed_preventive_window"] = missed
            if missed:
                reported["missed_preventive_evidence"] = dict(legal_pre_fault_ticks=legal, transfer=[fault,restored], extra_L=additional,
                    B_NR_effect=bwhen, V_NR_effect=vwhen, V_later_pump=[w for w in v["writes"] if w["task"] == "NP::A"])
    return reported


def final_minimum(case, arms):
    oracle, p = arms.get("ORACLE"), arms.get("P")
    if oracle is None:
        return dict(status="UNRESOLVED", reason="missing valid oracle return", certified_min=None)
    proof = dict(oracle["oracle"])
    if proof.get("lower") is None and not proof.get("error") and not proof.get("plan") and p is not None:
        params = {row["id"]:row["value"] for row in case["native"]["scenario"]["parameters"]}
        events = case["native"]["boundary_events"]
        targets = ("network_service_capacity", "filter_resistance_multiplier")
        identity = case["evaluation"]["family"] == "RESERVE_TRANSFER" and all(params[k] == 1 for k in targets)
        identity &= not any(e["parameter_id"] in targets for e in events)
        identity &= not p["requests"] and not oracle["requests"] and p["curve"] == oracle["curve"]
        if identity:
            proof.update(status="ATTAINED", certified_min=p["L"], lower=p["L"],
                         proof="Identity-only reserve. Verified no-op parameter proof and separate matching P and oracle trajectories.")
    minimum = proof["certified_min"]
    if minimum is not None and any(s["L"] < minimum-EPS for s in arms.values()):
        proof.update(status="UNRESOLVED", certified_min=None, reason="a lawful observed arm contradicts the proposed independent lower bound")
    return proof


def endpoint_structure(case, arms, proof):
    if proof["certified_min"] is None or "P" not in arms:
        return None
    tau = proof.get("latest_best")
    public_info = information(case, arms["P"], tau)
    samples = arms["P"]["diagnostics"]
    for arrival, decision, subject, _, sample in public_info["all_paid"]:
        if not any(r["subject"] == subject and r["sampled"] == sample and r["would_arrive"] == arrival
                   and r["usable"] == decision and r["fields"] is not None for r in samples):
            return None
    p = arms["P"]["L"]
    return "".join(str(int(bit)) for bit in (p>EPS, p-proof["certified_min"]>EPS, public_info["c1"], public_info["c2"]))


def samples(rows, prefix, name, count):
    seed = int.from_bytes(hashlib.sha256((prefix+name).encode()).digest()[:16], "big")
    rng = np.random.Generator(np.random.PCG64(seed))
    by_family = []
    for fam in sorted({r["family"] for r in rows}):
        idx = np.array([i for i,r in enumerate(rows) if r["family"] == fam])
        by_family.append(idx[rng.integers(0, len(idx), size=(count,len(idx)))])
    return np.concatenate(by_family, axis=1)


def estimates(rows, role, cmp, cfg, name, shared_draws):
    pairs = [r for r in rows if role in r["arms"] and cmp in r["arms"]]
    missing = [r["key"] for r in rows if role not in r["arms"] or cmp not in r["arms"]]
    if not pairs:
        return dict(planned=len(rows), available=0, missing=missing, metrics=None, directions=None)
    draws = shared_draws if not missing else samples(pairs,cfg["seed_prefix"],name,cfg["repetitions"])
    metrics = {}
    for k in METRICS:
        dif = np.asarray([r["arms"][role][k]-r["arms"][cmp][k] for r in pairs])
        lo, hi = np.percentile(dif[draws].mean(axis=1), cfg["interval_percentiles"], method=cfg["quantile_interpolation"])
        metrics[k] = dict(mean=float(dif.mean()), lo=float(lo), hi=float(hi))
    d = [r["arms"][role]["L"]-r["arms"][cmp]["L"] for r in pairs]
    return dict(planned=len(rows), available=len(pairs), missing=missing, metrics=metrics,
                directions=[sum(x < -EPS for x in d), sum(abs(x)<=EPS for x in d), sum(x>EPS for x in d)])


def describe(rows, roles, hypotheses, cfg, name):
    by_role = {}
    for role in roles:
        scores = [r["arms"][role] for r in rows if role in r["arms"]]
        orders = sum(len(s["checkpoints"][TICKS[-1]]) for s in scores)
        closure = {label: dict(current=[sum(z==label for s in scores for z in s["checkpoints"][t].values()) for t in TICKS],
                               ever=sum(sum(label in states for states in s["first"].values()) for s in scores))
                   for label in ("NA","PV")}
        by_role[role] = dict(planned=len(rows), valid=len(scores), orders=orders, closure=closure,
                             averages={k:(mean(s[k] for s in scores) if scores else None) for k in METRICS})
    shared = samples(rows, cfg["seed_prefix"], name, cfg["repetitions"])
    effects = {m["id"]:estimates(rows,"V_COST",m["comparator"],cfg,name,shared) for m in hypotheses}
    no_min = [r["key"] for r in rows if r["minimum"]["certified_min"] is None]
    incomplete = [r["key"] for r in rows if not {"P","V_COST"}.issubset(r["arms"])]
    num = den = ratio = None
    if not no_min and not incomplete:
        num = math.fsum(r["arms"]["V_COST"]["L"]-r["minimum"]["certified_min"] for r in rows)
        den = math.fsum(r["arms"]["P"]["L"]-r["minimum"]["certified_min"] for r in rows)
        ratio = num/den if den > EPS else None
    return dict(n=len(rows), by_role=by_role, test_effects=effects,
                recoverable=dict(numerator=num, denominator=den, ratio=ratio, oracle_unresolved=no_min, missing=incomplete))


def main():
    _, plan = check_sources()
    check_runtime()
    info = read_inputs(plan)
    pinned_source = sha(SOURCES)
    roles = plan["panel"]["role_order"]
    roots = bundle_inventory(plan, check_bytes=True)
    cfg = plan["analysis"]["bootstrap"]
    require(np.__version__ == "2.2.6", "frozen PCG64 implementation")
    records = ledger()
    status = slurm_rows(records)
    current_job = slurm_id()
    require(all(terminal(status.get(q["job"])) for q in records if q["job"] != current_job), "all prior allocations have terminal records")
    audits, rows = [], []
    case_group = {k:g for g,keys in groups(plan).items() for k in keys}
    bygroup = {group:[q for q in records if q["group"] == group] for group in groups(plan)}
    for key in info["order"]:
        case = load_case(key, info)
        group = case_group[key]
        arms = {};vmeta = None
        for role in roles:
            attempts = bygroup[group]
            s = None
            if not attempts:
                audits.append(dict(key=key, role=role, group=group, status="UNSUBMITTED_SUFFIX", native_entry=False, calls_accounted=0))
            for record in attempts:
                folder = batch_path(record)/"positions"/key/role
                score, audit, meta = verified_return(folder, record, key, role, case, info["conditions"][key],
                                                    roots[role][0] if role in roots else None, pinned_source)
                require(s is None, "more than one executed result attempt")
                audits.append(audit)
                if score is not None:
                    s = score
                    arms[role] = score
                    if role == "V_COST":
                        vmeta = meta
        proof = final_minimum(case, arms)
        failures = failure_counts(case, arms, vmeta)
        layer = endpoint_structure(case, arms, proof)
        public_scores = {role:{k:v[k] for k in (*METRICS,"checkpoints","first","requests","writes","paid","maintenance")} for role,v in arms.items()}
        rows.append(dict(key=key, family=info["conditions"][key]["family"], duration=case["maintenance"]["exposure_s"],
                         layer=layer, minimum=proof, failures=failures, arms=public_scores))
    require(len(rows) == 144 and len({(a["key"],a["role"]) for a in audits}) == 1440, "original scientific denominators")
    env_groups = {"overall": rows}
    for field in ("family","duration","layer"):
        for value in sorted({r[field] for r in rows}, key=str):
            env_groups[field+"/"+str(value)] = [r for r in rows if r[field] == value]
    hypotheses = plan["analysis"]["hypotheses"]
    scopes = {name:describe(group, roles, hypotheses, cfg, name) for name,group in env_groups.items()}
    tests = []
    gate = True
    for h in hypotheses:
        value = scopes["overall"]["test_effects"][h["id"]]
        if not gate:
            decision = "DESCRIPTIVE_ONLY"
        elif value["available"] != 144:
            decision = "INDETERMINATE"
        else:
            decision = "MET" if value["metrics"]["L"]["hi"] < 0 else "NOT_MET"
        tests.append(dict(h, decision=decision, comparison=value))
        gate = gate and decision == "MET"
    types = ("missed_preventive_window","measurement_vs_action_need","measurement_delayed_necessary_action","zero_P_in_measurement_case")
    failure_results = {kind:dict(count=sum(r["failures"][kind] is True for r in rows),
           assessed=sum(type(r["failures"][kind]) is bool for r in rows),
           indeterminate=sum(r["failures"][kind] is None for r in rows),
           not_applicable=sum(r["failures"][kind] == "NOT_APPLICABLE" for r in rows),
           keys=[r["key"] for r in rows if r["failures"][kind] is True]) for kind in types}
    counts = Counter(a["status"] for a in audits)
    outcome = dict(schema="T4b-holdout-v2", job=current_job, hypotheses=tests, scopes=scopes, failure_counts=failure_results,
                   rows=rows, positions=audits, counts=counts, facility_starts=sum(a["native_entry"] for a in audits),
                   calls_reconstructed=sum(a["calls_accounted"] for a in audits), exact_condition_sha256=os.environ["T4B_CONDITION_SHA"])
    write_gz(ACT/"results.json.gz", outcome)
    write(ACT/"headline.json", {k:v for k,v in outcome.items() if k not in ("rows","positions")})
    print("hypotheses", [(q["id"],q["decision"],q["comparison"]["available"]) for q in tests], "positions", dict(counts), flush=True)


if __name__ == "__main__":
    main()
