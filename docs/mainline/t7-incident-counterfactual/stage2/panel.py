"""Create the single H3 panel and freeze both overlap ledgers before any score exists."""

from collections import Counter, defaultdict
import hashlib
import os
import subprocess

from study import ACT, BASE, FAMILIES, HERE, KEYS, LEDGERS, REG_SHA, T4C, digest, need, publish, read, save, sha


def make_panel(reg):
    from inputs_v3 import FAMILIES as original_families, condition, templates
    from author import operative

    dir_ = ACT / "pre-score"
    dir_.mkdir()
    inputs = ACT / "inputs"
    inputs.mkdir()
    hist = reg["overlap_sensitivity"]["historical_reference"]
    dev = reg["overlap_sensitivity"]["development_reference"]
    idx = BASE / "T4b-holdout-confirmation-v2/condition-summary.json"
    need(sha(idx) == hist["sha256"], "T4b reference before authoring")
    historical = read(idx)["conditions"]
    old_full, old_op = defaultdict(list), defaultdict(list)
    for key, row in historical.items():
        family = row["family"]
        if family in FAMILIES:
            old_full[family, row["sha256"]].append(key)
            old_op[family, row["operative_sha256"]].append(key)
    need(all(sum(row["family"] == f for row in historical.values()) == 24 for f in FAMILIES), "T4b denominators")
    dfolder = T4C / "dev-inputs"
    need(sha(dfolder / "manifest.json") == dev["manifest_sha256"], "T4c reference before authoring")
    prior = read(dfolder / "manifest.json")
    dev_full, dev_op, devmap = defaultdict(list), defaultdict(list), {}
    for key in prior["order"]:
        file = dfolder / (key + ".json")
        ident = sha(file)
        need(ident == prior["files"][key], "T4c original input: " + key)
        op = operative(read(file))
        dev_full[ident].append(key)
        dev_op[op].append(key)
        devmap[key] = op
    need(len(devmap) == 72 and digest(devmap) == dev["operative_map_sha256"], "72 original operating identities")
    source = templates()
    need(tuple(original_families[4:6]) == FAMILIES, "original incident indices")
    handoff = read(HERE / "handoff.json")
    encrypted = ACT / "handoff/h3.sealed"
    need(handoff["matched"] and handoff["actual_sha256"] == reg["custody"]["sha256"]
         and sha(encrypted) == handoff["encrypted_sha256"], "H3 transport before consumption")
    save(ACT / "author-entry.json", {"job": os.environ["SLURM_JOB_ID"], "commitment": handoff["actual_sha256"],
                                      "execution_revision": os.environ["T7_EXEC_REV"], "consumption": 1})
    plain = bytearray(subprocess.check_output(["openssl", "pkeyutl", "-decrypt", "-inkey",
                     str(ACT / "handoff/transport-private.pem"), "-in", str(encrypted), "-pkeyopt",
                     "rsa_padding_mode:oaep", "-pkeyopt", "rsa_oaep_md:sha256", "-pkeyopt", "rsa_mgf1_md:sha256"]))
    try:
        need(len(plain) == 32 and hashlib.sha256(plain).hexdigest() == handoff["actual_sha256"], "transport integrity")
        seed = int.from_bytes(plain, "big")
    finally:
        plain[:] = bytes(len(plain))

    seen_full, seen_op = defaultdict(list), defaultdict(list)
    items, external, internal = {}, {}, {}
    durations, cells = defaultdict(Counter), defaultdict(set)
    for key in KEYS:
        family_index, draw = (int(v) - 1 for v in key.split("-"))
        family = original_families[family_index]
        case = condition(seed, family_index, draw, source)
        block = draw // 12
        need((case["evaluation"]["family"], case["evaluation"]["draw"]) == (family, draw), "frozen generator identity")
        path = inputs / (key + ".json")
        save(path, case)
        full, op = sha(path), operative(case)
        duration = case["maintenance"]["exposure_s"]
        need(case["maintenance"]["capacity"] == 0.5 and case["maintenance"]["recovery"] == 180, "frozen maintenance law")
        durations[family, block][duration] += 1
        cells[family, block].add(case["evaluation"]["cell"])
        items[key] = {"family": family, "draw": draw, "block": block, "sha256": full, "operative_sha256": op}
        h, d = old_op[family, op], dev_op[op]
        external[key] = {"t4b_full": old_full[family, full], "t4c_full": dev_full[full],
                         "t4b_operative": h, "t4c_operative": d, "exclude_descriptively": bool(h or d)}
        internal[key] = {"prior_full": list(seen_full[full]), "prior_operative": list(seen_op[op])}
        seen_full[full].append(key)
        seen_op[op].append(key)
    del seed
    need(len(items) == 120 and len(durations) == 10 and all(len(v) == 12 for v in cells.values())
         and all(v == {0: 4, 600: 4, 1200: 4} for v in durations.values()), "ten original twelve-cell quotas")
    blocks = []
    for family in FAMILIES:
        for block in range(5):
            keys = [k for k in KEYS if (items[k]["family"], items[k]["block"]) == (family, block)]
            h = {k for k in keys if external[k]["t4b_operative"]}
            d = {k for k in keys if external[k]["t4c_operative"]}
            blocks.append({"family": family, "block": block, "planned": len(keys), "t4b": len(h), "t4c": len(d),
                           "both": len(h & d), "excluded": len(h | d), "retained": len(keys) - len(h | d)})
    save(dir_ / LEDGERS[0], {"order": KEYS, "conditions": items, "original_commitment": handoff["actual_sha256"]})
    save(dir_ / LEDGERS[1], {"order": KEYS, "by_condition": external, "blocks": blocks,
                             "historical_reference": hist, "development_reference": dev, "references_complete": True})
    save(dir_ / LEDGERS[2], {"order": KEYS, "by_condition": internal,
                             "full_groups": [v for v in seen_full.values() if len(v) > 1],
                             "operative_groups": [v for v in seen_op.values() if len(v) > 1]})
    publish(dir_ / "input-freeze.json", {"job": os.environ["SLURM_JOB_ID"], "registration_sha256": REG_SHA,
            "execution_revision": os.environ["T7_EXEC_REV"], "files_sha256": {n: sha(dir_ / n) for n in LEDGERS},
            "author_entries": 1, "conditions_generated": len(items), "facility_entries": 0, "score_reads": 0})
