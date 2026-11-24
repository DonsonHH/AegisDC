"""Between frozen batches: read the terminal accounting database, do not run a policy."""
import sys

from control_v3c import BATCHES,OUT,accounting,check,read,save


def verify(names):
    rows=[]
    for name in names:
        reg=read(OUT/"registrations"/(name+".json"));terminal=read(OUT/"jobs"/name/"terminal.json")
        a=accounting(reg["job"])
        check(terminal["job"]==a["JobID"] and reg["reserved_s"]==a["reserved_s"],"batch and allocation identities")
        rows.append(dict(name=name,job=a["JobID"],exit=a["ExitCode"],states=terminal["states"],
                         reserved_s=reg["reserved_s"],actual_cpu_s=a["process_s"],
                         compliant=reg["reserved_s"]<=2*a["process_s"]))
    result=dict(through=names[-1],rows=rows,proceed=all(r["compliant"] for r in rows))
    dest=OUT/"admissions";dest.mkdir(exist_ok=True)
    save(dest/(names[-1]+".json"),result)
    print("verified",len(rows),"complete allocations; proceed",result["proceed"],flush=True)
    check(result["proceed"],"actual job reservation above 2x: stop next admissions and report")


if __name__=="__main__":
    n=sys.argv[1]
    verify((["pilot"]+list(BATCHES[:BATCHES.index(n)+1])) if n!="pilot" else ["pilot"])
