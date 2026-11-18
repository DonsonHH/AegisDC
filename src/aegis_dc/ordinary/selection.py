"""Offline pairing, exact Pareto promotion, and the two frozen ordinary selectors."""
from fractions import Fraction
from .policy import CATALOG, HUMAN, RANK, SEARCH, ContractError

RESOURCE = frozenset({"within_budget", "external_reservations_clear", "reserved_exit_honored"})


def metrics(row):
    if row.get("complete") is not True or type(row["closed"]) is not bool:
        raise ContractError("Incomplete outcome or unresolved closure")
    if len(row["z"]) != 4 or any(type(x) not in (int,str) for x in row["z"]):
        raise ContractError("Invalid four-dimensional outcome")
    z = tuple(Fraction(x) for x in row["z"])
    if min(z) < 0 or not set(row["violations"]) <= RESOURCE:
        raise ContractError("Invalid score or technical violation")
    return z


class Panels:
    def __init__(self, keys, references):
        self.keys = tuple(keys)
        if len(set(keys)) != len(keys) or set(references) != {"I", "D", "P"}:
            raise ContractError("Invalid panel or comparator identity")
        self.refs = references
        for col in references.values():
            self.check(col)
        self.mask = {key for key in keys if all(not col[key]["violations"] for col in references.values())}

    def check(self, column):
        if set(column) != set(self.keys):
            raise ContractError("A paid column must be complete before exposure")
        for row in column.values():
            metrics(row)

    def eligible(self, col):
        return all(set(col[k]["violations"]) <= set(self.refs["I"][k]["violations"]) for k in self.keys)

    def regress(self, row, base, key):
        return (not set(row["violations"]) <= set(base["violations"])
                or any(x > y for x,y in zip(metrics(row), metrics(base)))
                or (key in self.mask and base["closed"] and not row["closed"]))

    def compare(self, col, base):
        """None for no strict promotion; flags are service, person, tool, constraints."""
        flags = [False]*4
        strict_numeric = False
        for key in self.keys:
            x, y = col[key], base[key]
            if self.regress(x,y,key):
                return None
            if key in self.mask:
                less = [a < b for a,b in zip(metrics(x),metrics(y))]
                strict_numeric |= any(less)
                for dest, index in enumerate((0,2,3)):
                    flags[dest] |= less[index]
            flags[3] |= set(x["violations"]) < set(y["violations"])
        return flags if strict_numeric or flags[3] else None

    def rejections(self, purchased):
        result = {}
        for name, column in {"D": self.refs["D"], **purchased}.items():
            self.check(column)
            vetoes = {}
            for key in self.keys:
                row, base = column[key], self.refs["I"][key]
                reasons = sorted(set(row["violations"]) - set(base["violations"]))
                reasons += [label for label,x,y in zip(("L","U","person","tool"),metrics(row),metrics(base)) if x > y]
                if key in self.mask and base["closed"] and not row["closed"]:
                    reasons.append("lost_closure")
                if reasons:
                    vetoes[key] = reasons
            if vetoes or self.compare(column,self.refs["I"]) is None:
                result[name] = vetoes or {"strictness":"no effective strict improvement"}
        return result

    def lock(self, purchased):
        if not set(purchased) <= set(CATALOG):
            raise ContractError("Invalid selection candidate")
        cols = {"I": self.refs["I"], "D": self.refs["D"], **purchased}
        promotions = {}
        for name in RANK:
            if name == "I" or name not in cols:
                continue
            self.check(cols[name])
            if self.eligible(cols[name]):
                flags = self.compare(cols[name], cols["I"])
                if flags is not None:
                    promotions[name] = flags
        frontier = [name for name in promotions if not any(
            self.compare(cols[other],cols[name]) is not None for other in promotions if other != name)]
        locked = frontier[0] if frontier else "I"
        return dict(lock=locked, frontier=frontier, seen_service=any(x[0] for x in promotions.values()),
                    locked_service=bool(frontier and promotions[locked][0]), flags=promotions)


def next_candidate(group, history):
    """history contains only that group's complete paid reports, in ticket order."""
    if group not in ("U0","SEARCH") or len(history) >= 3:
        raise ContractError("Unknown group or exhausted logical tickets")
    if not history:
        return HUMAN
    if group == "SEARCH":
        return SEARCH[len(history)]
    last = next(reversed(history))
    seen = {"I","D","P",*history}

    def edit(name,index,value):
        fields = list(name)
        fields[index] = value
        result = "".join(fields)
        return "I" if result == "V全续" else result

    def growth(name, skip=None):
        flags = history[name]
        for enabled, index, value in (
            (flags[2] and name[1]=="全",1,"早"),
            (flags[3] and name[2]=="续",2,"止"),
            (flags[4],0,"C" if name[0]=="V" else "V")):
            if enabled and index != skip:
                candidate = edit(name,index,value)
                if candidate not in seen:
                    return candidate
        return None

    flags = history[last]
    for enabled,index,value in ((flags[0] and last[1]=="早",1,"全"),(flags[1] and last[2]=="止",2,"续")):
        if not enabled:
            continue
        neighbor = edit(last,index,value)
        if neighbor not in seen:
            return neighbor
        if neighbor in history:
            sibling = growth(neighbor,index)
            if sibling:
                return sibling
    return growth(last) or next(n for n in CATALOG if n not in seen)


def paired_summary(panels, bought, locks):
    """Retain both original denominators, resource tradeoffs and effective directions."""
    out = {}
    selected = {}
    for group, result in locks.items():
        name = result["lock"]
        selected[group] = ({**panels.refs, **bought[group]})[name]
    for group, col in selected.items():
        other = "SEARCH" if group == "U0" else "U0"
        comparators = {**panels.refs, HUMAN: bought[group][HUMAN], other: selected[other]}
        comparisons = {}
        for name, base in comparators.items():
            rows = {}
            for key in panels.keys:
                a,b = col[key],base[key]
                rows[key] = dict(in_mask=key in panels.mask,
                                 candidate={k:a[k] for k in ("z","violations","closed")},
                                 reference={k:b[k] for k in ("z","violations","closed")},
                                 difference=[str(i-j) for i,j in zip(metrics(a),metrics(b))])
            eligible = panels.eligible(col) and panels.eligible(base)
            comparisons[name] = dict(rows=rows,eligible=eligible,
                                     promotion_flags=panels.compare(col,base) if eligible else None)
        out[group] = comparisons
    return out
