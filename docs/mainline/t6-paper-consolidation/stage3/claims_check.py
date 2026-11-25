"""T6 paper and r2 ledger readback. Python standard library and immutable git show only."""
import sys
sys.dont_write_bytecode = True

import argparse
from collections import Counter
from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import re
import subprocess

HERE=Path(__file__).resolve().parent
T6=HERE.parent
ROOT=T6.parents[2]
PREFIX=T6.relative_to(ROOT).as_posix()+"/"
ACCEPTED="0ca350d1cb54ecc20fd99db5d69167d886cdef34"
R2="6fe021c85af6f506802c2d12c1b477f2b7a03ed1"
INPUTS=("opening.md.in","comparison-chapter.md.in","incident-chapter.md.in","improvement-chapter.md.in","rsi-chapter.md.in","advisor-questions.md.in")
OUTPUT_MD=T6/"manuscript.md"
STAGE2_PATH="r2/claims.json"
LEDGER_LINK="stage3/claims.json"
USER_SCOPE_A="在该合成发生器范围内，依据现有比较，RSI 相对同预算普通改进或固定父、子的独立服务增量不可辨识；这项判断不外推到真实设施。"
REFS={
    "Facility":("完整设施的方法和公开证据边界",ACCEPTED,"docs/mainline/full-facility-method-handoff.md","#L11"),
    "T4bProtocol":("T4b 预注册检验及对照", "3487276af9e9759357771d16eb45feceaa3c948a","docs/mainline/t4d-cost-baseline-v1/confirmation-protocol-v2.md","#L7-L17"),
    "T4b":("T4b 留出结果","3487276af9e9759357771d16eb45feceaa3c948a","docs/mainline/t4b-holdout-confirmation-v2/README.md",""),
    "T4d":("成本基线的原开发板","036ccfdf2d6e5d4b39ba11da480fa2a3d69c1f9f","docs/mainline/t4d-cost-baseline-v1/README.md",""),
    "T3":("事故族与事前证据的开发记录","85af7e48b60e61dc453456b5b7bc73ab832900b5","docs/mainline/t3-prior-information-v2/README.md",""),
    "LondonReport":("伦敦事故官方复盘定位","85af7e48b60e61dc453456b5b7bc73ab832900b5","docs/mainline/review-gated/R1/sources.md","#L18-L32"),
    "DutchReport":("荷兰事故官方复盘定位","85af7e48b60e61dc453456b5b7bc73ab832900b5","docs/mainline/review-gated/R1/sources.md","#L34-L43"),
    "R6":("伦敦维护降级 PRE 的有限证据","84eaa73d8e1365abd1ff1b8f6c0b83d01470bd69","docs/mainline/review-gated/R6/london-pre-manuscript-v1.3/claim-evidence-matrix.md",""),
    "V6first":("完整设施的原生首片比较","ec1e37475360dd5025d8571f04fa75253c67f33e","docs/mainline/v6-native-method-study-v1/README.md",""),
    "V6cold":("完整设施的联合冷态比较","b867628f1d0cd1a8355b9d5e4394bce9b12bd992","docs/mainline/v6-stage-three-cold-study-v2/README.md",""),
    "T5v1":("人工锚点的归因更正","0e89b678c7da4b3060d364d3625bd66952ff113f","docs/mainline/t5-ordinary-improvement-development-v2/manual-references.json",""),
    "T5v2":("无锚点开发结果","0e89b678c7da4b3060d364d3625bd66952ff113f","docs/mainline/t5-ordinary-improvement-development-v2/README.md",""),
    "T5v3a":("候选空间的开发诊断","29ac5a2eac2e6527cbfd04145b0caa2c9206c09e","docs/mainline/t5-landscape-diagnostic-v3a/README.md",""),
    "T5v3b":("分块重组的开发门槛","9360a3c8f9c06f4b85f4706ef529c2fc4ef811a3","docs/mainline/t5-block-recombination-v3b/README.md",""),
    "T5v3cDev":("公开选择器的旧板开发","25f86d8c7de5cad37e6b47d01a4991f161db0539","docs/mainline/t5-observable-selector-v3c/development-report.md",""),
    "T5v3cNew":("公开选择器的新板确认","87cdd7183970a7787616c666246b38b9fce8320b","docs/mainline/t5-observable-selector-v3c/README.md",""),
    "C4Readback":("固定向量和逐条件最小值的复算","383c00c3137958dd146d784a6e6251dbe9e603e7",PREFIX+"README.md",""),
    "Closeout":("实际处置与严格劣行","ce3ee6303a81f99341d40796d499185e997238da","docs/mainline/t5-closeout/README.md","#L9"),
}
SLOTS=re.compile(r"\{\{([^{}\n]+)\}\}")
LABEL=re.compile(r"^C[1-4]$")
ALLOWED_TERMS={"R6","V6","PRE","C1","C2","C3","C4","T3","T4b","T4d","T5","T6","H1","H2","H3","v1","v1.3","v2","v3a","v3b","v3c","V1","V2"}
QHEAD=("识别了什么","凭什么当时知道","能采取什么行动","是否来得及","额外收益从何而来")


def require(ok,msg):
    if not ok:raise ValueError("manuscript: "+msg)


def packed(obj):
    return (json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+"\n").encode("utf8")


def digest(b):return hashlib.sha256(b).hexdigest()


def git(rev,path):
    return subprocess.check_output(["git","-C",str(ROOT),"show",rev+":"+path])


def text(path):return path.read_bytes().decode("utf8")


def validate_revision():
    """Bind the r2 reader and its outputs before using them as the current ledger."""
    folder=T6/"r2"
    for f in ("claims_check.py","README.md","claims.json","delivery.json","verification.txt"):
        require((folder/f).read_bytes()==git(R2,PREFIX+"r2/"+f),"frozen r2 source "+f)
    spec=importlib.util.spec_from_file_location("t6_r2_verified",folder/"claims_check.py")
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    require(mod.run(True)==text(folder/"verification.txt"),"validated H1 and r2 transcript")
    # Accepted complete checker runs at its original version; the import occurs in that process only.
    proc=subprocess.run([sys.executable,"-B",str(T6/"claims_check.py"),"--check"],cwd=ROOT,capture_output=True)
    require(proc.returncode==0 and proc.stdout.replace(b"\r\n",b"\n")==git(ACCEPTED,PREFIX+"claims-verification.txt"),
            "stage-2 original numeric-source verification: "+proc.stderr.decode("utf8",errors="replace"))
    return json.loads(git(R2,PREFIX+STAGE2_PATH))


def apply_decision(ledger):
    """Set the identification statement without turning it into an affirmative RSI claim."""
    import copy
    result=copy.deepcopy(ledger);c4=result["claims"][3]
    require(c4["id"]=="C4" and c4["status"]=="未建立" and c4["statement"]=="","r2 pending wording")
    c4["statement"]=USER_SCOPE_A
    c4["wording_owner"]="用户授权执行者在 A 与 B 中选择；阶段 3 选择 A。未建立的是 RSI 的独立增量。"
    result["stage3_decision"]=dict(option="A",baseline=R2,scope="事后条件化余量与可部署的 RSI 对照分开；不外推到真实设施。",
        changed_C4_fields=["/claims/3/statement","/claims/3/wording_owner"],no_change_to_C4_status=True,research_numbers_added=0)
    require(result["claims"][:3]==ledger["claims"][:3] and c4["numbers"]==ledger["claims"][3]["numbers"],"wording cannot alter evidence")
    return result


def display(metric,fmt):
    exact=Fraction(metric["exact"])
    require(metric["value"]==(int(exact) if exact.denominator==1 else float(exact)),"stored numeric identity "+metric["id"])
    with localcontext() as ctx:
        ctx.prec=90;v=Decimal(exact.numerator)/Decimal(exact.denominator)
        if fmt=="i":
            require(exact.denominator==1,"nonintegral count "+metric["id"])
            return str(exact.numerator).replace("-","−")
        if fmt in ("pct2","pp2"):
            require(metric["unit"]==("比例" if fmt=="pct2" else "比例差"),"percentage unit "+metric["id"])
            return f"{v*100:.2f}".replace("-","−")+("%" if fmt=="pct2" else " 个百分点")
        m=re.fullmatch(r"(d|s|abs)([0-3])",fmt)
        require(m,"invalid rendering "+fmt)
        if m[1]=="abs":
            require(v<=0,"absolute reduction grammar only for negative values: "+metric["id"]);v=abs(v)
        return format(v,("+" if m[1]=="s" and v else "")+"."+m[2]+"f").replace("-","−")


def contains_id(label,ledger_text):
    return (label in ALLOWED_TERMS or label in ("B_cost","V**","V_COST","B_COST","RSI","U","R","S","W") or
            (bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*",label)) and
             not re.fullmatch(r"[\d.]+",label) and re.search(r"(?<![0-9A-Za-z-])"+re.escape(label)+r"(?![0-9A-Za-z-])",ledger_text) is not None))


def narrative(ledger):
    metrics={m["id"]:m for c in ledger["claims"] for m in c["numbers"]}
    require(len(metrics)==sum(len(c["numbers"]) for c in ledger["claims"]),"unique metric IDs")
    serialized=json.dumps(ledger,ensure_ascii=False)
    lines=[];preview=[];occurrences=[];labels=[];references={};part="";heads=[];site=None;helps={}
    for name in INPUTS:
        if lines:lines.append("");preview.append("")
        for no,line in enumerate(text(HERE/name).splitlines(),1):
            if line.startswith("## "):
                part=line.split(maxsplit=2)[1];heads.append((part,len(lines)+1));site=None
            elif part=="导师五问" and line.startswith("### "):
                site=line.removeprefix("### ");helps[site]=[]
            if part=="导师五问" and site and line.startswith("**"):
                q=re.match(r"^\*\*(.*?)。\*\*",line);require(q,"question paragraph")
                helps[site].append((q[1],line))
            static=SLOTS.sub("",line)
            if line.startswith("## ") and LABEL.fullmatch(part):static=static.replace("## "+part+" ","",1)
            require(not re.search(r"[0-9０-９]",static),f"{name}:{no}: numeric literal/identifier without ledger binding: "+static[:150])
            require("{{" not in static and "}}" not in static,f"{name}:{no}: malformed marker")
            a=[];b=[];pos=0
            for mt in SLOTS.finditer(line):
                a.append(line[pos:mt.start()]);b.append(line[pos:mt.start()]);pos=mt.end()
                tag,*args=mt[1].split("|")
                if tag=="metric":
                    require(len(args)==2 and args[0] in metrics,f"{name}:{no}: unknown metric "+str(args))
                    id,fmt=args;m=metrics[id];word=display(m,fmt)
                    require(part not in ("C1","C2","C3","C4") or id.startswith(part+".") or
                            (part=="C1" and id=="C2.T4b.NETHERLANDS.window_missed"),"unexpected cross-chapter metric "+id)
                    idx=len(occurrences)+1;anchor=f"n{idx:03}"
                    a.append(f"[{word}](stage3/evidence-notes.md#{anchor})");b.append(word)
                    occurrences.append(dict(anchor=anchor,chapter=part or "front",template=name,template_line=no,manuscript_line=len(lines)+1,
                          id=id,display=word,format=fmt,signed_value=m["value"],exact=m["exact"],unit=m["unit"],original_commit=m["commit"],
                          original_path=m["path"],fields=m["fields"],op=m["op"],rows=m.get("rows")))
                elif tag=="name":
                    require(len(args)==1 and contains_id(args[0],serialized),f"{name}:{no}: unknown name "+str(args))
                    shown={"V_COST":"V\\*\\*","B_COST":"B_cost"}.get(args[0],args[0])
                    a.append(shown);b.append(shown);labels.append(dict(line=len(lines)+1,identifier=args[0],display=shown))
                elif tag=="ref":
                    require(len(args)==1 and args[0] in REFS,f"{name}:{no}: unknown source")
                    key=args[0];label,rev,path,frag=REFS[key]
                    if key not in references:
                        raw=git(rev,path)
                        if frag:
                            nums=list(map(int,re.findall(r"\d+",frag)))
                            require(nums and max(nums)<=len(raw.splitlines()),"invalid citation lines "+key)
                        references[key]=dict(title=label,commit=rev,path=path,anchor=frag,sha256=digest(raw))
                    link=f" [{label}](https://github.com/DonsonHH/AegisDC/blob/{rev}/{path}{frag})"
                    a.append(link);b.append(link)
                else:raise ValueError("unrecognized manuscript token "+tag)
            a.append(line[pos:]);b.append(line[pos:]);lines.append("".join(a));preview.append("".join(b))
    required=["摘要","研究问题与计量","C1","C2","C3","C4","导师五问"]
    require([k for k,_ in heads]==required,"section ordering")
    for h,lo in heads[2:6]:
        following=next(start for _,start in heads if start>lo)
        section=lines[lo-1:following-1]
        require([q for q in section if q.startswith("### ")]==["### 结论","### 数字","### 失效条件与反例"],"chapter order "+h)
        chunks="\n".join(section).split("### 失效条件与反例")
        require("stage3/evidence-notes.md#" in chunks[-1] and len(section)>10,"same-section sourced counterexample "+h)
    require(list(helps)==["伦敦","荷兰"] and all(tuple(q for q,_ in a)==QHEAD for a in helps.values()),"five questions in both sites")
    for name,a in helps.items():
        require(all("未建立" in line for q,line in a if q!="识别了什么"),"explicit historical identification limit for unresolved site questions "+name)
    requirement={"C1":{"C1.T4b.H1.mean","C1.T4b.H1.lo","C1.T4b.H1.hi","C1.T4b.ALL.B.worse","C1.T4b.NETHERLANDS.B.worse",
                       "C1.T4b.COOLING_ACCESS.PERIODIC.loss_mean","C1.T4b.COOLING_ACCESS.PERIODIC.staff_delta","C1.v3c.ALL.B_COST.loss_mean"},
                 "C4":{"C4.fixed54.best","C4.fixed54.posthoc","C4.fixed54.conditional_room","C4.new.attained","C4.new.n","C4.new.room"}}
    for h,must in requirement.items():
        actual={q["id"] for q in occurrences if q["chapter"]==h}
        require(must<=actual,"mandatory metric bindings "+h+": "+str(must-actual))
    actual="\n".join(lines)+"\n"
    require("在该合成发生器范围内" in actual and "不可辨识" in actual and "非可部署策略" in actual and "RSI 无效" not in actual,"user-delegated option A")
    return actual,"\n".join(preview)+"\n",occurrences,labels,references


def notes_for(metrics,occurrences):
    out=["# 正文数字索引","","每个锚点对应正文中的一次定量报告。原值保留为整数或精确分数；“减少”可将负差写为减少的正数。"
         "重复使用同一指标时，分别记录出现位置。","","[返回正文](../manuscript.md) · [本版台账](claims.json)",""]
    for q in occurrences:
        m=metrics[q["id"]];url="https://github.com/DonsonHH/AegisDC/blob/"+m["commit"]+"/"+m["path"]
        out+= [f'<a id="{q["anchor"]}"></a>',
               f'**{q["display"]}** · {m["label"]} · {m["unit"]}。ID：<code>{m["id"]}</code>。'
               f' [原件 {m["commit"][:8]}]({url})；原值 {m["exact"]}；运算 {m["op"]}。'
               f' 具体字段及源行见[数字映射](manuscript-numbers.json)中的 {q["anchor"]}。','']
    return "\n".join(out).rstrip()+"\n"


def html_draft(body):
    lines=body.splitlines();title=lines.pop(0).removeprefix("# ")
    htmlrows=["---","title: "+title,"file: t6-manuscript","template: doc","theme: paper","lang: zh","---"]
    i=0
    for line in lines:
        if line.startswith("## "):line="## "+chr(65+i)+" "+line[3:];i+=1
        htmlrows.append(line)
    return "\n".join(htmlrows)+"\n"


class Panels(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.panels=[];self.current=None;self.depth=0;self.ignored=0
    def handle_starttag(self,t,a):
        if t in ("script","style","template"):self.ignored+=1;return
        if self.ignored:return
        if t=="section":
            if self.current is not None:self.depth+=1
            elif "am-panel" in dict(a).get("class","").split():self.current=[];self.depth=1
    def handle_endtag(self,t):
        if t in ("script","style","template"):self.ignored-=1;return
        if self.ignored:return
        if t=="section" and self.current is not None:
            self.depth-=1
            if self.depth==0:self.panels.append(" ".join(self.current));self.current=None
    def handle_data(self,data):
        if not self.ignored and self.current is not None:self.current.append(data)


def check_visible(markup,occurrences):
    parser=Panels();parser.feed(markup);parser.close()
    require(len(parser.panels)==7,"seven visible sections, four undivided chapter panels")
    order=["摘要","研究问题与计量","C1","C2","C3","C4","导师五问"]
    for k,p in zip(order,parser.panels,strict=True):
        require(k in p,"HTML chapter "+k)
        if k in ("C1","C2","C3","C4"):
            tags=("结论","数字","失效条件与反例")
            require(all(t in p for t in tags) and [p.index(t) for t in tags]==sorted(p.index(t) for t in tags),"same visible panel for conclusion, numbers, counterexamples")
        if k=="导师五问":
            require(all(p.count(q)>=2 for q in QHEAD) and "伦敦" in p and "荷兰" in p,"two sites and five visible answers")
        pos=0
        for word in [q["display"] for q in occurrences if q["chapter"]==k]:
            i=p.find(word,pos);require(i>=0,f"visible {k} lost a numeric display in source order: {word}");pos=i+len(word)


def outputs():
    data=apply_decision(validate_revision())
    md,plain,occurrences,labels,refs=narrative(data)
    metrics={m["id"]:m for c in data["claims"] for m in c["numbers"]}
    reg=dict(schema="t6-manuscript-numeric-concordance-v1",corrected_ledger=LEDGER_LINK,
             historical_numeric_baseline=ACCEPTED,r2_publication=R2,measurement_unit="one displayed numeric occurrence",
             occurrences={q["anchor"]:q for q in occurrences},identifiers=labels,qualitative_sources=refs,
             chapters=dict(C1="T4b whole-board H1 confirmed; family and labour readbacks descriptive",
                           C2="historical review, synthetic development, holdout strata and disclosed V6 panels distinguished",
                           C3="old-board development versus new-panel preregistered confirmation",C4="A: identification boundary, not a measured RSI effect"))
    files={OUTPUT_MD:md.encode(),HERE/"claims.json":packed(data),HERE/"manuscript-numbers.json":packed(reg),
           HERE/"evidence-notes.md":notes_for(metrics,occurrences).encode(),HERE/"review-draft.md":html_draft(plain).encode()}
    return files,data,occurrences,refs


def log_for(data,occ,refs):
    by=Counter(q["chapter"] for q in occ)
    return "\n".join([
        "Accepted stage 2 (0ca350d1): original --check passed; original claims.json and delivery files unchanged.",
        "r2 (6fe021c8): H1=MET => C1.B=成立, 确认, whole-board mean only. C1=部分成立; 14 B loss rows including 10 Dutch retained.",
        f"Current ledger: {sum(len(c['numbers']) for c in data['claims'])} original numeric entries unchanged; C4 uses option A; RSI increment status remains 未建立.",
        f"Manuscript: {len(occ)} numeric occurrences / {len({q['id'] for q in occ})} distinct metric IDs resolved to commits, files, fields and displays.",
        "Numeric occurrences by section: "+"; ".join(f"{s}={by[s]}" for s in ("摘要","研究问题与计量","C1","C2","C3","C4","导师五问"))+".",
        f"Sources: {len(refs)} qualitative references checked. Each claim chapter keeps its conclusion, numbers and counterexamples together.",
        "Advisor questions: London 5/5; Netherlands 5/5. Historical unknowns and conditional synthetic results kept separate.",
        "C4: 82.03 s fixed; 0.00 s hindsight (not deployable); old conditional room 82.03 s; new W at bound 36/36, room 0.00 s. No field extrapolation.",
        "Manuscript and visible HTML agree. Facility=0; Slurm=0; H2 generated/read/derived=0. STOP FOR REVIEW."
    ])+"\n"


def command():
    cli=argparse.ArgumentParser(description=__doc__);mode=cli.add_mutually_exclusive_group(required=True)
    for name in ("build","seal","check"):mode.add_argument("--"+name,action="store_true")
    arg=cli.parse_args()
    files,data,occ,refs=outputs()
    if arg.build:
        for p,b in files.items():p.write_bytes(b)
        return
    for p,b in files.items():require(p.read_bytes()==b,"recorded generated artifact differs: "+str(p.name))
    check_visible(text(T6/"manuscript.html"),occ)
    md=files[OUTPUT_MD].decode();notes=files[HERE/"evidence-notes.md"].decode()
    require(re.findall(r"\]\(stage3/evidence-notes.md#(n\d+)\)",md)==[q["anchor"] for q in occ] and
            re.findall(r'<a id="(n\d+)"></a>',notes)==[q["anchor"] for q in occ],"each numeric link has a unique corresponding note")
    transcript=log_for(data,occ,refs)
    if arg.seal:(HERE/"verification.txt").write_bytes(transcript.encode())
    else:require((HERE/"verification.txt").read_bytes()==transcript.encode(),"full check transcript")
    allfiles=[*files,T6/"manuscript.html",*(HERE/n for n in INPUTS),HERE/"claims_check.py",HERE/"verification.txt",HERE/"README.md"]
    manifest=dict(schema="t6-manuscript-v1",baseline=ACCEPTED,r2=R2,C4_decision="A (choice delegated by user)",C4_status="未建立",
                  manuscript=OUTPUT_MD.relative_to(ROOT).as_posix(),ledger=(HERE/"claims.json").relative_to(ROOT).as_posix(),
                  stage2_tree_untouched=True,amendment_files_untouched=True,files={p.relative_to(ROOT).as_posix():digest(p.read_bytes()) for p in allfiles},
                  renderer=dict(name="answer-me-with-html",version="0.6.4",cli_sha256="44e4610c22917cfd760e35619c394726b69e57881a3f211c2797cb973e41fa88",
                                use="offline presentation only; scientific readback uses Python standard library and git show"),
                  conclusion="DELIVERED_FOR_REVIEW",facility_calls=0,slurm_jobs=0,H2_generated=0,H2_read=0,H2_derived=0,next_stage_authorized=False)
    if arg.seal:(HERE/"delivery.json").write_bytes(packed(manifest))
    else:require((HERE/"delivery.json").read_bytes()==packed(manifest),"manuscript durable file identities")
    print(transcript,end="")


if __name__=="__main__":command()
