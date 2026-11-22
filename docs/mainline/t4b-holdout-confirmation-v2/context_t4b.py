"""T4b bindings and exact identities for the one-time holdout."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

PK = Path(__file__).resolve().parent
ROOT = PK.parents[2]
MAINLINE = PK.parent
T4C = MAINLINE / "t4c-action-cost-v3"
T4D = MAINLINE / "t4d-cost-baseline-v1"
T3 = MAINLINE / "t3-prior-information-v2"
T4A = MAINLINE / "t4a-public-risk-v1"
SHARE = Path("/share/home/renly/renly-patrol-rsi/mainline")
ACT = SHARE / "T4b-holdout-confirmation-v2"
CORE = SHARE / "V6-cold-launch-release-v1/source"
V3_DEV = SHARE / "T4c-action-cost-development-v3"
BUNDLE_B = SHARE / "T4a-public-risk-development-v1/public-only"
BUNDLE_V = V3_DEV / "public-only"
T4D_ACTIVITY = SHARE / "T4d-cost-baseline-v1"
PROTOCOL = PK / "run-manifest.json"
REGISTRATION = PK / "holdout-registration-v3.json"
SOURCES = PK / "phase2-sources.json"
EPS = 1e-7
TICKS = ("900", "1800", "2700", "3600")
sys.path[:0] = list(map(str, (PK, T4D, T4C, T3, T4A, CORE/"src", CORE/"scripts", ROOT/"src")))


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def read(path):
    return json.loads(Path(path).read_bytes())


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def digest(value):
    return hashlib.sha256(compact(value)).hexdigest()


def write(path, value):
    """Exclusive durable record, used for identities written before an irreversible call."""
    with Path(path).open("xb") as stream:
        stream.write(compact(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def write_gz(path, value):
    with Path(path).open("xb") as stream:
        stream.write(gzip.compress(compact(value) + b"\n", compresslevel=5, mtime=0))


def slurm_id():
    return os.environ["SLURM_JOB_ID"]


def check_sources():
    require(sha(SOURCES) == os.environ["T4B_SOURCE_SHA"], "published source manifest")
    evidence = read(SOURCES)
    plan = read(PROTOCOL)
    registered = read(REGISTRATION)
    require(registered["status"] == "USER_OFFLINE_COMMITMENTS_REGISTERED_H1_HANDOFF_RECEIVED"
            and registered["run_manifest_sha256"] == sha(PROTOCOL), "published commitment and run manifest")
    require(evidence["registration_revision"] == os.environ["T4B_REG_REV"]
            and evidence["registration_sha256"] == sha(REGISTRATION)
            and evidence["run_manifest_sha256"] == sha(PROTOCOL), "stage provenance")
    pinned = evidence["files"] | plan["fixed_identities"]["path_sha256"] | plan["fixed_identities"]["slice57_sha256"]
    for file, expected in pinned.items():
        require(sha(ROOT / file) == expected, "source identity: " + file)
    return registered, plan


def check_runtime():
    release = read(MAINLINE/"v6-stage-three-cold-launch-v1/launch-manifest.json")
    require(sha(sys.executable) == release["python"]["sha256"], "native interpreter")
    for file, expected in release["core_files"].items():
        require(sha(CORE/file) == expected, "native runtime: " + file)
    return release


def condition_order(plan):
    panel = plan["panel"]
    return [f"{family + 1}-{draw + 1:02}" for draw in range(panel["conditions_per_family"])
            for family in range(len(panel["family_order"]))]


def groups(plan):
    order = condition_order(plan)
    pilot = plan["slurm"]["pilot"]["jobs"]
    roster = {f"pilot-{i+1:02}": [key] for i, key in enumerate(order[:pilot])}
    remaining = order[pilot:]
    roster.update({f"main-{i//2+1:02}": remaining[i:i+2] for i in range(0, len(remaining), 2)})
    require(len(roster) == 75 and all(len(keys) == 2 for group, keys in roster.items() if group.startswith("main-")),
            "frozen batch partition")
    return roster


def read_inputs(plan):
    path = ACT/"condition-summary.json"
    require(sha(path) == os.environ["T4B_CONDITION_SHA"], "published ordered condition commitments")
    summary = read(path)
    require(summary["order"] == condition_order(plan)
            and summary["run_manifest_sha256"] == sha(PROTOCOL)
            and summary["registration_revision"] == os.environ["T4B_REG_REV"]
            and summary["registration_sha256"] == sha(REGISTRATION)
            and summary["author_source_sha256"] == sha(SOURCES)
            and summary["conditions_generated"] == 144, "complete input registration")
    return summary


def load_case(key, summary):
    path = ACT/"inputs"/(key + ".json")
    require(sha(path) == summary["conditions"][key]["sha256"], "condition bytes")
    return read(path)


def bundle_inventory(plan, check_bytes=False):
    from workpackage import verify_bundle
    parent = read(T4D/"input-manifest.json")
    inventory = parent["bundle_members"]
    roots = {}
    for name, pin in plan["fixed_identities"]["public_bundles"].items():
        identity = pin["sha256"]
        path = {"t4a_B_PA": BUNDLE_B, "t4c_v3": BUNDLE_V,
                "t4d_B_cost": T4D_ACTIVITY/"bundles"/identity}[name]
        members = inventory[identity]
        require(digest(members) == identity, "bundle descriptor")
        if check_bytes:
            verify_bundle(path, members)
        for role in pin["roles"]:
            roots[role] = (identity, path, members)
    return roots
