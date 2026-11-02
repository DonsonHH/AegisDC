"""Read and render the browser's print output; never run the research model."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '.work/briefing-v3-browser'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(text):
    return ''.join(text.split()).replace('−', '-').replace('—', '-').replace('–', '-')


def main():
    browser = json.loads((ROOT / 'paper/generated/briefing-browser-verification.json').read_text(encoding='utf-8'))
    pdf = WORK / 'complete-print.pdf'
    assert browser['status'] == 'PASS'
    assert browser['html_sha256'] == digest(ROOT / 'paper/supervisor-briefing.html')
    assert browser['print_pdf_sha256'] == digest(pdf)
    reader = PdfReader(pdf)
    assert len(reader.pages) == 5, 'Expected one complete printed page for each screen'
    required = [
        ['645', '885', '680', '705', '240', '300', '25', '事后', '128', '18'],
        ['A', 'B', 'C', '确认X', '未通过', '原巡回', '返回证书'],
        ['28/89', '70/89', '25/89', '净增42', '+0.50%', '-0.33%', '12', '89', '等实际成本'],
        ['11@605', '9@620', '17@645', '21@695', '23@635', '9@665', '17@690', '21@725',
         '665派出例行检查', '685风险提示', '650风险提示', '705额外派单', '725正常', '650-710', '不能把全部差异'],
        ['机制已实现', '条件性证明', '实验已完成', '初稿已整理', '28-60', 'FIFO70', 'RSI',
         '独立收益尚未证明', '当前机制能否独立成稿', '最关键的直接比较'],
    ]
    pages = []
    for number, (page, terms) in enumerate(zip(reader.pages, required), 1):
        text = normalize(page.extract_text())
        assert all(term in text for term in terms), (number, [term for term in terms if term not in text])
        assert '上一步' not in text and '从头讲' not in text, 'Printed interaction controls'
        pages.append({'page': number, 'required_fragments_verified': terms})
    renderer = shutil.which('pdftoppm')
    if not renderer:
        raise RuntimeError('Poppler pdftoppm is required for the visual print check')
    subprocess.run([renderer, '-scale-to', '1400', '-png', str(pdf), str(WORK / 'print')], check=True)
    for page in pages:
        page['render_sha256'] = digest(WORK / f"print-{page['page']}.png")
    report = {'status': 'PASS', 'html_sha256': browser['html_sha256'],
              'checker_sha256': digest(Path(__file__)),
              'pdf_sha256': digest(pdf), 'pages': pages, 'page_count': 5,
              'scope': 'Actual Chrome print output, text completeness and rendered page identity. Visual inspection is separate.'}
    (ROOT / 'paper/generated/briefing-print-verification.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print('PASS: 5 printed pages contain all stages, key times, results and discussion questions; controls excluded.')


if __name__ == '__main__':
    main()
