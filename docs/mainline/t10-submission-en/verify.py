"""Verify the ESWA submission package using published materials and document readers."""
import argparse
from collections import Counter
import csv
import hashlib
from pathlib import Path
import re
import subprocess
import tempfile
import unicodedata
from zipfile import ZipFile

from bs4 import BeautifulSoup, Tag
import cv2
from lxml import etree as ET
from pypdf import PdfReader
from figures import FACILITY, PLOTS, REV
from numeric_audit import audit, equal, frozen, LINK, outline, lines
from publication import HERE, SUB, MD, NAMED, review_body, works

LOCK="fec03bd390b1bd294afc98975a1afbc9ab7b3566"
REL="docs/mainline/t10-submission-en/"
NS={"w":"http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a":"http://schemas.openxmlformats.org/drawingml/2006/main",
    "wp":"http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"}
ATTACHMENTS=("ai-declaration","competing-interests","cover-letter","credit-statement",
             "data-and-code-availability","highlights","stress-checklist","title-page")

def require(value,why):
    if not value: raise ValueError(why)

def git(*args):
    return subprocess.check_output(["git",*args],cwd=HERE.parents[2])

def packed(s):
    return "".join(unicodedata.normalize("NFKC",s).replace("\u00ad","").split())

def block_text(soup):
    out=[]
    for tag in soup.children:
        if not isinstance(tag,Tag):continue
        if tag.name=="blockquote":
            out.append(tag.find("p").get_text())
            out.extend(f"{i}. "+v.get_text() for i,v in enumerate(tag.select("li"),1))
        elif tag.name=="table":out.extend(c.get_text() for c in tag.select("th,td"))
        elif not tag.find("img"):out.append(tag.get_text())
    return "\n".join(out)

def word_text(archive):
    root=ET.fromstring(archive.read("word/document.xml"))
    ps=["".join(p.xpath(".//w:t/text()",namespaces=NS)) for p in root.xpath("//w:body//w:p",namespaces=NS)]
    return root,"\n".join(ps)

def lock():
    equal(git("rev-parse",LOCK+"^").decode().strip(),REV,"claim-lock parent")
    equal(git("ls-tree","-r","--name-only",LOCK,"--",":(top)"+REL).decode().splitlines(),
          [REL+"claims-en.md"],"only the claims existed at the lock")
    equal(git("cat-file","blob",LOCK+":"+REL+"claims-en.md"),(HERE/"claims-en.md").read_bytes(),"claims lock")
    zh=frozen("docs/mainline/t9-submission-r1/manuscript.md").decode()
    en=(HERE/"manuscript.md").read_text(encoding="utf8")
    equal([outline(line) for _,line in lines(zh)],[outline(line) for _,line in lines(en)],"source structure")
    return en

def check_references(en):
    zh=frozen("docs/mainline/t9-submission-r1/manuscript.md").decode()
    rb="\n## References\n"
    body,refs=en.split(rb,1)
    equal(refs,zh.split("\n## 参考文献\n",1)[1].replace("[官方复盘]","[Official report]"),"all original bibliography records")
    cited=[int(c) for c in re.findall(r"\[(\d+)\]",body)]
    equal(list(dict.fromkeys(cited)),list(range(1,13)),"numbered citation order")
    refs_by_number=works()
    equal(set(refs_by_number),set(cited),"citation crosswalk")
    equal(len({row["url"] for row in refs_by_number.values()}),12,"unique reference links")
    return refs_by_number

def claim_boundaries(en):
    discussion=en.split("## 9　Discussion and conclusions",1)[1].split("### Limitations",1)[0]
    for statement in ("C1 was partially supported for the preregistered panel mean",
                      "C2 has confirmatory support for severity differences in two synthetic families",
                      "The synthetic event-rate test was indeterminate and field event rates remain unidentified",
                      "The specific C3 transfer claim was not supported",
                      "An independent C4 increment was not established"):
        require(statement in discussion,"frozen scientific interpretation: "+statement)
    for statement in ("The separate qualification panel (DEV) was not scored",
                      "The last column is a scenario projection",
                      "a shared account for procedural overlap checking",
                      "is disputed and has not been independently verified",
                      "can RSI find low-cost edits"):
        require(statement in en,"material scope: "+statement)

def check_doc(en,refs):
    raw_body=en.split("\n## References\n",1)[0]
    presentation=review_body()
    with ZipFile(HERE/"manuscript.docx") as archive:
        root,word=word_text(archive)
        equal(packed(word),packed(block_text(presentation)),"complete editable article text")
        equal(len(root.xpath("//w:tbl",namespaces=NS)),5,"native tables")
        equal(len(root.xpath("//wp:inline",namespaces=NS)),3,"inline figures")
        sizes=[int(el.get("cx"))/914400 for el in root.xpath("//wp:inline/wp:extent",namespaces=NS)]
        for stem in (FACILITY,*PLOTS):
            equal(archive.read("word/media/"+stem+".svg"),(HERE/"figures"/(stem+".svg")).read_bytes(),"embedded "+stem)
        private=(b"donsonhh",b"\\\\users\\\\",b"file://",b"private-archive")
        for name in archive.namelist():
            if name.endswith((".xml",".rels")):
                require(not any(s in archive.read(name).lower() for s in private),"identifying review metadata "+name)
    # Independently reverse the journal's citation presentation before comparing all prose.
    stripped=word.split("Declaration of generative AI and AI-assisted technologies in the writing process",1)[0]
    for n,ref in refs.items():
        if n in NAMED:
            key=NAMED[n]+" ("+ref["year_key"]+")"
            equal(stripped.count(key),1,"narrative reference "+str(n))
            stripped=stripped.replace(key,NAMED[n],1)
        else:
            key=" ("+ref["author_label"]+", "+ref["year_key"]+")"
            equal(stripped.count(key),1,"parenthetical reference "+str(n))
            stripped=stripped.replace(key,"",1)
    expected=block_text(BeautifulSoup(MD.render(re.sub(r" \[\d+\]","",raw_body)),"html.parser"))
    equal(packed(stripped),packed(expected),"underlying English text through the author–date conversion")
    pdf=PdfReader(HERE/"manuscript.pdf")
    page_count=len(pdf.pages)
    info=subprocess.check_output(["pdfinfo",str(HERE/"manuscript.pdf")])
    equal(int(re.search(rb"^Pages:\s*(\d+)",info,re.M)[1]),page_count,"Poppler physical pages")
    equal(pdf.trailer["/Root"]["/Pages"]["/Count"],page_count,"PDF page tree")
    readback=[];uris=set()
    for n,p in enumerate(pdf.pages,1):
        text=p.extract_text()
        require(re.match(r"^\s*"+str(n)+r"\s+",text),"physical page footer "+str(n))
        readback.append(re.sub(r"^\s*"+str(n)+r"\s+","",text,count=1))
        uris.update(a.get_object().get("/A",{}).get("/URI") for a in p.get("/Annots",[]))
    equal(packed("".join(readback)),packed(word),"entire printed article, including every formatted number")
    equal(uris,{r["url"] for r in refs.values()},"printed reference destinations")
    return page_count,sizes

def visual_pages(sizes):
    with tempfile.TemporaryDirectory(prefix="aegis-printed-") as tmp:
        t=Path(tmp);dpi=88
        subprocess.run(["pdftoppm","-r",str(dpi),"-png",str(HERE/"manuscript.pdf"),str(t/"page")],check=True)
        pages=[cv2.imread(str(f),cv2.IMREAD_GRAYSCALE) for f in sorted(t.glob("page-*.png"),key=lambda f:int(f.stem.split("-")[-1]))]
        found=[]
        for stem,width in zip((FACILITY,*PLOTS),sizes,strict=True):
            name=HERE/"figures"/(stem+".pdf")
            fig=PdfReader(name)
            equal(len(fig.pages),1,"individual figure page")
            tlabel=fig.pages[0].extract_text()
            require(tlabel.strip() and not re.search(r"[\u3400-\u9fff]",tlabel),"English labels "+stem)
            # Check all source annotation numbers in the selectable English figure PDF.
            svg=ET.fromstring((HERE/"figures"/(stem+".svg")).read_bytes())
            labels=[node.text or "" for node in svg.xpath("//*[local-name()='text']")]
            require(packed("".join(labels))==packed(tlabel),"complete figure PDF label readback "+stem)
            subprocess.run(["pdftoppm","-scale-to-x",str(round(width*dpi*2)),"-scale-to-y","-1","-singlefile",
                            "-png",str(name),str(t/"fig")],check=True)
            template=cv2.imread(str(t/"fig.png"),cv2.IMREAD_GRAYSCALE)
            scores=[0.0]*len(pages)
            for offset in (-1,0,1):
                w=round(width*dpi)+offset
                ref=cv2.resize(template,(w,round(w*template.shape[0]/template.shape[1])),interpolation=cv2.INTER_AREA)
                for k,page in enumerate(pages):
                    score=cv2.minMaxLoc(cv2.matchTemplate(page,ref,cv2.TM_CCOEFF_NORMED))[1]
                    scores[k]=max(scores[k],score)
            best=sorted(scores,reverse=True)
            require(best[0]>.75 and best[0]-best[1]>.15,"distinct visible figure on article page: "+stem)
            found.append(scores.index(best[0])+1)
        equal(len(set(found)),3,"three distinct figure pages")
        return found

def attachments(en):
    abstract=en.split("## Abstract\n",1)[1].split("**Keywords**",1)[0]
    words=len(re.findall(r"\b\w+(?:[.‘’'-]\w+)*\b",abstract))
    keywords=en.split("**Keywords**",1)[1].splitlines()[0].strip().split(",")
    hs=(SUB/"highlights.txt").read_text(encoding="utf8").splitlines()
    require(words<=250 and 1<=len(keywords)<=6 and 3<=len(hs)<=5 and max(map(len,hs))<=85,"abstract, keywords and highlights")
    for stem in ATTACHMENTS:
        ext=".md" if stem=="stress-checklist" else ".txt"
        content=(SUB/(stem+ext)).read_text(encoding="utf8")
        with ZipFile(SUB/(stem+".docx")) as z:_,actual=word_text(z)
        if ext==".md":expected=block_text(BeautifulSoup(MD.render(content),"html.parser"))
        else:expected=("Highlights\n" if stem=="highlights" else "")+content
        equal(packed(actual),packed(expected),"attachment source/Word: "+stem)
    data=(SUB/"data-and-code-availability.txt").read_text(encoding="utf8")
    require(data.split("\n\n")[1] in en and REV in data and "https://github.com/DonsonHH/AegisDC" in data,
            "availability matches the manuscript and gives the editor a versioned public locator")
    stress=(SUB/"stress-checklist.md").read_text(encoding="utf8")
    items=re.findall(r"^\| (\d\.\d) \|",stress,re.M)
    equal(items,[f"{i}.{j}" for i,k in enumerate((3,5,4,3,4,1),1) for j in range(1,k+1)],"STRESS items")
    require(all(w in stress for w in ("Entities","Activities","Resources","Queues","Entry and exit","Partial")),"components and limits")
    require("Expert Systems with Applications" in (SUB/"cover-letter.txt").read_text(encoding="utf8"),"cover letter target")
    return words,len(keywords),list(map(len,hs))

def deliverables():
    base={".gitattributes","README.md","claims-en.md","manuscript.md","manuscript.docx","manuscript.pdf",
          "figures.py","publication.py","build.py","verify.py","numeric_audit.py","reference-crosswalk.tsv",
          "quantity-phrases.tsv","numeric-ledger.tsv","verification.md","SHA256SUMS.txt"}
    base.update("figures/"+name+ext for name in (FACILITY,*PLOTS) for ext in (".svg",".pdf"))
    for stem in ATTACHMENTS:
        base.add("submission/"+stem+(".md" if stem=="stress-checklist" else ".txt"))
        base.add("submission/"+stem+".docx")
    return base

def formatted_report(inventory,words,keywords,highlights,npages,where):
    summary=Counter(row[0] for row in inventory.rows)
    entries="\n".join(f"| {key} | {count} | 0 |" for key,count in sorted(summary.items()))
    return f"""# English submission verification

Chinese scientific source: ¦{REV}¦. English claims were fixed in ¦{LOCK}¦ before the manuscript existed. Target journal: *Expert Systems with Applications*.

**Numeric discrepancies: 0.** The inventory contains {len(inventory.rows)} matched occurrences, including labels, identifiers and repeated values. Each row names the Chinese source file and commit, a paragraph/cell/figure location, the English occurrence, both expressions and the matched value. These counts describe documents, not study units. [Per-occurrence ledger](numeric-ledger.tsv)

| Occurrence class | Matched | Differences |
|---|---:|---:|
{entries}

The audit compares digit-bearing tokens in order within each corresponding paragraph or table cell, preserving signs, decimal precision, denominators and condition IDs. Written quantities are paired by local phrases, including counts, ordinals, “zero” and one- or two-sided intervals. Lexical uses such as “next”, “same” and measurement-unit names are distinguished from counts. Figure annotations, plotted geometry and metadata are checked against the accepted vectors. Cover and claim values point back to the same manuscript. STRESS item codes, section locators, document pagination and reference metadata are editorial identities.

The numbered source has 12 in-text identities and 12 retained bibliography records. The author–date conversion resolves the same 12 works, disambiguates the two corporate reports and preserves their destinations. After reversing that presentation, the entire review body matches the numbered English source. The editable file and PDF match in all printed text after normalizing whitespace and font composition and removing only the verified page footers. All 12 external links in the review PDF are bibliography links.

The abstract has {words} words under the published tokenizer, with {keywords} keywords. The {len(highlights)} highlights have {', '.join(map(str,highlights))} characters including spaces and punctuation. The Word article contains five editable tables and the three approved drawings with English type. The PDF has {npages} physical pages by both Poppler and pypdf. Independent raster matching located the drawings on pages {', '.join(map(str,where))} in figure order.

All eight attachment sources match their editable Word versions. The STRESS crosswalk covers all 20 top-level items, including the five component categories and explicitly partial items. No facility, scorer, scheduler, private study archive or sealed H2/H3 material is used by these checks.
""".replace("¦",chr(96))

def write_or_check(path,data,refresh):
    if refresh:path.write_bytes(data)
    else:equal(path.read_bytes(),data,path.name+" differs from verification")

def main(refresh=False,checkout=False):
    en=lock()
    claim_boundaries(en)
    refs=check_references(en)
    inv=audit()
    pg,sizes=check_doc(en,refs)
    where=visual_pages(sizes)
    words,keys,highlights=attachments(en)
    write_or_check(HERE/"numeric-ledger.tsv",inv.tsv().encode(),refresh)
    report=formatted_report(inv,words,keys,highlights,pg,where)
    write_or_check(HERE/"verification.md",report.encode(),refresh)
    declared=deliverables()
    sums="".join(hashlib.sha256((HERE/path).read_bytes()).hexdigest()+"  "+path+"\n" for path in sorted(declared-{"SHA256SUMS.txt"}))
    write_or_check(HERE/"SHA256SUMS.txt",sums.encode(),refresh)
    if checkout:
        files=set(git("ls-tree","-r","--name-only","HEAD","--",":(top)"+REL).decode().splitlines())
        equal(files,{REL+p for p in declared},"committed delivery set")
        for p in declared:equal((HERE/p).read_bytes(),git("cat-file","blob","HEAD:"+REL+p),"checkout "+p)
        equal(git("diff","--name-only",REV,"HEAD","--",":(top,exclude)"+REL+"**"),b"","previously delivered files")
        print(f"PASS {len(declared)} files byte-for-byte against Git HEAD. Accepted packages unchanged.")
    print(f"PASS numeric differences=0 | occurrences={len(inv.rows)} | citations=12 | abstract={words} | keywords={keys}")
    print(f"PASS PDF pages={pg} | visible figures={where} | editable tables=5 | attachments=8 | STRESS=20")
    print("SHA-256 index:",hashlib.sha256((HERE/"SHA256SUMS.txt").read_bytes()).hexdigest())

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group()
    group.add_argument("--check",action="store_true",help="read-only verification (default)")
    group.add_argument("--write-records",action="store_true",help="refresh the ledger, verification report and digest index")
    parser.add_argument("--checkout-bytes",action="store_true")
    args=parser.parse_args()
    main(args.write_records,args.checkout_bytes)
