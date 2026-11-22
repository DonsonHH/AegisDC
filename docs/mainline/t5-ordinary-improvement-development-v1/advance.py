"""Expose only paid fit scores to U, persist its proposals, and lock before DEV."""
import os

from context_t5 import ACT, LOCK, PK, TRACKS, cases, digest, job, read, require, settings, sha, verify_sources, write
from run_plan import state_at
from aegis_improvement.improver import MEASURES, update
from aegis_improvement.space import descriptor_id


def group_token(path,label,key):
    entry=path/"native-entry.json"
    scored=path/"score.json"
    base=dict(paid=entry.is_file(),status="MISSING_RETURN")
    if not scored.exists():
        return base
    record=read(scored)
    marker=read(entry)
    require(record["entry"]==marker and marker["label"]==label and marker["key"]==key and marker["input_manifest"]==os.environ["T5_INPUT_SHA"],
            "purchased input and descriptor")
    require(marker["paid"] and sha(path/"original.jsonl.gz")==record["raw_sha256"],"paid original bytes")
    return dict(base,status="SCORED",**{k:record[k] for k in MEASURES})


def main(round_number):
    verify_sources()
    panel=cases()
    _,space,u=settings()
    require(1<=round_number<=u["fit_rounds"],"fixed U rounds")
    current=state_at(round_number-1)
    state_out={}
    receipt={}
    by_track={}
    (ACT/"paid-feedback").mkdir(exist_ok=True)
    for track in TRACKS:
        state=current["tracks"][track]
        if state["terminal"] is not None:
            state_out[track]=state
            continue
        found={}
        refs=[(state["incumbent"],current.get("aliases",{}).get(state["incumbent"],track+"-root"))]
        for i,proposal in enumerate(state["proposals"],1):
            found[descriptor_id(proposal["theta"])]=f"{track}-r{round_number:02}-c{i:02}"
        require(not set(found).intersection(key for key,_ in refs),"genuinely new parameters")
        labels=dict(refs)|found
        keys=panel["order"]["FIT"]
        feedback={name:{digest([panel["conditions"][key]["operative_sha256"],"paid-unit"]):
            group_token(ACT/"positions"/label/key,label,key) for key in keys} for name,label in labels.items()}
        require(all(len(v)==36 for v in feedback.values()),"paired purchased fit panel")
        receipt[track]=dict(fit_feedback_sha256=digest(feedback),labels=labels,paid_present=sum(r["paid"] for key in found for r in feedback[key].values()))
        write(ACT/"paid-feedback"/f"{track}-r{round_number:02}.json",feedback)
        # Only these projected values are passed to U.
        updated=update(space,u,state,feedback)
        state_out[track]=updated
        by_track.update(found)
    data=dict(round=round_number,stage=round_number,tracks=state_out,feedback=receipt,
              aliases=current.get("aliases",{})|by_track,job=job(),source=sha(LOCK))
    # Digest and proposed/selected vectors stay linked to the scorer ledger.
    write(ACT/"search"/f"round-{round_number:02}.json",data)
    if all(x["terminal"] is not None for x in state_out.values()):
        write(ACT/"locked.json",dict(rounds=round_number,job=job(),source=sha(LOCK),U=sha(PK/"U.json"),
            tracks={t:dict(theta=s["parent"],descriptor=s["incumbent"],status=s["terminal"],history=s["history"],
                            source_label=data["aliases"].get(s["incumbent"],t+"-root")) for t,s in state_out.items()}))
    print("paid round",round_number,"terminal",[(t,s["terminal"]) for t,s in state_out.items()],flush=True)


if __name__=="__main__":
    import sys
    main(int(sys.argv[1]))
