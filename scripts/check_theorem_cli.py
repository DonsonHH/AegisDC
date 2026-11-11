"""A single local public CLI check for the theorem and field-record entrypoints."""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
ENTRY = Path("scripts/verify_theorem.py")
TEMPLATE = Path("docs/mainline/39r-ups-field-record.template.json")
SCHEMA = Path("docs/mainline/39r-ups-field-record.schema.json")
DELIVERY = Path("evidence/mainline/engineering/39r-ups-field-cli-v1/result.json")


def fixture():
    # The frozen v1 reference proportions, with declared example clocks.
    return {
        "schema": "aegisdc-ups-field-record-v1", "record_id": "synthetic-v1-reference",
        "asset_id": "local_controller", "basis": "DECLARED_FIXTURE",
        "evidence_refs": ["frozen v1 proportions; synthetic timestamps"],
        "legal_actions": ["defer", "escalate", "direct", "inspect"],
        "fixed_over_prior": True, "leaf_gap_s": "27.8",
        "parameters": {"a": "81/100", "b": "9/100", "q_I": "3/4", "q_R": 0.75,
                       "r_E": "3/8", "d_R": "1/10", "d_FP": "1/10", "d_E": 0, "k": "1/50"},
        "gates": {"direct_authorized": True, "direct_resource_feasible": True,
                  "inspection_resource_feasible": True, "restore_after_report_authorized": True,
                  "escalation_resource_feasible": True},
        "timestamps": {"decision_at": "2026-01-01T00:00:00Z", "deadline_at": "2026-01-01T00:00:10Z",
                       "direct_completion_at": "2026-01-01T00:00:04Z", "report_available_at": "2026-01-01T00:00:01Z",
                       "conditional_completion_at": "2026-01-01T00:00:05Z"},
    }


def cases(folder):
    base = ["pair", "--t", "9/10", "--u0", "1/10", "--u1", "1/10", "--q-i", "3/4",
            "--q-r", "3/4", "--d-r", "1/10", "--d-fp", "1/10", "--k", "1/50"]
    yield "pair_decimal", base + ["--s", "0.9"], 0, {
        "alpha": "71/1000", "beta": "-13/80", "strict_win_interval": "[0,142/467)", "tie_region": "{142/467}"
    }
    yield "pair_probability_above_one", base + ["--s", "1.1"], 1, "s must be in [0,1]"
    yield "pair_negative_fraction", base + ["--s=-1/10"], 1, "s must be in [0,1]"
    yield "pair_invalid_binary_gate", base + ["--s", "0.9", "--g", "2"], 2, "invalid choice"

    complete = fixture()
    harmless = deepcopy(complete)
    harmless["parameters"].update(d_R=0, d_FP=0)
    missing_q = deepcopy(harmless)
    missing_q["parameters"]["q_R"] = None
    unknown_grant = deepcopy(complete)
    unknown_grant["gates"]["direct_authorized"] = None
    late = deepcopy(complete)
    late["timestamps"]["direct_completion_at"] = late["timestamps"]["deadline_at"]
    records = [
        ("field_reference", complete, {
            "status": "COMPARABLE",
            "comparisons": {"direct": {"alpha": "71/1000", "beta": "-13/80", "strict_win_interval": "[0,142/467)"}},
            "best_no_inspection": {"strict_win_interval": "(58/483,142/467)"},
        }),
        ("field_no_disturbance", harmless, {
            "status": "COMPARABLE", "direct_dominance": {"status": "SATISFIED"},
            "comparisons": {"direct": {"strict_win_interval": None}},
        }),
        ("field_unknown_q_r", missing_q, {
            "status": "INSUFFICIENT_INPUT", "best_no_inspection": {"strict_win_interval": None},
            "comparisons": {"direct": {"missing_inputs": ["parameters.q_R"],
                "single_missing_boundary": {"parameter": "parameters.q_R",
                    "no_strict_win_parameter_range": "[47/80,1]", "could_flip_nonempty_strict_win": True}}},
        }),
        ("field_unknown_grant", unknown_grant, {
            "status": "INSUFFICIENT_INPUT",
            "eligibility": {"direct": {"status": "UNKNOWN", "missing_inputs": ["gates.direct_authorized"]}},
            "best_no_inspection": {"strict_win_interval": None},
        }),
        ("field_deadline_equality", late, {
            "status": "COMPARABLE", "eligibility": {"direct": {"status": "INELIGIBLE", "reasons": ["DEADLINE_NOT_MET"]}},
            "comparisons": {"direct": {"status": "NOT_COMPARABLE"}},
            "best_no_inspection": {"strict_win_interval": "(58/483,1]"},
        }),
        ("field_blank_template", json.loads((ROOT / TEMPLATE).read_bytes()), {
            "status": "INSUFFICIENT_INPUT", "best_no_inspection": {"strict_win_interval": None},
        }),
    ]
    for name, record, expected in records:
        path = folder / (name + ".json")
        path.write_text(json.dumps(record), encoding="utf-8")
        yield name, ["field", "--input", str(path)], 0, expected


def projection(expected, actual):
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return actual
        return {k: projection(v, actual[k]) for k, v in expected.items() if k in actual}
    return actual


def run():
    rows = []
    work = (ROOT / ".work").resolve()
    work.mkdir(exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="ups-cli-check-", dir=work)).resolve()
    if not folder.is_relative_to(work):
        raise ValueError("Temporary input path escaped the workspace")
    for name, args, code, expected in cases(folder):
        proc = subprocess.run([sys.executable, "-B", "-X", "utf8", str(ROOT / ENTRY), *args],
                              cwd=ROOT, text=True, encoding="utf-8", capture_output=True, timeout=10)
        if code == 0 and proc.returncode == 0:
            try:
                observed = projection(expected, json.loads(proc.stdout))
            except json.JSONDecodeError:
                observed = {"invalid_json_output": True}
        else:
            observed = (proc.stderr.strip().splitlines() or [""])[-1]
        ok = proc.returncode == code and (observed == expected if code == 0 else expected in observed)
        rows.append({"case": name, "expected_exit": code, "actual_exit": proc.returncode,
                     "expected": expected, "observed": observed, "passed": ok})
    sources = [ENTRY, Path(__file__).resolve().relative_to(ROOT), SCHEMA, TEMPLATE,
               Path("scripts/verify_theorem_v1.py"), Path("scripts/verify_theorem_field.py")]
    return {"status": "PASS_CLI_ONLY" if all(r["passed"] for r in rows) else "FAILED_CLI_CHECK",
            "sources": {p.as_posix(): sha256((ROOT / p).read_bytes()).hexdigest()
                        for p in sources if (ROOT / p).is_file()},
            "accounting": {"cli_cases": len(rows), "passed": sum(r["passed"] for r in rows),
                           "facility_entries": 0, "policy_calls": 0, "model_calls": 0, "registered_research_runs": 0},
            "cases": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", type=Path)
    mode.add_argument("--check", type=Path)
    parser.add_argument("--red-receipt", type=Path)
    args = parser.parse_args()
    if args.write and args.write.exists():
        parser.error("output already exists")
    current = run()
    result = {"schema": "aegisdc-ups-field-cli-verification-v1", "verification": current,
              "command": f"python -B scripts/check_theorem_cli.py --check {DELIVERY.as_posix()}",
              "scope": "Public CLI boundaries and declared field fixtures only; no model calibration"}
    if args.red_receipt:
        raw = args.red_receipt.read_bytes()
        red = json.loads(raw)["verification"]
        result["pre_implementation"] = {"sha256": sha256(raw).hexdigest(), "verification": red}
    if args.write:
        with args.write.open("x", encoding="utf-8", newline="\n") as f:
            json.dump(result, f, indent=2, sort_keys=True, ensure_ascii=True)
            f.write("\n")
    else:
        saved = json.loads(args.check.read_bytes())
        if current != saved["verification"]:
            parser.exit(1, "CLI verification differs from saved results\n")
    print(json.dumps({"status": current["status"], **current["accounting"]}, sort_keys=True))
    return 0 if current["status"] == "PASS_CLI_ONLY" else 1


if __name__ == "__main__":
    sys.exit(main())
