"""Registered T7 calculations over saved L/person values and the pre-score mask."""

from fractions import Fraction
from itertools import product
from math import isfinite, sqrt
from statistics import mean, pvariance, variance

from scipy.stats import t

from study import FAMILIES, KEYS, ROLES

TESTS = (("HA", "P", False), ("HB", "ALARM", False), ("HC", "P", True))


def available(arms, role):
    x = arms.get(role)
    return x is not None and x["status"] == "SCORED" and isfinite(x["L"]) and x["L"] >= 0


def difference(arms, control, event):
    a, b = (Fraction(str(arms[k]["L"])) for k in ("V_COST", control))
    return Fraction(int(a > 0) - int(b > 0)) if event else a - b


def analyze_endpoint(items, scores, keys, control, event, *, sensitivity):
    groups = {f: {b: [] for b in range(5)} for f in FAMILIES}
    missing = []
    for key in keys:
        arms = scores.get(key, {})
        if not (available(arms, control) and available(arms, "V_COST")):
            missing.append(key)
            continue
        row = items[key]
        groups[row["family"]][row["block"]].append(difference(arms, control, event))
    result = {"planned": len(keys), "valid": len(keys) - len(missing), "missing_pairs": missing,
              "estimate": None, "interval_95": None, "raw_p": None, "df": None, "se": None,
              "status": "INDETERMINATE", "family_estimates": {}}
    if missing:
        result["reason"] = "missing or invalid registered pairs"
        return result
    nonempty = {f: [g for g in groups[f].values() if g] for f in FAMILIES}
    if any(not g for g in nonempty.values()):
        result["reason"] = "no retained row in a family"
        return result
    centers = {f: mean(v for group in nonempty[f] for v in group) for f in FAMILIES}
    delta = mean(centers.values())
    result.update(estimate=float(delta), family_estimates={f: float(v) for f,v in centers.items()})
    df = min(len(g) for g in nonempty.values()) - 1
    if df < 1:
        result["reason"] = "fewer than two nonempty blocks in a family"
        return result
    result["df"] = df
    stratum_variances = []
    for f in FAMILIES:
        blocks = nonempty[f]
        k = len(blocks)
        if sensitivity:
            sums, sizes = [sum(g) for g in blocks], [len(g) for g in blocks]
            draws = (sum(sums[i] for i in seq) / sum(sizes[i] for i in seq)
                     for seq in product(range(k), repeat=k))
            corrected = pvariance(draws) * k / (k - 1)
        else:
            if k != 5 or any(len(g) != 12 for g in blocks):
                raise ValueError("primary analysis requires all original blocks")
            corrected = variance([mean(g) for g in blocks]) / k
        stratum_variances.append(corrected)
    se = sqrt(float(sum(stratum_variances) / 4))
    result["se"] = se
    if se == 0:
        result["reason"] = "both within-family block variances are zero"
        return result
    d = float(delta)
    half = float(t.ppf(0.975, df)) * se
    result["interval_95"] = [d - half, d + half]
    result["status"] = "ESTIMATED"
    if not sensitivity:
        result["raw_p"] = float(2 * t.sf(abs(d / se), df))
    return result


def all_results(manifest, overlap, scores):
    items = manifest["conditions"]
    if manifest["order"] != KEYS or overlap["order"] != KEYS or not overlap["references_complete"]:
        raise ValueError("unverified pre-score inclusion ledger")
    main = {name: analyze_endpoint(items, scores, KEYS, comp, event, sensitivity=False)
            for name, comp, event in TESTS}
    raw = {n: r["raw_p"] if r["raw_p"] is not None else 1.0 for n, r in main.items()}
    ordered = sorted(main, key=lambda n: (raw[n], list(main).index(n)))
    running = 0.0
    for i, name in enumerate(ordered):
        running = min(1., max(running, (3-i) * raw[name]))
        row = main[name]
        row.update(holm_p=running, p_used_for_holm=raw[name], holm_rank=i+1)
        if row["status"] == "ESTIMATED":
            row["status"] = "MET" if running <= 0.05 and row["estimate"] < 0 and row["interval_95"][1] < 0 else "NOT_MET"
    retained = [k for k in KEYS if not overlap["by_condition"][k]["exclude_descriptively"]]
    extra = {"status": "无需敏感性", "excluded": len(KEYS)-len(retained), "retained": len(retained)}
    if len(retained) != len(KEYS):
        extra.update(status="DESCRIPTIVE_ONLY", endpoints={
            n: analyze_endpoint(items, scores, retained, comp, event, sensitivity=True) for n,comp,event in TESTS})
    families, blocks, worse, comparisons = {}, [], [], {}
    for fam in FAMILIES:
        keys = [k for k in KEYS if items[k]["family"] == fam]
        cells = {"P0_V0": [], "P1_V0": [], "P0_V1": [], "P1_V1": [], "missing": []}
        means = {}
        for role in ROLES:
            valid = [scores[k][role] for k in keys if available(scores.get(k,{}), role)]
            means[role] = {"planned": len(keys), "scored": len(valid),
                           "mean_L": mean(s["L"] for s in valid) if valid else None,
                           "mean_person": mean(s["person"] for s in valid) if valid else None,
                           "events": sum(s["L"] > 0 for s in valid),
                           "event_rate": mean(int(s["L"] > 0) for s in valid) if valid else None}
        for k in keys:
            a = scores.get(k,{})
            if available(a, "V_COST") and available(a, "P"):
                cells[f"P{int(a['P']['L'] > 0)}_V{int(a['V_COST']['L'] > 0)}"].append(k)
            else:
                cells["missing"].append(k)
            if available(a, "PERIODIC") and available(a, "V_COST") and a["V_COST"]["L"] > a["PERIODIC"]["L"]:
                worse.append({"key": k, "family": fam, "V_L": a["V_COST"]["L"], "PERIODIC_L": a["PERIODIC"]["L"],
                              "V_person": a["V_COST"]["person"], "PERIODIC_person": a["PERIODIC"]["person"]})
        families[fam] = {"arms": means, "event_pairs": cells}
        comparisons[fam] = {}
        for other in ("P","ALARM","PERIODIC","B"):
            subset = [scores[k] for k in keys if available(scores.get(k,{}),other) and available(scores.get(k,{}),"V_COST")]
            result = {"planned": len(keys), "valid": len(subset)}
            for metric in ("L","person"):
                d = [a["V_COST"][metric] - a[other][metric] for a in subset]
                result[metric] = {"mean_difference": mean(d) if d else None,
                                  "better_equal_worse": [sum(x<0 for x in d),sum(x==0 for x in d),sum(x>0 for x in d)]}
            comparisons[fam][other] = result
        for b in range(5):
            block_keys = [k for k in keys if items[k]["block"] == b]
            keep = [k for k in block_keys if k in retained]
            ledger = next(v for v in overlap["blocks"] if (v["family"],v["block"]) == (fam,b))
            blocks.append(dict(ledger, positions_planned=len(block_keys)*5,
                missing_by_role={r:[k for k in block_keys if not available(scores.get(k,{}),r)] for r in ROLES},
                primary_pairs={n:sum(available(scores.get(k,{}),c) and available(scores.get(k,{}),"V_COST") for k in block_keys) for n,c,_ in TESTS},
                retained_pairs={n:sum(available(scores.get(k,{}),c) and available(scores.get(k,{}),"V_COST") for k in keep) for n,c,_ in TESTS}))
    return {"primary": main, "sensitivity": extra, "families": families, "blocks": blocks,
            "descriptive_pairs": comparisons, "worse_than_periodic": worse}
