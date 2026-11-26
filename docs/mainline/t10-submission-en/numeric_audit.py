"""Paired numeric inventory for the accepted text, table cells, references and figures."""
from collections import defaultdict
import csv
from io import StringIO
from pathlib import Path
import re
import subprocess
from figures import FACILITY, PLOTS, NS, REV, make_figure, original_plot_label, parse, source

HERE = Path(__file__).resolve().parent
CN = "docs/mainline/t9-submission-r1/"
TOKEN = re.compile(r"[0-9a-f]{8,40}(?![A-Za-z0-9])|(?:[A-Za-z]+\d+[a-z]*(?![A-Za-z0-9]))|(?<!\d)\d-\d{2}(?!\d)|[+−-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")
WORD_CN = re.compile(r"[零〇一二两三四五六七八九十百千万双单半]+")
WORD_EN = re.compile(r"\b(?:zero|once|twice|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|both|single|first|second|third|fourth|fifth|half|halves)\b", re.I)
# These phrases express identity, sequencing, terminology or units, not counted events.
LEXICAL_CN = ("同一", "下一", "唯一", "归一化", "一致", "一并", "一起", "一般", "单位", "工单", "菜单", "百分位", "百分点")
LEXICAL_EN = ("inspecting first", "First try", "present H2 first", "first attempted", "per person-second", "deficit-second")
LINK = re.compile(r"!?\[([^\]]*)\]\(([^()\s]+)\)")
ZH_VALUES={"零":"0","〇":"0","一":"1","首":"1","单":"1","二":"2","两":"2","双":"2","三":"3","四":"4",
           "五":"5","六":"6","七":"7","八":"8","九":"9","十":"10","十二":"12","半":"0.5","单一":"1"}
EN_VALUES=dict(zip("zero one two three four five six seven eight nine ten eleven twelve".split(),map(str,range(13))))
EN_VALUES.update(first="1",single="1",once="1",both="2",fourth="4",half="0.5",halves="0.5")

def frozen(path):
    return subprocess.check_output(["git", "cat-file", "blob", REV+":"+path], cwd=HERE)

def visible(s):
    return LINK.sub(lambda m: m[1], s).replace("\u3000", " ")

def lines(text):
    return [(n, s) for n, s in enumerate(text.splitlines(), 1) if s.strip()]

def cells(line):
    return line.strip("|").split("|") if line.startswith("|") else [line]

def equal(a, b, context):
    if a != b:
        raise ValueError(f"{context}: {a!r} != {b!r}")

def spelling(s):
    return s.replace("−", "-").replace(",", "")

def scope(s, phrase):
    hits = list(re.finditer(re.escape(phrase), s, flags=re.I))
    if len(hits) != 1:
        raise ValueError(f"Expected one occurrence of {phrase!r}: {s!r}")
    return hits[0].span()

def unmasked_words(s, spans, ignore, expression):
    covered = list(spans)
    for phrase in ignore:
        covered.extend(m.span() for m in re.finditer(re.escape(phrase),s,re.I))
    masked = "".join(" " if any(a <= i < b for a,b in covered) else c for i,c in enumerate(s))
    return [m[0] for m in expression.finditer(masked)]

def outline(line):
    if line.startswith("<!--"): return "print"
    if line.startswith("!["): return "figure"
    if line.startswith("|"): return "table"
    if line.startswith("#"): return line.split()[0]
    if line.startswith(">"): return "algorithm"
    if re.match(r"^\[\d+\]",line): return "reference"
    return "paragraph"

class Inventory:
    def __init__(self):
        self.rows = []

    def add(self, kind, path, zh, en, z, e, value):
        self.rows.append((kind, REV, path, zh, en, str(z), str(e), str(value)))

    def digit_pairs(self, path, zh, en, left, right):
        a=list(TOKEN.finditer(left))
        b=list(TOKEN.finditer(right))
        equal([spelling(m[0]) for m in a], [spelling(m[0]) for m in b], path+" "+zh)
        for x,y in zip(a,b,strict=True):
            self.add("printed token",path,f"{zh}@{x.start()+1}",f"{en}@{y.start()+1}",x[0],y[0],spelling(x[0]))

    def manuscripts(self):
        path=CN+"manuscript.md"
        left=lines(frozen(path).decode())
        right=lines((HERE/"manuscript.md").read_text(encoding="utf8"))
        wordmap=defaultdict(list)
        with (HERE/"quantity-phrases.tsv").open(encoding="utf8") as f:
            for row in csv.DictReader(f,delimiter="\t"):
                wordmap[int(row["source_line"])].append(row)
        for (n,cn),(m,en) in zip(left,right,strict=True):
            equal(outline(cn),outline(en),f"block at L{n}")
            equal([a.replace("../t9-submission-r1/","") for _,a in LINK.findall(en)],
                  [a for _,a in LINK.findall(cn)],f"destinations at L{n}")
            for j,(x,y) in enumerate(zip(cells(cn),cells(en),strict=True),1):
                self.digit_pairs(path,f"L{n}/cell{j}",f"L{m}/cell{j}",visible(x),visible(y))
            for (_,a),(_,b) in zip(LINK.findall(cn),LINK.findall(en),strict=True):
                if re.search(r"\d",a):
                    self.add("link identity",path,f"L{n}/link",f"L{m}/link",a,b,a)
            x,y=visible(cn),visible(en)
            zspan=[]; espan=[]
            for row in wordmap.pop(n,[]):
                zp,ep=row["chinese_phrase"],row["english_phrase"]
                zs,es=scope(x,zp),scope(y,ep)
                written=[ZH_VALUES[token] for token in WORD_CN.findall(zp) if token in ZH_VALUES]
                expressed=[EN_VALUES[token.lower()] for token in WORD_EN.findall(ep) if token.lower() in EN_VALUES]
                if written and row["value"] not in written or expressed and row["value"] not in expressed:
                    raise ValueError(f"Number-word value differs at L{n}: {zp} / {ep}")
                zspan.append(zs); espan.append(es)
                self.add("written quantity",path,f"L{n}@{zs[0]+1}",f"L{m}@{es[0]+1}",zp,ep,row["value"])
            equal(unmasked_words(x,zspan,LEXICAL_CN,WORD_CN),[],f"unclassified Chinese number word L{n}")
            equal(unmasked_words(y,espan,LEXICAL_EN,WORD_EN),[],f"unclassified English number word L{m}")
        equal(dict(wordmap),{},"unused word records")

    def figures(self):
        figure_words={
            "可到达记录进入在线决策": (("一个请求","one request",1),),
            "同一可能读数共用": (("一项","one continuation",1),),
            "一次请求或暂缓": (("一次","One request",1),),
            "两类合成事故的服务变化": (("两类","two synthetic",2),),
            "A  两族缺额增加": (("两族","either family",2),),
            "缺额归零": (("归零","to zero",0),),
            "每四行对应一轮": (("每四行","four rows",4),("一轮","a round",1),("两臂各","Each arm",2),("两臂重合","Shared descriptors",2),("一次","once",1)),
            "人员列为整板均差": (("单侧","one-sided",1),),
            "两臂锁定": (("两臂","both",2),),
            "另一个降低缺额的编辑": (("另一个","Other deficit-reducing edit",1),),
        }
        for stem in (FACILITY,*PLOTS):
            path=CN+"figures/"+stem+".svg"
            raw=(HERE/"figures"/(stem+".svg")).read_bytes()
            equal(raw==make_figure(stem),True,stem+" deterministic label transfer")
            a,b=parse(source(stem)),parse(raw)
            if stem==FACILITY:
                def tags(r): return r.xpath(".//s:title|.//s:desc|.//s:text",namespaces=NS)
                labels=[(str(i),u.text,v.text) for i,(u,v) in enumerate(zip(tags(a),tags(b),strict=True),1)]
            else:
                groups=a.xpath("//*[starts-with(@id,'text_')]")
                labels=[(g.get("id"),original_plot_label(g),b.xpath("//*[@id=$i]/s:text",i=g.get("id"),namespaces=NS)[0].text) for g in groups]
                old_title=a.xpath("//*[local-name()='title']")[0].text
                new_title=b.xpath("//*[local-name()='title']")[0].text
                self.digit_pairs(path,"metadata/title","metadata/title",old_title,new_title)
                if "单点" in old_title:
                    if "single-edit" not in new_title: raise ValueError("Figure title edit count")
                    self.add("figure word",path,"metadata/title","metadata/title","单点","single-edit",1)
            for id_,z,e in labels:
                self.digit_pairs(path,id_,id_,z,e)
                zs=[];es=[]
                for prefix,maps in figure_words.items():
                    if z.startswith(prefix):
                        for zp,ep,value in maps:
                            zs.append(scope(z,zp));es.append(scope(e,ep))
                            self.add("figure word",path,id_,id_,zp,ep,value)
                equal(unmasked_words(z,zs,LEXICAL_CN,WORD_CN),[],f"{stem}/{id_} Chinese figure words")
                equal(unmasked_words(e,es,("first action","first, then","person-second"),WORD_EN),[],f"{stem}/{id_} English figure words")
            def primitives(r):
                return [(node.tag,tuple(sorted(node.attrib.items()))) for node in r.xpath(
                    ".//*[self::s:path or self::s:rect or self::s:use or self::s:line or self::s:polygon]"
                    "[not(ancestor::s:g[starts-with(@id,'text_')])]",namespaces=NS)]
            equal(primitives(a),primitives(b),stem+" vector geometry")
        return self

    def tsv(self):
        s=StringIO()
        writer=csv.writer(s,delimiter="\t",lineterminator="\n")
        writer.writerow(("kind","source_commit","source_path","source_location","english_location",
                         "chinese","english","canonical_value"))
        writer.writerows(self.rows)
        return s.getvalue()

    def editorial_numbers(self):
        """Attach declared results in the claims lock and submission letters to manuscript locations."""
        article_rows=[r for r in self.rows if r[0]=="printed token" and r[2]==CN+"manuscript.md"]
        for file in [HERE/"claims-en.md",*sorted((HERE/"submission").glob("*.txt"))]:
            for n,line in lines(file.read_text(encoding="utf8")):
                for match in TOKEN.finditer(visible(line)):
                    val=spelling(match[0])
                    if val==REV:
                        self.add("revision identity",CN+"manuscript.md","Git commit",f"{file.name}:L{n}",REV,REV,REV)
                        continue
                    candidates=[r for r in article_rows if r[-1]==val]
                    if file.name=="claims-en.md" and line.startswith("| C"):
                        interval={"1":(75,99),"2":(102,121),"3":(124,134),"4":(136,154)}[line[3]]
                        local=[r for r in candidates if interval[0]<=int(r[3].split("/")[0][1:])<=interval[1]]
                        candidates=local or candidates
                    if not candidates: raise ValueError(f"Untraced editorial token {file.name}:L{n}: {match[0]}")
                    ref=candidates[0]
                    self.add("editorial token",ref[2],ref[3],f"{file.name}:L{n}@{match.start()+1}",ref[5],match[0],val)

def audit():
    inventory=Inventory()
    inventory.manuscripts()
    inventory.figures()
    inventory.editorial_numbers()
    return inventory

if __name__=="__main__":
    print(len(audit().rows),"paired occurrences")
