"""Map a published panel and frozen U state to the next registered paid evaluations."""
from context_t5 import ACT, TRACKS, read, require, settings


def state_at(round_number):
    return read(ACT/"search"/f"round-{round_number:02}.json")


def expected_positions(manifest, name):
    design,space,u=settings()
    pilot={key for key in manifest["order"]["FIT"][:design["pilot"]["families"]]}
    if name=="pilot":
        return [(r,k) for k in manifest["order"]["FIT"] if k in pilot for r in design["pilot"]["roles"]]
    if name.startswith("dev-"):
        _,part,role=name.split("-",2)
        lock=read(ACT/"locked.json")
        require(lock["rounds"]<=u["fit_rounds"] and role in design["evaluation_roles"],"registered final role")
        keys=manifest["order"]["DEV"]
        offset=24*(int(part)-1)
        require(part in ("1","2"),"registered development split")
        return [(role,k) for k in keys[offset:offset+24]]
    track,part,*suffix=name.split("-")
    require(track in TRACKS,"registered search track")
    if part=="root":
        require(not suffix,"original parent name")
    else:
        current=int(part[1:])
        state=state_at(current-1)["tracks"][track]
        require(state["terminal"] is None and state["round"]==current,"proposals bound to historical paid round")
        require(len(suffix)==1 and 1<=int(suffix[0][1:])<=len(state["proposals"]),"registered proposal index")
    include=manifest["order"]["FIT"]
    if name in design["pilot"]["roles"]:
        include=[k for k in include if k not in pilot]
    return [(name,k) for k in include]


def descriptor(name):
    from aegis_improvement.space import initial
    design,space,_=settings()
    if name in ("P","B","B_COST","V_COST","V_COST_NOPROBE"):
        return None
    if name in ("MAIN","HOT","HOT_NOPROBE"):
        locked=read(ACT/"locked.json")
        track=name.split("_")[0]
        return dict(track=track,theta=locked["tracks"][track]["theta"],no_probe=name.endswith("_NOPROBE"))
    track,part,*suffix=name.split("-")
    theta=initial(space,track) if part=="root" else state_at(int(part[1:])-1)["tracks"][track]["proposals"][int(suffix[0][1:])-1]["theta"]
    return dict(track=track,theta=theta,no_probe=False)


def fit_groups(round_number):
    _,_,u=settings()
    states=state_at(round_number-1)["tracks"]
    roots=[f"{t}-root" for t in TRACKS] if round_number==1 else []
    return roots+[f"{t}-r{round_number:02}-c{i+1:02}" for t in TRACKS if states[t]["terminal"] is None
                  for i in range(u["candidates_per_round"])]


def projection(pilot_wall,previous):
    import math
    d,_,u=settings()
    minutes=math.ceil((2*(1.2*pilot_wall+8)+6)/60)
    # Four pilot roles each finish with 30 remaining, all other FIT roles require 36.
    fit_lanes=4*15+(2*(1+u["fit_rounds"]*u["candidates_per_round"])-4)*18
    final_lanes=len(d["evaluation_roles"])*24
    jobs=len(previous)+2*(1+u["fit_rounds"]*u["candidates_per_round"])+2*len(d["evaluation_roles"])+u["fit_rounds"]+1
    reserve=sum(r["reserved"] for r in previous)+60*minutes*(fit_lanes+final_lanes)+60*(3*u["fit_rounds"]+12)
    return dict(minutes_per_two_positions=minutes,projected_jobs=jobs,projected_reserved_cpu_s=reserve,
                continue_=jobs<=d["max_jobs"] and reserve<=d["max_reserved_cpu_s"])
