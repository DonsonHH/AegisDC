"""Original facility/scorer entry inside the evaluator's one-condition mount."""

import hashlib
import json
import os
from pathlib import Path
import sys

NATIVE = Path("/native/docs/mainline")
CORE = Path("/share/home/renly/renly-patrol-rsi/mainline/V6-cold-launch-release-v1/source")
T3, T4A, T4C, T2 = (NATIVE/n for n in ("t3-prior-information-v2","t4a-public-risk-v1",
                                          "t4c-action-cost-v3","t2-minute-facility-v1"))
sys.path[:0] = [str(T4C),str(T3),str(T4A),str(T2),str(CORE/"src"),str(CORE/"scripts"),"/native/src"]


def packed(v):
    return json.dumps(v, sort_keys=True, separators=(",",":"), ensure_ascii=True, allow_nan=False).encode()


def send(obj):
    sys.stdout.buffer.write(packed(obj)+b"\n")
    sys.stdout.buffer.flush()


def require(v, msg):
    if not v: raise ValueError(msg)


class HardViolation(ValueError):
    pass


def store(name, value):
    with (Path("/out")/name).open("xb") as stream:
        stream.write(packed(value)+b"\n")


def run():
    from native_v3 import native_run
    from run_panel import retain
    from score_saved import score
    from aegis_action_cost.permit import Gate

    input_bytes = Path("/input.json").read_bytes()
    x = json.loads(input_bytes)
    pub = x["native"]["dispatch_program"]["public"]
    gate = Gate(x["maintenance"]["recovery"])
    subjects = {v["id"]:v for v in pub["subjects"]}
    events = []
    send({"public":pub})
    require(json.loads(sys.stdin.buffer.readline()) == {"ready":True}, "public handshake")

    def choose(static, view, role, plan):
        require(static == pub and not plan and view["time"] == len(events)*60, "monotonic public frame")
        send({"view":view})
        choice = json.loads(sys.stdin.buffer.readline())
        issued = choice["request"]
        if issued:
            real, why = gate.admit(pub,view,subjects[issued["subject"]],issued["phase"],issued["patrol_slot"])
            # The original physical adapter itself also performs the final gate at issue.
            if not ((real == issued and why == "ALLOW") or (real is None and why == "MAINTENANCE_CHANGE_BUSY")):
                raise HardViolation("issued public gate mismatch")
        events.append([view["time"],hashlib.sha256(packed(view)).hexdigest(),hashlib.sha256(packed(choice)).hexdigest()])
        return choice

    entry={"input":hashlib.sha256(input_bytes).hexdigest(),"facility_calls":1}
    send({"begin":entry["input"]})
    require(json.loads(sys.stdin.buffer.readline())=={"proceed":True},"durable native reservation")
    store("native-entry.json",entry)
    label=sys.argv[1]
    require(label in ("V_COST","T8"),"unknown evaluated role")
    result, term = native_run(x,label,{},(),decider=choose)
    raw = Path("/out/native.jsonl.gz")
    retain(raw,result,term)
    require(result["v3_received_maintenance"]==x["maintenance"] and not result["t3_unpurchased_evaluator_only"],
            "maintenance or evaluator-only diagnostic identity")
    measured = score(x,result,term,label)
    require(len(events) == measured["clocks"] == 61 and result["v3_received_maintenance"] == x["maintenance"] and
            not result["t3_unpurchased_evaluator_only"], "physical interface identity")
    require(events == [[e["at"],e["view"],e["proposal"]] for e in result["v3_proposals"]], "IPC transcript identity")
    require(measured["runtime"] == "67db74467194edf547cc7994a702019fa4040b8aa1cebf1eaa33574327b7b735",
            "native code identity")
    writes = [d["decision"]["request"] for d in result["policy_public_decisions"]
              if d["decision"]["request"] and d["decision"]["request"]["phase"] == "A"]
    if not all(b["at"] >= a["planned_end"] + x["maintenance"]["recovery"] for a,b in zip(writes,writes[1:])):
        raise HardViolation("overlapping original maintenance")
    with raw.open("rb") as stream: raw_hash = hashlib.file_digest(stream,"sha256").hexdigest()
    # Select the exact numeric JSON tokens produced by the original scorer before rounding.
    saved = {k:measured[k] for k in ("L","U","person","tool","fee","clocks","runtime","integral_balances")}
    saved.update(raw_sha256=raw_hash, public_transcript=hashlib.sha256(packed(events)).hexdigest(), hard_violations=0)
    store("score.json",saved)
    tokens = json.loads((Path("/out")/"score.json").read_bytes(), parse_float=str,parse_int=str)
    send({"complete":True,"L":tokens["L"],"person":tokens["person"],"hard_violations":0,
          "public_transcript":saved["public_transcript"]})


if __name__ == "__main__":
    os.umask(0o022)
    if sys.argv[1:] == ["--imports"]:
        from native_v3 import native_run
        from run_panel import retain
        from score_saved import score
        from aegis_dc.source_identity import runtime_source_identity
        send({"native_interface_available":True,"native_tree":runtime_source_identity(CORE),"facility_calls":0})
        sys.exit(0)
    try:
        run()
    except Exception as failure:
        store("failure.json", {"exception_type":type(failure).__name__, "reason":str(failure),
                              "hard_violation":True if isinstance(failure, HardViolation) else None})
        raise
