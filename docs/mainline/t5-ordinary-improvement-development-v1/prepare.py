"""Materialize the authorized development panels, and test the frozen starts before facility use."""
from collections import Counter
from copy import deepcopy
import hashlib

from context_t5 import (
    ACT, LOCK, PK, PUBLIC, ROOT, T4B, TRACKS, compact, digest, job, operative, read,
    require, settings, sha, verify_bundles, verify_sources, write,
)


def build_bundle():
    refs,members=verify_bundles()
    identity,root=refs["V_COST"]
    sources={k:root/k for k in members[identity]}
    paths=read(LOCK)["files"]
    for k in paths:
        if k.startswith("src/aegis_improvement/") and k.endswith(".py") and not k.endswith("improver.py"):
            sources[k.removeprefix("src/")]=ROOT/k
    for name in ("__init__.py","rule.py"):
        rel="aegis_cost_baseline/"+name
        sources[rel]=ROOT/"src"/rel
    sources["parameter-space.json"]=PK/"parameter-space.json"
    PUBLIC.mkdir()
    pins={}
    for name,pinned in sources.items():
        dest=PUBLIC/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open("xb") as stream:
            stream.write(pinned.read_bytes())
        pins[name]=sha(dest)
    write(ACT/"worker-bundle.json",dict(bundle=digest(pins),members=pins))
    verify_bundles(learned=True)


def materialize(design):
    from inputs_v3 import FAMILIES, condition, templates

    seed=(ACT/"private/development-seed.bin").read_bytes()
    expected=read(PK/"development-seed-commitment.json")["sha256"]
    require(len(seed)==32 and hashlib.sha256(seed).hexdigest()==expected,"new development seed")
    index=T4B/"condition-summary.json"
    require(index==ROOT/design["duplicates"]["forbidden_meta_path"],"designated public identity reference only")
    # T4b identities are public commitments. No previous scenario or score is loaded.
    held=read(index)["conditions"]
    require(len(held)==144,"complete previous identity corpus")
    used_full={x["sha256"] for x in held.values()}
    used_op={x["operative_sha256"] for x in held.values()}
    source=templates()
    folder=ACT/"inputs"
    folder.mkdir()
    result={}
    order={}
    attempts={}
    for split,per_family in (("FIT",design["fit_cases_per_family"]),("DEV",design["evaluation_cases_per_family"])):
        order[split]=[]
        draws=[block*12+s for block in range(design["per_family_blocks"]) for s in range(per_family//2)]
        for slot,draw in enumerate(draws,1):
            for fi,family in enumerate(FAMILIES):
                key=f"{split.lower()}-{fi+1}-{slot:02}"
                for n in range(design["duplicates"]["attempts_per_slot"]):
                    stream=hashlib.sha256(seed+f"|AegisDC/T5/development/v1|{split}|{family}|{draw}|{n}".encode()).digest()
                    candidate=condition(int.from_bytes(stream,"big"),fi,draw,source)
                    full=hashlib.sha256(compact(candidate)+b"\n").hexdigest()
                    operative_sha=operative(candidate)
                    if full not in used_full and operative_sha not in used_op:
                        break
                else:
                    raise ValueError("Committed development sampling slot exhausted: "+key)
                path=folder/(key+".json")
                write(path,candidate)
                require(sha(path)==full and candidate["evaluation"]["family"]==family,"generated identity")
                result[key]=dict(family=family,split=split,draw=draw,attempt=n,sha256=full,operative_sha256=operative_sha,
                                 duration_s=candidate["maintenance"]["exposure_s"])
                attempts[key]=n
                order[split].append(key)
                used_full.add(full)
                used_op.add(operative_sha)
    require(len(result)==84,"frozen panel size")
    for split,per_family in (("FIT",6),("DEV",8)):
        require(Counter(result[k]["family"] for k in order[split])==dict.fromkeys(FAMILIES,per_family),"family allocation")
    output=dict(schema="T5-committed-development-inputs-v1",conditions=result,order=order,seed_sha256=expected,
                prior_public_identity_sha256=sha(index),prior_condition_count=len(held),collision_rejected=sum(attempts.values()),
                job=job(),source_sha256=sha(LOCK),H2_accessed=False)
    write(ACT/"inputs.json",output)
    return output


def equivalent(space,folder):
    from isolation import history
    from isolation_guard import history_frames
    from public_process import Process
    from aegis_improvement.space import initial

    refs,_=verify_bundles(learned=True)
    tests=[]
    for key in ("2-02","5-04","6-02"):
        pub,views,*_=history(key)
        for track,role in (("MAIN","B_COST"),("HOT","V_COST")):
            old=Process(role,folder/(key+"-"+role+".stderr"),reference=refs[role])
            new=Process(track,folder/(key+"-"+track+".stderr"),descriptor=dict(track=track,theta=initial(space,track),no_probe=False))
            ended=False
            try:
                old.start(pub)
                new.start(pub)
                for view in history_frames(views,600):
                    require(old.choose(pub,view,role,{})==new.choose(pub,view,track,{}),"starting rules differ on "+key+" "+track)
                require(len(old.events)==61,"complete decision clock")
                tests.append(dict(key=key,track=track,public_frames=61,transcript=digest(old.events)))
                ended=True
            finally:
                old.close(failed=not ended)
                new.close(failed=not ended)
    pub,views,*_=history("5-04")
    for bad in ("private","future"):
        child=Process("MAIN",folder/(bad+".stderr"),descriptor=dict(track="MAIN",theta=initial(space,"MAIN"),no_probe=False))
        try:
            child.start(pub)
            frame=deepcopy(views[0])
            if bad=="private":
                frame["private_test_field"]=True
            else:
                frame["records"][0]["arrived"]=frame["time"]+60
            try:
                child.message({"view":frame})
            except RuntimeError:
                continue
            raise ValueError("Unregistered evidence accepted")
        finally:
            child.close(failed=True)
    return tests


def search_witness(space,u):
    from aegis_improvement.improver import roots,update
    from aegis_improvement.space import descriptor_id

    marks={}
    for track in TRACKS:
        state=roots(space,u,track)
        ids=[state["incumbent"],*(descriptor_id(q["theta"]) for q in state["proposals"])]
        df={}
        for i,key in enumerate(ids):
            df[key]={str(j):dict(paid=True,status="SCORED",L=100-i,person=40,tool=40,fee=1) for j in range(36)}
        a=update(space,u,state,df)
        other=deepcopy(df)
        for record in other[ids[1]].values():
            record["L"]=0
        b=update(space,u,state,other)
        require(a["incumbent"]==ids[3] and b["incumbent"]==ids[1] and a["proposals"]!=b["proposals"],
                "paid feedback must affect the next search state")
        marks[track]=[a["incumbent"],b["incumbent"]]
    return marks


def main():
    verify_sources()
    design,space,u=settings()
    from aegis_improvement.improver import roots
    from aegis_improvement.space import initial

    require(read(PK/"initial-policies.json")["policies"]=={t:initial(space,t) for t in TRACKS},
            "identical preregistered policy vectors")

    build_bundle()
    output=materialize(design)
    folder=ACT/"initial-checks"
    folder.mkdir()
    tests=equivalent(space,folder)
    marks=search_witness(space,u)
    write(folder/"result.json",dict(job=job(),input_sha256=sha(ACT/"inputs.json"),exact_initial=tests,
        negative_guards=["private","future"],feedback_witness=marks,native_entries=0,tracks=list(TRACKS)))
    (ACT/"search").mkdir()
    write(ACT/"search/round-00.json",dict(stage=0,tracks={k:roots(space,u,k) for k in TRACKS},job=job(),source=sha(LOCK)))
    print("Development inputs",len(output["conditions"]),"and zero-facility witnesses",len(tests),flush=True)


if __name__=="__main__":
    main()
