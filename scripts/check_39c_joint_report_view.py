"""View the report in preinstalled headless Edge; no project evaluation or dependencies."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'docs/mainline/39c-joint-checkpoint-20261110.html'
BROWSER = Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')

HOOK = r'''<script>
window.addEventListener('load',async()=>{const wait=()=>new Promise(r=>setTimeout(r,40));const images=[...document.querySelectorAll('img[data-zoom]')];const q={viewport:[innerWidth,innerHeight],dpr:devicePixelRatio,bodyWidth:document.documentElement.scrollWidth,imageCount:images.length,imagesLoaded:images.every(i=>i.complete&&i.naturalWidth>2000),errors:window.__reportQaErrors||[]};
if(new URLSearchParams(location.search).get('mode')==='zoom'){
const dialog=document.getElementById('figure-dialog'),image=document.getElementById('figure-image'),box=document.getElementById('figure-scroll');images[0].click();q.opened=dialog.open;let initial=parseFloat(image.style.width);document.getElementById('zoom-in').click();q.zoomIncreased=parseFloat(image.style.width)>initial;document.getElementById('zoom-fit').click();await wait();q.fitNoHorizontalOverflow=box.scrollWidth<=box.clientWidth+2;document.getElementById('zoom-close').click();await wait();q.closed=!dialog.open;q.focusReturned=document.activeElement===images[0];images[0].dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));q.keyboardOpened=dialog.open;document.getElementById('zoom-in').click();await wait();const r=dialog.getBoundingClientRect();q.dialogWithinViewport=r.left>=0&&r.top>=0&&r.right<=innerWidth+1&&r.bottom<=innerHeight+1;q.buttonsWithinDialog=[...dialog.querySelectorAll('button')].every(b=>{const z=b.getBoundingClientRect();return z.left>=r.left&&z.right<=r.right&&z.bottom<=r.bottom});q.finalImageWidth=parseFloat(image.style.width);q.panAvailable=box.scrollWidth>box.clientWidth;
}q.errors=window.__reportQaErrors||[];parent.document.getElementById('report-qa-result').textContent=JSON.stringify(q);parent.document.documentElement.dataset.qaComplete='true';});
</script>'''


class QaOutput(HTMLParser):
    def __init__(self):
        super().__init__();self.active=False;self.data=[]
    def handle_starttag(self,tag,attrs):
        if tag=='output' and dict(attrs).get('id')=='report-qa-result':self.active=True
    def handle_endtag(self,tag):
        if tag=='output':self.active=False
    def handle_data(self,data):
        if self.active:self.data.append(data)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--browser-version',required=True)
    args=parser.parse_args()
    if sys.platform!='win32' or not BROWSER.is_file():raise SystemExit('Use the existing Windows Edge viewer only')
    output=(ROOT/args.output).resolve()
    if not output.is_relative_to(ROOT/'.work'):raise SystemExit('Put temporary viewer profiles inside project .work')
    output.mkdir(parents=True,exist_ok=False)
    raw=SOURCE.read_bytes();source=raw.decode('utf-8')
    source=source.replace('<title>','<script>window.__reportQaErrors=[];window.addEventListener("error",e=>window.__reportQaErrors.push(String(e.message||"resource error")));</script><title>',1)
    child=output/'report-child.html';child.write_text(source.replace('</html>',HOOK+'</html>'),encoding='utf-8',newline='\n')
    rows=[]
    for name,width,height,mode in [('mobile',390,844,'default'),('desktop',1440,1000,'default'),('mobile-zoom',390,844,'zoom')]:
        frame=output/(name+'.html');relative=child.relative_to(ROOT).as_posix()
        frame.write_text(f'<!doctype html><html><style>html,body{{margin:0;background:#e3e8ee}}iframe{{display:block;border:0;width:{width}px;height:{height}px}}</style><output hidden id="report-qa-result"></output><iframe title="Report viewport" src="/{relative}?mode={mode}"></iframe></html>',encoding='utf-8',newline='\n')
        screenshot=output/(name+'.png');profile=output/('profile-'+name)
        url='http://127.0.0.1:18756/'+frame.relative_to(ROOT).as_posix()
        command=[str(BROWSER),'--headless=new','--disable-gpu','--disable-background-networking','--disable-extensions',
            '--no-first-run','--no-default-browser-check','--disable-sync','--force-device-scale-factor=1',
            '--user-data-dir='+str(profile),f'--window-size={max(width+80,700)},{height+200}',
            '--virtual-time-budget=5000','--screenshot='+str(screenshot),'--dump-dom',url]
        run=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45,creationflags=subprocess.CREATE_NO_WINDOW)
        (output/(name+'-stderr.log')).write_bytes(run.stderr)
        html=run.stdout.decode('utf-8',errors='replace');parsed=QaOutput();parsed.feed(html)
        (output/(name+'-dom.html')).write_text(html,encoding='utf-8',newline='\n')
        if run.returncode or not screenshot.is_file() or not parsed.data:raise RuntimeError(name+' browser view did not complete')
        observed=json.loads(''.join(parsed.data));passed=(observed['viewport']==[width,height] and observed['bodyWidth']<=width+1
            and observed['imageCount']==2 and observed['imagesLoaded'] and not observed['errors'])
        if mode=='zoom':passed=passed and all(observed.get(k) for k in ('opened','zoomIncreased','fitNoHorizontalOverflow','closed','focusReturned','keyboardOpened','dialogWithinViewport','buttonsWithinDialog','panAvailable'))
        rows.append(dict(case=name,requested_viewport=[width,height],observed=observed,passed=bool(passed),
            screenshot=screenshot.relative_to(ROOT).as_posix(),screenshot_sha256=hashlib.sha256(screenshot.read_bytes()).hexdigest(),
            process_exit_code=run.returncode))
    record=dict(classification='LOCAL_RESULT_VIEW_ONLY_NOT_PROJECT_COMPUTATION',browser=str(BROWSER),browser_version=args.browser_version,
        report=SOURCE.relative_to(ROOT).as_posix(),report_sha256=hashlib.sha256(raw).hexdigest(),
        viewer_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),cases=rows,all_passed=all(r['passed'] for r in rows),
        source_report_unchanged=(SOURCE.read_bytes()==raw),new_facility_calls=0,new_research_trials=0,
        visual_review='PENDING_SCREENSHOT_VIEW')
    (output/'receipt.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(record,ensure_ascii=False))
    if not record['all_passed']:raise SystemExit('Browser layout or public zoom interaction failed;retain observations')


if __name__=='__main__':main()
