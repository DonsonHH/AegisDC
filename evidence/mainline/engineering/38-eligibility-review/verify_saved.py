"""Verify the declared ticket38 decision/review delivery using saved bytes only."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
FILES = [
    "docs/mainline/38-eligibility-audit.md",
    "docs/mainline/38-eligibility-proposal.json",
    "docs/mainline/38-eligibility-audit-v2.md",
    "docs/mainline/38-eligibility-decision-v2.json",
    "docs/mainline/38-eligibility-revision.json",
    "evidence/mainline/engineering/38-eligibility-review/spec.zip",
    "evidence/mainline/engineering/38-eligibility-review/standards.zip",
    "evidence/mainline/engineering/38-eligibility-review/spec-review.md",
    "evidence/mainline/engineering/38-eligibility-review/standards-review.md",
    "evidence/mainline/engineering/38-eligibility-review/verify_saved.py",
    "evidence/mainline/engineering/38-eligibility-review/review-package-receipt.json",
    "docs/mainline/checkpoint38.md",
]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def write_new(path, data):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def package():
    started = datetime.now(timezone.utc).isoformat()
    packages = {}
    definitions = (
        ("spec", "38-eligibility-spec-01", "final-manifest.json", "a278a5ef73206eb1fcbf7d62f3bff9cf19c1bfd744ef536c9545610be7b23e1f", "report.md"),
        ("standards", "38-eligibility-standards-01", "manifest.json", "3815a13bf737fbf557d0bcc41427d1b673af0e3c0acb28a9c84993bb910deb5c", "standards-review.md"),
    )
    for axis, directory, manifest_name, expected, report_name in definitions:
        source = ROOT / ".work" / directory
        native = (source / manifest_name).read_bytes()
        assert sha(native) == expected
        manifest = json.loads(native)
        values = manifest.get("artifacts")
        if values is None:
            values = {entry["path"]: entry for entry in manifest["files"]}
        for name, entry in values.items():
            value = (source / name).read_bytes()
            assert sha(value) == entry["sha256"] and len(value) == entry["bytes"], name
        with zipfile.ZipFile(OUT / (axis + ".zip"), "x", compression=zipfile.ZIP_DEFLATED) as bundle:
            for name in sorted(values):
                bundle.writestr(name, (source / name).read_bytes())
            bundle.writestr(manifest_name, native)
        with (OUT / (axis + "-review.md")).open("xb") as stream:
            stream.write((source / report_name).read_bytes())
        packages[axis] = dict(manifest=manifest_name, manifest_sha256=expected, native_files=len(values))
    write_new(OUT / "review-package-receipt.json", dict(status="PACKAGED_EXACT_INDEPENDENT_REVIEWS", started_utc=started,
              completed_utc=datetime.now(timezone.utc).isoformat(), source=git("rev-parse", "HEAD").decode().strip(),
              authoring_tool_sha256=sha(Path(__file__).read_bytes()), packages=packages,
              execution="stdlib byte checks and archive creation only"))
    print(json.dumps(dict(status="PACKAGED", reviews=packages)))


def verify(checkpoint=False):
    manifest = json.loads((OUT / "delivery-manifest.json").read_text("utf-8"))
    assert set(manifest["files"]) == set(FILES)
    for name, expected in manifest["files"].items():
        assert sha((ROOT / name).read_bytes()) == expected, name
        assert sha(git("cat-file", "blob", "HEAD:" + name)) == expected, name
    for name in FILES[:2]:
        assert (ROOT / name).read_bytes() == git("cat-file", "blob", "9948d55d:" + name)
    for name in FILES[2:5]:
        assert (ROOT / name).read_bytes() == git("cat-file", "blob", "2a17aa56:" + name)
    assert git("rev-parse", "pre-meeting-20261103^{}").decode().strip() == "076d9aa15c5bc99a5b7985f296e15543b7b0f3d7"
    assert not git("diff", "--name-only", "2ba22965..HEAD", "--", "src", "configs", "tests", "scripts", ".github", "pyproject.toml").strip()
    report = ROOT / "paper/mainline-report-20261108"
    report_manifest = json.loads((report / "delivery-manifest.json").read_text("utf-8"))
    for name, expected in report_manifest["files"].items():
        assert sha((report / name).read_bytes()) == expected, name
        assert sha(git("cat-file", "blob", "HEAD:paper/mainline-report-20261108/" + name)) == expected, name
    members = {}
    for archive, native_manifest in (("spec.zip", "final-manifest.json"), ("standards.zip", "manifest.json")):
        with zipfile.ZipFile(OUT / archive) as bundle:
            assert bundle.testzip() is None
            assert len(bundle.namelist()) == len(set(bundle.namelist()))
            native = json.loads(bundle.read(native_manifest))
            values = native.get("artifacts")
            if values is None:
                values = {entry["path"]: entry for entry in native["files"]}
            assert set(bundle.namelist()) == set(values) | {native_manifest}
            for name, entry in values.items():
                value = bundle.read(name)
                assert sha(value) == entry["sha256"] and len(value) == entry["bytes"], name
            members[archive] = len(bundle.namelist())
    if checkpoint:
        progress = json.loads((ROOT / "docs/mainline/progress.json").read_text("utf-8"))
        assert progress["current_ticket"] == "39"
        assert progress["research_trials"]["completed"] == 180
        assert progress["research_trials"]["remaining_registered_attempts"] == 0
        assert progress["active_implementations"] == []
        for number in range(38, 43):
            ticket, = (ROOT / ".scratch/full-facility-mainline/issues").glob(str(number) + "-*.md")
            status = "resolved" if number == 38 else "ready-for-agent"
            assert "**Status:** " + status in ticket.read_text("utf-8"), number
        authority = json.loads((ROOT / "docs/mainline/evidence/38-root.json").read_text("utf-8"))
        assert authority["status"] == "ACCEPTED_CORRECTED_ELIGIBILITY"
        assert authority["decision"] == "ELIGIBLE_FOR_NARROW_STRUCTURED_POLICY_FACTOR"
        assert authority["overall_goal"] == "INCOMPLETE"
    return dict(status="PASS_FRESH_SAVED38_DELIVERY", source=git("rev-parse", "HEAD").decode().strip(),
                declared_files=len(FILES), review_members=members, unchanged_report_files=len(report_manifest["files"]),
                scientific_source_unchanged_from="2ba22965119615b157bb7f3a302875bf05e4989b",
                checkpoint_lifecycle_checked=checkpoint, verification="Saved bytes, Git and ZIP only; no project execution")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("package", "seal", "fresh"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--checkpoint", action="store_true")
    args = parser.parse_args()
    if args.mode == "package":
        package()
    elif args.mode == "seal":
        values = {name: sha((ROOT / name).read_bytes()) for name in FILES}
        for name, expected in values.items():
            assert sha(git("cat-file", "blob", "HEAD:" + name)) == expected, name
        write_new(OUT / "delivery-manifest.json", dict(schema="aegisdc-38-decision-delivery-v1",
                  authoring_source=git("rev-parse", "HEAD").decode().strip(), files=values,
                  scope="Exact original and revised decision, both independent review archives/reports and this verifier; caches excluded"))
        print(json.dumps(dict(status="SEALED", files=len(values))))
    else:
        assert args.output is not None
        try:
            result = verify(args.checkpoint)
        except Exception as error:
            write_new(args.output, dict(status="FAIL_SAVED38_DELIVERY", error=repr(error)))
            raise
        write_new(args.output, result)
        print(json.dumps(result, ensure_ascii=False))
