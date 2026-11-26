"""Check the submission edition against frozen public sources and its real PDF figures."""
import argparse
import base64
from contextlib import redirect_stdout
from decimal import Decimal
from functools import lru_cache
import hashlib
from io import StringIO
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup
from pypdf import PdfReader
from figure_values import verify_figure_values


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = "28c5969191bab0c7e3c4d508135cc057f89b809d"
EXEC = "c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5"
FREEZE = "cef45c0275ce330eaf2652362bfd5090dffd5aa6"
PREFIX = "docs/mainline/"
FIT = PREFIX + "t8-rsi-wait-repair/stage1b/analysis/"
VECTORS = {"T7":"78f58b7f9b1d9e6d56bd6fedecedb3ff6eca4f64c572c8c0d5c0997baee4ead1",
           "T8":"1c278f463e4e78463673526cd4cb66c16624b8bc94ebffe01e1d718bd4f6d296"}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


@lru_cache(maxsize=None)
def source(path, rev=BASE):
    # This reader accepts public narratives, settings and source, never row archives.
    require(path.endswith((".md", ".py", ".json")) and "/stage2/" not in path and
            "pre-score" not in path and "seed" not in path.lower(), "unexpected source " + path)
    return git("cat-file", "blob", rev+":"+path)


def norm(s):
    return s.replace("−","-").replace("\\*","*").replace("**","").replace(", "," ").replace("，"," ")


def table(text):
    return [[c.strip() for c in line.strip("|").split("|")] for line in text.splitlines() if line.startswith("|")]


def numbers(s):
    return re.findall(r"(?<![\w.])[-+]?\d+(?:\.\d+)?", norm(s))


def matched_row(rows, position, value):
    matching = [r for r in rows if len(r)>position and r[position] == value]
    require(len(matching) == 1, "did not locate exactly one row: "+value)
    return matching[0]


def publication():
    paper = (HERE/"manuscript.md").read_text(encoding="utf8")
    supp = (HERE/"evidence.md").read_text(encoding="utf8")
    public = BeautifulSoup((HERE/"manuscript.html").read_bytes(), "html.parser")
    manuscript_rows = table(paper)
    trial = table(source(PREFIX+"t4b-holdout-confirmation-v2/README.md").decode())
    for hyp in ("H2","H1","H3"):
        new = next(r for r in manuscript_rows if r[0].startswith(hyp+"　"))
        old = matched_row(trial,0,hyp)
        require(new[1] == old[2] and numbers(new[2]+" "+new[3]) == numbers(old[3]+" "+old[4]) and "MET" in new[4],
                "confirmation contrast or interval: "+hyp)
    abstract = paper.split("## 摘要",1)[1].split("## 1",1)[0]
    require(abstract.index("−55.83") < abstract.index("−343.90") and
            "H1、H2、H3 顺序" in paper, "mechanism leads; registered ordering preserved")
    for i, label in enumerate(("0 秒", "600 秒", "1200 秒"),1):
        old = matched_row(trial,0,label)
        mean = matched_row(manuscript_rows,0,"允许初检减禁购版的平均 L 差（秒）")[i]
        interval = matched_row(manuscript_rows,0,"双侧 95% 区间（秒）")[i]
        require([Decimal(x) for x in numbers(old[3])] ==
                [Decimal(x) for x in numbers(mean+" "+interval)] and old[1]=="48","maintenance stratum "+label)
    narrative = source(PREFIX+"t4c-action-cost-v3/README.md").decode()
    require(all(s in narrative for s in ("72/72","3-03","3-02","L=600","371.25","326.25")) and
            all(s in paper for s in ("72/72","3-03","3-02","从禁购版的 326.25 秒升到 371.25 秒","维护旁路与许可间隔","扩大损失")),
            "engineering boundary and opposed readout witnesses")
    print("PASS three registered H comparisons, H2-first narrative, duration strata and both development witnesses")

    t7 = source(PREFIX+"t7-closeout/manuscript.md").decode()
    for hyp in ("HA","HB","HC"):
        old = matched_row(table(t7),0,hyp)
        new = next(r for r in manuscript_rows if r[0].startswith(hyp+"　"))
        require(numbers(old[2]) == numbers(new[2]) and numbers(old[3]) == numbers(new[3]) and
                ("INDETERMINATE" if hyp == "HC" else "MET") in new[3],"incident estimate "+hyp)
    fit = table(source(FIT+"tables.md").decode())
    winner = matched_row(fit,0,"ORDER_FAR=3")
    require(Decimal(winner[4].split(" / ")[1]) == Decimal("18.958333"), "FIT pooled staff")
    for name, endpoint in (("伦敦","Q3-L"),("荷兰","Q3-N")):
        frozen = next(r for r in fit if r[0] == endpoint and r[2]=="person")
        new = next(r for r in manuscript_rows if r[0] == name and len(r)==4)
        require(Decimal(numbers(new[1])[0]) == Decimal(frozen[4]) and
                [Decimal(x) for x in numbers(new[2])] == [Decimal(x) for x in numbers(frozen[3])] and
                Decimal(numbers(new[3])[0]) == Decimal(frozen[7]).quantize(Decimal(".001")),
                "FIT observed family vs conditional DEV bound: "+name)
    require(all(s in paper for s in ("五个十二行块", "16 行", "Holm", "90 行", "45 行", "30 行",
                                      "荷兰 FIT 实测增加 36.458333","26.25 人秒","硬约束违例记录为 0",
                                      "情景预测","未评分","等价","有异议、未独立证实")), "scientific scope")
    print("PASS T7 endpoints and denominators, FIT pooled and family costs, conditional DEV and qualification boundaries")

    freeze=json.loads(source(PREFIX+"t4c-action-cost-v3/v-double-star-freeze.json",FREEZE))
    require(freeze["scientific_source"]==EXEC and freeze["public_bundle_sha256"] in supp,
            "scientific source and frozen policy bundle")
    names = ["src/aegis_action_cost/"+v for v in ("worker.py","planning.py","rules.json","permit.py")]
    names += ["src/aegis_risk_dispatch/"+v for v in ("knowledge.py","belief.py","policy.py","settings.json")]
    for n in names:
        require(hashlib.sha256(source(n,EXEC)).hexdigest()==freeze["sources"][n],"execution file "+n)
    for term in ("λ = 1","κ = 30","1/32","0.95","0.25 秒","60 秒","180 秒","0.50"):
        require(term in paper, "missing parameter "+term)
    require(public.select_one("blockquote ol") and len(public.select("blockquote li"))==6,"implemented algorithm box")
    anchors=set(re.findall(r'<a id="([^"]+)"></a>',supp))
    require(set(re.findall(r'evidence\.md#([\w-]+)',paper))<=anchors,"supplement anchors")
    refs=re.findall(r'https://github\.com/DonsonHH/AegisDC/blob/([0-9a-f]{40})/([^#)]+)#L(\d+)(?:-L(\d+))?',supp)
    for rev, name, first, last in refs:
        content=source(unquote(name),rev).decode().splitlines()
        require(1<=int(first)<=int(last or first)<=len(content),"source line range: "+name)
    works=set(re.findall(r'^\[(\d+)\] ',paper.split("## 参考文献",1)[1],re.M))
    cited=set()
    for group in re.findall(r'\[([1-9][0-9, ]*)\]',paper.split("## 参考文献",1)[0]):
        cited.update(v.strip() for v in group.split(","))
    require(works==cited==set("123456789") and len(public.select(".references p"))==9,
            "cited primary sources and published bibliography")
    print(f"PASS eight frozen method files, six algorithm steps, nine bibliography entries and {len(refs)} pinned source links")
    return paper,public


def illustrations(paper, html):
    entries=re.findall(r'!\[([^]]+)\]\((figures/[^)]+\.svg)\)',paper)
    require(len(entries)==3 and len(html.select("figure img"))==3,"three figures in both editable and screen editions")
    for (alt,relative), tag in zip(entries,html.select("figure img"),strict=True):
        data=(HERE/relative).read_bytes()
        root=ET.fromstring(data)
        require(len(root.findall(".//{http://www.w3.org/2000/svg}image"))==0 and
                base64.b64decode(tag["src"].split(",",1)[1])==data and tag["alt"]==alt,"source vector in HTML "+relative)
    pdf=PdfReader(HERE/"manuscript.pdf")
    seen={}
    for page in pdf.pages:
        content=page.get_contents().get_data()
        for ref in page.get("/Annots", []):
            a=ref.get_object().get("/A") or {}
            require(not str(a.get("/URI","")).startswith(("file:","https://layout.invalid/")), "private print target")
        for name,ref in page["/Resources"].get("/XObject",{}).items():
            if not name.startswith("/Aegis") or name.encode()+b" Do" not in content:
                continue
            key=name[len("/Aegis"):]
            require(key in VECTORS and key not in seen,"duplicate form use")
            form=ref.get_object()
            original=next((HERE/"figures").glob(key+"*.pdf"))
            require(hashlib.sha256(original.read_bytes()).hexdigest()==form["/AegisSourceSHA256"]==VECTORS[key],
                    "reviewed vector identity")
            require(form.get_data()==PdfReader(original).pages[0].get_contents().get_data()
                    and form["/Resources"].get("/Font") and form["/Subtype"]=="/Form","original vector content and fonts")
            seen[key]=name
    require(set(seen)==set(VECTORS), "both reviewed forms drawn")
    body="".join(page.extract_text() or "" for page in pdf.pages)
    require(all(s in body for s in ("55.83","343.90","38.152","36.458333","INDETERMINATE","参考文献")),
            "PDF body and estimates")
    print(f"PASS {len(pdf.pages)} PDF pages, three in-text vectors, both original reviewed PDF streams and their fonts")


def checkout():
    parent=HERE.relative_to(ROOT).as_posix()+"/"
    paths=git("ls-tree","-r","--name-only","HEAD","--",parent).decode().splitlines()
    require(len(paths)>9,"published package")
    for path in paths:
        require((ROOT/path).read_bytes()==git("cat-file","blob","HEAD:"+path),"checkout bytes "+path)
    protected=("t4b-holdout-confirmation-v2","t4c-action-cost-v3","t4d-cost-baseline-v1","t7-closeout",
               "t8-rsi-wait-repair","t8-closeout","t9-paper-final")
    require(not git("diff","--name-only",BASE,"HEAD","--",*(PREFIX+n+"/" for n in protected)),
            "accepted source packages were changed")
    print(f"PASS {len(paths)} publication files byte-for-byte and original evidence packages at their accepted versions")


def document_identities(paper, html):
    """Bind section 5 and the two public page counts to the delivered PDF files."""
    title = paper.splitlines()[0].removeprefix("# ")
    heading = "5　" + title.split("，", 1)[1].removesuffix("？") + "（C1）"
    require(paper.splitlines().count("## " + heading) == 1 and
            [h.get_text(strip=True) for h in html.find_all("h2")].count(heading) == 1,
            "section 5 must match the manuscript title")
    readme = (HERE/"README.md").read_text(encoding="utf8")
    for name in ("manuscript", "reference-coverage"):
        path = HERE / (name+".pdf")
        pdf = PdfReader(path)
        pages = len(pdf.pages)
        require(pages == pdf.trailer["/Root"]["/Pages"]["/Count"] and
                len({p.indirect_reference.idnum for p in pdf.pages}) == pages, "physical PDF page tree: "+name)
        compact = "".join("".join(p.extract_text() or "" for p in pdf.pages).split())
        if name == "manuscript":
            require("".join(heading.split()) in compact and f"正文 PDF 共 {pages} 页" in readme,
                    "delivered section heading or README page count")
        else:
            require(pages == 1 and "单独成册，共 1 页" in readme and
                    all(s in compact for s in ("RESS", "Howard", "Fauriat", "Bennaceur", "Deloux", "Pun")),
                    "one-page RESS coverage assessment")
            assessment = (HERE / "reference-coverage.md").read_text(encoding="utf8")
            expected_urls = set(re.findall(r"\[[^\]]+\]\((https://[^)\s]+)\)", assessment))
            screen = BeautifulSoup((HERE / "reference-coverage.html").read_bytes(), "html.parser")
            screen_urls = {a["href"] for a in screen.select("a[href]")}
            pdf_urls = {annotation.get_object().get("/A", {}).get("/URI")
                        for annotation in pdf.pages[0].get("/Annots", [])}
            require(len(expected_urls) == 5 and expected_urls == screen_urls == pdf_urls,
                    "RESS scope and four paper links in editable, screen and print editions")
        data = path.read_bytes()
        print(f"PDF {path.name} | pages={pages} | bytes={len(data)} | sha256={hashlib.sha256(data).hexdigest()}")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check",action="store_true",help="verify the public text and rendered paper (default)")
    parser.add_argument("--checkout-bytes",action="store_true")
    parser.add_argument("--refresh-record",action="store_true",
                        help="write the verification record after all content checks succeed")
    args=parser.parse_args()
    log = StringIO()
    with redirect_stdout(log):
        manuscript, page=publication()
        illustrations(manuscript,page)
        verify_figure_values(HERE/"figures", source, manuscript, page)
        document_identities(manuscript, page)
    record = log.getvalue()
    print(record, end="")
    path = HERE/"verification.txt"
    if args.refresh_record:
        path.write_bytes(record.encode())
    else:
        require(path.read_text(encoding="utf8") == record,
                "verification.txt differs from the PDFs or checks; verify the edition before refreshing")
    if args.checkout_bytes:checkout()
