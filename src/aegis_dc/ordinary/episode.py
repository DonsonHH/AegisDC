"""One descriptor, one isolated worker, one fresh facility. Only the evaluator owns it."""
import multiprocessing
import os
import json
import traceback
from copy import deepcopy
from pathlib import Path

from aegis_dc.london_e14 import E14Run
from aegis_dc.london_treatment_score import score_arm
from aegis_dc.london_treatments import reached_stage, validate_config
from . import policy
from .archive import Journal, digest, load, save

STOP = {"STOP", "STOP_UNRESOLVED", "NO_ACTION_CURRENT_SCOPE", "INFEASIBLE",
        "INSUFFICIENT_INFORMATION", "NO_NEW_ACTIONS"}
REFUSALS = {"ACCESS_DENIED", "BUDGET_UNAVAILABLE", "NOT_STARTED_RESOURCE",
            "WINDOW_UNAVAILABLE", "INSUFFICIENT_INFORMATION", "PRE_CLOSED"}
LIMITS = {"constructor": 1, "plant": 30, "policy": 20, "request": 5, "scorer": 1}
RESOURCE = {"within_budget", "external_reservations_clear", "reserved_exit_honored"}


class Bindings:
    """Only publications on this facility port can attest this instance's requests."""
    def __init__(self, source):
        self.source = source
        self.requests = {}
        self.publications = {}

    def admitted(self, payload):
        rid = payload["request_id"]
        if rid in self.requests:
            raise policy.ContractError("Duplicate request identity")
        self.requests[rid] = deepcopy(payload)

    def receive(self, source, view):
        if source is not self.source:
            raise policy.ContractError("Foreign facility publication")
        for row in [*view["receipts"], *view["history"], *view["records"]]:
            req = self.requests.get(row["request_id"])
            if not req or (req["action"], req["target"]) != (row["action"], row["target"]):
                raise policy.ContractError("Publication without local admitted request")
            kind = row["record_kind"]
            key = (kind, row.get("record_id", row["request_id"]))
            if key in self.publications and self.publications[key] != row:
                raise policy.ContractError("Published identity changed")
            if kind == "ACTION_RESULT" and req["action"] == policy.VERIFY:
                if (req.get("execution_id"), req.get("target_config_epoch")) != (
                        row["parent_execution_id"], row["config_epoch"]):
                    raise policy.ContractError("Observation parent differs from admitted VERIFY")
            self.publications[key] = deepcopy(row)
        return deepcopy(view)

    def check_payload(self, payload):
        if payload.get("mode") == "EVIDENCE":
            if any(("ACTION_RESULT", rid) not in self.publications for rid in payload["evidence_ids"]):
                raise policy.ContractError("Evidence was not published on this port")
        if payload["action"] == policy.VERIFY:
            if not any(row.get("status") == "EXECUTED_UNVERIFIED"
                       and (row.get("execution_id"), row.get("target_config_epoch")) ==
                       (payload["execution_id"], payload["target_config_epoch"])
                       for row in self.publications.values()):
                raise policy.ContractError("Unbound execution receipt")


class CountedCalls:
    def __init__(self, journal):
        self.journal = journal
        self.counts = dict.fromkeys(LIMITS, 0)
        self.pending = set()

    def call(self, kind, method, inputs, fn, *args, **kwargs):
        names = [kind, "request"] if kind == "plant" and method == "request" else [kind]
        if any(self.counts[n] >= LIMITS[n] for n in names):
            raise policy.ContractError("Per-episode call limit")
        cid = self.journal.event("intent", kind=kind, method=method, inputs=inputs)
        self.pending.add(cid)
        for n in names:
            self.counts[n] += 1
        try:
            value = fn(*args, **kwargs)
        except Exception as exc:
            self.journal.event("raised", call=cid, error=repr(exc))
            self.pending.remove(cid)
            raise
        stored = {"class": type(value).__name__} if kind == "constructor" else value
        self.journal.event("return", call=cid, value=stored)
        self.pending.remove(cid)
        return value


def evaluate(config, name, purpose, parent_pid, origin, calls):
    policy.descriptor(name, purpose)
    validate_config(config)
    frozen = deepcopy(config)
    model = calls.call("constructor", "E14Run", frozen, E14Run, deepcopy(frozen))
    bindings = Bindings(model)
    def plant(method, *args):
        return calls.call("plant", method, list(args), getattr(model, method), *args)

    initial = plant("audit")
    run = {"arm": name, "public_trace": [], "requests": [], "stop": None, "errors": []}
    for tick in range(21):
        public = plant("public_view") if tick == 0 else plant("advance", tick)
        view = bindings.receive(model, public)
        if not view["pre_open"]:
            run["stop"] = {"reason": "ENV_PRE_CUTOFF", "time": tick}
            break
        decision = calls.call("policy", "act", {"descriptor": name, "view": view},
                              policy.act, name, deepcopy(view), purpose=purpose)
        frame = {"time": tick, "view": view, "decision": decision, "payload": None, "reply": None}
        run["public_trace"].append(frame)
        action = decision["action"]
        if action == "WAIT_PENDING":
            continue
        if action in STOP:
            run["stop"] = {"reason": action, "time": tick}
            break
        payload = policy.request_for(name, decision, view, len(run["requests"]) + 1)
        bindings.check_payload(payload)
        if any(r["payload"]["action"] == payload["action"] for r in run["requests"]):
            raise policy.ContractError("Repeated action")
        reply = plant("request", payload)
        frame.update(payload=payload, reply=reply)
        run["requests"].append(dict(time=tick, payload=payload, reply=reply,
                                    frame_index=len(run["public_trace"])-1))
        if reply["status"] != "ADMITTED":
            if reply["status"] not in REFUSALS:
                raise policy.ContractError("Invalid technical request: " + reply["status"])
            run["stop"] = dict(reason="REQUEST_REJECTED", time=tick, request_status=reply["status"])
            break
        bindings.admitted(payload)
    if run["stop"] is None:
        raise policy.ContractError("Missing stop")
    checkpoint = plant("audit")
    if checkpoint["time"] < 20:
        plant("advance", 20)
    final = plant("audit")
    isolated = (parent_pid == os.getppid() and parent_pid != os.getpid()
                and initial["time"] == 0 and not initial["observations"] and not initial["receipts"]
                and not initial["operations"] and frozen == config == initial["original_input"] == final["original_input"]
                and initial["state_identity"] == final["state_identity"] and bindings.source is model)
    score = calls.call("scorer", "score_arm", {"input": digest(frozen), "final": digest(final),
                       "run": digest(run), "isolation": isolated}, score_arm, final, run, isolated, frozen)
    if score["trace_status"] != "COMPLETE" or any(not v for k,v in score["hard_constraints"].items() if k not in RESOURCE):
        raise policy.ContractError("Incomplete score or technical constraint failure")
    last = run["public_trace"][-1] if run["public_trace"] else None
    closed = any(policy.verified(f["view"]) for f in run["public_trace"])
    if last and run["stop"]["reason"] == "NO_ACTION_CURRENT_SCOPE":
        evidence = policy.Evidence(last["view"])
        closed |= any(evidence.negative(a) for a in policy.READS)
    return dict(origin=origin, purpose=purpose, descriptor=name, initial=initial, run=run, checkpoint=checkpoint,
                final=final, reached=reached_stage(final,run), score=score, closed=closed,
                isolation=dict(worker=os.getpid(), parent=parent_pid, passed=isolated,
                               accepted_publications=len(bindings.publications)), counts=calls.counts.copy())


def _worker(condition, name, purpose, parent_pid, origin, destination):
    dest = Path(destination)
    log = Journal(dest/"calls.jsonl")
    calls = CountedCalls(log)
    try:
        raw = evaluate(condition, name, purpose, parent_pid, origin, calls)
        save(dest/"raw.json", raw)
        save(dest/"terminal.json", dict(status="COMPLETE", counts=calls.counts, pending=[], raw=digest(raw)))
    except BaseException:
        save(dest/"terminal.json", dict(status="ERROR", counts=calls.counts, pending=sorted(calls.pending),
                                        error=traceback.format_exc()))
        raise
    finally:
        log.close()


def run_isolated(condition, name, purpose, origin, destination):
    name = policy.descriptor(name, purpose)
    if purpose not in (policy.ENGINEERING,policy.STUDY) or not os.environ.get("SLURM_JOB_ID"):
        raise policy.ContractError("Isolated facilities require an allocated engineering or authorized study job")
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=False)
    save(dest/"intent.json", dict(purpose=purpose, origin=origin, descriptor=name, condition=condition))
    proc = multiprocessing.get_context("spawn").Process(
        target=_worker,args=(condition,name,purpose,os.getpid(),origin,str(dest)))
    proc.start()
    proc.join()
    if not (dest/"terminal.json").is_file():
        from .ledger import NoReturn
        subtotal = dict.fromkeys(LIMITS,0)
        logfile = dest/"calls.jsonl"
        if logfile.exists():
            for line in logfile.read_bytes().splitlines():
                try:
                    rec = json.loads(line)
                except ValueError:
                    break
                if rec["event"] == "intent":
                    subtotal[rec["kind"]] += 1
                    if rec["kind"] == "plant" and rec["method"] == "request":
                        subtotal["request"] += 1
        raise NoReturn(f"Worker {proc.pid} has no durable return; exit {proc.exitcode}",subtotal)
    terminal = load(dest/"terminal.json")
    if proc.exitcode != 0:
        from .ledger import WorkerFailure
        raise WorkerFailure(terminal)
    raw = load(dest/"raw.json")
    if terminal["status"] != "COMPLETE" or terminal["raw"] != digest(raw) or terminal["pending"]:
        raise policy.ContractError("Unreconciled isolated worker")
    return raw


def outcome(raw):
    score = raw["score"]
    return dict(z=[score[k] for k in ("L","U","person_seconds","tool_seconds")],
                violations=sorted(k for k in RESOURCE if not score["hard_constraints"][k]),
                closed=raw["closed"], frames=raw["run"]["public_trace"], requests=raw["run"]["requests"],
                work_by_action=score["work_by_action"], complete=score["trace_status"] == "COMPLETE")
