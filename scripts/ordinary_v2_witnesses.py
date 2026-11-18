"""Engineering-only ledger witnesses. Surrogate callbacks cannot construct a facility."""
from copy import deepcopy
from pathlib import Path

from aegis_dc.ordinary.archive import Journal, digest, save
from aegis_dc.ordinary.feedback import extract_paid
from aegis_dc.ordinary.ledger import PaidStudy, RowCache, Tickets, collect, Stopped, NoReturn, COUNT_KEYS
from aegis_dc.ordinary.policy import ContractError, CATALOG, STUDY, descriptor
from ordinary_v2_fixture_io import base_fixture


def differences(actual, expected):
    # JSON distinguishes bool from integer and preserves list order.
    return [key for key in sorted(expected.keys() | actual.keys())
            if key not in expected or key not in actual or digest(actual[key]) != digest(expected[key])]


def feedback_case(f,case,log):
    tickets=Tickets(log)
    for group in case["paid_by"]:
        tickets.pay(group,case["descriptor"])
    panels,rows=base_fixture(f,case["rows"])
    for key in case["missing_keys"]:
        del rows[key]
    try:
        return {"bits":extract_paid(tickets,case["group"],case["descriptor"],rows,panels)}
    except ContractError as exc:
        log.event("feedback_refused",unit=case["id"],error=repr(exc))
        return {"status":"REJECT"}


def ledger_case(f, case, output, log, episodes, expected_episodes):
    op=case["op"]; inp=case["input"]
    panels,default=base_fixture(f)
    counters=dict.fromkeys(COUNT_KEYS,0)
    if op=="three_rounds":
        namespace=dict(f["cache_identity"], instance=case["id"])
        engine=PaidStudy(output/"sessions"/case["id"],namespace,panels,{k:digest(k) for k in panels.keys})
        bits={n:inp["flags"].get(n,inp["flags"]["default"]) for n in CATALOG}
        def fake(name,key):
            return {"counts":counters,"row":deepcopy(default[key])}
        reports=engine.run(fake,surrogate_feedback=bits)
        return dict(U0=engine.tickets.paid["U0"],SEARCH=engine.tickets.paid["SEARCH"],
                    paid=len(reports),cold_columns=sum(x["started"]>0 for x in engine.accounting),
                    logical_rows=sum(x["paid_rows"] for x in reports),
                    physical_stub_rows=sum(x["started"] for x in engine.accounting),
                    locks=[reports[-2]["selection"]["lock"],reports[-1]["selection"]["lock"]])
    if op=="rank":
        columns={name:base_fixture(f,rows)[1] for name,rows in inp["columns"].items()}
        return panels.lock(columns)
    if op=="cache_mismatch":
        cache=RowCache(output/"cache-guards"/case["id"],f["cache_identity"])
        key=cache.key(inp["key"],digest(inp["key"]),inp["descriptor"])
        wrong=dict(key);wrong[inp["field"]]=inp["value"]
        row=default[inp["key"]]
        save(cache.path(key),dict(identity=wrong,row=row,sha256=digest(row)))
        try:
            cache.read(key)
        except ContractError:
            return {"status":"REJECT","delivered":False}
        return {"status":"ACCEPT","delivered":True}
    if op=="repeat_ticket":
        tickets=Tickets(log)
        tickets.pay(inp["group"],inp["descriptor"])
        try:
            tickets.pay(inp["group"],inp["descriptor"])
        except ContractError:
            return dict(status="REJECT",paid=len(tickets.paid[inp["group"]]))
        return dict(status="ACCEPT",paid=len(tickets.paid[inp["group"]]))
    if op in ("normal_failure","fault"):
        tickets=Tickets(log);tickets.pay("U0","C全续")
        keys=inp["keys"]; fault=inp.get("fault")
        def callback(key):
            if fault=="NO_RETURN":
                raise NoReturn("Frozen no-return surrogate")
            raw={"row":dict(default[key],stage=inp.get("statuses",["DIAGNOSTIC"]*len(keys))[keys.index(key)])}
            if fault!="MISSING_COUNTS":
                raw["counts"]=counters
            return raw
        def archive(key,raw):
            if fault=="RAW_ARCHIVE_ERROR":
                raise OSError("Frozen raw-writer failure")
            save(output/"faults"/case["id"]/(key+".json"),raw)
        try:
            rows,state=tickets.collect("U0","C全续",keys,callback,archive,log)
            if set(rows)!=set(keys):
                raise ContractError("Lost a failed process row")
            return {k:state[k] for k in ("started","returned","pending","status","suffix")}
        except Stopped as exc:
            try:
                tickets.require_paid("U0","C全续")
                exposed=True
            except ContractError:
                exposed=False
            state=exc.record
            result={k:state[k] for k in ("started","returned","pending","unknown","status","suffix")}
            return dict(result,paid=len(tickets.paid["U0"]),exposed=exposed)
    if op=="oracle_mutation":
        actual=deepcopy(episodes[inp["unit"]])
        if "append_request" in inp:
            actual["requests"].append(inp["append_request"])
        actual.update(inp.get("override",{}))
        return {"mismatch":differences(actual,expected_episodes[inp["unit"]])}
    if op=="descriptor_rejection":
        try:
            purpose = STUDY if inp["purpose"] == "STUDY" else inp["purpose"]
            descriptor(inp["descriptor"],purpose)
        except ContractError:
            return dict(status="REJECT",constructors=0)
        return dict(status="ACCEPT",constructors=0)
    raise ContractError("Unknown fixture operation")
