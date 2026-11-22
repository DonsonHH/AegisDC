"""Fixed anchor-free U and an independent uniform-search control."""
from copy import deepcopy
import hashlib
from math import log1p, sqrt
from statistics import mean

import numpy as np

from .space import coordinates, fingerprint, root, uniform


def identifiers():
    return [f"{track}-{method}-{seed}" for track in ("MAIN", "HOT") for method in ("U", "R") for seed in (1, 2, 3)]


def generator(u, arm, epoch):
    text = f'{u["search_rng_domain"]}|{arm}|{epoch}'
    return np.random.Generator(np.random.PCG64(int.from_bytes(hashlib.sha256(text.encode()).digest()[:16], "big")))


def mutate(space, track, vector, credit, u, rng):
    dims = coordinates(space, track)
    operators = sorted({p["operator"] for p in dims})
    counts = sum(v["n"] for v in credit.values())
    if rng.random() < u["random_operator_probability"]:
        operator = operators[int(rng.integers(len(operators)))]
    else:
        value = []
        for op in operators:
            record = credit.get(op, {"gain": 0, "n": 0})
            score = record["gain"]/max(1,record["n"])+u["exploration_credit_s"]*sqrt(log1p(counts)/(1+record["n"]))
            value.append(score)
        best = [op for i, op in enumerate(operators) if value[i] == max(value)]
        operator = best[int(rng.integers(len(best)))]
    eligible = [p for p in dims if p["operator"] == operator]
    rate = float(rng.choice(u["mutation_density_levels"]))
    result = dict(vector)
    changed = [p for p in dims if rng.random() < (rate if p["operator"] == operator else u["background_mutation_probability"])]
    if not changed:
        changed = [eligible[int(rng.integers(len(eligible)))]]
    for p in changed:
        options = [x for x in p["levels"] if x != vector[p["id"]]]
        result[p["id"]] = options[int(rng.integers(len(options)))]
    return result, operator


def start(space, arm, behavior):
    track = arm.split("-")[0]
    seed = root(space, track)
    return dict(vector=seed, selected=track+"-root", seen=[behavior], credit={}, rounds_without_gain=0,
                history=[], fit_incumbent=None)


def propose(space, u, arm, state, epoch, replay):
    track, method, _ = arm.split("-")
    rng = generator(u, arm, epoch)
    seen = set(state["seen"])
    batch = []
    attempts = []
    for index in range(1,u["batch_size"]+1):
        for _ in range(u["replay_draw_limit_per_slot"]):
            if method == "U":
                vector, operator = mutate(space,track,root(space,track),state["credit"],u,rng)
            else:
                vector, operator = uniform(space,track,rng), "uniform"
            key = fingerprint(vector)
            outcome = replay(track,vector)
            duplicate = outcome in seen
            attempts.append(dict(parameters_sha256=key, behavior_sha256=outcome, duplicate=duplicate, operator=operator))
            if duplicate:
                continue
            seen.add(outcome)
            batch.append(dict(label=f"{arm}-r{epoch}-c{index}", vector=vector, behavior=outcome, parameters_sha256=key,
                              operator=operator))
            break
        else:
            break
    return batch, attempts


def learn(state, batch, feedback, u, adaptive):
    """Only paired scalar ratings from purchased FIT positions cross this boundary."""
    expected = {state["selected"],*(item["label"] for item in batch)}
    if feedback.keys() != expected:
        raise ValueError("Unexpected FIT feedback")
    if len({tuple(sorted(v)) for v in feedback.values()}) != 1:
        raise ValueError("FIT pairing")
    if any(not r["charged"] or r["status"] != "SCORED" for a in feedback.values() for r in a.values()):
        raise ValueError("Required paid FIT score missing")
    fields = ("L","person","tool","fee")
    averages = {label:{k:mean(v[k] for v in values.values()) for k in fields}
                for label,values in feedback.items()}
    next_state = deepcopy(state)
    current = averages[state["selected"]]["L"]
    if adaptive:
        for item in batch:
            credit = next_state["credit"].setdefault(item["operator"],dict(gain=0.0,n=0))
            credit["gain"] += current-averages[item["label"]]["L"]
            credit["n"] += 1
    best = min(batch, key=lambda r:(*(averages[r["label"]][k] for k in fields),r["parameters_sha256"]))
    improvement = current-averages[best["label"]]["L"]
    if improvement >= u["minimum_accept_gain_s"]:
        next_state["selected"] = best["label"]
        next_state["vector"] = best["vector"]
        next_state["rounds_without_gain"] = 0
    else:
        next_state["rounds_without_gain"] += 1
    next_state["fit_incumbent"] = averages[next_state["selected"]]
    next_state["seen"].extend(x["behavior"] for x in batch)
    next_state["history"].append(dict(selected=next_state["selected"], average=next_state["fit_incumbent"], paid=averages))
    return next_state
