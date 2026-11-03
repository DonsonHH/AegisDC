/* Render the standalone case report in an isolated, headless Chrome profile. */
const fs=require('node:fs');
const path=require('node:path');
const {spawn}=require('node:child_process');
const {pathToFileURL}=require('node:url');
const crypto=require('node:crypto');
const root=process.cwd();
const pack=path.join(root,'docs/research/20261104/facility-cases');
const work=path.join(root,'.work/facility-cases-20261104/browser');
const evidence=path.join(root,'evidence/facility-case-models-20261104');
const previews=path.join(evidence,'previews');
fs.mkdirSync(work,{recursive:true});fs.mkdirSync(previews,{recursive:true});
const profile=path.join(work,'profile-'+Date.now());
const standalone=path.join(work,'offline');fs.mkdirSync(standalone,{recursive:true});
fs.copyFileSync(path.join(pack,'report.html'),path.join(standalone,'report.html'));
const chrome=spawn('C:/Program Files/Google/Chrome/Application/chrome.exe',[
  '--headless','--disable-gpu','--no-first-run','--no-default-browser-check',
  '--disable-extensions','--disable-background-networking','--user-data-dir='+profile,
  '--remote-debugging-port=0','about:blank'],{windowsHide:true,stdio:'ignore'});
const pause=ms=>new Promise(r=>setTimeout(r,ms));
const assert=(condition,message)=>{if(!condition)throw new Error(message)};
let socket,sequence=0;const pending=new Map();
const report={scope:'Browser layout and interaction checks; no field/dynamic validation',viewports:[],figures:[],interactions:{},externalRequests:[],exceptions:[],screenshots:{}};
function send(method,params={}){return new Promise((resolve,reject)=>{
  const id=++sequence;const timer=setTimeout(()=>{pending.delete(id);reject(new Error('CDP timeout: '+method))},12000);
  pending.set(id,{resolve,reject,timer});socket.send(JSON.stringify({id,method,params}));
})}
async function evaluate(expression){const result=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(result.exceptionDetails)throw new Error(JSON.stringify(result.exceptionDetails));return result.result.value}
async function waitFor(expression){for(let i=0;i<90;i++){if(await evaluate(expression))return;await pause(60)}throw new Error('Browser condition not met: '+expression)}
async function click(selector){await evaluate(`document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block:'center'})`);const p=await evaluate(`(()=>{const r=document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`);await send('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...p});await send('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...p})}
async function screenshot(name){const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});const file=path.join(previews,name+'.png');fs.writeFileSync(file,Buffer.from(shot.data,'base64'));report.screenshots[path.relative(root,file).replaceAll('\\','/')]=crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')}
async function viewport(width,height){await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false});await pause(100)}
async function navigate(url){await send('Page.navigate',{url});await waitFor('document.readyState==="complete"');await evaluate('document.fonts.ready.then(()=>true)')}
(async()=>{try{
  const portFile=path.join(profile,'DevToolsActivePort');
  for(let i=0;i<100&&!fs.existsSync(portFile);i++){assert(chrome.exitCode===null,'Chrome exited early');await pause(100)}
  const port=fs.readFileSync(portFile,'utf8').split(/\r?\n/)[0];
  const tabs=await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  socket=new WebSocket(tabs.find(t=>t.type==='page').webSocketDebuggerUrl);
  socket.onmessage=event=>{const msg=JSON.parse(event.data);if(msg.id&&pending.has(msg.id)){const entry=pending.get(msg.id);clearTimeout(entry.timer);pending.delete(msg.id);msg.error?entry.reject(new Error(msg.error.message)):entry.resolve(msg.result)}else if(msg.method==='Runtime.exceptionThrown'){report.exceptions.push(msg.params.exceptionDetails)}else if(msg.method==='Network.requestWillBeSent'&&/^https?:/.test(msg.params.request.url)){report.externalRequests.push(msg.params.request.url)}};
  await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject});
  await send('Page.enable');await send('Runtime.enable');await send('Network.enable');
  await navigate(pathToFileURL(path.join(standalone,'report.html')).href);
  for(const [width,height] of [[320,900],[390,844],[768,1024],[1440,1000],[1920,1080]]){
    await viewport(width,height);await evaluate('scrollTo(0,0)');
    const state=await evaluate(`(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,figures:document.querySelectorAll('figure').length,parameters:document.querySelectorAll('.parameters tbody tr').length,math:document.querySelectorAll('math').length,zeroHeightMath:[...document.querySelectorAll('math')].filter(m=>m.getBoundingClientRect().height<10).length,brokenImages:[...document.images].filter(i=>!i.complete||!i.naturalWidth).length}))()`);
    assert(state.scrollWidth<=width+1,'Page overflow at '+width);assert(state.figures===8&&state.parameters===103&&state.math===28,'Report completeness mismatch');assert(state.zeroHeightMath===0&&state.brokenImages===0,'Math/image rendering failed');report.viewports.push(state);
    if([390,1440,1920].includes(width))await screenshot('report-'+width);
  }
  await viewport(390,844);
  const filterResult=await evaluate(`(()=>{const f=document.querySelector('#parameter-filter');f.value='gaps';f.dispatchEvent(new Event('change',{bubbles:true}));return{visible:document.querySelectorAll('.parameters tbody tr:not([hidden])').length,documentedVisible:[...document.querySelectorAll('.parameters tbody tr:not([hidden])')].filter(r=>r.dataset.availability==='documented').length}})()`);
  assert(filterResult.visible>0&&filterResult.visible<103&&filterResult.documentedVisible===0,'Missing-data filter failed');report.interactions.filter=filterResult;
  await click('.zoom');await waitFor('document.querySelector("#figure-dialog").open');
  const modal=await evaluate(`(()=>{const ids=[...document.querySelectorAll('[id]')].map(e=>e.id);return{open:document.querySelector('#figure-dialog').open,svg:document.querySelectorAll('#figure-canvas svg').length,duplicateIds:ids.length-new Set(ids).size,pageWidth:document.documentElement.scrollWidth,width:innerWidth}})()`);
  assert(modal.svg===1&&modal.duplicateIds===0&&modal.pageWidth<=modal.width+1,'Zoom dialog failed');
  await screenshot('mobile-figure-dialog');
  await evaluate(`(()=>{const s=document.querySelector('#figure-scale');s.value='120';s.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  assert(await evaluate('document.querySelector("#figure-canvas svg").getBoundingClientRect().width>1400'),'Figure scaling failed');
  await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',windowsVirtualKeyCode:27});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',windowsVirtualKeyCode:27});await waitFor('!document.querySelector("#figure-dialog").open');
  assert(await evaluate('document.activeElement.classList.contains("zoom")'),'Dialog focus did not restore');report.interactions.zoom={...modal,scale:'PASS',escapeAndFocusRestore:'PASS'};
  await viewport(1440,1000);
  for(const [prefix,name] of [['A4','equations-water'],['D2','equations-plate-hx'],['D3','equations-phase-change']]){
    await evaluate(`([...document.querySelectorAll('.equation-chapter h3')].find(h=>h.textContent.startsWith(${JSON.stringify(prefix)}))).scrollIntoView({block:'start'})`);
    await screenshot(name);
  }
  await evaluate(`document.querySelector('#el-capitan .subhead').scrollIntoView({block:'start'})`);await screenshot('parameters-desktop');
  const book=JSON.parse(fs.readFileSync(path.join(pack,'casebook.json'),'utf8'));
  const diagrams=[...book.cases.flatMap(c=>c.diagrams),...book.shared_diagrams];
  for(const d of diagrams){
    await viewport(d.width,d.height);await navigate(pathToFileURL(path.join(pack,'figures',d.id+'.svg')).href);
    const result=await evaluate(`(()=>{const s=document.documentElement.viewBox.baseVal;const outside=[];const nodeOutside=[];for(const t of document.querySelectorAll('text')){const b=t.getBBox();if(b.x<0||b.y<0||b.x+b.width>s.width+2||b.y+b.height>s.height+2)outside.push(t.textContent)}for(const g of document.querySelectorAll('[data-node]')){const r=g.querySelector('rect');const b={x:+r.getAttribute('x'),y:+r.getAttribute('y'),w:+r.getAttribute('width'),h:+r.getAttribute('height')};for(const t of g.querySelectorAll('text')){const a=t.getBBox();if(a.x<b.x-1||a.y<b.y-1||a.x+a.width>b.x+b.w+1||a.y+a.height>b.y+b.h+1)nodeOutside.push(t.textContent)}}return{outside,nodeOutside,nodes:document.querySelectorAll('[data-node]').length,edges:document.querySelectorAll('[data-edge]').length}})()`);
    assert(result.outside.length===0&&result.nodeOutside.length===0,'Figure text clipping: '+d.id+' '+JSON.stringify(result));report.figures.push({id:d.id,...result});await screenshot(d.id);
  }
  assert(report.externalRequests.length===0,'Offline report requested network resources');assert(report.exceptions.length===0,'Browser exception');
  report.status='PASS';report.html_sha256=crypto.createHash('sha256').update(fs.readFileSync(path.join(pack,'report.html'))).digest('hex');
  fs.writeFileSync(path.join(evidence,'browser-verification.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({status:report.status,viewports:report.viewports.length,figures:report.figures.length,externalRequests:report.externalRequests.length,screenshots:Object.keys(report.screenshots).length}));
}catch(error){report.status='FAIL';report.error=String(error);fs.writeFileSync(path.join(work,'failure.json'),JSON.stringify(report,null,2));console.error(error);process.exitCode=1}finally{if(socket)socket.close();chrome.kill();}})();
