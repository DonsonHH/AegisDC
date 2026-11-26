"""Build the ESWA review manuscript and printable figures without study execution."""
import argparse
from pathlib import Path
import tempfile
from bs4 import NavigableString, Tag
from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.packuri import PackURI
from docx.opc.part import Part
from docx.shared import Mm, Pt, RGBColor
from lxml import etree as ET
from playwright.sync_api import sync_playwright
from figures import FACILITY, PLOTS, make_figure, parse
from publication import HERE, MD, SUB, review_body
from bs4 import BeautifulSoup

FIG=HERE/"figures"

def render_art(browser_path, temporary):
    FIG.mkdir(exist_ok=True)
    with sync_playwright() as engine:
        browser=engine.chromium.launch(executable_path=browser_path,headless=True)
        for stem in (FACILITY,*PLOTS):
            raw=make_figure(stem)
            (FIG/(stem+".svg")).write_bytes(raw)
            svg=parse(raw)
            width,height=map(float,svg.get("viewBox").split()[2:])
            # SVG user units set both outputs' aspect ratio; no chart values are recomputed.
            w=round(width*2)
            h=round(w*height/width)
            page=browser.new_page(viewport={"width":w,"height":h},device_scale_factor=1.5)
            css=f"@page{{size:{width}pt {height}pt;margin:0}}*{{margin:0;padding:0}}svg{{display:block;width:100%;height:auto}}"
            page.set_content("<style>"+css+"</style>"+ET.tostring(svg,encoding="unicode"))
            page.screenshot(path=str(temporary/(stem+".png")))
            page.pdf(path=str(FIG/(stem+".pdf")),prefer_css_page_size=True,print_background=True)
            page.close()
        browser.close()

def face(style,font,size,colour="22282B"):
    style.font.name=font
    style.font.size=Pt(size)
    style.font.color.rgb=RGBColor.from_string(colour)

def configure(doc):
    sec=doc.sections[0]
    sec.page_width,sec.page_height=Mm(210),Mm(297)
    sec.left_margin=sec.right_margin=Mm(25)
    sec.top_margin,sec.bottom_margin=Mm(22),Mm(22)
    sec.footer_distance=Mm(10)
    main=doc.styles["Normal"]
    face(main,"Cambria",11)
    main.paragraph_format.line_spacing=1.18
    main.paragraph_format.space_after=Pt(5)
    main.paragraph_format.widow_control=True
    for sty,size in (("Title",19),("Subtitle",12),("Heading 1",14),("Heading 2",12)):
        st=doc.styles[sty];face(st,"Cambria",size,"1D292C");st.font.italic=False
        st.font.bold=sty!="Subtitle"
        fmt=st.paragraph_format;fmt.space_before=Pt(10 if sty.startswith("Heading") else 0);fmt.space_after=Pt(5)
        fmt.keep_with_next=True
        ppr=st.element.get_or_add_pPr()
        for border in ppr.findall(qn("w:pBdr")):ppr.remove(border)
    for name,size in (("Article Caption",9),("Article Table",9),("Article Reference",9.5),("Article Algorithm",10)):
        style=doc.styles.add_style(name,WD_STYLE_TYPE.PARAGRAPH); style.base_style=main
        face(style,"Cambria",size)
        style.paragraph_format.space_after=Pt(3);style.paragraph_format.line_spacing=1.10
    fmt=doc.styles["Article Reference"].paragraph_format
    fmt.left_indent=Mm(6);fmt.first_line_indent=Mm(-6)
    fmt.space_after=Pt(1)
    fmt.keep_together=True
    header=sec.footer.paragraphs[0]
    header.alignment=WD_ALIGN_PARAGRAPH.CENTER
    field=OxmlElement("w:fldSimple");field.set(qn("w:instr"),"PAGE");header._p.append(field)
    props=doc.core_properties
    props.author="";props.last_modified_by="";props.keywords="";props.comments=""
    props.title="When is a paid inspection worth waiting for during maintenance-induced degradation?"
    props.subject="Expert Systems with Applications"

def linked(par,text,url):
    h=OxmlElement("w:hyperlink");h.set(qn("r:id"),par.part.relate_to(url,RT.HYPERLINK,is_external=True))
    r=OxmlElement("w:r");p=OxmlElement("w:rPr");c=OxmlElement("w:color");c.set(qn("w:val"),"22546A");p.append(c);r.append(p)
    t=OxmlElement("w:t");t.text=text;r.append(t);h.append(r);par._p.append(h)

def inline(par,node,bold=False,italic=False,sub=False):
    if isinstance(node,NavigableString):
        run=par.add_run(str(node).replace("\u3000"," "));run.bold=bold;run.italic=italic;run.font.subscript=sub
        return
    if node.name=="a":
        label=node.get_text();url=node["href"]
        if url.startswith("https://"): linked(par,label,url)
        else:
            # The numbered source carries the versioned pointers, not the reviewer-facing file.
            run=par.add_run(label);run.italic=True;run.font.size=Pt(9);run.font.color.rgb=RGBColor.from_string("526268")
        return
    if node.name=="code":
        run=par.add_run(node.get_text());run.font.name="Consolas";run.font.size=Pt(9);return
    for child in node.children:
        inline(par,child,bold or node.name=="strong",italic or node.name=="em",sub or node.name=="sub")

def vector_image(doc,tag,tempdir):
    stem=Path(tag["src"]).stem
    p=doc.add_paragraph()
    p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next=True
    p.paragraph_format.space_after=Pt(2)
    width=Mm(137 if stem==PLOTS[1] else 158)
    pic=p.add_run().add_picture(str(tempdir/(stem+".png")),width=width)
    pic._inline.docPr.set("descr",tag["alt"])
    vector=Part(PackURI("/word/media/"+stem+".svg"),"image/svg+xml",(FIG/(stem+".svg")).read_bytes(),doc.part.package)
    rid=doc.part.relate_to(vector,RT.IMAGE)
    b=pic._inline.xpath(".//a:blip")[0];lst=OxmlElement("a:extLst");ext=OxmlElement("a:ext")
    ext.set("uri","{96DAC541-7B7A-43D3-8B79-37D633B846F1}")
    v=ET.SubElement(ext,"{http://schemas.microsoft.com/office/drawing/2016/SVG/main}svgBlip");v.set(qn("r:embed"),rid)
    lst.append(ext);b.append(lst)

def table(doc,tag):
    tr=tag.select("tr")
    widths={3:[34,64,62],4:[40,33,38,49],5:[44,17,25,36,38]}
    cols=len(tr[0].find_all(["th","td"],recursive=False))
    sizes=widths[cols]
    if "maintenance duration" in tr[0].get_text().lower(): sizes=[65,31,32,32]
    if "Reporting topic" in tr[0].get_text(): sizes=[13,28,43,76]
    t=doc.add_table(rows=0,cols=cols)
    t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
    for col,w in zip(t.columns,sizes,strict=True):col.width=Mm(w)
    borders=OxmlElement("w:tblBorders")
    for edge in ("top","bottom","insideH"):
        line=OxmlElement("w:"+edge);line.set(qn("w:val"),"single");line.set(qn("w:sz"),"5" if edge!="insideH" else "3")
        line.set(qn("w:color"),"738488" if edge!="insideH" else "CCD4D6");borders.append(line)
    t._tbl.tblPr.append(borders)
    for j,row in enumerate(tr):
        wrow=t.add_row();pr=wrow._tr.get_or_add_trPr();pr.append(OxmlElement("w:cantSplit"))
        if j==0:pr.append(OxmlElement("w:tblHeader"))
        for cell,txt,w in zip(wrow.cells,row.find_all(["th","td"],recursive=False),sizes,strict=True):
            cell.width=Mm(w);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            para=cell.paragraphs[0];para.style="Article Table"
            para.paragraph_format.space_before=Pt(3);para.paragraph_format.keep_with_next=j==0
            if j==0:
                sh=OxmlElement("w:shd");sh.set(qn("w:fill"),"EEF2F2");cell._tc.get_or_add_tcPr().append(sh)
            for child in txt.children:inline(para,child,bold=(j==0))

def write_word(tempdir):
    doc=Document();configure(doc)
    is_ref=False
    for tag in review_body().children:
        if not isinstance(tag,Tag):continue
        text=tag.get_text(strip=True)
        if tag.name.startswith("h") and tag.name in ("h1","h2","h3"):
            sty={"h1":"Title","h2":"Heading 1","h3":"Heading 2"}[tag.name]
            p=doc.add_paragraph(tag.get_text().replace("\u3000"," "),style=sty)
            if text=="References":is_ref=True
        elif tag.name=="table":table(doc,tag)
        elif tag.name=="blockquote":
            p=doc.add_paragraph(style="Article Algorithm");p.paragraph_format.keep_with_next=True
            for child in tag.find("p").children:inline(p,child)
            for i,item in enumerate(tag.select("ol > li"),1):
                p=doc.add_paragraph(style="Article Algorithm")
                p.paragraph_format.left_indent=Mm(6);p.paragraph_format.first_line_indent=Mm(-6)
                p.add_run(f"{i}. ").bold=True
                for child in item.children:inline(p,child)
        elif tag.name=="p":
            if tag.find("img"):vector_image(doc,tag.img,tempdir);continue
            if text.startswith(("Table ","Figure ")):style="Article Caption"
            elif text.startswith("A paired simulation study"):style="Subtitle"
            elif is_ref:style="Article Reference"
            else:style="Normal"
            p=doc.add_paragraph(style=style)
            for child in tag.children:inline(p,child)
        else:raise ValueError(f"Unrendered manuscript element: {tag.name}")
    out=HERE/"manuscript.docx";doc.save(out)
    return out

def print_word(path):
    import win32com.client
    app=win32com.client.DispatchEx("Word.Application")
    try:
        app.Visible=False;app.DisplayAlerts=0;app.AutomationSecurity=3
        doc=app.Documents.Open(str(path),ReadOnly=True,AddToRecentFiles=False,Visible=False)
        try: doc.ExportAsFixedFormat(str(path.with_suffix(".pdf")),17,IncludeDocProps=False,CreateBookmarks=1,BitmapMissingFonts=False)
        finally: doc.Close(False)
    finally: app.Quit()

def submission_documents():
    for src in sorted(SUB.glob("*.txt")):
        doc=Document();configure(doc)
        doc.core_properties.title=src.stem.replace("-"," ").title()
        body=src.read_text(encoding="utf8").strip()
        if src.stem=="highlights":
            doc.add_paragraph("Highlights",style="Title")
            for line in body.splitlines(): doc.add_paragraph(line,style="List Bullet")
        else:
            for i,block in enumerate(body.split("\n\n")):
                style="Title" if i==0 and src.stem!="cover-letter" else "Normal"
                doc.add_paragraph(block,style=style)
        doc.save(src.with_suffix(".docx"))
    src=SUB/"stress-checklist.md"
    doc=Document();configure(doc);doc.core_properties.title="STRESS reporting checklist"
    for tag in BeautifulSoup(MD.render(src.read_text(encoding="utf8")),"html.parser").children:
        if not isinstance(tag,Tag):continue
        if tag.name=="table": table(doc,tag)
        else:
            p=doc.add_paragraph(style="Title" if tag.name=="h1" else "Normal")
            for child in tag.children: inline(p,child)
    doc.save(src.with_suffix(".docx"))

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser-executable",help="Chrome/Chromium executable for deterministic figure typesetting")
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="aegis-publication-") as tmp:
        render_art(args.browser_executable,Path(tmp))
        print_word(write_word(Path(tmp)))
        submission_documents()
