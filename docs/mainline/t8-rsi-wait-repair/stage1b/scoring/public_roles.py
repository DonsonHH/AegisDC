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
        proof = request.pop("signed_feedback")
        program.require(operation == "select" and set(request) ==
                        {"arm","round","ast","incumbent","baseline","candidates","returns"}, "selection inputs")
        sys.path.insert(0,"/audit-crypto")
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        program.require(set(proof)=={"verification_key","packets"} and len(proof["packets"])==5,"signed FIT feedback")
        signer=Ed25519PublicKey.from_public_bytes(bytes.fromhex(proof["verification_key"]))
        for i,(paid,box) in enumerate(zip([request["baseline"], *request["returns"]],proof["packets"],strict=True)):
            program.require(set(paid) == {"fit_n","L_sum_us","person_sum_us","hard_violations","receipt"} and
                            paid["fit_n"] == 48, "aggregate-only score packet")
            ref = paid["receipt"]
            program.require(set(ref) == {"sha256","bytes","locator"} and
                            ref["locator"] == "objects/" + ref["sha256"], "opaque paid identity")
            program.require(set(box)=={"signer","payload","signature"} and box["signer"]==proof["verification_key"] and
                            program.fingerprint(box)==ref["sha256"],"original signed packet bytes")
            signer.verify(bytes.fromhex(box["signature"]),program.canonical(box["payload"]))
            binding=box["payload"]["binding"];data=box["payload"]["data"]
            program.require(set(box["payload"])=={"binding","data"} and set(binding)==
                            {"context","arm","round","slot","policy_id","roster_sha256"} and
                            set(data)=={"scheduled","completed","status","L_sum_us","person_sum_us","hard_violations"},
                            "fixed signed aggregate layout")
            program.require(data["status"]=="COMPLETE" and data["scheduled"]==data["completed"]==48 and
                            all(data[k]==paid[k] for k in ("L_sum_us","person_sum_us","hard_violations")),
                            "aggregate matches signature")
            program.require((i==0 and binding["arm"] in ("PARENT",request["arm"])) or
                            (i>0 and (binding["arm"],binding["round"],binding["slot"])==(request["arm"],request["round"],i)),
                            "own prepaid score only")
            vector=request["incumbent"] if i==0 else request["candidates"][i-1]
            program.require(binding["policy_id"]==program.policy_id(vector,
                "d7086b26d427266dea39fea4be4dbc88008b46f13af4e4158a2c1d692c8ca4c4",
                "28811a22be4e30a34526448c8379a004a96fd951363c9eeb2eceecad947074cd"),"paid policy identity")
        result = program.rank_and_rewrite(request["arm"], request["round"], request["ast"],
                    tuple(request["incumbent"]), request["baseline"],
                    [tuple(v) for v in request["candidates"]], request["returns"])
    emit(result)


def probe():
    # Public engineering-only evidence, never an attempted read of an actual research artifact.
    try:
        Path(sys.argv[2] if len(sys.argv)>2 else "/outside-fixture").read_bytes()
    except (FileNotFoundError, PermissionError):
        hidden = True
    else:
        hidden = False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM):
            blocked = False
    except PermissionError:
        blocked = True
    visible=Path("/role-marker")
    shared_marker = visible.read_bytes()==b"public interface check\n" if visible.exists() else False
    status=dict(line.split(":",1) for line in Path("/proc/self/status").read_text().splitlines() if ":" in line)
    emit({"uid":os.getuid(),"gid":os.getgid(),"hidden_engineering_marker":hidden,"socket_denied":blocked,
          "designated_marker_readable":shared_marker,"no_new_privileges":status["NoNewPrivs"].strip(),
          "ns":{k:os.readlink("/proc/self/ns/"+k) for k in ("mnt","pid","net","user")},
          "uid_map":Path("/proc/self/uid_map").read_text().split(),
          "caps":next(line.split()[1] for line in Path("/proc/self/status").read_text().splitlines()
                      if line.startswith("CapEff:"))})
    if len(sys.argv)>3 and sys.argv[3]=="hold":
        program.require(json.loads(sys.stdin.buffer.readline())=={"close":True},"probe close")


if __name__ == "__main__":
    {"descriptor":descriptor_worker,"search":proposal_worker,"probe":probe}[sys.argv[1]]()
