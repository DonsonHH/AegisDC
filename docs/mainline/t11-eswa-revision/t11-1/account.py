"""Reconcile Slurm allocation/step usage and package the narrow publication return."""
import argparse
import csv
from decimal import Decimal
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

from operations import ACTIVITY_NAME,BASE,check_stage,file_sha,need,read,save,now


def seconds(field):
    if not field or field in ("Unknown","INVALID","N/A"):return None
    days,sep,time=field.partition("-")
    if not sep:time,days=days,"0"
    parts=[Decimal(x) for x in time.split(":")]
    value=Decimal(days)*86400
    return value+sum(v*60**i for i,v in enumerate(reversed(parts)))


def write_table(path,records):
    with path.open("x",encoding="utf8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]),delimiter="\t",lineterminator="\n")
        w.writeheader();w.writerows(records)


def saved_calls(activity, filename):
    total=0
    for file in (activity/"positions").glob("*/*/"+filename):
        with file.open("rb") as handle:
            total+=sum(1 for line in handle if line.endswith(b"\n"))
    return total


def seal_return(activity, folder):
    index=folder/"RETURN-SHA256SUMS.txt"
    included=[]
    for line in index.read_text(encoding="utf8").splitlines():
        expected,name=line.split("  ",1)
        path=(folder/name).resolve()
        need(path.is_relative_to(folder.resolve()) and file_sha(path)==expected,"public return identity: "+name)
        included.append(name)
    included.append(index.name)
    need(set(included)=={p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()},
         "complete public return set")
    final=activity/"public-return.tar.gz"
    if not final.exists():
        fd,temp=tempfile.mkstemp(prefix="return-pack-",suffix=".tar.gz",dir=activity);os.close(fd)
        try:
            with tarfile.open(temp,"w:gz") as archive:
                for name in included:archive.add(folder/name,arcname=name,recursive=False)
            os.link(temp,final)
        finally:
            os.unlink(temp)
    print("return sha256",file_sha(final),"files",len(included))


def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument("--manifest",required=True);arg=a.parse_args()
    act,_=check_stage(BASE/ACTIVITY_NAME,arg.manifest)
    reg=read(act/"registration.json");jobs={}
    for key in reg["order"]:
        f=act/"submissions"/(key+".json")
        if (act/"submissions"/(key+".intent.json")).exists() and not f.exists():
            raise ValueError("Reconcile outstanding scheduler intent before accounting: "+key)
        if f.exists():
            row=read(f);jobs[row["job"]]=row
    need(jobs and len(jobs)<=63,"registered submissions")
    columns=("JobIDRaw","JobName","State","ExitCode","ElapsedRaw","AllocCPUS","TimelimitRaw","TotalCPU","UserCPU",
             "SystemCPU","ReqMem","MaxRSS","Start","End")
    cmd=["sacct","-n","-P","-j",",".join(jobs),"--format="+",".join(columns)]
    raw=subprocess.check_output(cmd,text=True)
    full=list(csv.DictReader(raw.splitlines(),fieldnames=columns,delimiter="|"))
    groups={r["JobIDRaw"]:r for r in full}
    end_states={"COMPLETED","NODE_FAIL","OUT_OF_MEMORY","BOOT_FAIL","CANCELLED","FAILED","TIMEOUT","PREEMPTED","DEADLINE","REVOKED"}
    qual=act/"qualification"/"acceptance.json"
    qualified=qual.is_file() and read(qual)["pass"] is True
    if qualified:
        need((act/"science-settled.json").is_file() and (act/"submissions"/"analysis.json").is_file(),
             "require reconciled science and terminal readback before sealing")
    else:
        need((act/"STOP.json").is_file() and not any(reg["groups"][j["name"]]["kind"]=="science" for j in jobs.values()),
             "only a documented stage-0 stop may close without science")
    if (act/"public-return").is_dir():
        existing=read(act/"public-return"/"accounting.json")
        need(existing["source_manifest_sha256"]==arg.manifest and set(existing["allocation_ids"])==set(jobs),
             "stored return belongs to a different freeze or allocation set")
        seal_return(act,act/"public-return")
        return
    for job in jobs:
        need(job in groups and groups[job]["State"].split()[0].rstrip("+") in end_states,
             "collect only after all submitted allocations are terminal: "+job)
    output=Path(tempfile.mkdtemp(prefix="public-return-prep-",dir=act))
    accounting=[];total_reserved=0;cpu_used=Decimal(0);known=0;lower_bound=False
    for job,row in jobs.items():
        rec=groups[job];name=row["name"]
        need(rec["State"].split()[0].rstrip("+") in end_states,"collect only after terminal: "+job)
        spec=reg["groups"][name]
        need(int(rec["AllocCPUS"])==1 and int(rec["TimelimitRaw"])*60==spec["seconds"]==row["reserved_cpu_s"],
             "scheduler CPU and time allocation: "+job)
        reservation=int(rec["AllocCPUS"])*int(rec["TimelimitRaw"])*60
        total_reserved+=reservation
        alloc=seconds(rec["TotalCPU"]); step=seconds(groups.get(job+".batch",{}).get("TotalCPU",""))
        measured_path=act/"job-costs"/(name+".json")
        measured=Decimal(str(read(measured_path)["process_cpu_s"])) if measured_path.is_file() else None
        if alloc is not None and alloc>0:
            actual=alloc;origin="Slurm allocation TotalCPU"
        elif step is not None and step>0:
            actual=step;origin="Slurm .batch TotalCPU"
        elif measured is not None:
            actual=measured;origin="workload process plus waited children (lower bound for allocation)";lower_bound=True
        else:
            actual=None;origin="UNESTABLISHED";lower_bound=True
        if actual is not None: cpu_used+=actual;known+=1
        accounting.append(dict(job=job,group=name,kind=spec["kind"],state=rec["State"],exit_code=rec["ExitCode"],
             reserved_cpu_s=reservation,elapsed_wall_s=rec["ElapsedRaw"],allocation_reported_cpu_s=alloc,
             batch_reported_cpu_s=step,measured_workload_cpu_s=measured,reported_used_cpu_s=actual,
             actual_basis=origin,start=rec["Start"],end=rec["End"]))
    need(total_reserved<=229800,"reservation cap")
    write_table(output/"jobs.tsv",accounting)
    with (output/"slurm-allocation-and-steps.psv").open("x",encoding="utf8") as fp:fp.write("|".join(columns)+"\n"+raw)
    included=[]
    def copy(rel,dest=None):
        path=act/rel
        if path.is_file():
            target=output/(dest or rel)
            target.parent.mkdir(parents=True,exist_ok=True)
            need(not target.exists(),"return collision")
            shutil.copyfile(path,target);included.append(str(target.relative_to(output)))
    for rel in ("qualification/identity.json","qualification/historical-fields.json","qualification/public-witness.json",
                "qualification/acceptance.json","pilot-projection.json","STOP.json","science-settled.json",
                "center-timing/status.json","analysis-job.json","qualification/engineering-stop.json",
                "qualification/engineering-disposition.json"):
        copy(rel)
    for f in sorted((act/"qualification"/"attempts").glob("*/*.json")):
        copy(f.relative_to(act).as_posix())
    for group in reg["order"]:
        copy("batches/"+group+"/terminal.json","batches/"+group+".json")
    analysis=act/"analysis"
    if analysis.is_dir():
        # Only compact, per-condition public analysis output. Original trajectories are never copied.
        for path in sorted(analysis.iterdir()):
            need(path.is_file() and not path.is_symlink() and path.suffix in (".json",".md",".tsv",".jsonl",".txt",".csv"),
                 "unexpected readback item: "+path.name)
            copy("analysis/"+path.name)
    native=sum(1 for _ in (act/"positions").glob("*/*/native-entry.json"))
    returned=sum(1 for _ in (act/"positions").glob("*/*/native-return.json"))
    complete=sum(1 for _ in (act/"positions").glob("*/*/score.json"))
    counts=[]
    diagnostic_count=0
    for role in reg["roles"]:
        scheduled=[g for g in reg["groups"].values() if g.get("role")==role and (act/"submissions"/(g["name"]+".json")).is_file()]
        n_sub=12*len(scheduled); role_root=act/"positions"/role
        entered=len(list(role_root.glob("*/native-entry.json")));scored=len(list(role_root.glob("*/score.json")))
        position_entries=len(list(role_root.glob("*/entry.json")))
        diagnosed=sum(1 for f in role_root.glob("*/failure.json") if
                      (obs:=read(f).get("observed") or {}).get("clocks")==61 and
                      all(k in obs for k in ("entry","raw_sha256","timing_sha256","IPC","L","U","person","tool","fee","runtime"))
                      and not (f.parent/"score.json").exists() and (f.parent/"native-return.json").exists())
        diagnostic_count+=diagnosed
        counts.append(dict(role=role,planned=72,slurm_jobs=len(scheduled),submitted_positions=n_sub,
                    complete_as_run_scores=scored+diagnosed,complete_diagnostics_only=diagnosed,
                    native_entries=entered,native_returns=len(list(role_root.glob("*/native-return.json"))),
                    complete_scores=scored,failed_or_unresolved_positions=position_entries-scored,
                    unentered_positions=72-position_entries,submitted_but_unentered=n_sub-position_entries))
    write_table(output/"per-role-ledger.tsv",counts)
    save(output/"accounting.json",dict(claim="post hoc supplementary, nonconfirmatory",jobs=len(jobs),allocation_ids=sorted(jobs),
         reserved_cpu_s=total_reserved,
         reported_used_cpu_s=float(cpu_used),used_cpu_scope="lower_bound_or_partial" if lower_bound else "Slurm process CPU",
         allocations_with_cpu_measure=len(accounting) if known==len(accounting) else known,
         charged_native_calls=native,native_returns=returned,complete_new_scores=complete,
         complete_as_run_scores=complete+diagnostic_count,scientific_retries=0,
         actual_decision_calls=saved_calls(act,"public-call-attempts.jsonl"),returned_public_decisions=saved_calls(act,"timing.jsonl"),
         center_native_runs=0,center_scores_created=0,sealed_H2_generate_read_derive=[0,0,0],
         sealed_H3_generate_read_derive=[0,0,0],utc=now(),source_manifest_sha256=arg.manifest))
    filenames=sorted(p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file())
    sums="".join(file_sha(output/name)+"  "+name+"\n" for name in filenames)
    (output/"RETURN-SHA256SUMS.txt").write_bytes(sums.encode())
    final=act/"public-return"
    output.rename(final)
    seal_return(act,final)
    print("return sha256",file_sha(act/"public-return.tar.gz"),"files",len(filenames)+1,"jobs",len(jobs),"reserved",total_reserved)


if __name__=="__main__":main()
