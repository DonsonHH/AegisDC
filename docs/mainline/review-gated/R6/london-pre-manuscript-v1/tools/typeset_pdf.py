#!/usr/bin/env python3
"""Typeset existing manuscript and figures with installed Pandoc/ReportLab.
No project runtime imports, research inputs, browser, or dependency installation.
"""
from pathlib import Path
import hashlib, importlib.metadata, json, re, subprocess, sys
from html import escape
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image as PILImage
from pypdf import PdfReader
from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, LongTable, TableStyle, KeepTogether

ROOT=Path(__file__).resolve().parents[1]
PUBLISH="https://github.com/DonsonHH/AegisDC/blob/donson/mainline-39c-endpoints/docs/mainline/review-gated/R6/london-pre-manuscript-v1/"
W,H=A4; CW=W-36*mm
rl_config.invariant=1
pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
for name,file in [("Latin","DejaVuSerif.ttf"),("Latin-Bold","DejaVuSerif-Bold.ttf")]:
    pdfmetrics.registerFont(TTFont(name,"/usr/share/fonts/truetype/dejavu/"+file))
pdfmetrics.registerFont(TTFont("Math",str(Path(matplotlib.get_data_path())/"fonts/ttf/STIXGeneral.ttf")))
pdfmetrics.registerFontFamily("STSong-Light",normal="STSong-Light",bold="STSong-Light",italic="STSong-Light",boldItalic="STSong-Light")
pdfmetrics.registerFontFamily("Latin",normal="Latin",bold="Latin-Bold",italic="Latin",boldItalic="Latin-Bold")
INK=colors.HexColor("#19343f"); MUTED=colors.HexColor("#49616d")
body=ParagraphStyle("body",fontName="STSong-Light",fontSize=10.5,leading=18.2,wordWrap="CJK",textColor=INK,
    allowWidows=0,allowOrphans=0,spaceAfter=7,alignment=TA_JUSTIFY)
styles={"body":body}
for key,kwargs in {
 "title":dict(fontSize=23,leading=33,spaceAfter=12,alignment=TA_LEFT,keepWithNext=True),
 "subtitle":dict(fontSize=15,leading=22,textColor=MUTED,spaceAfter=18,alignment=TA_LEFT,keepWithNext=True),
 "h2":dict(fontSize=15,leading=23,spaceBefore=16,spaceAfter=9,alignment=TA_LEFT,keepWithNext=True),
 "h3":dict(fontSize=12,leading=20,spaceBefore=13,spaceAfter=7,alignment=TA_LEFT,keepWithNext=True),
 "cell":dict(fontSize=8.3,leading=13.4,spaceAfter=0,alignment=TA_LEFT),
 "caption":dict(fontSize=8.8,leading=14,textColor=MUTED,spaceBefore=5,spaceAfter=12),
 "tablecaption":dict(fontSize=9.5,leading=16,spaceBefore=6,spaceAfter=5,keepWithNext=True)
}.items():styles[key]=ParagraphStyle(key,parent=body,**kwargs)

def runs(s):
    chunks=re.split(r"([\u0000-\u024f\u0370-\u03ff\u2000-\u206f\u2070-\u209f\u2100-\u22ff]+)",s)
    result=[]
    for i,c in enumerate(chunks):
        if not c:continue
        if not i%2:result.append(escape(c));continue
        segments=re.split(r"([\u2100-\u22ff]+)",c)
        for j,part in enumerate(segments):
            if part:result.append(f'<font name="{"Math" if j%2 else "Latin"}">{escape(part)}</font>')
    return "".join(result)

def inline(nodes):
    out=[]
    for n in nodes:
        t=n["t"];c=n.get("c")
        if t=="Str":out.append(runs(c))
        elif t in ("Space","SoftBreak"):out.append(" ")
        elif t=="LineBreak":out.append("<br/>")
        elif t in ("Strong","Emph"):
            tag="b" if t=="Strong" else "i";out.append(f"<{tag}>"+inline(c)+f"</{tag}>")
        elif t=="Code":out.append(runs(c[1]))
        elif t in ("Subscript","Superscript"):
            tag="sub" if t=="Subscript" else "super";out.append(f"<{tag}>"+inline(c)+f"</{tag}>")
        elif t=="Link":
            href=c[2][0]
            if not href.startswith(("https://","http://","#")):href=PUBLISH+href
            out.append(f'<link href="{escape(href,quote=True)}" color="#235e6d">'+inline(c[1])+"</link>")
        elif t=="Math":out.append(runs(c[1]))
        elif t=="Quoted":out.append(runs("“")+inline(c[1])+runs("”"))
        elif t=="Span":out.append(inline(c[1]))
        elif t=="RawInline":
            found=re.search(r'id="([^"]+)"',c[1])
            if found:out.append(f'<a name="{escape(found.group(1),quote=True)}"/>')
        elif t=="Image":pass
        else:raise ValueError("Unhandled inline "+t)
    return "".join(out)

def plain(nodes):return re.sub(r"<[^>]*>","",inline(nodes))
def cells(blocks):return "<br/>".join(inline(b["c"]) for b in blocks if b["t"] in ("Para","Plain"))
def image(path,max_h=126*mm,native_dpi=None):
    with PILImage.open(path) as im:w,h=im.size
    width=min(CW,w*72/native_dpi) if native_dpi else CW
    height=width*h/w
    if height>max_h:width*=max_h/height;height=max_h
    return Image(str(path),width=width,height=height,hAlign="CENTER")

def formulas():
    definitions=[
     [r"$L=\int_0^H \ell(t)\,\mathrm{d}t$",r"$\ell(t)=(d(t)-s(t))/d(t)\quad\mathrm{if}\ d(t)>0;\qquad 0\quad\mathrm{otherwise}$"],
     [r"$U=\int_0^H (d(t)-s(t))\,\mathrm{d}t$"]]
    paths=[]
    for idx,lines in enumerate(definitions,1):
        fig=plt.figure(figsize=(7,1.05 if len(lines)>1 else .65),facecolor="white")
        for j,line in enumerate(lines):fig.text(.5,.72-j*.43 if len(lines)>1 else .5,line,ha="center",va="center",fontsize=13.5,color="#19343f")
        path=ROOT/"figures"/f"formula-{idx}.png";fig.savefig(path,dpi=400,bbox_inches="tight",pad_inches=.05);plt.close(fig);paths.append(path)
    return paths

class PaperDoc(SimpleDocTemplate):
    def afterFlowable(self,f):
        if isinstance(f,Paragraph) and f.style.name in ("title","h2","h3"):
            level={"title":0,"h2":1,"h3":2}[f.style.name]
            key="heading-"+str(getattr(self,"headings",0));self.headings=getattr(self,"headings",0)+1
            self.canv.bookmarkPage(key);self.canv.addOutlineEntry(f.getPlainText(),key,level=level,closed=False)

def frame(canvas,doc):
    canvas.saveState();canvas.setStrokeColor(colors.HexColor("#d9e2e5"));canvas.setLineWidth(.4)
    canvas.line(18*mm,H-15*mm,W-18*mm,H-15*mm);canvas.setFont("Latin",7);canvas.setFillColor(MUTED)
    canvas.drawString(18*mm,H-12*mm,"AegisDC | London PRE | Chinese working paper v1")
    canvas.drawString(18*mm,11*mm,"Existing evidence; no new research runs");canvas.drawRightString(W-18*mm,11*mm,str(doc.page));canvas.restoreState()

def main():
    cmd=["pandoc",str(ROOT/"manuscript.md"),"--from","markdown+tex_math_dollars-implicit_figures","--to","json"]
    blocks=json.loads(subprocess.run(cmd,check=True,capture_output=True,text=True).stdout)["blocks"]
    fs=formulas();fi=0;ti=0;story=[];i=0
    while i<len(blocks):
        b=blocks[i];t=b["t"];c=b.get("c");i+=1
        if t=="Header":
            level,attr,nodes=c
            style="title" if level==1 else ("subtitle" if plain(nodes).startswith("伦敦式合成实例中的") else "h2" if level==2 else "h3")
            story.append(Paragraph(f'<a name="{escape(attr[0],quote=True)}"/>'+inline(nodes),styles[style]))
        elif t in ("Para","Plain"):
            if len(c)==1 and c[0]["t"]=="Image":
                group=[Spacer(1,7),image((ROOT/c[0]["c"][2][0]).with_suffix(".png"))]
                if i<len(blocks) and blocks[i]["t"]=="Para" and plain(blocks[i]["c"]).startswith("图 "):
                    group.append(Paragraph(inline(blocks[i]["c"]),styles["caption"]));i+=1
                story.append(KeepTogether(group))
            elif len(c)==1 and c[0]["t"]=="Math" and c[0]["c"][0]["t"]=="DisplayMath":
                story.extend([image(fs[fi],28*mm,native_dpi=400),Spacer(1,6)]);fi+=1
            else:
                if not plain(c).strip():continue
                content=inline(c)
                ref=re.match(r"\[(\d+)\]",plain(c))
                if ref:content=f'<a name="ref-{ref.group(1)}"/>'+content
                story.append(Paragraph(content,styles["tablecaption" if plain(c).startswith("表 ") else "body"]))
        elif t=="Table":
            head=c[3][1];rows=list(head)
            for part in c[4]:rows.extend(part[2]);rows.extend(part[3])
            data=[[Paragraph(cells(cell[4]),styles["cell"]) for cell in row[1]] for row in rows]
            widths=[[.12,.30,.30,.28],[.10,.14,.10,.10,.17,.39],[.17,.23,.28,.32],[.16,.20,.20,.24,.20]][ti];ti+=1
            table=LongTable(data,colWidths=[CW*x for x in widths],repeatRows=len(head),hAlign="LEFT")
            table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,len(head)-1),colors.HexColor("#eaf1f3")),
                ("LINEABOVE",(0,0),(-1,0),.8,colors.HexColor("#75939e")),("LINEBELOW",(0,0),(-1,len(head)-1),.5,colors.HexColor("#a9bec6")),
                ("LINEBELOW",(0,len(head)),(-1,-1),.25,colors.HexColor("#d8e2e6")),("VALIGN",(0,0),(-1,-1),"TOP"),
                ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7)]))
            story.extend([table,Spacer(1,10)])
        elif t=="RawBlock":
            pass # Reference anchors are attached to nonempty reference entries.
        elif t=="HorizontalRule":story.append(Spacer(1,8))
        else:raise ValueError("Unhandled block "+t)
    path=ROOT/"manuscript.pdf"
    doc=PaperDoc(str(path),pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=20*mm,bottomMargin=19*mm,
        title="维护降级条件下，事前核查何时值得等待？",author="AegisDC working manuscript",subject="Finite London PRE evidence and static R5 disposition")
    doc.build(story,onFirstPage=frame,onLaterPages=frame)
    record={"activity":"publication_typesetting_of_existing_prose_and_figures","python":sys.version,
        "reportlab":importlib.metadata.version("reportlab"),"pypdf":importlib.metadata.version("pypdf"),"matplotlib":matplotlib.__version__,
        "pandoc":subprocess.run(["pandoc","--version"],check=True,capture_output=True,text=True).stdout.splitlines()[0],
        "fonts":{"chinese":"Adobe STSong-Light CID","latin":"embedded DejaVu Serif","mathematical_symbols":"embedded STIXGeneral"},
        "page_count":len(PdfReader(path).pages),"pdf_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
        "manuscript_sha256":hashlib.sha256((ROOT/"manuscript.md").read_bytes()).hexdigest(),"research_figures":4,"formula_renders":2,"tables":ti,
        "browser_print_attempt":{"status":"FAILED_BEFORE_DOCUMENT_LOAD","error":"Chromium process singleton socket: Operation not permitted",
            "prior_script_sha256":"a54aeff45cb7a76518308c3dce0dad42af482951c257bd54f1bb7c40d4b7f800","fallback":"Installed ReportLab; no permission change or dependency installation"},
        "prior_typeset_attempt":{"status":"FAILED_BEFORE_VALID_PDF","error":"Undefined PDF reference destination ref-1","correction":"Attach reference anchors to nonempty reference paragraphs"},
        "project_facility_calls":0,"strategy_calls":0,"scorer_calls":0,"qualification_executions":0,"research_runs":0,
        "visual_review":"Recorded separately after final rendered-page inspection; this script does not attest visual quality."}
    (ROOT/"pdf-receipt.json").write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:record[k] for k in ("page_count","pdf_sha256","research_figures","formula_renders","tables")},ensure_ascii=False))

if __name__=="__main__":main()
