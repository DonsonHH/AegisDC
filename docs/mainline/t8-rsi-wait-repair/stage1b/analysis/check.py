"""Check the public 1c tables against the sealed rounds and a second private aggregate readback."""

import argparse
from collections import Counter
import hashlib
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import subprocess

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from scipy.stats import t
from tables import render


HERE = Path(__file__).resolve().parent
OLD = HERE.parent
REV = "59fe7b1c8f0c14e1195c2b80233c1599c8ad7417"
ROOT = HERE.parents[4]


def require(ok, name):
    if not ok:
        raise ValueError(name)


def same(a, b):
    return math.isclose(a, b, rel_tol=1e-11, abs_tol=1e-10)


def blob(rev, path):
    return subprocess.check_output(["git", "cat-file", "blob", rev + ":" + path.relative_to(ROOT).as_posix()], cwd=ROOT)


def old_json(path):
    return json.loads(blob(REV, path))


class VisibleCells(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current = None
        self.cells = []

    def handle_starttag(self, tag, attrs):
        if tag == "td":
            self.current = []

    def handle_endtag(self, tag):
        if tag == "td":
            self.cells.append("".join(self.current).strip())
            self.current = None

    def handle_data(self, text):
        if self.current is not None:
            self.current.append(text)


def check():
    d = json.loads((HERE / "statistics.json").read_bytes())
    second = json.loads((HERE / "independent-readback.json").read_bytes())
    seal = old_json(OLD / "results/results.json")
    require(d["sealed_revision"] == REV and d["batch_root"] == seal["fit_batch_root"], "FIT identity")
    rows = {c["id"]: c for c in d["candidates"]}
    seen = {"O": set(), "R": set()}
    for record in d["rounds"]:
        arm, rd = record["arm"], record["round"]
        archive = old_json(OLD / "results/rounds" / f"{arm}-{rd}.json")
        ids, distribution = [], Counter()
        for s in archive["slots"]:
            ident, ret = s["policy"]["id"], s["fit_return"]
            ids.append(ident)
            seen[arm].add(ident)
            require(ret["fit_n"] == 48 and ret["hard_violations"] == 0, "complete signed slot")
            scores = tuple(ret[k]/48_000_000 for k in ("L_sum_us", "person_sum_us"))
            require(all(same(a, b) for a, b in zip(scores, rows[ident]["means"], strict=True)), "slot means")
            require(f"{arm}{rd}.{s['slot']}" in rows[ident]["slots"], "separate paid positions")
            distribution[scores] += 1
        require(ids == record["ids"] and record["selected"] == archive["selection"]["accepted_slot"]
                and record["rewrite"] == archive["rewrite"]["reason"], "roster, selection and rewrite reason")
        freq = {(v["L_s"], v["person_s"]): v["slots"] for v in record["distribution"]}
        require(dict(distribution) == freq, "round frequency")
    require(seen["O"] == seen["R"] == set(rows) and 2*len(rows) == d["paid_proposals"] == 32
            and len(d["rounds"]) == 8, "distinct vs paid denominator")
    parent = d["shared_baseline_mean"]
    require(parent == [seal["baseline"]["score"][k] for k in ("L_mean_s", "person_mean_s")], "common baseline")
    for c in rows.values():
        for j in (0, 1):
            require(same(c["delta"][j], c["means"][j] - parent[j]) and
                    same(2*c["delta"][j], sum(m[j] for m in c["family_deltas"].values())), "family weighting")
    require(d["strict_joint_gain"] == sum(x["means"][0] < parent[0] and x["means"][1] < parent[1] for x in rows.values())
            and d["lower_loss_no_extra_person"] == sum(x["means"][0] < parent[0] and x["means"][1] <= parent[1]
                                                      for x in rows.values()), "joint gains")
    print("PASS 8 sealed rounds, 32 paid slots, 16 descriptors, round distributions and paired aggregate costs")

    for family, st in d["structure"].items():
        blocks = list(map(tuple, st["blocks_in_order"]))
        require(Counter(blocks) == {tuple(x["signature"]): x["blocks"] for x in st["block_patterns"]} and
                all(x["conditions"] == 12*x["blocks"] for x in st["block_patterns"]) and
                sum(p["conditions"] for p in st["row_patterns"]) == 24, "signature denominators")
        for j in range(5):
            require(sum(b[j] for b in blocks) == sum(r["flags"][j]*r["conditions"] for r in st["row_patterns"]),
                    "row signature components sum to the block signatures")
    s = d["saturation"]["ALL"]
    best = {rows[i]["edit"] for i in second["row_min_intersection"]}
    require(best == set(s["L_optimum_intersection"]) == {k for k, n in s["L_min_hits_by_edit"].items() if n == 48}
            and second["matched_arm_pairs"] == 768 and second["all_loss_tie_rows"] == s["row_counts"]["all_edits_tie_on_L"]
            and second["cheaper_equal_loss_rows"] == s["row_counts"]["another_edit_saves_staff_at_lock_loss"]
            and same(second["loss_gap"], s["loss_gap_lock_vs_row_min_s"])
            and same(second["staff_gap"], s["staff_gap_lock_vs_row_lex_s"]), "independent rowwise minima and ties")
    print("PASS 48 structural memberships, tied minima and separate saved-score readback of service and labor headroom")

    params = old_json(OLD.parent / "r0/registration.json")
    g = params["randomization"]["dev_blocks_per_family"]
    endpoints = params["estimands"]
    for e in d["endpoints"]:
        spec = endpoints[e["question"][:2].lower()]
        ix = int(e["metric"] == "person")
        means = [second["block_means_L_person"][f"{e['family']}-{i}"][ix] for i in (1, 2)]
        delta = sum(means)/2
        var = (means[1]-means[0])**2/2
        margin = spec["margin_person_s" if ix else "margin_s"]
        require(means == e["block_means"] and same(delta, e["mean"]) and same(var, e["block_sample_variance"])
                and e["threshold"] == margin and e["operator"] == spec["comparison"] and sum(e["improved_equal_worse"]) == 24,
                "paired endpoint definition")
        if var:
            upper = delta + t.isf(.05, g-1)*math.sqrt(var/g)
            u2 = delta + t.isf(.05, 1)*math.sqrt(var/2)
            passes = upper < margin if spec["comparison"] == "<" else upper <= margin
            require(same(upper, e["conditional_upper_g38"]) and same(u2, e["fit_upper_g2"])
                    and same(u2, e["fit_cluster_upper"]) and e["conditional_status"] == ("MET" if passes else "NOT_MET"),
                    "upper bounds and prediction")
        else:
            require(e["conditional_upper_g38"] is None and e["fit_cluster_upper"] is None and
                    e["fit_upper_g2"] is None and e["conditional_status"] == "INDETERMINATE", "zero variance rule")
    print("PASS r0 Q1, Q2 and both Q3 comparisons, sample variances, conditional upper bounds and degeneracy")

    folder = OLD / "fit-overlap"
    authority = old_json(OLD.parent / "custody/authority.json")
    message, sig = (blob(REV, folder / n) for n in ("receipt-signing.bin", "receipt.sig"))
    key = bytes.fromhex(authority["public_key_hex"])
    require(authority["credential_separation"] == "shared_account" and hashlib.sha256(key).hexdigest() ==
            authority["fingerprint_sha256"] and json.loads(message) == old_json(folder / "receipt.json")
            and (len(message), len(sig)) == (402, 64), "original procedural receipt")
    Ed25519PublicKey.from_public_bytes(key).verify(sig, message)
    require(not any(d["new_activity"].values()), "zero new research activity")
    require((HERE / "tables.md").read_bytes() == render(d).encode(), "table reproduction")
    html = VisibleCells()
    html.feed((HERE / "review.html").read_text(encoding="utf8"))
    for i, e in enumerate(d["endpoints"]):
        mean_cell, upper_cell = html.cells[4*i+1:4*i+3]
        for value, cell in ((e["mean"], mean_cell), (e["conditional_upper_g38"], upper_cell)):
            require(("未建立" in cell) if value is None else
                    (float(cell.replace("−", "-").split()[0]) == float(f"{value:.3f}")), "visible one-page values")
    print("PASS original detached signature, public table bytes, visible forecast cells and zero-activity ledger")


def checkout():
    prefix = HERE.relative_to(ROOT).as_posix() + "/"
    changed = subprocess.check_output(["git", "diff", "--no-renames", "--name-status", REV, "HEAD"],
                                      cwd=ROOT, text=True).splitlines()
    require(all(row.startswith("A\t"+prefix) for row in changed), "only new files in stage1b/analysis")
    files = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", "HEAD", "--", prefix],
                                    cwd=ROOT, text=True).splitlines()
    require(len(files) == len(changed) > 0, "declared added file set")
    for name in files:
        file = ROOT / name
        require(file.read_bytes() == blob("HEAD", file), "checkout bytes: " + name)
    print(f"PASS {len(files)} new analysis files byte-for-byte and zero changes to the sealed FIT tree")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", required=True, action="store_true")
    parser.add_argument("--checkout-bytes", action="store_true")
    args = parser.parse_args()
    check()
    if args.checkout_bytes:
        checkout()
