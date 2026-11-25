"""Verify the original T3 case bytes and the unmodified V_COST public handshake."""

import argparse
import ast
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
T3 = "85af7e48b60e61dc453456b5b7bc73ab832900b5"
T4B = "3487276af9e9759357771d16eb45feceaa3c948a"
R1 = "9d6bfd450298527f66a8c936633667efeac2837a"
R1_PATH = "docs/mainline/t7-incident-counterfactual/r1/registration.json"
R1_SHA = "27c16e98c6c345630077fd65a5a07e58cb973a15cf0072cb6cc75716c229019f"
T3_PATH = "docs/mainline/t3-prior-information-v2/"
T4A_PATH = "docs/mainline/t4a-public-risk-v1/"
CLOCK = tuple(range(0, 3601, 60))
ROSTER = [f"{family}-{draw:02}" for draw in range(1, 13) for family in (5, 6)]


def require(test, reason):
    if not test:
        raise ValueError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def packed(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def historical(rev, path, expected=None):
    data = subprocess.check_output(["git", "show", rev + ":" + path], cwd=ROOT)
    if expected is not None:
        require(sha(data) == expected, "public source SHA-256: " + path)
    return data


def assignment(path, name):
    for node in ast.parse(path.read_bytes()).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError("missing frozen public constant " + name)


def public_bundle(directory, pins):
    bridge = ROOT / T4A_PATH / "bridge.py"
    require(bridge.read_bytes() == historical(T4B, T4A_PATH + "bridge.py"), "T4a handshake source")
    for name, expected in pins.items():
        if name == "common.py":
            data = assignment(bridge, "SHIM")
        elif name == "public_work.py":
            data = historical(T3, T3_PATH + name)
        else:
            data = historical(T4B, "src/" + name)
        require(sha(data) == expected, "frozen public bundle member: " + name)
        dest = directory / name
        dest.parent.mkdir(exist_ok=True, parents=True)
        dest.write_bytes(data)


def archived_cases(spec):
    manifest = json.loads(historical(T3, T3_PATH + spec["manifest"], spec["manifest_sha256"]))
    archive = historical(T3, T3_PATH + spec["archive"], spec["archive_sha256"])
    require(manifest["zipped"] == sha(archive), "T3 archived input collection")
    cases = {}
    with gzip.GzipFile(fileobj=io.BytesIO(archive)) as stream:
        for line in stream:
            record = json.loads(line)
            key, case = record["key"], record["value"]
            if key not in ROSTER:
                continue
            original = (json.dumps(case, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode()
            require(sha(original) == manifest["files"][key], "original T3 row: " + key)
            require(set(case) == {"native", "attachment", "evaluation"} and key not in cases, "original T3 schema")
            cases[key] = (case, sha(original))
    require(list(cases) == ROSTER, "T3 incident roster/order")
    return cases


def handshake(directory, pub):
    command = [sys.executable, "-I", "-S", "-B", str(directory / "aegis_action_cost/worker.py"), "V_COST"]
    env = {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "OMP_NUM_THREADS": "1"}
    if os.name == "nt":
        env["SystemRoot"] = os.environ["SystemRoot"]
    message = packed({"public": pub}) + b'\n{"close":true}\n'
    reply = subprocess.run(command, input=message, capture_output=True, timeout=30, cwd=directory, env=env)
    require(reply.returncode == 0 and not reply.stderr, "public handshake failed: " + reply.stderr.decode(errors="replace"))
    require(len(reply.stdout.splitlines()) == 1 and json.loads(reply.stdout) == {"ready": True, "role": "V_COST"},
            "expected only the V_COST handshake acknowledgement")


def inspect():
    r = json.loads(historical(R1, R1_PATH, R1_SHA))
    source, policy = r["stage1_development"]["t3"], r["stage1_development"]["policy"]
    freeze = json.loads(historical(T4B, policy["freeze"], policy["freeze_sha256"]))
    pins = freeze["public_bundle_files"]
    require(freeze["role"] == "V_COST" and sha(packed(pins)) == policy["bundle_sha256"] == freeze["public_bundle_sha256"],
            "published strategy bundle descriptor")
    cases = archived_cases(source)
    entries = []
    with tempfile.TemporaryDirectory(prefix="aegis-t7-public-") as tmp:
        bundle = Path(tmp)
        public_bundle(bundle, pins)
        static_keys = assignment(bundle / "aegis_risk_dispatch/policy.py", "PUB_FIELDS")
        view_keys = assignment(bundle / "aegis_risk_dispatch/policy.py", "VIEW_FIELDS")
        native = ast.parse(historical(T3, T3_PATH + "native.py"))
        envelopes = [n.value for n in ast.walk(native) if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == "view" for t in n.targets)
                     and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name) and n.value.func.id == "dict"]
        require(len(envelopes) == 1 and {k.arg for k in envelopes[0].keywords} == view_keys, "T3 decision frame fields")
        for key, (case, identity) in cases.items():
            pub = case["native"]["dispatch_program"]["public"]
            require(set(pub) == static_keys and tuple(pub["clock"]) == CLOCK, "static interface: " + key)
            require({r["value"] for r in case["native"]["dispatch_program"]["channel"] if r["kind"] == "order"} == {"OPEN"},
                    "unmodified T3 signed orders: " + key)
            handshake(bundle, pub)
            entries.append({"key": key, "input_sha256": identity, "public_sha256": sha(packed(pub)),
                            "ready": True, "role": "V_COST"})
    return {"status": "PASS", "r1_revision": R1, "r1_registration_sha256": R1_SHA,
            "input_revision": T3, "input_manifest_sha256": source["manifest_sha256"],
            "input_archive_sha256": source["archive_sha256"], "strategy_revision": T4B,
            "strategy_freeze_sha256": policy["freeze_sha256"], "public_bundle_sha256": sha(packed(pins)),
            "public_members": len(pins), "view_fields": sorted(view_keys), "handshakes": entries,
            "facility_calls": 0, "policy_decisions": 0, "H2_seed_access": 0, "H3_seed_access": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", action="store_true", help="save the first compatibility receipt")
    args = parser.parse_args()
    result = inspect()
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    path = HERE / "compatibility.json"
    if args.record:
        with path.open("xb") as dst:
            dst.write(data)
    else:
        require(path.read_bytes() == data, "compatibility receipt differs")
    print("PASS r1 registration:", result["r1_registration_sha256"])
    print("PASS original T3 row hashes: 24/24 in frozen order; OPEN orders and original 61-tick declarations")
    print(f"PASS policy: {result['public_members']} frozen files; t4c_v3/V_COST {result['public_bundle_sha256']}")
    print("PASS T3 native public frame matches the worker declaration; isolated public-only handshakes: 24/24")
    print("Facility calls=0; policy decisions=0; Slurm jobs=0; H2/H3 seed access=0")
    print("Compatibility-SHA256:", sha(data))


if __name__ == "__main__":
    main()
