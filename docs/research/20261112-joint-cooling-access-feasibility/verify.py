"""Check the two-order result against the hand calculation fixed before execution."""

import argparse
import hashlib
import json
from pathlib import Path


# Each tuple is (A finish, B finish, total reserved person-seconds).
EXPECTED = {
    "slack": ((150.25, 360.75, 360.75), (300.75, 90.25, 300.75),
              "BOTH_FEASIBLE", ["AB", "BA"], [], []),
    "travel_deadline": ((150.25, 360.75, 360.75), (300.75, 90.25, 300.75),
                        "ONE_ORDER_FEASIBLE", ["BA"], ["DEADLINE:B"], []),
    "permit_wait": ((150.25, 360.75, 360.75), (465.5, 255, 465.5),
                    "ONE_ORDER_FEASIBLE", ["AB"], [], ["DEADLINE:A"]),
    "person_budget": ((150.25, 360.75, 360.75), (300.75, 90.25, 300.75),
                      "NEITHER_FEASIBLE", [], ["PERSON_BUDGET"], ["PERSON_BUDGET"]),
    "missing_permit": ((150.25, None, None), (None, None, None),
                        "INSUFFICIENT_EVIDENCE", [], ["WORK_PERMIT_UNKNOWN:B"], ["WORK_PERMIT_UNKNOWN:B"]),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("result", type=Path)
    parser.add_argument("verification", type=Path)
    args = parser.parse_args()
    result = json.loads(args.result.read_text(encoding="utf-8"))
    for name, key in (("analyze.py", "script"), ("protocol.json", "protocol")):
        check(sha(Path(__file__).with_name(name)) == result[key]["sha256"], f"Provenance: {name}")
    cases = {c["id"]: c for c in result["cases"]}
    check(set(cases) == set(EXPECTED), "Case set differs from hand calculation")
    for key, expected in EXPECTED.items():
        case = cases[key]
        for order, timing, reasons in (("AB", expected[0], expected[4]), ("BA", expected[1], expected[5])):
            plan = case["orders"][order]
            endpoints = tuple(plan["schedule"].get(task, {}).get("finish_s") for task in ("A", "B"))
            check((*endpoints, plan["person_s"]) == timing and plan["reasons"] == reasons,
                  f"Endpoint or gate mismatch: {key}/{order}")
            if timing[-1] is not None:
                check(plan["schedule"][order[0]]["finish_s"] == plan["schedule"][order[1]]["departure_s"],
                      f"Resource overlap or gap: {key}/{order}")
                check(plan["tool_s"] == timing[-1], f"Tool occupation mismatch: {key}/{order}")
        check(case["verdict"] == expected[2] and case["feasible_orders"] == expected[3],
              f"Verdict mismatch: {key}")
    check(cases["permit_wait"]["orders"]["BA"]["schedule"]["B"]["permit_wait_s"] == 164.75,
          "Permit wait arithmetic mismatch")
    check(cases["person_budget"]["single_tasks"] == {"A": "FEASIBLE", "B": "FEASIBLE"},
          "Single-task feasibility mismatch")
    check(result["new_facility_runs"] == result["new_policy_calls"] == result["registered_research_runs"] == 0,
          "Evidence scope mismatch")
    receipt = {"status": "PASS", "method": "Independent hand-calculated endpoints, failed gates and occupied intervals",
               "cases": len(EXPECTED), "orders": 2 * len(EXPECTED), "result_sha256": sha(args.result),
               "verification_script_sha256": sha(Path(__file__))}
    with args.verification.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(receipt, handle, indent=2)
        handle.write("\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
