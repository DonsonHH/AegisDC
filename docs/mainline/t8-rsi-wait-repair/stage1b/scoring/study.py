"""Four matched native FIT rounds, resumable only at sealed, successful Slurm job boundaries."""

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import sys
import tempfile
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
from jsonschema import Draft202012Validator

import sandbox
from access_audit import audit
from positions import stop
from prepare_runtime import BASE, PK, R1, STUDY, compact, copy_for_job, read, require, save
from qualification import qualify, checked_trace
from study_broker import NativeBroker

sys.path.insert(0,str(R1))
import fit_loop as loop
from fit_broker import ARM_US, CONTROLLER_US, ROWS, open_packet
from fit_evidence import Journal, Objects, authenticated, public_hex, signed
from fit_program import BASE as BASE_AST, ZERO, fingerprint

PACKAGE=PK.parents[1]
REG="f8a4d6d320c090a4a74280542df5c864677dcfe78e79638843b1fad86887340f"
DESIGN="d7086b26d427266dea39fea4be4dbc88008b46f13af4e4158a2c1d692c8ca4c4"
FIT_ROOT="6efbf682c4aceab4c32bc9f524223b78bd24f63fa1d9a1211a5d6d57b9b83db1"
FIT_SIGNATURE="cf04f4619484ab7f3a730a7e39747a341b0f4e8de9ed1fe152ed109a2f444597"


def cpu_us():
    total=0.0
    for who in (resource.RUSAGE_SELF,resource.RUSAGE_CHILDREN):
        usage=resource.getrusage(who);total+=usage.ru_utime+usage.ru_stime
    return int(round(total*1_000_000))


def score_gate():
    folder=PACKAGE/"stage1b/fit-overlap"
    request,receipt=read(folder/"request.json"),read(folder/"receipt.json")
    signature=(folder/"receipt.sig").read_bytes()
    expected={"registration_id":REG,"split":"FIT","batch_root":FIT_ROOT,
              "catalogue_root":"59cd699e7098493718ffb2c1ff8ba4dcd0deb31d7df710b833e2c1321455a119"}
    require(request==expected and receipt=={**request,"custodian_id":"pi-custodian","auditor_id":"pi-auditor",
        "aggregate_coverage_pct":100,"all_required_tests_complete":True,"decision":"PASS"},"actual procedural PASS")
    raw=compact(receipt)
    require((folder/"receipt.json").read_bytes()==raw+b"\n" and hashlib.sha256(raw).hexdigest()==
            "f5378967de5d8a361136811d5156f8be9aff39e87afe7c0385d16dc1432a8cee" and
            hashlib.sha256(signature).hexdigest()==FIT_SIGNATURE,"released receipt and detached bytes")
    authority=read(PACKAGE/"custody/authority.json")
    key=bytes.fromhex(authority["public_key_hex"])
    require(authority["credential_separation"]=="shared_account" and hashlib.sha256(key).hexdigest()==
            authority["fingerprint_sha256"]=="ae9b3a9714961a0f6f7e85288c414107c34df15934d382e97d9e11a947f74cb8",
            "registered public signer")
    Ed25519PublicKey.from_public_bytes(key).verify(signature,raw)
    batch=(BASE/"panel/batch.private.json").read_bytes()
    require(batch.endswith(b"\n") and hashlib.sha256(batch[:-1]).hexdigest()==FIT_ROOT,"frozen panel bytes")
    index=json.loads(batch)
    require(index["registration_id"]==REG and index["catalogue_root"]==request["catalogue_root"] and
            [r["ordinal"] for r in index["ordered"]]==list(range(1,49)),"approved ordered 48")
    return [r["v3_full"] for r in index["ordered"]]


def technical_keys(create=False):
    directory=STUDY/"technical-keys"
    if create:
        directory.mkdir(mode=0o700,exist_ok=False)
        for name in ("journal","evaluator","audit"):
            k=Ed25519PrivateKey.generate()
            with (directory/name).open("xb") as f:
                f.write(k.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption()))
                f.flush();os.fsync(f.fileno())
            (directory/name).chmod(0o600)
    return {n:Ed25519PrivateKey.from_private_bytes((directory/n).read_bytes()) for n in ("journal","evaluator","audit")}


def envelope(image_hash):
    keys=technical_keys()
    source=read(PK/"source-lock.json");export=read(PK/"export.json")
    packed_sources=export["members"]
    for name,h in packed_sources.items():require(sandbox.filehash(PK.parents[4]/name)==h,"execution source envelope")
    search=source["r1_files"]["fit_program.py"]
    budget=read(PACKAGE/"r0/registration.json")["budget"]
    frozen=dict(parent_bundle=source["parent_bundle"],policy_compiler=search,search_interpreter=search,selector=search,
        facility_metrics=fingerprint([source["native_tree"],source["native_members"],source["scoring_files"]["native_role.py"]]),
        score_adapter=fingerprint([sandbox.filehash(PK/"study_broker.py"),source["scoring_files"]["positions.py"],
                                   source["r1_files"]["fit_broker.py"]]),
        sandbox=fingerprint([image_hash,sandbox.UID,source["scoring_files"]]),resource_envelope=fingerprint(budget),
        fit_commitment=FIT_ROOT)
    public={n:public_hex(k) for n,k in keys.items()}
    record=dict(registration_sha256=REG,design_sha256=DESIGN,release_revision=export["revision"],
        export_sha256=sandbox.filehash(PK/"export.json"),
        source_lock=sandbox.filehash(PK/"source-lock.json"),fit_receipt_signature_sha256=FIT_SIGNATURE,
        image_manifest_sha256=image_hash,frozen=frozen,signer_fingerprints={n:hashlib.sha256(bytes.fromhex(v)).hexdigest() for n,v in public.items()})
    return record,keys


class PersistedObjects(Objects):
    def __init__(self,root):
        self.root=root
        require(all((root/n).is_dir() for n in ("objects","events","rounds")),"existing evidence store")


def restore_journal(key,context,first):
    loc=STUDY/"evidence"
    store=Objects(loc) if first else PersistedObjects(loc)
    j=Journal(store,key,context)
    for n,path in enumerate(sorted((loc/"events").glob("*.json")),1):
        ref=read(path);event=authenticated(store.get(ref),public_hex(key))
        require(path.name==f"{n:04}.json" and event["sequence"]==n and event["previous"]==j.head and
                event["context"]==context,"prior immutable chain")
        j.seq=n;j.head=ref["sha256"]
    return j


def collect(slot,binding,broker,journal):
    ref,packet=broker.evaluate(binding,tuple(slot["policy"]["levels"]))
    meter=authenticated(journal.store.get(ref),broker.authority)
    require(meter["binding"]==binding,"physical binding")
    attempts=meter["attempts"];ords=[x["ordinal"] for x in attempts]
    require(ords==sorted(set(ords)) and all(1<=n<=ROWS for n in ords),"physical ordinal set")
    slot.update(attempts_receipt=ref,status=meter["status"],failure_reason=meter["reason"],
                started_fit_n=len(ords),complete_fit_n=sum(x["complete"] for x in attempts))
    arrival=journal.seal("return-to-broker",{"binding":binding,"meter":ref,
                                    "signed_packet":journal.store.put(packet) if packet is not None else None})
    if packet is not None:
        require(slot["complete_fit_n"]==ROWS and slot["status"]=="COMPLETE","incomplete FIT packet")
        slot["fit_return"]=open_packet(packet,binding,broker.authority,journal.store)
        require(slot["fit_return"]["hard_violations"]==0,"hard violation at release")
    physical=journal.store.get(meter["physical"])["physical"]
    return sum(x["cpu_us"] for x in attempts),sum(x["cpu_us"] for x in physical if not x["native_entered"])


def optimizer(image, scratch, arm, label, task):
    root=scratch/("search-"+arm+"-"+label);root.mkdir()
    p=sandbox.spawn(image,"search-"+arm,"/t8/public_roles.py",["search"],root/"ops")
    output,_=p.communicate(compact(task)+b"\n",timeout=30)
    require(p.returncode==0,"isolated improvement worker")
    report=checked_trace(image,"search-"+arm,root/"ops",root/"auditor")
    save(root/"wire.json",{"own_request":task,"own_return":json.loads(output),"audit":report})
    destination=STUDY/"improver-reads"/(arm+"-"+label)
    destination.parent.mkdir(exist_ok=True)
    shutil.copytree(root,destination)
    return json.loads(output)


def state_before(j,arm,r,baseline):
    if r==1:
        origin={"kind":"PARENT_BASELINE","receipt":baseline["fit_return"]["receipt"]}
        return {"score":baseline["fit_return"],"seen":{ZERO},
                "state":loop.state(BASE_AST,baseline["policy"],origin,baseline["fit_return"],{ZERO},j.store)}
    old=read(j.store.root/"rounds"/f"{arm}-{r-1}.json")
    require(old["status"]=="CLOSED","unclosed predecessor")
    state=old["after"];ref=state["paid_score_receipt"];box=j.store.get(ref)
    packet=authenticated(box,os.environ["T8_SCORE_PUBLIC"])
    require(packet["binding"]["policy_id"]==state["incumbent"]["id"],"paid incumbent identity")
    score={k:packet["data"][k] for k in ("L_sum_us","person_sum_us","hard_violations")}
    score.update(receipt=ref,fit_n=ROWS)
    return {"state":state,"score":score,"seen":{tuple(x) for x in j.store.get(state["seen_set_bytes"])}}


def round_file(r,name):return STUDY/"checkpoints"/f"r{r}-{name}.json"


def start_round(j,r,baseline,frozen,image,scratch):
    records,rosters,clocks={},{},{}
    for arm in loop.ARMS:
        start=cpu_us()
        prev=read(j.store.root/"rounds"/f"{arm}-{r-1}.json") if r>1 else None
        state=state_before(j,arm,r,baseline)
        rec=loop.empty_record(arm,r,fingerprint(prev) if prev else None,REG,DESIGN,frozen)
        def propose(ast,center,seen,number,slots):
            candidates,diag=optimizer(image,scratch,arm,f"r{r}-roster",{"operation":"propose","ast":ast,
                "incumbent":center,"seen":sorted(seen),"round":number,"slots":slots})
            return [tuple(x) for x in candidates],diag
        with patch.object(loop,"roster",propose):
            ordered=loop.prepare(rec,state,j)
        if prev:require(ordered==prev["next_witness"]["after_roster"],"predicted prepaid paid roster")
        records[arm]=rec;rosters[arm]=ordered;clocks[arm]=cpu_us()-start
    require(r>1 or rosters["O"]==rosters["R"],"first-round treatment symmetry")
    barrier=j.seal("both-rosters-prepaid",{"round":r,"receipts":{a:rec["audit"]["roster_seal_before_feedback"]
                                                                  for a,rec in records.items()}})
    save(round_file(r,"reservation"),{"records":records,"ordered":rosters,"control":clocks,"barrier":barrier})


def execute_arm(j,broker,r,arm,baseline):
    prep=read(round_file(r,"reservation"))
    rec=prep["records"][arm];meters=[];preentry_us=0
    state=state_before(j,arm,r,baseline)
    seen=set(state["seen"]);control=prep["control"][arm]
    for slot in rec["slots"]:
        if (STUDY/"STOP").exists():break
        begin=cpu_us()
        defect=loop.check_issued(slot,seen,DESIGN,rec["frozen"],j.store)
        if defect:
            slot["status"],slot["failure_reason"]=defect
            stop(defect[0]);break
        seen.add(tuple(slot["policy"]["levels"]))
        bind=loop.slot_binding(j.context,arm,r,slot["slot"],slot["policy"],prep["ordered"][arm]["sha256"])
        control+=cpu_us()-begin
        if control>CONTROLLER_US:stop("round control CPU cap");break
        native_us,extra=collect(slot,bind,broker,j)
        meters.append(native_us);preentry_us+=extra
        if slot["fit_return"] is None or slot["status"]!="COMPLETE":stop("incomplete or unsafe paid position")
    save(round_file(r,arm),{"record":rec,"meters":meters,"control":control,"pre_entry":preentry_us,
                            "job":os.environ["SLURM_JOB_ID"]})


def finish_round(j,r,baseline,image,scratch,access,validate):
    prep=read(round_file(r,"reservation"));items={}
    for a in loop.ARMS:
        p=round_file(r,a)
        items[a]=read(p) if p.exists() else {"record":prep["records"][a],"meters":[],"pre_entry":0,
                                              "control":prep["control"][a],"job":None}
    reason=read(STUDY/"STOP")["reason"] if (STUDY/"STOP").exists() else None
    if not reason:
        for item in items.values():
            require(all(s["status"]=="COMPLETE" and s["fit_return"]["hard_violations"]==0 and s["complete_fit_n"]==ROWS
                        for s in item["record"]["slots"]),"paired complete and hard-safe")
        release=j.seal("paired-complete",{"round":r,"both_rosters":prep["barrier"],"own_packet_commitments":{
            a:j.store.put([s["fit_return"]["receipt"] for s in item["record"]["slots"]])["sha256"] for a,item in items.items()}})
    for a,item in items.items():
        rec=item["record"];start=cpu_us()
        if not reason:
            rec["audit"]["score_release_receipt"]=j.seal("release-own",{"arm":a,"round":r,
                "paired_complete":release["sha256"],"packets":[s["fit_return"]["receipt"] for s in rec["slots"]]})
            if r>1:loop.incoming(rec,read(j.store.root/"rounds"/f"{a}-{r-1}.json"),prep["ordered"][a],j)
            def select(arm,number,ast,center,score,candidates,returns):
                proofs={"verification_key":os.environ["T8_SCORE_PUBLIC"],
                        "packets":[j.store.get(x["receipt"]) for x in (score,*returns)]}
                return optimizer(image,scratch,arm,f"r{r}-select",dict(operation="select",arm=arm,round=number,
                                 ast=ast,incumbent=center,baseline=score,candidates=candidates,returns=returns,
                                 signed_feedback=proofs))
            with patch.object(loop,"rank_and_rewrite",select):loop.decide(rec,state_before(j,a,r,baseline),j)
        rec["audit"]["sandbox_and_read_receipt"]=access
        control=item["control"]+cpu_us()-start
        total=sum(item["meters"])+control+item["pre_entry"]
        rec["accounting"].update(started_positions=sum(s["started_fit_n"] for s in rec["slots"]),
                    complete_positions=sum(s["complete_fit_n"] for s in rec["slots"]),actual_process_cpu_us=total,
                    allocations_receipt=j.seal("allocation",{"arm":a,"round":r,"controller_us":control+item["pre_entry"],
                        "optimizer_cpu_us":control,"pre_native_us":item["pre_entry"],"per_evaluated_slot_us":item["meters"],
                        "position_cap_us":180_000_000,"controller_cap_us":CONTROLLER_US,"reserved_slots":4,
                        "reserved_positions":192,"slurm_job":item["job"],"barrier":prep["barrier"]}))
        previous=sum(read(j.store.root/"rounds"/f"{a}-{i}.json")["accounting"]["actual_process_cpu_us"] for i in range(1,r))
        if control>CONTROLLER_US or previous+total>ARM_US:
            reason="optimizer/arm CPU limit";stop(reason)
    for a,item in items.items():
        if reason:loop.keep_stop(item["record"],reason,True,j)
        j.round(item["record"],validate)
    return reason


def end(j,baseline_ref,frozen,keys,reason,first_missing_round,validate):
    for r in range(first_missing_round,5):
        for a in loop.ARMS:
            path=j.store.root/"rounds"/f"{a}-{r}.json"
            if path.exists():continue
            prev=read(j.store.root/"rounds"/f"{a}-{r-1}.json") if r>1 else None
            rec=loop.empty_record(a,r,fingerprint(prev) if prev else None,REG,DESIGN,frozen)
            loop.keep_stop(rec,reason,r==1,j);j.round(rec,validate)
    last={a:read(j.store.root/"rounds"/f"{a}-4.json") for a in loop.ARMS}
    heads={a:fingerprint(v) for a,v in last.items()}
    locked=None if reason else j.seal("dual-fixture-or-study-lock",{"round_heads":heads,
                                      "incumbents":{a:v["after"]["incumbent"] for a,v in last.items()}})
    summary=dict(context=j.context,registration_sha256=REG,design_sha256=DESIGN,frozen=frozen,
          journal_key=public_hex(keys["journal"]),score_key=public_hex(keys["evaluator"]),
          result=dict(context=j.context,shared=baseline_ref,stop=reason,round_heads=heads,dual_lock=locked))
    save(j.store.root/"case.json",summary)


def job(name,revision):
    sandbox.require_rootless()
    plan=read(STUDY/"execution-recovery.json")
    require(fingerprint(plan)==read(STUDY/"published-envelope-recovery.json")["fingerprint"],"published recovery envelope")
    require(plan["release_revision"]==revision==read(PK/"export.json")["revision"],"authorized score source revision")
    reservation=read(STUDY/"jobs"/(name+".json"))
    require(reservation["job"]==os.environ["SLURM_JOB_ID"] and reservation["cpus"]==int(os.environ["SLURM_CPUS_PER_TASK"])
            and reservation["release"]==revision and reservation["batch_root"]==FIT_ROOT,"named nontransferable Slurm allocation")
    full_inputs=score_gate()
    env,keys=envelope(plan["image_manifest_sha256"])
    require(env==plan,"frozen execution image or code")
    os.environ.update(T8_IMAGE_SOURCE=env["source_lock"],T8_IMAGE=env["image_manifest_sha256"],
                      T8_AUDIT_PUBLIC=public_hex(keys["audit"]),T8_SCORE_PUBLIC=public_hex(keys["evaluator"]))
    scratch=Path(tempfile.mkdtemp(prefix="t8-fit-"+reservation["job"]+"-"))
    image=copy_for_job(scratch)
    validate=Draft202012Validator(read(PACKAGE/"r0/round-ledger.schema.json")).validate
    j=restore_journal(keys["journal"],fingerprint(plan),name=="parent-a2")
    broker=NativeBroker(j.store,keys["evaluator"],image,scratch,full_inputs)
    save(STUDY/"jobs"/(name+"-entry.json"),dict(job=reservation["job"],name=name,release=revision,context=j.context))
    frozen=env["frozen"]
    if name=="parent-a2":
        (STUDY/"checkpoints").mkdir()
        shared=loop.policy(ZERO,DESIGN,frozen,j.store)
        base=loop.empty_slot(1);base["policy"]=shared
        prepaid=j.seal("shared-parent-reservation",{"policy":shared,"rows":48,"fit_commitment":FIT_ROOT})
        bind=loop.slot_binding(j.context,"PARENT",0,0,shared,prepaid["sha256"])
        try:
            result=qualify(image,scratch,STUDY/"engineering")
            access=j.seal("native-roles-qualified",{"qualification":j.store.put(result),"job":reservation["job"]})
            save(STUDY/"access.json",access)
        except Exception as exc:
            stop("public interface qualification: "+type(exc).__name__)
            if (scratch/"engineering").exists() and not (STUDY/"engineering").exists():
                shutil.copytree(scratch/"engineering",STUDY/"engineering")
            reason=read(STUDY/"STOP")["reason"]
            meter=j.store.put(signed(keys["evaluator"],{"binding":bind,"attempts":[],
                    "status":"FAILED","reason":reason,"originals":j.store.put({"binding":bind,"rows":[]})}))
            base.update(status="FAILED",failure_reason=reason,attempts_receipt=meter)
            j.seal("return-to-broker",{"binding":bind,"meter":meter,"signed_packet":None})
            ref=j.seal("shared-parent-return",{"slot":base,"cpu_us":0})
            save(STUDY/"baseline.json",{"slot":base,"ref":ref,"native_cpu_us":0,"pre_entry_cpu_us":0})
            end(j,ref,frozen,keys,reason,1,validate)
            raise
        cpu,pre=collect(base,bind,broker,j)
        ref=j.seal("shared-parent-return",{"slot":base,"cpu_us":cpu+pre})
        save(STUDY/"baseline.json",{"slot":base,"ref":ref,"native_cpu_us":cpu,"pre_entry_cpu_us":pre})
        if base["status"]!="COMPLETE" or (STUDY/"STOP").exists():
            stop("shared baseline incomplete")
            end(j,ref,frozen,keys,read(STUDY/"STOP")["reason"],1,validate)
            raise RuntimeError("shared parent stopped")
    else:
        require(not (STUDY/"STOP").exists(),"previous stop")
        baseline=read(STUDY/"baseline.json");base=baseline["slot"]
        require(base["status"]=="COMPLETE" and base["complete_fit_n"]==ROWS,"single shared baseline")
        r=1 if name=="pilot" else int(name[1])
        arms=loop.ARMS if name=="pilot" else [name[-1]]
        if arms[0]=="O":start_round(j,r,base,frozen,image,scratch)
        for a in arms:
            if not (STUDY/"STOP").exists():execute_arm(j,broker,r,a,base)
        if "R" in arms or (STUDY/"STOP").exists():
            reason=finish_round(j,r,base,image,scratch,read(STUDY/"access.json"),validate)
            if reason or r==4:end(j,baseline["ref"],frozen,keys,reason,r+1,validate)
            if reason:raise RuntimeError(reason)
    save(STUDY/"jobs"/(name+"-complete.json"),dict(job=reservation["job"],name=name,context=j.context,head=j.head))
    print("CLOSED",name,reservation["job"],flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--init-keys",action="store_true")
    p.add_argument("--envelope",metavar="IMAGE_SHA256")
    p.add_argument("--job",choices=("parent-a2","pilot","r2O","r2R","r3O","r3R","r4O","r4R"))
    p.add_argument("--revision")
    a=p.parse_args()
    os.umask(0o077)
    if a.init_keys:
        available=technical_keys(create=True)
        print("Technical study signers initialized:",", ".join(sorted(available)))
    elif a.envelope:
        score_gate();record,_=envelope(a.envelope);save(STUDY/"execution-recovery.json",record)
        print("Execution envelope",fingerprint(record))
    elif a.job and a.revision:
        try:job(a.job,a.revision)
        except Exception as failure:
            stop("study job stopped: "+type(failure).__name__)
            save(STUDY/"jobs"/(a.job+"-failure.json"),{"job":os.environ["SLURM_JOB_ID"],
                 "type":type(failure).__name__,"detail":str(failure),"stop":read(STUDY/"STOP")})
            raise
    else:p.error("expected --job and --revision, --envelope, or --init-keys")
