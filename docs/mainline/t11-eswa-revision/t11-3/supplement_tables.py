"""Assemble the public supplementary material from released bytes, without scoring."""
import csv
import io
import zipfile
from evidence import HERE, MAIN, PANEL, PRE, REV, blob, digest, lines, tsv

ANALYSIS_FILES = (
    "analysis.json","panel.md","positions.tsv","position-details.jsonl","purchase-splits.tsv",
    "scope-absolute.tsv","scope-contrasts.tsv","timing.tsv","witnesses.tsv",
    "native-evidence-index.tsv","native-readback-receipt.json","SHA256SUMS.txt",
)
JOB_FILES = ("accounting.json","jobs.tsv","per-role-ledger.tsv","slurm-allocation-and-steps.psv")
ORIGINAL = "80f8f089bd2d208ce4e8f4788f3a4c3509f80b9e6b4a15e48b53941015afaff9"
CORRECTED = "3c1956e568b3ca261a2f84b8c6d1d67c5bcd6c2e73f9e22291612f5d22a891e2"

def archive_members():
    root=REV+"t11-1/"
    names=["results/analysis/"+k for k in ANALYSIS_FILES]
    names+=["results/"+k for k in JOB_FILES]
    names+=["results/qualification/"+k+".json" for k in
            ("acceptance","engineering-stop","engineering-disposition","public-witness","historical-fields","identity")]
    names+=["results/qualification/attempts/"+d+"/"+n+".json" for d in (ORIGINAL,CORRECTED) for n in ("receipt","public-witness")]
    names+=["results/center-timing/status.json","stage0-receipt.md","stage0-identity.json","registration.json",
            "source-manifest.json","source-manifest-failed-qualification.json","environment-lock.json"]
    members={n:(PANEL,root+n) for n in names}
    for n in ("risk-scenarios.tsv","risk-family-means.tsv"):
        members["risk/"+n]=(PRE,REV+n)
    members["sacct-135652-135693.json"]=("10b3f7a08462623c22b87b3ae0dae7abe3c95378",root+"sacct-135652-135693.json")
    return members

def archive_index():
    records=[]
    for name,(commit,path) in sorted(archive_members().items()):
        data=blob(commit,path)
        rows=""
        if name.endswith((".tsv",".psv")): rows=len(data.splitlines())-1
        if name.endswith(".jsonl"): rows=len(data.splitlines())
        records.append(dict(archive_member=name,source_commit=commit,source_path=path,
                            data_rows=rows,bytes=len(data),sha256=digest(data)))
    return records

def write_archive():
    index=archive_index()
    (HERE/"supplement-B-index.tsv").write_bytes(tsv(index).encode())
    with zipfile.ZipFile(HERE/"supplement-B-tables.zip","w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as target:
        for entry in index:
            info=zipfile.ZipInfo(entry["archive_member"],(2026,11,27,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            target.writestr(info,blob(entry["source_commit"],entry["source_path"]),compresslevel=9)

def markdown_table(head,rows):
    return "\n".join("| "+" | ".join(row)+" |" for row in [head,["---"]*len(head),*rows])

def read_row(n):
    return [cell.strip() for cell in lines("P")[n-1].strip("|").split("|")]

def readable(value):
    return value.replace("-","−")

def supplement_text():
    sections={}
    groups=["Water-side heat","Network power","Reserve transfer","Cooling access","London analogue",
            "Netherlands analogue","Maintenance 0 s","Maintenance 600 s","Maintenance 1,200 s"]
    strata=[]
    for n,group in enumerate(groups,80):
        row=read_row(n)
        strata.append([group,row[1],row[2],readable(row[5]),readable(row[8])])
    sections["STRATA"]=markdown_table(["Scope","Pairs per comparison","Centre L (s)","Centre − myopic (s)","Centre − POMCP (s)"],strata)
    variants=["Labour price (low)","Labour price (high)","Fee equivalent (low)","Fee equivalent (high)",
              "Sensor match (low)","Sensor match (high)","Unknown report (low)","Unknown report (high)"]
    oat=[]
    for n,label in enumerate(variants,65):
        row=read_row(n)
        oat.append([label,row[2],readable(row[5]),readable(row[7]),readable(row[8])])
    sections["OAT"]=markdown_table(["Parameter","Setting","Δ deficit (s)","Δ labour (person-s)","Δ fees"],oat)
    times=[]
    for n,label in enumerate(["Centre · replay","Myopic · online","POMCP · online",*variants],131):
        row=read_row(n)
        times.append([label,row[2],row[3],row[4],row[5]])
    sections["TIMES"]=markdown_table(["Policy","Timed / planned","Median (ms)","P95 (ms)","Maximum (ms)"],times)
    text=(HERE/"supplement-B.in.md").read_text(encoding="utf8")
    for name,table in sections.items():text=text.replace("{{"+name+"}}",table)
    return text
