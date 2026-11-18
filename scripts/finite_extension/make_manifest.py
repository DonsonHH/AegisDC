"""Bind the published source/data hashes to the selected path; issues no authorization."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ARMS, BASE, FIXTURE, OLD, PACK, PYTHON_SHA, REAL, ROOT, RUNTIME, STUDY_OUTPUT, budget, durable, file_sha, prior, read


def construct(route, output_root):
    identity=read(ROOT/"staged.json")
    purpose=REAL if route=="study" else FIXTURE
    if purpose==REAL:
        data=PACK+"conditions.json"
        order=read(ROOT/data)["order"]
        supporting=[PACK+n for n in ("selection.json","protocol.md","static-audit.json","static-transfer.json","qualification.md","selection-notes.md","freeze-addendum.json")]
    else:
        data=OLD+"inputs.json"
        parts=read(ROOT/(PACK+"witnesses.json"))["parts"]
        order=parts["local_in_allocation"] if route=="suite" else parts["separate_serial_scheduler_jobs"]+parts["expected_unsubmitted_suffix"]
        supporting=[PACK+"witnesses.json",PACK+"freeze-addendum.json"]
    return dict(schema="aegisdc-finite-extension-launch-v1",purpose=purpose,route="suite" if route=="suite" else "serial",
        core_revision=prior.CORE_REV,source_revision=identity["revision"],python_sha256=PYTHON_SHA,
        runtime={f:identity["files"][f]["sha256"] for f in RUNTIME},data_path=data,data_sha256=file_sha(ROOT/data),
        supporting={f:file_sha(ROOT/f) for f in supporting},order=order,arm_order=ARMS,output_root=str(output_root),budget=budget(purpose),
        principal_comparison="I/D",background="P",study_authorization="Separate explicit user review of this manifest SHA",
        prerequisites="Fixed code, interpreter, source data and output identity. Readable same-account workspace.")


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("route",choices=["suite","serial","study"]);p.add_argument("output",type=Path);p.add_argument("run_root",type=Path)
    args=p.parse_args();durable(args.output,construct(args.route,args.run_root))
    print(file_sha(args.output))
