"""Read and weight already published per-condition scores. No simulator imports."""
import argparse
import csv
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
from io import StringIO
from pathlib import Path
import gzip
import json
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
FIELDS=("L","U","person","tool","fee")

def blob(rev,path):
    return subprocess.check_output(["git","cat-file","blob",rev+":"+path],cwd=ROOT)

def require(condition, message):
    if not condition:
        raise ValueError(message)

def read_scores(spec,revkey,pathkey,hashkey):
    data=blob(spec[revkey],spec[pathkey])
    if sha256(data).hexdigest()!=spec[hashkey]:raise ValueError(spec[pathkey])
    return json.loads(gzip.decompress(data),parse_float=Decimal)

def table(header,rows):
    buf=StringIO()
    writer=csv.writer(buf,delimiter="\t",lineterminator="\n")
    writer.writerow(header);writer.writerows(rows)
    return buf.getvalue()

def fmt(value):
    return format(Decimal(value.numerator)/Decimal(value.denominator),".6f")

def results():
    design=json.loads((HERE/"design.json").read_text(encoding="utf8"))
    p=design["panel"]; risk=design["scenario_weighting"]
    raw=blob(p["input_revision"],p["manifest"])
    require(sha256(raw).hexdigest()==p["manifest_sha256"], "Development manifest digest")
    manifest=json.loads(raw); keys=manifest["order"]; hashes=manifest["files"]; N=p["N"]
    require(len(keys)==len(set(keys))==len(hashes)==N and manifest["input_archive"]==p["archive_sha256"],
            "Unique condition denominator and frozen archive identity")
    c=read_scores(p,"score_revision","scores","scores_sha256")
    d=read_scores(p,"bcost_revision","bcost_base","bcost_sha256")
    old=json.loads(blob(p["bcost_revision"],"docs/mainline/t4d-cost-baseline-v1/settings-and-conditions.json"))
    require(old["order"]==keys and old["public_inputs"]==hashes and old["old_result_sha256"]==p["scores_sha256"],
            "T4d parent score, order and per-condition input digests")
    require([r["key"] for r in c["rows"]]==[r["key"] for r in d["panels"]["BASE"]]==keys,
            "Published score order")
    roles=risk["roles"]; families=p["families"]; by={(f,a):[] for f in families for a in roles}
    for a in roles:
        units=[u for u in (d if a=="B_COST" else c)["units"] if u["role"]==a and (a!="B_COST" or u["mode"]=="BASE")]
        require(len(units)==N and {u["key"]:u["input"] for u in units}==hashes, "Role inputs: "+a)
    for x,y in zip(c["rows"],d["panels"]["BASE"],strict=True):
        require(all(x[k]==y[k] for k in ("key","family","duration","layer")), "Row descriptors: "+x["key"])
        for a in roles:
            arm=(y if a=="B_COST" else x)["arms"][a]
            if a!="B_COST":
                require(all(x["arms"][a][f]==y["arms"][a][f] for f in FIELDS), "Parent scores: "+a+"/"+x["key"])
            by[x["family"],a].append(tuple(Fraction(arm[k]) for k in FIELDS))
    means={}; family_rows=[]
    for f in families:
        for a in roles:
            group=by[f,a]
            require(len(group)==p["per_family"], "Family denominator: "+f+"/"+a)
            vals=tuple(sum(v)/len(group) for v in zip(*group,strict=True));means[f,a]=vals
            family_rows.append([f,a,len(group),*map(fmt,vals)])
    scenario_rows=[]
    for label,nums in risk["frequency_numerators"].items():
        den=risk["frequency_denominator"]
        require(len(nums)==len(families) and sum(nums)==den and min(nums)>=0, "Frequency mixture: "+label)
        scores={a:tuple(sum(Fraction(k,den)*means[f,a][j] for f,k in zip(families,nums,strict=True))
                        for j in range(len(FIELDS))) for a in roles}
        for a in roles:
            diff=[v-u for v,u in zip(scores["V_COST"],scores[a],strict=True)]
            scenario_rows.append([label,a,N,*map(fmt,scores[a]),*map(fmt,diff)])
    return {"risk-family-means.tsv":table(["family","role","n",*FIELDS],family_rows),
            "risk-scenarios.tsv":table(["frequency_mix","role","source_n",*FIELDS,*["V_COST_minus_role_"+k for k in FIELDS]],scenario_rows)}

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write",action="store_true")
    args=parser.parse_args()
    for name,content in results().items():
        p=HERE/name
        if args.write:p.write_bytes(content.encode())
        elif p.read_bytes()!=content.encode():raise ValueError(name)
    print("PASS six families x twelve rows x five roles; exact rational weighting, six decimals at publication.")
