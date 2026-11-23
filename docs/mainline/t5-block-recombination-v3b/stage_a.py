"""Stage A: pure rules shared by the preregistered self-check and the readback."""
from fractions import Fraction
from hashlib import sha256
from math import isfinite

FAMILIES = ("WATER_HEAT", "NETWORK_POWER", "RESERVE_TRANSFER", "COOLING_ACCESS", "LONDON", "NETHERLANDS")
DOMAINS = ("C", "N", "LC", "LB", "LG", "NR", "NP", "NC")
GLOBAL = ("lookahead", "nr_need", "nr_slack", "nr_credit")
SUFFIX = tuple(f"deadline_{i}" for i in range(5)) + (
    "displacement", "probe_credit", "fast_need", "fast_slack", "bypass_weight", "veto")
ROLES = tuple(f"Q{i:02}" for i in range(1,49)) + (
    "B_COST","V_COST","M","M_HOT","MAIN-U-1","MAIN-U-2","MAIN-U-3","MAIN-R-1","MAIN-R-2","MAIN-R-3")
SEED = "AegisDC/T5-v3b/stage-A/paired-family-bootstrap/v1"


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def choice_set(labels, values):
    require(len(set(labels)) == len(labels) > 0, "nonempty distinct comparator labels")
    sums = {}
    for label in labels:
        x = values[label]
        require(len(x) and all(isfinite(v) for v in x), "missing finite L")
        sums[label] = sum(Fraction(v) for v in x)
    require(len({len(values[k]) for k in labels}) == 1, "identical paired denominators")
    smallest = min(sums.values())
    return [k for k in labels if sums[k] == smallest]


def columns(block):
    return tuple(block+"."+s for s in SUFFIX)


def construct(families, domains, counts, ties, vectors, base):
    def block(label, domain):
        return tuple(vectors[label][k] for k in columns(domain))
    candidates = {f:([k for k in ties[f] if k in vectors] if any(counts[f].values()) else ties[f][:1]) for f in families}
    if any(not candidates[f] for f in families):
        return dict(status="UNREPRESENTABLE_FAMILY_MINIMUM", families=[f for f in families if not candidates[f]])

    def compatible(i, fixed):
        if i == len(families):
            return {}
        f = families[i]
        seen = set()
        for label in candidates[f]:
            entries = tuple((b,block(label,b)) for b in domains if counts[f].get(b,0))
            if entries in seen or any(b in fixed and fixed[b] != v for b,v in entries):
                continue
            seen.add(entries)
            tail = compatible(i+1, {**fixed, **dict(entries)})
            if tail is not None:
                return {f:label, **tail}
        return None

    selected = compatible(0,{})
    exact = selected is not None
    if not exact:
        selected = {f:candidates[f][0] for f in families}
    theta = dict(base)
    ownership = {}
    for b in domains:
        voters = [f for f in families if counts[f].get(b,0)]
        votes = {f:counts[f][b] for f in voters}
        conflict = len({block(selected[f],b) for f in voters}) > 1
        winner = max(voters,key=votes.get) if conflict else next(iter(voters),None)
        label = selected[winner] if winner else "B_COST"
        theta.update({k:vectors[label][k] for k in columns(b)})
        ownership[b] = dict(family=winner, source=label, votes=votes, conflict=conflict,
                            representatives={f:selected[f] for f in voters},
                            coordinates={k:theta[k] for k in columns(b)})
    require(all(theta[k] == base[k] for k in GLOBAL),"fixed global coordinates")
    return dict(status="LOCKED",fully_compatible=exact,selected=selected,domains=ownership,theta=theta)


def mapped(pub, request):
    if request is None:
        return None
    subjects = {s["id"]:s["key"] for s in pub["subjects"]}
    domain = subjects[request["subject"]]
    require(domain in DOMAINS and isinstance(request["phase"],str), "public subject/action type")
    return domain


def gate(estimates):
    return len(estimates)==2 and all(e["mean"] < 0 and e["upper95"] < 0 for e in estimates)


def estimates(keys, families, treatments, controls):
    import numpy as np
    require(len(keys)==len(set(keys))==36 and len(controls)==2, "paired design")
    indices = [[i for i,k in enumerate(keys) if families[k]==f] for f in FAMILIES]
    require(all(len(ids)==6 for ids in indices), "six conditions per stratum")
    rng = np.random.Generator(np.random.PCG64(int.from_bytes(sha256(SEED.encode("ascii")).digest(),"big")))
    draw = rng.integers(0,6,size=(10000,6,6))
    selection = np.asarray(indices)[np.arange(6)[None,:,None],draw]
    results = []
    for control in controls:
        diff = np.asarray([treatments[k]-control[k] for k in keys], dtype=float)
        require(np.isfinite(diff).all(),"all original pairs")
        observed = diff[selection].mean(axis=(1,2))
        results.append(dict(mean=float(diff.mean()), upper95=float(np.quantile(observed,.95,method="linear")),
                            by_family={f:float(diff[idx].mean()) for f,idx in zip(FAMILIES,indices,strict=True)}))
    return results


def selfcheck():
    base = dict.fromkeys(GLOBAL,0) | {k:0 for b in DOMAINS for k in columns(b)}
    high = base | {k:1 for k in columns("C")}
    vs = {"lo":base,"hi":high,"B_COST":base}
    fam = ("first","second")
    counts = {"first":{"C":2},"second":{"C":3}}
    def pick(a,b):
        return construct(fam,DOMAINS,counts,dict(zip(fam,(a,b))),vs,base)
    require(pick(["lo","hi"],["hi"])["selected"]=={"first":"hi","second":"hi"},"search all tied winners")
    require(pick(["lo"],["hi"])["domains"]["C"]["source"]=="hi","larger request count")
    counts["first"]["C"]=3
    require(pick(["lo"],["hi"])["domains"]["C"]["source"]=="lo","family order on equal counts")
    require(pick(["opaque"],["hi"])["status"]=="UNREPRESENTABLE_FAMILY_MINIMUM","no rank substitution")
    counts["first"]={}
    require(pick(["opaque"],["hi"])["status"]=="LOCKED","no blocks to extract")
    require(choice_set(["b","a"],{"b":[1,0],"a":[0,1]})==["b","a"],"exact co-minima")
    require(mapped({"subjects":[{"id":"C-copy","key":"NC"}]},{"subject":"C-copy","phase":"R"})=="NC","public alias")
    fams={f+"-"+str(i):f for f in FAMILIES for i in range(6)}
    zeros = dict.fromkeys(fams,0)
    minus = {k:-(i//6+1) for i,k in enumerate(fams)}
    x=estimates(list(fams),fams,minus,[zeros,zeros])
    require(x[0]==x[1] and x[0]["mean"]==x[0]["upper95"]==-3.5 and gate(x),"paired strata and duplicate controls")
    require(not gate(estimates(list(fams),fams,zeros,[zeros,zeros])),"strict zero boundary")
    return ["public alias", "exact ranking", "compatible ties", "votes", "vote tie", "opaque donor", "empty map",
            "six stratified paired draws", "same control", "strict zero"]
