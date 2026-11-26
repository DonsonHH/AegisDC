"""Author the one approved FIT panel on Slurm. No old index, facility or scoring dependency."""

import argparse
from collections import Counter
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import sys


PARENT = "06ff51c5578f00951c42b4dd2e53cfb4989b0b8be923056332241058d4eb9f3b"
REGISTER = "f8a4d6d320c090a4a74280542df5c864677dcfe78e79638843b1fad86887340f"
CATALOGUE = "59cd699e7098493718ffb2c1ff8ba4dcd0deb31d7df710b833e2c1321455a119"
CATALOGUE_COMMIT = "61ba7c531fdbc561fa7242629fbed0853bd6ed4f"
BUNDLE = "7be88fbbc4f1b6c2af06eff1d9d910060122b3db4468ed5a1bdaf555d0cb41ae"
SEED_RECORD = "e06f32a8a7c83620c927e3cf00f414604085a409606a505371a5b909e14e7fc5"
PYTHON = "5b2187174e57eb543b1800d101a5f115afc24e52c1519b6f09e4759ca4d6abe6"
FAMILIES = ("LONDON", "NETHERLANDS")
IDENTITY_FIELDS = ("v3_full", "legacy_full", "v3_operative", "legacy_common")


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def packed(value, *, legacy=False):
    return json.dumps(value, sort_keys=not legacy, ensure_ascii=not legacy,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def save(path, data):
    with path.open("xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def pinned(path, expected):
    data = path.read_bytes()
    require(sha(data) == expected, "frozen source or declaration differs")
    return data


def bind_inputs(bundle):
    lock = json.loads(pinned(bundle/"r1/audit-sources.json", BUNDLE))
    for name, digest in lock["files_sha256"].items():
        pinned(bundle/name, digest)
    pinned(Path(sys.executable), PYTHON)
    reg = json.loads(pinned(bundle/"r0/registration.json", PARENT))["randomization"]
    require((reg["families"], reg["fit_blocks_per_family"], reg["conditions_per_block"],
             reg["fit_conditions_total"]) == (list(FAMILIES), 2, 12, 48), "wrong sampling quantities")
    seed_record = json.loads(pinned(bundle/"r0/seed-registration.json", SEED_RECORD))
    root = bytes.fromhex(seed_record["fresh_public_development_root_hex"])
    seed = sha(b"AegisDC/T8/r0/FIT/v1\0" + root)
    require(sha(root) == seed_record["root_sha256"] and seed == seed_record["fit_seed_hex"], "FIT randomness identity")
    law = json.loads((bundle/"r0/panel-law.json").read_bytes())["operative_variations"]
    groups = json.loads((bundle/"r1/audit-plan.json").read_bytes())["schedule_groups"]
    return seed, law, groups


def write_panel(bundle, output, revision):
    job = os.environ["SLURM_JOB_ID"]
    require(job.isdecimal() and os.environ["SLURM_CPUS_PER_TASK"] == "1" and
            re.fullmatch("[0-9a-f]{40}", revision), "unbound allocation or release")
    os.umask(0o077)
    output.mkdir(mode=0o700, exist_ok=False)
    header = {"registration_id": REGISTER, "parent_registration_id": PARENT, "split": "FIT",
              "catalogue_release": CATALOGUE_COMMIT, "catalogue_root": CATALOGUE,
              "generator_manifest_sha256": BUNDLE, "seed_registration_sha256": SEED_RECORD,
              "release_revision": revision, "job_id": job, "registered_rows": 48}
    save(output/"entry.json", packed(header) + b"\n")
    seed, law, groups = bind_inputs(bundle)
    sys.path.insert(0, str(bundle/"r1"))
    import capacity_audit as inherited
    require(Path(inherited.__file__).resolve() == bundle/"r1/capacity_audit.py", "wrong inherited helper")
    generator, _, _ = inherited.original_modules(bundle/"base")
    templates = generator.templates()
    cells = set(generator.incident_case.__globals__["CELLS"])
    start = range(law["start_ticks_inclusive"][0], law["start_ticks_inclusive"][1] + 1)
    end = range(law["end_ticks_inclusive"][0], law["end_ticks_inclusive"][1] + 1)
    profiles = list(itertools.product(start, end, start, end))
    require(len(profiles) == law["catalogue_size_per_family"] and len(set(groups)) == 11, "invalid profile law")
    orders = {f: inherited.ordered_profiles(seed, f, profiles)[:22] for f in FAMILIES}
    counts = {(f, block): (Counter(), Counter(), Counter()) for f in FAMILIES for block in (0, 1)}

    (output/"conditions").mkdir()
    (output/"legacy-encoding").mkdir()
    identities = []
    for draw in range(24):
        for family_index, family in enumerate(FAMILIES, 4):
            case = generator.condition(int(seed, 16), family_index, draw, templates)
            ev = case["evaluation"]
            require((ev["family"], ev["draw"], case["attachment"]["kind"]) == (family, draw, family),
                    "generator order or family differs")
            cell, block = ev["cell"], draw//12
            group = "TWIN_PAIR" if cell in ("TWIN_A", "TWIN_B") else cell
            profile = orders[family][11*block + groups.index(group)]
            offset = min(law["permit_end_offsets_ticks"], key=lambda j: (
                inherited.hash_obj(["AegisDC/T8/r0/window/v1", seed, family, [profile, j]]), j))
            public = case["native"]["dispatch_program"]["public"]
            original_windows = [tuple(sub["write_window"]) for sub in public["subjects"]]
            original_shifts = dict(public["workforce"]["shifts"])
            second = law["second_worker"][family]
            inherited.schedule(public, profile, offset, second)
            shifts = dict(original_shifts, worker_electrical=[60*profile[0], 60*profile[1]])
            shifts[second] = [60*profile[2], 60*profile[3]]
            require(public["workforce"]["shifts"] == shifts, "worker calendar")
            for (lo, hi), sub in zip(original_windows, public["subjects"], strict=True):
                upper = min(3600, max(lo+60, hi+60*offset)) if hi-lo >= 180 else hi
                require(tuple(sub["write_window"]) == (lo, upper), "permit boundary")
            cell_counts, exposure_counts, profile_counts = counts[family, block]
            cell_counts[cell] += 1
            exposure_counts[case["maintenance"]["exposure_s"]] += 1
            profile_counts[profile] += 1
            ordinal = len(identities)+1
            case_path = output/"conditions"/f"{ordinal:02}.json"
            legacy_path = output/"legacy-encoding"/f"{ordinal:02}.json"
            save(case_path, packed(case) + b"\n")
            save(legacy_path, packed(case, legacy=True) + b"\n")
            raw, legacy = case_path.read_bytes(), legacy_path.read_bytes()
            saved = json.loads(raw)
            require(json.loads(legacy) == saved and raw == packed(case) + b"\n", "saved input readback")
            full, effective, common = inherited.identity(saved)
            require(full == sha(raw), "canonical complete input")
            identities.append(dict(ordinal=ordinal, v3_full=full, legacy_full=sha(legacy),
                                   v3_operative=effective, legacy_common=common))
    for cell_counts, exposure_counts, profile_counts in counts.values():
        require(cell_counts == Counter({c: 1 for c in cells}) and exposure_counts == {0: 4, 600: 4, 1200: 4} and
                sorted(profile_counts.values()) == [1]*10 + [2], "incomplete block quota")
    require(len(identities) == 48, "incomplete fixed batch")
    # No old comparison, within-batch exclusion, resampling or scoring is performed by the curator.
    commitment = packed({**header, "ordered": identities})
    save(output/"batch.private.json", commitment + b"\n")
    batch_root = sha(commitment)
    request = {"registration_id": REGISTER, "split": "FIT", "batch_root": batch_root, "catalogue_root": CATALOGUE}
    save(output/"request.json", packed(request) + b"\n")
    save(output/"freeze.json", packed({**header, "batch_root": batch_root, "generator_calls": 48,
                                       "facility_calls": 0, "score_calls": 0}) + b"\n")
    print("FROZEN FIT 48", batch_root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-bundle", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    write_panel(args.source_bundle.resolve(), args.output.resolve(), args.revision)
