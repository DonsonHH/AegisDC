/* Browser checks for the offline report. Uses Node built-ins and an installed Chrome. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {spawn} = require('node:child_process');
const {pathToFileURL} = require('node:url');

const root = process.cwd();
const work = path.join(root, '.work/briefing-v2-browser');
const previews = path.join(root, 'paper/generated/briefing-previews');
fs.mkdirSync(work, {recursive:true});
fs.mkdirSync(previews, {recursive:true});
const htmlPath = path.join(root, 'paper/supervisor-briefing.html');
const copiedHtml = path.join(work, 'standalone.html');
fs.copyFileSync(htmlPath, copiedHtml);
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const report = {
  html_sha256: hash(htmlPath), manifest_sha256:hash(path.join(root, 'paper/generated/briefing-manifest.json')),
  checker_sha256:hash(__filename), offline_single_file:true, viewports:[], interactions:{},
  externalRequests:[], exceptions:[], screenshot_sha256:{},
};
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const profile = path.join(work, 'profile-' + Date.now());
const browserPath = process.env.BRIEFING_CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const chrome = spawn(browserPath, ['--headless','--disable-gpu','--no-first-run','--no-default-browser-check',
  '--user-data-dir='+profile,'--remote-debugging-port=0','about:blank'], {windowsHide:true,stdio:'ignore'});
let socket;
let nextId=0;
const pending=new Map();
function assert(value,message){if(!value)throw new Error(message);}
function send(method,params={}){
  return new Promise((resolve,reject)=>{
    const id=++nextId;
    const timer=setTimeout(()=>{pending.delete(id);reject(new Error('CDP timeout: '+method));},8000);
    pending.set(id,{resolve,reject,timer});socket.send(JSON.stringify({id,method,params}));
  });
}
async function evaluate(expression){
  const result=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});
  if(result.exceptionDetails)throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
async function waitFor(expression){
  for(let i=0;i<100;i++){if(await evaluate(expression))return;await delay(50);}
  throw new Error('Browser condition not met: '+expression);
}
async function click(selector){
  const location=await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`);
  await send('Input.dispatchMouseEvent',{type:'mousePressed',...location,button:'left',clickCount:1});
  await send('Input.dispatchMouseEvent',{type:'mouseReleased',...location,button:'left',clickCount:1});
}
async function key(key,code){
  await send('Input.dispatchKeyEvent',{type:'keyDown',key,windowsVirtualKeyCode:code});
  await send('Input.dispatchKeyEvent',{type:'keyUp',key,windowsVirtualKeyCode:code});
}
async function screen(number){
  await evaluate(`location.hash='#screen-${number}'`);
  await waitFor(`document.querySelector('.slide.is-active').id==='screen-${number}'`);
  await evaluate('document.fonts.ready.then(()=>true)');
  await delay(80);
}
async function inspect(width,height,number){
  const result=await evaluate(`(()=>{
    const s=document.querySelector('.slide.is-active');
    const toolbar=document.querySelector('.toolbar').getBoundingClientRect();
    const outside=[];const sizes=[];const graphicOverflow=[];const textOverlaps=[];
    for(const svg of s.querySelectorAll('svg')){
      const v=svg.viewBox.baseVal;const m=svg.getScreenCTM();
      const bounds=svg.getBoundingClientRect();
      const stage=(svg.closest('.visual-pair,.visual-single')||svg.closest('figure')).getBoundingClientRect();
      if(bounds.bottom>stage.bottom+1||bounds.right>stage.right+1||bounds.top<stage.top-1)graphicOverflow.push(svg.dataset.chart);
      const boxes=[];
      for(const t of svg.querySelectorAll('text')){
        const b=t.getBBox();const size=parseFloat(getComputedStyle(t).fontSize)*Math.hypot(m.a,m.b);
        sizes.push(size);
        boxes.push({text:t.textContent,...{x:b.x,y:b.y,width:b.width,height:b.height}});
        if(b.x<v.x-1||b.y<v.y-1||b.x+b.width>v.x+v.width+1||b.y+b.height>v.y+v.height+1)outside.push(t.textContent);
      }
      for(let i=0;i<boxes.length;i++)for(let j=i+1;j<boxes.length;j++){
        const a=boxes[i],b=boxes[j];
        if(Math.min(a.x+a.width,b.x+b.width)-Math.max(a.x,b.x)>2&&Math.min(a.y+a.height,b.y+b.height)-Math.max(a.y,b.y)>2)textOverlaps.push([a.text,b.text]);
      }
    }
    return{screen:s.id,title:s.querySelector('h1').textContent,width:innerWidth,height:innerHeight,
      documentWidth:document.documentElement.scrollWidth,documentHeight:document.documentElement.scrollHeight,
      visibleScreens:[...document.querySelectorAll('.slide')].filter(e=>!e.hidden&&getComputedStyle(e).display!=='none').length,
      toolbarTop:toolbar.top,sourceBottom:s.querySelector('.source-row').getBoundingClientRect().bottom,
      minimumSvgTextPx:Math.min(...sizes),svgTextOutsideViewBox:outside,graphicOverflow,svgTextOverlaps:textOverlaps,
      nativeFigures:s.querySelectorAll('[data-native]').length,notesVisible:!!document.querySelector('dialog[open]')};
  })()`);
  report.viewports.push(result);
  const file=path.join(previews,`${width}x${height}-screen-${number}.png`);
  const screenshot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
  fs.writeFileSync(file,Buffer.from(screenshot.data,'base64'));
  report.screenshot_sha256[path.relative(root,file).replaceAll('\\','/')]=hash(file);
  assert(result.visibleScreens===1,'Visible screen count');
  assert(result.documentWidth<=width,'Horizontal overflow');
  assert(result.documentHeight<=height,'Vertical scroll: '+number+' at '+width);
  assert(result.sourceBottom<result.toolbarTop-5,'Bottom controls cover content');
  assert(result.svgTextOutsideViewBox.length===0,'SVG text clipped: '+JSON.stringify(result.svgTextOutsideViewBox));
  assert(result.graphicOverflow.length===0,'Graphic overflows its allocated area: '+JSON.stringify(result.graphicOverflow));
  assert(result.svgTextOverlaps.length===0,'SVG labels overlap: '+JSON.stringify(result.svgTextOverlaps));
  assert(result.minimumSvgTextPx>=15,'SVG text too small');
}

(async()=>{
  try{
    const portFile=path.join(profile,'DevToolsActivePort');
    for(let i=0;i<100&&!fs.existsSync(portFile);i++){
      assert(chrome.exitCode===null,'Chrome stopped before debugger opened');await delay(100);
    }
    assert(fs.existsSync(portFile),'Chrome debugger not available');
    const port=fs.readFileSync(portFile,'utf8').split('\n')[0].trim();
    const tabs=await(await fetch(`http://127.0.0.1:${port}/json/list`)).json();
    socket=new WebSocket(tabs.find(t=>t.type==='page').webSocketDebuggerUrl);
    await new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true});});
    socket.addEventListener('message',event=>{
      const packet=JSON.parse(event.data);
      if(packet.id){
        const r=pending.get(packet.id);if(!r)return;clearTimeout(r.timer);pending.delete(packet.id);
        packet.error?r.reject(new Error(JSON.stringify(packet.error))):r.resolve(packet.result);
      }else if(packet.method==='Runtime.exceptionThrown')report.exceptions.push(packet.params);
      else if(packet.method==='Network.requestWillBeSent'&&/^https?:/.test(packet.params.request.url))report.externalRequests.push(packet.params.request.url);
    });
    report.browser=await send('Browser.getVersion');
    await send('Page.enable');await send('Runtime.enable');await send('Network.enable');
    await send('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:-1,uploadThroughput:-1});
    await send('Emulation.setDeviceMetricsOverride',{width:1366,height:768,deviceScaleFactor:1,mobile:false});
    await send('Page.navigate',{url:pathToFileURL(copiedHtml).href});
    await waitFor(`document.readyState==='complete'&&document.querySelectorAll('.slide').length===5`);
    for(const [width,height] of [[1366,768],[1920,1080]]){
      await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false});
      for(let number=1;number<=5;number++){await screen(number);await inspect(width,height,number);}
    }
    report.interactions.dataGraphics=await evaluate(`(()=>{
      const bars=[...document.querySelectorAll('[data-method]')].map(e=>[e.dataset.method,Number(e.dataset.count)]);
      return document.querySelectorAll('main [data-rack]').length===128&&document.querySelectorAll('main [data-agent]').length===18&&
        JSON.stringify(bars)===JSON.stringify([['tour',28],['fifo',70],['shuffled',25]])&&document.querySelectorAll('main [data-case]').length===12&&document.querySelectorAll('main [data-rule-sha]').length===9;
    })()`);
    report.interactions.twoDiscussionQuestions=await evaluate(`document.querySelectorAll('#screen-5 .discussion li').length===2`);
    await key('Home',36);await waitFor(`document.querySelector('.slide.is-active').id==='screen-1'`);
    report.interactions.firstPreviousDisabled=await evaluate(`document.querySelector('#previous').disabled`);
    await click('#next');await waitFor(`document.querySelector('.slide.is-active').id==='screen-2'`);
    await key('ArrowRight',39);await waitFor(`document.querySelector('.slide.is-active').id==='screen-3'`);
    await key('ArrowLeft',37);await waitFor(`document.querySelector('.slide.is-active').id==='screen-2'`);
    report.interactions.arrowsAndButtons=true;
    await key('5',53);await waitFor(`document.querySelector('.slide.is-active').id==='screen-5'`);
    report.interactions.lastNextDisabled=await evaluate(`document.querySelector('#next').disabled`);
    await key('n',78);await waitFor(`document.querySelector('#notes-dialog').open`);
    report.interactions.notesMatchScreen=await evaluate(`document.querySelector('#notes-title').textContent.includes('第5屏')&&document.querySelector('.notes-section.is-active').textContent.includes('9条登记规则')`);
    await key('ArrowLeft',37);
    report.interactions.dialogBlocksSlideNavigation=await evaluate(`document.querySelector('.slide.is-active').id==='screen-5'`);
    await key('Escape',27);await waitFor(`!document.querySelector('#notes-dialog').open`);
    await key('q',81);await waitFor(`document.querySelector('#materials-dialog').open`);
    await click('#materials-dialog summary');
    report.interactions.faq=await evaluate(`document.querySelectorAll('#materials-dialog details').length===8&&document.querySelector('#materials-dialog details').open`);
    report.interactions.pinnedSources=await evaluate(`[...document.querySelectorAll('#materials-dialog a')].every(a=>/d011e3229d65c03da1ebd0765e1c1c6fe829fff3|958e777c3a229bdabfe4e9448d6c2c01bc35b82a/.test(a.href))`);
    await key('Escape',27);await waitFor(`!document.querySelector('#materials-dialog').open`);
    for(const [number,keyName] of [[2,'framework'],[3,'paired'],[4,'timeline']]){
      await screen(number);await click(`#screen-${number} [data-figure="${keyName}"]`);
      await waitFor(`document.querySelector('#figure-dialog').open&&document.querySelector('#large-figure').complete&&document.querySelector('#large-figure').naturalWidth>0`);
      await click('#figure-zoom');
      assert(await evaluate(`document.querySelector('#figure-viewport').classList.contains('is-zoomed')`),'Original figure zoom');
      await key('Escape',27);await waitFor(`!document.querySelector('#figure-dialog').open`);
    }
    report.interactions.threeOriginalFigures=true;
    for(let number=1;number<=5;number++){
      await screen(number);
      const count=await evaluate(`document.querySelectorAll('#screen-${number} [data-native]').length`);
      for(let i=1;i<=count;i++){
        // Find by DOM index so the fifth screen's mixed layout is handled too.
        await evaluate(`document.querySelectorAll('#screen-${number} [data-native]')[${i-1}].id='native-check-target'`);
        await click('#native-check-target');
        await waitFor(`document.querySelector('#figure-dialog').open&&document.querySelector('#large-figure').complete&&document.querySelector('#large-figure').naturalWidth>0`);
        await key('Escape',27);await waitFor(`!document.querySelector('#figure-dialog').open`);
        await evaluate(`document.querySelector('#native-check-target').removeAttribute('id')`);
      }
    }
    report.interactions.nineNativeFigures=true;
    await screen(4);
    report.interactions.caseTimingBoundary=await evaluate(`document.querySelector('#screen-4').textContent.includes('665秒已派出例行检查，685秒才出现风险提示')`);
    await click('#fullscreen');await waitFor('!!document.fullscreenElement');
    await click('#fullscreen');await waitFor('!document.fullscreenElement');report.interactions.fullscreen=true;
    await send('Page.navigate',{url:pathToFileURL(copiedHtml).href+'#screen-5'});
    await waitFor(`document.readyState==='complete'&&document.querySelector('.slide.is-active')?.id==='screen-5'`);
    report.interactions.directLinkToFifth=true;
    assert(Object.values(report.interactions).every(Boolean),'Interaction failure');
    assert(report.externalRequests.length===0&&report.exceptions.length===0,'Network dependency or browser error');
    assert(hash(htmlPath)===report.html_sha256,'HTML changed during browser check');
    report.status='PASS';
  }catch(error){report.status='FAIL';report.error=String(error);process.exitCode=1;}
  finally{
    report.checked_at_utc=new Date().toISOString();
    fs.writeFileSync(path.join(root,'paper/generated/briefing-browser-verification.json'),JSON.stringify(report,null,2)+'\n');
    console.log(JSON.stringify({status:report.status,error:report.error,viewports:report.viewports,interactions:report.interactions},null,2));
    if(socket?.readyState===WebSocket.OPEN){try{await send('Browser.close');}catch{}socket.close();}
    if(chrome.exitCode===null)chrome.kill();
  }
})();
