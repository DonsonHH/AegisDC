"""Read stored T8 FIT inputs and signed score records. Emit aggregate statistics only."""

import argparse
from collections import Counter, defaultdict
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, variance
import sys

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from scipy.stats import t


SEALED = "59fe7b1c8f0c14e1195c2b80233c1599c8ad7417"
RESULT_HASH = "3f225fc941858c0259f015fdaaa97a6dad7877889dff7c17b52ad218b156efff"
PROOF_HASH = "fba93d1daec5f95037f5ae1a8c3e872163ca87a7b35ad8bf828bf3f90c2341e9"
AUDIT_LOCK = "7be88fbbc4f1b6c2af06eff1d9d910060122b3db4468ed5a1bdaf555d0cb41ae"
FAMILIES = ("LONDON", "NETHERLANDS")
CELLS = ("DIRECT_NEAR", "ALARM_NEAR", "ORDER_NEAR", "DIRECT_FAR", "ALARM_FAR", "ORDER_FAR")
MICRO = 1_000_000


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def pinned(path, digest):
    raw = path.read_bytes()
    require(sha(raw) == digest, "stored file hash mismatch: " + path.name)
    return raw


def signed(box, key):
    require(box["signer"] == key, "signature authority")
    Ed25519PublicKey.from_public_bytes(bytes.fromhex(key)).verify(
        bytes.fromhex(box["signature"]), canonical(box["payload"]))
    return box["payload"]


def object_at(evidence, ref):
    require(ref["locator"] == "objects/" + ref["sha256"] and len(ref["sha256"]) == 64, "sealed locator")
    raw = pinned(evidence / ref["locator"], ref["sha256"])
    require(len(raw) == ref["bytes"], "sealed length")
    return json.loads(raw)


def structure(root, batch_root):
    source = root / "source"
    lock = json.loads(pinned(source / "r1/audit-sources.json", AUDIT_LOCK))["files_sha256"]
    for name, digest in lock.items():
        if name.startswith("base/") or name in ("r1/capacity_audit.py", "r1/audit-plan.json"):
            pinned(source / name, digest)
    base = source / "base"
    sys.path[:0] = [str(source / "r1"), str(base / "src"), str(base / "docs/mainline/t3-prior-information-v2")]
    import capacity_audit as audit
    import public_work
    from aegis_action_cost import permit

    require(Path(audit.__file__).resolve() == source / "r1/capacity_audit.py"
            and all(Path(m.__file__).resolve().is_relative_to(base) for m in (public_work, permit)),
            "frozen static admission and signature code")
    raw = (root / "panel/batch.private.json").read_bytes()
    require(raw.endswith(b"\n") and sha(raw[:-1]) == batch_root, "frozen ordered FIT manifest")
    manifest = json.loads(raw)
    require(manifest["split"] == "FIT" and manifest["registered_rows"] == len(manifest["ordered"]) == 48,
            "FIT only")
    meta = []
    for ordinal, item in enumerate(manifest["ordered"], 1):
        require(item["ordinal"] == ordinal, "input ordinal")
        case = json.loads(pinned(root / "panel/conditions" / f"{ordinal:02}.json", item["v3_full"]))
        family, draw = case["evaluation"]["family"], case["evaluation"]["draw"]
        require(family == FAMILIES[(ordinal-1) % 2] and draw == (ordinal-1)//2, "family, draw and block order")
        features = audit.structural_features(case, family, public_work, permit.Gate)
        flags = audit.structural_signature({k: [(v, 1)] for k, v in features.items()})
        meta.append((family, draw//12, item["v3_full"], flags, features))
    output = {}
    block_types = {}
    for family in FAMILIES:
        family_rows = [m for m in meta if m[0] == family]
        blocks = []
        for block in (0, 1):
            rows = [m for m in family_rows if m[1] == block]
            require(len(rows) == 12, "twelve-row block")
            hist = {k: audit.histogram([m[4][k] for m in rows]) for k in audit.FEATURES}
            signature = audit.structural_signature(hist)
            require(tuple(map(sum, zip(*(m[3] for m in rows)))) == signature, "row contributions to block")
            blocks.append(signature)
        block_types[family] = blocks
        output[family] = {
            "blocks_in_order": blocks,
            "block_patterns": [{"signature": k, "blocks": n, "conditions": 12*n}
                               for k, n in sorted(Counter(blocks).items())],
            "row_patterns": [{"flags": k, "conditions": n}
                             for k, n in sorted(Counter(m[3] for m in family_rows).items())],
        }
    return meta, block_types, output


def read_slot(study, slot, expected, key, meta):
    evidence = study / "evidence"
    arm, rd, index, context = expected
    group = study / "positions" / f"{arm}-{rd}-{index}"
    closed = json.loads((group / "closed.json").read_bytes())
    require(closed["meter"] == slot["attempts_receipt"] and closed["packet"] == slot["fit_return"]["receipt"],
            "private slot attached to released ledger")
    packet = signed(object_at(evidence, closed["packet"]), key)
    meter = signed(object_at(evidence, closed["meter"]), key)
    numeric = object_at(evidence, meter["originals"])
    physical = object_at(evidence, meter["physical"])
    binding = packet["binding"]
    require(binding == meter["binding"] == numeric["binding"] == physical["binding"] and
            (binding["arm"], binding["round"], binding["slot"], binding["context"]) == expected and
            binding["policy_id"] == slot["policy"]["id"], "round, policy, score and input binding")
    require(len(numeric["rows"]) == len(physical["physical"]) == 48 and meter["status"] == "COMPLETE",
            "complete paid denominator")
    rows = []
    for n, (pair, original) in enumerate(zip(physical["physical"], numeric["rows"], strict=True), 1):
        ref = group / f"{n:02}"
        entry = json.loads(pinned(ref / "native-admitted.json", pair["native_entry_sha256"]))
        score = json.loads(pinned(ref / "sink/score.json", pair["score_sha256"]),
                           parse_float=str, parse_int=str)
        require(entry["ordinal"] == pair["ordinal"] == n and entry["input"] == meta[n-1][2]
                and pair["complete"] and pair["native_entered"], "paired original input")
        require(score["raw_sha256"] == pair["raw_sha256"] and int(score["hard_violations"]) ==
                original["hard_violations"] == 0, "safe saved outcome")
        require(all(score[k] == original[k] for k in ("L", "person")), "original decimal tokens")
        rows.append(tuple(Fraction(Decimal(score[k])) for k in ("L", "person")))
    for column, name in enumerate(("L_sum_us", "person_sum_us")):
        total = sum(round(row[column]*MICRO) for row in rows)
        require(total == slot["fit_return"][name] == packet["data"][name], "signed aggregate")
    return rows


def counts(pairs):
    return [{"L_s": float(k[0]), "person_s": float(k[1]), "slots": v}
            for k, v in sorted(Counter(pairs).items())]


def averages(rows):
    return tuple(mean(col) for col in zip(*rows, strict=True))


def read_search(study, public, sealed, proof, meta):
    context = sealed["execution_envelope_sha256"]
    require(context == proof["context"], "frozen execution identity")
    shared = signed(object_at(study / "evidence", proof["shared"]), proof["journal_public"])
    require(shared["purpose"] == "shared-parent-return" and shared["context"] == context, "shared return")
    parent = read_slot(study, shared["body"]["slot"], ("PARENT", 0, 0, context), proof["score_public"], meta)
    paid, candidate, rounds = {}, {}, []
    for arm in ("O", "R"):
        for rd, reported in enumerate(sealed["arms"][arm]["rounds"], 1):
            rec = json.loads((public / "rounds" / f"{arm}-{rd}.json").read_bytes())
            require(sha(canonical(rec)) == reported["record_sha256"] and rec["arm"] == arm
                    and rec["round"] == rd and rec["status"] == "CLOSED", "published complete round")
            seal_ref = rec["audit"]["record_seal"]
            journal = signed(object_at(study / "evidence", seal_ref), proof["journal_public"])
            body = dict(rec, audit={k: v for k, v in rec["audit"].items() if k != "record_seal"})
            require(journal["context"] == context and journal["purpose"] == "round"
                    and journal["body"]["payload_sha256"] == sha(canonical(body)), "round signature")
            means, ids = [], []
            for slot in rec["slots"]:
                idx = slot["slot"]
                ident = slot["policy"]["id"]
                levels = tuple(slot["policy"]["levels"])
                require(sum(x != 0 for x in levels) == 1, "one-coordinate edits from zero")
                cell = next(i for i, value in enumerate(levels) if value)
                label = f"{CELLS[cell]}={levels[cell]}"
                values = read_slot(study, slot, (arm, rd, idx, context), proof["score_public"], meta)
                require(ident not in candidate or candidate[ident] == (label, values),
                        "duplicate descriptor agrees on both original metrics at every ordinal")
                candidate[ident] = (label, values)
                paid[arm, rd, idx] = ident
                means.append(averages(values))
                ids.append(ident)
            rounds.append({"arm": arm, "round": rd, "ids": ids, "distribution": counts(means),
                           "selected": rec["selection"]["accepted_slot"], "rewrite": reported["rewrite_reason"],
                           "new_paid_slots": reported["new_paid_slots"],
                           "before": reported["program_before_sha256"], "after": reported["program_after_sha256"]})
    return parent, candidate, paid, rounds


def saturation(menu, parent, lock, indices):
    # Keep every minimizer, including ties. Classify rows on archived alternatives only.
    best_loss, best_lex = set(menu), set(menu)
    improvement = Counter()
    minimum_l, minimum_p, base_lex = [], [], []
    best_counts = Counter()
    for i in indices:
        loss, person = lock[i]
        options = {name: rows[i] for name, rows in menu.items()}
        low = min(x[0] for x in options.values())
        best = min(options.values())
        allowed = {name for name, x in options.items() if x[0] == low}
        best_loss &= allowed
        best_lex &= {name for name, x in options.items() if x == best}
        best_counts.update(allowed)
        minimum_l.append(low)
        minimum_p.append(best[1])
        base_lex.append(min(best, parent[i]))
        checks = {"lock_above_row_min_L": low < loss, "lock_above_row_min_lex": best < (loss, person),
                  "any_edit_lowers_parent_L": low < parent[i][0], "lock_lowers_parent_L": loss < parent[i][0],
                  "other_edit_helps_where_lock_does_not": low < parent[i][0] <= loss,
                  "another_edit_saves_staff_at_lock_loss": any(x[0] == loss and x[1] < person for x in options.values()),
                  "any_strict_joint_gain_over_parent": any(x[0] < parent[i][0] and x[1] < parent[i][1]
                                                         for x in options.values()),
                  "any_loss_gain_no_extra_staff": any(x[0] < parent[i][0] and x[1] <= parent[i][1]
                                                     for x in options.values()),
                  "all_edits_tie_on_L": len(allowed) == len(menu), "multiple_L_winners": len(allowed) > 1}
        for name, flag in checks.items():
            improvement[name] += int(flag)
    lock_L, lock_p = averages([lock[i] for i in indices])
    fixed = {k: averages([v[i] for i in indices]) for k, v in menu.items()}
    return {"n": len(indices), "L_optimum_intersection": sorted(best_loss),
            "lex_optimum_intersection": sorted(best_lex), "row_counts": dict(improvement),
            "L_min_hits_by_edit": {k: best_counts[k] for k in sorted(menu)},
            "best_fixed_mean_L_s": float(min(v[0] for v in fixed.values())),
            "row_min_mean_L_s": float(mean(minimum_l)), "least_person_at_row_min_L_s": float(mean(minimum_p)),
            "loss_gap_lock_vs_row_min_s": float(lock_L-mean(minimum_l)),
            "staff_gap_lock_vs_row_lex_s": float(lock_p-mean(minimum_p)),
            "parent_included_row_lex_means": list(map(float, averages(base_lex)))}


def endpoints(parent, lock, meta, block_types):
    results = []
    min_k = min(len(set(v)) for v in block_types.values())
    for q, fam, col, threshold in (("Q1", FAMILIES[1], 0, 0), ("Q2", FAMILIES[0], 0, 5),
                                   ("Q3-L", FAMILIES[0], 1, 5), ("Q3-N", FAMILIES[1], 1, 5)):
        pairs = [[lock[i][col] - parent[i][col] for i, m in enumerate(meta) if m[:2] == (fam, b)]
                 for b in (0, 1)]
        require(list(map(len, pairs)) == [12, 12], "complete paired blocks")
        means = list(map(mean, pairs))
        delta, var = mean(means), variance(means)
        def upper(g):
            return float(delta) + float(t.ppf(.95, g-1))*math.sqrt(float(var)/g) if var else None
        projection = upper(38)
        passes = projection is not None and (projection < threshold if q == "Q1" else projection <= threshold)
        cluster = defaultdict(Fraction)
        for sig, m in zip(block_types[fam], means, strict=True):
            cluster[sig] += m-delta
        k = len(cluster)
        cluster_var = (Fraction(k, k-1)*sum(x*x for x in cluster.values())/4
                       if k >= 2 and min_k >= 2 else None)
        cluster_u = (float(delta) + float(t.ppf(.95, min_k-1))*math.sqrt(float(cluster_var))
                     if cluster_var else None)
        rows = pairs[0] + pairs[1]
        results.append({"question": q, "family": fam, "metric": ("L", "person")[col], "threshold": threshold,
                        "operator": "<" if q == "Q1" else "<=", "n": len(rows),
                        "block_means": list(map(float, means)), "mean": float(delta), "block_sample_variance": float(var),
                        "block_sample_sd": math.sqrt(float(var)), "fit_upper_g2": upper(2),
                        "conditional_upper_g38": projection,
                        "conditional_status": ("INDETERMINATE" if projection is None else "MET" if passes else "NOT_MET"),
                        "fit_cluster_k": k, "fit_cluster_df": min_k-1, "fit_cluster_upper": cluster_u,
                        "improved_equal_worse": [sum(x < 0 for x in rows), sum(x == 0 for x in rows),
                                                 sum(x > 0 for x in rows)], "worst_row_delta": float(max(rows))})
    return results


def main(root):
    study = root / "scoring"
    public = study / "final-readback-497513ab/published"
    sealed = json.loads(pinned(public / "results.json", RESULT_HASH))
    proof = json.loads(pinned(public / "public-proof.json", PROOF_HASH))
    require(sealed["status"] == "DUAL_LOCKED_PENDING_REVIEW" and sealed["scored_positions"] == 1584, "sealed FIT")
    meta, block_types, signatures = structure(root, sealed["fit_batch_root"])
    parent, candidates, paid, rounds = read_search(study, public, sealed, proof, meta)
    lock_id = sealed["arms"]["R"]["locked"]["id"]
    require(lock_id == sealed["arms"]["O"]["locked"]["id"], "locked descriptors")
    menu = dict(candidates.values())
    require(len(candidates) == len(menu) and len(paid) == 32 and len(rounds) == 8, "candidate denominator")
    indices = {f: [i for i, m in enumerate(meta) if m[0] == f] for f in FAMILIES}
    baseline = averages(parent)
    table = []
    for ident, (edit, rows) in candidates.items():
        avg = averages(rows)
        difference = tuple(v-b for v, b in zip(avg, baseline, strict=True))
        by_family = {f: [float(mean(rows[i][c]-parent[i][c] for i in ix)) for c in (0, 1)]
                     for f, ix in indices.items()}
        table.append({"id": ident, "edit": edit, "slots": ["%s%d.%d" % key for key, val in paid.items() if val == ident],
                      "means": list(map(float, avg)), "delta": list(map(float, difference)), "family_deltas": by_family})
    lock_label, lock = candidates[lock_id]
    return {
        "schema": "AegisDC.T8.stage1c.fit-only.v1", "sealed_revision": SEALED, "batch_root": sealed["fit_batch_root"],
        "rounds": rounds, "distinct_candidates": len(candidates), "paid_proposals": len(paid),
        "shared_baseline_mean": list(map(float, baseline)), "locked_edit": lock_label, "candidates": table,
        "unpaid_single_edits": sorted({f"{cell}={level}" for cell in CELLS for level in (1, 2, 3)} - set(menu)),
        "strict_joint_gain": sum(v["delta"][0] < 0 and v["delta"][1] < 0 for v in table),
        "lower_loss_no_extra_person": sum(v["delta"][0] < 0 and v["delta"][1] <= 0 for v in table),
        "lower_loss_extra_person": sum(v["delta"][0] < 0 and v["delta"][1] > 0 for v in table),
        "structure": signatures,
        "saturation": {f: saturation(menu, parent, lock, ix) for f, ix in {**indices, "ALL": range(48)}.items()},
        "endpoints": endpoints(parent, lock, meta, block_types), "native_hard_violations_recorded": 0,
        "source_reads": {"fit_inputs": len(meta), "baseline_and_paid_positions": 48*(len(paid)+1),
                         "authenticated_rounds": len(rounds), "paid_score_packets_including_parent": len(paid)+1},
        "new_activity": {"facility_calls": 0, "research_scorer_calls": 0, "condition_generation": 0, "slurm_jobs": 0,
                         "FIT_overlap_requests": 0, "DEV_overlap_requests": 0, "DEV_panel_reads": 0,
                         "H2_accesses": 0, "H3_accesses_including_index": 0, "key_accesses_or_signatures": 0},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fit-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(main(args.fit_root.resolve()), indent=2, sort_keys=True, allow_nan=False))
