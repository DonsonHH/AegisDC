"""Audit the three public ledgers without the seed, generator, any H3 score or facility."""

from collections import defaultdict
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys

from study import FAMILIES, HERE, KEYS, LEDGERS, REG_SHA, digest, need, packed, read, sha


def blob(revision, path):
    return subprocess.check_output(["git","show",revision+":"+path], cwd=HERE)


def verify(folder):
    rbytes = blob("9d6bfd45","docs/mainline/t7-incident-counterfactual/r1/registration.json")
    need(hashlib.sha256(rbytes).hexdigest() == REG_SHA, "registration")
    reg = json.loads(rbytes)
    freeze = read(folder/"input-freeze.json")
    need(freeze["registration_sha256"]==REG_SHA and freeze["author_entries"]==1 and freeze["conditions_generated"]==120
         and freeze["facility_entries"]==freeze["score_reads"]==0, "pre-score freeze boundary")
    need(all(sha(folder/n)==freeze["files_sha256"][n] for n in LEDGERS), "ledger digests")
    panel, external, internal = [read(folder/n) for n in LEDGERS]
    need(all(x["order"]==KEYS for x in (panel,external,internal)) and panel["original_commitment"]==reg["custody"]["sha256"],
         "pre-score order and H3 commitment")
    need(all(set(obj)==set(KEYS) for obj in (panel["conditions"],external["by_condition"],internal["by_condition"])),
         "complete row membership")
    spec = reg["overlap_sensitivity"]
    h, d = spec["historical_reference"], spec["development_reference"]
    need(external["historical_reference"]==h and external["development_reference"]==d and external["references_complete"],
         "registered reference sets")
    hbytes=blob(h["revision"],h["path"])
    mbytes=blob(d["revision"],d["manifest"])
    archive=blob(d["revision"],d["archive"])
    need([hashlib.sha256(x).hexdigest() for x in (hbytes,mbytes,archive)] == [h["sha256"],d["manifest_sha256"],d["archive_sha256"]],
         "public historical bytes")
    hs, ho, ds, do = (defaultdict(list) for _ in range(4))
    for key, item in json.loads(hbytes)["conditions"].items():
        hs[item["family"],item["sha256"]].append(key)
        ho[item["family"],item["operative_sha256"]].append(key)
    dev = json.loads(mbytes)
    devmap = {}
    with gzip.GzipFile(fileobj=io.BytesIO(archive)) as stream:
        for line in stream:
            key, case = json.loads(line)
            f = hashlib.sha256(packed(case)+b"\n").hexdigest()
            need(f==dev["files"][key], "T4c input file " + key)
            o = digest({k:case[k] for k in ("native","attachment","maintenance")})
            ds[f].append(key)
            do[o].append(key)
            devmap[key]=o
    need(list(devmap)==dev["order"] and len(devmap)==72 and digest(devmap)==d["operative_map_sha256"], "operative reference map")
    seen_f, seen_o = defaultdict(list),defaultdict(list)
    block_stats = {}
    for index,key in enumerate(KEYS):
        row = panel["conditions"][key]
        fam, draw = FAMILIES[index%2], index//2
        need((row["family"],row["draw"],row["block"]) == (fam,draw,draw//12), "identity: "+key)
        f,o = row["sha256"],row["operative_sha256"]
        need(len(bytes.fromhex(f))==len(bytes.fromhex(o))==32, "hash length")
        matches=external["by_condition"][key]
        need(matches=={"t4b_full":hs[fam,f],"t4b_operative":ho[fam,o],"t4c_full":ds[f],"t4c_operative":do[o],
                       "exclude_descriptively":bool(ho[fam,o] or do[o])}, "historical matching: "+key)
        need(internal["by_condition"][key]=={"prior_full":seen_f[f],"prior_operative":seen_o[o]}, "within-panel matching: "+key)
        seen_f[f].append(key);seen_o[o].append(key)
        stats=block_stats.setdefault((fam,draw//12),dict(planned=0,t4b=0,t4c=0,both=0,excluded=0,retained=0))
        a,b=bool(ho[fam,o]),bool(do[o])
        for name,num in (("planned",1),("t4b",a),("t4c",b),("both",a and b),("excluded",a or b),("retained",not (a or b))):
            stats[name]+=int(num)
    need(internal["full_groups"]==[v for v in seen_f.values() if len(v)>1] and
         internal["operative_groups"]==[v for v in seen_o.values() if len(v)>1], "within-panel groups")
    expected=[dict(family=f,block=b,**block_stats[f,b]) for f in FAMILIES for b in range(5)]
    need(external["blocks"]==expected, "ten block denominators")
    return {"conditions":len(KEYS),"historical_exclusions":sum(r["excluded"] for r in expected),
            "within_operative_groups":len(internal["operative_groups"]), "manifest_sha256":sha(folder/LEDGERS[0])}


if __name__=="__main__":
    print(json.dumps(verify(Path(sys.argv[1]) if len(sys.argv)>1 else HERE),ensure_ascii=False))
