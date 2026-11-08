// Read-only browser checks of the authored report; no facility or policy calls.
import {spawn} from 'node:child_process';
import {existsSync,readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {pathToFileURL} from 'node:url';
const base=resolve('paper/mentor-review-20261108'),qa=join(base,'qa');mkdirSync(qa);
const profile=resolve('.work/mentor-report-cdp-01'),portFile=join(profile,'DevToolsActivePort');
if(existsSync(profile))throw Error('Use a fresh QA browser profile');
const browser=spawn('C:/Program Files/Google/Chrome/Application/chrome.exe',[
 '--headless=new','--disable-gpu','--disable-background-networking','--no-first-run','--no-default-browser-check',
 '--remote-debugging-port=0','--remote-debugging-address=127.0.0.1','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
const wait=ms=>new Promise(r=>setTimeout(r,ms));let ws;
try{
 for(let i=0;i<70&&!existsSync(portFile);i++)await wait(100);
 const port=readFileSync(portFile,'utf8').split(/\r?\n/)[0];
 const tabs=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();
 ws=new WebSocket(tabs.find(t=>t.type==='page').webSocketDebuggerUrl);
 await new Promise((r,j)=>{ws.addEventListener('open',r,{once:true});ws.addEventListener('error',j,{once:true})});
 let id=0;const pending=new Map(),events=new Map(),errors=[];
 ws.addEventListener('message',ev=>{const m=JSON.parse(ev.data);if(m.id){const p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(m.error):p.resolve(m.result)}}
  else if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.text);
  else if(events.has(m.method)){events.get(m.method)(m.params);events.delete(m.method)}});
 const call=(method,params={})=>new Promise((r,j)=>{const next=++id;pending.set(next,{resolve:r,reject:j});ws.send(JSON.stringify({id:next,method,params}))});
 const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r));return r.result.value};
 const shot=async name=>{const s=await call('Page.captureScreenshot',{format:'png',fromSurface:true});writeFileSync(join(qa,name),Buffer.from(s.data,'base64'),{flag:'wx'})};
 await call('Page.enable');await call('Runtime.enable');const results=[];
 for(const[name,width,height,mobile]of[['desktop',1440,1100,false],['phone',412,1050,true],['wide',1920,1200,false]]){
  await call('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile,screenWidth:width,screenHeight:height});
  const loaded=new Promise(r=>events.set('Page.loadEventFired',r));
  await call('Page.navigate',{url:pathToFileURL(join(base,'AegisDC-导师研究报告.html')).href});await Promise.race([loaded,wait(3500)]);
  const facts=await evaluate(`(async()=>{await document.fonts.ready;const imgs=[...document.querySelectorAll('figure img')];await Promise.all(imgs.map(i=>i.decode()));return{viewport:innerWidth,clientWidth:document.documentElement.clientWidth,pageWidth:document.documentElement.scrollWidth,images:imgs.map(i=>i.naturalWidth),formulas:document.querySelectorAll('math').length,formulaHeights:[...document.querySelectorAll('math')].map(m=>Math.round(m.getBoundingClientRect().height)),parameters:document.querySelectorAll('[data-param]').length,downloads:document.querySelectorAll('a[download]').length,sources:document.querySelectorAll('.source-list li').length,externalRuntime:document.querySelectorAll('script[src],link[rel=stylesheet],iframe').length,brokenAnchors:[...document.querySelectorAll('a[href^="#"]')].filter(a=>!document.getElementById(a.getAttribute('href').slice(1))).length}})()`);
  if(facts.viewport!==width||facts.pageWidth!==facts.clientWidth||facts.images.length!==15||facts.images.some(v=>!v)||facts.formulas!==8||facts.formulaHeights.some(v=>v<20)||facts.parameters!==113||facts.downloads!==23||facts.sources!==21||facts.externalRuntime!==0||facts.brokenAnchors)throw Error('Layout:'+JSON.stringify(facts));
  if(name!=='wide')await shot(name+'-top.png');
  for(const anchor of (name==='desktop'?['figure-systems','equations','value','primary']:name==='phone'?['equations','value','primary']:[])){
   await evaluate(`document.getElementById('${anchor}').scrollIntoView();true`);await wait(80);await shot(name+'-'+anchor+'.png');
  }
  const interactions=await evaluate(`(()=>{const details=document.getElementById('parameters-full');details.open=true;const s=document.getElementById('parameter-search');s.value='flow';s.dispatchEvent(new Event('input'));const filtered=[...document.querySelectorAll('[data-param]')].filter(r=>!r.hidden).length;s.value='';s.dispatchEvent(new Event('input'));const restored=[...document.querySelectorAll('[data-param]')].filter(r=>!r.hidden).length;details.open=false;document.querySelector('#figure-value [data-zoom]').click();return{filtered,restored,zoomOpen:document.getElementById('zoom').open}})()`);
  if(interactions.filtered<=0||interactions.filtered>=113||interactions.restored!==113||!interactions.zoomOpen)throw Error('Interaction:'+JSON.stringify(interactions));
  await evaluate(`(async()=>{await document.querySelector('#zoom img').decode();return true})()`);
  if(name==='phone')await shot('phone-zoom.png');
  await evaluate(`document.getElementById('zoom-close').click();window.scrollTo(0,0);true`);
  results.push({name,...facts,...interactions});
 }
 if(errors.length)throw Error('JavaScript:'+errors.join(','));
 writeFileSync(join(qa,'responsive-qa.json'),JSON.stringify({status:'PASS_MENTOR_REPORT_THREE_VIEWPORTS',results,javascript_errors:errors,new_physical_calls:0,new_selector_calls:0,new_research_trials:0},null,2)+'\n',{flag:'wx'});
 console.log(JSON.stringify({status:'PASS_MENTOR_REPORT_THREE_VIEWPORTS',viewports:results.map(r=>[r.name,r.viewport]),figures:15,formulas:8,parameters:113,downloads:23}));ws.close();
}finally{browser.kill()}
