"""Canonical product space, root encoding, and one uniform draw per coordinate."""
import hashlib
import json


def packed(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def fingerprint(value):
    return hashlib.sha256(packed(value)).hexdigest()


def coordinates(space, track):
    return [p for p in space["coordinates"] if p[track.lower()] is not None]


def root(space, track):
    return {p["id"]: p[track.lower()] for p in coordinates(space, track)}


def validate(space, track, vector):
    admissible = {p["id"]: p["levels"] for p in coordinates(space, track)}
    if vector.keys() != admissible.keys() or any(v not in admissible[k] for k, v in vector.items()):
        raise ValueError("Invalid policy vector")


def uniform(space, track, rng):
    return {p["id"]: p["levels"][int(rng.integers(len(p["levels"])))] for p in coordinates(space, track)}
