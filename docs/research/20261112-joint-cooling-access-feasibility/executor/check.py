"""One V6 facility prefix and one isolated executor contrast for travel_deadline."""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path


BASE = "b2ae76cadea3a31543b2dbe1e19305dd44738518"
V6 = "configs/full-facility-mainline-reserve-v6.json"
NOMINAL = "evidence/mainline/engineering/29-uncertainty-domain/prepared-01/cases/nominal.json"
LEDGER = "configs/full-facility-decision-v1/common-ledger.json"
ARITHMETIC = "docs/research/20261112-joint-cooling-access-feasibility/result.json"
WORKER = "worker_cooling"
METER = "tool_flow_meter"
QUALIFICATION = "qualified_cooling_inspection"
DEADLINE = 330
PREFIX = 151
STEP = .01
BUDGET = 500
TASKS = {"A": ("inspect_facility_cooling", "intake_pump"), "B": ("inspect_space_access", "it_access_gate")}
RATES = ("worker_travel_person_s", "worker_wait_person_s", "access_check_person_s",
         "rendezvous_wait_person_s", "queue_wait_person_s", "worker_work_person_s",
         "tool_occupation_tool_s", "tool_work_tool_s")


def need(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def identity(path):
    with path.open("rb") as handle:
        sha = hashlib.file_digest(handle, "sha256").hexdigest()
    return {"bytes": path.stat().st_size, "sha256": sha}


def write(path, data):
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def read_inputs(root, source):
    need(source["git_revision"] == BASE, "Pinned source revision differs")
    for path, expected in source["files"].items():
        need(identity(root / path) == expected, f"Input identity mismatch: {path}")
    need(source["files"][ARITHMETIC]["sha256"] ==
         "a8ebb05573fe8e57c9ffb5986a49969391f30ec16477b02e48558a4d367b6ba8",
         "Wrong arithmetic original")
    public = load(root / NOMINAL)["public_static"]
    arithmetic = next(c for c in load(root / ARITHMETIC)["cases"] if c["id"] == "travel_deadline")
    need(arithmetic["deadline_s"] == {"A": DEADLINE, "B": DEADLINE}
         and arithmetic["person_budget_s"] == BUDGET
         and arithmetic["permit_from_s"] == {"A": 0, "B": 0}
         and arithmetic["feasible_orders"] == ["BA"], "Wrong comparison fixture")
    need(arithmetic["orders"]["AB"]["schedule"]["B"]["finish_s"] == 360.75, "Wrong forecast original")
    ledger = load(root / LEDGER)
    ledger["records"] = []
    return public, ledger


def programs(public, ledger, gateway, prepare_work):
    profile = public["workforce_profile"]
    need(profile["access_check_s"] == .25 and profile["feedback_latency_s"] == .5
         and profile["shifts"][WORKER] == [0, 3600], "Wrong archived timing profile")
    need(profile["walk_times_s"]["a2"] == 60 and profile["walk_times_s"]["a3"] == 120
         and all(profile["work_times_s"][pair[0]] == 30 for pair in TASKS.values()),
         "Scaled timing is outside this slice")
    frame = gateway(public["nominal_knowledge"], ledger, {
        "schema": "aegisdc-public-preparation-plan-v1", "id": "39r-travel-deadline",
        "basis": "synthetic_assumption", "time_unit": "s", "decision_times_s": [0], "requests": [],
    }).next_frame()
    need(frame["as_of_s"] == 0, "Both jobs must issue at epoch")
    tasks = {}
    for key, (interface, target) in TASKS.items():
        task = {"id": key, "work_interface_id": interface, "target_id": target,
                "crew": [{"worker_id": WORKER, "qualification_id": QUALIFICATION}],
                "tool_carrier_id": WORKER, "deadline_s": DEADLINE,
                "source_note": "Bounded work-executor check; no inspection outcome, repair or field claim."}
        check = prepare_work(frame, profile, task)
        need(check["legal_for_planning"] and not check["execution_permission"], "Invalid public preparation")
        tasks[key] = task
    return {order: {"schema": "aegisdc-work-program-v1", "id": "39r-travel-deadline-" + order,
                    "profile": profile, "submissions": [{"frame": frame, "task": tasks[k]} for k in order]}
            for order in ("AB", "BA")}


def state_at(time_s, state):
    worker, tool = state["workers"][WORKER], state["tools"][METER]
    active = state["active_requests"]
    held = tool["reserved_by"]
    need(worker["request_id"] == held and active == ([held] if held is not None else []),
         "Worker, tool and active request disagree")
    need(worker["location_id"] != "loc_it" and tool["location_id"] != "loc_it"
         and worker.get("travel", {}).get("to_id") != "loc_it", "Forbidden location entered")
    return {"time_s": time_s, "worker_location_id": worker["location_id"], "worker_status": worker["status"],
            "tool_reserved_by": held, "queued": state["queued_requests"]}


def native_transitions(trace):
    transitions = []
    for row in trace:
        state = state_at(row["time_s"], row["domains"]["people_tools_work"])
        need(state["tool_reserved_by"] in (None, "A"), "Rejected B reserved the instrument")
        if not transitions or any(state[key] != transitions[-1][key] for key in state if key != "time_s"):
            transitions.append(state)
    return transitions


def run_isolated_ba(executor, scenario, program):
    parameters = {p["id"]: p["value"] for p in scenario["parameters"]}
    workforce = executor(scenario, parameters, program, DEADLINE)
    clock = 0
    occupations = {key: [] for key in RATES}
    events = []
    while True:
        workforce.process(clock, {"loc_it"})
        events.append(state_at(clock, workforce.snapshot()))
        if clock == DEADLINE:
            break
        end = min(DEADLINE, workforce.next_event(clock))
        need(end > clock, "Executor event clock did not advance")
        rates = workforce.occupation_rates()
        for key in RATES:
            occupations[key].append(rates[key] * (end - clock))
        clock = end
    return {"work_records": workforce.records, "events": events,
            "feedback": workforce.public_feedback(DEADLINE),
            "occupations": {key: math.fsum(values) for key, values in occupations.items()}}


def fields(records):
    keys = ("issued_at_s", "started_at_s", "arrived_at_s", "work_started_at_s", "scheduled_completion_at_s",
            "completed_at_s", "finished_at_s", "reason", "status", "queue_wait_s")
    return {row["id"]: {key: row.get(key) for key in keys} for row in records}


def check_rates(actual, values):
    need(all(math.isclose(actual[key], target, rel_tol=0, abs_tol=1e-9)
             for key, target in zip(RATES, values)), "Occupied time differs from the frozen independent expectations")


def verify(ab, ba, occupations, other_occupations, feedback, other_feedback, transitions, events):
    need(list(ab) == ["A", "B"] and list(ba) == ["B", "A"], "Same-time submission order not preserved")
    need(all(row["issued_at_s"] == 0 for case in (ab, ba) for row in case.values()), "Issue timing mismatch")
    a, b = ab["A"], ab["B"]
    need((a["started_at_s"], a["arrived_at_s"], a["work_started_at_s"], a["completed_at_s"], a["status"])
         == (0, 120.25, 120.25, 150.25, "completed"), "A-first real timestamps differ")
    need((b["status"], b["reason"], b["finished_at_s"], b["started_at_s"], b["arrived_at_s"],
          b["work_started_at_s"], b["completed_at_s"], b["scheduled_completion_at_s"])
         == ("rejected", "shift_or_deadline_unavailable", 150.25, None, None, None, None, None),
         "B must be refused before moving, with no realized completion")
    need([(r["task_id"], r["status"], r["observed_at_s"], r["arrived_at_s"]) for r in feedback]
         == [("A", "completed", 150.25, 150.75), ("B", "rejected", 150.25, 150.75)],
         "A-first feedback timing differs")
    need(transitions[0]["tool_reserved_by"] == "A" and transitions[0]["queued"] == ["B"]
         and transitions[-1]["time_s"] == 150.25 and transitions[-1]["tool_reserved_by"] is None
         and transitions[-1]["queued"] == [], "A-first queue/reservation boundary differs")
    for row, expected in ((ba["B"], (0, 60.25, 60.25, 90.25, 0)),
                          (ba["A"], (90.25, 270.75, 270.75, 300.75, 90.25))):
        need(tuple(row[k] for k in ("started_at_s", "arrived_at_s", "work_started_at_s",
                                    "completed_at_s", "queue_wait_s")) == expected and row["status"] == "completed",
             "B-first executor timestamps differ")
    need([(r["task_id"], r["status"], r["arrived_at_s"]) for r in other_feedback]
         == [("B", "completed", 90.75), ("A", "completed", 301.25)], "B-first feedback differs")
    need(events[0]["tool_reserved_by"] == "B" and events[0]["queued"] == ["A"]
         and any(e["time_s"] == 90.25 and e["tool_reserved_by"] == "A" and e["queued"] == [] for e in events)
         and events[-1]["tool_reserved_by"] is None, "B-first meter handoff differs")
    check_rates(occupations, (120, .25, .25, 0, 0, 30, 150.25, 30))
    check_rates(other_occupations, (240, .75, .75, 0, 0, 60, 300.75, 60))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_root", type=Path)
    parser.add_argument("source_manifest", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    out = args.output_directory
    out.mkdir(exist_ok=False)
    source = load(args.source_manifest)
    counts = {"facility_entries": 0, "completed_native_horizons": 0, "completed_native_seconds": 0,
              "isolated_executor_entries": 0, "registered_research_runs": 0, "policy_calls": 0}
    result = {"status": "ATTEMPT_OPEN", "scope": "39r travel_deadline executor reconciliation",
              "input_git_revision": BASE, "script": identity(Path(__file__)),
              "source_manifest": identity(args.source_manifest), "source_archive_sha256": source["archive_sha256"],
              "inputs": {key: source["files"][key] for key in (V6, NOMINAL, LEDGER, ARITHMETIC)},
              "python": sys.version.split()[0], "budget": {"facility_entries": 1, "isolated_executor_entries": 1},
              "conditions": {"deadline_s": DEADLINE, "native_prefix_s": PREFIX, "native_max_step_s": STEP,
                             "declared_person_budget_s_nonbinding": BUDGET, "forecast_b_completion_ab_s": 360.75},
              "actual_counts": counts, "field_calibration": "PENDING", "service_benefit": "NOT_EVALUATED",
              "private_originals_directory": str(out.resolve())}
    try:
        public, ledger = read_inputs(args.input_root, source)
        from aegis_dc import plant
        from aegis_dc.decision_view import DecisionGateway
        from aegis_dc.scenario import load_scenario
        from aegis_dc.workforce_dispatch import CrewWorkforce, prepare_work
        need(plant.ROOT.resolve() == args.input_root.resolve(), "Imported an unpinned runtime")
        scenario = load_scenario(args.input_root / V6)
        work = programs(public, ledger, DecisionGateway, prepare_work)
        write(out / "programs.json", work)
        result["programs"] = identity(out / "programs.json")
        counts["facility_entries"] = 1
        write(out / "entry-native.json", dict(counts))
        print("Entered the single native V6 A-first prefix", flush=True)
        native = plant.simulate_scenario(scenario, duration_s=PREFIX, step_s=STEP, work_program=work["AB"])
        counts.update(completed_native_horizons=1, completed_native_seconds=native["summary"]["duration_s"])
        manifest = plant.save_run(native, out / "native-AB")
        runtime_files = {key: row["sha256"] for key, row in source["files"].items()
                         if (Path(key).parent.as_posix() == "src/aegis_dc" and key.endswith(".py"))
                         or key == "src/patrol_rsi/contracts.py"}
        need(manifest["code_identity"]["files"] == runtime_files, "Native runtime files differ from pinned Git bytes")
        native_hashes = {name: identity(out / "native-AB" / name) for name in (*manifest["artifacts"], "run.json")}
        need(all(native_hashes[name]["sha256"] == expected["sha256"] for name, expected in manifest["artifacts"].items()),
             "Saved native artifact hash differs")
        ab = fields(native["work_records"])
        transitions = native_transitions(native["trace"])
        occupations = {key: native["summary"][key] for key in RATES}
        feedback = native["workforce_public_feedback"]
        result["native_ab"] = {"tasks": ab, "meter_and_worker": transitions, "occupations": occupations,
                               "feedback": feedback, "source_tree_sha256": manifest["code_identity"]["source_tree_sha256"],
                               "integration_steps": native["summary"]["integration_steps"],
                               "artifacts": native_hashes}
        del native
        print("Saved and hashed the native prefix; checking the reverse order in the executor", flush=True)
        counts["isolated_executor_entries"] = 1
        write(out / "entry-executor.json", dict(counts))
        other = run_isolated_ba(CrewWorkforce, scenario, work["BA"])
        write(out / "executor-BA.json", other)
        ba = fields(other["work_records"])
        result["executor_ba"] = {"tasks": ba, "meter_and_worker": other["events"], "occupations": other["occupations"],
                                 "feedback": other["feedback"], "artifact": identity(out / "executor-BA.json"),
                                 "access_assumption": "The two task routes are open; loc_it is excluded."}
        verify(ab, ba, occupations, other["occupations"], feedback, other["feedback"], transitions, other["events"])
        result["status"] = "PASS"
        print("PASS: native A-first refusal and isolated B-first completion", flush=True)
    except Exception as exc:
        result.update(status="FAIL", failure={"type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        write(out / "result.json", result)


if __name__ == "__main__":
    main()
