#!/usr/bin/env python3
"""Publish existing prose/figures as offline HTML. No project runtime imports.

Requires installed Pandoc 3.1+ and lxml. Uses MathML, embedded SVG/CSS and
no external JavaScript or stylesheet. It does not generate research inputs.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import lxml
from lxml import html, etree

ROOT = Path(__file__).resolve().parents[1]
DOCS = {
    "manuscript.md": "manuscript.html",
    "reproducibility.md": "reproducibility.html",
    "references.md": "references.html",
    "figure-map.md": "figure-map.html",
    "data/paired-tables.md": "paired-tables.html",
}

def convert(source, target):
    src = ROOT / source
    out = ROOT / target
    cmd = [
        "pandoc", str(src), "--from", "markdown+tex_math_dollars-implicit_figures",
        "--to", "html5", "--standalone", "--mathml", "--toc", "--toc-depth=3",
        "--embed-resources", "--resource-path", str(ROOT),
        "--template", str(ROOT / "tools/paper-template.html"),
        "--css", str(ROOT / "tools/paper.css"),
        "--metadata", "pagetitle=" + src.read_text(encoding="utf-8").splitlines()[0].lstrip("# "),
    ]
    raw = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=ROOT).stdout
    tree = html.document_fromstring(raw)
    # Keep the manually written scientific caption with its figure at page breaks.
    for paragraph in list(tree.xpath("//main/p[count(img)+count(svg)=1]")):
        image = paragraph.find("img")
        if image is None:
            image = paragraph.find("svg")
        if len(paragraph) != 1 or (paragraph.text or "").strip():
            continue
        parent = paragraph.getparent()
        figure = etree.Element("figure")
        parent.replace(paragraph, figure)
        figure.append(image)
        following = figure.getnext()
        if following is not None and following.tag == "p" and "".join(following.itertext()).lstrip().startswith("图 "):
            caption = etree.SubElement(figure, "figcaption")
            parent.remove(following)
            caption.append(following)
    for table in list(tree.xpath("//main/table")):
        wrapper = etree.Element("div", attrib={"class": "table-scroll"})
        table.getparent().replace(table, wrapper)
        wrapper.append(table)
    # The preview files sit together even when their Markdown source is in data/.
    for a in tree.xpath("//a[@href]"):
        href = a.get("href")
        bare, sep, anchor = href.partition("#")
        if bare in DOCS:
            a.set("href", DOCS[bare] + (sep + anchor if sep else ""))
        elif source.startswith("data/") and bare and not bare.startswith(("http:","https:","#","data:")):
            a.set("href", str((Path("data") / bare).as_posix()) + (sep + anchor if sep else ""))
    output = etree.tostring(tree, encoding="unicode", method="html", doctype="<!DOCTYPE html>")
    out.write_text(output, encoding="utf-8")
    return {"source": source, "output": target, "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
            "figures": len(tree.xpath("//figure")), "tables": len(tree.xpath("//table")),
            "mathml": len(tree.xpath("//*[local-name()='math']")), "command": cmd}

def main():
    rows = [convert(src, out) for src, out in DOCS.items()]
    record = {"activity": "publication_rendering_of_existing_records", "python": sys.version,
              "pandoc": subprocess.run(["pandoc","--version"],check=True,capture_output=True,text=True).stdout.splitlines()[0],
              "lxml": lxml.__version__, "outputs": rows,
              "project_facility_calls": 0, "strategy_calls": 0, "scorer_calls": 0,
              "qualification_executions": 0, "research_runs": 0}
    (ROOT / "preview-receipt.json").write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"outputs":[{k:r[k] for k in ("output","figures","tables","mathml")} for r in rows]},ensure_ascii=False))

if __name__ == "__main__":
    main()
