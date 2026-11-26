"""Reconcile the historical catalogue for shared-account FIT; no FIT inputs or overlap requests."""

import argparse
from functools import lru_cache
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DATA = "docs/mainline/"
R0 = HERE.parent / "r0"
SOURCE = "41709979b277812c1b7af8af5d7d3128293cb790"
SEALED = "0a74506cd10cf7d45d038a0bd027619d62852ede"
PANEL_LAW = "222cb1aaca8c2fe565696714981453f4422539b4a9d76c4bec4ea8849ea42a62"
SHARED_FIT = "f8a4d6d320c090a4a74280542df5c864677dcfe78e79638843b1fad86887340f"
SEALED_INDEX = "t7-incident-counterfactual/stage2/pre-score/input-manifest.json"
SEALED_HEADER = "t7-incident-counterfactual/stage2/pre-score/input-freeze.json"


def require(test):
    if not test:
        raise ValueError("Incomplete catalogue")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def packed(obj, legacy=False):
    return json.dumps(obj, sort_keys=not legacy, ensure_ascii=not legacy,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def is_hash(value):
    return isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value) is not None


@lru_cache(maxsize=None)
def blob(path, rev=SOURCE):
    require(re.fullmatch("[0-9a-f]{40}", rev))
    if path.startswith("t7-incident-counterfactual/stage2/"):
        require(rev == SEALED and path in (SEALED_INDEX, SEALED_HEADER))
    return subprocess.check_output(["git", "cat-file", "blob", f"{rev}:{DATA}{path}"],
                                   cwd=ROOT, stderr=subprocess.DEVNULL)


def metadata(path, rev=SOURCE):
    return json.loads(blob(path, rev))


def archive_group(folder, phase, legacy, expected):
    stem = f"{folder}/{phase}"
    manifest_path = stem + ("-inputs.json" if legacy else "-manifest.json")
    manifest = metadata(manifest_path)
    archive = blob(stem + "-inputs.jsonl.gz")
    require(sha(archive) == manifest["zipped" if legacy else "input_archive"])
    pairs = {}
    with gzip.GzipFile(fileobj=io.BytesIO(archive)) as lines:
        for line in lines:
            item = json.loads(line)
            name, value = (item["key"], item["value"]) if legacy else item
            original = value
            if not legacy and phase == "eng":
                # The version-pinned producer sorted integer plan times before JSON converted them to strings.
                original = dict(value, plan={int(t): action for t, action in value["plan"].items()})
            require(name not in pairs and sha(packed(original, legacy) + b"\n") == manifest["files"][name])
            case = value["input" if legacy else "case"] if phase in ("eng", "engineering") else value
            fields = ("native", "attachment") if legacy else ("native", "attachment", "maintenance")
            pairs[name] = (sha(packed(case, legacy) + b"\n"), sha(packed({k: case[k] for k in fields})))
    require(len(pairs) == expected and set(pairs) == set(manifest["files"]))
    return pairs


def from_register(path, table_name, counts, rev=SOURCE):
    register = metadata(path, rev)
    table, order = register[table_name], register["order"]
    if isinstance(order, dict):
        require(set(order) == {"FIT", "DEV"} and [len(order[s]) for s in ("FIT", "DEV")] == counts)
        groups = [order["FIT"], order["DEV"]]
    else:
        groups = [order]
    flat = [k for group in groups for k in group]
    require([len(g) for g in groups] == counts and len(flat) == len(set(flat)) and set(flat) == set(table))
    pairs = [{k: (table[k]["sha256"], table[k]["operative_sha256"]) for k in group} for group in groups]
    require(all(is_hash(h) for group in pairs for pair in group.values() for h in pair))
    return pairs


def historical_catalogue():
    """Private return values belong inside the catalogue or whole-batch comparator process."""
    law_bytes = (R0 / "panel-law.json").read_bytes()
    require(sha(law_bytes) == PANEL_LAW)
    law = json.loads(law_bytes)["historical_catalogue"]
    require(law["reference_revision_except_H3"] == SOURCE and law["entries"][-1]["revision"] == SEALED)
    t3, t4c = "t3-prior-information-v2", "t4c-action-cost-v3"
    v3a, v3b, v3c = ("t5-landscape-diagnostic-v3a", "t5-block-recombination-v3b", "t5-observable-selector-v3c")
    groups = {
        "T3": [archive_group(t3, "engineering", True, 27), archive_group(t3, "development", True, 72)],
        "T4b": from_register("t4b-holdout-confirmation-v2/condition-summary.json", "conditions", [144]),
        "T4c": [archive_group(t4c, "eng", False, 27), archive_group(t4c, "dev", False, 72)],
    }
    for version, table, counts, binding in [("v1", "conditions", [36, 48], "input_publication"),
                                           ("v2", "cases", [12, 24], "inputs_publication")]:
        folder = "t5-ordinary-improvement-development-" + version
        path = folder + "/inputs.json"
        receipt = metadata(folder + "/receipt.json")
        require(blob(path) == blob(path, receipt[binding]))
        published = from_register(path, table, counts)
        groups["T5-" + version] = published
        roster = {name: pair for group in published for name, pair in group.items()}
        positions = receipt["positions"]
        manifest_hash = sha(blob(path))
        require({pos["key"] for pos in positions} == set(roster) and
                all(pos["input"] == roster[pos["key"]][0] and pos["input_manifest"] == manifest_hash
                    for pos in positions))
        require(receipt["startup_witness" if version == "v1" else "public_checks"]["native_entries"] == 0)
    path_a = v3a + "/panel-and-strategies.json"
    receipt_a = metadata(v3a + "/receipt.json")
    require(blob(path_a) == blob(path_a, receipt_a["pre_execution_panel"]))
    groups["T5-v3a"] = from_register(path_a, "conditions", [36])
    auxiliary = metadata(path_a)["identity_only_keys"]
    require(receipt_a["extra_identity_witnesses"] == auxiliary and set(auxiliary).issubset(groups["T5-v3a"][0]))
    require({p["key"] for p in receipt_a["durable_position_index"]} == set(groups["T5-v3a"][0]))
    receipt_b = metadata(v3b + "/receipt.json")
    require(receipt_b["public_inputs"]["v3a"]["panel-and-strategies.json"] == sha(blob(path_a)) and
            receipt_b["stage_B_started"] is False)
    groups["T5-v3b"] = groups["T5-v3a"]
    prior = v3c + "/predecessors.json"
    receipt_c = metadata(v3c + "/development-receipt.json")
    require(receipt_c["checked_conditions"] == 36 and receipt_c["prior_sources_file_sha256"] == sha(blob(prior)))
    require(metadata(prior)["files"][DATA + path_a] == sha(blob(path_a)))
    path_c = v3c + "/new-panel.json"
    completed = metadata(v3c + "/confirmation-receipt.json")
    confirmation = completed["panel"]
    require(confirmation["sha256"] == sha(blob(path_c)) and blob(path_c) == blob(path_c, confirmation["commit"]))
    require(completed["originals_compared"] == completed["native_markers"] == completed["positions_planned"])
    groups["T5-v3c"] = [groups["T5-v3a"][0], *from_register(path_c, "cases", [36])]
    alias = metadata("t7-incident-counterfactual/stage1/compatibility.json")
    require(alias["status"] == "PASS" and alias["input_manifest_sha256"] == sha(blob(t3 + "/development-inputs.json"))
            and alias["input_archive_sha256"] == sha(blob(t3 + "/development-inputs.jsonl.gz")))
    subset = {}
    for entry in alias["handshakes"]:
        name = entry["key"]
        require(name not in subset and entry["input_sha256"] == groups["T3"][1][name][0])
        subset[name] = groups["T3"][1][name]
    require(len(subset) == 24)
    groups["T7-stage1"] = [subset]
    # The only H3 material admitted here is its prescore freeze header and the already sealed hash index.
    # Never read a seed, case, overlap ledger, outcome, or trace; never export per-input hashes.
    header = metadata(SEALED_HEADER, SEALED)
    require(header["conditions_generated"] == 120 and header["facility_entries"] == header["score_reads"] == 0 and
            header["files_sha256"]["input-manifest.json"] == sha(blob(SEALED_INDEX, SEALED)))
    groups["H3-sealed-index"] = from_register(SEALED_INDEX, "conditions", [120], SEALED)
    return groups


def declaration():
    groups = historical_catalogue()
    template = json.loads((HERE.parent/"custody/catalogue-coverage.json").read_bytes())
    require(template["registration_id"] == SHARED_FIT and len(template["sources"]) == len(groups) and
            {s["source"] for s in template["sources"]} == set(groups))
    law = (R0/"panel-law.json").read_bytes()
    require(sha(law) == PANEL_LAW)
    old = json.loads(law)["historical_catalogue"]
    private_inventory = []
    for entry in sorted(template["sources"], key=lambda item: item["source"]):
        source = entry["source"]
        ref = int(entry["count_reference"].split("/")[1])
        pinned_entry = old["entries"][ref]
        revision = pinned_entry.get("revision", SOURCE)
        require(revision == entry["reference_revision"] and [len(g) for g in groups[source]] ==
                entry["registered_counts"] == pinned_entry["counts"])
        enc = (["historical_full", "legacy_common"] if source in ("T3", "T7-stage1") else
               ["sealed_full", "sealed_operative"] if source == "H3-sealed-index" else ["historical_full", "v3_operative"])
        require(entry["required_encodings"] == enc)
        roots = {p:sha(blob(p.removeprefix(DATA), revision)) for p in pinned_entry["paths"]}
        item = {"source":source, "revision":revision, "references":roots, "encodings":enc,
                "counts":entry["registered_counts"], "reuse":entry["recorded_reuse"],
                "groups":[sorted(g.values()) for g in groups[source]]}
        private_inventory.append(item)
        entry["custodian"] = dict(version=revision, expected_counts=entry["registered_counts"], identity_encodings=enc)
    template["catalogue_root"] = sha(packed({"schema":"AegisDC.T8.FIT.historical-input-commitments.v1",
                                             "panel_law":PANEL_LAW, "sources":private_inventory}))
    template["additional_realizations_and_aliases_reconciled"] = True
    # The executor prepared the catalogue under option C. The PI still signs the actual comparison verdict.
    template["issued_by"] = "codex-executor"
    return template


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--public-declaration", action="store_true", help="emit public coverage metadata only")
    mode.add_argument("--check", action="store_true", help="verify the published historical catalogue root")
    args = parser.parse_args()
    try:
        result = declaration()
        if args.public_declaration:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            require(result == json.loads((HERE.parent/"custody/catalogue-coverage.json").read_bytes()))
            print("VERIFIED procedural catalogue; prescore commitments only; no FIT request or facility call")
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError):
        print("UNVERIFIED CATALOGUE", file=sys.stderr)
        sys.exit(1)
