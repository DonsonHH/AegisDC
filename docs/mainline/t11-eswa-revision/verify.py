"""Read-only document, provenance and public arithmetic checks for T11-0."""
import argparse
from collections import Counter
from decimal import Decimal
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
import csv
import html
import json
import re
import runpy
import subprocess
import time
from urllib.parse import quote, unquote, urlparse

from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PACKAGE = HERE.relative_to(ROOT).as_posix()
BASE = "abc8ff50c751543a15f993f695939357c8257918"
V1 = "0a97b43aefd8f6b6fe1af8af57e7d990b223749a"
FREEZE = "4f6843a8c56de353cfaaedcafb88f9e46a84e5f1"
RECEIPT_SHA = "8dfc03a7c1df9c254f246e1d40add424a0c04218ffdd345acc2b05ade6dc7284"
FILES = {
    ".gitattributes", "README.md", "claims-v2.md", "positioning-and-outline.md", "gap-audit.md",
    "literature-map.md", "doi-verification.json", "method-formalization.md", "design.json",
    "supplement-protocol.md", "protocol-lock.json", "protocol-addendum.md", "protocol-freeze.json",
    "risk-reweighting.md", "public-weighting.py", "risk-family-means.tsv", "risk-scenarios.tsv",
    "advisor-note.md", "advisor-note.html", "advisor-note.pdf", "review-and-receipt.md", "verify.py",
    "SHA256SUMS.txt",
}

def require(value, message):
    if not value:
        raise ValueError(message)

def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)

@lru_cache(maxsize=None)
def public_blob(revision, path):
    # Links to the confirmation chapter may resolve only its already-published report.
    if "t4b-holdout-confirmation-v2/" in path:
        require(path == "docs/mainline/t4b-holdout-confirmation-v2/README.md", "restricted confirmation path")
    return git("cat-file", "blob", revision+":"+path)

def read(name):
    return (HERE/name).read_text(encoding="utf8")

def obj(name):
    return json.loads(read(name))

def digest(data):
    return sha256(data).hexdigest()

def check_lock():
    current = obj("protocol-freeze.json")
    require(digest((HERE/"protocol-freeze.json").read_bytes()) == RECEIPT_SHA, "effective protocol digest")
    previous = obj("protocol-lock.json")
    require(set(previous["files"]) == {"design.json", "method-formalization.md", "supplement-protocol.md"}, "v1 contents")
    require(set(current["files"]) == set(previous["files"]) | {"protocol-lock.json", "protocol-addendum.md"}, "v1.1 contents")
    for name, sha in current["files"].items():
        data = (HERE/name).read_bytes()
        require(digest(data) == sha and public_blob(FREEZE, PACKAGE+"/"+name) == data, "v1.1 frozen bytes: "+name)
        if name in previous["files"] or name == "protocol-lock.json":
            require(public_blob(V1, PACKAGE+"/"+name) == data, "original frozen bytes: "+name)
    require(git("rev-parse",V1+"^").decode().strip() == BASE and
            git("rev-parse",FREEZE+"^").decode().strip() == V1, "effective freeze follows initial lock")
    require(public_blob(FREEZE, PACKAGE+"/protocol-freeze.json") == (HERE/"protocol-freeze.json").read_bytes(),
            "committed authoritative receipt")
    return obj("design.json")

def check_design(design):
    panel = design["panel"]
    archive = public_blob(panel["input_revision"], panel["archive"])
    require(digest(archive)==panel["archive_sha256"],"only the consumed development archive")
    alloc,par = design["allocation"],design["parameters"]
    centre=par["centre"]
    settings=set()
    for j,grid in enumerate(par["grid"]):
        require(len(set(grid))==3 and grid[1]==centre[j],"OAT centre")
        for v in (grid[0],grid[2]):
            variant=centre.copy();variant[j]=v
            settings.add(tuple(variant))
    require(centre==[1,30,.95,1/32] and par["grid"]==[[.5,1,2],[15,30,60],[.85,.95,.99],[1/64,1/32,1/16]],
            "specified OAT grid")
    roles=len(settings)+len(design["baselines"])
    n=panel["N"]; points=n*roles
    require(roles==alloc["roles"]==10 and points==alloc["positions"]==720,"non-centre positions")
    require(points*61==alloc["max_public_decisions"] and n*61==alloc["max_timing_worker_calls"],"real call bounds")
    pom=design["baselines"]["pomcp"]; simulations=n*61*pom["simulations_per_elective_root"]
    amendments=obj("protocol-freeze.json")["operational_amendments"]
    require(simulations==amendments["max_leaf_evaluations"] and simulations*pom["max_public_tree_steps"]==alloc["max_tree_transitions"],
            "tree and separate leaf caps")
    job_count=(roles-1)*alloc["batches_per_role"]
    require(alloc["conditions_per_batch"]*alloc["batches_per_role"]==n and job_count==alloc["ordinary_jobs"],
            "complete batch membership")
    require(job_count+alloc["pomcp_jobs"]+sum(count for _,count,_ in alloc["support"])==alloc["max_jobs"]==63,"job ceiling")
    total=job_count*alloc["ordinary_job_s"]+alloc["pomcp_jobs"]*alloc["pomcp_job_s"]+sum(count*secs for _,count,secs in alloc["support"])
    require(total==alloc["max_reserved_cpu_s"]==229800 and alloc["scientific_retries"]==0,"single-core allocation ceiling")
    risk=design["scenario_weighting"]
    require(list(risk["frequency_numerators"].values())==[[10]*6,[12,12,12,12,6,6],[3,3,3,3,24,24]],"frequency assumptions")
    require(design["current_activity"]=={"facility_calls":0,"slurm_jobs":0,"h2_generate_read_derive":[0]*3,
            "h3_generate_read_derive":[0]*3,"full_manuscript_rewrite":False},"current gate")
    print("PASS frozen method, common action mask, observation boundary, 72 archived inputs, 720 future positions, 63 jobs and 229800 reserved CPU seconds")

def check_claims(design):
    cn=public_blob(design["accepted_science"],"docs/mainline/t9-submission-r1/manuscript.md").decode()
    new=read("claims-v2.md")
    values = lambda s: re.findall(r"[+−-]?\d+(?:\.\d+)?",s)
    for endpoint in ("H1","H2","H3","HA","HB","HC"):
        old=next(l for l in cn.splitlines() if l.startswith("| "+endpoint+"　")).strip("|").split("|")
        row=next(l for l in new.splitlines() if l.startswith("| "+endpoint+" |")).strip("|").split("|")
        require(values(row[2])==values(old[2]) and values(row[3])==values(old[3]),"original estimate/interval: "+endpoint)
        require(("INDETERMINATE" if endpoint=="HC" else "MET") in row[4],"original outcome: "+endpoint)
    for phrase in ("部分成立","登记的迁移优势不成立","未建立","80.49 秒 [41.31, 123.48]","R−O","26.25","38.152"):
        require(phrase in new,"claim boundary: "+phrase)
    lines=[l for l in read("positioning-and-outline.md").splitlines() if re.match(r"^\| [^|]+\| [0-9]+\.[0-9]+ \|",l)]
    budgets=[Decimal(l.split("|")[2].strip()) for l in lines if "**合计**" not in l]
    require(len(budgets)==11 and sum(budgets)==16,"section budgets")
    paper=PdfReader(HERE/"advisor-note.pdf")
    require(len(paper.pages)==paper.trailer["/Root"]["/Pages"]["/Count"]==1,"physical mentor page")
    text="".join((paper.pages[0].extract_text() or "").split())
    require(all(x in text for x in ("完整","144","55.83","53.67","59.91","31.85","FEMA","RSI","另立")),
            "mentor brief covers scope and separate research")
    print("PASS six archived endpoints, four bounded claims, 16-page outline and one-page Chinese mentor brief")

def check_literature(live):
    rows=obj("doi-verification.json")["records"]; mapping=read("literature-map.md")
    entries=[l for l in mapping.splitlines() if re.match(r"\| [VPFIE]\d\d \|",l)]
    require(len(entries)==len(rows)==len({r["doi"].lower() for r in rows})==50,"unique literature count")
    require(len({r["title"].casefold() for r in rows})==50,"unique works")
    require(sum(2022<=r["published"][0]<=2026 for r in rows)==43 and sum(r["venue"]=="Expert Systems with Applications" for r in rows)==8,
            "publication years and ESWA set")
    for rec in rows:
        doi=rec["doi"]
        hits=[l for l in entries if "["+doi+"](" in l]
        require(len(hits)==1 and rec["title"].replace("|",r"\|") in hits[0] and f'| {rec["published"][0]} |' in hits[0],
                "title, year and DOI in reference map: "+doi)
        require(len(hits[0].split("|")[-3].strip())>15 and rec["authors"] and rec["venue"],"relationship and authors: "+doi)
        require(doi.casefold()==rec["crossref_record"].casefold() and rec["handle_code"]==1 and
                urlparse(rec["handle_target"]).scheme in ("http","https"),"archived DOI registration/handle: "+doi)
    if live:
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        with requests.Session() as session:
            session.headers["User-Agent"]="AegisDC-publication-reference-check/1.0"
            retries=Retry(total=5,backoff_factor=1,status_forcelist=(429,500,502,503,504),
                          allowed_methods={"GET"},respect_retry_after_header=True)
            session.mount("https://",HTTPAdapter(max_retries=retries))
            for rec in rows:
                encoded=quote(rec["doi"],safe="/")
                upstream=session.get("https://api.crossref.org/works/"+encoded,timeout=30)
                upstream.raise_for_status()
                cr=upstream.json()["message"]
                resolution=session.get("https://doi.org/api/handles/"+encoded,timeout=30)
                resolution.raise_for_status()
                handle=resolution.json()
                title=" ".join(html.unescape(re.sub("<[^>]+>"," ",cr["title"][0])).split())
                require(cr["DOI"].casefold()==handle["handle"].casefold()==rec["doi"].casefold()
                        and handle["responseCode"]==1 and cr["published"]["date-parts"][0][0]==rec["published"][0]
                        and title==rec["title"],"live DOI identity, title and year: "+encoded)
                time.sleep(.35)
    print("PASS 50 DOI records/50 individual relevance notes; 43 published in 2022–2026; 8 ESWA; "+("fresh network lookup" if live else "archived registry and resolver records"))

def links():
    count=0
    for name in sorted(FILES):
        if not name.endswith(".md"): continue
        for m in re.finditer(r"\]\(((?:\\.|[^)\s])+)\)",read(name)):
            url=m[1].replace(r"\(","(").replace(r"\)",")")
            if url.startswith("https://github.com/DonsonHH/AegisDC/blob/"):
                ref=url.split("/blob/",1)[1];rev,path=ref.split("/",1)
                path,_,anchor=path.partition("#"); data=public_blob(rev,unquote(path)); count+=1
                if anchor.startswith("L"):
                    loc=re.fullmatch(r"L(\d+)(?:-L(\d+))?",anchor)
                    require(loc and 1<=int(loc[1])<=int(loc[2] or loc[1])<=len(data.splitlines()),"Git line locator: "+url)
            elif "://" not in url and not url.startswith("#"):
                file=unquote(url.split("#",1)[0])
                require(file in FILES and (HERE/file).is_file(),"local delivery link: "+url)
    return count

def main(write,checkout,live):
    design=check_lock();check_design(design);check_claims(design);check_literature(live)
    output=runpy.run_path(str(HERE/"public-weighting.py"))["results"]()
    for name,content in output.items(): require((HERE/name).read_bytes()==content.encode(),"public result readback: "+name)
    rows=list(csv.DictReader(read("risk-scenarios.tsv").splitlines(),delimiter="\t"))
    require(len(rows)==15 and len(output["risk-family-means.tsv"].splitlines())==31,"risk matrix dimensions")
    manifest="".join(digest((HERE/f).read_bytes())+"  "+f+"\n" for f in sorted(FILES-{"SHA256SUMS.txt"}))
    if write:(HERE/"SHA256SUMS.txt").write_bytes(manifest.encode())
    require((HERE/"SHA256SUMS.txt").read_bytes()==manifest.encode(),"delivery hashes")
    print(f"PASS 3 mixtures x 5 roles; all five endpoints and paired differences reconstructed; {links()} pinned Git file links")
    if checkout:
        files=set(git("ls-tree","-r","--name-only","HEAD","--",PACKAGE+"/").decode().splitlines())
        require(files=={PACKAGE+"/"+f for f in FILES},"declared Git files")
        for f in FILES:require((HERE/f).read_bytes()==public_blob("HEAD",PACKAGE+"/"+f),"fresh checkout bytes: "+f)
        require(not git("diff","--name-only",BASE,"HEAD","--",":(top,exclude)"+PACKAGE+"/**"),"old packages changed")
        print(f"PASS {len(FILES)} files byte-for-byte; all tracked paths outside T11 equal T10")
    print("Effective protocol SHA-256:",RECEIPT_SHA)

if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    mode=cli.add_mutually_exclusive_group()
    mode.add_argument("--check",action="store_true",help="read-only verification (default)")
    mode.add_argument("--write-manifest",action="store_true",help="write the publication digest list")
    cli.add_argument("--checkout-bytes",action="store_true")
    cli.add_argument("--live-dois",action="store_true",help="refresh all Crossref/Handle identities as an extra network check")
    args=cli.parse_args()
    main(args.write_manifest,args.checkout_bytes,args.live_dois)
