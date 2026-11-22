"""Commit disjoint development inputs and check the roots and behavior lower bound."""
from collections import Counter
from copy import deepcopy
import hashlib

from context_v2 import ACT, LOCK, PK, ROOT, V1, config, digest, job, need, operative, packed, put, read, references, sha, verify_bundle, verify_sources
from public_ipc import Process
from aegis_improvement_v2.space import root


def make_inputs(design):
    from inputs_v3 import FAMILIES, condition, templates

    seed=(ACT/"private/development-seed.bin").read_bytes()
    commitment=read(PK/"development-seed-commitment.json")["sha256"]
    need(len(seed)==32 and hashlib.sha256(seed).hexdigest()==commitment,"registered v2 development seed")
    need(list(FAMILIES)==design["families"],"original family law")
    corpora=design["filters"]["public_identity_corpora"]
    indices=[read(ROOT/f) for f in corpora]
    held=[indices[0]["conditions"],indices[1]["conditions"]]
    need([len(c) for c in held]==[144,84],"complete public exclusion registers")
    prior_full={x["sha256"] for c in held for x in c.values()}
    prior_op={x["operative_sha256"] for c in held for x in c.values()}
    source=templates()
    order={}; table={}; rejected=[]
    (ACT/"inputs").mkdir()
    for split in ("FIT","DEV"):
        order[split]=[]
        for slot,draw in enumerate(design["panel_draw_slots"][split],1):
            for family_i,family in enumerate(FAMILIES):
                key=f"{split.lower()}-{family_i+1}-{slot:02}"
                for attempt in range(design["attempts_per_slot"]):
                    name=f'{design["sampling_seed_domain"]}|{split}|{family}|{draw}|{attempt}'
                    raw=hashlib.sha256(seed+b"|"+name.encode()).digest()
                    sample=condition(int.from_bytes(raw,"big"),family_i,draw,source)
                    full=hashlib.sha256(packed(sample)+b"\n").hexdigest()
                    operation=operative(sample)
                    if full not in prior_full and operation not in prior_op:
                        break
                    rejected.append(dict(key=key,attempt=attempt,full=full,operative=operation))
                else:
                    raise ValueError("Open sampling slot: "+key)
                put(ACT/"inputs"/(key+".json"),sample)
                prior_full.add(full);prior_op.add(operation)
                table[key]=dict(family=family,split=split,draw=draw,attempt=attempt,sha256=full,operative_sha256=operation,
                    duration_s=sample["maintenance"]["exposure_s"])
                order[split].append(key)
    need(len(table)==36,"registered development denominators")
    result=dict(schema="T5-v2-ordered-development-inputs",source=sha(LOCK),seed=commitment,job=job(),order=order,cases=table,
        public_exclusion_registers={f:sha(ROOT/f) for f in corpora},rejected=rejected)
    put(ACT/"inputs.json",result)
    return result


def make_bundles():
    checkout=read(LOCK)["files"]
    refs=references()
    for identity,folder,files in {(h,r,tuple(sorted(f.items()))) for h,r,f in refs.values()}:
        need(verify_bundle(folder,dict(files))==identity,"accepted reference bundle")
    public=ACT/"public"
    public.mkdir()
    _,base,pins=refs["V_COST"]
    inventory={}
    common={f:base/f for f in pins}
    for file in ("__init__.py","rule.py"):
        rel="aegis_cost_baseline/"+file
        common[rel]=ROOT/"src"/rel
    for label in ("manual","learned"):
        sources=dict(common)
        old="aegis_improvement"
        for file in ("__init__.py","policy.py","space.py"):
            rel=old+"/"+file
            sources[rel]=ROOT/"src"/rel
        if label=="manual":
            sources[old+"/worker.py"]=ROOT/"src"/old/"worker.py"
            sources["parameter-space.json"]=V1/"parameter-space.json"
        else:
            for file in ("__init__.py","policy.py","space.py","worker.py"):
                rel="aegis_improvement_v2/"+file
                sources[rel]=ROOT/"src"/rel
            sources["space.json"]=PK/"space.json"
        folder=public/label
        folder.mkdir()
        written={}
        for name,origin in sources.items():
            if origin.is_relative_to(ROOT):
                need(checkout[origin.relative_to(ROOT).as_posix()]==sha(origin),"frozen public member")
            target=folder/name
            target.parent.mkdir(exist_ok=True,parents=True)
            with target.open("xb") as out:
                out.write(origin.read_bytes())
            written[name]=sha(target)
        inventory[label]=dict(sha256=verify_bundle(folder,written),files=written)
    put(ACT/"bundle-index.json",inventory)


def public_histories(design):
    from isolation import history
    from isolation_guard import history_frames

    records=[]
    for key in design["replay"]["keys"]:
        pub,frames,_,raw_sha=history(key)
        frames=list(history_frames(frames,600))
        need(len(frames)==design["replay"]["clocks"],"all 61 clocks per history")
        records.append(dict(key=key,pub=pub,views=frames,original_sha256=raw_sha,frame_sha256=digest(frames)))
    return records


def isolated_choice(track, vector, pub, frames, directory):
    token=digest([track,vector,pub,frames])[:24]
    worker=Process(track,directory/(token+".stderr"),dict(track=track,theta=vector,no_probe=False))
    ended=False
    try:
        worker.start(pub)
        responses=[worker.choose(pub,frame,track,{}) for frame in frames]
        ended=True
        return responses
    finally:
        worker.close(failed=not ended)


def check_behavior(space,histories,folder):
    import public_work as work
    from aegis_action_cost.permit import Gate
    from aegis_cost_baseline import rule as bc
    from aegis_improvement_v2.policy import Policy
    settings=read(ROOT/"src/aegis_risk_dispatch/settings.json")
    settings["maintenance_capacity"]=0.5
    base=root(space,"MAIN")
    template={s["key"]:r for r in histories for s in r["pub"]["subjects"] if s["primary"]}
    records=[]
    for kind in space["action_types"]:
        original=template[kind]
        for band,slack in enumerate((60,120,180,240,360)):
            pub=deepcopy(original["pub"])
            sub=next(s for s in pub["subjects"] if s["key"]==kind and s["primary"])
            sid=sub["id"]
            pub["routes"]=[sid]
            pub["subjects"]=[sub]
            sub["allow_initial"]=False
            pub["workforce"]["shifts"][sub["worker"]]=[0,3600]
            sub["write_window"]=[0,work.duration(pub,sub,sub["start"])+slack+1]
            order=dict(kind="order",subject=sid,source="public-guard",origin="order/"+sid,copied_from=None,
                       value="OPEN/MAINT-600",sampled=0,arrived=0,until=3601)
            frame=dict(time=0,records=[order],work=[],paid=[],writes=[],fixed=[],issued=[])
            if kind in ("NC","NP"):
                v="HANDOVER_RELEASED" if kind=="NC" else "POWER_RETURNED"
                t="release" if kind=="NC" else "status"
                frame["records"].append(dict(order,kind=t,value=v,origin="permission/"+sid))
            starts=bc.legal_times(pub,frame,sub,Gate(180))
            need(starts and starts[-1]==slack,"legal witness with specified slack")
            coordinate=f"{kind}.deadline_{band}"
            # Other deadline cells are set to their high level to check that they cannot affect this decision.
            variant={**base,**{p["id"]:120 for p in space["coordinates"] if ".deadline_" in p["id"]}}
            decisions=[]
            for level in (0,120):
                variant[coordinate]=level
                response=Policy(space,settings,"MAIN",dict(variant)).dispatch(pub,frame)
                decisions.append(response["request"]["task"] if response["request"] else None)
            original_request=Policy(space,settings,"MAIN",base).dispatch(pub,frame)["request"]
            need(original_request is None and decisions==[None,sid+"::A"],"separable deadline coordinate "+coordinate)
            records.append(dict(coordinate=coordinate,slack_s=slack,frame_sha256=digest([pub,frame]),actual=decisions))
    need(len(records)==40,"40 independent binary decisions")
    return dict(lower_bound=2**len(records),witnesses=records)


def check_roots(space,histories,folder):
    outputs=[]; root_behavior={}
    for track,reference in (("MAIN","B_COST"),("HOT","V_COST")):
        requests=[]
        for h in histories:
            frozen=Process(reference,folder/(track+"-"+h["key"]+"-ref.stderr"))
            ended=False
            try:
                frozen.start(h["pub"])
                saved=[frozen.choose(h["pub"],frame,reference,{}) for frame in h["views"]]
                fresh=isolated_choice(track,root(space,track),h["pub"],h["views"],folder)
                need(fresh==saved,"starting policy equals original "+track)
                requests.extend(r["request"] for r in fresh)
                outputs.append(dict(track=track,key=h["key"],frames=len(fresh),full_response_sha256=digest(fresh)))
                ended=True
            finally:
                frozen.close(failed=not ended)
        root_behavior[track]=digest(requests)
    # Ensure the v2 decisions reject future and private-evaluator fields at the same closed interface.
    pub=histories[0]["pub"]
    for negative in ("private","future"):
        child=Process("MAIN",folder/(negative+".stderr"),dict(track="MAIN",theta=root(space,"MAIN"),no_probe=False))
        frame=deepcopy(histories[0]["views"][0])
        if negative=="private":
            frame["private_test_field"]=True
        else:
            frame["records"][0]["arrived"]=frame["time"]+60
        refused=False
        try:
            child.start(pub)
            try:
                child.message({"view":frame})
            except RuntimeError:
                refused=True
        finally:
            child.close(failed=True)
        need(refused,"public gate rejected "+negative)
    return outputs,root_behavior


def main():
    verify_sources()
    design,space,u=config()
    manifest=make_inputs(design)
    make_bundles()
    folder=ACT/"public-checks"
    folder.mkdir()
    histories=public_histories(design)
    put(folder/"histories.json",histories)
    roots,root_behavior=check_roots(space,histories,folder)
    bound=check_behavior(space,histories,folder)
    credit_witness=check_feedback(space,u)
    put(folder/"result.json",dict(job=job(),inputs=sha(ACT/"inputs.json"),native_entries=0,roots=roots,root_behavior=root_behavior,
        rejected=["private","future"],lower_bound=bound,credit_witness=credit_witness,histories_sha256=sha(folder/"histories.json")))
    from rounds_v2 import first
    first(manifest,space,u,histories,root_behavior)
    print("development panels",len(manifest["cases"]),"initial frames",sum(r["frames"] for r in roots),"behavior bound",bound["lower_bound"],flush=True)


def check_feedback(space,u):
    from aegis_improvement_v2.search import generator, learn, mutate, start

    proofs={}
    for track in ("MAIN","HOT"):
        arm=f"{track}-U-1"
        parent=root(space,track)
        round_state=start(space,arm,"public-test-history")
        for index in range(64):
            rng=generator(u,arm+"-self-check",index)
            one,op=mutate(space,track,parent,{},u,rng)
            two,other=mutate(space,track,parent,{},u,rng)
            if op!=other:
                break
        else:
            raise ValueError("Two generated search test operators")
        batch=[dict(label=label,vector=v,operator=o,parameters_sha256=digest(v),behavior=digest([label,v]))
               for label,v,o in (("first",one,op),("second",two,other))]
        proposed=[]
        for winner in ("first","second"):
            ratings={k:{"public-test":dict(charged=True,status="SCORED",L=35 if k==winner else 100,person=10,tool=10,fee=1)}
                     for k in (track+"-root","first","second")}
            state=learn(round_state,batch,ratings,u,adaptive=True)
            for index in range(64):
                if generator(u,arm+"-credit-test",index).random()>=u["random_operator_probability"]:
                    break
            rng=generator(u,arm+"-credit-test",index)
            vector,operator=mutate(space,track,parent,state["credit"],u,rng)
            proofs.setdefault(track,[]).append(dict(selected=state["selected"],operator=operator,parameters_sha256=digest(vector)))
            proposed.append(operator)
        need(proposed==[op,other],"FIT feedback changes the proposal operator under a fixed RNG")
    return proofs


if __name__=="__main__":
    main()
