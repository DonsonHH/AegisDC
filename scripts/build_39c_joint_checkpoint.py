"""Edit the qualified56 HTML into a portable reading page with accessible zoom."""
import base64
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'evidence/mainline/engineering/39c-development/slice-56/AegisDC-joint-checkpoint.html'
OUTPUT = ROOT/'docs/mainline/39c-joint-checkpoint-20261110.html'

STYLE = '''
img[data-zoom]{cursor:zoom-in}img[data-zoom]:focus-visible{outline:3px solid #0072b2;outline-offset:4px}
.zoom-hint{font-size:14px;color:#56677a}.figure-dialog{box-sizing:border-box;width:calc(100vw - 20px);height:calc(100vh - 24px);max-width:1800px;max-height:none;padding:16px;border:0;border-radius:12px;background:#fff;color:#233044}
.figure-dialog[open]{display:flex;flex-direction:column;overflow:hidden}.figure-dialog::backdrop{background:rgba(15,23,42,.78)}.figure-toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;justify-content:space-between;margin-bottom:12px}.figure-toolbar button{font:inherit;padding:8px 14px;border:1px solid #b8c7d6;border-radius:7px;background:#f4f7fa;cursor:pointer;min-height:44px}.figure-scroll{overflow:auto;flex:1;min-height:0;overscroll-behavior:contain;background:#eef2f6}.figure-scroll img{display:block;max-width:none;width:1200px;height:auto;background:white;touch-action:pan-x pan-y pinch-zoom}.figure-scroll.fit img{width:100%;max-width:100%}
@media print{.figure-dialog,.zoom-hint{display:none}}
'''
DIALOG = '''
<dialog id="figure-dialog" class="figure-dialog" aria-label="图表放大查看"><div class="figure-toolbar"><span id="figure-title">图表</span><div><button type="button" id="zoom-in">放大</button> <button type="button" id="zoom-out">缩小</button> <button type="button" id="zoom-fit">适应屏幕</button> <button type="button" id="zoom-close" autofocus>关闭</button></div></div><div class="figure-scroll" id="figure-scroll"><img id="figure-image" alt=""></div></dialog>
<script>
(()=>{const dialog=document.getElementById('figure-dialog'),image=document.getElementById('figure-image'),scroll=document.getElementById('figure-scroll');let width=1200,origin=null;
const setWidth=value=>{width=Math.max(400,Math.min(5000,value));scroll.classList.remove('fit');image.style.width=width+'px'};
const open=target=>{origin=target;target.focus({preventScroll:true});image.src=target.src;image.alt=target.alt;document.getElementById('figure-title').textContent=target.alt;setWidth(Math.max(1200,window.innerWidth-80));dialog.showModal();scroll.scrollTo(0,0)};
document.querySelectorAll('img[data-zoom]').forEach(target=>{target.addEventListener('click',()=>open(target));target.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();open(target)}})});
document.getElementById('zoom-in').addEventListener('click',()=>setWidth(width*1.25));document.getElementById('zoom-out').addEventListener('click',()=>setWidth(width/1.25));document.getElementById('zoom-fit').addEventListener('click',()=>{scroll.classList.add('fit');image.style.width='100%'});document.getElementById('zoom-close').addEventListener('click',()=>dialog.close());dialog.addEventListener('close',()=>{if(origin)origin.focus({preventScroll:true})});dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close()});})();
</script>
'''


def main():
    raw=SOURCE.read_bytes();text=raw.decode('utf-8')
    if text.count('<img alt=')!=2:
        raise ValueError('Expected exactly two qualified source figures')
    separator_corrections=text.count('data:image/png;base64:')
    text=text.replace('data:image/png;base64:','data:image/png;base64,')
    text=text.replace('</style>',STYLE+'</style>',1)
    text=text.replace('<img alt=', '<img data-zoom tabindex="0" role="button" alt=')
    text=text.replace('<h2>四个实际工况</h2>','<h2>四个实际工况</h2><p class="zoom-hint">点击图表可放大查看；窄屏可横向拖动大图。</p>')
    text=text.replace('href="joint-actual-data.csv"','href="../../evidence/mainline/engineering/39c-development/slice-56/joint-actual-data.csv"')
    text=text.replace('</html>',DIALOG+'</html>')
    for identifier,label in {'single-worker':'单人','crew-rendezvous':'双人：逐边门禁','no-human':'无人处置','service-unqualified':'服务证据不合格'}.items():
        text=text.replace('<td>'+identifier+'</td>','<td>'+label+'</td>')
    class InlineImages(HTMLParser):
        def __init__(self):super().__init__();self.sources=[]
        def handle_starttag(self,tag,attrs):
            if tag=='img' and dict(attrs).get('src','').startswith('data:'):self.sources.append(dict(attrs)['src'])
    images=InlineImages();images.feed(text)
    if len(images.sources)!=2:raise ValueError('Reading page must retain both complete inline figures')
    image_pins=[]
    for source,name in zip(images.sources,('joint-endpoints-and-costs.png','joint-public-private-architecture.png')):
        if not source.startswith('data:image/png;base64,'):raise ValueError('Invalid data URL separator')
        decoded=base64.b64decode(source.split(',',1)[1],validate=True)
        native=(SOURCE.parent/name).read_bytes()
        if decoded!=native:raise ValueError('Inline figure differs from the verified native PNG')
        image_pins.append(dict(path=(SOURCE.parent/name).relative_to(ROOT).as_posix(),sha256=hashlib.sha256(native).hexdigest()))
    OUTPUT.write_text(text,encoding='utf-8',newline='\n')
    declared=[SOURCE,ROOT/'evidence/mainline/engineering/39c-development/slice-56/joint-actual-data.csv',
        *[SOURCE.parent/name for name in ('joint-endpoints-and-costs.png','joint-public-private-architecture.png')],Path(__file__).resolve()]
    record=dict(schema='aegisdc-reading-page-source-v1',classification='DOCUMENT_AUTHORING_ONLY_NO_SIMULATION',
        sources={path.relative_to(ROOT).as_posix():dict(bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in declared},
        output=dict(path=OUTPUT.relative_to(ROOT).as_posix(),bytes=OUTPUT.stat().st_size,sha256=hashlib.sha256(OUTPUT.read_bytes()).hexdigest()),
        native56_html_unchanged=(SOURCE.read_bytes()==raw),data_url_separator_corrections=separator_corrections,
        inline_png_byte_identities=image_pins,new_facility_calls=0,new_research_trials=0,
        scope='Correct native HTML data URL delimiter in the derivative reading page;add Chinese case labels,reading layout,zoom and CSV link. Native files/data remain intact.')
    (ROOT/'docs/mainline/39c-joint-checkpoint-20261110-sources.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(record['output']))


if __name__=='__main__':main()
