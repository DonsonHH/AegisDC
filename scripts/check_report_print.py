"""Inspect the existing browser printout of the self-reading report."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'.work/self-reading-check'


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(text):return ''.join(text.split()).replace('−','-').replace('—','-').replace('–','-')


def main():
    browser=json.loads((ROOT/'paper/generated/supervisor-report-verification.json').read_text(encoding='utf-8'))
    pdf=WORK/'report-print.pdf'
    assert browser['status']=='PASS' and browser['html_sha256']==digest(ROOT/'paper/supervisor-briefing.html')
    assert browser['print_pdf_sha256']==digest(pdf)
    reader=PdfReader(pdf);text=normalize('\n'.join(p.extract_text() for p in reader.pages))
    terms=['128','161','176','32MW','48023-2026','48097-2026','2027-02-01','2027-03-01',
           '450秒','455秒','0.0081','0.0656','525秒','540秒','545秒','20秒','5秒',
           '28/89','70/89','25/89','77段热异常','12段制冷异常','0.50%','下降约0.33%',
           '两本任务账','离线评分与约束审计','研究决策','项目主线摘要','原理框①','原理框②','原理框③',
           '800kJ/K','0.7604','229次','4R-1','0.05','0.20','第1周','第2周','第3周','条款原文','VAE-UNet',
           'RMSE','R²','0.484','0.462','0.424','0.401','FirstIn,FirstOut']
    missing=[v for v in terms if v not in text];assert not missing,missing
    assert '从头讲' not in text and '下一步／上一步' not in text
    renderer=shutil.which('pdftoppm');assert renderer,'Poppler pdftoppm required'
    subprocess.run([renderer,'-scale-to','1400','-png',str(pdf),str(WORK/'print')],check=True)
    pages=[]
    for number,page in enumerate(reader.pages,1):
        image=WORK/f'print-{number:0{len(str(len(reader.pages)))}d}.png'
        pages.append({'page':number,'text_characters':len(page.extract_text()),'text_start':page.extract_text()[:100],
                      'render_sha256':digest(image)})
    report={'status':'PASS','html_sha256':browser['html_sha256'],'pdf_sha256':digest(pdf),
            'checker_sha256':digest(Path(__file__)),'page_count':len(reader.pages),'verified_terms':terms,'pages':pages}
    target=ROOT/'paper/generated/supervisor-report-print-verification.json'
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    (ROOT/'paper/generated/briefing-print-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS:',len(reader.pages),'printed pages; model, risk, actual queue, constraints and paper comparisons retained.')


if __name__=='__main__':main()
