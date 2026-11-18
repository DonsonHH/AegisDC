"""Build the frozen finite list by static interval arithmetic. No facility imports."""
import argparse
from copy import deepcopy
from fractions import Fraction
from itertools import product
import hashlib
import json
import os
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from london_confirmation_entry import FIELDS, EntryError, config_hash

GATES = ROOT / "docs/mainline/review-gated"
PACK = GATES / "R4/finite-extension-v1"
OLD = GATES / "R4/confirmation-entry-v1"
READS = ("READ_POS", "READ_VOLT", "READ_CONFIG")
ARMS = ["I", "D", "P"]


def load(path):
    return json.loads(path.read_bytes())


def encoded(value):
    if isinstance(value, Fraction):
        return int(value) if value.denominator == 1 else str(value)
    if isinstance(value, dict):
        return {k: encoded(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [encoded(v) for v in value]
    return value


def store(path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(encoded(value), handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def get_public_configs(baseline):
    """Resolve every canonical identity, including disclosed interface mutations."""
    found = {}
    def visit(node):
        if isinstance(node, dict):
            if set(node) == FIELDS:
                try:
                    found[config_hash(node)] = node
                except EntryError:
                    pass  # Original identity is retained as RAW_CONFIG_OUTSIDE_ENTRY_SHAPE.
                return
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)
    for source in baseline["sources"]:
        file = ROOT / source["path"]
        if hashlib.sha256(file.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError(f"Public source drift: {file}")
        doc = load(file)
        rows = doc.get("units", doc.get("cases", doc.get("conditions", [doc])))
        for row in rows:
            visit(row.get("input", row.get("common", row)))
        if file.name == "interface-fixtures.json":
            anchor = load(OLD / "inputs.json")["conditions"][0]["common"]
            for row in rows:
                if row["operation"] in ("normalize_equal", "invalid_config"):
                    visit(dict(anchor, **row["change"]))
    wanted = {r["sha256"] for r in baseline["config_identities"] if r["kind"] == "CANONICAL_H20_CONFIG"}
    if set(found) != wanted:
        raise ValueError("Public canonical identities could not all be resolved")
    return found


def available_start(config, time, reserve):
    start = max(time, config["window"][0])
    for left, right in config["calendar"]:
        if start < right and start + reserve > left:
            start = right
    return start


def read_recipe(config):
    """Nominal successive public release times; gates remain explicit underneath."""
    time = 0
    records = []
    outcomes = [config["cB"], config["vB"], config["family"]]
    for index, (action, value) in enumerate(zip(READS, outcomes)):
        work = config["read_work"]
        reserve = work + config["exit_work"]
        start = available_start(config, time, reserve)
        sample = start + work
        channel = ["zCB", "zVB", None][index]
        definite = config["read_modes"][action] == "DEFINITE" and channel not in config["signal_missing"]
        records.append(dict(action=action, request=time, start=start, sample=sample,
                            available=sample + config["publish"], expires=sample + config["ttl"],
                            reserve=reserve, reserved_until=start+reserve, prior_spent=index*work,
                            source=["pos-B","volt-B","cfg-local"][index],
                            target=["feeder-B","feeder-B","ctrl-1"][index], problem="q-1",
                            maintenance_epoch="m0", receiver="AUDITOR", config_epoch=0 if index==2 else None,
                            possible_evidence=value if definite else "NO_RESULT"))
        time = records[-1]["available"]
    return records


def repair(config, request, prior, direct):
    prep = config["prep"]
    commit_work = config["commit_work"]
    exit_work = config["exit_work"]
    verify_work = config["verify_work"]
    reserve_fix = prep + commit_work + exit_work
    approval = request + config["approval_work"]
    start = available_start(config, approval, reserve_fix)
    commit = start + prep + commit_work
    receipt = commit + config["publish"]
    exit_end = start + reserve_fix
    verify = available_start(config, max(exit_end, receipt), verify_work + exit_work)
    publish = verify + verify_work + config["publish"]
    end = verify + verify_work + exit_work
    window_min = max(publish + 1, end)
    roles = ["read","verify","propose"] + (["direct"] if direct else [])
    return dict(request=request, approval=approval, fix_start=start, commit=commit,
                execution_receipt=receipt, exit_end=exit_end, verify_start=verify,
                verify_sample=verify+verify_work, verify_arrival=publish,
                verify_reserve_end=end, min_window=window_min, prior_read_spent=prior,
                chain_reserve=reserve_fix+verify_work+exit_work, min_budget=prior+reserve_fix+verify_work+exit_work,
                roles=roles, roles_allow=all(config["permissions"][r]=="ALLOW" for r in roles),
                compatible=config["compatible"]=="ALLOW", grant_covers_commit=commit<Fraction(config["grant_expiry"]),
                budget_ok=prior+reserve_fix+verify_work+exit_work <= Fraction(config["budget"]),
                window_ok=publish < config["window"][1] and end <= config["window"][1])


def static_certificate(config):
    r = read_recipe(config)
    cutoff = min(config["window"][1], Fraction(config["tF"]) if config["tF"] is not None else config["H"])
    i_chain = repair(config, r[-1]["available"], 3*config["read_work"], False)
    d_chain = repair(config, 0, 0, True)
    values = [0, 1, "LEGACY_LINE"]
    prefix = True
    all_match = True
    for row, match in zip(r, values):
        row["prefix_reachable"] = prefix
        row["read_authorized"] = config["permissions"]["read"] == "ALLOW"
        row["budget_ok"] = row["prior_spent"] + row["reserve"] <= Fraction(config["budget"])
        row["window_ok"] = row["reserved_until"] <= config["window"][1]
        row["request_before_cutoff"] = row["request"] < cutoff
        row["public_opportunity"] = prefix and row["read_authorized"] and row["budget_ok"] and row["window_ok"] and row["request_before_cutoff"]
        row["lawful_arrival"] = row["public_opportunity"] and row["available"] < cutoff and row["available"] < row["expires"]
        row["valid_at_evidence_FIX_tick"] = row["lawful_arrival"] and row["available"] <= i_chain["request"] < min(cutoff,row["expires"])
        negative = row["possible_evidence"] not in ("NO_RESULT",match)
        prefix = row["lawful_arrival"] and not negative
        all_match &= row["possible_evidence"] == match and row["valid_at_evidence_FIX_tick"]
    for chain, permitted in [(i_chain,all_match),(d_chain,True)]:
        chain["publicly_feasible_at_request"] = all(chain[k] for k in ("roles_allow","compatible","budget_ok","window_ok"))
        chain["lawful_request_opportunity"] = bool(permitted and chain["request"] < cutoff and chain["publicly_feasible_at_request"])
        chain["normal_commit_before_cutoff"] = chain["commit"] < cutoff
        chain["normal_verify_before_cutoff"] = chain["verify_arrival"] < cutoff
        chain["normal_full_chain_statically_reachable"] = bool(chain["lawful_request_opportunity"] and chain["grant_covers_commit"] and chain["normal_verify_before_cutoff"])
    return dict(reads=r, I=i_chain, D=d_chain, cutoff=cutoff,
                public_permissions=config["permissions"], window=config["window"],
                resource_limit_each=config["budget"], external_calendar_evaluator_only=config["calendar"],
                preconditions_basis="Nominal public recipe; private plans and cutoff are evaluator-side checks, never policy inputs",
                observe_actual_stage_after_execution=True)


def mechanism(config, cert):
    """Conservative active distinctions only. No service scores enter selection."""
    visible=[]
    horizon=cert["cutoff"]
    for row in cert["reads"]:
        if row["public_opportunity"] and row["start"] < horizon:
            visible.append([row["action"],row["start"],min(row["sample"],horizon),
                            row["available"] if row["lawful_arrival"] else None,
                            row["possible_evidence"] if row["lawful_arrival"] else None])
    def reachable_chain(chain, direct):
        if not chain["lawful_request_opportunity"]:
            return []
        events=[["request",chain["request"]]]
        if chain["approval"]>=horizon:
            return events
        events.append(["approval",chain["approval"],config["approval"]])
        if config["approval"]!="APPROVE" or chain["fix_start"]>=horizon:
            return events
        events.append(["work",chain["fix_start"],config["work_mode"]])
        if chain["commit"]>=horizon or not chain["grant_covers_commit"]:
            return events
        events.append(["write",chain["commit"],config["guard"],config["commit"] if config["guard"]=="ALLOW" else None])
        if chain["exit_end"] <= config["H"]:
            events.append(["exit",chain["exit_end"],config["exit_result"]])
        if config["exit_result"]=="SUCCESS" and config["commit"]=="SUCCESS" and config["guard"]=="ALLOW" and chain["verify_arrival"]<horizon:
            events.append(["probe",chain["verify_sample"],chain["verify_arrival"],config["verification"]])
        return events
    # Empty versus positive intervals differ as challenges even if the loss agrees.
    fault = None if config["tF"] is None else [Fraction(config["tF"]),None if config["tR"] is None else Fraction(config["tR"])]
    available_backup=None
    if fault and (fault[1] is None or fault[1]>fault[0]) and not config["cB"]:
        available_backup=[config["ready"],config["permit"],config["connected"],config["exec_fault"]]
    return encoded(dict(public_read_opportunities=visible,direct_chain=reachable_chain(cert["D"],True),
                        evidence_chain=reachable_chain(cert["I"],False),external_interval=fault,
                        backup_parents_during_challenge=available_backup))


def make_group(key, ids, background):
    r=read_recipe(background)
    direct=repair(background,0,0,True)
    check=repair(background,r[-1]["available"],3*background["read_work"],False)
    rows=[deepcopy(background) for _ in ids]
    if key=="A_POS":
        for row in rows:row["cB"]=1
        rows[1]["work_mode"]="LOAD_ISOLATED"
    elif key=="A_CFG":
        rows[0]["family"]="REVISED_LOCAL"
    elif key=="A_CHAIN":
        rows[1]["work_mode"]=rows[2]["work_mode"]="LOAD_ISOLATED"
        rows[2]["exit_result"]="FAIL"
    elif key=="C":
        rows[0]["read_modes"]["READ_POS"]="INCONCLUSIVE"
    elif key=="D":
        rows[0]["permissions"]["direct"]="DENY"
    elif key=="E":
        for row,(field,value) in zip(rows,[("approval","DENY"),("commit","FAIL"),("guard","BLOCK"),("verification","FAIL"),("verification","INCONCLUSIVE")]):
            row[field]=value
    elif key=="F":
        for row,field in zip(rows,["ready","permit"]):
            row[field]=False
            row["tF"]=max(check["verify_arrival"],direct["verify_arrival"])+1
    elif key.startswith("G_"):
        t=(direct if key=="G_D" else check)["commit"]
        for row,offset in zip(rows,[-1,0,1]):row.update(tF=t+offset,tR=19)
    elif key.startswith("H_"):
        b={"H_READ":3*background["read_work"]+background["exit_work"],"H_D":direct["min_budget"],"H_I":check["min_budget"]}[key]
        for row,offset in zip(rows,[-1,0]):row["budget"]=b+offset
    elif key.startswith("J_"):
        w=(direct if key=="J_D" else check)["min_window"]
        for row,offset in zip(rows,[-1,0]):row["window"]=[0,w+offset]
    elif key=="K":
        rows[1].update(tF=check["commit"],tR=19)
    elif key=="L":
        for row in rows:row["tF"]=check["commit"]
        rows[0]["tR"]=check["commit"]
    else:
        raise ValueError(key)
    return rows


SUPPORT={
    "A_POS":("position disproves R at I decision; D normal complete path","E03, X01/X02, I11"),
    "A_CFG":("config disproves R after legal three-read prefix; D normal complete path","C03 development, I11, E01, A07"),
    "A_CHAIN":("both nominal chains; compare ONLINE / isolation / isolation exit failure","E01/E11/E12, X07/X08, S07/S08"),
    "C":("POS inconclusive, other two reads still legally available","E04, I08, X07"),
    "D":("only D lacks direct permission; I evidence path available","E08, C4/C7 H01-H06"),
    "E":("one failure plan, actual arrival at the assigned stage must be reported","E05/E06/E07, X03/X04, A03/A06"),
    "F":("revision reachable before fault; one physical backup parent absent","E16, C05, X05/X06"),
    "G_D":("D nominal commit with early/equal/late cutoff","T01-T03, E02/E14, X07"),
    "G_I":("I nominal commit with early/equal/late cutoff","T01-T03, E02/E14, X07"),
    "H_READ":("third necessary read reserve immediately below/at threshold","T10, E10, C4/C7 F01-F12"),
    "H_D":("direct chain immediately below/at public reserve","T10, E10, C4/C7 F01-F12"),
    "H_I":("evidence chain immediately below/at reserve after reads","T10, E10, C4/C7 F01-F12"),
    "J_D":("direct chain window one before/at minimum","C4/C7 F01-F12, E09/E15, X07"),
    "J_I":("evidence chain window one before/at minimum","C4/C7 F01-F12, E09/E15, X07"),
    "K":("legal queue and complete chain / I cutoff after queue","E09/E15, C4/C7, X07"),
    "L":("empty external interval with PRE close / no external restore","T09/S13, E02, X05/X06"),
}


def eligibility(group, slot, config, c):
    horizon=config["H"]
    if any(x is not None and not 0<=x<=horizon for x in (config["tF"],config["tR"])) or config["tR"] is not None and config["tR"]<config["tF"]:
        return False
    if not (0 < config["window"][1]<=horizon and 1<=config["budget"]<=20):
        return False
    full=lambda arm:c[arm]["normal_full_chain_statically_reachable"]
    reads=c["reads"]
    if group=="A_POS":
        return reads[0]["lawful_arrival"] and reads[0]["possible_evidence"]==1 and full("D")
    if group=="A_CFG":
        return all(r["lawful_arrival"] and r["valid_at_evidence_FIX_tick"] for r in reads) and reads[-1]["possible_evidence"]=="REVISED_LOCAL" and full("D")
    if group=="F":return full("I") and full("D") and config["tF"]+config["tauG"]<horizon
    if group in {"A_CHAIN","E"}:return full("I") and full("D")
    if group=="C":return all(r["lawful_arrival"] for r in reads) and full("D")
    if group=="D":return full("I") and not c["D"]["roles_allow"]
    if group=="K":
        queues=reads[0]["start"]>0 and c["D"]["fix_start"]>c["D"]["approval"]
        return queues and (full("D") and full("I") if slot=="K01" else c["I"]["lawful_request_opportunity"] and c["D"]["commit"]<config["tF"]==c["I"]["commit"])
    if group.startswith("G_"):
        arm=group[-1]
        return c[arm]["lawful_request_opportunity"] and c[arm]["grant_covers_commit"]
    if group=="H_READ":return all(r["lawful_arrival"] for r in reads[:2]) and reads[2]["budget_ok"]==(slot=="H02")
    if group in {"H_D","H_I","J_D","J_I"}:
        arm=group[-1]
        upper=slot in {"H04","H06","J02","J04"}
        prefix=arm=="D" or all(r["valid_at_evidence_FIX_tick"] for r in reads)
        return prefix and c[arm]["publicly_feasible_at_request"]==upper and (not upper or full(arm))
    if group=="L":return c["D"]["commit"]<config["tF"] and c["I"]["lawful_request_opportunity"]
    raise ValueError(group)


def build(output):
    rules=load(PACK/"selection.json")
    baseline_path=OLD/"public-dedup.json"
    if hashlib.sha256(baseline_path.read_bytes()).hexdigest()!=rules["public_baseline_sha256"]:
        raise ValueError("Public dedup baseline mismatch")
    baseline=load(baseline_path)
    configs=get_public_configs(baseline)
    signatures={key:mechanism(conf,static_certificate(conf)) for key,conf in configs.items()}
    origins={r["sha256"]:r["origins"][0]["source"] for r in baseline["config_identities"]}
    prior=dict(signatures);used={};selected={};audits={};attempts=[];gaps=[]
    c0=load(GATES/"R3/formal-protocol-v1/development-inputs.json")["conditions"][0]["common"]
    comparisons=0
    for group in rules["groups"]:
        name=group["group"];ids=group["slots"]
        for rank,((r,v),calendar) in enumerate(product(rules["recipes"],rules["calendars"]),start=1):
            if rank>rules["bounds"]["group_backgrounds"] or len(attempts)>=rules["bounds"]["total_backgrounds"]:
                raise ValueError("Selection operation ceiling")
            background=deepcopy(c0);background.update(rules["fixed_defaults"],read_work=r,verify_work=v,calendar=calendar)
            rows=make_group(name,ids,background);batch={};reasons=[]
            for slot,config in zip(ids,rows):
                comparisons+=1
                if comparisons>rules["bounds"]["total_materialized_slot_checks"]:raise ValueError("Slot operation ceiling")
                c=static_certificate(config);key=config_hash(config);sig=mechanism(config,c)
                if not eligibility(name,slot,config,c):reasons.append([slot,"static precondition"])
                if key in prior or key in used or key in {item[0] for item in batch.values()}:reasons.append([slot,"exact duplicate",key])
                if sig in prior.values() or sig in used.values() or sig in [item[1] for item in batch.values()]:reasons.append([slot,"active mechanism duplicate"])
                batch[slot]=(key,sig,c,config)
            attempts.append(dict(group=name,rank=rank,recipe=[r,v],calendar=calendar,rejections=reasons))
            if reasons:continue
            for slot,(key,sig,c,config) in batch.items():
                used[key]=sig;selected[slot]=dict(condition_id=slot,common=config,canonical_sha256=key)
                nearest=min(prior,key=lambda k:(sum(sig[f]!=prior[k][f] for f in sig),k))
                differences={f:dict(selected=sig[f],public=prior[nearest][f]) for f in sig if sig[f]!=prior[nearest][f]}
                obligation,refs=SUPPORT[name]
                audits[slot]=dict(slot=slot,group=name,members=ids,rank=rank,obligation=obligation,
                    varying_fields=group["paired_fields"],public_certificate=c,static_mechanism=sig,
                    nearest_disclosed=dict(config_sha256=nearest,origin=origins[nearest],active_differences=differences),
                    canonical_sha256=key,qualified_basis=refs,analytic_basis="Apply the recorded recipe and inequalities to this row. Physical, observation, control and score relationships use unchanged core; actual reached stages must be read from the later raw returns.",
                    applicability=dict(F1="complete compliant row",F2=slot in ("A01","A02"),F3="complete compliant row",F4="ONLINE and no actual physical intervention",F5="all actual applicable steps",direct_publicly_infeasible_at_start=not c["D"]["publicly_feasible_at_request"]),
                    explicit_limits="Static transfer for this recipe only; no execution or observed stage asserted.")
            break
        else:gaps.append(dict(group=name,slots=ids,reason="TEMPLATE_SEARCH_EXHAUSTED",impossibility_proven=False))
    order=sorted(slot for group in rules["groups"] for slot in group["slots"])
    store(output/"conditions.json",dict(purpose="FINITE_SYNTHETIC_EXTENSION",schema=1,order=order,
         conditions=[selected.get(slot,dict(condition_id=slot,common=None,reason="TEMPLATE_SEARCH_EXHAUSTED")) for slot in order]))
    store(output/"static-audit.json",dict(selection_sha256=hashlib.sha256((PACK/"selection.json").read_bytes()).hexdigest(),
          public_baseline_sha256=rules["public_baseline_sha256"],public_units=baseline["counts"]["public_units"],
          old_canonical_count=len(prior),new_fixture_configs="X01/X08 only, included in public baseline",
          candidate_backgrounds_examined=len(attempts),slot_examinations=comparisons,attempts=attempts,
          rows=[audits.get(s,dict(slot=s,status="UNRESOLVED")) for s in order],gaps=gaps,
          ready_for_static_review=len(selected)==len(order),model_calls=0,policy_calls=0,scorer_calls=0))
    return dict(selected=len(selected),slots=len(order),gaps=gaps,backgrounds=len(attempts),slot_checks=comparisons)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("output",type=Path)
    output=parser.parse_args().output
    if not os.environ.get("SLURM_JOB_ID") or socket.gethostname().split(".")[0]=="mu01":raise SystemExit("Slurm compute allocation required")
    output.mkdir(parents=True,exist_ok=False)
    print(json.dumps(build(output)))
