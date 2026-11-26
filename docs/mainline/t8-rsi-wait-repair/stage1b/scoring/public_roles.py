"""Entrypoints for the public decision worker and each arm's aggregate-only proposer."""

import json
import os
from pathlib import Path
import socket
import sys

sys.path.insert(0, "/t8")
import fit_program as program


def emit(obj):
    sys.stdout.buffer.write(program.canonical(obj) + b"\n")
    sys.stdout.buffer.flush()


def descriptor_worker():
    message = json.loads(sys.stdin.buffer.readline())
    program.require(set(message) == {"levels"}, "descriptor interface")
    levels = program.validate_levels(message["levels"])
    sys.path.insert(0, "/public")
    from aegis_risk_dispatch import policy
    from aegis_action_cost import worker

    original = policy.decide

    def child(role, pub, view, settings, gate):
        def parent(p, v):
            return original(role, p, v, settings, gate)
        return program.public_decision(levels, pub, view, parent, gate, policy.validate)

    policy.decide = child
    emit({"configured": True})
    # The original V_COST entry loads settings and enables the original Gate and audit hook.
    sys.argv = [worker.__file__, "V_COST"]
    worker.main()


def proposal_worker():
    request = json.loads(sys.stdin.buffer.readline())
    operation = request.pop("operation")
    if operation == "propose":
        program.require(set(request) == {"ast","incumbent","seen","round","slots"}, "proposal inputs")
        seen = {tuple(program.validate_levels(v)) for v in request["seen"]}
        result = program.roster(request["ast"], request["incumbent"], seen, request["round"], request["slots"])
    else:
        program.require(operation == "select" and set(request) ==
                        {"arm","round","ast","incumbent","baseline","candidates","returns"}, "selection inputs")
        for paid in [request["baseline"], *request["returns"]]:
            program.require(set(paid) == {"fit_n","L_sum_us","person_sum_us","hard_violations","receipt"} and
                            paid["fit_n"] == 48, "aggregate-only score packet")
            ref = paid["receipt"]
            program.require(set(ref) == {"sha256","bytes","locator"} and
                            ref["locator"] == "objects/" + ref["sha256"], "opaque paid identity")
        result = program.rank_and_rewrite(request["arm"], request["round"], request["ast"],
                    tuple(request["incumbent"]), request["baseline"],
                    [tuple(v) for v in request["candidates"]], request["returns"])
    emit(result)


def probe():
    # Public engineering-only evidence, never an attempted read of an actual research artifact.
    try:
        Path("/outside-fixture").read_bytes()
    except FileNotFoundError:
        hidden = True
    else:
        hidden = False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM):
            blocked = False
    except PermissionError:
        blocked = True
    emit({"uid":os.getuid(),"gid":os.getgid(),"hidden_engineering_marker":hidden,"socket_denied":blocked,
          "ns":{k:os.readlink("/proc/self/ns/"+k) for k in ("mnt","pid","net","user")},
          "uid_map":Path("/proc/self/uid_map").read_text().split(),
          "caps":next(line.split()[1] for line in Path("/proc/self/status").read_text().splitlines()
                      if line.startswith("CapEff:"))})


if __name__ == "__main__":
    {"descriptor":descriptor_worker,"search":proposal_worker,"probe":probe}[sys.argv[1]]()
