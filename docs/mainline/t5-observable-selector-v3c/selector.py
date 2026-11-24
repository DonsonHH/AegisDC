"""The feature interface contains only a public catalogue and already visible signals."""
DOMAINS=("C","N","LC","LB","LG","NR","NP","NC")
ARCH=(("MAIN",{"C","N"}),("LONDON_STYLE",{"LC","LB","LG"}),("NETHERLANDS_STYLE",{"NR","NP","NC"}))
PRIORITY={"alarm":0,"abnormal_meter":1,"prior":2,"release":3,"status":4}


def catalogue(public):
    return tuple((s["id"],s["key"]) for s in public["subjects"])


def signals(view):
    t=view["time"]
    def visible(r):
        return r["sampled"]<=r["arrived"]<=t<r["until"]
    rows=[]
    for r in view["records"]:
        kind=r["kind"]
        if kind not in ("alarm","prior","release","status") or r["copied_from"] is not None or not visible(r):
            continue
        category="prior:"+str(r.get("record_type") or "UNSPECIFIED") if kind=="prior" else kind
        rows.append((r["arrived"],PRIORITY[kind],r["subject"],category))
    for r in view["fixed"]:
        if r["ok"] is False and visible(r) and r["source"]=="meter/"+r["field"]:
            rows.append((r["arrived"],PRIORITY["abnormal_meter"],r["field"],"abnormal_meter"))
    return rows


def features(static, history):
    ids=dict(static); keys=set(ids.values())
    facility=next((name for name,known in ARCH if keys and keys<=known),"OTHER")
    candidates=[(t,p,"SERVICE" if s=="service" else ids.get(s,"UNSCOPED"),kind)
                for frame in history for t,p,s,kind in frame]
    if not candidates:
        return facility,"NONE","NONE"
    _,_,subject,category=min(candidates)
    return facility,subject,category


def select(locked,cell):
    return locked["cells"].get("|".join(cell),locked["winner"])
