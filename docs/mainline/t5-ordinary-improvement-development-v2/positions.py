"""Derive paid groups and the locked evaluation arms from durable round records."""
from collections import Counter
import math

from context_v2 import ACT, PK, config, need, read
from aegis_improvement_v2.search import identifiers
from aegis_improvement_v2.space import root


def forecast_groups(manifest, epoch):
    _, _, u = config()
    history = read(ACT/"search"/f"proposals-{epoch}.json")
    need(history["epoch"] == epoch, "paid round identity")
    labels = ["MAIN-root", "HOT-root"] if epoch == 1 else []
    labels += [r["label"] for batch in history["groups"].values() for r in batch]
    return split_groups(manifest, labels, "FIT", f"fit-{epoch}")


def pilot(manifest):
    history = read(ACT/"search/proposals-1.json")["groups"]
    origins = ("MAIN-U-1","HOT-R-1")
    need(all(history[arm] for arm in origins), "pilot includes new U and R strategies")
    labels = ["MAIN-root", "HOT-root", *(history[arm][0]["label"] for arm in origins)]
    first = manifest["order"]["FIT"][:6]
    need(len({manifest["cases"][k]["family"] for k in first})==6,"one pilot in each family")
    return [(label,key) for label in labels for key in first]


def dev_labels():
    design, _, _ = config()
    arms = identifiers()
    return design["references"] + arms + [arm+"-NP" for arm in arms if arm.startswith("HOT-")]


def split_groups(manifest, labels, domain, prefix):
    design, _, _ = config()
    known = set(pilot(manifest)) if domain=="FIT" and prefix=="fit-1" else set()
    slots = [(label,key) for label in labels for key in manifest["order"][domain] if (label,key) not in known]
    size = design["offload"]["position_batch_size"]
    return {f"{prefix}-{i//size+1:02}":slots[i:i+size] for i in range(0,len(slots),size)}


def dev_groups(manifest):
    locked = read(ACT/"locked.json")
    need(set(locked["arms"])==set(identifiers()),"all three seeds locked on both arms of each track")
    return split_groups(manifest,dev_labels(),"DEV","dev")


def binding(label):
    design, space, _ = config()
    if label in design["references"]:
        if label in ("M","M_HOT"):
            reference = read(PK/"manual-references.json")["references"][label]
            return {"track":reference["track"],"theta":reference["theta"],"no_probe":False}, True
        return None,False
    if label in ("MAIN-root","HOT-root"):
        track=label.split("-")[0]
        return dict(track=track,theta=root(space,track),no_probe=False),False
    if "-r" in label:
        epoch=int(label.split("-r")[1].split("-")[0])
        grouped=read(ACT/"search"/f"proposals-{epoch}.json")["groups"]
        item=next(q for batch in grouped.values() for q in batch if q["label"]==label)
        return dict(track=label.split("-")[0],theta=item["vector"],no_probe=False),False
    item=read(ACT/"locked.json")["arms"][label.removesuffix("-NP")]
    return dict(track=label.split("-")[0],theta=item["vector"],no_probe=label.endswith("-NP")),False


def projection(wall, records):
    design, _, u = config()
    future_fit=2*12+len(identifiers())*u["batch_size"]*u["rounds"]*12-design["pilot"]["positions"]
    future_dev=len(dev_labels())*24
    size=design["offload"]["position_batch_size"]
    minutes=math.ceil((2*(1.2*wall+8)+6)/60)
    # Both panels split on even batch boundaries, with even remainders.
    jobs=len(records)+math.ceil(future_fit/size)+math.ceil(future_dev/size)+u["rounds"]+1
    seconds=sum(r["reserved_cpu_s"] for r in records)+60*minutes*(future_fit+future_dev)//2
    seconds+=60*(u["rounds"]*design["offload"]["per_update_minutes"]+design["offload"]["final_minutes"])
    return dict(positions=design["pilot"]["positions"]+future_fit+future_dev, minutes=minutes,
                projected_jobs=jobs,projected_reserved_cpu_s=seconds,proceed=jobs<=design["max_jobs"] and seconds<=design["max_reserved_cpu_s"])
