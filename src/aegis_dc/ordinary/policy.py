"""Frozen 4182f423 grammar. The only online inputs are the name and a detached v2 view."""
from fractions import Fraction

from aegis_dc.london_e14 import ACQUISITION_PLAN_FIELDS, READS
from aegis_dc.london_treatments import choose, fix_feasibility, make_request, validate_view

POS, VOLT, CONFIG = READS
FIX, VERIFY = "FIX_CTRL", "VERIFY_CTRL"
CATALOG = ("C全续", "C早止", "V早续", "C早续", "C全止", "V全止", "V早止")
HUMAN = CATALOG[0]
RANK = ("I", "D", *CATALOG)
SEARCH = CATALOG[:3]
DIAGNOSTIC = "ENGINEERING_POS_DIRECT"
ENGINEERING = "PUBLIC_ENGINEERING_ONLY"
SURROGATE = "ENGINEERING_SURROGATE"
STUDY = "ORDINARY_V2_RESEARCH"
TARGET = {POS: "feeder-B", VOLT: "feeder-B", CONFIG: "ctrl-1", VERIFY: "ctrl-1"}
SOURCE = {POS: "pos-B", VOLT: "volt-B", CONFIG: "cfg-local", VERIFY: "probe-local"}
SUPPORT = {POS: 0, VOLT: 1, CONFIG: "LEGACY_LINE"}
NEGATIVE = {POS: 1, VOLT: 0, CONFIG: "REVISED_LOCAL"}


class ContractError(ValueError):
    """A technical contract violation, distinct from a lawful unsuccessful action."""


def descriptor(name, purpose):
    if name in CATALOG or name in ("I", "D", "P"):
        return name
    if name == DIAGNOSTIC and purpose == ENGINEERING:
        return name
    raise ContractError("Unknown or out-of-purpose descriptor")


def order(name):
    return (POS, CONFIG, VOLT) if name.startswith("C") else (POS, VOLT, CONFIG)


def validate_public(view):
    validate_view(view)
    plans = view["context"]["acquisition_plans"]
    if set(plans) != {*READS, VERIFY}:
        raise ContractError("Invalid acquisition plan set")
    for plan in plans.values():
        if set(plan) != ACQUISITION_PLAN_FIELDS or type(plan["admissible"]) is not bool:
            raise ContractError("Invalid public acquisition fields")
        if plan["admissible"] != (plan["reason"] == "ADMITTED"):
            raise ContractError("Inconsistent public acquisition admission")
    if set(view["context"]["permissions"]) != {"read", "propose", "verify", "direct"}:
        raise ContractError("Invalid public permissions")
    # History and receipts are data, never a secondary feature interface.
    def private_keys(value):
        if isinstance(value, dict):
            if {"work_mode", "calendar", "slot", "panel", "condition_id", "case_id",
                "input_hash", "source_sha256", "next_event", "private"} & value.keys():
                raise ContractError("Private input in public envelope")
            for child in value.values():
                private_keys(child)
        elif isinstance(value, list):
            for child in value:
                private_keys(child)
    private_keys(view)


def original(row, action, now):
    return (row.get("record_kind") == "ACTION_RESULT" and row.get("action") == action
            and not row.get("copy_of") and row.get("problem_id") == "q-1"
            and row.get("maintenance_epoch") == "m0" and row.get("receiver_role") == "AUDITOR"
            and row.get("target") == TARGET[action] and row.get("source_group") == SOURCE[action]
            and bool(row.get("record_id")) and bool(row.get("request_id"))
            and Fraction(row["observed_at"]) <= Fraction(row["available_at"]) <= now)


class Evidence:
    def __init__(self, view):
        now = Fraction(view["time"])
        self.current = {}
        self.settled = set()
        for action in READS:
            if any(original(r, action, now) for r in view["history"]):
                self.settled.add(action)
            rows = [r for r in view["records"] if original(r, action, now)
                    and r["status"] == "KNOWN" and now < Fraction(r["expires_at"])
                    and (action != CONFIG or (view["known_epoch"] is not None
                         and r["config_epoch"] == view["known_epoch"]))]
            if not rows:
                continue
            values = {(type(r["value"]), r["value"]) for r in rows}
            if len(values) != 1 or not values.issubset({
                    (type(SUPPORT[action]), SUPPORT[action]), (type(NEGATIVE[action]), NEGATIVE[action])}):
                continue
            self.current[action] = min(rows, key=lambda r: (-Fraction(r["available_at"]), r["record_id"]))

    def supported(self, action):
        return action in self.current and self.current[action]["value"] == SUPPORT[action]

    def negative(self, action):
        return action in self.current and self.current[action]["value"] == NEGATIVE[action]

    def unknown_attempts(self, view):
        return {a for a in READS if a in view["attempted"] and a not in self.current}


def execution_receipt(view):
    for row in reversed(view["receipts"]):
        if (row.get("record_kind") == "EXECUTION_RECEIPT" and row.get("status") == "EXECUTED_UNVERIFIED"
                and row.get("problem_id") == "q-1" and row.get("target") == "ctrl-1"
                and row.get("receiver_role") == "AUDITOR" and row.get("action") == FIX
                and row.get("execution_id") and row.get("target_config_epoch") is not None
                and Fraction(row["available_at"]) <= Fraction(view["time"])):
            return row
    return None


def verified(view):
    parent = execution_receipt(view)
    if not parent or not view["pre_open"]:
        return False
    now = Fraction(view["time"])
    return any(original(r, VERIFY, now) and now < Fraction(r["expires_at"])
               and r["status"] == "VERIFIED_FOR_TARGET" and r["value"] == "PASS"
               and r["parent_execution_id"] == parent["execution_id"]
               and r["config_epoch"] == parent["target_config_epoch"] for r in view["records"])


def readable(view, action):
    c = view["context"]
    return (c["read_parameters_known"] and c["permissions"]["read"] == "ALLOW"
            and (action != VERIFY or c["permissions"]["verify"] == "ALLOW")
            and c["acquisition_plans"][action]["admissible"])


def early_allowed(name, view, evidence):
    first, second, last = order(name)
    if (set(view["attempted"]) != {first, second} or not evidence.supported(first)
            or not evidence.supported(second) or last in evidence.current
            or not readable(view, last) or fix_feasibility(view, "DIRECT")):
        return False
    c = view["context"]
    plan = c["acquisition_plans"][last]
    delay = Fraction(plan["available_at"]) - Fraction(view["time"])
    residual = Fraction(c["available"]) - Fraction(plan["work"])
    end = Fraction(c["window"][1])
    publish_margin = end - Fraction(c["chain_finish"]) - delay
    resource_margin = end - Fraction(c["chain_resource_end"]) - delay
    return (residual >= Fraction(c["chain_reserve"]) and publish_margin > 0
            and resource_margin >= 0 and min(publish_margin, resource_margin) < Fraction(plan["exit_reserve"]))


def output(action, mode=None, reason=None):
    return {"action": action, "mode": mode, "reason": reason or action}


def act(name, view, *, purpose=STUDY):
    descriptor(name, purpose)
    validate_public(view)
    if not view["pre_open"]:
        raise ContractError("Environment cutoff precedes policy invocation")
    if name in ("I", "D", "P"):
        return choose(name, view)
    if view["terminal_failure"]:
        return output("STOP_UNRESOLVED")
    if view["pending"]:
        return output("WAIT_PENDING")
    if verified(view):
        return output("NO_ACTION_CURRENT_SCOPE", reason="VERIFIED")
    if view["phase"] == "AWAITING_VERIFY":
        if VERIFY in view["attempted"]:
            return output("STOP_UNRESOLVED")
        if execution_receipt(view) and readable(view, VERIFY):
            return output(VERIFY)
        return output("INSUFFICIENT_INFORMATION")
    if FIX in view["attempted"]:
        return output("STOP_UNRESOLVED")
    evidence = Evidence(view)
    if any(evidence.negative(a) for a in READS):
        return output("NO_ACTION_CURRENT_SCOPE", reason="NEGATIVE")
    if all(evidence.supported(a) for a in READS):
        blocked = fix_feasibility(view, "EVIDENCE")
        return output(blocked) if blocked else output("PROPOSE_FIX", "EVIDENCE")
    unknown = evidence.unknown_attempts(view)
    if unknown - evidence.settled:
        return output("INSUFFICIENT_INFORMATION", reason="NO_ORIGINAL")
    if unknown and name.endswith("止"):
        return output("INSUFFICIENT_INFORMATION", reason="SETTLED_UNKNOWN")
    if name == DIAGNOSTIC:
        if set(view["attempted"]) == {POS} and evidence.supported(POS):
            blocked = fix_feasibility(view, "DIRECT")
            return output(blocked) if blocked else output("PROPOSE_FIX", "DIRECT")
        if POS not in view["attempted"] and readable(view, POS):
            return output(POS)
        return output("INSUFFICIENT_INFORMATION")
    if name[1] == "早" and early_allowed(name, view, evidence):
        return output("PROPOSE_FIX", "DIRECT", "PUBLIC_CHAIN_MARGIN")
    for action in order(name):
        if action not in evidence.current and action not in view["attempted"] and readable(view, action):
            return output(action)
    return output("INSUFFICIENT_INFORMATION")


def request_for(name, decision, view, index):
    payload = make_request(decision, view, index)
    if name in CATALOG and decision["mode"] == "EVIDENCE":
        evidence = Evidence(view)
        payload["evidence_ids"] = [evidence.current[a]["record_id"] for a in READS]
    if payload["action"] == VERIFY:
        parent = execution_receipt(view)
        if not parent or (payload["execution_id"], payload["target_config_epoch"]) != (
                parent["execution_id"], parent["target_config_epoch"]):
            raise ContractError("Invalid verification parent")
    return payload
