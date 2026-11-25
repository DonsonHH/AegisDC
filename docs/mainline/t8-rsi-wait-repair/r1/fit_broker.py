"""Paid-slot evaluator boundary. Only signed fixed-layout aggregates cross to a proposer."""

from decimal import Decimal
from fractions import Fraction

from fit_evidence import authenticated, public_hex, signed
from fit_program import require

ROWS = 48
POSITION_US = 180_000_000
CONTROLLER_US = 60_000_000
ARM_US = 138_480_000_000
PACKET_FIELDS = {"scheduled", "completed", "status", "L_sum_us", "person_sum_us", "hard_violations"}


def microseconds(token):
    require(isinstance(token, str), "expected original numeric token")
    number = Decimal(token)
    require(number.is_finite() and number >= 0, "invalid measured value")
    return round(Fraction(number) * 1_000_000)


def count(value):
    return type(value) is int and value >= 0


class SlotFailure(Exception):
    """A launched evaluator position failed. Its measured CPU is retained if available."""

    def __init__(self, status, reason, cpu_us=None):
        super().__init__(reason)
        self.status = status
        self.cpu_us = cpu_us


class Broker:
    """The injected position service owns condition lookup. It has no role in selection."""

    def __init__(self, store, signer, position):
        self.store = store
        self.signer = signer
        self.authority = public_hex(signer)
        self.position = position
        self.spent = set()

    def evaluate(self, binding, levels):
        charge = (binding["context"], binding["arm"], binding["round"], binding["slot"])
        require(charge not in self.spent, "duplicate paid invocation")
        self.spent.add(charge)
        attempts = []
        rows = []
        totals = [0, 0, 0]
        status, reason = "COMPLETE", None
        for ordinal in range(1, ROWS + 1):
            attempt = {"ordinal": ordinal, "complete": False, "cpu_us": None}
            attempts.append(attempt)
            try:
                result = self.position(binding, levels, ordinal)
                require(set(result) == {"L", "person", "hard_violations", "cpu_us"}, "unexpected result layout")
                require(count(result["cpu_us"]), "missing CPU meter")
                attempt["cpu_us"] = result["cpu_us"]
                values = [microseconds(result["L"]), microseconds(result["person"]), result["hard_violations"]]
                require(count(values[2]), "missing hard constraint count")
                rows.append(result)
                attempt["complete"] = True
                totals = [a + b for a, b in zip(totals, values)]
                if attempt["cpu_us"] > POSITION_US:
                    raise SlotFailure("TIMEOUT", "per-position CPU cap", attempt["cpu_us"])
            except SlotFailure as exc:
                status, reason = exc.status, str(exc)
                if exc.cpu_us is not None:
                    require(count(exc.cpu_us), "negative CPU accounting")
                    attempt["cpu_us"] = exc.cpu_us
                break
            except Exception as exc:
                status, reason = "FAILED", type(exc).__name__ + ": " + str(exc)
                break
        complete = sum(x["complete"] for x in attempts)
        # The private archive and allocation account are never passed to rank_and_rewrite.
        raw = self.store.put({"binding": binding, "rows": rows})
        meter = self.store.put(signed(self.signer, {"binding": binding, "attempts": attempts,
                                  "status": status, "reason": reason, "originals": raw}))
        if status != "COMPLETE":
            return meter, None
        data = dict(scheduled=ROWS, completed=complete, status="COMPLETE", L_sum_us=totals[0],
                    person_sum_us=totals[1], hard_violations=totals[2])
        return meter, signed(self.signer, {"binding": binding, "data": data})


def open_packet(envelope, binding, authority, store):
    obj = authenticated(envelope, authority)
    require(set(obj) == {"binding", "data"} and obj["binding"] == binding, "score receipt identity")
    data = obj["data"]
    require(set(data) == PACKET_FIELDS and data["status"] == "COMPLETE" and
            all(count(data[k]) for k in PACKET_FIELDS - {"status"}) and
            data["scheduled"] == data["completed"] == ROWS, "invalid or non-redacted packet")
    return {"fit_n": ROWS, "L_sum_us": data["L_sum_us"], "person_sum_us": data["person_sum_us"],
            "hard_violations": data["hard_violations"], "receipt": store.put(envelope)}
