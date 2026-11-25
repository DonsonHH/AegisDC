"""Versioned wording amendment. Only its own new files may be written, never in --check mode."""
import sys
sys.dont_write_bytecode=True

import argparse
from collections import Counter
from html import escape
from html.parser import HTMLParser
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess

from readback import BASE,HERE,HYP,OWNER,PREFIX,RESULT,ROOT,SITES,T3,T4B,T6,collect,git,need,pack,sha

OLD_STAGE="stage3/"
TOKEN=re.compile(r"\{\{(old|add|ref):([^{}\n]+)\}\}")
NOTE=re.compile(r"\[([^\[\]\n]+)\]\(evidence-notes\.md#(n\d+)\)")
OLD_NOTE=re.compile(r"\[([^\[\]\n]+)\]\(stage3/evidence-notes\.md#(n\d+)\)")
NUMERIC_URL="numeric-source.html#"
BUILDER_PATH="C:/Users/Donson/.codex/skills/answer-me-with-html/scripts/am.mjs"
RENDERER_SHA="44e4610c22917cfd760e35619c394726b69e57881a3f211c2797cb973e41fa88"


def old_reader():
    path=T6/"stage3/claims_check.py"
    need(path.read_bytes()==git(BASE,PREFIX+OLD_STAGE+"claims_check.py"),"frozen original markup reader")
    spec=importlib.util.spec_from_file_location("paper_at_21a4624b",path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod


def verify_base():
    original=json.loads(git(BASE,PREFIX+"stage3/delivery.json"))
    for path,h in original["files"].items():
        b=git(BASE,path);need(sha(b)==h and (ROOT/path).read_bytes()==b,"original delivery bytes "+path)
    need((T6/"stage3/delivery.json").read_bytes()==git(BASE,PREFIX+"stage3/delivery.json"),"original delivery manifest")
    # Reuse only the sealed read-only verifiers. No facility code or estimator is imported.
    expected=git(BASE,PREFIX+"stage3/verification.txt")
    run=subprocess.run([sys.executable,"-B",str(T6/"stage3/claims_check.py"),"--check"],cwd=ROOT,capture_output=True,
                       env={**os.environ,"PYTHONIOENCODING":"utf-8"})
    need(run.returncode==0 and not run.stderr and run.stdout.replace(b"\r\n",b"\n")==expected,"original --check transcript")


def source_url(ref):
    return f"https://github.com/DonsonHH/AegisDC/blob/{ref['commit']}/{ref['path']}"+ref.get("anchor","")


def primary_map():
    return json.loads(git(BASE,PREFIX+"stage3/manuscript-numbers.json"))


def delta_table():
    return "\n".join([
        "| 比对项目 | 任务书指针 | 封存读回 | 差异 |","|---|---|---|---|",
        "| H1、H2、H3 均差及区间 | 摘要补 H1 区间；C1 补 H2、H3 区间及确认标注 | H1 −343.90 [−445.94, −244.22]；H2 −55.83 [−110.00, −11.61]；H3 −390.48 [−488.63, −292.83] 秒；均 MET | 数值无差异 |",
        "| 两站反事实机会 | 假设从 0 秒派工，50 秒可得 | 两站均如此；供评价端核实，不是必然发生的购买 | 无 |",
        "| 首条登记提示 | 伦敦 60 秒；荷兰 120 秒 | 分别为路径维护提示、复电测试提示；两站起点只有常规开工授权，未见风险触发 | 登记提示时刻无差异；若把“公开材料”解释为所有公开频道记录，荷兰此前在 90 秒已有施工未移交记录 |",
        "| 同一条件、截止前的实际购买 | 以各臂实际回执填报；证据不足写“未建立” | 两站 P 和报警响应均未取得；周期巡检均取得；V** 在 T3 无该臂，未建立 | 没有任务书预给的实际观测值；新结果不代替反事实机会 |",
        "| C4 措辞归属 | 在两种归属中据实填列 | 用户授权执行者选择；沿用选项 A | 无 |",
        "| 旧数值与状态 | 960 个原数值、135 处旧报告、全部状态和全部反例不变 | 完全一致；新增的只读观测 ID 单独列附记 | 无 |"])


def compose(ledger,old,edits):
    base_md=git(BASE,PREFIX+"manuscript.md").decode().splitlines()
    oldmap=primary_map();occ=oldmap["occurrences"];refs=dict(oldmap["qualitative_sources"])
    refs["T3Readback"]=dict(title="T3 开发原始计分与实际回执",commit=T3,path=RESULT,anchor="",sha256=sha(git(T3,RESULT)))
    orig={m["id"]:m for c in ledger["claims"] for m in c["numbers"]}
    extra={m["id"]:m for m in ledger["r3_supplement"]["numbers"]}
    metrics=orig|extra;need(len(orig)==960 and len(occ)==135 and not orig.keys() & extra.keys(),"ledger domains")
    specs={e["old_line"]:e for e in edits["edits"]}
    need(edits["base_commit"]==BASE and len(specs)==4,"four requested text loci")
    records={};changes=[];next_new=len(occ)+1;chapter=None;seen_old=[]
    md=[];html_md=[]
    def record(id,fmt,anchor,old_line,new_line,source):
        m=metrics[id];word=old.display(m,fmt);browser=NUMERIC_URL+anchor
        fields=dict(id=id,format=fmt,display=word,unit=m["unit"],signed_value=m["value"],exact=m["exact"],original_commit=m["commit"],
                    original_path=m["path"],fields=m["fields"],op=m["op"],rows=m.get("rows"),chapter=chapter,
                    base_manuscript_line=old_line,manuscript_line=new_line,kind=source,browser_ledger_url=browser)
        if source=="retained":
            prev=occ[anchor]
            for key in ("id","format","display","unit","signed_value","exact","original_commit","original_path","fields","op","rows","chapter"):
                need(fields[key]==prev[key],f"changed original number {anchor}/{key}")
            need(old_line==prev["manuscript_line"],"original placement identity")
            seen_old.append(anchor)
        need(anchor not in records,"duplicate numeric anchor");records[anchor]=fields
        return f"[{word}](evidence-notes.md#{anchor})"
    for i,line in enumerate(base_md,1):
        if line.startswith("## "):chapter=line.split(maxsplit=2)[1]
        aliases=[q[1] for q in OLD_NOTE.findall(line)]
        if i not in specs:
            def keep(m):
                q=occ[m[2]];need(m[1]==q["display"],"frozen source text")
                return record(q["id"],q["format"],m[2],i,len(md)+1,"retained")
            paragraphs=[OLD_NOTE.sub(keep,line)]
        else:
            e=specs[i];need(aliases==e["original_numeric_anchors"],"wrong original paragraph or anchors")
            need((line.startswith("**凭什么当时知道。**") if i in (161,173) else chapter in ("摘要","C1")),"section identity")
            paragraphs=[];all_old=[]
            for t in e["paragraphs"]:
                static=TOKEN.sub("",t)
                protected=old.NATIVE_NAMES.sub("",static)
                need(not re.search(r"[0-9０-９]",protected) and "{{" not in static and "}}" not in static,"unbound literal in edited paragraph: "+t[:80])
                lineno=len(md)+len(paragraphs)+1
                def substitute(match):
                    nonlocal next_new
                    tag,arg=match.groups()
                    if tag=="old":
                        q=occ[arg];all_old.append(arg)
                        return record(q["id"],q["format"],arg,i,lineno,"retained")
                    if tag=="ref":
                        r=refs[arg];return f" [{r['title']}]({source_url(r)})"
                    id,fmt=arg.rsplit(":",1);need(id in metrics,"missing new value ID: "+id)
                    a=f"n{next_new:03}";next_new+=1
                    return record(id,fmt,a,i,lineno,"additional")
                paragraphs.append(TOKEN.sub(substitute,t));paragraphs.append("")
            paragraphs.pop()
            need(all_old==aliases,f"lost/reordered an old printed number at line {i}")
            changes.append(dict(label=e["label"],source_path=PREFIX+"manuscript.md",source_commit=BASE,
                                source_line=i,new_lines=[len(md)+1,len(md)+len(paragraphs)],old_text=line,new_text="\n".join(paragraphs),
                                unchanged_numeric_anchors=aliases))
        for p in paragraphs:
            md.append(p)
            html_md.append(NOTE.sub(lambda q:f"[{q[1]}]({NUMERIC_URL+q[2]})",p))
    need(seen_old==list(occ),"original 135 identities and text-order are unchanged")
    manuscript="\n".join(md)+"\n";htext="\n".join(html_md)+"\n"
    # The original checker scans scientific literals separately from model and condition identifiers.
    old.check_literal_hygiene(manuscript.replace("](evidence-notes.md#","](stage3/evidence-notes.md#"))
    matched=NOTE.findall(manuscript)
    need([(q["display"],a) for a,q in records.items()]==matched,"all displayed quantitative values in source order")
    need(not any("{{" in p or "}}" in p for p in md),"unexpanded source markers")
    need("H2（确认，MET）" in manuscript and "H3（确认，MET）" in manuscript and
         "预注册 H1 确认检验" in md[changes[0]["new_lines"][0]-1],"confirmation labels in requested sections")
    for change in changes[-2:]:
        need("反事实可买机会" in change["new_text"] and "没有公开风险触发" in change["new_text"] and "没有 V\\*\\* 臂" in change["new_text"] and
             "未建立" in change["new_text"] and "实际回执" in change["new_text"],"two-site source/actual separation")
    return manuscript,old.html_draft(htext),records,changes,refs


def evidence_pages(ledger,records):
    metrics={m["id"]:m for c in ledger["claims"] for m in c["numbers"]}
    metrics.update({m["id"]:m for m in ledger["r3_supplement"]["numbers"]})
    notes=["# 正文数字索引 · r3","","[返回正文](manuscript.md) · [当前完整台账](claims.json) · [逐次映射](manuscript-numbers.json)",""]
    # Standalone source table with stable local HTML fragments, including newly added observations.
    page=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
          '<title>r3　正文数字来源</title><main><h1>正文数字来源</h1>',
          '<p><a href="manuscript.html">返回正文</a> · <a href="claims.json">机器台账</a> · <a href="manuscript-numbers.json">逐次定位</a></p>',
          '<table><thead><tr><th>位置／正文值</th><th>台账 ID 与含义</th><th>封存来源</th></tr></thead><tbody>']
    for a,q in records.items():
        m=metrics[q["id"]];url=f"https://github.com/DonsonHH/AegisDC/blob/{m['commit']}/{m['path']}"
        detail=", ".join(m["fields"]);idx="; rows="+str(m["rows"]) if "rows" in m else ""
        expanded=detail+idx
        notes.extend([f'<a id="{a}"></a>',f"**{q['display']}** · {m['label']}（{m['unit']}）。ID：{m['id']}。"
                    f" [封存文件 {m['commit'][:8]}]({url})；字段：{expanded}；原值：{m['exact']}；运算：{m['op']}。",""])
        page+= [f'<tr id="{a}"><td>{a} · {escape(q["display"])} {escape(m["unit"])}</td>'
                f'<td><code>{escape(m["id"])}</code><br>{escape(m["label"])}</td>'
                f'<td><a href="{escape(url,quote=True)}">{m["commit"][:8]} · {escape(m["path"])}</a><br>'
                f'<code>{escape(expanded)}</code><br>{escape(m["op"])}；原值 {escape(str(m["exact"]))}</td></tr>']
    return "\n".join(notes).rstrip()+"\n","\n".join(page+["</tbody></table></main></html>"])+"\n"


def changes_markdown(changes):
    lines=["# 修订 r3 的变更行与差异","","基线 21a4624b。下列为正文实质变更；其余行只将相对数字链接指向本版数字索引。所有原有位置的 ID、值、显示及次序保持不变。","",
           "| 正文位置 | 原行 | r3 行（含新增段落） | 原数字锚点 |","|---|---:|---|---|"]
    for c in changes:
        a,b=c["new_lines"];lines.append(f"| {c['label']} | {c['source_line']} | {a}–{b} | {', '.join(c['unchanged_numeric_anchors'])} |")
    lines+=["","C4 署名字段：/claims/3/wording_owner 改为“用户授权执行者选择”。选项仍为 A；statement、status、反例和 numbers 不变。"
           "全部 960 个原始 numbers 条目逐字段保留，新观测仅列在 r3_supplement。","","## 与任务书参考值的差异","",delta_table(),"",
            "[逐字变更记录](changed-lines.json) · [原始输入及分臂回执定位](claims.json) · [核验输出](verification.txt)。"]
    return "\n".join(lines)+"\n"


def outputs(old):
    ledger=collect();edits=json.loads((HERE/"revision-edits.json").read_bytes())
    md,draft,records,changes,refs=compose(ledger,old,edits)
    note,browser=evidence_pages(ledger,records)
    fullmap=dict(schema="aegisdc-stage3-r3-number-map",reviewed=BASE,ledger="claims.json",occurrences=records,
                 original_occurrences=135,new_occurrences=len(records)-135,qualitative_sources=refs)
    prior=json.loads(git(BASE,PREFIX+"stage3/claims.json"))
    old_lines=git(BASE,PREFIX+"stage3/claims.json").decode().splitlines()
    new_lines=pack(ledger).decode().splitlines()
    def owner_line(lines):
        return next(i for i,line in enumerate(lines,1) if '"wording_owner":' in line)
    diff=dict(base=BASE,lines_one_based=True,substantive_changes=changes,source_file=PREFIX+"manuscript.md",
        output_file=PREFIX+"r3/manuscript.md",remaining_line_changes="Relative numeric backlink targets rebound for r3 only.",
        ledger_owner=dict(pointer="/claims/3/wording_owner",old_line=owner_line(old_lines),new_line=owner_line(new_lines),
                          old_value=prior["claims"][3]["wording_owner"],new_value=ledger["claims"][3]["wording_owner"]),
        ledger_addition=dict(pointer="/r3_supplement",additive_metric_ids=[x["id"] for x in ledger["r3_supplement"]["numbers"]]))
    return ledger,records,{"manuscript.md":md.encode(),"review-draft.md":draft.encode(),"claims.json":pack(ledger),
            "manuscript-numbers.json":pack(fullmap),"evidence-notes.md":note.encode(),"numeric-source.html":browser.encode(),
            "changed-lines.json":pack(diff),"changes.md":changes_markdown(changes).encode()}


class Notes(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.table={};self.current=None
    def handle_starttag(self,tag,attrs):
        if tag=="tr":
            self.current=dict(attrs).get("id")
            if self.current:need(self.current not in self.table,"duplicate numeric HTML anchor");self.table[self.current]=["",[]]
        if tag=="a" and self.current:self.table[self.current][1].append(dict(attrs)["href"])
    def handle_endtag(self,tag):
        if tag=="tr":self.current=None
    def handle_data(self,txt):
        if self.current:self.table[self.current][0]+=txt


def check_surfaces(old,files,records):
    md=files["manuscript.md"].decode();browser=(HERE/"manuscript.html").read_text(encoding="utf8")
    parser=old.Panels();parser.feed(browser);parser.close()
    must=old.expected_blocks(md)
    norm=lambda s:" ".join(s.split())
    need(len(parser.groups)==len(must)==7 and [[(t,norm(v)) for t,v in g] for g in parser.groups]==must,
         "full visible HTML: all headings, paragraphs, limitations and table cells of the revised manuscript")
    to_browser={f"evidence-notes.md#{a}":q["browser_ledger_url"] for a,q in records.items()}
    links=[(to_browser.get(url,url),old.plain_inline(name)) for name,url in old.LINK.findall(md)]
    need(parser.links==links,"exact scientific and evidence links, not just presence of numbers")
    notes=Notes();notes.feed(files["numeric-source.html"].decode());notes.close()
    ordered=[a for a in records]
    need(list(notes.table)==ordered and re.findall(r'<a id="(n\d+)"></a>',files["evidence-notes.md"].decode())==ordered,"both evidence surfaces")
    for a,q in records.items():
        t,urls=notes.table[a]
        need(q["id"] in t and q["display"] in t and q["exact"] in t and all(v in t for v in q["fields"]) and
             urls==[f"https://github.com/DonsonHH/AegisDC/blob/{q['original_commit']}/{q['original_path']}"],"source note identity "+a)


def log(ledger,records):
    s=ledger["r3_supplement"];old=[r for r in records.values() if r["kind"]=="retained"]
    lines=["Reviewed stage3 (21a4624b), r2 and stage2 baseline --check: PASS. No original file modified.",
        f"Original: {sum(len(c['numbers']) for c in ledger['claims'])}/960 numeric entries, all claim statuses and counterexamples, {len(old)}/135 numeric occurrences preserved.",
        f"r3: {len(s['numbers'])} additional evidence IDs; {len(records)-len(old)} additional printed occurrences; {len(records)} total.",
        "T4b H1/H2/H3: preregistered confirmation, MET/MET/MET; means and interval endpoints verified in original order.",
        "T3: paid opportunity (dispatch 0, potential arrival 50); first registered prior London 60, Netherlands 120; no risk trigger at dispatch. Dutch WORK_OPEN arrived at 90.",
        "5-01 / deadline 720: PERIODIC first LC::I at 50, LB::I at 110; P and ALARM no paid receipt before deadline; V_COST absent (not established).",
        "6-02 / deadline 540: PERIODIC first NR::I at 50, NP::I at 230; P and ALARM no paid receipt before deadline; V_COST absent (not established).",
        "C4 wording_owner=用户授权执行者选择; option A retained; all original statements and statuses unchanged.",
        "Markdown, visible HTML, each numeric link, bindings, change list and task/reference differences: PASS.",
        "Facility calls=0; Slurm jobs=0; H2 seed generated/read/derived=0. STOP FOR REVIEW."]
    return "\n".join(lines)+"\n"


def main():
    p=argparse.ArgumentParser(description=__doc__)
    g=p.add_mutually_exclusive_group(required=True)
    for opt in ("build","seal","check"):g.add_argument("--"+opt,action="store_true")
    a=p.parse_args();verify_base();old=old_reader()
    ledger,records,files=outputs(old)
    if a.build:
        for name,raw in files.items():(HERE/name).write_bytes(raw)
        return
    for name,raw in files.items():need((HERE/name).read_bytes()==raw,"actual delivery record: "+name)
    check_surfaces(old,files,records)
    transcript=log(ledger,records).encode("utf-8")
    if a.seal:(HERE/"verification.txt").write_bytes(transcript)
    else:need((HERE/"verification.txt").read_bytes()==transcript,"full read-only verification output")
    members=[*files,"manuscript.html","verification.txt","claims_check.py","readback.py","revision-edits.json","README.md"]
    manifest=dict(schema="t6-stage3-wording-r3",baseline=BASE,durable_files={n:sha((HERE/n).read_bytes()) for n in members},
        changes="changed-lines.json",reference_differences="changes.md",render=dict(tool="answer-me-with-html",version="0.6.4",
         cli_sha256=RENDERER_SHA,scope="offline presentation only",input="review-draft.md",output="manuscript.html",eol="LF"),
        original_numeric_entries=960,original_numeric_occurrences=135,roles_measured=["P","PERIODIC","ALARM"],V_COST_on_these_T3_conditions="未建立",
        option="A",wording_owner=OWNER,facility_calls=0,slurm_jobs=0,H2_generated=0,H2_read=0,H2_derived=0,status="DELIVERED_PENDING_REVIEW")
    if a.seal:(HERE/"delivery.json").write_bytes(pack(manifest))
    else:need((HERE/"delivery.json").read_bytes()==pack(manifest),"r3 delivery manifest")
    print(transcript.decode(),end="")


if __name__=="__main__":
    sys.stdout.reconfigure(encoding="utf-8");main()
