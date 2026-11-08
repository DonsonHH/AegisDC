"""Narrow saved-byte review of the pre36 archive format correction only."""
from pathlib import Path
import hashlib
import io
import json
import subprocess
import zipfile

ROOT=Path(r"C:\Users\Donson\Documents\ChatGPT\Renly")
OUT=Path(__file__).resolve().parent
SOURCE="f1b1e19112330e82ff2d987a1ab58df0374c1cc9"
REFUSED="9b14d147d9130fc6277307fe12129527d561fd82"
AUDIT="docs/mainline/audits/20261108-pre36/"
checks=[]
def ck(ok,label):
    checks.append({"label":label,"passed":bool(ok)});assert ok,label
def sha(raw):return hashlib.sha256(raw).hexdigest()
def git(*args):return subprocess.check_output(["git","-C",str(ROOT),*args])
def blob(rev,path):return git("cat-file","blob",rev+":"+path)

manifest_path=AUDIT+"delivery-manifest.json"
manifest_bytes=blob(SOURCE,manifest_path);manifest=json.loads(manifest_bytes)
ck(manifest_bytes==blob(REFUSED,manifest_path),"pre-staging manifest unchanged; no new hashes substituted")
ck(blob(SOURCE,"scripts/seal_pre36_audit.py")==blob(REFUSED,"scripts/seal_pre36_audit.py"),"fresh verifier unchanged; no hash waiver")
attrs=blob(SOURCE,".gitattributes").decode().splitlines()
oldattrs=blob(REFUSED,".gitattributes").decode().splitlines()
added=[AUDIT+"reviews/*.zip -text",AUDIT+"ticket-matrix.md -text"]
ck([line for line in attrs if line not in added]==oldattrs and all(attrs.count(line)==1 for line in added),"exactly two path-scoped binary/native-record rules added")
ck(attrs.index("docs/mainline/** text eol=lf")<attrs.index(added[0])<attrs.index(added[1]),"specific byte-preservation rules follow broad docs text rule")
ck(not git("diff","--name-only",REFUSED,SOURCE,"--","src","configs","scripts","tests").strip(),"no model, test, source, exporter or verifier changes")

folders={
    "spec-original":"pre36-spec-audit-01",
    "standards-original":"pre36-standards-audit-01",
    "spec-corrections":"pre36-spec-corrections-01",
    "spec-readout":"pre36-spec-readout-01",
    "standards-corrections":"pre36-standards-corrections-01",
}
archives=[];member_count=0
for role,entry in manifest["review_packets"].items():
    path=entry["path"];raw=blob(SOURCE,path);previous=blob(REFUSED,path);expected=manifest["files"][path]
    ck(len(raw)==expected["bytes"] and sha(raw)==expected["sha256"],"sealed ZIP SHA/size equals unchanged manifest "+role)
    ck((ROOT/path).read_bytes()==raw,"working sealed ZIP bytes equal corrected Git blob "+role)
    ck(previous==raw.replace(b"\r\n",b"\n"),"refused ZIP differs only by broad CRLF normalization "+role)
    folder=ROOT/".work"/folders[role]
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        ck(len(z.namelist())==len(set(z.namelist())) and set(z.namelist())==set(entry["members"]),"exact unique original ZIP member set "+role)
        for name,digest in entry["members"].items():
            member=z.read(name)
            ck(sha(member)==digest and (folder/name).read_bytes()==member,"original sealed reviewer member unchanged "+role+"/"+name)
            member_count+=1
        original_manifests=[name for name,digest in entry["members"].items() if digest==entry["original_manifest_sha256"]]
        ck(len(original_manifests)==1,"original review manifest identity retained "+role)
    archives.append({"role":role,"path":path,"sha256":sha(raw),"bytes":len(raw),"refused_bytes":len(previous),"original_crlf_pairs":raw.count(b"\r\n"),"members":len(entry["members"]),"original_manifest_sha256":entry["original_manifest_sha256"]})
ck(len(archives)==5 and member_count==84,"all five original sealed packets and84 members verified")
matrix=AUDIT+"ticket-matrix.md";raw=blob(SOURCE,matrix);previous=blob(REFUSED,matrix);entry=manifest["files"][matrix]
ck(sha(raw)==entry["sha256"] and len(raw)==entry["bytes"],"original matrix unchanged manifest SHA/size")
ck(raw==(ROOT/".work/pre36-spec-audit-01/ticket-matrix.md").read_bytes(),"matrix restored byte-for-byte from original reviewer source")
ck(previous==raw.replace(b"\r\n",b"\n"),"matrix change restores original CRLF only")

prefix="evidence/mainline/engineering/pre36-delivery-checks/attempt-01/"
failure={name:blob(SOURCE,prefix+name) for name in ["start.json","receipt.json","stderr.log","stdout.log"]}
receipt=json.loads(failure["receipt.json"]);start=json.loads(failure["start.json"])
ck(REFUSED in json.dumps(start),"original fresh-check start identifies refused delivery commit")
ck("spec-original.zip" in failure["stderr.log"].decode() and "AssertionError" in failure["stderr.log"].decode(),"actual first manifest refusal preserved")
ck(receipt['status']=='REFUSED_DELIVERY' and receipt['source']==REFUSED and receipt['exit_code']==1,"original refused terminal not relabelled pass")
classification_path="docs/mainline/evidence/pre36-format-correction.json"
classification_bytes=blob(SOURCE,classification_path);classification=json.loads(classification_bytes)
ck(classification["refused_delivery"]==REFUSED and classification["failure_record"]==prefix.rstrip('/'),"additive classification binds exact original refusal")
ck(all(classification[k]==0 for k in ["new_physical_calls","new_selectors","new_registered_runs"]),"format repair declares no project/research execution")
result={"status":"PASS_NARROW_FORMAT_BYTE_PRESERVATION","source":SOURCE,"refused_source":REFUSED,"delivery_manifest_sha256":sha(manifest_bytes),"archives":archives,"review_members":member_count,"matrix":{"sha256":sha(raw),"bytes":len(raw),"crlf_pairs":raw.count(b"\r\n")},"original_failure_artifacts":[{"path":prefix+n,"sha256":sha(v),"bytes":len(v)} for n,v in failure.items()],"classification_sha256":sha(classification_bytes),"checks":checks,"check_count":len(checks),"review_scope":"Raw Git/archive/member/manifest bytes and precise attributes only; models/readout values not re-audited and no fresh-delivery verifier executed by reviewer.","new_project_calls":{"tests":0,"plant":0,"selector":0,"rng":0,"nonce":0,"capture":0,"project_imports":0,"tracked_edits":0}}
(OUT/"result.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"status":result["status"],"checks":len(checks),"archives":5,"members":member_count,"manifest_unchanged":True,"no_hash_waiver":True,"new_project_calls":0}))
