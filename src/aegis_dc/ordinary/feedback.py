"""Derive proposal feedback from actual requests, public frames and scored occupancy."""
from fractions import Fraction
from .policy import ContractError, Evidence, FIX, order, readable, early_allowed


def row_bits(name, key, row, panels):
    bits = [False]*5
    first,second,last = order(name)
    requests = {}
    for req in row["requests"]:
        i = req["frame_index"]
        if i in requests or not 0 <= i < len(row["frames"]):
            raise ContractError("Invalid request/frame binding")
        frame = row["frames"][i]
        if (frame["payload"],frame["reply"],frame["time"]) != (req["payload"],req["reply"],req["time"]):
            raise ContractError("Unmatched actual request")
        requests[i] = req
    any_fix = any(r["payload"]["action"] == FIX for r in requests.values())
    last_read_ids = set()
    base = panels.refs["I"][key]
    for i, frame in enumerate(row["frames"]):
        view = frame["view"]
        facts = Evidence(view)
        req = requests.get(i)
        payload = req["payload"] if req else {}
        action = payload.get("action")
        unknown = facts.unknown_attempts(view) & facts.settled
        if (action == FIX and payload.get("mode") == "DIRECT" and
                set(view["attempted"]) == {first,second} and facts.supported(first) and facts.supported(second)):
            bits[0] |= panels.regress(row,base,key)
        decision = frame["decision"]
        if name.endswith("止") and decision["action"] == "INSUFFICIENT_INFORMATION" and unknown:
            bits[1] |= (decision.get("reason") == "SETTLED_UNKNOWN" and key in panels.mask
                        and base["closed"] and not row["closed"] and any(
                            a not in view["attempted"] and readable(view,a) for a in (first,second,last)))
        if action == last and facts.supported(second):
            last_read_ids.add(payload["request_id"])
            bits[2] |= (key in panels.mask and early_allowed(name,view,facts)
                        and Fraction(row["z"][0]) > Fraction(panels.refs["D"][key]["z"][0]))
        if action in (first,second,last) and unknown and req["reply"]["status"] == "ADMITTED":
            bits[3] |= (not any_fix and not row["closed"] and action not in unknown
                        and Fraction(row["work_by_action"].get(action,0)) > 0)
        if decision["action"] == "NO_ACTION_CURRENT_SCOPE" and row["closed"] and facts.negative(last):
            bits[4] |= facts.current[last]["request_id"] in last_read_ids and i == len(row["frames"])-1
    return bits


def extract_paid(tickets, group, name, column, panels):
    tickets.require_paid(group,name)
    panels.check(column)
    bits = [False]*5
    for key in panels.keys:
        flags = row_bits(name,key,column[key],panels)
        bits = [a or b for a,b in zip(bits,flags)]
    return bits
