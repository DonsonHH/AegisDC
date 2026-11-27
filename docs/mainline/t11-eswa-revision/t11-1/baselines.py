"""T11 public admissibility and the registered one-intervention VoI comparison."""
from collections import defaultdict

from aegis_action_cost.permit import exposure
from aegis_action_cost.planning import PublicCalendar, expected
from aegis_risk_dispatch import knowledge, policy


def guard(pub, view, gate, has_support=True):
    """Match V3's mandatory, unsupported and outstanding-initial priority at a public node."""
    required, renewals = policy.priorities(pub, view, gate)
    request, refusals = policy.first_legal(required + renewals, pub, view, gate)
    if request:
        return "MANDATORY_OWN_WORK", request, refusals
    if not has_support:
        return "UNSUPPORTED_PUBLIC_EVIDENCE", None, refusals
    paid_tasks = {row["task"] for row in view["paid"]}
    for issue in view["issued"]:
        if issue["phase"] != "I":
            continue
        terminal = gate.ack(view, issue["task"])
        if terminal is None and view["time"] <= issue["planned_end"] + pub["latency"]:
            return "AWAIT_OWN_PAID_RESULT", None, refusals
        if (terminal and terminal["status"] == "completed" and issue["task"] not in paid_tasks
                and view["time"] < terminal["observed_at_s"] + pub["latency"]):
            return "AWAIT_OWN_PAID_RESULT", None, refusals
    return "VALUE", None, refusals


def menu_with_refusals(pub, view, gate, calendar=None):
    """Return WAIT and gate-admitted I/A whose success branch has a legal calendar."""
    opened = {row["subject"] for row in gate.live(view, "order")}
    issued = {row["task"] for row in view["issued"]}
    menu = {None: None}
    refusals = []
    for subject in sorted(pub["subjects"], key=lambda sub: sub["id"]):
        sid = subject["id"]
        if not subject["primary"] or sid not in opened:
            continue
        for phase in ("A", "I"):
            if phase == "I" and sid + "::A" in issued:
                continue
            request, reason = gate.admit(pub, view, subject, phase)
            if request is None:
                refusals.append([sid, phase, reason])
                continue
            if calendar is None:
                calendar = PublicCalendar(pub, view, gate)
            action = (sid, phase)
            if calendar.run(action, (), renew_initial=False) is not None:
                menu[action] = request
    return menu, refusals


def elective_menu(pub, view, gate):
    return menu_with_refusals(pub, view, gate)[0]


def myopic(pub, view, weights, price, settings, gate):
    """One immediate A, or WAIT/I followed by at most one A shared per report."""
    calendar = PublicCalendar(pub, view, gate)
    menu, refusals = menu_with_refusals(pub, view, gate, calendar)
    now = view["time"]
    future_writes = [
        (sid, "A") for sid, sub in calendar.subjects.items()
        if sub["primary"] and sid in calendar.opened and sid + "::A" not in calendar.done
        and sub["write_window"][1] > now
    ]
    # An empty current action menu can still justify WAIT for a later legal write.
    alternatives = [()] + [(action,) for action in sorted(future_writes)]
    accounting = (price, settings["fee_in_person_seconds"], (calendar.debit, calendar.fees),
                  exposure(view), settings["maintenance_capacity"])

    def paths_at(first, sequences, renew_initial):
        paths = []
        for sequence in sequences:
            plan = calendar.run(first, sequence, renew_initial=renew_initial)
            if plan is not None:
                paths.append((sequence, plan))
        return paths

    def best_path(paths, distribution):
        ranked = []
        for sequence, plan in paths:
            vector = expected(plan, distribution, *accounting)
            rank = (round(vector[3], 9), round(vector[1], 9), round(vector[2], 9),
                    len(sequence), sequence)
            ranked.append((rank, sequence, vector))
        _, sequence, vector = min(ranked, key=lambda item: item[0])
        return [sid for sid, _ in sequence], list(vector)

    def inspect(first, paths):
        # The first step is fixed, so all these paths have the same nominal sample time.
        sid = first[0]
        sample_time = paths[0][1][0][0][4]
        kind = calendar.subjects[sid]["key"]
        grouped = defaultdict(list)
        for world, mass in weights:
            signature = knowledge.sample(world, kind, sample_time, calendar.known_effects)
            grouped[signature].append((world, mass))
        q = settings["unknown_report_probability"]
        table = {}
        adequate_paths = None
        for signature, group in sorted(grouped.items()):
            # The frozen calendar opens a conditional X on an adequate initial read.
            adequate = (signature in ("OK", "CONTACT", "CLOSED", "READY", "COMMISSIONED")
                        or signature.startswith("AUTO/RUN"))
            if adequate and adequate_paths is None:
                adequate_paths = paths_at(first, [seq for seq, _ in paths], True)
            choices = adequate_paths if adequate else paths
            if not choices:
                return None
            mass = sum(p for _, p in group)
            continuation, cost = best_path(choices, [(w, p / mass) for w, p in group])
            table[signature] = dict(probability=(1 - q) * mass, continue_with=continuation, cost=cost)
        empty = [(seq, plan) for seq, plan in paths if not seq]
        if not empty:
            return None
        _, cost = best_path(empty, weights)
        table["UNKNOWN"] = dict(probability=q, continue_with=[], cost=cost)
        return table

    branches = []
    for first in menu:
        # A is the sole elective write on the direct branch. WAIT and I each
        # leave a single later opportunity, subject to the frozen issue/arrival clock.
        sequences = [()] if first is not None and first[1] == "A" else alternatives
        paths = paths_at(first, sequences, False)
        if not paths:
            continue
        if first is not None and first[1] == "I":
            table = inspect(first, paths)
            if table is None:
                continue
        else:
            continuation, cost = best_path(paths, weights)
            table = {"CURRENT": dict(probability=1, continue_with=continuation, cost=cost)}
        vector = [sum(row["probability"] * row["cost"][j] for row in table.values()) for j in range(4)]
        branches.append(dict(first=list(first) if first else None, vector=vector, table=table,
                             admitted_continuation_plans=len(paths)))
    if not branches:
        return None, refusals, [], None
    winner = min(branches, key=lambda item: (
        round(item["vector"][3], 9), round(item["vector"][1], 9), round(item["vector"][2], 9),
        item["first"] is not None, tuple(item["first"] or ())))
    first = winner["first"]
    return menu[tuple(first) if first else None], refusals, branches, first
