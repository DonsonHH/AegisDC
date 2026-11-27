"""Run public witnesses within the single, fixed-duration qualification allocation."""
import os
from pathlib import Path
import shutil
import subprocess
import time

from operations import PYTHON, cpu, file_sha, need, now, original_identities, public_bundle, read, save

CHECKS={"wait_inspect_act","public_action_mask","required_pending_refusal","one_intervention_voi",
        "shared_delivered_report","simulated_silence","seed_replay","separate_leaf","oat_single_change","private_ingress_rejected"}


def validate_release(folder,manifest):
    lock=read(folder/"source-manifest.json")
    need(file_sha(folder/"source-manifest.json")==manifest,"candidate implementation identity")
    for name,digest in lock["files"].items():
        need(file_sha(folder/name)==digest,"candidate file identity: "+name)
    return lock


def attempt(folder,manifest,out):
    lock=validate_release(folder,manifest)
    bundle=public_bundle(folder)
    location=out/"attempts"/manifest
    location.mkdir(parents=True)
    witness_path=location/"public-witness.json"
    program=folder/"source"/"qualification.py"
    # The worker and fixture processes share this Slurm allocation and its one CPU.
    ret=subprocess.run([str(PYTHON),"-I","-B",str(program),"--bundle",str(folder/"public-only"),
                        "--output",str(witness_path)],check=False)
    w=read(witness_path) if witness_path.is_file() and witness_path.stat().st_size else {}
    passed=(ret.returncode==0 and w.get("status")=="PASS" and w.get("passed") is True and w.get("failed")==[] and
            w.get("native_runs")==w.get("facility_calls")==0 and w.get("bundle_sha256")==bundle and
            w.get("qualification_sha256")==file_sha(program) and set(w.get("checks",{}))==CHECKS and
            all(c["passed"] is True for c in w["checks"].values()))
    result={"pass":passed,"job":os.environ["SLURM_JOB_ID"],"implementation_manifest":manifest,
            "implementation_revision":lock["implementation_revision"],"bundle":bundle,"witness_exit":ret.returncode,
            "native_calls":0,"utc":now(),"witness_sha256":file_sha(witness_path) if witness_path.is_file() else None}
    save(location/"receipt.json",result)
    print("PUBLIC_QUALIFICATION",result,flush=True)
    return result,witness_path


def run(activity,manifest):
    out=activity/"qualification";out.mkdir()
    start=time.monotonic();started_cpu=cpu()
    identity=original_identities(activity)
    save(out/"identity.json",identity)
    from center_timing import inspect_archives
    save(out/"historical-fields.json",inspect_archives(activity))
    result,witness=attempt(activity,manifest,out)
    initial_manifest=manifest
    tested_folder=activity
    # A failed engineering witness never releases scientific jobs. Keep the rest of
    # this same allocation available for a documented and Git-frozen code-only repair.
    # No extra sbatch, no scientific position, no implicit retry or parameter change.
    if not result["pass"]:
        save(out/"engineering-stop.json",dict(job=result["job"],receipt=result["implementation_manifest"],utc=now()))
        instruction=out/"engineering-disposition.json"
        deadline=start+1150
        while not instruction.exists() and time.monotonic()<deadline:time.sleep(2)
        if instruction.exists():
            request=read(instruction)
            if request["action"]=="test_frozen_engineering_fix":
                need(request["initial_manifest"]==initial_manifest and request["reason"] and
                     request["protocol_or_budget_changed"] is False,"engineering disposition")
                new=request["manifest"]
                need(len(new)==64 and all(c in "0123456789abcdef" for c in new) and new!=initial_manifest,"new source identity")
                candidate=activity/"engineering-releases"/new
                new_lock=validate_release(candidate,new)
                old_lock=read(activity/"source-manifest.json")
                for path in old_lock["files"]:
                    if path.startswith("references/") or path in ("registration.json","source/stage0-identity.json",
                                                                "source/qualification.py"):
                        need(new_lock["files"].get(path)==old_lock["files"][path],"immutable gates, witnesses and panel")
                need(not list((activity/"positions").glob("*/*/native-entry.json")),"correction after scientific entry")
                result,witness=attempt(candidate,new,out)
                if result["pass"]:
                    tested_folder=candidate;manifest=new
            else:need(request["action"]=="stop","unknown engineering disposition")
    if tested_folder!=activity:
        # Preserve the initial deployed source in full. During the swap the acceptance
        # record is still absent, so no controller can start a scientific position.
        previous=activity/"implementation-history"/initial_manifest
        previous.mkdir(parents=True)
        for name in ("source","source-manifest.json","public-only"):
            (activity/name).rename(previous/name)
            (activity/name).symlink_to(tested_folder/name,target_is_directory=name!="source-manifest.json")
    if witness.is_file():shutil.copyfile(witness,out/"public-witness.json")
    save(out/"acceptance.json",dict(**result,initial_implementation_manifest=initial_manifest,
         measured_workload_cpu_s=cpu()-started_cpu,engineering_attempts=len(list((out/"attempts").glob("*/receipt.json")))))
    need(result["pass"],"public qualification gate stopped; no native release")
