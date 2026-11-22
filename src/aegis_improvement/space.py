"""Frozen parameter descriptors shared by the trainer and public policy."""
from copy import deepcopy
import hashlib
import json


def stable(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def descriptor_id(value):
    return hashlib.sha256(stable(value)).hexdigest()


def initial(space, track):
    if track not in space["track_initial"]:
        raise ValueError("Unregistered improvement track")
    return {
        "global": {name: cfg["initial"][track] for name, cfg in space["global_parameters"].items()},
        "subjects": {kind: {name: cfg["initial"] for name,cfg in space["subject_parameters"].items()}
                     for kind in space["action_kinds"]},
    }


def check(space, track, theta):
    base = initial(space, track)
    if set(theta) != set(base) or set(theta["global"]) != set(base["global"]) or set(theta["subjects"]) != set(base["subjects"]):
        raise ValueError("Incomplete parameter descriptor")
    for name, value in theta["global"].items():
        if value not in space["global_parameters"][name]["levels"]:
            raise ValueError(name)
        if track == "HOT" and name not in space["hot_mutable"]["global"] and value != base["global"][name]:
            raise ValueError("Out-of-scope warm-start parameter: "+name)
    for kind, values in theta["subjects"].items():
        if set(values) != set(base["subjects"][kind]):
            raise ValueError(kind)
        for name, value in values.items():
            if value not in space["subject_parameters"][name]["levels"]:
                raise ValueError(name)
            if track == "HOT" and name not in space["hot_mutable"]["subject"] and value != base["subjects"][kind][name]:
                raise ValueError("Out-of-scope warm-start parameter: "+name)


def batch_anchor(space, track, patch):
    theta = deepcopy(initial(space,track))
    for name, value in patch.items():
        if name in theta["global"]:
            theta["global"][name] = value
        else:
            for subject in theta["subjects"].values():
                subject[name] = value
    check(space,track,theta)
    return theta
