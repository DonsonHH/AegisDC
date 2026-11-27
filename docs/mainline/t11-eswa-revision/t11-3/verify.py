"""Verify the released manuscript and attachments. No model or study analysis is imported."""
import argparse
import csv
from collections import Counter
import io
import json
import re
import subprocess
import tempfile
import unicodedata
import zipfile
from pathlib import Path

import cv2
import numpy as np
from bs4 import BeautifulSoup, Tag
from lxml import etree
from markdown_it import MarkdownIt
from pypdf import PdfReader

from evidence import (HERE, ROOT, REL, REV, MAIN, PRE, PANEL, PIN, OLD, SOURCES, EQ,
                      blob, compile_article, digest, one_location, require, tsv)
from supplement_tables import archive_index, archive_members, supplement_text

ACCOUNT="10b3f7a08462623c22b87b3ae0dae7abe3c95378"
MD=MarkdownIt("commonmark",{"html":True}).enable("table")
NS={"w":"http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "m":"http://schemas.openxmlformats.org/officeDocument/2006/math",
    "s":"http://www.w3.org/2000/svg","wp":"http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"}

def git(*args):
    return subprocess.check_output(["git",*args],cwd=ROOT)

def plain(s):
    s=unicodedata.normalize("NFKC",s).casefold()
    return "".join(s.translate(str.maketrans({"−":"-","–":"-","‑":"-","’":"'","\xad":""})).split())

def accounts():
    path=REV+"t11-1/"
    receipt=json.loads(blob(ACCOUNT,path+"sacct-135652-135693.json"))
    jobs=list(csv.DictReader(io.StringIO(blob(PANEL,path+"results/jobs.tsv").decode()),delimiter="\t"))
    numbers={"135652","135693"}
    require(len(jobs)==63 and not numbers.intersection(j["job"] for j in jobs),"Registered allocation identity")
    require(receipt["exit_status"]==0 and receipt["project_account_rows"]==[],"Scoped sacct read")
    rows=[x.split("|") for x in receipt["all_visible_rows"]]
    require({x[0] for x in rows if x[1]=="different_account"}==numbers and
            {x[0] for x in rows}==numbers|{s+".batch" for s in numbers},"Both allocations and both steps")
    prior=blob(PANEL,path+"SHA256SUMS.txt").splitlines()
    new=blob(ACCOUNT,path+"SHA256SUMS.txt").splitlines()
    require(len(new)==len(prior)+1 and set(prior)<=set(new),"Historical T11-1 index preserved")
    require(digest(blob(ACCOUNT,path+"SHA256SUMS.txt"))=="42dad67b2a63befa5e9626e311e16c7178731d1295262bc4fd02f3e98c100fd4","Readback index")
    require(digest(blob(PRE,REV+"protocol-freeze.json"))=="8dfc03a7c1df9c254f246e1d40add424a0c04218ffdd345acc2b05ade6dc7284","Effective protocol identity")
    ledger=json.loads((HERE/"activity.json").read_bytes())
    require(all(x==0 for x in ledger["this_revision"].values()),"Manuscript-only activity ledger")
    print("PASS stage zero: both other-account allocations excluded; 63 original jobs; signed-off protocol identity and prior index intact.")

def claims():
    v2=blob(PRE,REV+"claims-v2.md").decode()
    v3=(HERE/"claims-v3.md").read_text(encoding="utf8")
    new=" 相对两种在线基线，本开发面板未显示额外服务优势。[T11-1 解读与成绩，93748f27](https://github.com/DonsonHH/AegisDC/blob/93748f272939166b81ae4188299f096b0fa23fe2/docs/mainline/t11-eswa-revision/t11-1/manuscript-panel-en.md)"
    require(v3.count(new)==1 and new in next(l for l in v3.splitlines() if l.startswith("| C1")),"C1-only insertion")
    require(v2[v2.index("修订改变"):]==v3[v3.index("修订改变"):].replace(new,""),"All original grades, counterexamples, tables and values")
    require((HERE/"claims-v3.md").read_bytes()==blob(PIN,REL+"claims-v3.md"),"Prerewrite claim lock")
    print("PASS claims v3: a single C1 insertion; all previous dispositions, figures and counterexamples preserved.")

def document_blocks(xml):
    return ["".join(node.xpath(".//w:t/text()",namespaces=NS)) for node in
            xml.xpath("//w:body//w:p",namespaces=NS) if node.xpath(".//w:t/text()",namespaces=NS)]

def markdown_blocks(text):
    out=[]
    soup=BeautifulSoup(MD.render(text),"html.parser")
    for node in soup.children:
        if not isinstance(node,Tag) or node.get("data-equation") or node.find("img"):continue
        if node.name=="table":
            out.extend(cell.get_text() for cell in node.select("th,td"))
        elif node.name=="ul":out.extend(li.get_text() for li in node.select("li"))
        else:out.append(node.get_text())
    return out

def read_xml(docx):
    with zipfile.ZipFile(docx) as z:
        return etree.fromstring(z.read("word/document.xml"))

def doc_check(src,docx,pdf=None):
    xml=read_xml(docx)
    blocks=document_blocks(xml)
    expected=markdown_blocks(src)
    require([plain(x) for x in blocks]==[plain(x) for x in expected],"Editable text or table differs: "+docx.stem)
    if pdf:
        reader=PdfReader(pdf)
        excerpt="".join(re.sub(r"^\s*"+str(i)+r"\s*","",page.extract_text()) for i,page in enumerate(reader.pages,1))
        normalized=plain(excerpt)
        for b in blocks:require(plain(b) in normalized,"Printed text/cell differs in "+pdf.stem+": "+b[:60])
        info=subprocess.check_output(["pdfinfo",str(pdf)],text=True,encoding="utf8",errors="replace")
        poppler=int(re.search(r"(?m)^Pages:\s+(\d+)",info)[1])
        require(poppler==len(reader.pages),"Independent physical page counts")
        return xml,reader
    return xml,None

def policy_scope(text):
    abstract=text.split("## Abstract",1)[1].split("**Keywords**",1)[0]
    conclusion=text.split("### Conclusions",1)[1].split("### Data and code",1)[0]
    section=text.split("## 6. Alternative",1)[1].split("## 7.",1)[0]
    required=["post hoc, nonconfirmatory","identical on all 72 conditions","3 conditions with different issued request",
              "−57.50 [−118.06, +9.36]","−72.78 [−93.96, −52.71]","−1.35 [−1.69, −1.00]",
              "207 named work orders","36 for the centre and 52 for POMCP","903","3,156","4,392","128 simulations",
              "depth 4","−200.96 [−296.92, −103.75]","−150.00 [−282.50, −32.50]","post hoc marginal intervals",
              "+58.81 [+6.67, +124.69]","−42.22 [−57.85, −27.78]","only service interval among the eight",
              "no additional service advantage","original worker's internal CPU clock was unavailable"]
    for st in required:require(plain(st) in plain(section),"Missing PI boundary: "+st)
    require(all(x not in abstract+conclusion for x in ("200.96","150.00","58.81","42.22","1,200","λ")),"Exploratory subgroup promotion")
    for line in text.splitlines():
        if line.startswith(("**Table E.","*Figure A.")):
            require("135631" in line and "replay" in line and "CPU" in line and "unavailable" in line and "IPC" in line,"Timing source in caption")
    require(text.count("shared account")==1 and "signature" not in abstract+conclusion and "disputed" not in text,"Main-article custody scope")
    supplements=(HERE/"supplement-B.md").read_text(encoding="utf8")
    for st in ("55d37ee8","nine of ten","2.0","integer 2","3a096231","one line","All ten","Both attempt receipts"):
        require(st in supplements,"Qualification history: "+st)
    require("disputed and has not been independently verified" in (HERE/"supplement-C.md").read_text(encoding="utf8"),"Signature attribution")
    return section

def feedback_height(reader):
    positions={}
    for i,page in enumerate(reader.pages,1):
        def visit(t,cm,tm,font,size):
            for key,prefix in (("top","8. Boundaries of feedback"),("bottom","Conclusions")):
                if t.strip().startswith(prefix) and key not in positions:
                    positions[key]=(i,tm[4]*cm[1]+tm[5]*cm[3]+cm[5],size)
        page.extract_text(visitor_text=visit)
    top,bottom=positions["top"],positions["bottom"]
    require(top[0]==bottom[0],"Feedback text crossed a physical page")
    height=float(reader.pages[top[0]-1].mediabox.height)
    # Include the heading's full font height and all space down to the next
    # heading baseline. This overcounts the actual section by a small margin.
    span=top[1]+top[2]-bottom[1]
    require(0<span<=.75*height,"Physical feedback limit")
    return top[0],span,height

def figure_check(xml,reader):
    path=HERE/"figures"/"decision-latency.svg"
    original=path.read_bytes()
    with zipfile.ZipFile(HERE/"manuscript.docx") as z:
        require(z.read("word/media/decision-latency.svg")==original,"Embedded and standalone chart differ")
    root=etree.fromstring(original)
    scale=json.loads(blob(*SOURCES["G"]))
    def group(id):return root.xpath(f".//s:g[@id='{id}']",namespaces=NS)[0]
    axis=[]
    for i,tick in enumerate(scale["major_ticks"],1):
        node=group("xtick_"+str(i))
        label=next(c.text.strip() for c in node.xpath(".//comment()") if c.text.strip().isdigit())
        require(str(tick)==label,"Axis value")
        axis.append(float(node.find(".//s:use",NS).get("x")))
    dx=(axis[-1]-axis[0])/(scale["major_ticks"][-1]-scale["major_ticks"][0])
    w=float(root.get("viewBox").split()[2])
    panelpage=next(i for i,p in enumerate(reader.pages,1) if "figurea." in plain(p.extract_text()))
    svg_marks=[]
    for i,line in enumerate(scale["source_lines"]):
        row=[]
        for j,col in enumerate(scale["source_columns"]):
            mark=group(f"timing-{i}-{j}").find(".//s:use",NS)
            x=float(mark.get("x"))
            value=float(one_location("P",line,col))
            require(abs(x-axis[0]-dx*value)<.00001,"Source cell vs SVG marker")
            row.append(x)
        svg_marks.append(row)
    with tempfile.TemporaryDirectory() as tmp:
        base=Path(tmp)/"chart"
        subprocess.run(["pdftoppm","-f",str(panelpage),"-l",str(panelpage),"-r","95","-singlefile","-png",str(HERE/"manuscript.pdf"),str(base)],check=True)
        im=cv2.imread(str(base.with_suffix(".png")))
    pagewidth=float(reader.pages[panelpage-1].mediabox.width)
    artwidth=float(xml.xpath("//wp:extent",namespaces=NS)[0].get("cx"))/12700
    for j,colour in enumerate(("173d52","25756c","9a4d22")):
        b=np.array(list(bytes.fromhex(colour))[::-1],dtype=int)
        mask=cv2.inRange(im,np.maximum(b-23,0).astype("uint8"),np.minimum(b+23,255).astype("uint8"))
        n,_,stats,centers=cv2.connectedComponentsWithStats(mask)
        points=sorted((centers[k][1],centers[k][0]) for k in range(1,n) if
                      9<=stats[k,4]<=320 and 3<=stats[k,2]<=20 and 3<=stats[k,3]<=20)
        require(len(points)==4,"Missing PDF chart marker or legend")
        for i,(_,actual_x) in enumerate(points[1:]):
            expected=((pagewidth-artwidth)/2+svg_marks[i][j]/w*artwidth)*95/72
            require(abs(actual_x-expected)<=2.6,"Printed chart displaced a timing mark")
    return panelpage

def supplements():
    expected=supplement_text()
    require((HERE/"supplement-B.md").read_bytes()==expected.encode(),"Supplementary displayed tables")
    index=archive_index()
    require((HERE/"supplement-B-index.tsv").read_bytes()==tsv(index).encode(),"Archive catalogue")
    with zipfile.ZipFile(HERE/"supplement-B-tables.zip") as z:
        require(len(z.namelist())==len(index) and set(z.namelist())==set(archive_members()),"Archive complete")
        for row in index:
            require(z.read(row["archive_member"])==blob(row["source_commit"],row["source_path"]),"Table or retained attempt byte discrepancy")
    pages=[]
    for key in "ABC":
        base=HERE/f"supplement-{key}"
        _,pdf=doc_check(base.with_suffix(".md").read_text(encoding="utf8"),base.with_suffix(".docx"),base.with_suffix(".pdf"))
        pages.append(len(pdf.pages))
    sub=HERE/"submission"
    for src in sorted(sub.glob("*.md")):doc_check(src.read_text(encoding="utf8"),src.with_suffix(".docx"))
    highlights=(sub/"highlights.txt").read_text(encoding="utf8").splitlines()
    require(3<=len(highlights)<=5 and all(0<len(x)<=85 for x in highlights),"Highlight count or length")
    doc_check("# Highlights\n\n"+"\n".join("- "+x for x in highlights),sub/"highlights.docx")
    stress=(sub/"stress-checklist.md").read_text(encoding="utf8")
    items=re.findall(r"(?m)^\| (\d+\.\d+) \|",stress)
    original=blob(OLD,MAIN+"t10-submission-en/submission/stress-checklist.md").decode()
    require(len(items)==20 and items==re.findall(r"(?m)^\| (\d+\.\d+) \|",original),"STRESS item coverage")
    print(f"PASS supplements A/B/C: {pages} pages; {len(index)} archive members matched source blobs; 20 STRESS items; highlight lengths {[len(x) for x in highlights]}.")

def integrity(checkout,write):
    actual={p.relative_to(HERE).as_posix() for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.name!="SHA256SUMS"}
    lines="".join(f"{digest((HERE/name).read_bytes())}  {name}\n" for name in sorted(actual))
    man=HERE/"SHA256SUMS"
    if write:man.write_bytes(lines.encode())
    require(man.read_bytes()==lines.encode(),"Package hash index or file set differs")
    if checkout:
        known={s[len(REL):] for s in git("ls-tree","-r","--name-only","HEAD","--",REL).decode().splitlines()}
        require(known==actual|{"SHA256SUMS"},"Unindexed or absent Git file")
        for name in known:require((HERE/name).read_bytes()==blob("HEAD",REL+name),"Checkout bytes differ: "+name)
        changes=git("diff","--name-only",PANEL,"HEAD","--").decode().splitlines()
        permitted={REV+"t11-1/SHA256SUMS.txt",REV+"t11-1/sacct-135652-135693.json"}
        require({s for s in changes if not s.startswith(REL)}==permitted,"Earlier package change")
        for path in permitted:require(blob("HEAD",path)==blob(ACCOUNT,path),"Phase-zero receipt drift")
        print(f"PASS checkout: {len(known)} publication files match Git HEAD byte for byte; preceding packages differ only by the two phase-zero accounting files.")
    print("SHA256SUMS",digest(man.read_bytes()))

def main(checkout,write):
    accounts()
    claims()
    text,trace=compile_article()
    require((HERE/"manuscript.md").read_bytes()==text.encode() and (HERE/"numeric-trace.tsv").read_bytes()==tsv(trace).encode(),"Occurrence trace or article text")
    xml,reader=doc_check(text,HERE/"manuscript.docx",HERE/"manuscript.pdf")
    equations=xml.xpath("//m:oMath",namespaces=NS)
    require(len(equations)==len(EQ) and len(xml.xpath("//w:tbl",namespaces=NS))==6,"Native equations or tables")
    for eq,symbols in zip(equations,("LU","Ptime","bRAIS","Jλκ","Qμσ"),strict=True):
        raw="".join(eq.xpath(".//m:t/text()",namespaces=NS))
        require(all(c in raw for c in symbols),"Equation lost a required term "+raw)
    policy_scope(text)
    p,span,h=feedback_height(reader)
    fig=figure_check(xml,reader)
    print(f"PASS article: {len(reader.pages)} PDF pages; {len(trace)} trace rows; 50 registered DOI works plus 5 supporting sources; 6 native tables and {len(equations)} editable equations.")
    print(f"PASS PI wording checks: both online comparisons, descriptive strata, labour-price trade-off and original timing source; feedback section p.{p}, conservative span {span:.2f}/{h:.2f} pt = {span/h:.3f} page.")
    print(f"PASS Word/PDF text and tables; all nine source-linked timing marks verified in SVG, embedded Word artwork and rendered PDF p.{fig}.")
    supplements()
    integrity(checkout,write)

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check",action="store_true")
    mode.add_argument("--write-manifest",action="store_true")
    parser.add_argument("--checkout-bytes",action="store_true")
    args=parser.parse_args()
    main(args.checkout_bytes,args.write_manifest)
