"""Prepare editable journal files and print proofs using public, frozen values."""
import argparse
from contextlib import contextmanager
import importlib.util
import re
from pathlib import Path
import sys
import tempfile
from bs4 import BeautifulSoup, Tag
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.packuri import PackURI
from docx.opc.part import Part
from docx.shared import Mm, Pt
from lxml import etree
from markdown_it import MarkdownIt

from evidence import HERE, MAIN, OLD, ROOT, blob, compile_article, one_location, tsv
from equations import office_math
from supplement_tables import supplement_text, write_archive

FIG=HERE/"figures"
SUB=HERE/"submission"
MD=MarkdownIt("commonmark",{"html":True}).enable("table")
OLD_DIR=ROOT/MAIN/"t10-submission-en"
# The previous edition owns its Word styling. Load its build helpers by a
# separate module name, and leave its original documents and directories alone.
def load_old_helpers():
    sys.path.insert(0,str(OLD_DIR))
    try:
        old_spec=importlib.util.spec_from_file_location("accepted_word_format", OLD_DIR/"build.py")
        old=importlib.util.module_from_spec(old_spec)
        old_spec.loader.exec_module(old)
        return old
    finally:
        sys.path.pop(0)

def make_figure(temp):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":9,"svg.fonttype":"path",
                         "svg.hashsalt":"aegis-eswa-timing","pdf.fonttype":42})
    FIG.mkdir(exist_ok=True)
    fig,ax=plt.subplots(figsize=(6.3,2.32))
    fig.subplots_adjust(left=.235,right=.965,top=.75,bottom=.25)
    colours=["#173d52","#25756c","#9a4d22"]
    markers=["o","s","D"]
    labels=["Median","95th percentile","Maximum"]
    for idx,label in enumerate(("Centre (replay)","Myopic (online)","POMCP (online)")):
        vals=[float(one_location("P",131+idx,k)) for k in (4,5,6)]
        y=2-idx
        ax.plot([0,vals[-1]],[y,y],lw=1.3,color="#9caeb5",zorder=1)
        for j,v in enumerate(vals):
            line,=ax.plot(v,y,linestyle="none",marker=markers[j],markersize=5.5,color=colours[j],
                          label=labels[j] if idx==0 else "_nolegend_",zorder=2)
            line.set_gid(f"timing-{idx}-{j}")
    ax.set_yticks([2,1,0],["Centre (replay)","Myopic (online)","POMCP (online)"])
    ax.set_ylim(-.55,2.5)
    ax.set_xlim(0,55)
    ax.set_xticks(range(0,51,10))
    ax.set_xlabel("Outer IPC wall time (ms)",labelpad=5)
    ax.spines[["right","top","left"]].set_visible(False)
    ax.tick_params(axis="y",length=0)
    ax.grid(axis="x",color="#e3e8e9",lw=.6)
    ax.legend(loc="lower right",bbox_to_anchor=(1,1.06),ncol=3,frameon=False,
              handlelength=.8,handletextpad=.8,columnspacing=2.75,fontsize=8)
    fig.savefig(FIG/"decision-latency.svg",metadata={"Date":None})
    fig.savefig(FIG/"decision-latency.pdf",metadata={"CreationDate":None,"ModDate":None})
    fig.savefig(temp/"decision-latency.png",dpi=230)
    plt.close(fig)

def insert_art(doc,temp):
    para=doc.add_paragraph()
    para.alignment=WD_ALIGN_PARAGRAPH.CENTER
    para.paragraph_format.keep_with_next=True
    pic=para.add_run().add_picture(str(temp/"decision-latency.png"),width=Mm(155))
    pic._inline.docPr.set("descr","Outer IPC wall time for centre replay and the two online comparators.")
    part=Part(PackURI("/word/media/decision-latency.svg"),"image/svg+xml",(FIG/"decision-latency.svg").read_bytes(),doc.part.package)
    rid=doc.part.relate_to(part,RT.IMAGE)
    blip=pic._inline.xpath(".//a:blip")[0]
    lst=OxmlElement("a:extLst")
    ext=OxmlElement("a:ext")
    ext.set("uri","{96DAC541-7B7A-43D3-8B79-37D633B846F1}")
    svg=etree.SubElement(ext,"{http://schemas.microsoft.com/office/drawing/2016/SVG/main}svgBlip")
    svg.set(qn("r:embed"),rid)
    lst.append(ext)
    blip.append(lst)

WIDTHS={
    "Test and comparator":[47,19,29,40,25],
    "Public maintenance duration (s)":[49,36,75],
    "Comparator":[36,40,44,40],
    "Method and clock source":[48,26,27,33,26],
    "Assumed mixture":[41,44,39,36],
    "Evidence":[31,74,55],
    "Scope":[36,25,28,35,36],
    "Parameter":[37,21,38,37,27],
    "Policy":[42,32,27,31,28],
    "Public file":[40,61,59],
    "Item":[13,28,36,83],
}

def write_table(doc,node,style):
    rows=[r.find_all(["th","td"],recursive=False) for r in node.select("tr")]
    heading=rows[0][0].get_text(strip=True)
    sizes=WIDTHS[heading]
    if heading=="Test and comparator" and len(rows[0])==4:
        sizes=[49,28,51,32]
    table=doc.add_table(rows=0,cols=len(sizes))
    table.autofit=False
    for col,width in zip(table.columns,sizes,strict=True):
        col.width=Mm(width)
    borders=OxmlElement("w:tblBorders")
    for edge in ("top","bottom","insideH"):
        rule=OxmlElement("w:"+edge)
        for key,val in (("val","single"),("sz","4"),("color","A5B2B5")):
            rule.set(qn("w:"+key),val)
        borders.append(rule)
    table._tbl.tblPr.append(borders)
    for idx,cells in enumerate(rows):
        r=table.add_row()
        prop=r._tr.get_or_add_trPr()
        prop.append(OxmlElement("w:cantSplit"))
        if idx==0:prop.append(OxmlElement("w:tblHeader"))
        for cell,tag,width in zip(r.cells,cells,sizes,strict=True):
            cell.width=Mm(width)
            p=cell.paragraphs[0]
            p.style="Article Table"
            p.paragraph_format.space_before=Pt(2)
            p.paragraph_format.keep_with_next=idx==0 or len(rows)<=5 and idx<len(rows)-1
            if idx==0:
                shade=OxmlElement("w:shd")
                shade.set(qn("w:fill"),"EDF2F3")
                cell._tc.get_or_add_tcPr().append(shade)
            for child in tag.children:style.inline(p,child,bold=idx==0)

def write_doc(src,out,temp,style,kind="normal"):
    doc=Document()
    style.configure(doc)
    title=src.splitlines()[0].lstrip("# ")
    doc.core_properties.title=title
    refs=False
    clean=src.replace("\u3000"," ")
    soup=BeautifulSoup(MD.render(clean),"html.parser")
    for tag in soup.children:
        if not isinstance(tag,Tag):continue
        if kind=="supplement":
            for link in tag.select("a[href^='https://github.com/']"):link.unwrap()
        txt=tag.get_text(" ",strip=True)
        if tag.name in ("h1","h2","h3"):
            attr={"h1":"Title","h2":"Heading 1","h3":"Heading 2"}[tag.name]
            p=doc.add_paragraph(txt,attr)
            if txt=="References":
                refs=True
            continue
        if tag.name=="table":
            write_table(doc,tag,style)
            continue
        if tag.name=="ul":
            for node in tag.find_all("li",recursive=False):doc.add_paragraph(node.get_text(),"List Bullet")
            continue
        if tag.name!="p":raise ValueError(tag.name)
        if tag.get("data-equation"):
            p=doc.add_paragraph()
            p.alignment=WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after=Pt(5)
            p._p.append(office_math(tag["data-equation"]))
        elif tag.img:insert_art(doc,temp)
        else:
            caption=bool(re.match(r"^(Table|Figure) [A-F]\.",txt))
            label="Article Reference" if refs else "Article Caption" if caption else "Normal"
            p=doc.add_paragraph(style=label)
            if caption and txt.startswith("Table "):p.paragraph_format.keep_with_next=True
            for node in tag.children:style.inline(p,node)
    doc.save(out)

@contextmanager
def word_exporter():
    import win32com.client
    word=win32com.client.DispatchEx("Word.Application")
    try:
        word.Visible=False
        word.DisplayAlerts=0
        word.AutomationSecurity=3
        def export(path,target):
            doc=word.Documents.Open(str(path),ReadOnly=True,AddToRecentFiles=False,Visible=False)
            try:doc.ExportAsFixedFormat(str(target),17,IncludeDocProps=False,CreateBookmarks=1,BitmapMissingFonts=False)
            finally:doc.Close(False)
        yield export
    finally:word.Quit()

def main(proofs):
    text,ledger=compile_article()
    (HERE/"manuscript.md").write_bytes(text.encode())
    (HERE/"numeric-trace.tsv").write_bytes(tsv(ledger).encode())
    supplement=supplement_text()
    (HERE/"supplement-B.md").write_bytes(supplement.encode())
    write_archive()
    old=load_old_helpers()
    with tempfile.TemporaryDirectory() as folder:
        temp=Path(folder)
        make_figure(temp)
        publications=[(HERE/"manuscript.md","article"),*[(HERE/f"supplement-{k}.md","supplement") for k in "ABC"]]
        attachments=[(p,"attachment") for p in sorted(SUB.glob("*.md"))]
        for src,kind in publications+attachments:
            write_doc(src.read_text(encoding="utf8"),src.with_suffix(".docx"),temp,old,kind)
        highlights=(SUB/"highlights.txt").read_text(encoding="utf8").splitlines()
        write_doc("# Highlights\n\n"+"\n".join("- "+line for line in highlights),SUB/"highlights.docx",temp,old)
        with word_exporter() as export:
            for src,kind in publications:export(src.with_suffix(".docx"),src.with_suffix(".pdf"))
            if proofs:
                proofs.mkdir(parents=True,exist_ok=True)
                for path in sorted(SUB.glob("*.docx")):export(path,proofs/path.with_suffix(".pdf").name)
    print(f"Prepared manuscript, three supplements, author files and {len(ledger)} traced occurrences.")

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attachment-proofs",type=Path)
    args=parser.parse_args()
    main(args.attachment_proofs.resolve() if args.attachment_proofs else None)
