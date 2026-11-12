"""Screen two fixed orders using pinned V6 configuration and declared fixtures."""

import argparse
import hashlib
import json
from pathlib import Path


def identity(path):
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def source_inputs(root, spec):
    found = {}
    for key, item in spec["inputs"].items():
        path = root / item["path"]
        require(identity(path) == {k: item[k] for k in ("bytes", "sha256")}, f"Input changed: {key}")
        found[key] = load(path)
    return found


def project(spec, inputs):
    scenario = inputs["v6"]
    profile = inputs["timing_case"]["public_static"]["workforce_profile"]
    require(scenario["id"] == spec["facility_id"] == profile["facility_id"], "Wrong facility")
    require(profile["id"] == spec["timing_profile_id"] and profile["time_unit"] == "s", "Wrong timing profile")
    entities = {e["id"]: e for e in scenario["entities"]}
    interfaces = {i["id"]: i for d in scenario["domains"] for i in d["work_interfaces"]}
    access = {e["id"]: e for e in scenario["graphs"]["access"]}
    parameters = {p["id"]: p for p in scenario["parameters"]}
    worker, tool = (entities[spec[key]] for key in ("worker_id", "tool_id"))
    release = spec["declared_assumptions"]["release_s"]
    require(worker["kind"] == "worker" and tool["kind"] == "tool", "Wrong resource kind")
    require(worker["location_id"] == tool["location_id"] == spec["start_location"], "Resources must be colocated")
    require(spec["declared_assumptions"]["worker_and_tool_available_at_release"], "Resources must be available")
    require(tool["id"] in worker["tool_ids"], "Worker cannot use shared tool")
    shift = profile["shifts"][worker["id"]]
    require(shift == [0, parameters["shift_end_time"]["value"]] and shift[0] <= release < shift[1], "Shift mismatch")
    qualification = spec["qualification_id"]
    require(qualification in worker["qualification_ids"], "Missing worker qualification")
    tasks = {}
    for key, task in spec["tasks"].items():
        interface, entity = interfaces[task["interface_id"]], entities[task["target_id"]]
        require(entity["id"] in interface["target_ids"], "Target not in registered interface")
        require(interface["qualification_id"] == qualification and interface["tool_ids"] == [tool["id"]]
                and interface["specialty"] in worker["specialties"] and interface["specialty"] in tool["specialties"],
                "The interfaces do not share the declared resources")
        duration = parameters[interface["duration_parameter"]]
        work = profile["work_times_s"][interface["id"]]
        require(duration["unit"] == "s" and work == duration["value"] > 0, "Work duration mismatch")
        location = entity["id"] if entity["kind"] == "location" else entity["location_id"]
        tasks[key] = {**task, "location": location, "work_s": work, "work_parameter": duration["id"]}
    check = profile["access_check_s"]
    require(check > 0, "Access check must take positive time")
    routes = {}
    for name, ids in spec["routes"].items():
        src, dest = name.split("_to_")
        loc = spec["start_location"] if src == "start" else tasks[src]["location"]
        legs = []
        for edge_id in ids:
            edge = access[edge_id]
            require(edge_id in spec["declared_assumptions"]["authorized_access_edges"], "No route authorization")
            require(set(edge["requires_qualification_ids"]) <= set(worker["qualification_ids"]), "Unqualified route")
            if edge["from"] == loc:
                next_location = edge["to"]
            else:
                require(edge["bidirectional"] and edge["to"] == loc, "Noncontiguous or reversed directed route")
                next_location = edge["from"]
            require(not {loc, next_location}.intersection(spec["excluded_locations"]), "Route enters excluded location")
            duration = parameters[edge["duration_parameter"]]
            walk = profile["walk_times_s"][edge_id]
            require(duration["unit"] == "s" and walk == duration["value"] > 0, "Walk duration mismatch")
            legs.append({"edge": edge_id, "from": loc, "to": next_location, "walk_s": walk,
                         "access_check_s": check, "walk_parameter": duration["id"]})
            loc = next_location
        require(legs and loc == tasks[dest]["location"], "Route does not end at the task")
        routes[name] = legs
    return {"release_s": release, "shift_end_s": shift[1], "tasks": tasks, "routes": routes,
            "worker_id": worker["id"], "tool_id": tool["id"], "start_location": worker["location_id"],
            "qualification_id": qualification, "timing_profile_id": profile["id"]}


def screen(model, case, order):
    t = model["release_s"]
    occupied = {"walk": 0, "access_check": 0, "permit_wait": 0, "work": 0}
    schedule, reasons = {}, []
    previous = "start"
    for key in order:
        task = model["tasks"][key]
        legs = model["routes"][f"{previous}_to_{key}"]
        walk = sum(leg["walk_s"] for leg in legs)
        check = sum(leg["access_check_s"] for leg in legs)
        arrive = t + walk + check
        permit = case["permit_from_s"][key]
        deadline = case["deadline_s"][key]
        record = {"departure_s": t, "arrival_after_access_checks_s": arrive,
                  "route": [leg["edge"] for leg in legs], "permit_from_s": permit, "deadline_s": deadline,
                  "start_s": None, "finish_s": None, "permit_wait_s": None}
        schedule[key] = record
        if permit is None:
            return {"status": "UNKNOWN", "reasons": [*reasons, f"WORK_PERMIT_UNKNOWN:{key}"],
                    "schedule": schedule, "person_s": None, "tool_s": None, "person_breakdown_s": None}
        start = max(arrive, permit)
        finish = start + task["work_s"]
        wait = start - arrive
        record.update(start_s=start, finish_s=finish, permit_wait_s=wait)
        occupied["walk"] += walk
        occupied["access_check"] += check
        occupied["permit_wait"] += wait
        occupied["work"] += task["work_s"]
        if finish > deadline:
            reasons.append(f"DEADLINE:{key}")
        if finish > model["shift_end_s"]:
            reasons.append(f"SHIFT_END:{key}")
        t, previous = finish, key
    person = sum(occupied.values())
    tool = t - model["release_s"]
    require(person == tool, "Shared occupation accounting mismatch")
    if person > case["person_budget_s"]:
        reasons.append("PERSON_BUDGET")
    return {"status": "INFEASIBLE" if reasons else "FEASIBLE", "reasons": reasons,
            "schedule": schedule, "person_s": person, "tool_s": tool, "person_breakdown_s": occupied}


def compare(model, case):
    orders = {o: screen(model, case, o) for o in ("AB", "BA")}
    accepted = [o for o, row in orders.items() if row["status"] == "FEASIBLE"]
    if any(row["status"] == "UNKNOWN" for row in orders.values()):
        verdict = "INSUFFICIENT_EVIDENCE"
    else:
        verdict = ("NEITHER_FEASIBLE", "ONE_ORDER_FEASIBLE", "BOTH_FEASIBLE")[len(accepted)]
    single = {k: screen(model, case, k)["status"] for k in ("A", "B")}
    return {**case, "verdict": verdict, "feasible_orders": accepted, "orders": orders, "single_tasks": single}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    protocol = Path(__file__).with_name("protocol.json")
    spec = load(protocol)
    model = project(spec, source_inputs(args.input_root, spec))
    cases = [compare(model, case) for case in spec["cases"]]
    result = {"status": spec["scope"], "protocol_id": spec["id"], "protocol": identity(protocol),
              "script": identity(Path(__file__)), "input_git_revision": spec["input_git_revision"],
              "inputs": spec["inputs"], "model": model, "cases": cases,
              "new_facility_runs": 0, "new_policy_calls": 0, "registered_research_runs": 0,
              "service_benefit": "NOT_EVALUATED", "field_calibration": "PENDING"}
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({c["id"]: [c["verdict"], c["feasible_orders"]] for c in cases}))


if __name__ == "__main__":
    main()
