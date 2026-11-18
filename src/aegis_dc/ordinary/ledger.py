"""Paid queries and append-only raw storage. A missing internal count never funds a retry."""
from copy import deepcopy
from pathlib import Path
from time import process_time
from .archive import Journal, digest, load, save
from .feedback import extract_paid
from .policy import CATALOG, STUDY, SURROGATE, ContractError
from .selection import next_candidate

COUNT_KEYS = ("constructor", "plant", "policy", "request", "scorer")


class NoReturn(RuntimeError):
    """The underlying worker has no proved terminal return."""

    def __init__(self, message, subtotal=None):
        super().__init__(message)
        self.subtotal = subtotal or {}


class WorkerFailure(RuntimeError):
    def __init__(self, receipt):
        super().__init__(receipt.get("error","Worker returned an error terminal"))
        self.receipt = receipt


class Stopped(RuntimeError):
    def __init__(self, record):
        self.record = record
        super().__init__(record["error"])


class Tickets:
    def __init__(self, journal):
        self.journal = journal
        self.paid = {"U0": [], "SEARCH": []}
        self.stopped = False

    def pay(self, group, name):
        if (self.stopped or group not in self.paid or name not in CATALOG
                or name in self.paid[group] or len(self.paid[group]) >= 3):
            raise ContractError("Repeated, exhausted, stopped or invalid query")
        self.journal.event("ticket", group=group, descriptor=name, ticket=len(self.paid[group])+1,
                           prior=list(self.paid[group]))
        self.paid[group].append(name)

    def require_paid(self, group, name):
        if self.stopped or name not in self.paid.get(group, ()):
            raise ContractError("Feedback access without own paid complete query")

    def stop(self, group, name, exc):
        if not self.stopped:
            self.stopped = True
            self.journal.event("query_stopped",group=group,descriptor=name,error=repr(exc),
                               known_paid=self.paid,partial_feedback_released=False)

    def collect(self, group, name, *args, **kwargs):
        self.require_paid(group,name)
        try:
            return collect(*args, **kwargs)
        except Exception as exc:
            self.stop(group,name,exc)
            raise


class RowCache:
    def __init__(self, root, identity):
        if identity.get("purpose") not in (STUDY,SURROGATE):
            raise ContractError("Cache purpose is not a study or a metered surrogate")
        required = {"purpose","protocol","core","runtime","source","input_revision",
                    "clock_horizon","scoring","initial","observations"}
        if not required <= identity.keys():
            raise ContractError("Incomplete cache namespace")
        self.root = Path(root)
        self.identity = deepcopy(identity)

    def key(self, panel_key, condition_digest, name):
        if name not in CATALOG:
            raise ContractError("Not a payable candidate")
        return {**self.identity, "panel_key": panel_key, "condition_digest": condition_digest, "descriptor": name}

    def path(self, key):
        return self.root/(digest(key)+".json")

    def read(self, key):
        path = self.path(key)
        if not path.exists():
            return None
        record = load(path)
        if record["identity"] != key or record["sha256"] != digest(record["row"]):
            raise ContractError("Cache purpose, binding or content mismatch")
        return record["row"]

    def write(self, key, row):
        save(self.path(key), dict(identity=key, row=row, sha256=digest(row)))


def counted(raw):
    counts = raw.get("counts") if isinstance(raw,dict) else None
    if not isinstance(counts,dict) or set(counts) != set(COUNT_KEYS):
        return None
    if any(type(v) is not int or v < 0 for v in counts.values()):
        return None
    return counts


def collect(keys, evaluate, archive, journal, *, cached=None, completed=None):
    """No partial delivery. Physical starts, returns and unresolved work live outside the writer."""
    keys = tuple(keys)
    rows = {}
    state = dict(started=0, returned=0, pending=0, unknown=0, cache_hits=0, failed_returns=[],
                 known_counts=dict.fromkeys(COUNT_KEYS,0), status="COMPLETE", suffix=[])
    for i, key in enumerate(keys):
        active = False
        try:
            previous = cached(key) if cached else None
            if previous is not None:
                rows[key] = previous
                state["cache_hits"] += 1
                journal.event("cache_hit", key=key)
                continue
            journal.event("physical_intent", key=key)
            state["started"] += 1
            state["pending"] += 1
            active = True
            raw = evaluate(key)
            state["returned"] += 1
            state["pending"] -= 1
            active = False
            counts = counted(raw)
            if counts is None:
                state["unknown"] += 1
            else:
                for field, value in counts.items():
                    state["known_counts"][field] += value
            # This outer tally survives a failure writing the raw or derived files.
            journal.event("returned",key=key,counts=counts)
            archive(key,raw)
            if counts is None:
                raise ContractError("Unknown internal counts")
            row = raw["row"]
            if row.get("complete") is not True:
                raise ContractError("Missing full-window outcome")
            if completed:
                completed(key,row)
            rows[key] = row
        except Exception as exc:
            if active:
                if isinstance(exc,WorkerFailure):
                    state["returned"] += 1
                    state["pending"] -= 1
                    state["failed_returns"].append(key)
                    known = counted(exc.receipt)
                    for field,value in (known or {}).items():
                        state["known_counts"][field] += value
                    state["unknown"] += int(known is None or bool(exc.receipt.get("pending")))
                else:
                    state["unknown"] += 1
                    if isinstance(exc,NoReturn):
                        for field,value in exc.subtotal.items():
                            state["known_counts"][field] += value
                    else:
                        state["pending"] -= 1
                        state["failed_returns"].append(key)
            state.update(status="STOPPED",suffix=list(keys[i+1:]),failed_key=key,error=repr(exc))
            journal.event("batch_stop",**state)
            raise Stopped(state) from exc
    journal.event("batch_complete",**state)
    return rows,state


class PaidStudy:
    """Shared evaluator; each proposal program receives only its own paid history."""
    def __init__(self, root, identity, panels, input_digests):
        self.root = Path(root)
        self.root.mkdir(parents=True,exist_ok=False)
        self.journal = Journal(self.root/"ledger.jsonl")
        self.tickets = Tickets(self.journal)
        self.cache = RowCache(self.root/"cache",identity)
        self.panels = panels
        if set(input_digests) != set(panels.keys):
            raise ContractError("Incomplete condition identities")
        self.input_digests = dict(input_digests)
        self.history = {group:{} for group in self.tickets.paid}
        self.columns = {group:{} for group in self.tickets.paid}
        self.accounting = []
        self.materialized = set()
        self.selection_cpu = dict.fromkeys(self.history,0.0)

    def query(self, group, evaluate, *, surrogate_feedback=None):
        if surrogate_feedback is not None and self.cache.identity["purpose"] != SURROGATE:
            raise ContractError("Injected feedback prohibited outside engineering surrogate")
        begin = process_time()
        name = next_candidate(group,self.history[group])
        self.selection_cpu[group] += process_time() - begin
        if self.selection_cpu[group] >= 30:
            exc = ContractError("Selector CPU limit before query")
            self.tickets.stop(group,name,exc)
            raise exc
        self.tickets.pay(group,name)
        ticket = len(self.tickets.paid[group])
        target = self.root/group/str(ticket)
        def ck(key):
            return self.cache.key(key,self.input_digests[key],name)
        def cached(key):
            identity = ck(key)
            value = self.cache.read(identity)
            if (value is not None) != (digest(identity) in self.materialized):
                raise ContractError("Missing previously charged cache entry or unsolicited prefill")
            return value
        def completed(key,row):
            identity = ck(key)
            self.cache.write(identity,row)
            self.materialized.add(digest(identity))
        try:
            rows,state = self.tickets.collect(group,name,self.panels.keys,lambda key:evaluate(name,key),
                    lambda key,raw:save(target/"raw"/(digest(ck(key))+".json"),raw),self.journal,
                    cached=cached,completed=completed)
            begin = process_time()
            self.panels.check(rows)
            if surrogate_feedback is None:
                flags = extract_paid(self.tickets,group,name,rows,self.panels)
            else:
                flags = list(surrogate_feedback[name])
            self.columns[group][name] = rows
            chosen = self.panels.lock(self.columns[group])
            report = dict(group=group,ticket=ticket,descriptor=name,bits=flags,selection=chosen,accounting=state)
            report["paid_rows"] = len(rows)
            report["prior_paid_history"] = deepcopy(self.history[group])
            report["row_hashes"] = {key:digest(row) for key,row in rows.items()}
            report["rejections"] = self.panels.rejections(self.columns[group])
            self.selection_cpu[group] += process_time() - begin
            report["selector_cpu_seconds"] = self.selection_cpu[group]
            if self.selection_cpu[group] > 30:
                raise ContractError("Selector CPU budget consumed")
            save(target/"report.json",report)
            self.history[group][name] = flags
            self.accounting.append(state)
            self.journal.event("unlocked",group=group,ticket=ticket,descriptor=name,feedback=flags,lock=chosen["lock"])
            return report
        except Exception as exc:
            self.tickets.stop(group,name,exc)
            raise

    def run(self, evaluate, *, surrogate_feedback=None):
        reports = []
        try:
            for _ in range(3):
                for group in ("U0","SEARCH"):
                    reports.append(self.query(group,evaluate,surrogate_feedback=surrogate_feedback))
            return reports
        finally:
            self.journal.close()
