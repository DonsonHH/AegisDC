#!/usr/bin/env python3
"""Extract publication data from three byte-pinned, already saved JSON records.

This script imports no AegisDC module and performs no facility, policy, scoring,
qualification, or research execution. --source-dir must contain the originals
terminal.json, paired-results.json, and conditions.json at the pinned revision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REVISION = "cf666ec5c3f390ecb3b07818365cf4be2c475cde"
SOURCE_SPECS = {
    "dev19": {
        "file": "terminal.json",
        "path": "docs/mainline/review-gated/R4/public-development-v1/terminal.json",
        "git_blob": "0388efd41b56db7c540b6d18732c00a7efa42c69",
        "sha256": "f554b18a916ad3cf7fb0785e4aeb2b8a16df53d5ba5e896949634e3297f254f5",
    },
    "ext35": {
        "file": "paired-results.json",
        "path": "docs/mainline/review-gated/R4/finite-extension-study-v1/paired-results.json",
        "git_blob": "40a816680df7c119726463923f74e1f043898a55",
        "sha256": "e167cbe40b7791a9e94d0658e28fb8786244b3e40856f6d07aec025a20dd0bdc",
    },
    "ext35_conditions": {
        "file": "conditions.json",
        "path": "docs/mainline/review-gated/R4/finite-extension-v1/conditions.json",
        "git_blob": "0dc2ef19561551e0c88d4f0bac398fc07c9fa7b2",
        "sha256": "4b025bbb29e3652ff70a0a0ccd53556aaa131177bb3b6b9830c6c4e0053aa7d9",
    },
}


def load_pinned(source_dir: Path, spec: dict) -> dict:
    raw = (source_dir / spec["file"]).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    if digest != spec["sha256"] or blob != spec["git_blob"]:
        raise ValueError(f"Source identity mismatch: {spec['file']}")
    return json.loads(raw)


def extract(source_dir: Path) -> dict:
    originals = {k: load_pinned(source_dir, v) for k, v in SOURCE_SPECS.items()}
    data = {
        "schema": "aegisdc-london-pre-publication-figure-data-v1",
        "classification": "PUBLICATION_VIEW_OF_EXISTING_RECORDS_NO_NEW_RESEARCH",
        "source_revision": REVISION,
        "sources": {k: dict(v, url=f"https://github.com/DonsonHH/AegisDC/blob/{REVISION}/{v['path']}") for k, v in SOURCE_SPECS.items()},
        "number_semantics": "Copied JSON values retain source integer/string rational representation; float conversion occurs only at plot coordinates.",
        "arms": ["I", "D", "P"],
        "units": {"L": "service-deficit seconds", "U": "normalized-service-unit seconds", "person_seconds": "person seconds", "tool_seconds": "tool seconds", "time": "synthetic seconds", "energy": "kJ"},
        "panels": {},
        "cases": {},
        "source_visibility": "Repository-published saved summaries; private raw trajectories were not re-fetched for this manuscript.",
    }
    for panel in ("dev19", "ext35"):
        rows = []
        for idx, original in enumerate(originals[panel]["rows"]):
            case_id = original["condition_id"] if panel == "dev19" else original["slot"]
            eligible = original["valid_comparison"] if panel == "dev19" else original["eligible"]
            row = {
                "id": f"{panel}.{case_id}",
                "source_id": case_id,
                "source_pointer": f"/rows/{idx}",
                "eligible": eligible,
                "arms": {},
            }
            for arm in ("I", "D", "P"):
                v = original["arms"][arm]
                row["arms"][arm] = {key: v[key] for key in ("L", "U", "stage", "hard_constraints_ok", "recoveries")}
                row["arms"][arm]["costs"] = {key: v["costs"][key] for key in ("person_seconds", "tool_seconds")}
            rows.append(row)
        data["panels"][panel] = {
            "source": panel,
            "rows": rows,
            "condition_count": len(rows),
            "eligible_count": sum(r["eligible"] for r in rows),
            "noncompliant_ids": [r["id"] for r in rows if not r["eligible"]],
        }
    condition_index = {v["condition_id"]: i for i, v in enumerate(originals["ext35_conditions"]["conditions"])}
    for case_id in ("B01", "G05", "G06", "F01", "F02"):
        idx, original = next((i, v) for i, v in enumerate(originals["ext35"]["rows"]) if v["slot"] == case_id)
        ci = condition_index[case_id]
        cfg = originals["ext35_conditions"]["conditions"][ci]["common"]
        case = {
            "source": "ext35",
            "source_pointer": f"/rows/{idx}",
            "condition_source_pointer": f"/conditions/{ci}/common",
            "condition": {key: cfg[key] for key in ("H", "tF", "tR", "P", "E0", "ready", "permit", "work_mode", "demand")},
            "arms": {},
        }
        for arm in ("I", "D", "P"):
            v = original["arms"][arm]
            keys = ("L", "U", "ups_energy", "ending_UPS", "costs", "supply", "service_states", "load_isolation", "stage", "reached", "stop", "requests", "execution_receipts", "verify_records", "observations", "final_G", "final_device", "recoveries")
            case["arms"][arm] = {key: v[key] for key in keys}
        data["cases"][f"ext35.{case_id}"] = case
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "figure-data.json")
    args = parser.parse_args()
    data = extract(args.source_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "rows": {k: v["condition_count"] for k, v in data["panels"].items()}, "new_research_calls": 0}))


if __name__ == "__main__":
    main()
