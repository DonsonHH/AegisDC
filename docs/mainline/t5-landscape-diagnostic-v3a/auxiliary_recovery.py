"""Bind the original no-action worker for the two retained pre-entry auxiliary failures."""
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

from landscape import ACT, LOCK, PK, batches, check, check_source, config, job, manifest, read, sha, write

NAME="identity-witness-a2"
AUX=ACT/"auxiliary-P-a2"


def prior_failure():
    m=manifest();cfg=config()
    prior=read(ACT/"registrations/identity-witness.json")
    terminal=read(ACT/"batches/identity-witness/terminal.json")
    record=read(PK/"auxiliary-recovery.json")
    check(sha(Path(__file__))==record["wrapper_sha256"] and sha(LOCK)==record["source_freeze_sha256"],"recovery source")
    check(sha(ACT/"batches/identity-witness/terminal.json")==record["first_terminal_sha256"] and
          prior["job"]==terminal["job"]==record["first_job"],"retained first allocation")
    lanes=batches(m,cfg)["identity-witness"]
    check(prior["slots"]==[list(x) for x in lanes[0]] and
          all(not q["entered"] and not q["scored"] and q["exit_code"]==1 for q in terminal["positions"]),
          "pre-native estimator failure only")
    for _,k in lanes[0]:
        folder=ACT/"positions"/"P"/k
        check(not (folder/"native-entry.json").exists() and not (folder/"score.json").exists()
              and not (folder/"original.jsonl.gz").exists(),"original first attempt contained no facility call or score")
    return record,lanes


def registered(name,records):
    import schedule_landscape as sl
    if name==NAME:
        recovery,lanes=prior_failure()
        original=next(r for r in records if r["name"]=="identity-witness")
        check(sl.statuses([original])[original["job"]][1:3]==["COMPLETED","0:0"],"settled original accounting")
        check(not AUX.exists() and len(lanes)==1,"unique auxiliary retry")
        check(read(ACT/"pilot-budget.json")["proceed"],"same pilot release")
        return Path(__file__).name,["run"],lanes,1,recovery["minutes"],"4G"
    check(name=="analyse","only the two explicit entry points")
    return None


def submit(name):
    import schedule_landscape as sl
    check_source(compute=False)
    original=sl.choose
    def choice(label,records):
        if label==NAME:
            return registered(label,records)
        script,args,lanes,cpus,minutes,memory=original(label,records)
        check(label=="analyse" and script=="analyse_landscape.py","frozen saved-only analysis")
        return Path(__file__).name,["readback"],lanes,cpus,minutes,memory
    sys.argv[:]=[sys.argv[0],"submit",name]
    with patch.object(sl,"choose",choice):
        sl.main()


def run():
    tree=check_source()
    _,lanes=prior_failure()
    reg=read(ACT/"registrations"/(NAME+".json"))
    check(reg["job"]==job() and reg["panel"]==os.environ["V3A_PANEL"] and
          reg["slots"]==[list(x) for x in lanes[0]],"supplemental registered inputs")
    AUX.mkdir()
    (AUX/"positions").mkdir()
    # Only new P position files live here; both attempts use the same durable central job ledger.
    (AUX/"batches").symlink_to(ACT/"batches",target_is_directory=True)
    (AUX/"registrations").symlink_to(ACT/"registrations",target_is_directory=True)
    folder=ACT/"batches"/NAME;folder.mkdir()
    write(folder/"entry.json",dict(job=job(),slots=reg["slots"],core_tree=tree))
    start=time.monotonic();rows=[];lane=sorted(os.sched_getaffinity(0))[0]
    for label,key in lanes[0]:
        with (folder/(label+"-"+key+".log")).open("x") as stream:
            ret=subprocess.run([sys.executable,"-B",str(Path(__file__).resolve()),"unit",key,str(lane)],
                               stdout=stream,stderr=subprocess.STDOUT,check=False)
        dst=AUX/"positions"/label/key
        rows.append(dict(label=label,key=key,exit_code=ret.returncode,entered=(dst/"native-entry.json").exists(),
                         scored=(dst/"score.json").exists()))
    write(folder/"terminal.json",dict(job=job(),positions=rows,wall_s=time.monotonic()-start))
    print("additional P scores",sum(q["scored"] for q in rows),"of",len(rows),flush=True)


def unit(key,lane):
    import public_ipc
    import score_positions
    from context_v2 import references, verify_bundle

    refs=references()
    identity,base,files=refs["V_COST"]
    check(verify_bundle(base,files)==identity and key in manifest()["identity_only_keys"],"exact frozen P executable")
    # V3's accepted public worker has P on its role whitelist and calls public_work.choose for P.
    # Restore this role's mapping locally without changing any file in the frozen bundle.
    with patch.object(public_ipc,"references",lambda:dict(refs,P=(identity,base,files))),patch.object(score_positions,"ACT",AUX):
        score_positions.unit(NAME,"P",key,lane)


def readback():
    import analyse_landscape as analysis
    from context_v2 import references
    prior_failure()
    original=analysis.audit_score
    actual=read(ACT/"registrations"/(NAME+".json"))
    def route(label,key,case,panel,registration,worker_ids):
        if label!="P":
            return original(label,key,case,panel,registration,worker_ids)
        with patch.object(analysis,"ACT",AUX):
            return original(label,key,case,panel,actual,dict(worker_ids,P=references()["V_COST"][0]))
    with patch.object(analysis,"audit_score",route):
        analysis.main()


if __name__=="__main__":
    action=sys.argv[1]
    if action=="submit":submit(sys.argv[2])
    elif action=="run":run()
    elif action=="unit":unit(*sys.argv[2:])
    elif action=="readback":readback()
    else:raise ValueError(action)
