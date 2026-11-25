"""One study identity, immutable input/position names, and durable records."""

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
BASE = Path("/share/home/renly/renly-patrol-rsi/mainline")
ACT = BASE / "T7-incident-counterfactual-stage2-v1"
OLD = BASE / "T4b-holdout-confirmation-v2/source"
PK = OLD / "docs/mainline/t4b-holdout-confirmation-v2"
CORE = BASE / "V6-cold-launch-release-v1/source"
T4C = BASE / "T4c-action-cost-development-v3"
FAMILIES = ("LONDON", "NETHERLANDS")
ROLES = ("P", "PERIODIC", "ALARM", "B", "V_COST")
KEYS = [f"{i}-{n:02}" for n in range(1, 61) for i in (5, 6)]
LEDGERS = ("input-manifest.json", "overlap-ledger.json", "within-panel.json")
REG_SHA = "27c16e98c6c345630077fd65a5a07e58cb973a15cf0072cb6cc75716c229019f"


def need(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_bytes())


def packed(obj):
    return json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(obj):
    return hashlib.sha256(packed(obj)).hexdigest()


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, obj):
    """Exclusive creation for entry markers and immutable outputs."""
    with Path(path).open("xb") as stream:
        stream.write(packed(obj) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def publish(path, obj):
    """Expose a complete receipt only after all referenced files are durable."""
    dest = Path(path)
    with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as fp:
        fp.write(packed(obj) + b"\n")
        fp.flush()
        os.fsync(fp.fileno())
    try:
        os.link(fp.name, dest)
    finally:
        os.unlink(fp.name)


def stage(full=False):
    need(HERE == ACT / "source" and os.environ.get("SLURM_JOB_ID"), "registered Slurm activity")
    need(sha(HERE / "execution.json") == os.environ["T7_EXEC_SHA"], "published execution lock")
    spec = read(HERE / "execution.json")
    for name, pin in spec["stage_files"].items():
        need(sha(HERE / name) == pin, "stage source: " + name)
    need(sha(HERE / "registration.json") == REG_SHA, "accepted registration")
    reg = read(HERE / "registration.json")
    need(reg["panel"]["role_order"] == list(ROLES) and reg["panel"]["total_conditions"] == len(KEYS), "panel identity")
    sys.path.insert(0, str(PK))
    import context_t4b as frozen
    if full:
        src = PK / "phase2-sources.json"
        need(sha(src) == reg["baseline"]["source_manifest_sha256"], "frozen source inventory")
        plan = PK / "run-manifest.json"
        need(sha(plan) == reg["baseline"]["run_manifest_sha256"], "frozen facility and bundle manifest")
        binding = read(plan)["fixed_identities"]
        pins = read(src)["files"] | binding["path_sha256"] | binding["slice57_sha256"]
        for name, pin in pins.items():
            need(sha(OLD / name) == pin, "original source: " + name)
        frozen.check_runtime()
        need(binding["native_core"] == reg["baseline"]["native_revision"], "native revision")
        roots = frozen.bundle_inventory(read(plan))
        from workpackage import verify_bundle
        for group in ("P", "B"):
            ident, folder, members = roots[group]
            need(ident == binding["public_bundles"][reg["baseline"]["arm_bundles"][group]]["sha256"], "bundle identity")
            verify_bundle(folder, members)
    return spec, reg


def verified_release():
    release = read(ACT / "score-release.json")
    need(len(release["publication_commit"]) == 40 and release["execution_revision"] == os.environ["T7_EXEC_REV"]
         and release["input_freeze_sha256"] == sha(ACT / "pre-score/input-freeze.json"),
         "pre-score publication gate")
    freeze = read(ACT / "pre-score/input-freeze.json")
    need(freeze["registration_sha256"] == REG_SHA and freeze["facility_entries"] == freeze["score_reads"] == 0,
         "input freeze precedes scores")
    for name in LEDGERS:
        need(freeze["files_sha256"][name] == sha(ACT / "pre-score" / name), "published input ledger: " + name)
    return release
