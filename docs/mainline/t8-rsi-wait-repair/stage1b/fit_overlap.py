"""Single-use FIT comparison. The only outward decision payload is the registered nine-field receipt."""

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CUSTODY = HERE.parent / "custody"
PUBLIC = HERE / "fit-overlap"
sys.path[:0] = [str(HERE), str(CUSTODY)]
import freeze_fit_inputs as form
import historical_catalogue as historical
import verify_receipt as verify


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def exclusive(path, value):
    with path.open("xb") as out:
        out.write(verify.canonical(value) + b"\n")
        out.flush()
        os.fsync(out.fileno())


def git_bytes(revision, path):
    verify.need(re.fullmatch("[0-9a-f]{40}", revision))
    return subprocess.check_output(["git", "cat-file", "blob", f"{revision}:{path.relative_to(ROOT).as_posix()}"],
                                   cwd=ROOT, stderr=subprocess.DEVNULL)


def slot_path():
    # This is the common parent registration's single FIT slot, also across custody revisions.
    return Path(os.environ["LOCALAPPDATA"]) / "AegisDC" / "T8" / "overlap-journal" / form.PARENT / "FIT"


def process_tree_cpu():
    """Unprivileged Windows accounting job. Counts CPU from this process and all its subsequent children."""
    import ctypes as c
    from ctypes import wintypes as w

    kernel = c.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [w.LPVOID, w.LPCWSTR]
    kernel.CreateJobObjectW.restype = w.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    kernel.QueryInformationJobObject.argtypes = [w.HANDLE, c.c_int, w.LPVOID, w.DWORD, w.LPVOID]
    handle = kernel.CreateJobObjectW(None, None)
    verify.need(handle and kernel.AssignProcessToJobObject(handle, w.HANDLE(-1)))

    class Account(c.Structure):
        _fields_ = [(name, c.c_longlong) for name in ("user", "system", "period_user", "period_system")]
        _fields_ += [(name, w.DWORD) for name in ("faults", "processes", "active", "terminated")]

    def read():
        info = Account()
        verify.need(kernel.QueryInformationJobObject(handle, 1, c.byref(info), c.sizeof(info), None))
        return (info.user + info.system) // 10
    return read


def author_cpu(job, path):
    with path.open(encoding="ascii", newline="") as stream:
        rows = {r["JobID"]: r for r in csv.DictReader(stream, delimiter="|")}
    record, batch = rows[job], rows[job+".batch"]
    verify.need(record["State"] == batch["State"] == "COMPLETED" and
                record["ExitCode"] == batch["ExitCode"] == "0:0" and
                record["TotalCPU"] == batch["TotalCPU"] and record["AllocCPUS"] == "1" and
                record["TimelimitRaw"] == "4")
    parts = record["TotalCPU"].split(":")
    verify.need(len(parts) in (2, 3))
    value = Decimal(0)
    for part in parts:
        value = value*60 + Decimal(part)
    verify.need(0 < value <= 240)
    return int(value*1_000_000)


def ready(revision):
    verify.need(re.fullmatch("[0-9a-f]{40}", revision))
    request_path = (PUBLIC/"request.json").relative_to(ROOT).as_posix()
    first = subprocess.check_output(["git","log","--format=%H",revision,"--",request_path],
                                    cwd=ROOT,stderr=subprocess.DEVNULL).decode().splitlines()
    verify.need(first == [revision])
    # Only the previously published whole request and the trusted public anchors can enter this slot.
    for p in (PUBLIC/"request.json", PUBLIC/"input-freeze.json", PUBLIC/"authoring-accounting.psv",
              CUSTODY/"authority.json", CUSTODY/"catalogue-coverage.json", CUSTODY/"verify_receipt.py",
              HERE/"fit-overlap-authorization.json", HERE/"fit-shared-account.json", HERE/"historical_catalogue.py",
              HERE/"fit_overlap.py", HERE/"freeze_fit_inputs.py"):
        verify.need(p.read_bytes() == git_bytes(revision, p))
    subprocess.run(["git","merge-base","--is-ancestor",revision,"origin/donson/mainline-39c-endpoints"],
                   cwd=ROOT,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    verify.check_schemas()
    approval = verify.parse((HERE/"fit-overlap-authorization.json").read_bytes())
    verify.need(approval["approved_catalogue_commit"] == form.CATALOGUE_COMMIT and
                approval["registration_id"] == form.REGISTER and approval["parent_registration_id"] == form.PARENT and
                approval["catalogue_root"] == form.CATALOGUE)
    verify.pinned(HERE/"historical_catalogue.py", approval["historical_catalogue_code_sha256"])
    verify.pinned(CUSTODY/"catalogue-coverage.json", approval["coverage_publication_sha256"])
    authority = verify.parse((CUSTODY/"authority.json").read_bytes())
    declaration = verify.parse((CUSTODY/"catalogue-coverage.json").read_bytes())
    verify.authority_key(authority, verify.engineering_evidence()[0])
    verify.need(verify.catalogue(declaration, authority, template=False) == form.CATALOGUE)
    request = verify.read_wire(PUBLIC/"request.json")
    verify.validate_request(request)
    verify.need(request["registration_id"] == form.REGISTER and request["split"] == "FIT" and
                request["catalogue_root"] == form.CATALOGUE)
    frozen = verify.parse((PUBLIC/"input-freeze.json").read_bytes())
    verify.exact_keys(frozen, {"registration_id","parent_registration_id","split","catalogue_release",
          "catalogue_root","generator_manifest_sha256","seed_registration_sha256","release_revision","job_id",
          "registered_rows","batch_root","generator_calls","facility_calls","score_calls"})
    verify.need(all(frozen[k] == request[k] for k in request) and
                frozen["parent_registration_id"] == form.PARENT and frozen["catalogue_release"] == form.CATALOGUE_COMMIT and
                frozen["generator_manifest_sha256"] == form.BUNDLE and frozen["seed_registration_sha256"] == form.SEED_RECORD and
                frozen["registered_rows"] == frozen["generator_calls"] == 48 and frozen["facility_calls"] == frozen["score_calls"] == 0 and
                re.fullmatch("[0-9]+", frozen["job_id"]))
    for p in (HERE/"freeze_fit_inputs.py", HERE/"fit_overlap.py", HERE/"fit-overlap-authorization.json"):
        verify.need(p.read_bytes() == git_bytes(frozen["release_revision"], p))
    cpu = author_cpu(frozen["job_id"], PUBLIC/"authoring-accounting.psv")
    return request, frozen, authority, declaration, cpu


def open_batch(request, frozen):
    command = 'cat -- "$HOME/renly-patrol-rsi/mainline/T8-stage1b-procedural-v1/panel/batch.private.json"'
    raw = subprocess.check_output(["ssh","-T","-o","BatchMode=yes","-o","StrictHostKeyChecking=yes",
               "-o","ConnectTimeout=12","myserver",command], stderr=subprocess.DEVNULL, timeout=30)
    verify.need(len(raw) <= 128*1024 and raw.endswith(b"\n") and verify.sha(raw[:-1]) == request["batch_root"])
    index = verify.parse(raw)
    verify.need(raw == verify.canonical(index) + b"\n")
    header = {k: v for k,v in frozen.items() if k not in ("batch_root","generator_calls","facility_calls","score_calls")}
    verify.need({k:v for k,v in index.items() if k!="ordered"} == header)
    rows = index["ordered"]
    verify.need(type(rows) is list and len(rows) == 48)
    for ordinal, row in enumerate(rows, 1):
        verify.exact_keys(row, {"ordinal", *form.IDENTITY_FIELDS})
        verify.need(type(row["ordinal"]) is int and row["ordinal"] == ordinal and
                    all(verify.is_root(row[field]) for field in form.IDENTITY_FIELDS))
    return index


def compare(rows, groups):
    """Only the private journal receives these exact counts. Never drop a row or stop at the first hit."""
    within = {field:len(rows)-len({r[field] for r in rows}) for field in form.IDENTITY_FIELDS}
    sources = {}
    for source, panels in groups.items():
        pairs = [pair for panel in panels for pair in panel.values()]
        old_full = {p[0] for p in pairs}
        old_operative = {p[1] for p in pairs}
        full, operative = (("legacy_full","legacy_common") if source in ("T3","T7-stage1")
                           else ("v3_full","v3_operative"))
        sources[source] = {
            "memberships":len(pairs), "rows_checked":len(rows),
            "full_hits":sum(r[full] in old_full for r in rows),
            "operative_hits":sum(r[operative] in old_operative for r in rows),
        }
    collision = any(within.values()) or any(s["full_hits"] or s["operative_hits"] for s in sources.values())
    return ("BLOCKED" if collision else "PASS"), {"within":within, "historical":sources}


def consume(revision):
    meter = process_tree_cpu()
    request, frozen, authority, published, author_us = ready(revision)
    slot = slot_path()
    slot.parent.mkdir(parents=True, exist_ok=True)
    try:
        slot.mkdir(exist_ok=False)
    except FileExistsError:
        raise ValueError("The FIT slot was already reserved; use the saved output") from None
    began = time.monotonic()
    exclusive(slot/"request.json", request)
    exclusive(slot/"consumed.json", {"parent_registration_id":form.PARENT, "split":"FIT",
              "freeze_revision":revision, "request_sha256":verify.sha(verify.canonical(request)+b"\n"),
              "received_at_utc":utc(), "consumed":1})
    decision, pct, complete = "BLOCKED", 0, False
    try:
        index = open_batch(request, frozen)
        exclusive(slot/"frozen-fit-index.json", index)
        verify.need(historical.declaration() == published)
        groups = historical.historical_catalogue()
        verify.need(set(groups) == set(verify.SOURCE_BINDINGS))
        decision, private = compare(index["ordered"], groups)
        exclusive(slot/"private-comparison.json", private)
        pct, complete = 100, True
    except Exception as exc:
        exclusive(slot/"private-interruption.json", {"class":type(exc).__name__, "ended_at_utc":utc()})
    local_us = meter()
    if local_us + author_us > 300_000_000:
        decision, complete = "BLOCKED", False
    receipt = {**request, "custodian_id":authority["custodian_id"], "auditor_id":authority["auditor_id"],
               "aggregate_coverage_pct":pct, "all_required_tests_complete":complete, "decision":decision}
    verify.bound(request, receipt, authority, published["catalogue_root"])
    exclusive(slot/"receipt.json", receipt)
    exclusive(slot/"accounting.json", {"local_comparison_process_tree_cpu_us":local_us,
              "slurm_author_cpu_us":author_us,"charged_cpu_us":local_us+author_us,
              "scope":"until all comparisons and their private journal close", "completed_at_utc":utc()})
    # Single fixed release window, independent of source, matches and decision. No interim stdout.
    time.sleep(max(0, 60-(time.monotonic()-began)))
    exclusive(slot/"released.json", {"receipt_sha256":verify.sha(verify.canonical(receipt)+b"\n"),"time_utc":utc()})
    print("ONE FIT REQUEST CONSUMED; RECEIPT AWAITS PI SIGNATURE")


def export(revision):
    request, _, authority, published, _ = ready(revision)
    slot = slot_path()
    consumed = verify.parse((slot/"consumed.json").read_bytes())
    verify.need(consumed["freeze_revision"] == revision and verify.read_wire(slot/"request.json") == request)
    receipt = verify.read_wire(slot/"receipt.json")
    verify.bound(request, receipt, authority, published["catalogue_root"])
    released = verify.parse((slot/"released.json").read_bytes())
    verify.need(verify.sha((slot/"receipt.json").read_bytes()) == released["receipt_sha256"])
    dest = PUBLIC/"receipt.json"
    if not dest.exists():
        exclusive(dest, receipt)
    verify.need(dest.read_bytes() == (slot/"receipt.json").read_bytes())
    print("UNSIGNED", receipt["decision"])


def check():
    # Hand-labelled dummy identities only. Never use a research split or the historical catalogue in this test.
    rows = [{"ordinal":i+1, **{f:verify.sha(f"example/{f}/{i}".encode()) for f in form.IDENTITY_FIELDS}} for i in range(48)]
    old = ("x","y")
    for source, fields in [("T3",("legacy_full","legacy_common")),("T4c",("v3_full","v3_operative")),
                           ("H3-sealed-index",("v3_full","v3_operative"))]:
        verify.need(compare(rows,{source:[{"example":old}]})[0] == "PASS")
        for i, field in enumerate(fields):
            pair = list(old)
            pair[i] = rows[-1][field]
            decision, counts = compare(rows,{source:[{"example":pair}]})
            verify.need(decision == "BLOCKED" and counts["historical"][source]["rows_checked"] == 48)
    for field in form.IDENTITY_FIELDS:
        copy = [dict(r) for r in rows]
        copy[-1][field] = copy[0][field]
        verdict, counts = compare(copy,{"T3":[{"example":old}]})
        verify.need(verdict == "BLOCKED" and counts["within"][field] == 1)
    print("PASS synthetic controls: both encodings, four within-batch duplicate checks, full traversal")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    options = p.add_mutually_exclusive_group(required=True)
    options.add_argument("--check", action="store_true")
    options.add_argument("--consume", metavar="PUBLISHED_REQUEST_COMMIT")
    options.add_argument("--export-saved", metavar="PUBLISHED_REQUEST_COMMIT")
    args = p.parse_args()
    if args.check:
        check()
    elif args.consume:
        consume(args.consume)
    else:
        export(args.export_saved)
