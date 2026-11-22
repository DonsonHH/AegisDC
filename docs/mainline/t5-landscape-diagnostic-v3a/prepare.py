"""Generate only new diagnostic cases and commit replay-filtered vectors before any scoring."""
from collections import Counter
import hashlib
from unittest.mock import patch
import numpy as np

from landscape import (ACT, LOCK, PK, ROOT, V2, V2_REMOTE, check, check_source, config, digest, job, old_identities,
                       operative, packed, read, seed_bytes, sha, stream_int, verify_workers, write)
from aegis_improvement_v2.space import root, uniform


def build_panel(cfg,seed):
    from inputs_v3 import FAMILIES, condition, templates
    check(list(FAMILIES)==cfg["families"],"fixed family order")
    old=old_identities(cfg)
    complete={h for f,_ in old.values() for h in f}
    effective={h for _,o in old.values() for h in o}
    samples=templates()
    folder=ACT/"inputs";folder.mkdir()
    table={};order=[];reject=[];aux=[]
    for half in cfg["halves"]:
        for slot in range(cfg["per_family_half"]):
            for i,family in enumerate(FAMILIES):
                key=f"{half}-{i+1}-{slot+1:02}"
                for attempt in range(cfg["max_input_attempts_per_slot"]):
                    sub=f"{half}|{family}|block0" if attempt==0 else f"{half}|{family}|slot{slot}|retry{attempt}"
                    value=condition(stream_int(seed,cfg["seeds"]["panel"],sub),i,slot,samples)
                    full=hashlib.sha256(packed(value)+b"\n").hexdigest()
                    op=operative(value)
                    if full not in complete and op not in effective:
                        break
                    reject.append(dict(key=key,attempt=attempt,full=full,operative=op))
                else:
                    raise ValueError("Input identity screen exhausted for "+key)
                path=folder/(key+".json");write(path,value)
                check(sha(path)==full,"exact original condition bytes")
                complete.add(full);effective.add(op);order.append(key)
                table[key]=dict(half=half,family=family,slot=slot,attempt=attempt,sha256=full,operative_sha256=op)
                original=value["evaluation"]["original"]
                if family=="RESERVE_TRANSFER" and original["group"]=="mask":
                    aux.append(key)
    check(len(table)==36 and all(n==3 for n in Counter((r["half"],r["family"]) for r in table.values()).values()),
          "balanced halves")
    return order, table, reject, aux


def vector_collection(cfg,seed):
    import rounds_v2
    registered=read(LOCK)["predecessor_evidence"]
    histories=read(V2_REMOTE/"public-checks/histories.json")
    check([q["key"] for q in histories]==cfg["draws"]["history_keys"] and all(len(x["views"])==61 for x in histories),"exact original public frames")
    # Replay's constructor allocates its log at ACT; substitute only our new output directory.
    with patch.object(rounds_v2,"ACT",ACT):
        replay=rounds_v2.Replay(histories,0)
    space=read(V2/"space.json")
    base=root(space,"MAIN")
    base_signature=replay("MAIN",base)
    check(base_signature==registered["root_signature"],"frozen B_cost-start behavior")
    seen={base_signature:"B_COST-root"}
    rng=np.random.Generator(np.random.PCG64(stream_int(seed,cfg["seeds"]["vectors"],"48-accepted")))
    vectors={};draws=[]
    for label in cfg["roles"]["random"]:
        for attempt in range(cfg["draws"]["max_attempts_per_slot"]):
            vector=uniform(space,"MAIN",rng)
            signature=replay("MAIN",vector)
            duplicate=seen.get(signature)
            draws.append(dict(label=label,attempt=attempt,parameters=digest(vector),behavior=signature,duplicate_of=duplicate))
            if duplicate is None:
                seen[signature]=label
                vectors[label]=dict(theta=vector,parameters_sha256=digest(vector),behavior=signature)
                break
        else:
            raise ValueError("Behavior screen exhausted for "+label)
    return vectors,draws


def main():
    check_source()
    verified=verify_workers()
    cfg=config()
    order,table,reject,aux=build_panel(cfg,seed_bytes("panel"))
    vectors,draws=vector_collection(cfg,seed_bytes("vectors"))
    from statistics_v3a import selfcheck
    numerical=selfcheck()
    orig=read(V2/"manual-references.json")["references"]
    locks=read(V2/"locked.json")["arms"]
    references={"B_COST":verified["B_COST"],"V_COST":verified["V_COST"],
                **{k:orig[k]["descriptor_sha256"] for k in ("M","M_HOT")},
                **{k:locks[k]["descriptor_sha256"] for k in cfg["roles"]["reference"] if k.startswith("MAIN-")}}
    check(len(references)==10 and len(vectors)==48 and len(aux)<=6,"declared collection and auxiliary evidence")
    result=dict(schema="T5-v3a-exact-panel-and-replay-accepted-vectors",source=sha(LOCK),job=job(),
        order=order,conditions=table,vectors=vectors,reference_identities=references,identity_only_keys=aux,
        draws=draws,discarded_draws=len(draws)-len(vectors),rejected_input_identities=reject,
        selfcheck=numerical,worker_bundles=verified,native_starts=0,H2_accessed=False)
    write(ACT/"panel-and-strategies.json",result)
    print("registered",len(table),"conditions",len(vectors),"unique vectors",len(draws)-len(vectors),"replay discards",
          len(aux),"structural witnesses",sha(ACT/"panel-and-strategies.json"),flush=True)


if __name__=="__main__":
    main()
