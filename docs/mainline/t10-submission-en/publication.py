"""Editable and review typesetting from the numbered English source."""
from pathlib import Path
import csv
import re
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt

HERE=Path(__file__).resolve().parent
SUB=HERE/"submission"
MD=MarkdownIt("commonmark",{"html":True}).enable("table")
NAMED={1:"Howard's",2:"Memarzadeh and Pozzi",3:"Andriotis and Papakonstantinou",
       4:"Fauriat and Zio",5:"Yanes Luis et al.",10:"Bennaceur and Kloul"}

def works():
    data=(HERE/"manuscript.md").read_text(encoding="utf8")
    entries=re.findall(r"^\[(\d+)\] (.+)$",data.split("\n## References\n",1)[1],re.M)
    with (HERE/"reference-crosswalk.tsv").open(encoding="utf8") as f:
        authors=list(csv.DictReader(f,delimiter="\t"))
    references={}
    for (key,entry),row in zip(entries,authors,strict=True):
        assert key==row["source_id"]
        num=int(key)
        url=re.search(r"\]\((https://[^)]+)\)$",entry)[1]
        if num<=10:
            # The accepted records all have an explicit italicized container title.
            prefix,venue,details=entry.split("*")
            title=prefix.split(". ",1)[1].strip().rstrip(".")
            published=details.split(". [DOI]")[0].strip(", ")
            volume_and_location,year=published.rsplit(", ",1)
            assert year==row["year_key"]
            volume,separator,location=volume_and_location.partition(", ")
            if separator:
                number,issue_mark,issue=volume.partition("(")
                volume_and_location=f"*{number}*{issue_mark}{issue}, {location}"
            ref=f'{row["reference_authors"]} ({year}). {title}. *{venue}*, {volume_and_location}. [{url}]({url})'
        else:
            title=entry.split("Google Cloud. ",1)[1].split(". Report issued",1)[0]
            issued=entry.split("Report issued ",1)[1].split(". [",1)[0].split()
            ref=f'Google Cloud. ({row["year_key"]}, {issued[1]} {issued[0]}). *{title}*. [{url}]({url})'
        references[num]=dict(row,url=url,ref=ref)
    return references

def review_body():
    text=(HERE/"manuscript.md").read_text(encoding="utf8").split("\n## References\n",1)[0]
    refs=works()
    paragraphs=text.splitlines()
    for i,line in enumerate(paragraphs):
        for number in re.findall(r"\[(\d+)\]",line):
            n=int(number)
            if n not in refs: raise ValueError("Unknown citation "+number)
            row=refs[n]
            mark=" ["+number+"]"
            name=NAMED.get(n)
            if name and name in line:
                line=line.replace(name,name+" ("+row["year_key"]+")",1).replace(mark,"",1)
            else:
                line=line.replace(mark," ("+row["author_label"]+", "+row["year_key"]+")",1)
        paragraphs[i]=line
    ai=(SUB/"ai-declaration.txt").read_text(encoding="utf8").strip().split("\n\n",1)
    paragraphs.extend(["","### "+ai[0],"",ai[1],"","## References",""])
    for ref in sorted(refs.values(),key=lambda r:(r["reference_authors"].casefold(),r["year_key"])):
        paragraphs.extend([ref["ref"],""])
    return BeautifulSoup(MD.render("\n".join(paragraphs)), "html.parser")

def flatten(node):
    return " ".join(node.get_text(" ",strip=True).split())
