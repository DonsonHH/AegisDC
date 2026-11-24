"""On a verified allocation failure: retain all 327 denominators, never run or resubmit."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

from control_v3c import OUT,targets,read,save


def inventory():
    panel=read(OUT/"panel.json")
    pilot,groups=targets(panel["order"]);groups={"pilot":pilot,**groups}
    index=[]
    for name,positions in groups.items():
        r=OUT/"registrations"/(name+".json");jid=read(r)["job"] if r.is_file() else None
        for key,role in positions:
            root=OUT/"positions"/key/role
            row=root/"row.json"; entry=root/"entry.json"; raw=root/"original.jsonl.gz"
            item=dict(key=key,arm=role,batch=name,job=jid,entered=entry.is_file(),raw_present=raw.is_file())
            if row.exists():
                item["row_sha256"]=hashlib.sha256(row.read_bytes()).hexdigest()
                try:
                    value=read(row);item.update(state=value["status"],error=value.get("error"))
                except (OSError,ValueError,KeyError) as err:
                    item.update(state="INCOMPLETE_ROW",error=str(err))
            else:item["state"]="ENTERED_NO_RETURN" if entry.exists() else "REGISTERED_NO_ENTRY" if jid else "UNSUBMITTED"
            index.append(item)
    assert len(index)==len({(r["key"],r["arm"]) for r in index})==327
    return dict(positions=index,planned=327,states=dict(Counter(r["state"] for r in index)),facility_calls_from_markers=sum(r["entered"] for r in index),
                scientific_endpoint="NOT_RECONSTRUCTED_FROM_PARTIAL_RUN")


if __name__=="__main__":
    save(OUT/"stopped-inventory.json",inventory())
