"""Export the finite saved-data checkpoint to one offline HTML; standard library only."""

import base64
import hashlib
import html
import json
from pathlib import Path
import re
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'docs/mainline/39c-review-checkpoint-20261110.md'
OUTPUT = SOURCE.with_suffix('.html')
SOURCES = {}


def read(path):
    data = path.read_bytes()
    SOURCES[path.relative_to(ROOT).as_posix()] = dict(
        bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    return data


def target(value):
    if value.startswith(('https://', 'http://', '#')):
        return value
    path = (SOURCE.parent/value).resolve().relative_to(ROOT).as_posix()
    return 'https://github.com/DonsonHH/AegisDC/blob/donson/mainline-39c-endpoints/' + quote(path, safe='/')


def inline(value):
    value = html.escape(value)
    value = re.sub(r'`([^`]+)`', r'<code>\1</code>', value)
    value = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', value)
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',
                  lambda match: '<a href="' + html.escape(target(html.unescape(match[2])), quote=True)
                  + '">' + match[1] + '</a>', value)


def main():
    read(Path(__file__).resolve())
    lines = read(SOURCE).decode('utf-8').splitlines()
    parts = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith('#'):
            level = len(line) - len(line.lstrip('#'))
            parts.append(f'<h{level}>' + inline(line[level:].strip()) + f'</h{level}>')
        elif line.startswith('!['):
            match = re.fullmatch(r'!\[([^\]]*)\]\(([^)]+)\)', line)
            if match is None:
                raise ValueError('Unsupported figure markup')
            path = (SOURCE.parent/match[2]).resolve()
            raw = read(path)
            url = 'data:image/png;base64,' + base64.b64encode(raw).decode()
            parts.append('<figure><img loading="eager" src="' + url + '" alt="'
                         + html.escape(match[1], quote=True) + '"><figcaption>'
                         + inline(match[1]) + ' · 点击放大</figcaption></figure>')
        elif line.startswith('|'):
            table = []
            while i < len(lines) and lines[i].startswith('|'):
                table.append([cell.strip() for cell in lines[i].strip('|').split('|')])
                i += 1
            parts.append('<div class="table-wrap"><table><thead><tr>'
                + ''.join('<th scope="col">' + inline(cell) + '</th>' for cell in table[0])
                + '</tr></thead><tbody>'
                + ''.join('<tr>' + ''.join('<td>' + inline(cell) + '</td>' for cell in row)
                          + '</tr>' for row in table[2:]) + '</tbody></table></div>')
            continue
        else:
            parts.append('<p>' + inline(line) + '</p>')
        i += 1
    style = '''
    :root{color-scheme:light;font:16px/1.8 "Segoe UI","Microsoft YaHei",sans-serif;color:#182333;background:#f2f5f8}
    *{box-sizing:border-box}body{margin:0}main{max-width:1160px;margin:36px auto;padding:44px 56px;background:#fff;border:1px solid #e3e9ef;border-radius:18px}
    h1{font-size:clamp(26px,3.5vw,40px);line-height:1.35;margin:0 0 22px}h2{font-size:24px;margin:42px 0 16px;padding-top:18px;border-top:1px solid #e4eaf0}
    p{margin:16px 0}a{color:#1667a5;text-underline-offset:3px}code{font-size:.88em;background:#eef3f7;padding:2px 5px;border-radius:4px;overflow-wrap:anywhere}
    .table-wrap{overflow-x:auto;margin:20px 0;border:1px solid #dde5ed;border-radius:10px}table{border-collapse:collapse;width:100%;min-width:620px;font-size:15px}th,td{padding:12px 16px;vertical-align:top;text-align:left;border-bottom:1px solid #e3e9ef}th{background:#edf4fa}tbody tr:last-child td{border:0}
    figure{margin:26px 0}img{width:100%;height:auto;display:block;cursor:zoom-in;border:1px solid #e4eaf0;border-radius:9px}figcaption{font-size:13px;color:#576b7d;margin-top:8px}
    dialog{width:98vw;max-width:none;max-height:96vh;padding:12px;border:0;border-radius:10px}dialog::backdrop{background:#172230cf}dialog img{cursor:zoom-out;width:100%;border:0}dialog button{float:right;padding:8px 14px;margin-bottom:8px;cursor:pointer}
    @media(max-width:680px){main{margin:0;border:0;border-radius:0;padding:28px 18px}h2{font-size:21px}th,td{padding:10px 12px}}
    @media(min-width:1800px){main{max-width:1440px;padding:56px 72px}}
    @media print{body{background:white}main{max-width:none;margin:0;padding:0;border:0}h2{break-after:avoid}figure,table{break-inside:avoid}img{border:0}.table-wrap{overflow:visible}table{min-width:0}dialog{display:none}}
    '''
    markup = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>39c阅读检查点 · AegisDC</title><style>' + style + '</style></head><body><main>' + '\n'.join(parts) + '''</main>
    <dialog id="zoom" aria-label="图形放大"><button type="button">关闭</button><img alt=""></dialog>
    <script>const d=document.getElementById('zoom');document.querySelectorAll('figure img').forEach(img=>img.addEventListener('click',()=>{d.querySelector('img').src=img.src;d.querySelector('img').alt=img.alt;d.showModal()}));d.addEventListener('click',()=>d.close());</script></body></html>'''
    if OUTPUT.exists():
        raise FileExistsError('Checkpoint export already exists; preserve published versions')
    OUTPUT.write_text(markup, encoding='utf-8', newline='\n')
    OUTPUT.with_name(OUTPUT.stem + '-sources.json').write_text(json.dumps(dict(
        classification='OFFLINE_READING_EXPORT_NO_RESEARCH_EXECUTION', sources=SOURCES,
        output=dict(path=OUTPUT.relative_to(ROOT).as_posix(), bytes=OUTPUT.stat().st_size,
                    sha256=hashlib.sha256(OUTPUT.read_bytes()).hexdigest())), indent=2) + '\n',
        encoding='utf-8', newline='\n')
    print(json.dumps(dict(output=str(OUTPUT), figures=markup.count('<figure>'), tables=markup.count('<table>'))))


if __name__ == '__main__':
    main()
