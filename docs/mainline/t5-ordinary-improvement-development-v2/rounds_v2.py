"""Run replay screening and pass only original prepaid FIT outcomes to the search code."""
import os
from pathlib import Path

from context_v2 import ACT, LOCK, config, digest, job, need, panel, put, read, sha, verify_learned, verify_sources
from public_ipc import Process
from aegis_improvement_v2.search import identifiers, learn, propose, start


class Replay:
    def __init__(self, history, epoch):
        self.histories = history
        self.log = ACT/"replay"/f"r{epoch}"
        self.log.mkdir(parents=True)
        self.cache = {}
        self.measured = 0

    def __call__(self, track, vector):
        identity = digest([track,vector])
        if identity in self.cache:
            return self.cache[identity]
        requests=[]
        for witness in self.histories:
            pub=witness["pub"]
            policy=dict(track=track,theta=vector,no_probe=False)
            process=Process(track,self.log/(identity+"-"+witness["key"]+".stderr"),policy)
            completed=False
            try:
                process.start(pub)
                responses=[process.choose(pub,view,track,{})["request"] for view in witness["views"]]
                need(len(responses)==61,"entire observable history retained")
                requests.extend(responses)
                completed=True
            finally:
                process.close(failed=not completed)
        self.measured+=1
        self.cache[identity]=digest(requests)
        return self.cache[identity]


def proposal_file(round_no):
    return ACT/"search"/f"proposals-{round_no}.json"


def state_file(round_no):
    return ACT/"search"/f"state-{round_no}.json"


def create_proposals(states, space, u, histories, epoch):
    replay=Replay(histories,epoch)
    proposals={}
    audit={}
    for arm, state in states.items():
        if state.get("terminal"):
            continue
        batch, attempts=propose(space,u,arm,state,epoch,replay)
        proposals[arm]=batch
        audit[arm]=dict(proposed=len(batch),discarded=sum(r["duplicate"] for r in attempts),draws=attempts)
    # Each R/U pair spends the same number of calls if the frozen screen runs out of behavior.
    for track in ("MAIN","HOT"):
        for seed in (1,2,3):
            u_arm,r_arm=(f"{track}-{kind}-{seed}" for kind in ("U","R"))
            slots = min(len(proposals.get(k,[])) for k in (u_arm,r_arm))
            for arm in (u_arm,r_arm):
                if arm not in proposals:
                    continue
                audit[arm]["paid_slots"]=slots
                audit[arm]["unallocated_unique"]=len(proposals[arm])-slots
                audit[arm]["dedup_exhausted"]=len(proposals[arm])<u["batch_size"]
                proposals[arm]=proposals[arm][:slots]
    put(proposal_file(epoch),dict(epoch=epoch,job=job(),inputs=sha(ACT/"inputs.json"),groups=proposals,
                               replay=audit,computed_vectors=replay.measured,facility_entries=0))


def first(manifest,space,u,histories,behavior):
    need(len(manifest["order"]["FIT"])==12,"paired development sample")
    (ACT/"search").mkdir()
    states={arm:start(space,arm,behavior[arm.split("-")[0]]) for arm in identifiers()}
    put(state_file(0),dict(states=states,epoch=0,job=job()))
    create_proposals(states,space,u,histories,1)


def paid_return(label,key,manifest):
    row=ACT/"positions"/label/key
    native=row/"entry.json"
    score=row/"score.json"
    if not score.is_file():
        return dict(charged=native.is_file(),status="MISSING")
    result=read(score)
    entry=read(native)
    need(result["entry"]==entry and entry["label"]==label and entry["key"]==key and entry["input"]==manifest["cases"][key]["sha256"]
         and entry["input_manifest"]==os.environ["T5V2_INPUTS"] and entry["source"]==sha(LOCK)
         and sha(row/"native.jsonl.gz")==result["raw_sha256"],"paid scalar feedback identity")
    return dict(charged=True,status="SCORED",**{field:result[field] for field in ("L","person","tool","fee")})


def advance(epoch):
    verify_sources()
    verify_learned("learned")
    manifest=panel()
    _,space,u=config()
    need(1<=epoch<=u["rounds"],"fixed U rounds")
    previous=read(state_file(epoch-1))["states"]
    batch=read(proposal_file(epoch))
    need(batch["inputs"]==os.environ["T5V2_INPUTS"],"proposals bound before purchase")
    next_states={}
    receipts={}
    folder=ACT/"paid-feedback"
    folder.mkdir(exist_ok=True)
    for arm,state in previous.items():
        if state.get("terminal"):
            next_states[arm]=state
            continue
        candidates=batch["groups"].get(arm,[])
        labels=[state["selected"],*(item["label"] for item in candidates)]
        ratings={label:{digest([manifest["cases"][key]["operative_sha256"],"FIT"]):paid_return(label,key,manifest)
                        for key in manifest["order"]["FIT"]} for label in labels}
        need(all(len(x)==12 for x in ratings.values()),"same FIT pair identities")
        path=folder/f"{arm}-r{epoch}.json"
        put(path,ratings)
        receipts[arm]=dict(file=path.name,sha256=sha(path),charged_new=sum(r["charged"] for x in candidates for r in ratings[x["label"]].values()))
        if any(r["status"]!="SCORED" or not r["charged"] for group in ratings.values() for r in group.values()):
            need(u["stop_on_missing_fit"],"registered terminal status")
            next_states[arm]=dict(state,terminal="INVALID_FIT_FEEDBACK")
            continue
        if not candidates:
            next_states[arm]=dict(state,terminal="REPLAY_SPACE_EXHAUSTED")
            continue
        adaptive=arm.split("-")[1]=="U"
        updated=learn(state,candidates,ratings,u,adaptive)
        updated["history"][-1]["round"]=epoch
        next_states[arm]=updated
    for track in ("MAIN","HOT"):
        for seed in (1,2,3):
            a,b=(f"{track}-{method}-{seed}" for method in ("U","R"))
            pair=(next_states[a],next_states[b])
            if any(x.get("terminal") for x in pair):
                for x in pair:
                    x.setdefault("terminal","MATCHED_PEER_STOP")
            elif all(x["rounds_without_gain"]>=u["patience_rounds"] for x in pair):
                for x in pair:
                    x["terminal"]="MATCHED_PATIENCE"
    out=dict(states=next_states,receipts=receipts,epoch=epoch,job=job(),source=sha(LOCK),proposal_sha256=sha(proposal_file(epoch)))
    put(state_file(epoch),out)
    if epoch<u["rounds"]:
        histories=read(ACT/"public-checks/histories.json")
        need(sha(ACT/"public-checks/histories.json")==read(ACT/"public-checks/result.json")["histories_sha256"],"the same three public histories")
        create_proposals(next_states,space,u,histories,epoch+1)
    else:
        lock={}
        for arm,state in next_states.items():
            lock[arm]=dict(vector=state["vector"],descriptor_sha256=digest(state["vector"]),
                          selected=state["selected"],status=state.get("terminal","ROUNDS_COMPLETE"),history=state["history"])
        put(ACT/"locked.json",dict(job=job(),inputs=sha(ACT/"inputs.json"),source=sha(LOCK),final_round=epoch,arms=lock))
    print("paid FIT round",epoch,"arms",len(receipts),"locked",epoch==u["rounds"],flush=True)


if __name__=="__main__":
    import sys
    advance(int(sys.argv[1]))
