"""Audit one saved study using frozen post-return predicates and independent arithmetic.

No entry into a facility, policy, runner or scorer is permitted in this process.
Raw trajectories stay on the private filesystem. Public products are summaries
and source/attempt/file identities.
"""
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import traceback

sys.path.insert(0,str(Path(__file__).resolve().parent))
from observations import ARMS, KINDS, canonical, equal, insist, norm, observe_arm
from render_results import write_reports

BASE=Path("/share/home/renly/renly-patrol-rsi/mainline/R4-finite-extension-20261118")
SOURCE=BASE/"source-24cc268d"
STUDY=BASE/"study-v1"
AUTH=BASE/"execution-authorization-01"
PREP=Path("docs/mainline/review-gated/R4/finite-extension-v1")
MANIFEST_SHA="fa5478798a47d9b37c05e25775337e59f4ac0e2425d495e393852f9dd28164d0"
INPUT_SHA="4b025bbb29e3652ff70a0a0ccd53556aaa131177bb3b6b9830c6c4e0053aa7d9"
APPROVAL_SHA="871489cf0165631ae1b9ccf54df9cba3b0ca93131cc90b5799c745487362737c"
TERMINAL_SHA="5d204aa6dca47b3011bbd4fa947a555b3d9298546a3efb10839ee94f013785b9"
SCHEDULER_SHA="5d630da1588a3eb02eb1a047ef4f96e1972cea2fbca65cd0f15e5caac0d9679b"


class NoModel:
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split(".")[0]=="aegis_dc":
            raise RuntimeError("Saved-evidence audit prohibits facility imports: "+fullname)
        return None


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def identity(path):
    return dict(sha256=sha(path),bytes=path.stat().st_size)


def save(path,value):
    with path.open("x",encoding="utf-8",newline="\n") as handle:
        json.dump(norm(value),handle,ensure_ascii=False,indent=2,allow_nan=False)
        handle.write("\n")


def inventory(directory):
    return {p.relative_to(directory).as_posix():identity(p) for p in sorted(directory.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts and p.suffix not in (".pyc",".pyo")}


def schedule(path):
    fields="job_id name partition state exit submit start end elapsed_seconds limit cpus memory tres total_cpu max_rss node".split()
    rows=[dict(zip(fields,line.split("|"))) for line in path.read_text().splitlines() if line.strip()]
    return {r["job_id"]:r for r in rows if r["job_id"].isdigit()},[r for r in rows if not r["job_id"].isdigit()]


def bind_inputs():
    mf=BASE/"review-01/output/execution-manifest.json"
    approval=AUTH/"approved.json"
    equal(sha(mf),MANIFEST_SHA,"Review manifest SHA")
    equal(sha(approval),APPROVAL_SHA,"Approved file SHA")
    equal(read(approval),dict(purpose="FINITE_SYNTHETIC_EXTENSION",decision="AUTHORIZE_ONE_FROZEN_EXECUTION",manifest_sha256=MANIFEST_SHA),"Authorization payload")
    manifest=read(mf);staged=read(SOURCE/"staged.json")
    equal(staged["revision"],manifest["source_revision"],"Execution source revision")
    equal(sha(SOURCE/"staged.json"),"45987d1133a1c1d6362527ccb6230192ed3392b760fd0d25d060482b8b9d716b","Staged identity")
    equal(sha(Path(sys.executable).resolve()),manifest["python_sha256"],"Interpreter")
    for name,meta in staged["files"].items():
        equal(identity(SOURCE/name),meta,"Staged file: "+name)
    for name,digest in {**manifest["runtime"],**manifest["supporting"]}.items():
        equal(sha(SOURCE/name),digest,"Manifest binding: "+name)
    equal(sha(SOURCE/manifest["data_path"]),INPUT_SHA,"Frozen full input")
    equal(manifest["data_sha256"],INPUT_SHA,"Input manifest field")
    equal(manifest["output_root"],str(STUDY),"Exclusive study location")
    equal(read(STUDY/"manifest.json"),manifest,"Manifest saved at run start")
    equal(read(STUDY/"started.json")["manifest_sha256"],MANIFEST_SHA,"Dispatch start")
    equal(sha(STUDY/"terminal.json"),TERMINAL_SHA,"Dispatch terminal file")
    equal(sha(AUTH/"study-sacct.psv"),SCHEDULER_SHA,"Settled scheduler source")
    return manifest,staged


def slot_evidence(slot,config,index,final_row,manifest,scheduler,reinspect,public_packets):
    root=STUDY/slot
    item=dict(slot=slot,dispatch_status=final_row["status"],eligible=final_row["eligible"],
              score_available=final_row["score_available"],assigned_stage_observed=final_row.get("assigned_stage_observed"),
              preclassified=dict(work_mode=config["work_mode"],budget=config["budget"],window=config["window"],calendar=config["calendar"],
                                  tF=config["tF"],tR=config["tR"],ready=config["ready"],permit=config["permit"],permissions=config["permissions"]),
              arms={a:None for a in ARMS},effective_propositions=final_row.get("finite_propositions"),unknown_internal_calls=None)
    if final_row["status"]=="NOT_SUBMITTED":
        insist(not root.exists() and not (STUDY/f"job-{slot}.json").exists(),"Unexpected suffix attempt: "+slot)
        item.update(job_id=None,accounting=None,calls_proved=0,gap_reason="Frozen suffix not submitted")
        return item
    job=read(STUDY/f"job-{slot}.json")["job_id"]
    sub=read(STUDY/f"submit-{slot}.json")
    equal([sub["index"],sub["manifest_sha256"]],[index,MANIFEST_SHA],"Submission binding")
    flags=sub["command"]
    expected_entry=[str(SOURCE/"scripts/finite_extension/slot.slurm"),str(SOURCE),str(BASE/"review-01/output/execution-manifest.json"),MANIFEST_SHA,str(index),str(root),str(AUTH/"approved.json"),APPROVAL_SHA]
    equal(flags[-8:],expected_entry,"Actual approval/source/slot invocation")
    insist(all(x in flags for x in ("--no-requeue","--cpus-per-task=1","--mem=1G","--time=00:01:00","--partition=cu")),"Submission budget")
    settled=scheduler[job]
    equal([settled["name"],settled["cpus"],settled["memory"],settled["limit"],settled["partition"]],
          ["ext-"+slot,"1","1G","00:01:00","cu"],"Allocated slot resources")
    sched=read(STUDY/f"scheduler-{slot}.json")
    equal(sched["row"],final_row,"Progress versus dispatch terminal")
    equal(read(STUDY/f"progress-{index+1:02}.json")[index],final_row,"Step archive versus terminal")
    item.update(job_id=job,scheduler=settled)
    if not (root/"exit.json").is_file():
        item.update(accounting=final_row.get("accounting"),calls_proved=None,gap_reason="Slot exit evidence incomplete")
        return item
    exit_row=read(root/"exit.json");ledger=exit_row["accounting"]
    item.update(accounting=ledger,calls_proved=ledger["calls_proved"],
                unknown_internal_calls=ledger["unreturned_or_pending"]+ledger["returned_count_unknown"])
    if final_row["status"] not in ("PASS","NONCOMPLIANT"):
        item.update(gap_reason="Technical stop or unresolved dispatch",raw_available=(root/"raw.json").is_file(),
                    failure=exit_row.get("error"),provisional_summary_available=(root/"summary.json").is_file())
        return item
    equal([settled["state"],settled["exit"],sched["permit_next"],exit_row["technical_stop"]],["COMPLETED","0:0",True,False],"Successful authoritative exit")
    equal(exit_row["status"],final_row["status"],"Worker/outer status")
    equal([exit_row["purpose"],exit_row["slot"],exit_row["job_id"],exit_row["manifest_sha256"]],[manifest["purpose"],slot,job,MANIFEST_SHA],"Exit binding")
    equal(read(root/"accounting.json"),ledger,"Independent accounting receipt")
    equal([ledger["calls_proved"],ledger["returned"],ledger["unreturned_or_pending"],ledger["returned_count_unknown"]],[1,1,0,0],"One known run")
    insist(not (root/"fixture-entered.json").exists(),"Surrogate used in real study")
    raw_path=root/"raw.json"
    raw=read(raw_path);actual=raw["actual"]
    equal(raw["exception"],None,"Saved return")
    equal(raw["binding"],read(root/"intent.json"),"Raw-to-start identity")
    bind=raw["binding"]
    digest=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
    equal([bind[k] for k in ("slot","job_id","manifest_sha256","purpose","common_sha256")],[slot,job,MANIFEST_SHA,manifest["purpose"],digest],"Call intent")
    equal(sha(raw_path),exit_row["files"]["raw_sha256"],"Raw archive identity")
    equal(read(root/"interpretation-started.json")["raw_sha256"],sha(raw_path),"Raw saved before interpretation")
    equal(sha(root/"summary.json"),exit_row["files"]["summary_sha256"],"Worker summary identity")
    count=Counter(c["kind"] for c in actual["calls"])
    insist(set(count)==set(KINDS),"Call kinds")
    counts={key:count[k] for k,key in KINDS.items()}
    equal(counts,actual["counts"],"Raw call ledger")
    equal(counts,ledger["known_reported_subtotal"],"Independent counter")
    insist(counts["constructor_attempts"]==3 and counts["policy_calls"]<=60,"Triplet/call cap")
    equal(actual["execution_order"],list(ARMS),"Treatment order")
    for call in actual["calls"]:
        if call["kind"]=="constructor":equal(call["arguments"]["config"],config,"Constructed input")
    # Frozen analysis consumes the archived object and performs no simulation or scoring.
    repeated=reinspect(slot,config,actual);summary=read(root/"summary.json")
    equal(repeated,summary,"Saved frozen analysis reproduction")
    equal(summary["arms"],final_row["arms"],"Published results")
    equal(final_row["finite_propositions"],summary["finite_propositions"] if final_row["eligible"] else None,"Eligibility masks")
    equal(summary["valid_comparison"],final_row["eligible"],"Eligibility")
    equal(summary["assigned_stage_observed"],final_row["assigned_stage_observed"],"Actual coverage")
    for arm in ARMS:
        observed=observe_arm(actual,config,slot,arm,public_packets)
        stored=summary["arms"][arm]
        equal(observed["stage"],stored["stage"],"Actual stage reported")
        equal(observed["costs"],stored["costs"],"Reported cost vector")
        equal([observed["L"],observed["U"]],[stored["L"],stored["U"]],"Reported L/U")
        observed.update(failure_status=stored["failure_status"],request_statuses=stored["request_statuses"],
                        hard_constraints_ok=stored["hard_constraints_ok"])
        item["arms"][arm]=observed
    id_delta=norm(Fraction(item["arms"]["D"]["L"])-Fraction(item["arms"]["I"]["L"]))
    ip_delta=norm(Fraction(item["arms"]["I"]["L"])-Fraction(item["arms"]["P"]["L"]))
    equal(id_delta,final_row["delta_L_D_minus_I"],"Primary difference")
    equal(ip_delta,final_row["P_background"]["delta_L_I_minus_P"],"Background difference")
    item.update(delta_L_D_minus_I=id_delta,delta_L_I_minus_P=ip_delta,
                delta_costs_I_minus_D=final_row["I_minus_D_costs"],delta_costs_I_minus_P=final_row["P_background"]["delta_costs_I_minus_P"],
                worker_propositions=summary["finite_propositions"],raw_sha256=sha(raw_path),raw_path=str(raw_path),
                gap_reason=None if item["assigned_stage_observed"] else "Frozen stage predicate not met; see observed requests, events, receipts and stop for each arm")
    return item


def run(output,tools_identity):
    insist(os.environ.get("SLURM_JOB_ID") and socket.gethostname().split(".")[0]!="mu01","Compute allocation required")
    insist(os.environ.get("SLURM_CPUS_PER_TASK")=="1" and os.environ.get("SLURM_MEM_PER_NODE")=="1024","Audit allocation")
    output.mkdir(exist_ok=False,parents=True)
    tool_meta=read(tools_identity)
    for name,meta in tool_meta["files"].items():
        equal(identity(tools_identity.parent/name),meta,"Audit tool identity")
    mf,stage=bind_inputs()
    sys.meta_path.insert(0,NoModel())
    sys.path.insert(0,str(SOURCE/"scripts/finite_extension"))
    from analysis import inspect as saved_inspect
    for name in ("analysis","coverage","common","london_confirmation_entry","run_london_public_development"):
        file=Path(sys.modules[name].__file__).resolve()
        equal(sha(file),mf["runtime"][str(file.relative_to(SOURCE))],"Loaded analysis identity")
    before=inventory(STUDY)
    terminal=read(STUDY/"terminal.json")
    equal(terminal["manifest_sha256"],MANIFEST_SHA,"Terminal manifest")
    order=mf["order"];inputs=read(SOURCE/mf["data_path"])
    equal([r["condition_id"] for r in inputs["conditions"]],order,"Frozen order")
    equal([r["slot"] for r in terminal["rows"]],order,"Full denominator")
    equal([r["slot"] for r in read(STUDY/"denominator.json")],order,"Initial denominator")
    sched,steps=schedule(AUTH/"study-sacct.psv")
    history={};rows=[]
    for i,(c,record) in enumerate(zip(inputs["conditions"],terminal["rows"])):
        row=slot_evidence(order[i],c["common"],i,record,mf,sched,saved_inspect,history)
        row["input_canonical_sha256"]=c["canonical_sha256"]
        rows.append(row)
    selected=[r["scheduler"] for r in rows if "scheduler" in r]
    insist(set(sched)=={r["job_id"] for r in selected},"Exactly declared research jobs")
    insist(all(prev["end"]<=nxt["submit"]<=nxt["start"] for prev,nxt in zip(selected,selected[1:])),"Serial job ordering")
    equal(inventory(STUDY),before,"Study originals changed while reading")
    insist(not any(s.split(".")[0]=="aegis_dc" for s in sys.modules),"Runtime modules imported")
    for name,h in mf["runtime"].items():equal(sha(SOURCE/name),h,"Runtime drift after audit")
    index=dict(manifest_sha256=MANIFEST_SHA,manifest_source=str(BASE/"review-01/output/execution-manifest.json"),
        source_root=str(SOURCE),source_revision=stage["revision"],staged_identity_sha256=sha(SOURCE/"staged.json"),runtime=mf["runtime"],
        input_file=str(SOURCE/mf["data_path"]),input_sha256=INPUT_SHA,approval_file=str(AUTH/"approved.json"),approval_sha256=APPROVAL_SHA,
        original_study_directory=str(STUDY),files=before,dispatcher_directory=str(AUTH),
        dispatcher_files={name:identity(AUTH/name) for name in ("dispatch.sh","approved.json","dispatcher-pid","dispatcher-exit","preflight.json","stdout.log","stderr.log","study-sacct.psv")},
        scheduler_command="sacct -n -P -j <actual recorded job IDs> -o JobID,JobName%32,Partition,State,ExitCode,Submit,Start,End,ElapsedRaw,Timelimit,AllocCPUS,ReqMem,AllocTRES%72,TotalCPU,MaxRSS,NodeList",
        scheduler_allocations=selected,scheduler_steps=steps,job_ids=[r["job_id"] for r in selected])
    save(output/"identity-index.json",index)
    propositions=write_reports(output,rows,terminal["status"])
    save(output/"paired-results.json",dict(manifest_sha256=MANIFEST_SHA,classification="FINITE_SYNTHETIC_EXTENSION_STUDY",order=order,rows=rows))
    save(output/"propositions.json",propositions)
    checks=dict(readonly_saved_evidence=True,terminal_status=terminal["status"],terminal_sha256=TERMINAL_SHA,
        research_denominator=len(order),research_jobs=len(selected),study_archive_files_verified=len(before),
        runtime_files_rechecked=len(mf["runtime"]),staged_files_verified=len(stage["files"]),identical_public_packets=len(history),
        per_arm_checks=["frozen demand L/U and power integration","occupied time and by-action/by-stage costs","queue and approval/unstarted waits","actual stages, VERIFY bindings, recoveries","v2 policy arguments, timing and equality on identical public packets"],
        saved_analysis_module="Frozen scripts/finite_extension/analysis.py inspect() and its report and coverage dependencies only",
        scorer_module_imported=False,real_runner_calls=0,real_facility_calls=0,real_policy_calls=0,real_scorer_calls=0,
        tool_identity=tool_meta,tool_identity_sha256=sha(tools_identity),job_id=os.environ["SLURM_JOB_ID"],host=socket.gethostname(),
        files={p.name:identity(p) for p in output.iterdir() if p.is_file()})
    save(output/"saved-verification.json",checks)
    print(json.dumps(dict(status="PASS_SAVED_R4_STUDY_RECONCILIATION",jobs=len(selected),eligibility=propositions["denominator"],known_calls=propositions["calls"],real_calls_this_job=0)))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True);parser.add_argument("--tool-identity",type=Path,required=True)
    args=parser.parse_args()
    try:run(args.output,args.tool_identity)
    except Exception as exc:
        if args.output.is_dir() and not (args.output/"audit-failure.json").exists():
            save(args.output/"audit-failure.json",dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc(),
                 study_reexecution=False,real_calls_this_job=0))
        raise
