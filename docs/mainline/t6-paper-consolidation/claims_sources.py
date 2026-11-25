"""Read numeric evidence from immutable Git objects using only the standard library."""
from fractions import Fraction
from functools import lru_cache
import gzip
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BASE = "383c00c3137958dd146d784a6e6251dbe9e603e7"
T4B = "3487276af9e9759357771d16eb45feceaa3c948a"
T4D = "036ccfdf2d6e5d4b39ba11da480fa2a3d69c1f9f"
OLD = "29ac5a2eac2e6527cbfd04145b0caa2c9206c09e"
NEW = "87cdd7183970a7787616c666246b38b9fce8320b"
P4B = "docs/mainline/t4b-holdout-confirmation-v2/results.json.gz"
P4D = "docs/mainline/t4d-cost-baseline-v1/development-result.json.gz"
POLD = "docs/mainline/t5-landscape-diagnostic-v3a/results.json.gz"
PNEW = "docs/mainline/t5-observable-selector-v3c/confirmation-result.json"
PDESIGN = "docs/mainline/t5-landscape-diagnostic-v3a/design.json"
P1 = "docs/mainline/t6-paper-consolidation/stage1-evidence.json"
FAMS = ("WATER_HEAT","NETWORK_POWER","RESERVE_TRANSFER","COOLING_ACCESS","LONDON","NETHERLANDS")
NAMES = dict(zip(FAMS,("水侧与热","网络与供电","有限备用","冷却与通行","伦敦式","荷兰式"),strict=True))


def require(ok, why):
    if not ok:
        raise ValueError("claims: "+why)


def packed(obj):
    return (json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+"\n").encode("utf8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def ptr(data,path):
    if path=="": return data
    require(isinstance(path,str) and path.startswith("/"),"invalid JSON pointer: "+str(path))
    for part in path[1:].split("/"):
        key=part.replace("~1","/").replace("~0","~")
        data=data[int(key)] if isinstance(data,list) else data[key]
    return data


def fraction(v):
    require(type(v) in (int,float) and math.isfinite(v),"non-numeric or nonfinite source field "+repr(v))
    return Fraction(v)


def mean(values):
    require(bool(values),"empty numeric denominator")
    return sum(values,Fraction())/len(values)


@lru_cache(None)
def revision(commit):
    require(re.fullmatch(r"[0-9a-f]{8,40}",commit),"expected immutable Git revision")
    return subprocess.check_output(["git","-C",str(ROOT),"show","-s","--format=%H",commit],text=True).strip()


@lru_cache(None)
def git_bytes(commit,path):
    pp=PurePosixPath(path)
    require(not pp.is_absolute() and ".." not in pp.parts and (path.startswith("docs/mainline/") or path.startswith("src/"))
            and not any(p.lower().endswith(".bin") or "seed" in p.lower() or "custody" in p.lower() for p in pp.parts),
            "source outside sealed result/code files: "+path)
    return subprocess.check_output(["git","-C",str(ROOT),"show",commit+":"+path])


class Book:
    def __init__(self):
        self.files={}
        self.cache={}

    def raw(self,commit,path):
        rev=revision(commit);raw=git_bytes(rev,path)
        if (rev,path) not in self.files:
            self.files[rev,path]=dict(commit=rev,path=path,sha256=sha(raw))
        return raw

    def get(self,commit,path):
        key=(revision(commit),path)
        if key not in self.cache:
            data=self.raw(*key)
            self.cache[key]=json.loads(gzip.decompress(data) if path.endswith(".gz") else data)
        return self.cache[key]

    def text(self,commit,path):
        return self.raw(commit,path).decode("utf8")

    def ref(self,commit,path,field):
        rev=revision(commit)
        if path.endswith((".json",".json.gz")):
            ptr(self.get(rev,path),field)
        else:
            lines=self.text(rev,path).splitlines()
            m=re.fullmatch(r"L(\d+)(?:-L?(\d+))?",field)
            require(m and 1<=int(m[1])<=int(m[2] or m[1])<=len(lines),"invalid line anchor: "+field)
        return dict(commit=rev,path=path,field=field)

    def value(self,metric):
        fields=metric["fields"];data=self.get(metric["commit"],metric["path"])
        op=metric["op"];indices=metric.get("rows")
        require(fields and all(isinstance(x,str) for x in fields),"field list")
        if indices is None:
            raw=[ptr(data,f) for f in fields]
            if op in ("rational_value","rational_subtract"):
                require(len(raw)==(1 if op=="rational_value" else 2) and
                        all(isinstance(v,str) and re.fullmatch(r"-?(?:0|[1-9]\d*)(?:/[1-9]\d*)?",v) for v in raw),
                        "expected original rational string fields")
                return Fraction(raw[0]) if op=="rational_value" else Fraction(raw[0])-Fraction(raw[1])
            if op=="value":
                require(len(raw)==1,"one scalar for value")
                return fraction(raw[0])
            if op=="length":return Fraction(len(raw[0]))
            if op=="count_true":return Fraction(sum(v is True for v in raw))
            if op=="count":return Fraction(len(raw))
            numbers=[fraction(x) for x in raw]
            if op=="subtract":return numbers[0]-numbers[1]
            if op=="mean":return mean(numbers)
            if op=="sum":return sum(numbers,Fraction())
            raise ValueError("unknown scalar operation "+op)
        require(indices and len(set(indices))==len(indices) and all(type(i) is int and i>=0 for i in indices),"unrepeated selected indices")
        groups=[[ptr(data,f.replace("{i}",str(i))) for f in fields] for i in indices]
        if op=="count":return Fraction(len(groups))
        if op=="count_true":return Fraction(sum(a[0] is True for a in groups))
        vals=[[fraction(x) for x in a] for a in groups]
        if op=="mean":return mean([a[0] for a in vals])
        if op=="sum":return sum((x[0] for x in vals),Fraction())
        if op in ("fixed_best","fixed_second","rowwise_best_gap"):
            # First column: certified lower bound; remaining columns: frozen candidate Ls.
            if op=="rowwise_best_gap":return mean([min(a[1:])-a[0] for a in vals])
            cols=sorted(mean([a[j]-a[0] for a in vals]) for j in range(1,len(fields)))
            return cols[0 if op=="fixed_best" else 1]
        require(len(fields)>=2,"paired outcome columns")
        # Two columns are an ordinary pair. More than two control columns implement
        # the declared post-hoc best status quo or the retrospective candidate envelope.
        dif=[a[0]-min(a[1:]) for a in vals]
        if op=="mean_delta":return mean(dif)
        if op=="better":return Fraction(sum(v<0 for v in dif))
        if op=="equal":return Fraction(sum(v==0 for v in dif))
        if op=="worse":return Fraction(sum(v>0 for v in dif))
        if op in ("at_bound","above_tolerance"):
            tol=Fraction(metric["tolerance"])
            require(min(dif)>=0,"negative gap to certified bound")
            return Fraction(sum(v<=tol for v in dif) if op=="at_bound" else sum(v>tol for v in dif))
        raise ValueError("unknown row operation "+op)

    def num(self,id,label,unit,commit,path,fields,op="value",rows=None,**kwargs):
        metric=dict(id=id,label=label,unit=unit,commit=revision(commit),path=path,
                    fields=[fields] if isinstance(fields,str) else list(fields),op=op)
        if rows is not None:metric["rows"]=list(rows)
        metric.update(kwargs)
        n=self.value(metric)
        metric["value"]=int(n) if n.denominator==1 else float(n)
        metric["exact"]=str(n)
        return metric


def roster(book):
    d=book.get(OLD,PDESIGN)["roles"]
    full=d["random"]+d["reference"]
    main=d["random"]+[r for r in d["reference"] if r.startswith(("MAIN-R-","MAIN-U-"))]
    require(len(set(main))==len(main)==54 and len(set(full))==len(full)==58
            and [r for r in full if r not in main]==["B_COST","V_COST","M","M_HOT"],"frozen policy pools")
    return main,full
