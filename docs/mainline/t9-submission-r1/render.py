"""Typeset the editable paper and place the two reviewed vector PDFs inside its print edition.

Dependencies: markdown-it-py, beautifulsoup4, playwright with Chromium, pypdf.
The build reads manuscript assets only; it has no facility or scoring imports.
"""
import argparse
import base64
import hashlib
from html import escape
from io import BytesIO
from pathlib import Path
import re
from urllib.parse import quote

from bs4 import BeautifulSoup
from markdown_it import MarkdownIt


HERE = Path(__file__).resolve().parent
PUBLIC = "https://github.com/DonsonHH/AegisDC/blob/donson/mainline-39c-endpoints/docs/mainline/t9-submission-r1/"
MARK = "https://layout.invalid/aegis-vector/"
VECTORS = {"T7-paired-directions": "78f58b7f9b1d9e6d56bd6fedecedb3ff6eca4f64c572c8c0d5c0997baee4ead1",
           "T8-edit-tradeoffs": "1c278f463e4e78463673526cd4cb66c16624b8bc94ebffe01e1d718bd4f6d296"}

CSS = """
*{box-sizing:border-box} html{color-scheme:light} body{margin:0;background:#eff2f3;color:#1b2932}
main{font:16px/1.72 'Noto Serif CJK SC','Songti SC','SimSun',serif}
.sheet{max-width:880px;margin:22px auto;padding:38px 52px 42px;background:white;border:1px solid #dce3e6}
h1,h2,h3,table,figcaption,blockquote,.caption{font-family:'Microsoft YaHei','Noto Sans CJK SC',sans-serif}
h1{font-size:2.05rem;line-height:1.25;margin:0 0 .3em}h2{font-size:1.34rem;color:#104e64;margin:1.1em 0 .4em}
h3{font-size:1.08rem;margin:1em 0 .4em;color:#243b46} .sheet>:first-child{margin-top:0}
p{margin:.54em 0;text-align:justify;overflow-wrap:break-word;orphans:2;widows:2}
p.subtitle{font:600 1.12rem/1.5 'Microsoft YaHei',sans-serif;color:#415765;margin:.35em 0 1.2em}
a{color:#13627c;text-decoration-thickness:.065em;text-underline-offset:.16em}
table{border-collapse:collapse;width:100%;margin:.7em 0;font-size:.84em;line-height:1.5}
th,td{border-bottom:1px solid #d9e0e3;padding:.44em .50em;vertical-align:top}
th{background:#e9f2f4;color:#173f4d;text-align:left;border-top:1.4px solid #38788a}
tr:last-child td{border-bottom:1.2px solid #73919c}
figure{margin:.75em auto .55em;text-align:center;break-inside:avoid}
figure img{display:block;width:100%;height:auto}
.figure-link{display:block;width:100%;line-height:0;text-decoration:none}
figure.edit-plot{max-width:680px}
figcaption,.caption{font-size:.81em;line-height:1.52;color:#475761;text-align:left;margin:.4em 0}
figcaption em,.caption em{font-style:normal}
blockquote{margin:.65em 0;padding:.65em 1em;border-left:3px solid #397e91;background:#f0f5f6;font-size:.92em;line-height:1.5}
blockquote p{margin:.22em 0}blockquote ol{padding-left:1.5em;margin:.36em 0}blockquote li{margin:.18em 0}
code{font: .88em/1.3 'Consolas','Liberation Mono',monospace;overflow-wrap:anywhere}
.references p{font-size:.88em;line-height:1.48;margin:.48em 0;text-align:left}
@media(max-width:640px){.sheet{margin:0;padding:20px 16px;border:none} main{font-size:15px}
h1{font-size:1.7rem}table{font-size:.79em}td,th{padding:.34em .28em}p{text-align:left}figure{width:100%}}
@page{size:A4;margin:16mm 17mm 16mm;@bottom-center{content:counter(page);font:9pt Arial;color:#516672}}
@media print{
  body{background:#fff}main{font-size:10.8pt;line-height:1.56}
  .sheet{width:auto;max-width:none;margin:0;padding:0;border:0;break-before:page}
  .sheet:first-child{break-before:auto}h1{font-size:23pt}h2{font-size:14.2pt}h3{font-size:11.8pt}
  h1,h2,h3{break-after:avoid}p.subtitle{font-size:12pt}
  p{margin:.42em 0}table{font-size:9.2pt;line-height:1.42;break-inside:avoid}
  th,td{padding:.37em .45em}blockquote{font-size:9.8pt;line-height:1.49}
  figure.edit-plot{max-width:172mm}figcaption,.caption{font-size:8.6pt}figure{margin:.50em auto}
  .references p{font-size:8.7pt;line-height:1.38;margin:.40em 0}
  a{color:#214e60;text-decoration:none} *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
}
"""


def make_html(source=HERE / "manuscript.md"):
    md = MarkdownIt("commonmark", {"html": True}).enable("table")
    pages = source.read_text(encoding="utf8").split("<!-- page -->")
    main = "".join('<section class="sheet">' + md.render(p) + "</section>" for p in pages)
    doc = BeautifulSoup("<main>" + main + "</main>", "html.parser")
    title = doc.h1.get_text(strip=True)
    doc.h1.find_next_sibling("p")["class"] = "subtitle"
    for img in doc.select("p > img"):
        path = HERE / img["src"]
        if path.parent != HERE / "figures" or path.suffix != ".svg":
            raise ValueError("Figure must be a local vector asset")
        figure = doc.new_tag("figure")
        if path.stem.startswith("T8-"):
            figure["class"] = "edit-plot"
        parent = img.parent
        caption = parent.find_next_sibling("p")
        if not caption or not caption.get_text(strip=True).startswith("图 "):
            raise ValueError("Missing figure caption")
        parent.replace_with(figure)
        img.extract()
        img["src"] = "data:image/svg+xml;base64," + base64.b64encode(path.read_bytes()).decode()
        if path.stem in VECTORS:
            link = doc.new_tag("a", href="figures/"+path.stem+".pdf")
            link["class"] = "figure-link"
            link["data-vector"] = path.stem
            figure.append(link)
            link.append(img)
        else:
            figure.append(img)
        caption.extract()
        caption.name = "figcaption"
        figure.append(caption)
    for para in doc.select("p"):
        if para.get_text(strip=True).startswith("表 ") and para.find("em"):
            para["class"] = "caption"
    refs = doc.find("h2", string="参考文献")
    if refs:
        container = doc.new_tag("section", attrs={"class":"references"})
        for node in list(refs.find_next_siblings()):
            container.append(node.extract())
        refs.insert_after(container)
    return ("<!doctype html>\n<html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<title>"+escape(title)+"</title><style>"+CSS+"</style></head><body>"+str(doc)+"</body></html>\n")


def original_forms(pdf, output):
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import (ArrayObject, DecodedStreamObject, DictionaryObject, FloatObject,
                               NameObject, TextStringObject)
    writer = PdfWriter()
    writer.append(PdfReader(BytesIO(pdf)))
    seen = set()
    for page in writer.pages:
        annots = page.get("/Annots", [])
        for ref in list(annots):
            annotation = ref.get_object()
            action = annotation.get("/A") or {}
            url = str(action.get("/URI", ""))
            if url.startswith("file:"):
                raise ValueError("Local path in print link")
            if not url.startswith(MARK):
                continue
            stem = url[len(MARK):].rstrip("/")
            if stem in seen or stem not in VECTORS:
                raise ValueError("Repeated or unknown vector slot")
            data = (HERE / "figures" / (stem+".pdf")).read_bytes()
            if hashlib.sha256(data).hexdigest() != VECTORS[stem]:
                raise ValueError("Reviewed figure bytes have changed")
            original = PdfReader(BytesIO(data)).pages[0]
            box = original.mediabox
            left,bottom,right,top = map(float,annotation["/Rect"])
            ratio_x = (right-left)/float(box.width)
            ratio_y = (top-bottom)/float(box.height)
            if min(ratio_x,ratio_y) <= 0 or abs(ratio_x/ratio_y-1) > .018:
                raise ValueError("Print slot aspect ratio differs from reviewed figure")
            scale = min(ratio_x, ratio_y)
            x = (left + right - scale*float(box.width))/2
            y = (bottom + top - scale*float(box.height))/2
            form = DecodedStreamObject()
            form.set_data(original.get_contents().get_data())
            form.update({NameObject("/Type"):NameObject("/XObject"), NameObject("/Subtype"):NameObject("/Form"),
                         NameObject("/BBox"):ArrayObject([FloatObject(v) for v in box]),
                         NameObject("/Resources"):original["/Resources"].clone(writer),
                         NameObject("/AegisSourceSHA256"):TextStringObject(VECTORS[stem])})
            resources = page["/Resources"]
            resources.setdefault(NameObject("/XObject"), DictionaryObject())
            refname = "/Aegis" + stem[:2]
            resources["/XObject"][NameObject(refname)] = writer._add_object(form)
            stream = DecodedStreamObject()
            # Chromium can leave a page-scale transform active. Place the original
            # vector form in default PDF user space, where link rectangles live.
            stream.set_data(b"q\n" + page.get_contents().get_data() + b"\nQ\n" +
                            f"q {scale:.8f} 0 0 {scale:.8f} {x:.6f} {y:.6f} cm {refname} Do Q\n".encode())
            page[NameObject("/Contents")] = writer._add_object(stream)
            annots.remove(ref)
            seen.add(stem)
    if seen != set(VECTORS):
        raise ValueError("Print did not expose both vector slots")
    writer.add_metadata({"/Title":"维护降级时，何时值得等待一次付费核查？",
                         "/Subject":"耦合算力设施中的稀疏证据、作业窗口与服务损失"})
    with output.open("wb") as f:
        writer.write(f)


def render_pdf(html_path, output, executable, *, coverage_note=False):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        options = {"executable_path": executable} if executable else {"channel":"chrome"}
        browser = playwright.chromium.launch(headless=True, **options)
        page = browser.new_page()
        page.route("http**://**/*", lambda r:r.abort())
        page.goto(html_path.resolve().as_uri(), wait_until="load")
        page.evaluate("""({base,marker}) => {
          for(const a of document.querySelectorAll('a[href]')){
            const raw=a.getAttribute('href');
            if(a.dataset.vector){
              a.href=marker+a.dataset.vector;
              const image=a.querySelector('img'), w=image.naturalWidth,h=image.naturalHeight;
              if(!w || !h) throw Error('Vector slot did not load');
              const empty='<svg xmlns="http://www.w3.org/2000/svg" width="'+w+'" height="'+h+'"><rect width="100%" height="100%" fill="white"/></svg>';
              image.src='data:image/svg+xml,'+encodeURIComponent(empty);
            }else if(!/^(?:https?:|#)/.test(raw)){ a.href=base+raw; }
          }
        }""", {"base":PUBLIC,"marker":MARK})
        page.evaluate("() => Promise.all([...document.images].map(i=>i.decode()))")
        page.evaluate("() => document.fonts.ready")
        data = page.pdf(format="A4", prefer_css_page_size=True, print_background=True,
                        display_header_footer=False)
        browser.close()
    if coverage_note:
        from pypdf import PdfReader
        if len(PdfReader(BytesIO(data)).pages) != 1:
            raise ValueError("The bibliography assessment must fit on one A4 page")
        output.write_bytes(data)
    else:
        original_forms(data, output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=HERE)
    parser.add_argument("--browser-executable")
    parser.add_argument("--html-only", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name in ("manuscript", "reference-coverage"):
        html_path = args.output_dir / (name + ".html")
        html_path.write_bytes(make_html(HERE / (name + ".md")).encode())
        if not args.html_only:
            render_pdf(html_path, args.output_dir / (name + ".pdf"), args.browser_executable,
                       coverage_note=(name == "reference-coverage"))
