"""Publish scope-corrected reading editions without editing sealed originals."""
import hashlib
import html
import json
import posixpath
from pathlib import Path
import re

from qualify_study_scope import SCOPE_PATH,qualify_prose,qualify_visible_html

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'paper/preset-dispatch-scope-review-20261110'
REVIEW_NOTE='本阅读版等待用户审查，不继承原文件的交付验收。以下数据与检查点保留原时点；当前研究扩展已暂停，39r风险基线与39t时间基础先交审查，第57项草稿未执行。'


def rebase(target,old_parent,new_parent):
    if target.startswith(('http:','https:','data:','#','mailto:','javascript:')):return target
    return posixpath.relpath(posixpath.normpath(posixpath.join(old_parent,target)),new_parent)


def main():
    OUT.mkdir(parents=True,exist_ok=True);scope=json.loads(SCOPE_PATH.read_bytes())
    records=[]
    for source,filename,kind in [
        ('paper/mainline-report-20261108/report.md','report.md','md'),
        ('paper/mainline-report-20261108/AegisDC-会后研究报告.html','report.html','html'),
        ('docs/mainline/39c-joint-checkpoint-20261110.md','engineering-checkpoint.md','md'),
        ('docs/mainline/39c-cost-checkpoint-20261110.md','cost-checkpoint.md','md'),
        ('docs/mainline/39c-cost-checkpoint-20261110.html','cost-checkpoint.html','html'),
        ('docs/mainline/39c-temporal-checkpoint-20261110.md','temporal-checkpoint.md','md'),
        ('docs/mainline/39c-temporal-checkpoint-20261110.html','temporal-checkpoint.html','html'),
        ('docs/mainline/39c-review-checkpoint-20261110.md','review-checkpoint.md','md'),
        ('docs/mainline/39c-review-checkpoint-20261110.html','review-checkpoint.html','html'),
        ('docs/mainline/39c-joint-checkpoint-20261110.html','engineering-checkpoint.html','html')]:
        raw=(ROOT/source).read_bytes();text=raw.decode('utf-8');old_parent=Path(source).parent.as_posix();new_parent=OUT.relative_to(ROOT).as_posix()
        if kind=='md':
            text=qualify_prose(text)
            if filename=='report.md':text=re.sub(r'^# .*$', '# '+scope['study_name'],text,count=1,flags=re.M)
            text=re.sub(r'\]\(([^)]+)\)',lambda m:']('+rebase(m.group(1),old_parent,new_parent)+')',text)
            if filename=='report.md':text=text.replace('\n','\n\n> 主比较是两个预设策略，另有四个参照臂。验证关闭未入环、候选仅2个预设实例、无现场标定；不回答全场问题触发检查价值或全场风险基线是否成立。原180次运行及数值不改，未闭环收益下界未识别。\n',1)
            text=text.replace('\n','\n\n> '+REVIEW_NOTE+'\n',1)
        else:
            text=qualify_visible_html(text)
            if filename=='report.html':
                text=re.sub(r'<title>.*?</title>','<title>'+html.escape(scope['study_name'])+'</title>',text,count=1,flags=re.S)
                text=re.sub(r'(<h1[^>]*>).*?(</h1>)',lambda m:m.group(1)+html.escape(scope['study_name'])+m.group(2),text,count=1,flags=re.S)
                note='<section style="padding:16px;border:2px solid #0072b2;margin:16px 0"><strong>范围更正：</strong>主对照为两个预设派工策略，另保留四个参照臂。验证关闭未入环、候选仅2个预设实例、无现场标定；本比较不回答会议R1/R4的全场问题触发价值与风险基线。原180次数据不改，也未识别其为收益下界。</section>'
                text=re.sub(r'</h1>','</h1>'+note,text,count=1)
            text=re.sub(r'</h1>','</h1><p style="padding:12px;border-left:4px solid #0072b2">'+html.escape(REVIEW_NOTE)+'</p>',text,count=1)
            text=re.sub(r'\b(href|src)="([^"]+)"',lambda m:m.group(1)+'="'+rebase(m.group(2),old_parent,new_parent)+'"',text)
        output=OUT/filename;output.write_text(text,encoding='utf-8',newline='\n')
        records.append(dict(source=source,source_sha256=hashlib.sha256(raw).hexdigest(),source_unchanged=((ROOT/source).read_bytes()==raw),
            output=output.relative_to(ROOT).as_posix(),output_sha256=hashlib.sha256(output.read_bytes()).hexdigest()))
    (OUT/'sources.json').write_text(json.dumps(dict(classification='SCOPE_CORRECTED_READING_EDITION_NOT_NEW_ANALYSIS',scope=str(SCOPE_PATH.relative_to(ROOT)),
        qualifier=scope['qualifier'],records=records,authoring_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__).resolve(),ROOT/'scripts/qualify_study_scope.py',SCOPE_PATH)},
        original_registered_runs_unchanged=180,new_research_runs=0),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(editions=len(records),output=str(OUT))))


if __name__=='__main__':main()
