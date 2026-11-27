"""Typeset released quantities and carry their origin into an occurrence ledger."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import subprocess
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(subprocess.check_output(["git", "-C", str(HERE), "rev-parse", "--show-toplevel"], text=True).strip())
MAIN = "docs/mainline/"
REV = MAIN + "t11-eswa-revision/"
REL = REV + "t11-3/"
PRE = "e3484fd1967164bfb3fe7b5d9c0309e513e95444"
PANEL = "93748f272939166b81ae4188299f096b0fa23fe2"
PIN = "76be52b299d817e565d87a92bbd9108d486e163d"
OLD = "abc8ff50c751543a15f993f695939357c8257918"
HOLD = "3487276af9e9759357771d16eb45feceaa3c948a"
INC = "40949cb0c97511b901c180ce6f2334573119bcdb"
SOURCES = {
    "M": (PRE, REV + "method-formalization.md"),
    "D": (HOLD, MAIN + "t4b-holdout-confirmation-v2/README.md"),
    "I": (INC, MAIN + "t7-closeout/manuscript.md"),
    "T": (OLD, MAIN + "t10-submission-en/manuscript.md"),
    "R": (PRE, REV + "risk-reweighting.md"),
    "P": (PANEL, REV + "t11-1/results/analysis/panel.md"),
    "B": (PRE, REV + "supplement-protocol.md"),
    "J": (PRE, REV + "design.json"),
    "K": (PANEL, REV + "t11-1/stage0-receipt.md"),
    "S": (PIN, REL + "editorial-scope.md"),
    "A": (PIN, REL + "reference-metadata.json"),
    "Y": (PRE, REV + "literature-map.md"),
    "C": (PRE, REV + "claims-v2.md"),
    "G": ("650cb3c07f8682c7b8d63dc1b47588d8eeddba95", REL+"figure-scale.json"),
}
MARK = re.compile(r"\{\{([A-Z])(\d+)(?:\.(\d+))?\|([^{}|]+)\}\}")
CITE = re.compile(r"\[@([A-Za-z0-9,]+)\]")
NUM = re.compile(r"[+−-]?\d+(?:,\d{3})*(?:\.\d+)?")
COUNT_WORDS = re.compile(r"\b(?:zero|one|two|three|four|five|six|eight|ten|twelve|twice)\b",re.I)
# A verbal count sometimes describes a design or a threshold in a sentence,
# for which a cited line or a family of rows is the appropriate source unit.
VERBAL = (
    ("Let *N*", "M", 47, 51), ("The scheduler starts", "M", 15, 24),
    ("A registration hint", "M", 24, 24), ("An eligible primary", "M", 11, 11),
    ("For a possible inspection", "M", 36, 43), ("The confirmation panel", "T", 69, 73),
    ("Table A reports", "D", 9, 16), ("The middle stratum", "D", 45, 47),
    ("Two earlier development", "T", 98, 98), ("## 5. Two synthetic", "I", 7, 9),
    ("Each family contributed", "I", 19, 27), ("Of {{I31", "I", 31, 31),
    ("The supplementary panel", "P", 3, 12), ("The myopic value-of-information", "B", 15, 22),
    ("For POMCP,", "P", 11, 18), ("Two descriptive slices", "P", 80, 88),
    ("Each one-at-a-time", "P", 63, 72), ("Table F applies", "R", 19, 25),
    ("**Table F.", "R", 19, 25), ("Changing the assumed mix", "R", 21, 27),
    ("A selector developed", "C", 9, 10), ("For these paired synthetic", "I", 7, 25),
)
EQ = {
    "posterior": ("M", 18, 21, "b(w | h) = b₀(w)R(w)A(w)I(w)S(w) / Σᵥ b₀(v)R(v)A(v)I(v)S(v)"),
    "endpoints": ("M", 28, 28, "L = ∫_{d(t)>0} [(d(t) − y(t))/d(t)] dt,     U = ∫ (d(t) − y(t)) dt"),
    "complexity": ("M", 49, 51, "Pₘ = ∑_{j=0}^m m!/(m−j)!,     time = O(Cᵦ + F Pₘ (g+1)(Ccal + N Ceval))"),
    "objective": ("M", 30, 32, "J(π | h) = Eᵦ[L̂ + λ(T̂staff + κ F̂)]"),
    "inspection": ("M", 36, 40, "Q(i) = (1−q) ∑_{z: μᶻ>0} μᶻ min_{σ∈Sᵢ,ᶻ} C(i,σ;bᶻ) + q C(i,∅;b)"),
}
def require(condition, message):
    if not condition:
        raise ValueError(message)

@lru_cache(maxsize=None)
def blob(commit, path):
    return subprocess.check_output(["git", "cat-file", "blob", commit + ":" + path], cwd=ROOT)

@lru_cache(maxsize=None)
def lines(source):
    return blob(*SOURCES[source]).decode("utf8").splitlines()

def digest(data):
    return hashlib.sha256(data).hexdigest()

def tsv(records):
    dest = io.StringIO(newline="")
    writer = csv.DictWriter(dest, fieldnames=list(records[0]), delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(records)
    return dest.getvalue()

def normalized(token):
    return Decimal(token.replace(",", "").replace("−", "-"))

def one_location(key, number, column):
    line = lines(key)[number-1]
    if column:
        require(line.startswith("|"), f"Not a table at {key}{number}")
        return line.strip("|").split("|")[column-1].strip()
    return line

def initials(given):
    pieces = re.findall(r"[^\W\d_]+|-", given, flags=re.UNICODE)
    return " ".join(p[0].upper()+"." if p!="-" else p for p in pieces).replace(" - ","-")

def author_list(names):
    if len(names)>20:
        return ", ".join(names[:19]) + ", … " + names[-1]
    return ", ".join(names[:-1]) + ", & " + names[-1] if len(names)>1 else names[0]

def reference_title(record):
    """Sentence case with the proper names/acronyms in the registered titles."""
    keep={"monte":"Monte","carlo":"Carlo","markov":"Markov","bayesian":"Bayesian",
          "frontier":"Frontier","bcube":"BCube","sc24":"SC24"}
    def word(match):
        token=match[0]
        return keep.get(token.casefold(),token if token.isupper() else token.lower())
    title=re.sub(r"[^\W\d_]+",word,record["title"].rstrip("."),flags=re.UNICODE)
    return re.sub(r"(^|: )(\w)",lambda m:m[1]+m[2].upper(),title)

def publications():
    meta = json.loads(blob(*SOURCES["A"]))
    registry = json.loads(blob(PRE,REV+"doi-verification.json"))["records"]
    registered = {x["doi"].lower(): x for x in registry}
    require(len(meta)==len(registered)==50, "Fixed DOI denominator")
    refs = {}
    surname_people = {}
    for r in meta:
        person=r["authors"][0]
        surname_people.setdefault(person["family"],set()).add(initials(person["given"]))
    for i,r in enumerate(meta):
        frozen=registered[r["doi"]]
        require((r["title"],r["venue"],r["year"])==(frozen["title"],frozen["venue"],frozen["published"][0]),"Registry mismatch "+r["id"])
        authors = r["authors"]
        names = [a["family"]+", "+initials(a["given"]) if a["family"] else a["name"] for a in authors]
        label = authors[0]["family"]
        if len(surname_people[label])>1:
            label=initials(authors[0]["given"])+" "+label
        if len(authors)==2: label += " & " + authors[1]["family"]
        if len(authors)>2: label += " et al."
        place = ("*, *"+r["volume"]+"*") if r["volume"] else "*"
        place += ("("+r["issue"]+")") if r["volume"] and r["issue"] else ""
        page = r["pages"].replace("-", "–") or r["article_number"]
        url="https://doi.org/"+r["doi"]
        entry = f'{author_list(names)} ({r["year"]}). {reference_title(r)}. *{r["venue"]}{place}'
        if page: entry += ", " + page
        entry += f". [{url}]({url})"
        refs[r["id"]]=(label,str(r["year"]),entry,"A",f"/{i} ({r['doi']})",r)
    extras = {
        "POMCP": ("Silver & Veness","2010","Silver, D., & Veness, J. (2010). Monte-Carlo planning in large POMDPs. *Advances in Neural Information Processing Systems*. [Proceedings](https://proceedings.neurips.cc/paper/2010/hash/edfbe1afcf9246bb0d40eb4d8027d90f-Abstract.html)","B","L26, original proceedings link"),
        "FEMA": ("Federal Emergency Management Agency","n.d.","Federal Emergency Management Agency. (n.d.). *National Risk Index technical documentation*. [Risk methodology](https://www.fema.gov/sites/default/files/documents/fema_national-risk-index_technical-documentation.pdf)","R","L15, technical documentation"),
        "STRESS": ("Monks et al.","2019","Monks, T., Currie, C. S. M., Onggo, B. S., Robinson, S., Kunc, M., & Taylor, S. J. E. (2019). Strengthening the reporting of empirical simulation studies: Introducing the STRESS guidelines. *Journal of Simulation, 13*(1), 55–67. [https://doi.org/10.1080/17477778.2018.1442155](https://doi.org/10.1080/17477778.2018.1442155)","T","reference [9]"),
        "LONDON": ("Google Cloud","2026b","Google Cloud. (2026b, November 4). *Incident report for europe-west2-b*. [Service Health](https://status.cloud.google.com/incidents/Xs2XTHzAVC9YnafnPyzj)","T","reference [11]"),
        "NL": ("Google Cloud","2026a","Google Cloud. (2026a, July 25). *Incident report for europe-west4-a*. [Service Health](https://status.cloud.google.com/incidents/3BvH3LVGcupoYqV6F4Nw)","T","reference [12]"),
    }
    refs.update({k:(*v,{}) for k,v in extras.items()})
    return refs

def compile_article():
    template=(HERE/"article.in.md").read_text(encoding="utf8")
    refs=publications()
    records, output, cited = [],[],set()
    section="front matter"
    def log(where,kind,display,source,locator,source_value):
        commit,path=SOURCES[source]
        records.append(dict(id=f"N{len(records)+1:04}",section=section,article_location=where,
                            kind=kind,display=display,source_commit=commit,source_file=path,
                            source_locator=locator,source_value=source_value))
    def section_id(where,n):
        require(1<=int(n)<=8, "Unregistered section")
        log(where,"editorial section",n,"S","L3, ordered section range","1–8")
    for no,line in enumerate(template.splitlines(),1):
        where=f"article.in.md L{no}"
        head=re.match(r"^## (\d+)\. (.+)$",line)
        if head:
            section=head[0][3:]
            section_id(where,head[1])
        words=COUNT_WORDS.findall(line)
        if words:
            item=next((s for s in VERBAL if line.startswith(s[0])),None)
            require(item is not None,f"Unmapped verbal count {where}: {words}")
            _,key,first,last=item
            excerpt=" ".join(lines(key)[first-1:last])
            for word in words:
                log(where,"verbal count or design convention",word,key,f"L{first}–L{last}",excerpt.split("[http")[0][:330].rstrip())
        def resolve(m):
            k,n,c,desired=m.groups()
            n=int(n)
            c=int(c or 0)
            if k=="S":
                section_id(where,desired)
                return desired
            expr,_,position=desired.partition("@")
            absolute=expr.endswith("#abs")
            expr=expr.removesuffix("#abs")
            if absolute: expr=expr.lstrip("−-")
            cell=one_location(k,n,c)
            raw=list(NUM.finditer(cell))
            wanted=list(NUM.finditer(expr))
            require(wanted,f"Empty numeric tag {where}: {m[0]}")
            start=int(position)-1 if position else 0
            for token in wanted:
                target=normalized(token[0])
                index=next((i for i in range(start,len(raw)) if (abs(normalized(raw[i][0])) if absolute else normalized(raw[i][0]))==target),None)
                require(index is not None and (not position or index==start),
                        f"{where}: {m[0]} could not match {token[0]} in {cell}")
                origin=f"L{n}"+(f", column {c}" if c else "")+f", token {index+1}"
                log(where,"magnitude in prose" if absolute else "reported quantity or identifier",token[0],k,origin,raw[index][0])
                start=index+1
            return expr
        def cite(m):
            ids=m[1].split(",")
            cited.update(ids)
            ordered=sorted(ids,key=lambda k:(refs[k][0].casefold(),refs[k][1]))
            for k in ordered:
                r=refs[k]
                log(where,"citation",r[0]+", "+r[1],r[3],r[4],r[1])
            return "("+("; ".join(refs[k][0]+", "+refs[k][1] for k in ordered))+")"
        equation=re.fullmatch(r"\{\{EQ:(\w+)\}\}",line)
        if equation:
            key=equation[1]
            src,a,b,formula=EQ[key]
            excerpt=" ".join(lines(src)[a-1:b])
            log(where,"displayed equation",formula,src,f"L{a}–L{b}",excerpt)
            output.append(f'<p class="equation" data-equation="{key}">{formula.replace("<","&lt;").replace(">","&gt;")}</p>')
            continue
        plain=CITE.sub("",MARK.sub("",line))
        if head:plain=re.sub(r"^## \d+\. ","",plain)
        require(not NUM.search(plain),f"Untraced number {where}: {plain}")
        output.append(CITE.sub(cite,MARK.sub(resolve,line)))
    require(cited==set(refs),f"Uncited or missing works {set(refs)^cited}")
    section="References"
    output+=["","## References",""]
    for key in sorted(refs,key=lambda k:refs[k][2].casefold()):
        label,year,entry,src,loc,raw=refs[key]
        visible=re.sub(r"\[([^]]+)\]\([^)]+\)",r"\1",entry)
        for x in NUM.finditer(visible):
            log("reference "+key,"bibliographic number or identifier",x[0],src,loc,(raw.get("doi") or year))
        output.extend([entry,""])
    scale=json.loads(blob(*SOURCES["G"]))
    for i,tick in enumerate(scale["major_ticks"]):
        log("Figure A, x axis","axis graduation (ms)",str(tick),"G",f"/major_ticks/{i}",str(tick))
    log("Figure A, legend","percentile label","95","P","L129, column 5","P95 ms")
    for i,role in enumerate(("centre replay","myopic online","POMCP online"),131):
        for j,statistic in enumerate(("median","95th percentile","maximum"),4):
            val=one_location("P",i,j)
            log("Figure A, "+role,"graphical mark "+statistic,val,"P",f"L{i}, column {j}",val)
    return "\n".join(output).rstrip()+"\n",records
