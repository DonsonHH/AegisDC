"""Generate the one frozen panel and publish only commitments to the new conditions."""
from collections import Counter, defaultdict
import hashlib
import os
from context_t4b import (
    ACT, PK, PROTOCOL, REGISTRATION, SOURCES, T4C, V3_DEV, check_sources, check_runtime,
    condition_order, digest, read, require, sha, slurm_id, write,
)


def operative(case):
    return digest({key: case[key] for key in ("native", "attachment", "maintenance")})


def main():
    from inputs_v3 import FAMILIES, condition, templates

    job = slurm_id()
    registered, plan = check_sources()
    check_runtime()
    seed_path = ACT/"private"/"H1.bin"
    seed_bytes = seed_path.read_bytes()
    require(len(seed_bytes) == 32 and hashlib.sha256(seed_bytes).hexdigest() == registered["seeds"]["H1"]["sha256"],
            "H1 verification failed before condition creation")
    seed = int.from_bytes(seed_bytes, "big")
    del seed_bytes

    panel = plan["panel"]
    require(list(FAMILIES) == panel["family_order"], "frozen family order")
    old_manifest = read(T4C/"dev-manifest.json")
    require(len(old_manifest["files"]) == 72 and sha(V3_DEV/"dev-inputs/manifest.json") == sha(T4C/"dev-manifest.json"),
            "disclosed original v3 comparison set")
    full_dev, operative_dev = defaultdict(list), defaultdict(list)
    for key in old_manifest["order"]:
        old_path = V3_DEV/"dev-inputs"/(key + ".json")
        require(sha(old_path) == old_manifest["files"][key], "prior disclosed input identity")
        old = read(old_path)
        full_dev[digest(old)].append(key)
        operative_dev[operative(old)].append(key)

    # One creation marker for this seed, kept even if input authoring is interrupted.
    write(ACT/"author-entry.json", {"job": job, "registration_sha256": sha(REGISTRATION), "source_sha256": sha(SOURCES)})
    inputs = ACT/"inputs"
    inputs.mkdir()
    source = templates()
    complete_seen, operative_seen = defaultdict(list), defaultdict(list)
    durations, cells = defaultdict(Counter), defaultdict(set)
    table = {}
    repeats = []
    order = condition_order(plan)
    for key in order:
        family_index, draw = (int(v)-1 for v in key.split("-"))
        case = condition(seed, family_index, draw, source)
        family = FAMILIES[family_index]
        block = draw//12
        maintenance = case["maintenance"]
        require(case["evaluation"]["family"] == family and case["evaluation"]["draw"] == draw
                and maintenance["capacity"] == panel["maintenance_support_capacity"]
                and maintenance["recovery"] == panel["additional_write_gap_s"], "original v3 law")
        duration = maintenance["exposure_s"]
        durations[(family, block)][duration] += 1
        cells[(family, block)].add(case["evaluation"]["cell"])
        full, effective = digest(case), operative(case)
        finding = {"key": key, "full_within": complete_seen[full], "operative_within": operative_seen[effective],
                   "full_vs_disclosed_v3": full_dev[full], "operative_vs_disclosed_v3": operative_dev[effective]}
        if any(value for name, value in finding.items() if name != "key"):
            repeats.append({name: list(value) if name != "key" else value for name, value in finding.items()})
        complete_seen[full].append(key)
        operative_seen[effective].append(key)
        path = inputs/(key + ".json")
        write(path, case)
        table[key] = dict(family=family, draw=draw, block=block, duration_s=duration, sha256=sha(path),
                          operative_sha256=effective)
    require(len(table) == panel["conditions"] and len(durations) == 12
            and all(c == dict.fromkeys(panel["maintenance_duration_s"], 4) for c in durations.values())
            and all(len(c) == panel["conditions_per_block"] for c in cells.values()), "two complete twelve-cell blocks per family")
    summary = dict(schema="T4b-ordered-condition-commitments-v1", registration_revision=os.environ["T4B_REG_REV"],
                   registration_sha256=sha(REGISTRATION), run_manifest_sha256=sha(PROTOCOL), author_source_sha256=sha(SOURCES),
                   v3_rules_sha256=registered["v3_rules_sha256"], author_job=job, conditions_generated=len(table),
                   order=order, conditions=table, repeat_audit=repeats, compared_disclosed_v3_conditions=72,
                   facility_starts_at_authoring=0)
    write(ACT/"condition-summary.json", summary)
    print("conditions", len(table), "registered input matches", len(repeats), "condition summary", sha(ACT/"condition-summary.json"), flush=True)


if __name__ == "__main__":
    main()
